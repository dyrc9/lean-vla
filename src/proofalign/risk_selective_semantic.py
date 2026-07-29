"""Risk-selective semantic monitoring with nominal-policy non-interference.

The predecessor stack mixed three distinct concerns:

* physical safety constraints;
* soft task-progress preferences; and
* policy prompting.

That coupling changed every clean action block, stopped an episode after one
soft effect miss, and replaced the policy's full-task prompt with a local
subtask prompt.  This successor preserves the full-task policy and its exact
source action block whenever the trusted checker finds no physical risk.
Soft semantic mismatch and missing progress remain audited, but cause replanning
rather than terminal failure.  Physical-risk atoms, observed violations, and
execution-integrity failures remain fail closed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Iterator

import numpy as np

from proofalign.contact_phase_pick_up import (
    ContactPhaseLocalCheckerConfig,
    ContactPhaseSemanticExecutablePrefixChecker,
)
from proofalign.digests import digest_payload
from proofalign.integrity_v4_runtime import (
    ExecutionEvaluation,
    SingleUsePrefixDispatchBoundary,
    TransactionVerdict,
)
from proofalign.horizon_consistent_release_prefix import (
    ReleasePrefixSemanticExecutablePrefixChecker,
)
from proofalign.semantic_action_selection import (
    select_checked_action_block,
)
from proofalign.semantic_local_checker import (
    LOCAL_CHECKER_ID,
    LocalActionAssessment,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
)
from proofalign.semantic_policy_wrapper import (
    DeterministicSemanticSelection,
    SemanticPolicyPreparation,
    SemanticPolicyRequest,
    TrustedSemanticPolicyWrapper,
)
from scripts import run_l2_execution_attack_eval_v2 as v2
from scripts import run_l2_execution_attack_eval_v3 as v3


RISK_SELECTIVE_CHECKER_VERSION = "6"
RISK_SELECTIVE_AUDIT_SCHEMA = (
    "proofalign.semantic-risk-selective-selection.v9"
)
RISK_SELECTIVE_EFFECT_POLICY_VERSION = "1"
PHYSICAL_RISK_ATOM_PREFIXES = (
    "translation_velocity_limit",
    "rotation_velocity_limit",
    "workspace_exit",
    "unexpected_contact_neighborhood:",
)


def is_physical_risk_atom(atom: str) -> bool:
    """Return whether a predicted checker atom is a physical hard gate."""

    return isinstance(atom, str) and atom.startswith(
        PHYSICAL_RISK_ATOM_PREFIXES
    )


@dataclass(frozen=True)
class RiskSelectiveLocalCheckerConfig(
    ContactPhaseLocalCheckerConfig
):
    """Content-addressed identity for the physical/soft partition."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": RISK_SELECTIVE_CHECKER_VERSION,
                **self.__dict__,
                "physical_risk_atom_prefixes": (
                    PHYSICAL_RISK_ATOM_PREFIXES
                ),
                "soft_semantic_mismatch_policy": (
                    "advisory_replan_without_command_change"
                ),
                "nominal_policy_prompt": "trusted_full_task",
            }
        )


class RiskSelectiveSemanticExecutablePrefixChecker(
    ContactPhaseSemanticExecutablePrefixChecker
):
    """Keep physical gates hard while making task progress advisory."""

    def __init__(
        self,
        config: LocalCheckerConfig | None = None,
    ) -> None:
        selected = (
            RiskSelectiveLocalCheckerConfig()
            if config is None
            else RiskSelectiveLocalCheckerConfig(**config.__dict__)
        )
        # Initialize the shared base directly: every intermediate constructor
        # deliberately re-wraps the config with its own historical identity.
        # The assess methods remain in the MRO, but the v9 partition must have
        # its own content-addressed config in evidence.
        SemanticExecutablePrefixChecker.__init__(self, selected)

    def predecessor_assess(self, **kwargs: Any) -> LocalActionAssessment:
        """Expose the unpartitioned predecessor result for audit only."""

        return super().assess(**kwargs)

    def assess(self, **kwargs: Any) -> LocalActionAssessment:
        predecessor = self.predecessor_assess(**kwargs)
        if not predecessor.known:
            return predecessor
        physical = tuple(
            atom
            for atom in predecessor.violation_atoms
            if is_physical_risk_atom(atom)
        )
        advisory = tuple(
            atom
            for atom in predecessor.violation_atoms
            if atom not in physical
        )
        preconditions = tuple(
            dict.fromkeys(
                (
                    *predecessor.precondition_atoms,
                    "risk_selective_nominal_monitor",
                    *(
                        f"advisory_semantic_atom:{atom}"
                        for atom in advisory
                    ),
                )
            )
        )
        return replace(
            predecessor,
            semantic_compatible=not physical,
            precondition_atoms=preconditions,
            violation_atoms=physical,
            progress_margin=(
                predecessor.progress_margin
                if physical
                else max(
                    float(predecessor.progress_margin or 0.0),
                    self.config.min_progress_m,
                )
            ),
        )


class RiskSelectiveCandidatePolicy(v2.BoundedCandidatePolicy):
    """Authorize an unchanged nominal block unless a physical gate fires."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        if self.candidate_count != 1 or self.replan_steps != 10:
            raise RuntimeError(
                "risk-selective policy requires frozen H10xK1"
            )
        wrapper = self.wrapper
        request = self.request
        if wrapper is None or request is None:
            raise RuntimeError(
                "risk-selective policy lacks semantic bindings"
            )
        source_result = self.inner.infer(element)
        source_chunk = np.asarray(
            source_result["actions"], dtype=np.float64
        )
        if (
            source_chunk.ndim != 2
            or source_chunk.shape[1] != 7
            or len(source_chunk) < self.replan_steps
            or not np.isfinite(source_chunk).all()
        ):
            raise RuntimeError(
                "source policy returned an invalid LIBERO ActionBlock"
            )
        nominal = source_chunk[: self.replan_steps]
        envelope = np.clip(nominal, -1.0, 1.0)
        shape = tuple(nominal.shape)
        checked, local = wrapper.checker.checked_candidate(
            candidate_index=0,
            semantic_subtask_digest=request.artifact.artifact_digest,
            semantic_subtask=request.artifact.selected_subtask,
            observation=request.local_observation,
            nominal_command=tuple(
                float(value) for value in nominal.reshape(-1)
            ),
            final_command=tuple(
                float(value) for value in envelope.reshape(-1)
            ),
            command_shape=shape,
            expected_state_epoch=request.context.state_epoch,
            release_destination=request.release_destination,
        )
        selection = select_checked_action_block(
            (checked,),
            expected_semantic_subtask_digest=(
                request.artifact.artifact_digest
            ),
            min_progress_margin=wrapper.min_progress_margin,
            max_projection_l2=wrapper.max_projection_l2,
        )
        eligible = selection.selected is not None
        predecessor = wrapper.checker.predecessor_assess(
            semantic_subtask=request.artifact.selected_subtask,
            observation=request.local_observation,
            command=tuple(
                float(value) for value in envelope.reshape(-1)
            ),
            command_shape=shape,
            expected_state_epoch=request.context.state_epoch,
            release_destination=request.release_destination,
        )
        physical = tuple(
            atom
            for atom in predecessor.violation_atoms
            if is_physical_risk_atom(atom)
        )
        advisory = tuple(
            atom
            for atom in predecessor.violation_atoms
            if atom not in physical
        )
        source_digest = v2._array_digest(source_chunk)
        self.audits.append(
            {
                "schema": RISK_SELECTIVE_AUDIT_SCHEMA,
                "candidate_count": 1,
                "replan_steps": self.replan_steps,
                "fixed_semantic_subtask": (
                    request.artifact.selected_subtask
                ),
                "selection_reason": (
                    "risk_selective_nominal_safe_unchanged"
                    if eligible
                    else "risk_selective_physical_gate_rejected"
                ),
                "eligible_selected_source_candidate_index": (
                    0 if eligible else None
                ),
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": not eligible,
                "returned_source_policy_chunk_sha256": source_digest,
                "returned_action_chunk_sha256": source_digest,
                "risk_selective": {
                    "nominal_command_changed": False,
                    "full_task_prompt_preserved": True,
                    "physical_risk_atoms": physical,
                    "advisory_semantic_atoms": advisory,
                    "soft_progress_gate_active": False,
                },
                "candidates": [
                    {
                        "source_candidate_index": 0,
                        "source_policy_chunk_sha256": source_digest,
                        "source_policy_chunk_shape": tuple(
                            source_chunk.shape
                        ),
                        "nominal_checked": v3._checked_payload(
                            checked,
                            local,
                            projection_l2=v3._l2(
                                nominal, envelope
                            ),
                            eligible=eligible,
                        ),
                        "progress_projection": {
                            "schema": RISK_SELECTIVE_AUDIT_SCHEMA,
                            "accepted": eligible,
                            "projected": False,
                            "reason": (
                                "nominal_safe_noninterference"
                                if eligible
                                else "physical_risk_gate"
                            ),
                            "semantic_subtask": (
                                request.artifact.selected_subtask
                            ),
                            "command_shape": shape,
                            "projection_l2": v3._l2(
                                nominal, envelope
                            ),
                        },
                        "checked": v3._checked_payload(
                            checked,
                            local,
                            projection_l2=v3._l2(
                                nominal, envelope
                            ),
                            eligible=eligible,
                        ),
                    }
                ],
            }
        )
        # The outer wrapper applies the same numeric clipping as the base VLA
        # runner.  Returning the exact source chunk preserves policy output.
        return {**source_result, "actions": source_chunk.copy()}


class _FixedSelector:
    def __init__(
        self, selection: DeterministicSemanticSelection
    ) -> None:
        self.selection = selection

    def select(self, _observation: Any) -> DeterministicSemanticSelection:
        return self.selection


class RiskSelectiveSemanticPolicyWrapper(
    TrustedSemanticPolicyWrapper
):
    """Monitor a trusted subtask without replacing the full-task prompt."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._last_known_subtask: str | None = None
        self._last_release_destination: str | None = None

    def _fallback_selection(
        self,
        predecessor: DeterministicSemanticSelection,
    ) -> DeterministicSemanticSelection:
        first = self.graph.goals[0]
        return DeterministicSemanticSelection(
            known=True,
            finished=False,
            selected_subtask=(
                self._last_known_subtask or first.subtasks[0]
            ),
            goal_index=(
                predecessor.goal_index
                if predecessor.goal_index is not None
                else 0
            ),
            release_destination=(
                self._last_release_destination or first.destination
            ),
            reason=(
                "risk_selective_fallback_from_"
                f"{predecessor.reason}"
            ),
        )

    def begin_policy_call(
        self,
        *,
        proposal_index: int,
        local_observation: Any,
        trusted_observation_digest: str,
        external_policy_prompt: str,
        generated_at_ns: int,
    ) -> SemanticPolicyPreparation:
        selected = self.selector.select(local_observation)
        if selected.known and not selected.finished:
            self._last_known_subtask = selected.selected_subtask
            self._last_release_destination = (
                selected.release_destination
            )
            preparation = super().begin_policy_call(
                proposal_index=proposal_index,
                local_observation=local_observation,
                trusted_observation_digest=(
                    trusted_observation_digest
                ),
                external_policy_prompt=external_policy_prompt,
                generated_at_ns=generated_at_ns,
            )
        else:
            fallback = self._fallback_selection(selected)
            original_selector = self.selector
            self.selector = _FixedSelector(fallback)
            try:
                preparation = super().begin_policy_call(
                    proposal_index=proposal_index,
                    local_observation=local_observation,
                    trusted_observation_digest=(
                        trusted_observation_digest
                    ),
                    external_policy_prompt=external_policy_prompt,
                    generated_at_ns=generated_at_ns,
                )
            finally:
                self.selector = original_selector
            self._last_known_subtask = fallback.selected_subtask
            self._last_release_destination = (
                fallback.release_destination
            )
        request = preparation.request
        if request is None:
            raise RuntimeError(
                "risk-selective wrapper failed to create a policy request"
            )
        nominal_request = replace(
            request,
            exact_policy_prompt=external_policy_prompt,
        )
        return replace(
            preparation,
            reason=(
                preparation.reason
                if selected.known and not selected.finished
                else self._fallback_selection(selected).reason
            ),
            request=nominal_request,
        )


def risk_selective_effect_evaluation(
    evaluation: ExecutionEvaluation,
) -> ExecutionEvaluation:
    """Demote only missing soft effects to an audited replan."""

    if (
        evaluation.verdict is TransactionVerdict.REJECT
        and evaluation.issues
        and all(
            issue.startswith("expected effects missing:")
            for issue in evaluation.issues
        )
    ):
        return ExecutionEvaluation(
            TransactionVerdict.ALLOW,
            tuple(
                f"advisory_replan:{issue}"
                for issue in evaluation.issues
            ),
        )
    return evaluation


class RiskSelectivePrefixDispatchBoundary(
    SingleUsePrefixDispatchBoundary
):
    """Preserve integrity and violations while replanning on effect miss."""

    def seal(
        self,
        session: Any,
        contract: Any,
        evidence: Any,
    ) -> ExecutionEvaluation:
        return risk_selective_effect_evaluation(
            super().seal(session, contract, evidence)
        )


@contextmanager
def patched_risk_selective_wrapper_bindings() -> Iterator[None]:
    """Temporarily inject the v6 checker into the frozen wrapper."""

    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = (
        RiskSelectiveSemanticExecutablePrefixChecker
    )
    wrapper.LOCAL_CHECKER_VERSION = RISK_SELECTIVE_CHECKER_VERSION
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


__all__ = [
    "PHYSICAL_RISK_ATOM_PREFIXES",
    "RISK_SELECTIVE_AUDIT_SCHEMA",
    "RISK_SELECTIVE_CHECKER_VERSION",
    "RISK_SELECTIVE_EFFECT_POLICY_VERSION",
    "RiskSelectiveCandidatePolicy",
    "RiskSelectiveLocalCheckerConfig",
    "RiskSelectivePrefixDispatchBoundary",
    "RiskSelectiveSemanticExecutablePrefixChecker",
    "RiskSelectiveSemanticPolicyWrapper",
    "is_physical_risk_atom",
    "patched_risk_selective_wrapper_bindings",
    "risk_selective_effect_evaluation",
]
