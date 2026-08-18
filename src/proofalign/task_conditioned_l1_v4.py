"""Qualified no-dispatch abort for irrecoverable task-conditioned L1 states.

Version 3 remains immutable.  Its fixed 55-action recovery lattice can still
contain no exact-shadow ALLOW ActionBlock.  Version 4 does not weaken that
decision and does not dispatch a rejected fallback.  Instead it returns an
internal finite sentinel which is rejected by both the semantic checker and a
defence-in-depth dispatch boundary.  The base runner therefore closes the
episode normally as a qualified no-dispatch deadlock, retaining the trace and
all L1 audits collected before the abort.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from typing import Any, Iterable, Sequence

import numpy as np

from proofalign.digests import digest_payload
from proofalign.integrity_v4_runtime import OpenDispatchResult, TransactionVerdict
from proofalign.physical_sufficiency_semantic import (
    PhysicalSufficiencyPrefixDispatchBoundary,
)
from proofalign.risk_selective_semantic import (
    RiskSelectiveSemanticExecutablePrefixChecker,
)
from proofalign.semantic_local_checker import LocalActionAssessment
from proofalign.task_conditioned_l1 import (
    AdvisoryAfterExactShadowChecker,
    L1Verdict,
    TaskConditionedL1Error,
)
from proofalign.task_conditioned_l1_v2 import (
    REGISTERED_RISK_CHANNELS,
    TransitionAlignedShadowChecker,
    _base_array_digest,
)
from proofalign.task_conditioned_l1_v3 import (
    BoundedRetreatRecoveryCandidatePolicy,
    bounded_retreat_candidates,
    recovery_library_digest,
)
from scripts.run_l2_execution_attack_eval_v2 import _array_digest


TASK_CONDITIONED_L1_V4_SCHEMA = "proofalign.task-conditioned-l1.v4"
TASK_CONDITIONED_L1_V4_VERSION = "4"
ABORT_SENTINEL_VALUE = 1.875
ABORT_SELECTION_REASON = "no_exact_shadow_allow_qualified_no_dispatch"

# Each experimental process is single-threaded and runs one episode at a time.
# A new L1 policy instance resets this bit before its first proposal.  It is
# used only as defence in depth: the checker is the primary no-dispatch gate.
_QUALIFIED_ABORT_ARMED = False


def reset_qualified_abort_state() -> None:
    global _QUALIFIED_ABORT_ARMED
    _QUALIFIED_ABORT_ARMED = False


def _arm_qualified_abort() -> None:
    global _QUALIFIED_ABORT_ARMED
    _QUALIFIED_ABORT_ARMED = True


def _abort_sentinel(source_chunk: np.ndarray, replan_steps: int) -> np.ndarray:
    returned = np.asarray(source_chunk, dtype=np.float64).copy()
    returned[:replan_steps] = ABORT_SENTINEL_VALUE
    return returned


def _is_abort_command(
    command: Iterable[float], command_shape: Sequence[int]
) -> bool:
    try:
        shape = tuple(int(value) for value in command_shape)
        values = np.asarray(tuple(command), dtype=np.float64).reshape(shape)
    except (TypeError, ValueError):
        return False
    return bool(
        values.ndim == 2
        and values.shape[1] == 7
        and len(values) > 0
        and np.isfinite(values).all()
        and np.all(values == ABORT_SENTINEL_VALUE)
    )


def no_dispatch_protocol_digest() -> str:
    return digest_payload(
        {
            "schema": TASK_CONDITIONED_L1_V4_SCHEMA + ".no-dispatch-protocol",
            "sentinel_value": ABORT_SENTINEL_VALUE,
            "checker_gate": "known incompatible qualified_no_dispatch_abort",
            "boundary_gate": "reject while qualified abort is armed",
            "dispatch_count": 0,
            "risk_threshold_changed": False,
            "recovery_library_digest": recovery_library_digest(),
        }
    )


class QualifiedNoDispatchChecker(AdvisoryAfterExactShadowChecker):
    """Reject only the armed internal abort sentinel as non-executable."""

    def assess(self, **kwargs: Any) -> LocalActionAssessment:
        if _QUALIFIED_ABORT_ARMED and _is_abort_command(
            kwargs.get("command", ()), kwargs.get("command_shape", ())
        ):
            predecessor = (
                RiskSelectiveSemanticExecutablePrefixChecker.predecessor_assess(
                    self, **kwargs
                )
            )
            return replace(
                predecessor,
                known=True,
                semantic_compatible=False,
                precondition_atoms=tuple(
                    dict.fromkeys(
                        (
                            *predecessor.precondition_atoms,
                            "qualified_no_dispatch_abort_armed",
                        )
                    )
                ),
                violation_atoms=("qualified_no_dispatch_abort",),
                progress_margin=None,
                unknown_reason=None,
            )
        return super().assess(**kwargs)


class QualifiedNoDispatchBoundary(PhysicalSufficiencyPrefixDispatchBoundary):
    """Defence in depth: an armed abort can never open a dispatch session."""

    def open(self, authorization: Any, *, now_ns: int) -> OpenDispatchResult:
        global _QUALIFIED_ABORT_ARMED
        if _QUALIFIED_ABORT_ARMED:
            _QUALIFIED_ABORT_ARMED = False
            return OpenDispatchResult(
                TransactionVerdict.REJECT,
                None,
                ("qualified L1 no-dispatch abort",),
            )
        return super().open(authorization, now_ns=now_ns)


class QualifiedNoDispatchRecoveryCandidatePolicy(
    BoundedRetreatRecoveryCandidatePolicy
):
    """Use v3 ALLOW actions, or close normally without dispatching anything."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        reset_qualified_abort_state()
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
                f"l1v4:proposal:{self.request.context.state_epoch}:nominal:"
                f"{_array_digest(nominal)}"
            ),
        )
        selected: np.ndarray | None = nominal
        selected_kind = "nominal"
        recovery_rows = []
        if nominal_assessment.verdict is not L1Verdict.ALLOW:
            self.recovery_attempt_count += 1
            for recovery_id, candidate in bounded_retreat_candidates(nominal):
                assessed = self.shadow.assess(
                    candidate,
                    semantic_subtask=subtask,
                    source_id=(
                        f"l1v4:proposal:{self.request.context.state_epoch}:"
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
                selected = None
                selected_kind = "qualified_no_dispatch_abort"
                _arm_qualified_abort()
        else:
            self.recovery_attempt_count = 0

        source_digest = _array_digest(source_chunk)
        if selected is None:
            returned = _abort_sentinel(source_chunk, self.replan_steps)
            selected_digest = None
            returned_digest = _array_digest(returned)
        else:
            returned = source_chunk.copy()
            returned[: self.replan_steps] = selected
            selected_digest = _array_digest(selected)
            returned_digest = _array_digest(returned)
        counts = Counter(
            row["assessment"]["verdict"] for row in recovery_rows
        )
        self.audits.append(
            {
                "schema": TASK_CONDITIONED_L1_V4_SCHEMA + ".candidate-decision",
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
                "nominal_command_changed": bool(
                    selected is None or not np.array_equal(selected, nominal)
                ),
                "fresh_recovery_transaction": bool(
                    selected is not None and selected_kind != "nominal"
                ),
                "qualified_no_dispatch_abort": selected is None,
                "dispatch_intent": "none" if selected is None else "exact_action_block",
                "recovery_attempt_count": self.recovery_attempt_count,
                "recovery_candidates": recovery_rows,
                "recovery_verdict_counts": dict(counts),
                "recovery_library_digest": recovery_library_digest(),
                "recovery_library_size": len(bounded_retreat_candidates(nominal)),
                "no_dispatch_protocol_digest": no_dispatch_protocol_digest(),
                "selection_reason": (
                    ABORT_SELECTION_REASON
                    if selected is None
                    else "transition_aligned_exact_shadow_allow"
                    if selected_kind == "nominal"
                    else "bounded_retreat_exact_shadow_allow"
                ),
                "eligible_selected_source_candidate_index": (
                    None if selected is None else 0
                ),
                "returned_source_candidate_index": None if selected is None else 0,
                "fallback_for_fail_closed_recheck": selected is None,
                "returned_source_policy_chunk_sha256": source_digest,
                "returned_action_chunk_sha256": returned_digest,
                "source_digest_algorithm": "v2_array_digest_sha256",
                "cross_arm_identity_digest_algorithm": (
                    "base_online_runner_array_digest_sha256"
                ),
                "registered_risk_channels": REGISTERED_RISK_CHANNELS,
                "unqualified_fallback_dispatch_allowed": False,
                "sentinel_is_authorizable": False,
            }
        )
        return {**source_result, "actions": returned}


__all__ = [
    "ABORT_SENTINEL_VALUE",
    "QualifiedNoDispatchBoundary",
    "QualifiedNoDispatchChecker",
    "QualifiedNoDispatchRecoveryCandidatePolicy",
    "TASK_CONDITIONED_L1_V4_SCHEMA",
    "TASK_CONDITIONED_L1_V4_VERSION",
    "no_dispatch_protocol_digest",
    "reset_qualified_abort_state",
]
