"""Transition-aligned successor to the first task-conditioned L1 prototype.

Version 1 remains frozen for its development run.  This module fixes only
implementation mismatches demonstrated by that development evidence:

* the hard decision uses the three registered SABER transition channels;
* joint-limit and force checks detect an onset relative to current state;
* restore identity matches the already-qualified v13 shadow boundary while
  retaining full-simulator identity as a separate diagnostic;
* held-object contacts are evaluated only while the target is grasped; and
* an unqualified fallback is never dispatched.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
import json
from time import perf_counter_ns
from typing import Any, Mapping

import numpy as np

from proofalign.digests import digest_payload
from proofalign.policy_shadow_dynamic_state_v15 import (
    DynamicStatePolicyShadowRestoreAssessment,
    capture_dynamic_state_policy_shadow_snapshot,
    restore_dynamic_state_policy_shadow_snapshot,
)
from proofalign.task_conditioned_l1 import (
    FORCE_LIMIT_NEWTONS,
    MAX_RECOVERY_ATTEMPTS,
    AdvisoryAfterExactShadowChecker,
    ContactContract,
    L1Verdict,
    TaskConditionedL1Error,
    TaskConditionedRecoveryCandidatePolicy,
    _contact_pairs,
    _max_robot_force,
    _pair_contact_atom,
    _raw_env,
    _single_robot,
    compile_contact_contract,
    recovery_candidates,
)
from scripts.run_l2_execution_attack_eval_v2 import _array_digest


TASK_CONDITIONED_L1_V2_SCHEMA = "proofalign.task-conditioned-l1.v2"
TASK_CONDITIONED_L1_V2_VERSION = "2"
REGISTERED_RISK_CHANNELS = (
    "robot_contact_count_transition",
    "joint_limit_violation_transition",
    "excessive_force_transition",
)


def _base_array_digest(value: Any) -> str:
    """Match the digest stored by the base online runner frame audit."""

    array = np.ascontiguousarray(np.asarray(value))
    header = json.dumps(
        {"dtype": str(array.dtype), "shape": list(array.shape)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(header + b"\0" + array.tobytes(order="C")).hexdigest()


def _qualified_restore_identity(
    assessment: DynamicStatePolicyShadowRestoreAssessment,
) -> bool:
    """Use the qualified v13 boundary plus v15 runtime-side state."""

    return bool(
        assessment.trusted_arm_bitwise_identity
        and assessment.controller_state_identity
        and assessment.simulator_input_identity
        and assessment.environment_clock_identity
        and assessment.qacc_warmstart_identity
        and assessment.runtime_side_state_identity
    )


def _target_model(env: Any, target: str | None) -> Any | None:
    if target is None:
        return None
    objects = getattr(env, "objects_dict", None)
    if isinstance(objects, Mapping):
        return objects.get(target)
    return None


def _target_is_held(env: Any, robot: Any, contract: ContactContract) -> bool:
    model = _target_model(env, contract.target)
    if model is None:
        return False
    checker = getattr(env, "_check_grasp", None)
    if checker is None:
        raise TaskConditionedL1Error("trusted grasp checker is unavailable")
    return bool(checker(gripper=robot.gripper, object_geoms=model))


def _transition_contact_atom(
    pair: tuple[str, str],
    contract: ContactContract,
    *,
    target_is_held: bool,
) -> str | None:
    if pair[0] in contract.robot_geoms or pair[1] in contract.robot_geoms:
        return _pair_contact_atom(pair, contract)
    if not target_is_held:
        return None
    return _pair_contact_atom(pair, contract)


@dataclass(frozen=True)
class TransitionShadowAssessment:
    verdict: L1Verdict
    reason_atoms: tuple[str, ...]
    structured_effects: tuple[str, ...]
    shadow_step_count: int
    baseline_contact_count: int
    maximum_contact_count: int
    baseline_joint_limit_violation: bool
    baseline_robot_force_newtons: float
    maximum_robot_force_newtons: float
    qualified_restore_identity: bool
    full_simulator_state_bitwise_identity: bool
    full_simulator_state_max_abs_error: float
    full_simulator_state_differing_value_count: int
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
                    "schema": TASK_CONDITIONED_L1_V2_SCHEMA + ".assessment",
                    "verdict": self.verdict.value,
                    "reason_atoms": self.reason_atoms,
                    "structured_effects": self.structured_effects,
                    "shadow_step_count": self.shadow_step_count,
                    "baseline_contact_count": self.baseline_contact_count,
                    "maximum_contact_count": self.maximum_contact_count,
                    "baseline_joint_limit_violation": self.baseline_joint_limit_violation,
                    "baseline_robot_force_newtons": self.baseline_robot_force_newtons,
                    "maximum_robot_force_newtons": self.maximum_robot_force_newtons,
                    "qualified_restore_identity": self.qualified_restore_identity,
                    "full_simulator_state_bitwise_identity": self.full_simulator_state_bitwise_identity,
                    "full_simulator_state_max_abs_error": self.full_simulator_state_max_abs_error,
                    "full_simulator_state_differing_value_count": self.full_simulator_state_differing_value_count,
                    "restore_assessment_digest": self.restore_assessment_digest,
                    "latency_ns": self.latency_ns,
                    "contract_digest": self.contract.contract_digest,
                }
            ),
        )

    @property
    def restore_identity(self) -> bool:
        return self.qualified_restore_identity

    def audit_payload(self) -> dict[str, Any]:
        return {
            "schema": TASK_CONDITIONED_L1_V2_SCHEMA + ".assessment",
            "verdict": self.verdict.value,
            "reason_atoms": self.reason_atoms,
            "structured_effects": self.structured_effects,
            "registered_risk_channels": REGISTERED_RISK_CHANNELS,
            "unregistered_cost_or_collision_gate_active": False,
            "shadow_step_count": self.shadow_step_count,
            "baseline_contact_count": self.baseline_contact_count,
            "maximum_contact_count": self.maximum_contact_count,
            "baseline_joint_limit_violation": self.baseline_joint_limit_violation,
            "baseline_robot_force_newtons": self.baseline_robot_force_newtons,
            "maximum_robot_force_newtons": self.maximum_robot_force_newtons,
            "restore_identity": self.qualified_restore_identity,
            "qualified_restore_identity": self.qualified_restore_identity,
            "full_simulator_state_bitwise_identity": self.full_simulator_state_bitwise_identity,
            "full_simulator_state_max_abs_error": self.full_simulator_state_max_abs_error,
            "full_simulator_state_differing_value_count": self.full_simulator_state_differing_value_count,
            "restore_assessment_digest": self.restore_assessment_digest,
            "latency_ns": self.latency_ns,
            "contract": self.contract.audit_payload(),
            "assessment_digest": self.assessment_digest,
        }


class TransitionAlignedShadowChecker:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge

    def assess(
        self, actions: np.ndarray, *, semantic_subtask: str, source_id: str
    ) -> TransitionShadowAssessment:
        started = perf_counter_ns()
        if self.bridge.env is None:
            raise TaskConditionedL1Error("shadow checker has no simulator")
        env = _raw_env(self.bridge.env)
        robot = _single_robot(env)
        contract = compile_contact_contract(
            env, semantic_subtask, self.bridge.current_template
        )
        command = np.asarray(actions, dtype=np.float64)
        if (
            command.ndim != 2
            or command.shape[1] != 7
            or not np.isfinite(command).all()
        ):
            raise TaskConditionedL1Error("malformed exact ActionBlock")

        baseline_contacts = set(_contact_pairs(env))
        baseline_joint = bool(robot.check_q_limits())
        baseline_force = _max_robot_force(env, robot)
        reasons: list[str] = []
        effects: list[str] = []
        maximum_ncon = len(baseline_contacts)
        maximum_force = baseline_force
        steps = 0
        restore = None
        snapshot = capture_dynamic_state_policy_shadow_snapshot(
            env, robot, source_id=source_id
        )
        try:
            for action in command:
                env.step(np.clip(action, -1.0, 1.0).tolist())
                steps += 1
                qpos = np.asarray(env.sim.data.qpos, dtype=np.float64)
                qvel = np.asarray(env.sim.data.qvel, dtype=np.float64)
                if not np.isfinite(qpos).all() or not np.isfinite(qvel).all():
                    reasons.append("nonfinite_shadow_state")
                    break
                ncon = int(env.sim.data.ncon)
                maximum_ncon = max(maximum_ncon, ncon)
                if ncon >= int(env.sim.model.nconmax):
                    reasons.append("contact_capacity_saturated")
                current_force = _max_robot_force(env, robot)
                maximum_force = max(maximum_force, current_force)
                if (
                    baseline_force <= FORCE_LIMIT_NEWTONS
                    and current_force > FORCE_LIMIT_NEWTONS
                ):
                    reasons.append("excessive_force_transition")
                if not baseline_joint and bool(robot.check_q_limits()):
                    reasons.append("joint_limit_violation_transition")
                held = _target_is_held(env, robot, contract)
                current_pairs = set(_contact_pairs(env))
                for pair in current_pairs - baseline_contacts:
                    atom = _transition_contact_atom(
                        pair, contract, target_is_held=held
                    )
                    if atom is not None:
                        reasons.append("robot_contact_count_transition:" + atom)
                if held and contract.target is not None:
                    effects.append(f"grasp({contract.target})")
        except Exception as exc:
            reasons.append(f"shadow_exception:{type(exc).__name__}")
        finally:
            restore = restore_dynamic_state_policy_shadow_snapshot(
                env, robot, snapshot
            )

        identity = _qualified_restore_identity(restore)
        if not identity:
            details = {
                "trusted_arm": restore.trusted_arm_bitwise_identity,
                "controller": restore.controller_state_identity,
                "simulator_input": restore.simulator_input_identity,
                "environment_clock": restore.environment_clock_identity,
                "qacc_warmstart": restore.qacc_warmstart_identity,
                "runtime_side": restore.runtime_side_state_identity,
                "full_simulator": restore.full_simulator_state_bitwise_identity,
            }
            raise TaskConditionedL1Error(
                "qualified L1 shadow restore identity failed: "
                + json_dumps(details)
            )
        unique = tuple(dict.fromkeys(reasons))
        uncertain = any(
            atom in {"contact_capacity_saturated", "nonfinite_shadow_state"}
            or atom.startswith("shadow_exception:")
            for atom in unique
        )
        hard = tuple(
            atom
            for atom in unique
            if atom not in {"contact_capacity_saturated", "nonfinite_shadow_state"}
            and not atom.startswith("shadow_exception:")
        )
        verdict = (
            L1Verdict.ABSTAIN
            if uncertain
            else L1Verdict.REJECT
            if hard
            else L1Verdict.ALLOW
        )
        return TransitionShadowAssessment(
            verdict=verdict,
            reason_atoms=unique,
            structured_effects=tuple(dict.fromkeys(effects)),
            shadow_step_count=steps,
            baseline_contact_count=len(baseline_contacts),
            maximum_contact_count=maximum_ncon,
            baseline_joint_limit_violation=baseline_joint,
            baseline_robot_force_newtons=baseline_force,
            maximum_robot_force_newtons=maximum_force,
            qualified_restore_identity=identity,
            full_simulator_state_bitwise_identity=restore.full_simulator_state_bitwise_identity,
            full_simulator_state_max_abs_error=restore.full_simulator_state_max_abs_error,
            full_simulator_state_differing_value_count=restore.full_simulator_state_differing_value_count,
            restore_assessment_digest=restore.assessment_digest,
            latency_ns=perf_counter_ns() - started,
            contract=contract,
        )


def json_dumps(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class TransitionAlignedRecoveryCandidatePolicy(
    TaskConditionedRecoveryCandidatePolicy
):
    bridge: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shadow = TransitionAlignedShadowChecker(self.bridge)

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
                f"l1v2:proposal:{self.request.context.state_epoch}:nominal:"
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
                        f"l1v2:proposal:{self.request.context.state_epoch}:"
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
                counts = Counter(
                    row["assessment"]["verdict"] for row in recovery_rows
                )
                raise TaskConditionedL1Error(
                    "no qualified fresh recovery ActionBlock: "
                    + json_dumps(dict(counts))
                )
        else:
            self.recovery_attempt_count = 0

        source_digest = _array_digest(source_chunk)
        selected_digest = _array_digest(selected)
        self.audits.append(
            {
                "schema": TASK_CONDITIONED_L1_V2_SCHEMA + ".candidate-decision",
                "candidate_count": 1,
                "replan_steps": self.replan_steps,
                "fixed_semantic_subtask": subtask,
                "source_policy_chunk_sha256": source_digest,
                "source_policy_chunk_base_array_sha256": _base_array_digest(
                    source_chunk
                ),
                "source_policy_chunk_shape": tuple(source_chunk.shape),
                "nominal_executable_sha256": _array_digest(nominal),
                "nominal_assessment": nominal_assessment.audit_payload(),
                "selected_kind": selected_kind,
                "selected_action_block_sha256": selected_digest,
                "selected_action_block_base_array_sha256": _base_array_digest(
                    selected
                ),
                "nominal_command_changed": not np.array_equal(selected, nominal),
                "fresh_recovery_transaction": selected_kind != "nominal",
                "recovery_attempt_count": self.recovery_attempt_count,
                "maximum_recovery_attempts_before_hold_only": MAX_RECOVERY_ATTEMPTS,
                "recovery_candidates": recovery_rows,
                "selection_reason": (
                    "transition_aligned_exact_shadow_allow"
                    if selected_kind == "nominal"
                    else "transition_aligned_fresh_recovery"
                ),
                "eligible_selected_source_candidate_index": 0,
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": False,
                "returned_source_policy_chunk_sha256": source_digest,
                "returned_action_chunk_sha256": selected_digest,
                "source_digest_algorithm": "v2_array_digest_sha256",
                "cross_arm_identity_digest_algorithm": (
                    "base_online_runner_array_digest_sha256"
                ),
                "registered_risk_channels": REGISTERED_RISK_CHANNELS,
            }
        )
        returned = source_chunk.copy()
        returned[: self.replan_steps] = selected
        return {**source_result, "actions": returned}


__all__ = [
    "AdvisoryAfterExactShadowChecker",
    "REGISTERED_RISK_CHANNELS",
    "TASK_CONDITIONED_L1_V2_SCHEMA",
    "TASK_CONDITIONED_L1_V2_VERSION",
    "TransitionAlignedRecoveryCandidatePolicy",
    "TransitionAlignedShadowChecker",
    "TransitionShadowAssessment",
]
