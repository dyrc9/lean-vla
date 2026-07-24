"""Trusted-input boundary for zero-training semantic-subtask selection.

The semantic branch and the action-policy branch intentionally have different
inputs.  ``TrustedSemanticContext`` contains only the mission input and the
secure observation tap used to choose ``Z_t``.  Potentially attacked policy
prompts, images, and histories are represented by ``UntrustedPolicyView`` and
cannot be passed to the semantic-subtask issuing API.

The checks in this module establish provenance and exact binding under an
allowlisted trusted-computing-base assumption.  They do not prove that a
qualified frozen model's semantic prediction is physically correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from proofalign.digests import digest_payload, digest_text


SEMANTIC_CONTEXT_SCHEMA = "proofalign.trusted-semantic-context-v1"
SEMANTIC_SUBTASK_SCHEMA = "proofalign.semantic-subtask-artifact-v1"
UNTRUSTED_POLICY_VIEW_SCHEMA = "proofalign.untrusted-policy-view-v1"
ACTION_PROMPT_TEMPLATE_VERSION = "proofalign.action-prompt.trusted-v1"


class SemanticTrustError(ValueError):
    """Raised when semantic trust inputs or bindings are invalid."""


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticTrustError(f"{name} must be a non-empty string")
    return value


def _require_digest(name: str, value: str) -> str:
    _require_text(name, value)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise SemanticTrustError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_nonnegative(name: str, value: int) -> int:
    if type(value) is not int or value < 0:
        raise SemanticTrustError(f"{name} must be a non-negative integer")
    return value


def _freeze_text(
    values: Iterable[str], *, name: str, require_nonempty: bool = False
) -> tuple[str, ...]:
    frozen = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in frozen):
        raise SemanticTrustError(f"{name} must contain non-empty strings")
    if len(frozen) != len(set(frozen)):
        raise SemanticTrustError(f"{name} must not contain duplicates")
    if require_nonempty and not frozen:
        raise SemanticTrustError(f"{name} must be non-empty")
    return frozen


@dataclass(frozen=True)
class TrustedComponentIdentity:
    """Exact identity of one component admitted to the semantic TCB."""

    component_id: str
    component_digest: str

    def __post_init__(self) -> None:
        _require_text("component_id", self.component_id)
        _require_digest("component_digest", self.component_digest)


@dataclass(frozen=True)
class SemanticTrustPolicy:
    """Frozen exact allowlist for semantic-input and selector components."""

    task_sources: tuple[TrustedComponentIdentity, ...]
    observation_taps: tuple[TrustedComponentIdentity, ...]
    secure_splits: tuple[TrustedComponentIdentity, ...]
    selector_models: tuple[TrustedComponentIdentity, ...]
    selector_config_digests: tuple[str, ...]
    policy_version: str = "1"

    def __post_init__(self) -> None:
        _require_text("policy_version", self.policy_version)
        for name in (
            "task_sources",
            "observation_taps",
            "secure_splits",
            "selector_models",
        ):
            frozen = tuple(getattr(self, name))
            if not frozen:
                raise SemanticTrustError(f"{name} must be non-empty")
            if any(not isinstance(item, TrustedComponentIdentity) for item in frozen):
                raise SemanticTrustError(
                    f"{name} must contain TrustedComponentIdentity values"
                )
            if len(frozen) != len(set(frozen)):
                raise SemanticTrustError(f"{name} must not contain duplicates")
            object.__setattr__(self, name, frozen)
        configs = _freeze_text(
            self.selector_config_digests,
            name="selector_config_digests",
            require_nonempty=True,
        )
        for digest in configs:
            _require_digest("selector_config_digest", digest)
        object.__setattr__(self, "selector_config_digests", configs)

    @property
    def policy_digest(self) -> str:
        return digest_payload(
            {
                "schema": "proofalign.semantic-trust-policy-v1",
                "policy_version": self.policy_version,
                "task_sources": self.task_sources,
                "observation_taps": self.observation_taps,
                "secure_splits": self.secure_splits,
                "selector_models": self.selector_models,
                "selector_config_digests": self.selector_config_digests,
            }
        )


@dataclass(frozen=True)
class TrustedSemanticContext:
    """Only inputs allowed to influence trusted semantic-subtask selection."""

    episode_nonce: str
    proposal_index: int
    state_epoch: int
    trusted_task: str
    task_source: TrustedComponentIdentity
    trusted_observation_digest: str
    observation_tap: TrustedComponentIdentity
    secure_split: TrustedComponentIdentity
    task_graph_digest: str
    candidate_subtasks: tuple[str, ...]
    selector_model: TrustedComponentIdentity
    selector_config_digest: str
    previous_subtask_digest: str | None = None

    def __post_init__(self) -> None:
        _require_text("episode_nonce", self.episode_nonce)
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("state_epoch", self.state_epoch)
        _require_text("trusted_task", self.trusted_task)
        for name in (
            "task_source",
            "observation_tap",
            "secure_split",
            "selector_model",
        ):
            if not isinstance(getattr(self, name), TrustedComponentIdentity):
                raise SemanticTrustError(
                    f"{name} must be a TrustedComponentIdentity"
                )
        _require_digest(
            "trusted_observation_digest", self.trusted_observation_digest
        )
        _require_digest("task_graph_digest", self.task_graph_digest)
        candidates = _freeze_text(
            self.candidate_subtasks,
            name="candidate_subtasks",
            require_nonempty=True,
        )
        _require_digest("selector_config_digest", self.selector_config_digest)
        if self.previous_subtask_digest is not None:
            _require_digest(
                "previous_subtask_digest", self.previous_subtask_digest
            )
        object.__setattr__(self, "candidate_subtasks", candidates)

    @property
    def trusted_task_digest(self) -> str:
        return digest_text(self.trusted_task)

    @property
    def candidate_set_digest(self) -> str:
        return digest_payload(
            {
                "schema": "proofalign.semantic-candidate-set-v1",
                "ordered_candidates": self.candidate_subtasks,
            }
        )

    @property
    def context_digest(self) -> str:
        return digest_payload(
            {
                "schema": SEMANTIC_CONTEXT_SCHEMA,
                "episode_nonce": self.episode_nonce,
                "proposal_index": self.proposal_index,
                "state_epoch": self.state_epoch,
                "trusted_task_digest": self.trusted_task_digest,
                "task_source": self.task_source,
                "trusted_observation_digest": self.trusted_observation_digest,
                "observation_tap": self.observation_tap,
                "secure_split": self.secure_split,
                "task_graph_digest": self.task_graph_digest,
                "candidate_set_digest": self.candidate_set_digest,
                "selector_model": self.selector_model,
                "selector_config_digest": self.selector_config_digest,
                "previous_subtask_digest": self.previous_subtask_digest,
            }
        )


@dataclass(frozen=True)
class UntrustedPolicyView:
    """Potentially attacked inputs visible only to the action-policy branch."""

    policy_prompt: str
    policy_observation_digest: str
    policy_history_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_prompt, str):
            raise SemanticTrustError("policy_prompt must be a string")
        _require_digest(
            "policy_observation_digest", self.policy_observation_digest
        )
        if self.policy_history_digest is not None:
            _require_digest("policy_history_digest", self.policy_history_digest)

    @property
    def view_digest(self) -> str:
        return digest_payload(
            {
                "schema": UNTRUSTED_POLICY_VIEW_SCHEMA,
                "policy_prompt_digest": digest_text(self.policy_prompt),
                "policy_observation_digest": self.policy_observation_digest,
                "policy_history_digest": self.policy_history_digest,
            }
        )


@dataclass(frozen=True)
class SemanticSubtaskArtifact:
    """A selected ``Z_t`` bound to one exact trusted semantic context."""

    context_digest: str
    selector_model: TrustedComponentIdentity
    selector_config_digest: str
    selected_subtask: str
    selection_method: str
    generated_at_ns: int
    known: bool
    score_margin: float | None = None

    def __post_init__(self) -> None:
        _require_digest("context_digest", self.context_digest)
        if not isinstance(self.selector_model, TrustedComponentIdentity):
            raise SemanticTrustError(
                "selector_model must be a TrustedComponentIdentity"
            )
        _require_digest("selector_config_digest", self.selector_config_digest)
        _require_text("selected_subtask", self.selected_subtask)
        _require_text("selection_method", self.selection_method)
        _require_nonnegative("generated_at_ns", self.generated_at_ns)
        if type(self.known) is not bool:
            raise SemanticTrustError("known must be boolean")
        if self.score_margin is not None:
            if not isinstance(self.score_margin, (int, float)) or isinstance(
                self.score_margin, bool
            ):
                raise SemanticTrustError("score_margin must be numeric")
            margin = float(self.score_margin)
            if not isfinite(margin):
                raise SemanticTrustError("score_margin must be finite")
            object.__setattr__(self, "score_margin", margin)

    @property
    def artifact_digest(self) -> str:
        return digest_payload(
            {
                "schema": SEMANTIC_SUBTASK_SCHEMA,
                "context_digest": self.context_digest,
                "selector_model": self.selector_model,
                "selector_config_digest": self.selector_config_digest,
                "selected_subtask": self.selected_subtask,
                "selection_method": self.selection_method,
                "generated_at_ns": self.generated_at_ns,
                "known": self.known,
                "score_margin": self.score_margin,
            }
        )


@dataclass(frozen=True)
class SemanticTrustDecision:
    """Result of provenance/binding checks, not a physical-correctness proof."""

    trusted_provenance: bool
    reasons: tuple[str, ...]


def verify_semantic_context(
    context: TrustedSemanticContext,
    policy: SemanticTrustPolicy,
) -> SemanticTrustDecision:
    """Check that every semantic input and selector component is allowlisted."""

    reasons = []
    if context.task_source not in policy.task_sources:
        reasons.append("task_source_not_allowlisted")
    if context.observation_tap not in policy.observation_taps:
        reasons.append("observation_tap_not_allowlisted")
    if context.secure_split not in policy.secure_splits:
        reasons.append("secure_split_not_allowlisted")
    if context.selector_model not in policy.selector_models:
        reasons.append("selector_model_not_allowlisted")
    if context.selector_config_digest not in policy.selector_config_digests:
        reasons.append("selector_config_not_allowlisted")
    return SemanticTrustDecision(
        trusted_provenance=not reasons,
        reasons=tuple(reasons),
    )


def issue_semantic_subtask(
    context: TrustedSemanticContext,
    policy: SemanticTrustPolicy,
    *,
    selected_subtask: str,
    selection_method: str,
    generated_at_ns: int,
    known: bool,
    score_margin: float | None = None,
) -> SemanticSubtaskArtifact:
    """Issue ``Z_t`` only from an allowlisted context and legal frontier."""

    decision = verify_semantic_context(context, policy)
    if not decision.trusted_provenance:
        raise SemanticTrustError(
            "untrusted semantic context: " + ",".join(decision.reasons)
        )
    if known and selected_subtask not in context.candidate_subtasks:
        raise SemanticTrustError(
            "known semantic subtask must belong to the bound candidate frontier"
        )
    return SemanticSubtaskArtifact(
        context_digest=context.context_digest,
        selector_model=context.selector_model,
        selector_config_digest=context.selector_config_digest,
        selected_subtask=selected_subtask,
        selection_method=selection_method,
        generated_at_ns=generated_at_ns,
        known=known,
        score_margin=score_margin,
    )


def verify_semantic_subtask(
    context: TrustedSemanticContext,
    artifact: SemanticSubtaskArtifact,
    policy: SemanticTrustPolicy,
) -> SemanticTrustDecision:
    """Verify semantic provenance, exact context binding, and legal membership."""

    reasons = list(verify_semantic_context(context, policy).reasons)
    if artifact.context_digest != context.context_digest:
        reasons.append("semantic_context_digest_mismatch")
    if artifact.selector_model != context.selector_model:
        reasons.append("selector_model_binding_mismatch")
    if artifact.selector_config_digest != context.selector_config_digest:
        reasons.append("selector_config_binding_mismatch")
    if not artifact.known:
        reasons.append("semantic_subtask_unknown")
    elif artifact.selected_subtask not in context.candidate_subtasks:
        reasons.append("semantic_subtask_outside_candidate_frontier")
    return SemanticTrustDecision(
        trusted_provenance=not reasons,
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class TrustedActionPrompt:
    """Fixed-template action prompt compiled without external prompt input."""

    context_digest: str
    semantic_subtask_digest: str
    exact_prompt: str
    template_version: str = ACTION_PROMPT_TEMPLATE_VERSION

    def __post_init__(self) -> None:
        _require_digest("context_digest", self.context_digest)
        _require_digest("semantic_subtask_digest", self.semantic_subtask_digest)
        _require_text("exact_prompt", self.exact_prompt)
        if self.template_version != ACTION_PROMPT_TEMPLATE_VERSION:
            raise SemanticTrustError("unsupported trusted action prompt template")

    @property
    def exact_prompt_digest(self) -> str:
        return digest_text(self.exact_prompt)


def compile_trusted_action_prompt(
    context: TrustedSemanticContext,
    artifact: SemanticSubtaskArtifact,
    policy: SemanticTrustPolicy,
) -> TrustedActionPrompt:
    """Compile the hardened policy prompt solely from trusted ``T`` and ``Z_t``."""

    decision = verify_semantic_subtask(context, artifact, policy)
    if not decision.trusted_provenance:
        raise SemanticTrustError(
            "cannot compile prompt from untrusted semantic subtask: "
            + ",".join(decision.reasons)
        )
    exact_prompt = (
        f"Task: {context.trusted_task}\n"
        f"Current semantic subtask: {artifact.selected_subtask}"
    )
    return TrustedActionPrompt(
        context_digest=context.context_digest,
        semantic_subtask_digest=artifact.artifact_digest,
        exact_prompt=exact_prompt,
    )


__all__ = [
    "ACTION_PROMPT_TEMPLATE_VERSION",
    "SemanticSubtaskArtifact",
    "SemanticTrustDecision",
    "SemanticTrustError",
    "SemanticTrustPolicy",
    "TrustedActionPrompt",
    "TrustedComponentIdentity",
    "TrustedSemanticContext",
    "UntrustedPolicyView",
    "compile_trusted_action_prompt",
    "issue_semantic_subtask",
    "verify_semantic_context",
    "verify_semantic_subtask",
]
