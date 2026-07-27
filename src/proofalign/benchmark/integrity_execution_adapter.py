"""Simulator-facing execution-only adapter for the Integrity v1 prototype.

The adapter owns the sole call to a supplied ``env.step`` function.  A raw
policy command is represented as an ``ActionProposal``; the configured
intervention may project it; and the exact resulting command must pass the
Integrity authorizer before the environment receives it.  It is intentionally
an execution-layer adapter: it does not infer a semantic plan from VLA output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from proofalign.digests import digest_payload, digest_text
from proofalign.integrity_checker import DeterministicFastChecker, ExactPrefixAuthorizer
from proofalign.integrity_models import (
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    CoreVerdict,
    ExecutionEvidence,
    MethodArm,
    StateSnapshot,
    TrustedTaskArtifact,
)
from proofalign.integrity_runtime import AppliedCommand, CommandSink, ProofAlignPrototype

from proofalign.benchmark.integrity_action_envelope import (
    ActionEnvelopeIntervention,
    intervention_audit,
)


class IntegrityDispatchError(RuntimeError):
    """Raised when a command cannot pass the one dispatch boundary."""


@dataclass
class EnvironmentCommandSink(CommandSink):
    """Call the supplied simulator step exactly once for an authorized action."""

    step: Callable[[list[float]], Any]
    normalize: Callable[[Any], tuple[Any, float, bool, dict[str, Any]]]
    sink_id: str = "proofalign-integrity-libero-env-step-v1"
    last_transition: tuple[Any, float, bool, dict[str, Any]] | None = None

    def apply(self, command: tuple[float, ...], *, now_ns: int) -> AppliedCommand:
        self.last_transition = self.normalize(self.step(list(command)))
        return AppliedCommand(command=command, applied_at_ns=now_ns)


def action_envelope_artifact(
    *,
    source_id: str,
    source_version: str,
    artifact_digest: str,
    trusted_instruction: str,
) -> TrustedTaskArtifact:
    """Create the fixed one-phase artifact used by the execution adapter."""

    from proofalign.integrity_models import PhaseTemplate

    return TrustedTaskArtifact(
        source_id=source_id,
        source_version=source_version,
        artifact_digest=artifact_digest,
        instruction_digest=digest_text(trusted_instruction),
        phases=("action_envelope",),
        initial_phase="action_envelope",
        templates=(
            PhaseTemplate(
                phase_before="action_envelope",
                expected_next_phase="action_envelope",
                skill="vla_action_prefix",
                obligation_id="preserve_action_envelope",
                completion_atoms=("rollout_terminal",),
            ),
        ),
        hard_invariants=("raw_policy_action_is_reauthorized_after_projection",),
    )


def snapshot_digest(observation: Any) -> str:
    """Bind each authorization to the adapter's caller-provided observation."""

    return digest_payload(
        {
            "schema": "proofalign.integrity-libero-observation-binding.v1",
            "observation": observation,
        }
    )


@dataclass
class IntegrityExecutionAdapter:
    """Authorize, dispatch, and bind the post-step observation for one episode."""

    prototype: ProofAlignPrototype
    sink: EnvironmentCommandSink
    intervention: ActionEnvelopeIntervention
    tick_ns: int = 1_000_000
    _proposal_index: int = 0

    @classmethod
    def create(
        cls,
        *,
        artifact: TrustedTaskArtifact,
        episode_nonce: str,
        l2_limit: float,
        step: Callable[[list[float]], Any],
        normalize: Callable[[Any], tuple[Any, float, bool, dict[str, Any]]],
    ) -> "IntegrityExecutionAdapter":
        sink = EnvironmentCommandSink(step=step, normalize=normalize)
        prototype = ProofAlignPrototype.create(
            arm=MethodArm.EXECUTION_ONLY,
            artifact=artifact,
            episode_nonce=episode_nonce,
            authorizer=ExactPrefixAuthorizer(
                DeterministicFastChecker(), authorization_ttl_ns=1
            ),
            sink=sink,
        )
        transaction = prototype.certify_contract(now_ns=0)
        if transaction.verdict is not CoreVerdict.ALLOW:
            raise IntegrityDispatchError("could not certify the frozen action-envelope contract")
        return cls(
            prototype=prototype,
            sink=sink,
            intervention=ActionEnvelopeIntervention(l2_limit=l2_limit),
        )

    def dispatch_and_step(
        self,
        *,
        raw_command: Iterable[float],
        observation: Any,
    ) -> tuple[Any, float, bool, dict[str, Any], dict[str, object]]:
        """Dispatch a single raw policy command through the exact boundary."""

        now_ns = (self._proposal_index + 1) * self.tick_ns
        observation_digest = snapshot_digest(observation)
        proposal = ActionProposal(
            episode_nonce=self.prototype.mission.episode_nonce,
            proposal_index=self._proposal_index,
            proposed_at_ns=now_ns,
            observation_digest=observation_digest,
            state_epoch=self._proposal_index,
            command=tuple(raw_command),
        )
        assessment = ActionBlockAssessment(
            assessor_id="proofalign-action-envelope-analytic-assessor",
            assessor_version="1",
            assessor_kind=ActionAssessmentKind.ANALYTIC,
            episode_nonce=self.prototype.mission.episode_nonce,
            proposal_index=self._proposal_index,
            generated_at_ns=now_ns,
            action_block_digest=proposal.action_block_digest,
            observation_digest=observation_digest,
            state_epoch=self._proposal_index,
            known=True,
            predicted_skill="vla_action_prefix",
            predicted_effect_atoms=("command_applied",),
            predicted_violation_atoms=(),
            precondition_atoms=(),
        )
        execution_contract = BlockExecutionContract(
            issuer_id="proofalign-action-envelope-contract-compiler",
            issuer_version="1",
            episode_nonce=self.prototype.mission.episode_nonce,
            proposal_index=self._proposal_index,
            issued_at_ns=now_ns,
            action_block_digest=proposal.action_block_digest,
            assessment_digest=assessment.assessment_digest,
            observation_digest=observation_digest,
            state_epoch=self._proposal_index,
            expected_effect_atoms=("command_applied",),
            forbidden_effect_atoms=(),
            observation_window_steps=1,
        )
        state = StateSnapshot(
            episode_nonce=self.prototype.mission.episode_nonce,
            state_epoch=self._proposal_index,
            observed_at_ns=now_ns,
            max_age_ns=1,
            state_digest=observation_digest,
            known=True,
        )
        authorization = self.prototype.authorize_exact_prefix(
            assessment=assessment,
            execution_contract=execution_contract,
            proposal=proposal,
            state=state,
            now_ns=now_ns,
            intervention_policy=self.intervention,
        )
        if authorization.verdict is not CoreVerdict.ALLOW or authorization.final_command is None:
            raise IntegrityDispatchError(
                "execution authorization rejected policy command: "
                + ", ".join(authorization.execution_check.issues)
            )
        dispatched = self.prototype.dispatch(
            authorization,
            authorization.final_command,
            now_ns=now_ns,
        )
        if dispatched.verdict is not CoreVerdict.ALLOW or dispatched.receipt is None:
            raise IntegrityDispatchError("exact command dispatch failed: " + ", ".join(dispatched.issues))
        if self.sink.last_transition is None:  # pragma: no cover - defensive sink contract check
            raise IntegrityDispatchError("dispatch sink did not return an environment transition")
        next_observation, reward, done, info = self.sink.last_transition
        evidence = ExecutionEvidence(
            authorization_digest=authorization.authorization_digest,
            receipt_digest=dispatched.receipt.receipt_digest,
            action_block_digest=proposal.action_block_digest,
            execution_contract_digest=execution_contract.execution_contract_digest,
            episode_nonce=authorization.episode_nonce,
            proposal_index=authorization.proposal_index,
            observed_at_ns=now_ns,
            observed_command_digest=dispatched.receipt.applied_command_digest,
            observed_atoms=("command_applied",),
            known=True,
            observation_window_complete=True,
            violation=(
                bool(info.get("collision"))
                or (
                    any(bool(value) for value in (info.get("cost") or {}).values())
                    if isinstance(info.get("cost"), dict)
                    else info.get("cost") not in (None, {}, [], 0, 0.0, False)
                )
            ),
        )
        effect = self.prototype.check_effect_update(
            execution_contract=execution_contract,
            authorization=authorization,
            receipt=dispatched.receipt,
            evidence=evidence,
        )
        audit = {
            "schema": "proofalign.integrity-execution-dispatch-audit.v2",
            "method_id": self.prototype.mission.method_id,
            "method_arm": self.prototype.arm.value,
            "proposal_index": proposal.proposal_index,
            "action_assessor_kind": assessment.assessor_kind.value,
            "action_block_digest": proposal.action_block_digest,
            "assessment_digest": assessment.assessment_digest,
            "execution_contract_digest": execution_contract.execution_contract_digest,
            "proposal_digest": proposal.proposal_digest,
            "state_snapshot_digest": state.snapshot_digest,
            "authorization_digest": authorization.authorization_digest,
            "authorization_verdict": authorization.verdict.value,
            "final_command_digest": authorization.final_command_digest,
            "receipt_digest": dispatched.receipt.receipt_digest,
            "effect_evidence_digest": evidence.evidence_digest,
            "effect_verdict": effect.verdict.value,
            "intervention": intervention_audit(
                authorization.intervention,
                l2_limit=self.intervention.l2_limit,
            ),
        }
        self._proposal_index += 1
        return next_observation, reward, done, info, audit


__all__ = [
    "EnvironmentCommandSink",
    "IntegrityDispatchError",
    "IntegrityExecutionAdapter",
    "action_envelope_artifact",
    "snapshot_digest",
]
