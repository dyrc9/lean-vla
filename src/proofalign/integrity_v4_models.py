"""Semantic-bound runtime records for the ProofAlign integrity v4 mainline.

The frozen ``proofalign-integrity-v3`` records remain in
``proofalign.integrity_models``.  This module deliberately defines a new digest
domain instead of adding fields to those historical records.

These records establish exact byte-level provenance and binding.  As with the
v3 records, their digests are not authentication and do not prove that a
semantic selector, local checker, or physical observer is correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, prod
from typing import Any, Iterable, Sequence

from proofalign.digests import digest_payload
from proofalign.semantic_trust import (
    SemanticSubtaskArtifact,
    SemanticTrustPolicy,
    TrustedActionPrompt,
    TrustedSemanticContext,
    UntrustedPolicyView,
    compile_trusted_action_prompt,
)


METHOD_ID = "proofalign-integrity-v4"
RUNTIME_SCHEMA_VERSION = "proofalign.semantic-integrity-runtime-v4"


class IntegrityV4Error(ValueError):
    """Raised when a semantic-bound v4 record is malformed or misbound."""


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntegrityV4Error(f"{name} must be a non-empty string")
    return value


def _require_digest(name: str, value: str) -> str:
    _require_text(name, value)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise IntegrityV4Error(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_optional_digest(name: str, value: str | None) -> str | None:
    if value is not None:
        _require_digest(name, value)
    return value


def _require_nonnegative(name: str, value: int) -> int:
    if type(value) is not int or value < 0:
        raise IntegrityV4Error(f"{name} must be a non-negative integer")
    return value


def _freeze_text(
    values: Iterable[str], *, name: str, require_nonempty: bool = False
) -> tuple[str, ...]:
    frozen = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in frozen):
        raise IntegrityV4Error(f"{name} must contain non-empty strings")
    if len(frozen) != len(set(frozen)):
        raise IntegrityV4Error(f"{name} must not contain duplicates")
    if require_nonempty and not frozen:
        raise IntegrityV4Error(f"{name} must be non-empty")
    return frozen


def _freeze_command(command: Iterable[float]) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in command)
    except (TypeError, ValueError) as exc:
        raise IntegrityV4Error("command must be numeric") from exc
    if not frozen or any(not isfinite(value) for value in frozen):
        raise IntegrityV4Error("command must be a non-empty finite numeric sequence")
    return frozen


def _freeze_shape(
    shape: Sequence[int], *, value_count: int
) -> tuple[int, ...]:
    frozen = tuple(shape)
    if (
        not frozen
        or any(type(dimension) is not int or dimension <= 0 for dimension in frozen)
        or prod(frozen) != value_count
    ):
        raise IntegrityV4Error(
            "command_shape must contain positive dimensions whose product "
            "equals the flattened command length"
        )
    return frozen


def command_digest(command: Iterable[float]) -> str:
    """Digest one exact numeric command in the v4 command domain."""

    return digest_payload(
        {
            "schema": f"{RUNTIME_SCHEMA_VERSION}.command",
            "command": _freeze_command(command),
        }
    )


class SemanticBindingStatus(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class ActionAssessmentKind(str, Enum):
    """Provenance class for a v4 local ActionBlock checker."""

    FROZEN_MODEL = "frozen_model"
    ANALYTIC = "analytic"
    SHADOW_ROLLOUT = "shadow_rollout"
    ORACLE_TEST = "oracle_test"

    @property
    def efficacy_eligible(self) -> bool:
        return self in (
            ActionAssessmentKind.FROZEN_MODEL,
            ActionAssessmentKind.ANALYTIC,
            ActionAssessmentKind.SHADOW_ROLLOUT,
        )


@dataclass(frozen=True)
class ActionProposal:
    """One exact executable prefix with its complete semantic provenance.

    ``UNKNOWN`` records are useful for fail-closed audit trails, but cannot
    carry a trusted prompt digest and are never dispatchable.
    """

    episode_nonce: str
    proposal_index: int
    candidate_index: int
    proposed_at_ns: int
    state_epoch: int
    semantic_context_digest: str
    semantic_subtask_digest: str
    semantic_binding_status: SemanticBindingStatus
    exact_policy_prompt_digest: str | None
    trusted_observation_digest: str
    policy_observation_digest: str
    source_policy_chunk_digest: str
    command: tuple[float, ...]
    command_shape: tuple[int, ...]
    semantic_unknown_reason: str | None = None
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    proposal_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "action proposal uses an unsupported semantic-integrity version"
            )
        _require_text("episode_nonce", self.episode_nonce)
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("candidate_index", self.candidate_index)
        _require_nonnegative("proposed_at_ns", self.proposed_at_ns)
        _require_nonnegative("state_epoch", self.state_epoch)
        for name in (
            "semantic_context_digest",
            "semantic_subtask_digest",
            "trusted_observation_digest",
            "policy_observation_digest",
            "source_policy_chunk_digest",
        ):
            _require_digest(name, getattr(self, name))
        if not isinstance(self.semantic_binding_status, SemanticBindingStatus):
            raise TypeError(
                "semantic_binding_status must be SemanticBindingStatus"
            )
        _require_optional_digest(
            "exact_policy_prompt_digest", self.exact_policy_prompt_digest
        )
        if self.semantic_binding_status is SemanticBindingStatus.KNOWN:
            if self.exact_policy_prompt_digest is None:
                raise IntegrityV4Error(
                    "known semantic binding requires an exact trusted prompt digest"
                )
            if self.semantic_unknown_reason is not None:
                raise IntegrityV4Error(
                    "known semantic binding cannot carry an unknown reason"
                )
        else:
            if self.exact_policy_prompt_digest is not None:
                raise IntegrityV4Error(
                    "unknown semantic binding cannot carry a trusted prompt digest"
                )
            _require_text(
                "semantic_unknown_reason", self.semantic_unknown_reason or ""
            )
        command = _freeze_command(self.command)
        shape = _freeze_shape(self.command_shape, value_count=len(command))
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "command_shape", shape)
        object.__setattr__(self, "proposal_digest", digest_payload(self.payload()))

    @classmethod
    def from_trusted_semantics(
        cls,
        *,
        context: TrustedSemanticContext,
        artifact: SemanticSubtaskArtifact,
        trust_policy: SemanticTrustPolicy,
        prompt: TrustedActionPrompt,
        policy_view: UntrustedPolicyView,
        candidate_index: int,
        proposed_at_ns: int,
        source_policy_chunk_digest: str,
        command: Iterable[float],
        command_shape: Sequence[int],
    ) -> "ActionProposal":
        """Construct a dispatchable proposal from an exactly verified ``Z_t``.

        Recompiling the prompt here prevents a caller from pairing valid
        semantic digests with different prompt bytes.  Unknown semantic
        artifacts fail in ``compile_trusted_action_prompt``.
        """

        expected_prompt = compile_trusted_action_prompt(
            context, artifact, trust_policy
        )
        if prompt != expected_prompt:
            raise IntegrityV4Error(
                "trusted action prompt does not match the bound semantic context"
            )
        return cls(
            episode_nonce=context.episode_nonce,
            proposal_index=context.proposal_index,
            candidate_index=candidate_index,
            proposed_at_ns=proposed_at_ns,
            state_epoch=context.state_epoch,
            semantic_context_digest=context.context_digest,
            semantic_subtask_digest=artifact.artifact_digest,
            semantic_binding_status=SemanticBindingStatus.KNOWN,
            exact_policy_prompt_digest=prompt.exact_prompt_digest,
            trusted_observation_digest=context.trusted_observation_digest,
            policy_observation_digest=policy_view.policy_observation_digest,
            source_policy_chunk_digest=source_policy_chunk_digest,
            command=tuple(command),
            command_shape=tuple(command_shape),
        )

    @property
    def dispatchable(self) -> bool:
        """Whether schema-level semantic provenance permits later authorization."""

        return (
            self.semantic_binding_status is SemanticBindingStatus.KNOWN
            and self.exact_policy_prompt_digest is not None
        )

    @property
    def action_block_digest(self) -> str:
        return self.proposal_digest

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "candidate_index": self.candidate_index,
            "proposed_at_ns": self.proposed_at_ns,
            "state_epoch": self.state_epoch,
            "semantic_context_digest": self.semantic_context_digest,
            "semantic_subtask_digest": self.semantic_subtask_digest,
            "semantic_binding_status": self.semantic_binding_status.value,
            "semantic_unknown_reason": self.semantic_unknown_reason,
            "exact_policy_prompt_digest": self.exact_policy_prompt_digest,
            "trusted_observation_digest": self.trusted_observation_digest,
            "policy_observation_digest": self.policy_observation_digest,
            "source_policy_chunk_digest": self.source_policy_chunk_digest,
            "command": self.command,
            "command_shape": self.command_shape,
        }


@dataclass(frozen=True)
class ActionBlockAssessment:
    """Local checker result bound to one exact final v4 ActionBlock."""

    assessor_id: str
    assessor_version: str
    assessor_config_digest: str
    assessor_kind: ActionAssessmentKind
    episode_nonce: str
    proposal_index: int
    candidate_index: int
    generated_at_ns: int
    state_epoch: int
    semantic_subtask_digest: str
    trusted_observation_digest: str
    action_block_digest: str
    known: bool
    motion_atoms: tuple[str, ...]
    precondition_atoms: tuple[str, ...]
    predicted_effect_atoms: tuple[str, ...]
    predicted_violation_atoms: tuple[str, ...]
    progress_margin: float | None
    target: str | None = None
    part: str | None = None
    region: str | None = None
    unknown_reason: str | None = None
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "action assessment uses an unsupported semantic-integrity version"
            )
        for name in ("assessor_id", "assessor_version", "episode_nonce"):
            _require_text(name, getattr(self, name))
        _require_digest("assessor_config_digest", self.assessor_config_digest)
        if not isinstance(self.assessor_kind, ActionAssessmentKind):
            raise TypeError("assessor_kind must be ActionAssessmentKind")
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("candidate_index", self.candidate_index)
        _require_nonnegative("generated_at_ns", self.generated_at_ns)
        _require_nonnegative("state_epoch", self.state_epoch)
        for name in (
            "semantic_subtask_digest",
            "trusted_observation_digest",
            "action_block_digest",
        ):
            _require_digest(name, getattr(self, name))
        if type(self.known) is not bool:
            raise TypeError("known must be bool")
        for name in (
            "motion_atoms",
            "precondition_atoms",
            "predicted_effect_atoms",
            "predicted_violation_atoms",
        ):
            object.__setattr__(
                self,
                name,
                _freeze_text(
                    getattr(self, name),
                    name=name,
                    require_nonempty=(name == "motion_atoms" and self.known),
                ),
            )
        for name in ("target", "part", "region"):
            value = getattr(self, name)
            if value is not None:
                _require_text(name, value)
        if self.known:
            if self.unknown_reason is not None:
                raise IntegrityV4Error(
                    "known action assessment cannot carry an unknown reason"
                )
            if not isinstance(self.progress_margin, (int, float)) or isinstance(
                self.progress_margin, bool
            ):
                raise IntegrityV4Error(
                    "known action assessment requires a numeric progress margin"
                )
            margin = float(self.progress_margin)
            if not isfinite(margin):
                raise IntegrityV4Error("progress_margin must be finite")
            object.__setattr__(self, "progress_margin", margin)
        else:
            if (
                self.motion_atoms
                or self.precondition_atoms
                or self.predicted_effect_atoms
                or self.predicted_violation_atoms
                or self.progress_margin is not None
                or any(
                    value is not None
                    for value in (self.target, self.part, self.region)
                )
            ):
                raise IntegrityV4Error(
                    "unknown action assessment cannot carry predictions"
                )
            _require_text("unknown_reason", self.unknown_reason or "")
        object.__setattr__(
            self, "assessment_digest", digest_payload(self.payload())
        )

    @classmethod
    def for_proposal(
        cls,
        proposal: ActionProposal,
        *,
        assessor_id: str,
        assessor_version: str,
        assessor_config_digest: str,
        assessor_kind: ActionAssessmentKind,
        generated_at_ns: int,
        known: bool,
        motion_atoms: Iterable[str] = (),
        precondition_atoms: Iterable[str] = (),
        predicted_effect_atoms: Iterable[str] = (),
        predicted_violation_atoms: Iterable[str] = (),
        progress_margin: float | None = None,
        target: str | None = None,
        part: str | None = None,
        region: str | None = None,
        unknown_reason: str | None = None,
    ) -> "ActionBlockAssessment":
        if generated_at_ns < proposal.proposed_at_ns:
            raise IntegrityV4Error(
                "action assessment cannot predate the exact action proposal"
            )
        return cls(
            assessor_id=assessor_id,
            assessor_version=assessor_version,
            assessor_config_digest=assessor_config_digest,
            assessor_kind=assessor_kind,
            episode_nonce=proposal.episode_nonce,
            proposal_index=proposal.proposal_index,
            candidate_index=proposal.candidate_index,
            generated_at_ns=generated_at_ns,
            state_epoch=proposal.state_epoch,
            semantic_subtask_digest=proposal.semantic_subtask_digest,
            trusted_observation_digest=proposal.trusted_observation_digest,
            action_block_digest=proposal.action_block_digest,
            known=known,
            motion_atoms=tuple(motion_atoms),
            precondition_atoms=tuple(precondition_atoms),
            predicted_effect_atoms=tuple(predicted_effect_atoms),
            predicted_violation_atoms=tuple(predicted_violation_atoms),
            progress_margin=progress_margin,
            target=target,
            part=part,
            region=region,
            unknown_reason=unknown_reason,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "assessor_id": self.assessor_id,
            "assessor_version": self.assessor_version,
            "assessor_config_digest": self.assessor_config_digest,
            "assessor_kind": self.assessor_kind.value,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "candidate_index": self.candidate_index,
            "generated_at_ns": self.generated_at_ns,
            "state_epoch": self.state_epoch,
            "semantic_subtask_digest": self.semantic_subtask_digest,
            "trusted_observation_digest": self.trusted_observation_digest,
            "action_block_digest": self.action_block_digest,
            "known": self.known,
            "motion_atoms": self.motion_atoms,
            "target": self.target,
            "part": self.part,
            "region": self.region,
            "precondition_atoms": self.precondition_atoms,
            "predicted_effect_atoms": self.predicted_effect_atoms,
            "predicted_violation_atoms": self.predicted_violation_atoms,
            "progress_margin": self.progress_margin,
            "unknown_reason": self.unknown_reason,
        }


@dataclass(frozen=True)
class BlockExecutionContract:
    """Effect obligation for an assessed, exact final v4 ActionBlock."""

    issuer_id: str
    issuer_version: str
    issuer_config_digest: str
    episode_nonce: str
    proposal_index: int
    candidate_index: int
    issued_at_ns: int
    state_epoch: int
    semantic_subtask_digest: str
    exact_policy_prompt_digest: str
    action_block_digest: str
    assessment_digest: str
    expected_effect_atoms: tuple[str, ...]
    forbidden_effect_atoms: tuple[str, ...]
    observation_window_steps: int
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    execution_contract_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "execution contract uses an unsupported semantic-integrity version"
            )
        for name in ("issuer_id", "issuer_version", "episode_nonce"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("candidate_index", self.candidate_index)
        _require_nonnegative("issued_at_ns", self.issued_at_ns)
        _require_nonnegative("state_epoch", self.state_epoch)
        for name in (
            "issuer_config_digest",
            "semantic_subtask_digest",
            "exact_policy_prompt_digest",
            "action_block_digest",
            "assessment_digest",
        ):
            _require_digest(name, getattr(self, name))
        expected = _freeze_text(
            self.expected_effect_atoms,
            name="expected_effect_atoms",
            require_nonempty=True,
        )
        forbidden = _freeze_text(
            self.forbidden_effect_atoms, name="forbidden_effect_atoms"
        )
        overlap = set(expected).intersection(forbidden)
        if overlap:
            raise IntegrityV4Error(
                "expected and forbidden effect atoms overlap: "
                + ", ".join(sorted(overlap))
            )
        if (
            type(self.observation_window_steps) is not int
            or self.observation_window_steps <= 0
        ):
            raise IntegrityV4Error(
                "observation_window_steps must be a positive integer"
            )
        object.__setattr__(self, "expected_effect_atoms", expected)
        object.__setattr__(self, "forbidden_effect_atoms", forbidden)
        object.__setattr__(
            self,
            "execution_contract_digest",
            digest_payload(self.payload()),
        )

    @classmethod
    def for_assessment(
        cls,
        proposal: ActionProposal,
        assessment: ActionBlockAssessment,
        *,
        issuer_id: str,
        issuer_version: str,
        issuer_config_digest: str,
        issued_at_ns: int,
        expected_effect_atoms: Iterable[str],
        forbidden_effect_atoms: Iterable[str],
        observation_window_steps: int,
    ) -> "BlockExecutionContract":
        issues = assessment_binding_issues(proposal, assessment)
        if issues:
            raise IntegrityV4Error(
                "assessment is not bound to proposal: " + ",".join(issues)
            )
        if not proposal.dispatchable:
            raise IntegrityV4Error(
                "execution contract requires a dispatchable semantic proposal"
            )
        if not assessment.known:
            raise IntegrityV4Error(
                "execution contract cannot be compiled from unknown assessment"
            )
        if issued_at_ns < assessment.generated_at_ns:
            raise IntegrityV4Error(
                "execution contract cannot predate its bound assessment"
            )
        if proposal.exact_policy_prompt_digest is None:  # pragma: no cover
            raise AssertionError("dispatchable proposal lacks prompt digest")
        return cls(
            issuer_id=issuer_id,
            issuer_version=issuer_version,
            issuer_config_digest=issuer_config_digest,
            episode_nonce=proposal.episode_nonce,
            proposal_index=proposal.proposal_index,
            candidate_index=proposal.candidate_index,
            issued_at_ns=issued_at_ns,
            state_epoch=proposal.state_epoch,
            semantic_subtask_digest=proposal.semantic_subtask_digest,
            exact_policy_prompt_digest=proposal.exact_policy_prompt_digest,
            action_block_digest=proposal.action_block_digest,
            assessment_digest=assessment.assessment_digest,
            expected_effect_atoms=tuple(expected_effect_atoms),
            forbidden_effect_atoms=tuple(forbidden_effect_atoms),
            observation_window_steps=observation_window_steps,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "issuer_id": self.issuer_id,
            "issuer_version": self.issuer_version,
            "issuer_config_digest": self.issuer_config_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "candidate_index": self.candidate_index,
            "issued_at_ns": self.issued_at_ns,
            "state_epoch": self.state_epoch,
            "semantic_subtask_digest": self.semantic_subtask_digest,
            "exact_policy_prompt_digest": self.exact_policy_prompt_digest,
            "action_block_digest": self.action_block_digest,
            "assessment_digest": self.assessment_digest,
            "expected_effect_atoms": self.expected_effect_atoms,
            "forbidden_effect_atoms": self.forbidden_effect_atoms,
            "observation_window_steps": self.observation_window_steps,
        }


@dataclass(frozen=True)
class PrefixAuthorization:
    """Fresh, exact, one-prefix authorization issued after final rebinding."""

    authorizer_id: str
    authorizer_version: str
    authorizer_config_digest: str
    episode_nonce: str
    proposal_index: int
    candidate_index: int
    state_epoch: int
    semantic_context_digest: str
    semantic_subtask_digest: str
    exact_policy_prompt_digest: str
    trusted_observation_digest: str
    action_block_digest: str
    assessment_digest: str
    execution_contract_digest: str
    final_command: tuple[float, ...]
    command_shape: tuple[int, ...]
    issued_at_ns: int
    valid_until_ns: int
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    final_command_digest: str = field(init=False)
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "prefix authorization uses an unsupported semantic-integrity version"
            )
        for name in (
            "authorizer_id",
            "authorizer_version",
            "episode_nonce",
        ):
            _require_text(name, getattr(self, name))
        for name in (
            "authorizer_config_digest",
            "semantic_context_digest",
            "semantic_subtask_digest",
            "exact_policy_prompt_digest",
            "trusted_observation_digest",
            "action_block_digest",
            "assessment_digest",
            "execution_contract_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("candidate_index", self.candidate_index)
        _require_nonnegative("state_epoch", self.state_epoch)
        _require_nonnegative("issued_at_ns", self.issued_at_ns)
        if (
            type(self.valid_until_ns) is not int
            or self.valid_until_ns <= self.issued_at_ns
        ):
            raise IntegrityV4Error("authorization validity window is empty")
        final = _freeze_command(self.final_command)
        shape = _freeze_shape(self.command_shape, value_count=len(final))
        if len(shape) != 2:
            raise IntegrityV4Error(
                "v4 prefix authorization requires a rank-2 command shape"
            )
        object.__setattr__(self, "final_command", final)
        object.__setattr__(self, "command_shape", shape)
        object.__setattr__(
            self, "final_command_digest", command_digest(final)
        )
        object.__setattr__(
            self, "authorization_digest", digest_payload(self.payload())
        )

    @classmethod
    def for_transaction(
        cls,
        proposal: ActionProposal,
        assessment: ActionBlockAssessment,
        contract: BlockExecutionContract,
        *,
        authorizer_id: str,
        authorizer_version: str,
        authorizer_config_digest: str,
        issued_at_ns: int,
        valid_until_ns: int,
        current_state_epoch: int,
        current_trusted_observation_digest: str,
    ) -> "PrefixAuthorization":
        issues = execution_contract_binding_issues(
            proposal, assessment, contract
        )
        if issues:
            raise IntegrityV4Error(
                "authorization artifacts are not exactly bound: "
                + ",".join(issues)
            )
        if not proposal.dispatchable:
            raise IntegrityV4Error(
                "authorization requires a dispatchable semantic proposal"
            )
        if not assessment.known:
            raise IntegrityV4Error(
                "authorization requires a known fresh assessment"
            )
        if assessment.predicted_violation_atoms:
            raise IntegrityV4Error(
                "authorization refuses assessed violations: "
                + ",".join(assessment.predicted_violation_atoms)
            )
        if contract.issued_at_ns < assessment.generated_at_ns:
            raise IntegrityV4Error(
                "authorization contract predates its assessment"
            )
        if issued_at_ns < contract.issued_at_ns:
            raise IntegrityV4Error(
                "authorization cannot predate its execution contract"
            )
        if current_state_epoch != proposal.state_epoch:
            raise IntegrityV4Error(
                "authorization state epoch is stale or substituted"
            )
        _require_digest(
            "current_trusted_observation_digest",
            current_trusted_observation_digest,
        )
        if (
            current_trusted_observation_digest
            != proposal.trusted_observation_digest
        ):
            raise IntegrityV4Error(
                "authorization trusted observation is stale or substituted"
            )
        if proposal.exact_policy_prompt_digest is None:  # pragma: no cover
            raise AssertionError("dispatchable proposal lacks prompt digest")
        return cls(
            authorizer_id=authorizer_id,
            authorizer_version=authorizer_version,
            authorizer_config_digest=authorizer_config_digest,
            episode_nonce=proposal.episode_nonce,
            proposal_index=proposal.proposal_index,
            candidate_index=proposal.candidate_index,
            state_epoch=proposal.state_epoch,
            semantic_context_digest=proposal.semantic_context_digest,
            semantic_subtask_digest=proposal.semantic_subtask_digest,
            exact_policy_prompt_digest=proposal.exact_policy_prompt_digest,
            trusted_observation_digest=proposal.trusted_observation_digest,
            action_block_digest=proposal.action_block_digest,
            assessment_digest=assessment.assessment_digest,
            execution_contract_digest=contract.execution_contract_digest,
            final_command=proposal.command,
            command_shape=proposal.command_shape,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
        )

    @property
    def action_count(self) -> int:
        return self.command_shape[0]

    @property
    def action_dimension(self) -> int:
        return self.command_shape[1]

    def action_at(self, step_index: int) -> tuple[float, ...]:
        if type(step_index) is not int or not 0 <= step_index < self.action_count:
            raise IntegrityV4Error("authorization action index is out of range")
        start = step_index * self.action_dimension
        return self.final_command[start : start + self.action_dimension]

    def is_fresh(self, now_ns: int) -> bool:
        return (
            type(now_ns) is int
            and self.issued_at_ns <= now_ns <= self.valid_until_ns
        )

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "authorizer_id": self.authorizer_id,
            "authorizer_version": self.authorizer_version,
            "authorizer_config_digest": self.authorizer_config_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "candidate_index": self.candidate_index,
            "state_epoch": self.state_epoch,
            "semantic_context_digest": self.semantic_context_digest,
            "semantic_subtask_digest": self.semantic_subtask_digest,
            "exact_policy_prompt_digest": self.exact_policy_prompt_digest,
            "trusted_observation_digest": self.trusted_observation_digest,
            "action_block_digest": self.action_block_digest,
            "assessment_digest": self.assessment_digest,
            "execution_contract_digest": self.execution_contract_digest,
            "final_command": self.final_command,
            "command_shape": self.command_shape,
            "issued_at_ns": self.issued_at_ns,
            "valid_until_ns": self.valid_until_ns,
        }


@dataclass(frozen=True)
class StepDispatchReceipt:
    """Receipt for one action consumed under a logical prefix authorization."""

    authorization_digest: str
    action_block_digest: str
    assessment_digest: str
    execution_contract_digest: str
    episode_nonce: str
    proposal_index: int
    step_index: int
    action_count: int
    authorized_action_digest: str
    applied_action: tuple[float, ...]
    applied_at_ns: int
    sink_id: str
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    applied_action_digest: str = field(init=False)
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "dispatch receipt uses an unsupported semantic-integrity version"
            )
        for name in (
            "authorization_digest",
            "action_block_digest",
            "assessment_digest",
            "execution_contract_digest",
            "authorized_action_digest",
        ):
            _require_digest(name, getattr(self, name))
        for name in ("episode_nonce", "sink_id"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("step_index", self.step_index)
        if type(self.action_count) is not int or self.action_count <= 0:
            raise IntegrityV4Error("action_count must be a positive integer")
        if self.step_index >= self.action_count:
            raise IntegrityV4Error("receipt step index exceeds action count")
        _require_nonnegative("applied_at_ns", self.applied_at_ns)
        applied = _freeze_command(self.applied_action)
        object.__setattr__(self, "applied_action", applied)
        object.__setattr__(
            self, "applied_action_digest", command_digest(applied)
        )
        object.__setattr__(
            self, "receipt_digest", digest_payload(self.payload())
        )

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "authorization_digest": self.authorization_digest,
            "action_block_digest": self.action_block_digest,
            "assessment_digest": self.assessment_digest,
            "execution_contract_digest": self.execution_contract_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "step_index": self.step_index,
            "action_count": self.action_count,
            "authorized_action_digest": self.authorized_action_digest,
            "applied_action": self.applied_action,
            "applied_at_ns": self.applied_at_ns,
            "sink_id": self.sink_id,
        }


@dataclass(frozen=True)
class PrefixExecutionEvidence:
    """Receipt/effect record for the observation window of one v4 prefix."""

    observer_id: str
    observer_version: str
    observer_config_digest: str
    authorization_digest: str
    action_block_digest: str
    assessment_digest: str
    execution_contract_digest: str
    episode_nonce: str
    proposal_index: int
    window_started_at_ns: int
    observed_at_ns: int
    initial_observation_digest: str
    observation_digests: tuple[str, ...]
    step_receipt_digests: tuple[str, ...]
    observed_action_digests: tuple[str, ...]
    observed_effect_atoms: tuple[str, ...]
    observed_violation_atoms: tuple[str, ...]
    prefix_complete: bool
    observation_window_complete: bool
    effects_known: bool
    unknown_reason: str | None = None
    method_id: str = METHOD_ID
    schema_version: str = RUNTIME_SCHEMA_VERSION
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != RUNTIME_SCHEMA_VERSION:
            raise IntegrityV4Error(
                "execution evidence uses an unsupported semantic-integrity version"
            )
        for name in (
            "observer_id",
            "observer_version",
            "episode_nonce",
        ):
            _require_text(name, getattr(self, name))
        for name in (
            "observer_config_digest",
            "authorization_digest",
            "action_block_digest",
            "assessment_digest",
            "execution_contract_digest",
            "initial_observation_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("window_started_at_ns", self.window_started_at_ns)
        _require_nonnegative("observed_at_ns", self.observed_at_ns)
        if self.observed_at_ns < self.window_started_at_ns:
            raise IntegrityV4Error(
                "execution evidence observation predates its window"
            )
        for name in (
            "prefix_complete",
            "observation_window_complete",
            "effects_known",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        for name in (
            "observation_digests",
            "step_receipt_digests",
            "observed_action_digests",
        ):
            frozen = tuple(getattr(self, name))
            for value in frozen:
                _require_digest(name, value)
            object.__setattr__(self, name, frozen)
        if not (
            len(self.observation_digests)
            == len(self.step_receipt_digests)
            == len(self.observed_action_digests)
        ):
            raise IntegrityV4Error(
                "evidence must bind one observation and action per receipt"
            )
        for name in ("observed_effect_atoms", "observed_violation_atoms"):
            object.__setattr__(
                self,
                name,
                _freeze_text(getattr(self, name), name=name),
            )
        if self.effects_known:
            if self.unknown_reason is not None:
                raise IntegrityV4Error(
                    "known effects cannot carry an unknown reason"
                )
        else:
            _require_text("unknown_reason", self.unknown_reason or "")
        object.__setattr__(
            self, "evidence_digest", digest_payload(self.payload())
        )

    @classmethod
    def for_window(
        cls,
        authorization: PrefixAuthorization,
        contract: BlockExecutionContract,
        receipts: Sequence[StepDispatchReceipt],
        *,
        observer_id: str,
        observer_version: str,
        observer_config_digest: str,
        window_started_at_ns: int,
        observed_at_ns: int,
        initial_observation_digest: str,
        observation_digests: Sequence[str],
        observed_effect_atoms: Iterable[str],
        observed_violation_atoms: Iterable[str],
        observation_window_complete: bool,
        effects_known: bool,
        unknown_reason: str | None = None,
    ) -> "PrefixExecutionEvidence":
        receipt_tuple = tuple(receipts)
        issues = prefix_receipt_binding_issues(
            authorization, contract, receipt_tuple
        )
        if issues:
            raise IntegrityV4Error(
                "execution receipts are not exactly bound: "
                + ",".join(issues)
            )
        return cls(
            observer_id=observer_id,
            observer_version=observer_version,
            observer_config_digest=observer_config_digest,
            authorization_digest=authorization.authorization_digest,
            action_block_digest=authorization.action_block_digest,
            assessment_digest=authorization.assessment_digest,
            execution_contract_digest=contract.execution_contract_digest,
            episode_nonce=authorization.episode_nonce,
            proposal_index=authorization.proposal_index,
            window_started_at_ns=window_started_at_ns,
            observed_at_ns=observed_at_ns,
            initial_observation_digest=initial_observation_digest,
            observation_digests=tuple(observation_digests),
            step_receipt_digests=tuple(
                receipt.receipt_digest for receipt in receipt_tuple
            ),
            observed_action_digests=tuple(
                receipt.applied_action_digest for receipt in receipt_tuple
            ),
            observed_effect_atoms=tuple(observed_effect_atoms),
            observed_violation_atoms=tuple(observed_violation_atoms),
            prefix_complete=len(receipt_tuple) == authorization.action_count,
            observation_window_complete=observation_window_complete,
            effects_known=effects_known,
            unknown_reason=unknown_reason,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "observer_id": self.observer_id,
            "observer_version": self.observer_version,
            "observer_config_digest": self.observer_config_digest,
            "authorization_digest": self.authorization_digest,
            "action_block_digest": self.action_block_digest,
            "assessment_digest": self.assessment_digest,
            "execution_contract_digest": self.execution_contract_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "window_started_at_ns": self.window_started_at_ns,
            "observed_at_ns": self.observed_at_ns,
            "initial_observation_digest": self.initial_observation_digest,
            "observation_digests": self.observation_digests,
            "step_receipt_digests": self.step_receipt_digests,
            "observed_action_digests": self.observed_action_digests,
            "observed_effect_atoms": self.observed_effect_atoms,
            "observed_violation_atoms": self.observed_violation_atoms,
            "prefix_complete": self.prefix_complete,
            "observation_window_complete": self.observation_window_complete,
            "effects_known": self.effects_known,
            "unknown_reason": self.unknown_reason,
        }


def assessment_binding_issues(
    proposal: ActionProposal,
    assessment: ActionBlockAssessment,
) -> tuple[str, ...]:
    """Return every exact-binding mismatch between a proposal and assessment."""

    comparisons = (
        ("episode_nonce", proposal.episode_nonce, assessment.episode_nonce),
        ("proposal_index", proposal.proposal_index, assessment.proposal_index),
        ("candidate_index", proposal.candidate_index, assessment.candidate_index),
        ("state_epoch", proposal.state_epoch, assessment.state_epoch),
        (
            "semantic_subtask_digest",
            proposal.semantic_subtask_digest,
            assessment.semantic_subtask_digest,
        ),
        (
            "trusted_observation_digest",
            proposal.trusted_observation_digest,
            assessment.trusted_observation_digest,
        ),
        (
            "action_block_digest",
            proposal.action_block_digest,
            assessment.action_block_digest,
        ),
    )
    return tuple(
        f"{name}_mismatch"
        for name, expected, observed in comparisons
        if expected != observed
    )


def execution_contract_binding_issues(
    proposal: ActionProposal,
    assessment: ActionBlockAssessment,
    contract: BlockExecutionContract,
) -> tuple[str, ...]:
    """Return all v4 proposal/assessment/contract identity mismatches."""

    issues = list(assessment_binding_issues(proposal, assessment))
    comparisons = (
        ("episode_nonce", proposal.episode_nonce, contract.episode_nonce),
        ("proposal_index", proposal.proposal_index, contract.proposal_index),
        ("candidate_index", proposal.candidate_index, contract.candidate_index),
        ("state_epoch", proposal.state_epoch, contract.state_epoch),
        (
            "semantic_subtask_digest",
            proposal.semantic_subtask_digest,
            contract.semantic_subtask_digest,
        ),
        (
            "exact_policy_prompt_digest",
            proposal.exact_policy_prompt_digest,
            contract.exact_policy_prompt_digest,
        ),
        (
            "action_block_digest",
            proposal.action_block_digest,
            contract.action_block_digest,
        ),
        (
            "assessment_digest",
            assessment.assessment_digest,
            contract.assessment_digest,
        ),
    )
    issues.extend(
        f"contract_{name}_mismatch"
        for name, expected, observed in comparisons
        if expected != observed
    )
    return tuple(issues)


def authorization_binding_issues(
    proposal: ActionProposal,
    assessment: ActionBlockAssessment,
    contract: BlockExecutionContract,
    authorization: PrefixAuthorization,
) -> tuple[str, ...]:
    """Return exact final-artifact mismatches in a v4 authorization."""

    issues = list(
        execution_contract_binding_issues(proposal, assessment, contract)
    )
    comparisons = (
        ("episode_nonce", proposal.episode_nonce, authorization.episode_nonce),
        (
            "proposal_index",
            proposal.proposal_index,
            authorization.proposal_index,
        ),
        (
            "candidate_index",
            proposal.candidate_index,
            authorization.candidate_index,
        ),
        ("state_epoch", proposal.state_epoch, authorization.state_epoch),
        (
            "semantic_context_digest",
            proposal.semantic_context_digest,
            authorization.semantic_context_digest,
        ),
        (
            "semantic_subtask_digest",
            proposal.semantic_subtask_digest,
            authorization.semantic_subtask_digest,
        ),
        (
            "exact_policy_prompt_digest",
            proposal.exact_policy_prompt_digest,
            authorization.exact_policy_prompt_digest,
        ),
        (
            "trusted_observation_digest",
            proposal.trusted_observation_digest,
            authorization.trusted_observation_digest,
        ),
        (
            "action_block_digest",
            proposal.action_block_digest,
            authorization.action_block_digest,
        ),
        (
            "assessment_digest",
            assessment.assessment_digest,
            authorization.assessment_digest,
        ),
        (
            "execution_contract_digest",
            contract.execution_contract_digest,
            authorization.execution_contract_digest,
        ),
        ("final_command", proposal.command, authorization.final_command),
        ("command_shape", proposal.command_shape, authorization.command_shape),
    )
    issues.extend(
        f"authorization_{name}_mismatch"
        for name, expected, observed in comparisons
        if expected != observed
    )
    return tuple(issues)


def prefix_receipt_binding_issues(
    authorization: PrefixAuthorization,
    contract: BlockExecutionContract,
    receipts: Sequence[StepDispatchReceipt],
) -> tuple[str, ...]:
    """Validate ordered, exact step receipts for one logical authorization."""

    issues: list[str] = []
    if (
        contract.execution_contract_digest
        != authorization.execution_contract_digest
    ):
        issues.append("authorization_contract_mismatch")
    receipt_tuple = tuple(receipts)
    if len(receipt_tuple) > authorization.action_count:
        issues.append("receipt_count_exceeds_authorized_prefix")
    for expected_index, receipt in enumerate(receipt_tuple):
        comparisons = (
            (
                "authorization_digest",
                authorization.authorization_digest,
                receipt.authorization_digest,
            ),
            (
                "action_block_digest",
                authorization.action_block_digest,
                receipt.action_block_digest,
            ),
            (
                "assessment_digest",
                authorization.assessment_digest,
                receipt.assessment_digest,
            ),
            (
                "execution_contract_digest",
                authorization.execution_contract_digest,
                receipt.execution_contract_digest,
            ),
            (
                "episode_nonce",
                authorization.episode_nonce,
                receipt.episode_nonce,
            ),
            (
                "proposal_index",
                authorization.proposal_index,
                receipt.proposal_index,
            ),
            ("step_index", expected_index, receipt.step_index),
            (
                "action_count",
                authorization.action_count,
                receipt.action_count,
            ),
            (
                "authorized_action_digest",
                command_digest(authorization.action_at(expected_index)),
                receipt.authorized_action_digest,
            ),
            (
                "applied_action_digest",
                command_digest(authorization.action_at(expected_index)),
                receipt.applied_action_digest,
            ),
        )
        issues.extend(
            f"receipt_{expected_index}_{name}_mismatch"
            for name, expected, observed in comparisons
            if expected != observed
        )
        if not authorization.is_fresh(receipt.applied_at_ns):
            issues.append(f"receipt_{expected_index}_outside_authorization_window")
    return tuple(issues)


def execution_evidence_binding_issues(
    authorization: PrefixAuthorization,
    contract: BlockExecutionContract,
    receipts: Sequence[StepDispatchReceipt],
    evidence: PrefixExecutionEvidence,
) -> tuple[str, ...]:
    """Return receipt/window/effect evidence binding mismatches."""

    receipt_tuple = tuple(receipts)
    issues = list(
        prefix_receipt_binding_issues(
            authorization, contract, receipt_tuple
        )
    )
    comparisons = (
        (
            "authorization_digest",
            authorization.authorization_digest,
            evidence.authorization_digest,
        ),
        (
            "action_block_digest",
            authorization.action_block_digest,
            evidence.action_block_digest,
        ),
        (
            "assessment_digest",
            authorization.assessment_digest,
            evidence.assessment_digest,
        ),
        (
            "execution_contract_digest",
            contract.execution_contract_digest,
            evidence.execution_contract_digest,
        ),
        (
            "episode_nonce",
            authorization.episode_nonce,
            evidence.episode_nonce,
        ),
        (
            "proposal_index",
            authorization.proposal_index,
            evidence.proposal_index,
        ),
        (
            "step_receipt_digests",
            tuple(receipt.receipt_digest for receipt in receipt_tuple),
            evidence.step_receipt_digests,
        ),
        (
            "observed_action_digests",
            tuple(receipt.applied_action_digest for receipt in receipt_tuple),
            evidence.observed_action_digests,
        ),
        (
            "prefix_complete",
            len(receipt_tuple) == authorization.action_count,
            evidence.prefix_complete,
        ),
    )
    issues.extend(
        f"evidence_{name}_mismatch"
        for name, expected, observed in comparisons
        if expected != observed
    )
    if len(evidence.observation_digests) != len(receipt_tuple):
        issues.append("evidence_observation_window_length_mismatch")
    if receipt_tuple and evidence.observed_at_ns < receipt_tuple[-1].applied_at_ns:
        issues.append("evidence_observation_predates_last_dispatch")
    return tuple(issues)


__all__ = [
    "METHOD_ID",
    "RUNTIME_SCHEMA_VERSION",
    "ActionAssessmentKind",
    "ActionBlockAssessment",
    "ActionProposal",
    "BlockExecutionContract",
    "IntegrityV4Error",
    "PrefixAuthorization",
    "PrefixExecutionEvidence",
    "SemanticBindingStatus",
    "StepDispatchReceipt",
    "assessment_binding_issues",
    "authorization_binding_issues",
    "command_digest",
    "execution_evidence_binding_issues",
    "execution_contract_binding_issues",
    "prefix_receipt_binding_issues",
]
