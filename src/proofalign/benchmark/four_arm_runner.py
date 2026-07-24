"""Shared no-dispatch runner for the four-arm fixed-trace gate.

The VLA-facing object is only a numeric ``ActionProposal``.  A frozen,
consumer-side assessor predicts what that block will do, and a separate
consumer-side execution contract states what must be observed if the block is
dispatched.  No explicit policy plan is required or reconstructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any, Iterable, Sequence

from proofalign.benchmark.confirmatory import ARM_ORDER, FIXED_TRACE_RESULT_SCHEMA
from proofalign.integrity_checker import DeterministicFastChecker, ExactPrefixAuthorizer
from proofalign.integrity_intervention import InterventionPolicy
from proofalign.integrity_models import (
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    CoreVerdict,
    MethodArm,
    StateSnapshot,
    TrustedTaskArtifact,
)
from proofalign.integrity_runtime import InMemoryCommandSink, ProofAlignPrototype


class FixedTraceRunnerError(RuntimeError):
    """Raised when shared-runner identity or no-dispatch invariants fail."""


@dataclass(frozen=True)
class TypedTraceProposal:
    """One frozen ActionBlock plus consumer-generated assessment and contract."""

    episode_nonce: str
    proposal_index: int
    proposed_at_ns: int
    assessed_at_ns: int
    execution_contract_issued_at_ns: int
    assessor_id: str
    assessor_version: str
    assessor_kind: ActionAssessmentKind
    predicted_skill: str
    command: tuple[float, ...]
    state_epoch: int
    state_observed_at_ns: int
    state_max_age_ns: int
    state_digest: str
    precondition_atoms: tuple[str, ...]
    predicted_effect_atoms: tuple[str, ...]
    predicted_violation_atoms: tuple[str, ...]
    expected_effect_atoms: tuple[str, ...]
    forbidden_effect_atoms: tuple[str, ...]
    observation_window_steps: int
    command_shape: tuple[int, ...] = ()
    target: str | None = None
    part: str | None = None
    region: str | None = None
    assessment_known: bool = True
    assessment_unknown_reason: str | None = None
    state_known: bool = True
    state_unknown_reason: str | None = None
    contract_issuer_id: str = "proofalign-block-contract-compiler"
    contract_issuer_version: str = "1"

    def proposal(self) -> ActionProposal:
        return ActionProposal(
            episode_nonce=self.episode_nonce,
            proposal_index=self.proposal_index,
            proposed_at_ns=self.proposed_at_ns,
            observation_digest=self.state_digest,
            state_epoch=self.state_epoch,
            command=self.command,
            command_shape=self.command_shape,
        )

    def assessment(self) -> ActionBlockAssessment:
        proposal = self.proposal()
        return ActionBlockAssessment(
            assessor_id=self.assessor_id,
            assessor_version=self.assessor_version,
            assessor_kind=self.assessor_kind,
            episode_nonce=self.episode_nonce,
            proposal_index=self.proposal_index,
            generated_at_ns=self.assessed_at_ns,
            action_block_digest=proposal.action_block_digest,
            observation_digest=self.state_digest,
            state_epoch=self.state_epoch,
            known=self.assessment_known,
            predicted_skill=(
                self.predicted_skill if self.assessment_known else None
            ),
            target=self.target if self.assessment_known else None,
            part=self.part if self.assessment_known else None,
            region=self.region if self.assessment_known else None,
            precondition_atoms=(
                self.precondition_atoms if self.assessment_known else ()
            ),
            predicted_effect_atoms=(
                self.predicted_effect_atoms if self.assessment_known else ()
            ),
            predicted_violation_atoms=(
                self.predicted_violation_atoms if self.assessment_known else ()
            ),
            unknown_reason=(
                None if self.assessment_known else self.assessment_unknown_reason
            ),
        )

    def execution_contract(self) -> BlockExecutionContract:
        proposal = self.proposal()
        assessment = self.assessment()
        return BlockExecutionContract(
            issuer_id=self.contract_issuer_id,
            issuer_version=self.contract_issuer_version,
            episode_nonce=self.episode_nonce,
            proposal_index=self.proposal_index,
            issued_at_ns=self.execution_contract_issued_at_ns,
            action_block_digest=proposal.action_block_digest,
            assessment_digest=assessment.assessment_digest,
            observation_digest=self.state_digest,
            state_epoch=self.state_epoch,
            expected_effect_atoms=self.expected_effect_atoms,
            forbidden_effect_atoms=self.forbidden_effect_atoms,
            observation_window_steps=self.observation_window_steps,
        )

    def state(self) -> StateSnapshot:
        return StateSnapshot(
            episode_nonce=self.episode_nonce,
            state_epoch=self.state_epoch,
            observed_at_ns=self.state_observed_at_ns,
            max_age_ns=self.state_max_age_ns,
            state_digest=self.state_digest if self.state_known else None,
            known=self.state_known,
            unknown_reason=self.state_unknown_reason,
        )

    def export_payload(self) -> dict[str, Any]:
        proposal = self.proposal()
        assessment = self.assessment()
        execution_contract = self.execution_contract()
        return {
            "action_block": {
                **proposal.payload(),
                "command": list(proposal.command),
                "action_block_digest": proposal.action_block_digest,
            },
            "intent_action_assessment": {
                **assessment.payload(),
                "assessment_digest": assessment.assessment_digest,
            },
            "execution_contract": {
                **execution_contract.payload(),
                "execution_contract_digest": (
                    execution_contract.execution_contract_digest
                ),
            },
            "proposal_index": proposal.proposal_index,
            "action_block_digest": proposal.action_block_digest,
            "proposal_digest": proposal.proposal_digest,
            "assessment_digest": assessment.assessment_digest,
            "execution_contract_digest": (
                execution_contract.execution_contract_digest
            ),
            "state": {
                "state_epoch": self.state_epoch,
                "observed_at_ns": self.state_observed_at_ns,
                "max_age_ns": self.state_max_age_ns,
                "state_digest": self.state_digest if self.state_known else None,
                "known": self.state_known,
                "unknown_reason": self.state_unknown_reason,
            },
        }


class SharedFourArmShadowRunner:
    """Evaluate byte-identical ActionBlocks under the two layer switches."""

    def __init__(
        self,
        *,
        artifact: TrustedTaskArtifact,
        episode_nonce: str,
        intervention_policy: InterventionPolicy | None = None,
        authorization_ttl_ns: int = 100_000_000,
    ) -> None:
        self.artifact = artifact
        self.episode_nonce = episode_nonce
        self.intervention_policy = intervention_policy
        self._prototypes: dict[MethodArm, ProofAlignPrototype] = {}
        for arm in ARM_ORDER:
            prototype = ProofAlignPrototype.create(
                arm=arm,
                artifact=artifact,
                episode_nonce=episode_nonce,
                authorizer=ExactPrefixAuthorizer(
                    DeterministicFastChecker(),
                    authorization_ttl_ns=authorization_ttl_ns,
                ),
                sink=InMemoryCommandSink(),
            )
            transaction = prototype.certify_contract(now_ns=0)
            if transaction.verdict is not CoreVerdict.ALLOW:
                raise FixedTraceRunnerError(
                    f"could not certify shared contract for {arm.value}"
                )
            self._prototypes[arm] = prototype
        roots = {prototype.mission.root_digest for prototype in self._prototypes.values()}
        contracts = {
            prototype.monitor.active_contract.contract_digest
            for prototype in self._prototypes.values()
            if prototype.monitor.active_contract is not None
        }
        if len(roots) != 1 or len(contracts) != 1:
            raise FixedTraceRunnerError(
                "arm initialization changed shared mission/contract identity"
            )

    def evaluate(
        self,
        *,
        unit_id: str,
        proposals: Sequence[TypedTraceProposal],
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        if [item.proposal_index for item in proposals] != list(range(len(proposals))):
            raise FixedTraceRunnerError("proposal indices must be contiguous from zero")
        if any(item.episode_nonce != self.episode_nonce for item in proposals):
            raise FixedTraceRunnerError("proposal trace is bound to another episode")
        for item in proposals:
            proposal = item.proposal()
            assessment = item.assessment()
            execution_contract = item.execution_contract()
            state = item.state()
            for arm in ARM_ORDER:
                prototype = self._prototypes[arm]
                started = perf_counter_ns()
                authorization = prototype.authorize_exact_prefix(
                    assessment=assessment,
                    execution_contract=execution_contract,
                    proposal=proposal,
                    state=state,
                    now_ns=item.execution_contract_issued_at_ns,
                    intervention_policy=self.intervention_policy,
                )
                latency = perf_counter_ns() - started
                rows.append(
                    {
                        "unit_id": unit_id,
                        "proposal_index": item.proposal_index,
                        "action_block_digest": proposal.action_block_digest,
                        "proposal_digest": proposal.proposal_digest,
                        "assessment_digest": assessment.assessment_digest,
                        "execution_contract_digest": (
                            execution_contract.execution_contract_digest
                        ),
                        "arm": arm.value,
                        "intent_action_enabled": arm.intent_enabled,
                        "action_execution_enabled": arm.execution_enabled,
                        "authorization_verdict": authorization.verdict.value,
                        "intent_verdict": authorization.intent_check.verdict.value,
                        "execution_verdict": authorization.execution_check.verdict.value,
                        "authorization_digest": authorization.authorization_digest,
                        "final_command_digest": authorization.final_command_digest,
                        "checker_latency_ns": latency,
                        "dispatch_attempted": False,
                    }
                )
        for prototype in self._prototypes.values():
            sink = prototype.dispatch_boundary.sink
            if not isinstance(sink, InMemoryCommandSink) or sink.applied:
                raise FixedTraceRunnerError("fixed-trace gate reached a dispatch sink")
        return {
            "schema": FIXED_TRACE_RESULT_SCHEMA,
            "unit_id": unit_id,
            "dispatch_attempt_count": 0,
            "rows": rows,
        }


def proposal_trace_payload(
    *,
    unit_id: str,
    condition: str,
    proposal_adapter_id: str,
    proposal_adapter_sha256: str,
    proposals: Iterable[TypedTraceProposal],
) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "condition": condition,
        "proposal_adapter": {
            "id": proposal_adapter_id,
            "sha256": proposal_adapter_sha256,
        },
        "proposals": [proposal.export_payload() for proposal in proposals],
    }


__all__ = [
    "FixedTraceRunnerError",
    "SharedFourArmShadowRunner",
    "TypedTraceProposal",
    "proposal_trace_payload",
]
