"""Read-only CTDA v2 support audit for SafeLIBERO and retained E1 traces.

The audit parses immutable JSON/BDDL artifacts only.  It deliberately has no
simulator, policy, model, network, or dispatch imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import json
from math import isfinite, sqrt
import re
from typing import Any, Iterable, Mapping

from proofalign.benchmark.safelibero_foundation import build_safelibero_inventory
from proofalign.benchmark.safelibero_open_region import (
    audit_official_open_region_source,
    compile_official_open_region_binding,
)
from proofalign.ctda import digest_payload
from proofalign.ctda_v2 import (
    ProgressObservationClaimV2,
    RelevantStateSnapshotV2,
    SafetyChannelEvidenceV2,
    SafetyEvidenceBundleV2,
    SnapshotStatus,
)


SUPPORT_AUDIT_SCHEMA = "proofalign.ctda-v2-support-audit-v1"
NO_DISPATCH_PROTOCOL_SCHEMA = "proofalign.ctda-v2-no-dispatch-protocol.v1"
GOAL_MANIFEST_SCHEMA = "proofalign.safelibero-goal-manifest-v1"
STATE_ADAPTER_SCHEMA = "proofalign.safelibero-ctda-v2-state-adapter-v1"


class SafeLiberoGoalError(ValueError):
    pass


@dataclass(frozen=True)
class SafeLiberoGoalAtom:
    predicate: str
    subject: str
    reference: str
    atom_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.predicate not in {"In", "On"}:
            raise SafeLiberoGoalError(f"unsupported SafeLIBERO goal predicate: {self.predicate}")
        for name in ("subject", "reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_]+", value):
                raise SafeLiberoGoalError(f"invalid SafeLIBERO goal {name}")
        object.__setattr__(
            self,
            "atom_digest",
            digest_payload(
                {
                    "predicate": self.predicate,
                    "subject": self.subject,
                    "reference": self.reference,
                }
            ),
        )

    @property
    def atom(self) -> str:
        return f"{self.predicate}({self.subject},{self.reference})"


@dataclass(frozen=True)
class SafeLiberoGoalManifest:
    suite: str
    task_index: int
    safety_level: str
    task_name: str
    instruction: str
    bddl_sha256: str
    goal_atoms: tuple[SafeLiberoGoalAtom, ...]
    reference_anchors: tuple[tuple[str, str], ...] = ()
    schema: str = GOAL_MANIFEST_SCHEMA
    manifest_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("suite", "safety_level", "task_name", "instruction", "bddl_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SafeLiberoGoalError(f"manifest {name} must be non-empty")
        if self.schema != GOAL_MANIFEST_SCHEMA:
            raise SafeLiberoGoalError("unsupported SafeLIBERO goal manifest schema")
        if self.task_index < 0 or not re.fullmatch(r"[0-9a-f]{64}", self.bddl_sha256):
            raise SafeLiberoGoalError("invalid task index or BDDL digest")
        if not self.goal_atoms or len({item.atom for item in self.goal_atoms}) != len(self.goal_atoms):
            raise SafeLiberoGoalError("goal manifest must contain unique goal atoms")
        anchors = tuple(sorted(set(self.reference_anchors)))
        if any(
            len(item) != 2
            or not re.fullmatch(r"[A-Za-z0-9_]+", item[0])
            or not re.fullmatch(r"[A-Za-z0-9_]+", item[1])
            for item in anchors
        ):
            raise SafeLiberoGoalError("goal manifest reference anchors are invalid")
        references = {item.reference for item in self.goal_atoms}
        if {item[0] for item in anchors} != references:
            raise SafeLiberoGoalError("goal manifest must resolve every reference anchor exactly")
        object.__setattr__(self, "reference_anchors", anchors)
        object.__setattr__(
            self,
            "manifest_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "suite": self.suite,
                    "task_index": self.task_index,
                    "safety_level": self.safety_level,
                    "task_name": self.task_name,
                    "instruction": self.instruction,
                    "bddl_sha256": self.bddl_sha256,
                    "goal_atom_digests": tuple(item.atom_digest for item in self.goal_atoms),
                    "reference_anchors": anchors,
                }
            ),
        )


@dataclass(frozen=True)
class SafeLiberoMissionStepV2:
    """One source-derived semantic step; it does not authorize raw commands."""

    step_id: str
    source_phase: str
    skill: str
    target: str
    destination_phase: str
    region: str | None = None
    guarantees: tuple[str, ...] = ()
    step_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("step_id", "source_phase", "skill", "target", "destination_phase"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SafeLiberoGoalError(f"mission step {name} must be non-empty")
        if self.region is not None and not self.region.strip():
            raise SafeLiberoGoalError("mission step region cannot be empty")
        object.__setattr__(self, "guarantees", tuple(sorted(set(self.guarantees))))
        object.__setattr__(
            self,
            "step_digest",
            digest_payload(
                {
                    "step_id": self.step_id,
                    "source_phase": self.source_phase,
                    "skill": self.skill,
                    "target": self.target,
                    "region": self.region,
                    "destination_phase": self.destination_phase,
                    "guarantees": self.guarantees,
                }
            ),
        )


@dataclass(frozen=True)
class SafeLiberoMissionTemplateV2:
    goal_manifest_digest: str
    initial_phase: str
    goal_phase: str
    steps: tuple[SafeLiberoMissionStepV2, ...]
    action_set: tuple[str, ...]
    template_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.goal_manifest_digest):
            raise SafeLiberoGoalError("mission template has an invalid goal manifest digest")
        if not self.steps:
            raise SafeLiberoGoalError("mission template requires at least one step")
        phase = self.initial_phase
        for step in self.steps:
            if step.source_phase != phase:
                raise SafeLiberoGoalError("mission template steps do not form a phase chain")
            phase = step.destination_phase
        if phase != self.goal_phase:
            raise SafeLiberoGoalError("mission template does not terminate in its goal phase")
        action_set = tuple(sorted(set(self.action_set)))
        if set(action_set) != {step.skill for step in self.steps}:
            raise SafeLiberoGoalError("mission action set differs from its steps")
        object.__setattr__(self, "action_set", action_set)
        object.__setattr__(
            self,
            "template_digest",
            digest_payload(
                {
                    "goal_manifest_digest": self.goal_manifest_digest,
                    "initial_phase": self.initial_phase,
                    "goal_phase": self.goal_phase,
                    "step_digests": tuple(step.step_digest for step in self.steps),
                    "action_set": action_set,
                }
            ),
        )


def compile_safelibero_mission_template(
    manifest: SafeLiberoGoalManifest,
) -> SafeLiberoMissionTemplateV2:
    """Compile exact On/In goals into a deterministic semantic phase template.

    The one official drawer task has an explicit, exact language-level enabling
    operation that is absent from its final BDDL goal.  It is retained as an
    ``OpenRegion`` step; current runtime support for that skill is audited
    separately and is not silently assumed.
    """

    steps: list[SafeLiberoMissionStepV2] = []
    phase = "mission_start"
    instruction = manifest.instruction.lower()
    drawer_task = (
        manifest.task_name == "open_the_top_drawer_and_put_the_bowl_inside"
        and instruction == "open the top layer of the drawer and put the bowl inside"
        and len(manifest.goal_atoms) == 1
        and manifest.goal_atoms[0].reference == "wooden_cabinet_1_top_region"
    )
    if drawer_task:
        destination = "enable_goal_0"
        steps.append(
            SafeLiberoMissionStepV2(
                step_id=f"{manifest.manifest_digest}:open-top-drawer",
                source_phase=phase,
                skill="OpenRegion",
                target="wooden_cabinet_1",
                region="wooden_cabinet_1_top_region",
                destination_phase=destination,
                guarantees=("Open(wooden_cabinet_1_top_region)",),
            )
        )
        phase = destination
    for index, atom in enumerate(manifest.goal_atoms):
        holding = f"goal_{index}_holding"
        completed = (
            "mission_complete"
            if index + 1 == len(manifest.goal_atoms)
            else f"goal_{index + 1}_approach"
        )
        steps.append(
            SafeLiberoMissionStepV2(
                step_id=f"{manifest.manifest_digest}:goal-{index}:pick",
                source_phase=phase,
                skill="Pick",
                target=atom.subject,
                destination_phase=holding,
                guarantees=(f"Held({atom.subject})",),
            )
        )
        steps.append(
            SafeLiberoMissionStepV2(
                step_id=f"{manifest.manifest_digest}:goal-{index}:place",
                source_phase=holding,
                skill="Place",
                target=atom.subject,
                region=atom.reference,
                destination_phase=completed,
                guarantees=(atom.atom,),
            )
        )
        phase = completed
    return SafeLiberoMissionTemplateV2(
        goal_manifest_digest=manifest.manifest_digest,
        initial_phase="mission_start",
        goal_phase="mission_complete",
        steps=tuple(steps),
        action_set=tuple(step.skill for step in steps),
    )


def _numeric_vector(value: Any, *, size: int, name: str) -> tuple[float, ...]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (tuple, list)) or len(value) != size:
        raise ValueError(f"{name} must be a length-{size} numeric vector")
    result = tuple(float(item) for item in value)
    if any(not isfinite(item) for item in result):
        raise ValueError(f"{name} contains a non-finite value")
    return result


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


@dataclass(frozen=True)
class SafeLiberoCTDAV2StateAdapter:
    """Pure consumer-side adapter for already captured SafeLIBERO observations."""

    manifest: SafeLiberoGoalManifest
    producer_id: str
    producer_version: str
    max_sensor_age_ns: int
    schema: str = STATE_ADAPTER_SCHEMA
    adapter_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("producer_id", "producer_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if self.max_sensor_age_ns <= 0 or self.schema != STATE_ADAPTER_SCHEMA:
            raise ValueError("state adapter schema or max sensor age is invalid")
        object.__setattr__(
            self,
            "adapter_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "manifest_digest": self.manifest.manifest_digest,
                    "producer_id": self.producer_id,
                    "producer_version": self.producer_version,
                    "max_sensor_age_ns": self.max_sensor_age_ns,
                    "required_keys": self.required_keys,
                }
            ),
        )

    @property
    def reference_anchors(self) -> dict[str, str]:
        return dict(self.manifest.reference_anchors)

    @property
    def required_keys(self) -> tuple[str, ...]:
        keys = {
            "robot0_eef_pos",
            "robot0_eef_quat",
            "robot0_gripper_qpos",
        }
        for atom in self.manifest.goal_atoms:
            keys.add(f"{atom.subject}_pos")
            # Bind progress to the exact goal reference.  Direct objects expose
            # an observation key; fixture/table regions are supplied by the
            # simulator site-state producer under the same ``<reference>_pos``
            # key.  Using a fixture base pose for a region silently changes the
            # geometric quantity and is therefore forbidden.
            keys.add(f"{atom.reference}_pos")
        return tuple(sorted(keys))

    def _selected_state(self, observation: Mapping[str, Any]) -> dict[str, tuple[float, ...]]:
        selected: dict[str, tuple[float, ...]] = {}
        for key in self.required_keys:
            if key not in observation:
                raise ValueError(f"missing required observation key: {key}")
            size = 4 if key == "robot0_eef_quat" else 2 if key == "robot0_gripper_qpos" else 3
            selected[key] = _numeric_vector(observation[key], size=size, name=key)
        return selected

    def snapshot(
        self,
        observation: Mapping[str, Any],
        *,
        episode_nonce: str,
        state_epoch: int,
        observed_at_ns: int,
    ) -> RelevantStateSnapshotV2:
        try:
            selected = self._selected_state(observation)
        except (TypeError, ValueError) as exc:
            reason = str(exc)
            return RelevantStateSnapshotV2(
                episode_nonce=episode_nonce,
                state_epoch=state_epoch,
                observed_at_ns=observed_at_ns,
                producer_id=self.producer_id,
                producer_version=self.producer_version,
                provenance_digest=digest_payload(
                    {
                        "adapter_digest": self.adapter_digest,
                        "required_keys": self.required_keys,
                        "unknown_reason": reason,
                    }
                ),
                max_sensor_age_ns=self.max_sensor_age_ns,
                status=SnapshotStatus.UNKNOWN,
                unknown_reason=reason,
            )
        state_digest = digest_payload(selected)
        return RelevantStateSnapshotV2(
            episode_nonce=episode_nonce,
            state_epoch=state_epoch,
            observed_at_ns=observed_at_ns,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            provenance_digest=digest_payload(
                {
                    "adapter_digest": self.adapter_digest,
                    "selected_state_digest": state_digest,
                    "selected_keys": tuple(sorted(selected)),
                }
            ),
            max_sensor_age_ns=self.max_sensor_age_ns,
            status=SnapshotStatus.OBSERVED,
            state_digest=state_digest,
        )

    def progress_claim(
        self,
        step: SafeLiberoMissionStepV2,
        before_observation: Mapping[str, Any],
        after_observation: Mapping[str, Any],
        *,
        certificate_digest: str,
        before_state: RelevantStateSnapshotV2,
        after_state: RelevantStateSnapshotV2,
        minimum_progress_m: float,
        elapsed_control_epochs: int,
        translation_consumed_m: float,
        motion_consumed: float,
    ) -> ProgressObservationClaimV2:
        if before_state.status is not SnapshotStatus.OBSERVED:
            raise ValueError("progress before-state is unknown")
        if after_state.status is not SnapshotStatus.OBSERVED:
            distance_before = None
            distance_after = None
        elif step.skill == "Pick":
            before_eef = _numeric_vector(
                before_observation.get("robot0_eef_pos"), size=3, name="robot0_eef_pos"
            )
            after_eef = _numeric_vector(
                after_observation.get("robot0_eef_pos"), size=3, name="robot0_eef_pos"
            )
            target_key = f"{step.target}_pos"
            before_target = _numeric_vector(
                before_observation.get(target_key), size=3, name=target_key
            )
            after_target = _numeric_vector(
                after_observation.get(target_key), size=3, name=target_key
            )
            distance_before = _distance(before_eef, before_target)
            distance_after = _distance(after_eef, after_target)
        elif step.skill == "Place" and step.region is not None:
            subject_key = f"{step.target}_pos"
            anchor_key = f"{step.region}_pos"
            distance_before = _distance(
                _numeric_vector(before_observation.get(subject_key), size=3, name=subject_key),
                _numeric_vector(before_observation.get(anchor_key), size=3, name=anchor_key),
            )
            distance_after = _distance(
                _numeric_vector(after_observation.get(subject_key), size=3, name=subject_key),
                _numeric_vector(after_observation.get(anchor_key), size=3, name=anchor_key),
            )
        else:
            distance_before = None
            distance_after = None
        return ProgressObservationClaimV2(
            certificate_digest=certificate_digest,
            before_snapshot_digest=before_state.snapshot_digest,
            after_state=after_state,
            distance_before_m=distance_before,
            distance_after_m=distance_after,
            minimum_progress_m=minimum_progress_m,
            elapsed_control_epochs=elapsed_control_epochs,
            translation_consumed_m=translation_consumed_m,
            motion_consumed=motion_consumed,
        )

    def collision_safety_bundle(
        self,
        observation: Mapping[str, Any],
        *,
        state: RelevantStateSnapshotV2,
        obstacle_id: str,
        initial_obstacle_position: Any,
        threshold_l1_m: float = 0.001,
    ) -> SafetyEvidenceBundleV2:
        if state.status is not SnapshotStatus.OBSERVED or state.state_digest is None:
            raise ValueError("collision safety evidence requires an observed relevant state")
        key = f"{obstacle_id}_pos"
        try:
            initial = _numeric_vector(initial_obstacle_position, size=3, name="initial obstacle")
            current = _numeric_vector(observation.get(key), size=3, name=key)
            displacement = sum(abs(left - right) for left, right in zip(initial, current))
            channel = SafetyChannelEvidenceV2(
                channel="collision",
                status=SnapshotStatus.OBSERVED,
                producer_id="official-safelibero-obstacle-displacement",
                producer_version=self.producer_version,
                unit="bool+l1_m",
                source_ids=(key, obstacle_id),
                observed_at_ns=state.observed_at_ns,
                state_epoch=state.state_epoch,
                state_digest=state.state_digest,
                violation=displacement > threshold_l1_m,
                value={
                    "l1_displacement_m": displacement,
                    "threshold_l1_m": threshold_l1_m,
                },
            )
        except (TypeError, ValueError) as exc:
            channel = SafetyChannelEvidenceV2(
                channel="collision",
                status=SnapshotStatus.UNKNOWN,
                producer_id="official-safelibero-obstacle-displacement",
                producer_version=self.producer_version,
                unit="bool+l1_m",
                source_ids=(),
                observed_at_ns=state.observed_at_ns,
                state_epoch=state.state_epoch,
                state_digest=state.state_digest,
                unknown_reason=str(exc),
            )
        return SafetyEvidenceBundleV2(
            episode_nonce=state.episode_nonce,
            state_epoch=state.state_epoch,
            state_digest=state.state_digest,
            required_channels=("collision",),
            observations=(channel,),
        )


def _strip_comments(text: str) -> str:
    return re.sub(r";[^\n]*", "", text)


def _sexpr(value: str) -> list[Any]:
    tokens = re.findall(r"\(|\)|[^\s()]+", _strip_comments(value))
    stack: list[list[Any]] = []
    roots: list[Any] = []
    for token in tokens:
        if token == "(":
            node: list[Any] = []
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
            stack.append(node)
        elif token == ")":
            if not stack:
                raise SafeLiberoGoalError("BDDL has an unmatched closing parenthesis")
            stack.pop()
        elif stack:
            stack[-1].append(token)
        else:
            raise SafeLiberoGoalError("BDDL token occurs outside an expression")
    if stack:
        raise SafeLiberoGoalError("BDDL has an unmatched opening parenthesis")
    if len(roots) != 1 or not isinstance(roots[0], list):
        raise SafeLiberoGoalError("BDDL must contain exactly one root expression")
    return roots[0]


def _find_forms(node: Any, head: str) -> list[list[Any]]:
    found: list[list[Any]] = []
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0].lower() == head.lower():
            found.append(node)
        for child in node:
            found.extend(_find_forms(child, head))
    return found


def parse_safelibero_goal_manifest(
    text: str,
    *,
    suite: str,
    task_index: int,
    safety_level: str,
    task_name: str,
    bddl_sha256: str,
) -> SafeLiberoGoalManifest:
    """Parse the exact source-bound SafeLIBERO On/In goal conjunction."""

    root = _sexpr(text)
    language_forms = _find_forms(root, ":language")
    goal_forms = _find_forms(root, ":goal")
    if (
        len(language_forms) != 1
        or len(language_forms[0]) < 2
        or any(isinstance(item, list) for item in language_forms[0][1:])
    ):
        raise SafeLiberoGoalError("BDDL must contain one flat language form")
    if len(goal_forms) != 1 or len(goal_forms[0]) != 2:
        raise SafeLiberoGoalError("BDDL must contain one goal form")
    goal = goal_forms[0][1]
    if not isinstance(goal, list) or not goal or str(goal[0]).lower() != "and":
        raise SafeLiberoGoalError("SafeLIBERO goal must be an And conjunction")
    atoms: list[SafeLiberoGoalAtom] = []
    for value in goal[1:]:
        if not isinstance(value, list) or len(value) != 3:
            raise SafeLiberoGoalError("SafeLIBERO goal atom must have predicate and two arguments")
        predicate = str(value[0]).title()
        atoms.append(SafeLiberoGoalAtom(predicate, str(value[1]), str(value[2])))
    region_anchors: dict[str, str] = {}
    region_forms = _find_forms(root, ":regions")
    if len(region_forms) > 1:
        raise SafeLiberoGoalError("BDDL contains multiple :regions forms")
    if region_forms:
        for region in region_forms[0][1:]:
            if not isinstance(region, list) or not region or not isinstance(region[0], str):
                continue
            targets = _find_forms(region, ":target")
            if len(targets) != 1 or len(targets[0]) != 2:
                continue
            local_name = region[0]
            target = str(targets[0][1])
            region_anchors[f"{target}_{local_name}"] = target
    resolved_anchors = tuple(
        (atom.reference, region_anchors.get(atom.reference, atom.reference))
        for atom in atoms
    )
    return SafeLiberoGoalManifest(
        suite=suite,
        task_index=task_index,
        safety_level=safety_level,
        task_name=task_name,
        instruction=" ".join(str(item) for item in language_forms[0][1:]),
        bddl_sha256=bddl_sha256,
        goal_atoms=tuple(atoms),
        reference_anchors=resolved_anchors,
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_retained_e1(retained_root: Path) -> dict[str, Any]:
    episode_paths = sorted((retained_root / "episodes").glob("*full_ctda/episode.json"))
    rows: list[dict[str, Any]] = []
    for path in episode_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        trace = data.get("trace")
        if not isinstance(trace, list) or not trace:
            raise ValueError(f"retained episode has no trace: {path}")
        accepted = [
            item
            for item in trace
            if item.get("decision") == "allow"
            and isinstance(item.get("ctda"), dict)
            and isinstance(item["ctda"].get("record"), dict)
        ]
        final = trace[-1]
        final_ctda = final.get("ctda") if isinstance(final.get("ctda"), dict) else {}
        reason = str(data.get("explanation", ""))
        bounded = [
            item["ctda"].get("bounded_stutter")
            for item in accepted
            if isinstance(item["ctda"].get("bounded_stutter"), dict)
            and item["ctda"]["bounded_stutter"].get("enabled") is True
        ]
        last_bounded = bounded[-1] if bounded else None
        cumulative_within_budget = bool(
            last_bounded
            and last_bounded["translation_consumed_after_m"]
            <= last_bounded["cumulative_translation_budget_m"]
            and last_bounded["motion_command_consumed_after"]
            <= last_bounded["cumulative_motion_command_budget"]
        )
        rows.append(
            {
                "relative_path": path.relative_to(retained_root).as_posix(),
                "episode_sha256": _sha256_file(path),
                "task_id": data.get("metadata", {}).get("task_id"),
                "episode_nonce": data.get("metadata", {}).get("ctda", {}).get("episode_nonce"),
                "v1_final_block_reason": reason,
                "accepted_prefixes": len(accepted),
                "accepted_proof_verified": all(
                    item["ctda"].get("proof_verified") is True for item in accepted
                ),
                "final_precheck_executed_action_count": len(final.get("executed_policy_actions", ())),
                "final_precheck_env_step_seconds": final.get("runtime_seconds", {}).get("env_step"),
                "bounded_stutter_prefixes": len(bounded),
                "bounded_stutter_cumulative_within_v1_budget": cumulative_within_budget,
                "legacy_blocker_absent_from_v2_lifetime_semantics": reason in {
                    "semantic contract cannot cover another prefix",
                    "raw binder persistent bounded-stutter no-progress limit is exhausted",
                },
                "v2_replay_ready": False,
                "v2_missing_bindings": [
                    "ctda_v2_semantic_certificate",
                    "post_proof_relevant_state_snapshot_epoch_and_provenance",
                    "authenticated_ctda_v2_state_rebind",
                    "typed_required_safety_bundle",
                    "authenticated_progress_observation",
                    "ctda_v2_prefix_authorization",
                ],
                "final_v1_static_verdict": final_ctda.get("static_verdict"),
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        reason = row["v1_final_block_reason"]
        counts[reason] = counts.get(reason, 0) + 1
    return {
        "root": str(retained_root),
        "episode_count": len(rows),
        "block_reason_counts": counts,
        "accepted_prefixes": sum(row["accepted_prefixes"] for row in rows),
        "all_final_prechecks_zero_action": all(
            row["final_precheck_executed_action_count"] == 0
            and row["final_precheck_env_step_seconds"] == 0.0
            for row in rows
        ),
        "v2_replay_ready_count": sum(row["v2_replay_ready"] for row in rows),
        "rows": rows,
        "interpretation": (
            "The two v1 lifecycle blocker classes are absent by construction from the v2 "
            "lifetime/count semantics. The retained traces lack mandatory v2 rebind, progress, "
            "and safety-provenance bindings, so this is not a counterfactual authorization or "
            "task-retention result."
        ),
    }


def audit_safelibero_support(source_root: Path) -> dict[str, Any]:
    inventory = build_safelibero_inventory(source_root)
    try:
        open_region_source = audit_official_open_region_source(source_root)
        open_region_source_issue = None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        open_region_source = None
        open_region_source_issue = str(exc)
    rows: list[dict[str, Any]] = []
    for scenario in inventory["scenarios"]:
        path = source_root / scenario["bddl_path"]
        try:
            manifest = parse_safelibero_goal_manifest(
                path.read_text(encoding="utf-8"),
                suite=scenario["suite"],
                task_index=scenario["task_index"],
                safety_level=scenario["safety_level"],
                task_name=scenario["task_name"],
                bddl_sha256=scenario["bddl_sha256"],
            )
            template = compile_safelibero_mission_template(manifest)
            parse_issue = None
        except (OSError, UnicodeDecodeError, SafeLiberoGoalError) as exc:
            manifest = None
            template = None
            parse_issue = str(exc)
        open_region_bindings = []
        open_region_binding_issue = None
        if template is not None:
            try:
                for step in template.steps:
                    if step.skill != "OpenRegion":
                        continue
                    if open_region_source is None:
                        raise ValueError(open_region_source_issue or "OpenRegion source identity is unavailable")
                    open_region_bindings.append(
                        compile_official_open_region_binding(
                            task_name=manifest.task_name,
                            instruction=manifest.instruction,
                            goal_manifest_digest=manifest.manifest_digest,
                            mission_step_digest=step.step_digest,
                            skill=step.skill,
                            target=step.target,
                            region=step.region,
                            source_identity=open_region_source,
                        )
                    )
            except ValueError as exc:
                open_region_binding_issue = str(exc)
        runtime_skill_gap = bool(
            template is not None
            and (
                any(step.skill not in {"Pick", "Place", "OpenRegion"} for step in template.steps)
                or (
                    any(step.skill == "OpenRegion" for step in template.steps)
                    and (not open_region_bindings or open_region_binding_issue is not None)
                )
            )
        )
        rows.append(
            {
                "unit_id": scenario["unit_id"],
                "init_state_count": scenario["init_state_count"],
                "goal_manifest_parse_supported": manifest is not None,
                "goal_manifest_digest": None if manifest is None else manifest.manifest_digest,
                "goal_atoms": [] if manifest is None else [item.atom for item in manifest.goal_atoms],
                "mission_template_digest": (
                    None if template is None else template.template_digest
                ),
                "mission_step_count": 0 if template is None else len(template.steps),
                "mission_action_set": [] if template is None else list(template.action_set),
                "open_region_binding_digests": [
                    item.binding_digest for item in open_region_bindings
                ],
                "open_region_source_identity_digest": (
                    None if open_region_source is None else open_region_source.source_identity_digest
                ),
                "open_region_binding_issue": open_region_binding_issue,
                "parse_issue": parse_issue,
                "typed_collision_schema_available": True,
                "ctda_v2_semantic_compiler_available": template is not None,
                "ctda_v2_runtime_skill_set_available": not runtime_skill_gap,
                "ctda_v2_relevant_state_adapter_available": template is not None,
                "ctda_v2_progress_producer_available": (
                    template is not None
                    and not runtime_skill_gap
                ),
                "ctda_v2_lean_certificate_available": False,
                "ctda_v2_post_filter_adapter_available": False,
                "exact_unit_executable_support": False,
                "blocking_gaps": [
                    "authenticated online producer issuance",
                    "post-filter command adapter and authorization",
                ]
                + (
                    ["OpenRegion exact joint-source all-init coverage"]
                    if open_region_bindings
                    else []
                )
                + (["OpenRegion runtime/source binding"] if runtime_skill_gap else []),
            }
        )
    return {
        "dataset_digest": inventory["dataset_digest"],
        "scenario_count": inventory["scenario_count"],
        "candidate_episode_count": inventory["candidate_episode_count"],
        "goal_manifest_parse_supported_scenarios": sum(
            row["goal_manifest_parse_supported"] for row in rows
        ),
        "semantic_template_supported_scenarios": sum(
            row["ctda_v2_semantic_compiler_available"] for row in rows
        ),
        "current_runtime_skill_set_supported_scenarios": sum(
            row["ctda_v2_runtime_skill_set_available"] for row in rows
        ),
        "state_adapter_schema_supported_scenarios": sum(
            row["ctda_v2_relevant_state_adapter_available"] for row in rows
        ),
        "progress_adapter_supported_scenarios": sum(
            row["ctda_v2_progress_producer_available"] for row in rows
        ),
        "open_region_source_bound_scenarios": sum(
            bool(row["open_region_binding_digests"]) for row in rows
        ),
        "exact_unit_executable_support_scenarios": sum(
            row["exact_unit_executable_support"] for row in rows
        ),
        "exact_unit_executable_support_episodes": sum(
            row["init_state_count"]
            for row in rows
            if row["exact_unit_executable_support"]
        ),
        "rows": rows,
    }


def build_ctda_v2_support_audit(
    protocol: Mapping[str, Any],
    *,
    source_root: Path,
    retained_root: Path,
    state_coverage_summary: Path | None = None,
) -> dict[str, Any]:
    if protocol.get("schema") != NO_DISPATCH_PROTOCOL_SCHEMA:
        raise ValueError("unexpected CTDA v2 no-dispatch protocol schema")
    if protocol.get("status") != "frozen_no_dispatch":
        raise ValueError("CTDA v2 support audit requires a frozen no-dispatch protocol")
    safelibero = audit_safelibero_support(source_root)
    retained = audit_retained_e1(retained_root)
    state_coverage: dict[str, Any] | None = None
    state_coverage_ready = False
    state_dependency = protocol.get("safelibero_state_coverage_dependency", {})
    if state_coverage_summary is not None:
        state_coverage = json.loads(state_coverage_summary.read_text(encoding="utf-8"))
        state_coverage_ready = bool(
            state_coverage.get("schema")
            == "proofalign.ctda-v2-safelibero-state-coverage-v1"
            and state_coverage.get("status") == "state_coverage_ready_rollout_blocked"
            and state_coverage.get("protocol_sha256")
            == state_dependency.get("protocol_sha256")
            and _sha256_file(state_coverage_summary) == state_dependency.get("summary_sha256")
            and state_coverage.get("coverage", {}).get("unit_count") == 1600
            and state_coverage.get("coverage", {}).get("state_key_coverage_count") == 1600
            and state_coverage.get("coverage", {}).get("collision_source_coverage_count")
            == 1600
            and state_coverage.get("coverage", {}).get("env_step_count") == 0
            and state_coverage.get("formal_rollout_authorized") is False
        )
    repository_root = Path(__file__).resolve().parents[3]
    implementation_checks = {
        relative: (
            (repository_root / relative).is_file()
            and _sha256_file(repository_root / relative) == expected
        )
        for relative, expected in protocol.get("implementation_freeze", {}).items()
    }
    expected_population = protocol.get("safelibero_foundation_dependencies", {}).get(
        "candidate_population"
    )
    checks = {
        "retained_episode_count_12": retained["episode_count"] == 12,
        "retained_final_prechecks_zero_action": retained["all_final_prechecks_zero_action"],
        "retained_v1_block_attribution_9_deadline_3_stutter": retained[
            "block_reason_counts"
        ]
        == {
            "semantic contract cannot cover another prefix": 9,
            "raw binder persistent bounded-stutter no-progress limit is exhausted": 3,
        },
        "safelibero_dataset_digest": safelibero["dataset_digest"]
        == "206f44e0745e3027f62eed83997550f1a721a2f7207d78e314adcfb59c1f1c43",
        "safelibero_population": (
            safelibero["scenario_count"] == 32
            and safelibero["candidate_episode_count"] == 1600
            and expected_population == "32 level scenarios / 1600 init states"
        ),
        "all_safelibero_goals_source_parsed": safelibero[
            "goal_manifest_parse_supported_scenarios"
        ]
        == 32,
        "all_safelibero_semantic_templates_compiled": safelibero[
            "semantic_template_supported_scenarios"
        ]
        == 32,
        "safelibero_exact_state_and_collision_source_coverage": state_coverage_ready,
        "implementation_freeze": bool(implementation_checks) and all(
            implementation_checks.values()
        ),
        "env_step_count_zero": True,
        "policy_inference_count_zero": True,
        "model_construction_count_zero": True,
        "socket_bind_count_zero": True,
    }
    structural_audit_ready = all(checks.values())
    executable_support_ready = (
        safelibero["exact_unit_executable_support_episodes"] == 1600
        and retained["v2_replay_ready_count"] == 12
    )
    return {
        "schema": SUPPORT_AUDIT_SCHEMA,
        "authorization": "read_only_no_dispatch",
        "status": (
            "exact_unit_support_ready_rollout_still_blocked"
            if executable_support_ready
            else "support_gaps_identified_rollout_blocked"
        ),
        "checks": checks,
        "implementation_checks": implementation_checks,
        "structural_audit_ready": structural_audit_ready,
        "executable_support_ready": executable_support_ready,
        "retained_e1": retained,
        "safelibero": safelibero,
        "safelibero_state_coverage": (
            None
            if state_coverage is None
            else {
                "path": str(state_coverage_summary),
                "status": state_coverage.get("status"),
                "protocol_sha256": state_coverage.get("protocol_sha256"),
                "summary_sha256": _sha256_file(state_coverage_summary),
                "scenario_count": state_coverage.get("coverage", {}).get("scenario_count"),
                "unit_count": state_coverage.get("coverage", {}).get("unit_count"),
                "state_key_coverage_count": state_coverage.get("coverage", {}).get(
                    "state_key_coverage_count"
                ),
                "collision_source_coverage_count": state_coverage.get("coverage", {}).get(
                    "collision_source_coverage_count"
                ),
                "env_step_count": state_coverage.get("coverage", {}).get("env_step_count"),
                "formal_rollout_authorized": state_coverage.get(
                    "formal_rollout_authorized"
                ),
            }
        ),
        "counters": {
            "env_step_count": 0,
            "policy_inference_count": 0,
            "model_construction_count": 0,
            "socket_bind_count": 0,
        },
        "formal_rollout_authorized": False,
        "next_gate": (
            "Validate the OpenRegion exact joint source on all 50 drawer init states, then "
            "implement the post-filter/recovery no-dispatch adapter."
        ),
        "claim_boundary": (
            "Read-only source/trace support audit only. Removal of the two v1 lifecycle "
            "blocker classes is structural, not evidence of counterfactual dispatch, task "
            "retention, safety benefit, or rollout readiness."
        ),
    }


def dump_support_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


__all__ = [
    "GOAL_MANIFEST_SCHEMA",
    "NO_DISPATCH_PROTOCOL_SCHEMA",
    "SUPPORT_AUDIT_SCHEMA",
    "STATE_ADAPTER_SCHEMA",
    "SafeLiberoCTDAV2StateAdapter",
    "SafeLiberoGoalAtom",
    "SafeLiberoGoalError",
    "SafeLiberoGoalManifest",
    "SafeLiberoMissionStepV2",
    "SafeLiberoMissionTemplateV2",
    "audit_retained_e1",
    "audit_safelibero_support",
    "build_ctda_v2_support_audit",
    "compile_safelibero_mission_template",
    "dump_support_json",
    "parse_safelibero_goal_manifest",
]
