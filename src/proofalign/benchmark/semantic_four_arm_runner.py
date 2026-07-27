"""Dispatch-free four-arm evaluator for semantic-bound integrity v4.

This module is deliberately separate from the frozen v3 four-arm runner.  It
evaluates shared final proposal/assessment/contract bytes under the two
treatment switches without constructing a simulator, command sink, or dispatch
session.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import (
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    assessment_binding_issues,
    command_digest,
    execution_contract_binding_issues,
)


SEMANTIC_FIXED_TRACE_SCHEMA = (
    "proofalign.semantic-v4-four-arm-fixed-trace-result.v1"
)


class SemanticMethodArm(str, Enum):
    VLA_ONLY = "vla_only"
    SEMANTIC_ONLY = "semantic_only"
    EXECUTION_ONLY = "execution_only"
    DUAL = "dual"

    @property
    def semantic_enabled(self) -> bool:
        return self in (
            SemanticMethodArm.SEMANTIC_ONLY,
            SemanticMethodArm.DUAL,
        )

    @property
    def execution_enabled(self) -> bool:
        return self in (
            SemanticMethodArm.EXECUTION_ONLY,
            SemanticMethodArm.DUAL,
        )


ARM_ORDER = (
    SemanticMethodArm.VLA_ONLY,
    SemanticMethodArm.SEMANTIC_ONLY,
    SemanticMethodArm.EXECUTION_ONLY,
    SemanticMethodArm.DUAL,
)


class ShadowLayerVerdict(str, Enum):
    DISABLED = "disabled"
    PROVEN = "proven"
    REFUTED = "refuted"
    UNKNOWN = "unknown"


class ShadowCoreVerdict(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    UNKNOWN = "unknown"


class SemanticFixedTraceError(RuntimeError):
    """Raised when a v4 no-dispatch identity invariant is violated."""


@dataclass(frozen=True)
class SemanticV4TraceProposal:
    case_id: str
    proposal: ActionProposal
    assessment: ActionBlockAssessment
    execution_contract: BlockExecutionContract
    semantic_compatible: bool
    current_state_epoch: int
    current_trusted_observation_digest: str
    checked_at_ns: int
    dispatch_command: tuple[float, ...] | None = None
    authorization_reused: bool = False

    def __post_init__(self) -> None:
        if not self.case_id:
            raise SemanticFixedTraceError("case_id must be non-empty")
        if type(self.semantic_compatible) is not bool:
            raise TypeError("semantic_compatible must be bool")
        if type(self.current_state_epoch) is not int:
            raise TypeError("current_state_epoch must be int")
        if type(self.checked_at_ns) is not int or self.checked_at_ns < 0:
            raise SemanticFixedTraceError(
                "checked_at_ns must be non-negative"
            )
        if type(self.authorization_reused) is not bool:
            raise TypeError("authorization_reused must be bool")
        if self.dispatch_command is not None:
            command_digest(self.dispatch_command)

    def export_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "proposal": {
                **self.proposal.payload(),
                "action_block_digest": self.proposal.action_block_digest,
            },
            "assessment": {
                **self.assessment.payload(),
                "assessment_digest": self.assessment.assessment_digest,
            },
            "execution_contract": {
                **self.execution_contract.payload(),
                "execution_contract_digest": (
                    self.execution_contract.execution_contract_digest
                ),
            },
            "semantic_compatible": self.semantic_compatible,
            "current_state_epoch": self.current_state_epoch,
            "current_trusted_observation_digest": (
                self.current_trusted_observation_digest
            ),
            "checked_at_ns": self.checked_at_ns,
            "dispatch_command_digest": (
                None
                if self.dispatch_command is None
                else command_digest(self.dispatch_command)
            ),
            "authorization_reused": self.authorization_reused,
        }


@dataclass(frozen=True)
class SemanticV4ShadowChecker:
    """Finite Python predicate corresponding to the v4 Lean truth-table scope."""

    max_artifact_age_ns: int = 1_000

    def __post_init__(self) -> None:
        if (
            type(self.max_artifact_age_ns) is not int
            or self.max_artifact_age_ns <= 0
        ):
            raise SemanticFixedTraceError(
                "max_artifact_age_ns must be positive"
            )

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker": "proofalign-semantic-v4-shadow-checker",
                "version": "1",
                "max_artifact_age_ns": self.max_artifact_age_ns,
            }
        )

    def check_semantic(
        self, item: SemanticV4TraceProposal
    ) -> tuple[ShadowLayerVerdict, tuple[str, ...]]:
        issues = list(
            assessment_binding_issues(item.proposal, item.assessment)
        )
        unknown = []
        if not item.proposal.dispatchable:
            unknown.append("semantic_proposal_not_dispatchable")
        if not item.assessment.known:
            unknown.append(
                "assessment_unknown:"
                f"{item.assessment.unknown_reason}"
            )
        if not item.assessment.assessor_kind.efficacy_eligible:
            issues.append("assessor_kind_not_efficacy_eligible")
        if item.assessment.predicted_violation_atoms:
            issues.append("predicted_violation_atoms_nonempty")
        if not item.semantic_compatible:
            issues.append("semantic_subtask_action_mismatch")
        if issues:
            return ShadowLayerVerdict.REFUTED, tuple(issues)
        if unknown:
            return ShadowLayerVerdict.UNKNOWN, tuple(unknown)
        return ShadowLayerVerdict.PROVEN, ()

    def check_execution(
        self, item: SemanticV4TraceProposal
    ) -> tuple[ShadowLayerVerdict, tuple[str, ...]]:
        issues = list(
            execution_contract_binding_issues(
                item.proposal,
                item.assessment,
                item.execution_contract,
            )
        )
        unknown = []
        if (
            item.current_state_epoch
            != item.proposal.state_epoch
        ):
            unknown.append("stale_state_epoch")
        if (
            item.current_trusted_observation_digest
            != item.proposal.trusted_observation_digest
        ):
            unknown.append("stale_trusted_observation")
        if item.proposal.proposed_at_ns > item.checked_at_ns:
            unknown.append("proposal_from_future")
        if item.assessment.generated_at_ns > item.checked_at_ns:
            unknown.append("assessment_from_future")
        if item.execution_contract.issued_at_ns > item.checked_at_ns:
            unknown.append("contract_from_future")
        elif (
            item.checked_at_ns
            - item.execution_contract.issued_at_ns
            > self.max_artifact_age_ns
        ):
            unknown.append("artifact_transaction_stale")
        dispatch_command = (
            item.proposal.command
            if item.dispatch_command is None
            else item.dispatch_command
        )
        if (
            command_digest(dispatch_command)
            != command_digest(item.proposal.command)
        ):
            issues.append("dispatch_command_substitution")
        if item.authorization_reused:
            issues.append("authorization_replay")
        if issues:
            return ShadowLayerVerdict.REFUTED, tuple(issues)
        if unknown:
            return ShadowLayerVerdict.UNKNOWN, tuple(unknown)
        return ShadowLayerVerdict.PROVEN, ()


class SharedSemanticV4ShadowRunner:
    """Evaluate four arms while guaranteeing zero dispatch capability."""

    def __init__(
        self, checker: SemanticV4ShadowChecker | None = None
    ) -> None:
        self.checker = checker or SemanticV4ShadowChecker()

    def evaluate(
        self,
        *,
        unit_id: str,
        proposals: Sequence[SemanticV4TraceProposal],
    ) -> dict[str, Any]:
        if not unit_id:
            raise SemanticFixedTraceError("unit_id must be non-empty")
        if [
            item.proposal.proposal_index for item in proposals
        ] != list(range(len(proposals))):
            raise SemanticFixedTraceError(
                "proposal indices must be contiguous from zero"
            )
        rows = []
        for item in proposals:
            semantic_verdict, semantic_issues = (
                self.checker.check_semantic(item)
            )
            execution_verdict, execution_issues = (
                self.checker.check_execution(item)
            )
            for arm in ARM_ORDER:
                active_semantic = (
                    semantic_verdict
                    if arm.semantic_enabled
                    else ShadowLayerVerdict.DISABLED
                )
                active_execution = (
                    execution_verdict
                    if arm.execution_enabled
                    else ShadowLayerVerdict.DISABLED
                )
                enabled = tuple(
                    verdict
                    for verdict in (
                        active_semantic,
                        active_execution,
                    )
                    if verdict is not ShadowLayerVerdict.DISABLED
                )
                if ShadowLayerVerdict.REFUTED in enabled:
                    core = ShadowCoreVerdict.REJECT
                elif ShadowLayerVerdict.UNKNOWN in enabled:
                    core = ShadowCoreVerdict.UNKNOWN
                else:
                    core = ShadowCoreVerdict.ALLOW
                decision_payload = {
                    "schema": "proofalign.semantic-v4-shadow-decision.v1",
                    "unit_id": unit_id,
                    "case_id": item.case_id,
                    "arm": arm.value,
                    "proposal_digest": item.proposal.proposal_digest,
                    "assessment_digest": (
                        item.assessment.assessment_digest
                    ),
                    "execution_contract_digest": (
                        item.execution_contract.execution_contract_digest
                    ),
                    "semantic_verdict": active_semantic.value,
                    "execution_verdict": active_execution.value,
                    "core_verdict": core.value,
                    "checker_config_digest": self.checker.config_digest,
                }
                rows.append(
                    {
                        **decision_payload,
                        "proposal_index": item.proposal.proposal_index,
                        "action_block_digest": (
                            item.proposal.action_block_digest
                        ),
                        "semantic_enabled": arm.semantic_enabled,
                        "execution_enabled": arm.execution_enabled,
                        "semantic_issues": (
                            semantic_issues
                            if arm.semantic_enabled
                            else ()
                        ),
                        "execution_issues": (
                            execution_issues
                            if arm.execution_enabled
                            else ()
                        ),
                        "decision_digest": digest_payload(
                            decision_payload
                        ),
                        "dispatch_attempted": False,
                    }
                )
        return {
            "schema": SEMANTIC_FIXED_TRACE_SCHEMA,
            "unit_id": unit_id,
            "proposal_count": len(proposals),
            "row_count": len(rows),
            "dispatch_attempt_count": 0,
            "simulator_created": False,
            "sink_created": False,
            "rows": rows,
        }


__all__ = [
    "ARM_ORDER",
    "SEMANTIC_FIXED_TRACE_SCHEMA",
    "SemanticFixedTraceError",
    "SemanticMethodArm",
    "SemanticV4ShadowChecker",
    "SemanticV4TraceProposal",
    "ShadowCoreVerdict",
    "ShadowLayerVerdict",
    "SharedSemanticV4ShadowRunner",
]
