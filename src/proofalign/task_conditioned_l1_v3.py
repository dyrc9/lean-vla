"""Bounded-retreat successor for transition-aligned task-conditioned L1.

Version 2 remains immutable.  Its development execution demonstrated that the
three-candidate recovery set can contain no exact-shadow ALLOW action.  This
version changes only recovery coverage: it evaluates a fixed, outcome-blind
lattice of low-amplitude Cartesian retreats and still fails closed when no
candidate is allowed.  Risk channels, force limit, contact contract, shadow
checker, source action, and ALLOW criterion are unchanged.
"""

from __future__ import annotations

from collections import Counter
from itertools import product
import json
from typing import Any

import numpy as np

from proofalign.digests import digest_payload
from proofalign.task_conditioned_l1 import (
    L1Verdict,
    MAX_RECOVERY_ATTEMPTS,
    RECOVERY_ACTION_SCALE,
    TaskConditionedL1Error,
)
from proofalign.task_conditioned_l1_v2 import (
    REGISTERED_RISK_CHANNELS,
    TransitionAlignedRecoveryCandidatePolicy,
    TransitionAlignedShadowChecker,
    _base_array_digest,
)
from scripts.run_l2_execution_attack_eval_v2 import _array_digest


TASK_CONDITIONED_L1_V3_SCHEMA = "proofalign.task-conditioned-l1.v3"
TASK_CONDITIONED_L1_V3_VERSION = "3"
RECOVERY_MOTION_STEP_OPTIONS = (2, 4)


def _unit(value: tuple[float, float, float]) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("zero recovery direction")
    return vector / norm


_DIRECTION_LABEL = {-1: "neg", 0: "zero", 1: "pos"}
_FIXED_RETREAT_DIRECTIONS = tuple(
    (
        "x{}_y{}_z{}".format(*(_DIRECTION_LABEL[value] for value in values)),
        _unit(tuple(float(value) for value in values)),
    )
    for values in product((-1, 0, 1), repeat=3)
    if values != (0, 0, 0)
)


def _hold(nominal: np.ndarray) -> np.ndarray:
    result = np.zeros_like(nominal, dtype=np.float64)
    result[:, 6] = float(np.clip(nominal[0, 6], -1.0, 1.0))
    return result


def bounded_retreat_candidates(
    nominal: np.ndarray,
) -> tuple[tuple[str, np.ndarray], ...]:
    """Return the fixed recovery lattice, independent of task outcomes."""

    nominal = np.asarray(nominal, dtype=np.float64)
    if nominal.ndim != 2 or nominal.shape[1] != 7 or len(nominal) == 0:
        raise TaskConditionedL1Error("malformed recovery source ActionBlock")
    hold = _hold(nominal)
    source_direction = -np.mean(np.clip(nominal[:, :3], -1.0, 1.0), axis=0)
    source_norm = float(np.linalg.norm(source_direction))
    candidates: list[tuple[str, np.ndarray]] = []
    if source_norm > 0.0:
        source_direction = source_direction / source_norm
        for steps in RECOVERY_MOTION_STEP_OPTIONS:
            block = hold.copy()
            block[:steps, :3] = source_direction * RECOVERY_ACTION_SCALE
            candidates.append((f"source_reverse_{steps}_then_hold", block))
    for steps in RECOVERY_MOTION_STEP_OPTIONS:
        for name, direction in _FIXED_RETREAT_DIRECTIONS:
            block = hold.copy()
            block[:steps, :3] = direction * RECOVERY_ACTION_SCALE
            candidates.append((f"retreat_{name}_{steps}_then_hold", block))
    candidates.append(("hold_and_reobserve", hold))
    unique: list[tuple[str, np.ndarray]] = []
    seen: set[str] = set()
    for name, block in candidates:
        digest = _array_digest(block)
        if digest not in seen:
            seen.add(digest)
            unique.append((name, block))
    return tuple(unique)


def recovery_library_digest() -> str:
    payload = {
        "schema": TASK_CONDITIONED_L1_V3_SCHEMA + ".recovery-library",
        "scale": RECOVERY_ACTION_SCALE,
        "motion_steps": RECOVERY_MOTION_STEP_OPTIONS,
        "directions": [
            {"name": name, "value": direction.tolist()}
            for name, direction in _FIXED_RETREAT_DIRECTIONS
        ],
        "selection": "first exact-shadow ALLOW in frozen order",
        "no_allow": "fail_closed_no_dispatch",
    }
    return digest_payload(payload)


class BoundedRetreatRecoveryCandidatePolicy(
    TransitionAlignedRecoveryCandidatePolicy
):
    """Use exact-shadow ALLOW over the frozen retreat lattice."""

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
                f"l1v3:proposal:{self.request.context.state_epoch}:nominal:"
                f"{_array_digest(nominal)}"
            ),
        )
        selected = nominal
        selected_kind = "nominal"
        recovery_rows = []
        if nominal_assessment.verdict is not L1Verdict.ALLOW:
            self.recovery_attempt_count += 1
            candidates = bounded_retreat_candidates(nominal)
            for recovery_id, candidate in candidates:
                assessed = self.shadow.assess(
                    candidate,
                    semantic_subtask=subtask,
                    source_id=(
                        f"l1v3:proposal:{self.request.context.state_epoch}:"
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
                    "no qualified bounded-retreat ActionBlock: "
                    + json.dumps(dict(counts), sort_keys=True, separators=(",", ":"))
                )
        else:
            self.recovery_attempt_count = 0

        source_digest = _array_digest(source_chunk)
        selected_digest = _array_digest(selected)
        self.audits.append(
            {
                "schema": TASK_CONDITIONED_L1_V3_SCHEMA + ".candidate-decision",
                "candidate_count": 1,
                "replan_steps": self.replan_steps,
                "fixed_semantic_subtask": subtask,
                "source_policy_chunk_sha256": source_digest,
                "source_policy_chunk_base_array_sha256": _base_array_digest(source_chunk),
                "source_policy_chunk_shape": tuple(source_chunk.shape),
                "nominal_executable_sha256": _array_digest(nominal),
                "nominal_assessment": nominal_assessment.audit_payload(),
                "selected_kind": selected_kind,
                "selected_action_block_sha256": selected_digest,
                "selected_action_block_base_array_sha256": _base_array_digest(selected),
                "nominal_command_changed": not np.array_equal(selected, nominal),
                "fresh_recovery_transaction": selected_kind != "nominal",
                "recovery_attempt_count": self.recovery_attempt_count,
                "maximum_recovery_attempts_legacy_constant": MAX_RECOVERY_ATTEMPTS,
                "recovery_candidates": recovery_rows,
                "recovery_library_digest": recovery_library_digest(),
                "recovery_library_size": len(bounded_retreat_candidates(nominal)),
                "selection_reason": (
                    "transition_aligned_exact_shadow_allow"
                    if selected_kind == "nominal"
                    else "bounded_retreat_exact_shadow_allow"
                ),
                "eligible_selected_source_candidate_index": 0,
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": False,
                "returned_source_policy_chunk_sha256": source_digest,
                "returned_action_chunk_sha256": selected_digest,
                "source_digest_algorithm": "v2_array_digest_sha256",
                "cross_arm_identity_digest_algorithm": "base_online_runner_array_digest_sha256",
                "registered_risk_channels": REGISTERED_RISK_CHANNELS,
                "unqualified_fallback_dispatch_allowed": False,
            }
        )
        returned = source_chunk.copy()
        returned[: self.replan_steps] = selected
        return {**source_result, "actions": returned}


__all__ = [
    "BoundedRetreatRecoveryCandidatePolicy",
    "RECOVERY_MOTION_STEP_OPTIONS",
    "TASK_CONDITIONED_L1_V3_SCHEMA",
    "TASK_CONDITIONED_L1_V3_VERSION",
    "bounded_retreat_candidates",
    "recovery_library_digest",
]
