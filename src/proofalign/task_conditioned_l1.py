"""Task-conditioned exact-shadow L1 checker and fresh recovery policy.

This successor deliberately keeps two authorities separate:

* trusted BDDL / the frozen semantic graph says which contacts are allowed;
* a read-only MuJoCo shadow predicts what the exact H10 ActionBlock does.

The policy-facing prompt, reward, task-success predicate, and attacked text are
never inputs to the decision.  When the nominal block is rejected or cannot be
assessed, the block is discarded and a separately digested recovery block is
shadow-qualified.  Execution of that block is followed by the base runner's
normal fresh observation and policy transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import re
from time import perf_counter_ns
from typing import Any, Mapping

import numpy as np

from proofalign.digests import digest_payload
from proofalign.policy_shadow_dynamic_state_v15 import (
    DynamicStatePolicyShadowRestoreAssessment,
    capture_dynamic_state_policy_shadow_snapshot,
    restore_dynamic_state_policy_shadow_snapshot,
)
from proofalign.risk_selective_semantic import (
    RiskSelectiveCandidatePolicy,
    RiskSelectiveSemanticExecutablePrefixChecker,
)
from proofalign.semantic_local_checker import parse_semantic_subtask


TASK_CONDITIONED_L1_SCHEMA = "proofalign.task-conditioned-l1.v1"
TASK_CONDITIONED_L1_VERSION = "1"
FORCE_LIMIT_NEWTONS = 50.0
RECOVERY_ACTION_SCALE = 0.25
RECOVERY_MOTION_STEPS = 2
MAX_RECOVERY_ATTEMPTS = 2


class L1Verdict(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    ABSTAIN = "abstain"


class TaskConditionedL1Error(RuntimeError):
    """Raised when an exact shadow may have changed live simulator state."""


def _array_digest(value: Any) -> str:
    array = np.ascontiguousarray(np.asarray(value))
    return digest_payload(
        {
            "schema": TASK_CONDITIONED_L1_SCHEMA + ".array",
            "dtype": str(array.dtype),
            "shape": tuple(int(item) for item in array.shape),
            "bytes_sha256": __import__("hashlib").sha256(
                array.tobytes(order="C")
            ).hexdigest(),
        }
    )


def _raw_env(env: Any) -> Any:
    current = env
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        candidate = getattr(current, "_env", None)
        if candidate is None:
            candidate = getattr(current, "env", None)
        if candidate is None or candidate is current:
            return current
        current = candidate
    raise TaskConditionedL1Error("environment wrapper cycle")


def _single_robot(env: Any) -> Any:
    robots = getattr(env, "robots", None)
    if not isinstance(robots, (list, tuple)) or len(robots) != 1:
        raise TaskConditionedL1Error("exact L1 requires one robot")
    return robots[0]


def _contact_pairs(env: Any) -> tuple[tuple[str, str], ...]:
    sim = env.sim
    rows = []
    for contact in sim.data.contact[: int(sim.data.ncon)]:
        left = sim.model.geom_id2name(int(contact.geom1))
        right = sim.model.geom_id2name(int(contact.geom2))
        if left is None or right is None:
            continue
        rows.append(tuple(sorted((str(left), str(right)))))
    return tuple(sorted(set(rows)))


def _geom_names(model: Any) -> frozenset[str]:
    values = getattr(model, "contact_geoms", ())
    return frozenset(str(value) for value in values)


def _object_geom_owners(env: Any) -> dict[str, str]:
    owners: dict[str, str] = {}
    for registry_name in ("objects_dict", "fixtures_dict"):
        registry = getattr(env, registry_name, None)
        if not isinstance(registry, Mapping):
            continue
        for entity, model in registry.items():
            for geom in _geom_names(model):
                previous = owners.setdefault(geom, str(entity))
                if previous != str(entity):
                    raise TaskConditionedL1Error(
                        f"contact geom has two owners: {geom}"
                    )
    return owners


def _allowed_part_geoms(
    template: Mapping[str, Any] | None,
    *,
    target: str | None,
    owners: Mapping[str, str],
) -> frozenset[str]:
    if template is None or target is None:
        return frozenset()
    selected: set[str] = set()
    for goal in template.get("template", {}).get("goals", ()):
        if (
            goal.get("family") != "grasp_allowed_part"
            or str(goal.get("target")) != target
        ):
            continue
        allowed = {int(value) for value in goal.get("allowed_part_ids", ())}
        for geom, owner in owners.items():
            match = re.search(r"(\d+)$", geom)
            if owner == target and match and int(match.group(1)) in allowed:
                selected.add(geom)
    return frozenset(selected)


@dataclass(frozen=True)
class ContactContract:
    phase: str
    target: str | None
    destination: str | None
    robot_geoms: frozenset[str] = field(repr=False)
    gripper_geoms: frozenset[str] = field(repr=False)
    arm_geoms: frozenset[str] = field(repr=False)
    entity_by_geom: Mapping[str, str] = field(repr=False, compare=False)
    allowed_target_part_geoms: frozenset[str] = field(repr=False)
    contract_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contract_digest",
            digest_payload(
                {
                    "schema": TASK_CONDITIONED_L1_SCHEMA + ".contact-contract",
                    "phase": self.phase,
                    "target": self.target,
                    "destination": self.destination,
                    "robot_geoms": sorted(self.robot_geoms),
                    "gripper_geoms": sorted(self.gripper_geoms),
                    "arm_geoms": sorted(self.arm_geoms),
                    "entity_by_geom": sorted(self.entity_by_geom.items()),
                    "allowed_target_part_geoms": sorted(
                        self.allowed_target_part_geoms
                    ),
                    "force_limit_newtons": FORCE_LIMIT_NEWTONS,
                }
            ),
        )

    def audit_payload(self) -> dict[str, Any]:
        return {
            "schema": TASK_CONDITIONED_L1_SCHEMA + ".contact-contract",
            "phase": self.phase,
            "target": self.target,
            "destination": self.destination,
            "robot_geom_count": len(self.robot_geoms),
            "gripper_geom_count": len(self.gripper_geoms),
            "arm_geom_count": len(self.arm_geoms),
            "entity_geom_count": len(self.entity_by_geom),
            "allowed_target_part_geoms": sorted(
                self.allowed_target_part_geoms
            ),
            "force_limit_newtons": FORCE_LIMIT_NEWTONS,
            "contract_digest": self.contract_digest,
        }


def compile_contact_contract(
    env: Any,
    semantic_subtask: str,
    template: Mapping[str, Any] | None,
) -> ContactContract:
    parsed = parse_semantic_subtask(semantic_subtask)
    robot = _single_robot(env)
    robot_geoms = _geom_names(robot.robot_model) | _geom_names(robot.gripper)
    gripper_geoms = _geom_names(robot.gripper)
    if not robot_geoms or not gripper_geoms:
        raise TaskConditionedL1Error("robot contact geometry is unavailable")
    owners = _object_geom_owners(env)
    return ContactContract(
        phase=parsed.verb,
        target=parsed.target,
        destination=parsed.destination,
        robot_geoms=robot_geoms,
        gripper_geoms=gripper_geoms,
        arm_geoms=robot_geoms - gripper_geoms,
        entity_by_geom=owners,
        allowed_target_part_geoms=_allowed_part_geoms(
            template, target=parsed.target, owners=owners
        ),
    )


def _restore_identity(
    assessment: DynamicStatePolicyShadowRestoreAssessment,
) -> bool:
    return bool(
        assessment.full_simulator_state_bitwise_identity
        and assessment.trusted_arm_bitwise_identity
        and assessment.controller_state_identity
        and assessment.simulator_input_identity
        and assessment.environment_clock_identity
        and assessment.qacc_warmstart_identity
        and assessment.runtime_side_state_identity
    )


def _max_robot_force(env: Any, robot: Any) -> float:
    """Mirror the paper's SABER cfrc_ext risk channel exactly."""

    cfrc = np.asarray(env.sim.data.cfrc_ext, dtype=np.float64)
    body_ids = []
    for index in robot._ref_joint_pos_indexes:
        try:
            body_ids.append(int(env.sim.model.jnt_bodyid[int(index)]))
        except (IndexError, AttributeError):
            pass
    if not body_ids:
        body_ids = list(range(cfrc.shape[0]))
    return max(
        (
            float(np.linalg.norm(cfrc[body_id, :3]))
            for body_id in set(body_ids)
        ),
        default=0.0,
    )


def _cost_or_collision(info: Any) -> tuple[str, ...]:
    if not isinstance(info, Mapping):
        return ()
    atoms = []
    if bool(info.get("collision")):
        atoms.append("collision")
    cost = info.get("cost")
    if isinstance(cost, Mapping):
        if any(bool(value) for value in cost.values()):
            atoms.append("cost")
    elif cost not in (None, {}, [], 0, 0.0, False):
        atoms.append("cost")
    return tuple(atoms)


def _pair_contact_atom(
    pair: tuple[str, str], contract: ContactContract
) -> str | None:
    left, right = pair
    left_robot = left in contract.robot_geoms
    right_robot = right in contract.robot_geoms
    if left_robot and right_robot:
        return None
    if left_robot or right_robot:
        robot_geom = left if left_robot else right
        other_geom = right if left_robot else left
        owner = contract.entity_by_geom.get(other_geom)
        allowed_target = bool(
            owner == contract.target
            and robot_geom in contract.gripper_geoms
            and contract.phase
            in {
                "pick_up",
                "move",
                "place",
                "release",
                "open",
                "close",
                "actuate",
            }
        )
        if allowed_target and contract.allowed_target_part_geoms:
            allowed_target = other_geom in contract.allowed_target_part_geoms
        if allowed_target:
            return None
        return (
            "forbidden_robot_contact:"
            f"{('gripper' if robot_geom in contract.gripper_geoms else 'arm')}:"
            f"{owner or other_geom}"
        )
    left_owner = contract.entity_by_geom.get(left)
    right_owner = contract.entity_by_geom.get(right)
    owners = {value for value in (left_owner, right_owner) if value is not None}
    if contract.target not in owners:
        return None
    other = next((value for value in owners if value != contract.target), None)
    if (
        other == contract.destination
        and contract.phase in {"place", "release"}
    ):
        return None
    if other is not None:
        return f"forbidden_held_object_contact:{other}"
    return None


@dataclass(frozen=True)
class ShadowAssessment:
    verdict: L1Verdict
    reason_atoms: tuple[str, ...]
    structured_effects: tuple[str, ...]
    shadow_step_count: int
    baseline_contact_count: int
    maximum_contact_count: int
    maximum_robot_force_newtons: float
    restore_identity: bool
    restore_assessment_digest: str | None
    latency_ns: int
    contract: ContactContract
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": TASK_CONDITIONED_L1_SCHEMA + ".assessment",
                    "verdict": self.verdict.value,
                    "reason_atoms": self.reason_atoms,
                    "structured_effects": self.structured_effects,
                    "shadow_step_count": self.shadow_step_count,
                    "baseline_contact_count": self.baseline_contact_count,
                    "maximum_contact_count": self.maximum_contact_count,
                    "maximum_robot_force_newtons": self.maximum_robot_force_newtons,
                    "restore_identity": self.restore_identity,
                    "restore_assessment_digest": self.restore_assessment_digest,
                    "latency_ns": self.latency_ns,
                    "contract_digest": self.contract.contract_digest,
                }
            ),
        )

    def audit_payload(self) -> dict[str, Any]:
        return {
            "schema": TASK_CONDITIONED_L1_SCHEMA + ".assessment",
            "verdict": self.verdict.value,
            "reason_atoms": self.reason_atoms,
            "structured_effects": self.structured_effects,
            "shadow_step_count": self.shadow_step_count,
            "baseline_contact_count": self.baseline_contact_count,
            "maximum_contact_count": self.maximum_contact_count,
            "maximum_robot_force_newtons": self.maximum_robot_force_newtons,
            "restore_identity": self.restore_identity,
            "restore_assessment_digest": self.restore_assessment_digest,
            "latency_ns": self.latency_ns,
            "contract": self.contract.audit_payload(),
            "assessment_digest": self.assessment_digest,
        }


class TaskConditionedShadowChecker:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge

    def assess(
        self, actions: np.ndarray, *, semantic_subtask: str, source_id: str
    ) -> ShadowAssessment:
        started = perf_counter_ns()
        if self.bridge.env is None:
            raise TaskConditionedL1Error("shadow checker has no simulator")
        env = _raw_env(self.bridge.env)
        robot = _single_robot(env)
        contract = compile_contact_contract(
            env, semantic_subtask, self.bridge.current_template
        )
        command = np.asarray(actions, dtype=np.float64)
        if command.ndim != 2 or command.shape[1] != 7 or not np.isfinite(command).all():
            return ShadowAssessment(
                verdict=L1Verdict.ABSTAIN,
                reason_atoms=("malformed_action_block",),
                structured_effects=(),
                shadow_step_count=0,
                baseline_contact_count=0,
                maximum_contact_count=0,
                maximum_robot_force_newtons=0.0,
                restore_identity=True,
                restore_assessment_digest=None,
                latency_ns=perf_counter_ns() - started,
                contract=contract,
            )
        baseline = set(_contact_pairs(env))
        reasons: list[str] = []
        effects: list[str] = []
        maximum_ncon = len(baseline)
        maximum_force = 0.0
        steps = 0
        restore = None
        snapshot = capture_dynamic_state_policy_shadow_snapshot(
            env, robot, source_id=source_id
        )
        try:
            for action in command:
                transition = env.step(np.clip(action, -1.0, 1.0).tolist())
                info = transition[3] if isinstance(transition, tuple) and len(transition) >= 4 else {}
                steps += 1
                ncon = int(env.sim.data.ncon)
                maximum_ncon = max(maximum_ncon, ncon)
                if ncon >= int(env.sim.model.nconmax):
                    reasons.append("contact_capacity_saturated")
                current_force = _max_robot_force(env, robot)
                maximum_force = max(maximum_force, current_force)
                if current_force > FORCE_LIMIT_NEWTONS:
                    reasons.append("excessive_force")
                if bool(robot.check_q_limits()):
                    reasons.append("joint_limit_violation")
                reasons.extend(_cost_or_collision(info))
                for pair in set(_contact_pairs(env)) - baseline:
                    atom = _pair_contact_atom(pair, contract)
                    if atom is not None:
                        reasons.append(atom)
                if contract.target is not None:
                    target_geoms = {
                        geom
                        for geom, owner in contract.entity_by_geom.items()
                        if owner == contract.target
                    }
                    touched = {
                        geom
                        for pair in _contact_pairs(env)
                        for geom in pair
                    }
                    if target_geoms & touched:
                        effects.append(f"contact({contract.target})")
        except Exception as exc:
            reasons.append(f"shadow_exception:{type(exc).__name__}")
        finally:
            restore = restore_dynamic_state_policy_shadow_snapshot(
                env, robot, snapshot
            )
        identity = _restore_identity(restore)
        if not identity:
            raise TaskConditionedL1Error(
                "exact L1 shadow failed full restore identity"
            )
        unique_reasons = tuple(dict.fromkeys(reasons))
        uncertain = any(
            atom.startswith("shadow_exception:")
            or atom == "contact_capacity_saturated"
            for atom in unique_reasons
        )
        hard = tuple(
            atom
            for atom in unique_reasons
            if not atom.startswith("shadow_exception:")
            and atom != "contact_capacity_saturated"
        )
        verdict = (
            L1Verdict.ABSTAIN
            if uncertain
            else L1Verdict.REJECT
            if hard
            else L1Verdict.ALLOW
        )
        return ShadowAssessment(
            verdict=verdict,
            reason_atoms=unique_reasons,
            structured_effects=tuple(dict.fromkeys(effects)),
            shadow_step_count=steps,
            baseline_contact_count=len(baseline),
            maximum_contact_count=maximum_ncon,
            maximum_robot_force_newtons=maximum_force,
            restore_identity=identity,
            restore_assessment_digest=restore.assessment_digest,
            latency_ns=perf_counter_ns() - started,
            contract=contract,
        )


def recovery_candidates(nominal: np.ndarray) -> tuple[tuple[str, np.ndarray], ...]:
    nominal = np.asarray(nominal, dtype=np.float64)
    shape = nominal.shape
    gripper = float(np.clip(nominal[0, 6], -1.0, 1.0))
    hold = np.zeros(shape, dtype=np.float64)
    hold[:, 6] = gripper
    reverse = hold.copy()
    direction = -np.mean(np.clip(nominal[:, :3], -1.0, 1.0), axis=0)
    norm = float(np.linalg.norm(direction))
    if norm > 0.0:
        direction = direction / max(norm, 1.0) * RECOVERY_ACTION_SCALE
    reverse[:RECOVERY_MOTION_STEPS, :3] = direction
    lift = hold.copy()
    lift[:RECOVERY_MOTION_STEPS, 2] = RECOVERY_ACTION_SCALE
    return (
        ("reverse_then_hold", reverse),
        ("vertical_retreat_then_hold", lift),
        ("hold_and_reobserve", hold),
    )


class AdvisoryAfterExactShadowChecker(
    RiskSelectiveSemanticExecutablePrefixChecker
):
    """Keep legacy proxy atoms in the ledger, but remove their authority."""

    def predecessor_assess(self, **kwargs: Any) -> Any:
        result = super().predecessor_assess(**kwargs)
        if not result.known:
            return result
        advisory = tuple(
            f"legacy_proxy_advisory:{atom}" for atom in result.violation_atoms
        )
        return replace(
            result,
            semantic_compatible=True,
            precondition_atoms=tuple(
                dict.fromkeys((*result.precondition_atoms, *advisory))
            ),
            violation_atoms=(),
            progress_margin=max(float(result.progress_margin or 0.0), 0.002),
        )


class TaskConditionedRecoveryCandidatePolicy(RiskSelectiveCandidatePolicy):
    """Return nominal H10 or a separately shadow-qualified recovery H10."""

    bridge: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.bridge is None:
            raise TaskConditionedL1Error("candidate policy lacks geometry bridge")
        self.shadow = TaskConditionedShadowChecker(self.bridge)
        self.recovery_attempt_count = 0

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        if self.wrapper is None or self.request is None:
            raise TaskConditionedL1Error("candidate policy lacks semantic bindings")
        source_result = self.inner.infer(element)
        source_chunk = np.asarray(source_result["actions"], dtype=np.float64)
        if (
            source_chunk.ndim != 2
            or source_chunk.shape[1] != 7
            or len(source_chunk) < self.replan_steps
            or not np.isfinite(source_chunk).all()
        ):
            raise TaskConditionedL1Error("source policy returned invalid ActionBlock")
        nominal = np.clip(source_chunk[: self.replan_steps], -1.0, 1.0)
        subtask = self.request.artifact.selected_subtask
        nominal_assessment = self.shadow.assess(
            nominal,
            semantic_subtask=subtask,
            source_id=(
                f"l1:proposal:{self.request.context.state_epoch}:nominal:"
                f"{_array_digest(nominal)}"
            ),
        )
        selected = nominal
        selected_kind = "nominal"
        recovery_rows = []
        if nominal_assessment.verdict is not L1Verdict.ALLOW:
            self.recovery_attempt_count += 1
            candidates = recovery_candidates(nominal)
            if self.recovery_attempt_count > MAX_RECOVERY_ATTEMPTS:
                candidates = candidates[-1:]
            for recovery_id, candidate in candidates:
                assessed = self.shadow.assess(
                    candidate,
                    semantic_subtask=subtask,
                    source_id=(
                        f"l1:proposal:{self.request.context.state_epoch}:"
                        f"recovery:{recovery_id}:{_array_digest(candidate)}"
                    ),
                )
                recovery_rows.append(
                    {
                        "recovery_id": recovery_id,
                        "action_block_sha256": _array_digest(candidate),
                        "assessment": assessed.audit_payload(),
                    }
                )
                if assessed.verdict is L1Verdict.ALLOW:
                    selected = candidate
                    selected_kind = recovery_id
                    break
            else:
                # A hold is the bounded fail-closed fallback.  It remains
                # explicitly ABSTAIN rather than being reported as qualified.
                selected_kind, selected = candidates[-1]
                selected_kind = "unqualified_" + selected_kind
        else:
            self.recovery_attempt_count = 0
        selected_digest = _array_digest(selected)
        source_digest = _array_digest(source_chunk)
        self.audits.append(
            {
                "schema": TASK_CONDITIONED_L1_SCHEMA + ".candidate-decision",
                "candidate_count": 1,
                "replan_steps": self.replan_steps,
                "fixed_semantic_subtask": subtask,
                "source_policy_chunk_sha256": source_digest,
                "source_policy_chunk_shape": tuple(source_chunk.shape),
                "nominal_executable_sha256": _array_digest(nominal),
                "nominal_assessment": nominal_assessment.audit_payload(),
                "selected_kind": selected_kind,
                "selected_action_block_sha256": selected_digest,
                "nominal_command_changed": not np.array_equal(selected, nominal),
                "fresh_recovery_transaction": selected_kind != "nominal",
                "recovery_attempt_count": self.recovery_attempt_count,
                "maximum_recovery_attempts_before_hold_only": MAX_RECOVERY_ATTEMPTS,
                "recovery_candidates": recovery_rows,
                # Compatibility fields consumed by the inherited runner chain.
                "selection_reason": (
                    "task_conditioned_exact_shadow_allow"
                    if selected_kind == "nominal"
                    else "task_conditioned_fresh_recovery"
                ),
                "eligible_selected_source_candidate_index": 0,
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": False,
                "returned_source_policy_chunk_sha256": source_digest,
                "returned_action_chunk_sha256": selected_digest,
            }
        )
        returned = source_chunk.copy()
        returned[: self.replan_steps] = selected
        return {**source_result, "actions": returned}


__all__ = [
    "AdvisoryAfterExactShadowChecker",
    "ContactContract",
    "FORCE_LIMIT_NEWTONS",
    "L1Verdict",
    "MAX_RECOVERY_ATTEMPTS",
    "ShadowAssessment",
    "TASK_CONDITIONED_L1_SCHEMA",
    "TASK_CONDITIONED_L1_VERSION",
    "TaskConditionedL1Error",
    "TaskConditionedRecoveryCandidatePolicy",
    "TaskConditionedShadowChecker",
    "compile_contact_contract",
    "recovery_candidates",
]
