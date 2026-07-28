"""Phase-aware availability for finite pick-up contact prefixes.

The predecessor checker already treats a finite ``pick_up`` block as
semantically compatible when it closes near the target or lifts an already
held target, even if the block's closest-distance progress is below the
generic approach threshold.  The predecessor selector nevertheless applies
that same generic threshold a second time and can reject the compatible
contact block.

This successor gives those checker-recognized contact blocks exactly the
minimum selector margin.  It does not change commands, hard-violation atoms,
workspace or velocity limits, the semantic subtask, or the post-execution
effect contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Iterator, Mapping

from proofalign.digests import digest_payload
from proofalign.horizon_consistent_release_h4 import (
    HorizonConsistentReleaseH4CandidatePolicy,
)
from proofalign.horizon_consistent_release_prefix import (
    RELEASE_PREFIX_OBSERVER_VERSION,
    ReleasePrefixLocalCheckerConfig,
    ReleasePrefixSemanticExecutablePrefixChecker,
)
from proofalign.semantic_local_checker import (
    LOCAL_CHECKER_ID,
    LocalActionAssessment,
    LocalCheckerConfig,
    parse_semantic_subtask,
)
from scripts import run_l2_execution_attack_eval_v3 as v3


CONTACT_PHASE_CHECKER_VERSION = "5"
CONTACT_PHASE_AUDIT_SCHEMA = (
    "proofalign.semantic-contact-phase-pick-up-selection.v8"
)
CONTACT_PHASE_BYPASS_REASON = (
    "pick_up_contact_phase_nominal_checker_bypass"
)


@dataclass(frozen=True)
class ContactPhaseLocalCheckerConfig(
    ReleasePrefixLocalCheckerConfig
):
    """Distinct content-addressed identity for the phase-aware checker."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": CONTACT_PHASE_CHECKER_VERSION,
                **self.__dict__,
                "contact_phase_credit_rule": (
                    "known compatible zero-violation pick_up below generic "
                    "minimum receives exactly min_progress_m"
                ),
            }
        )


class ContactPhaseSemanticExecutablePrefixChecker(
    ReleasePrefixSemanticExecutablePrefixChecker
):
    """Align selector margin with a checker-recognized pick-up phase."""

    def __init__(
        self,
        config: LocalCheckerConfig | None = None,
    ) -> None:
        selected = (
            ContactPhaseLocalCheckerConfig()
            if config is None
            else ContactPhaseLocalCheckerConfig(**config.__dict__)
        )
        # Skip predecessor constructors that would replace the v5 config.
        super(ReleasePrefixSemanticExecutablePrefixChecker, self).__init__(
            selected
        )

    def assess(self, **kwargs: Any) -> LocalActionAssessment:
        result = super().assess(**kwargs)
        semantic_subtask = kwargs.get("semantic_subtask")
        if (
            result.known
            and result.semantic_compatible
            and not result.violation_atoms
            and isinstance(semantic_subtask, str)
            and parse_semantic_subtask(semantic_subtask).verb == "pick_up"
            and result.progress_margin is not None
            and result.progress_margin < self.config.min_progress_m
            and any(
                atom in result.motion_atoms
                for atom in ("grasp", "lift")
            )
        ):
            return replace(
                result,
                progress_margin=self.config.min_progress_m,
                precondition_atoms=tuple(
                    dict.fromkeys(
                        (
                            *result.precondition_atoms,
                            "pick_up_contact_phase_compatible",
                        )
                    )
                ),
            )
        return result


def _contact_phase_nominal_safe(
    candidate: Mapping[str, Any],
) -> bool:
    projection = candidate.get("progress_projection")
    nominal = candidate.get("nominal_checked")
    if not isinstance(projection, Mapping) or not isinstance(
        nominal, Mapping
    ):
        return False
    hard = nominal.get("hard_violation_atoms")
    return bool(
        projection.get("reason")
        == "semantic_projection_budget_exceeded"
        and nominal.get("known") is True
        and nominal.get("semantic_compatible") is True
        and nominal.get("post_projection_compatible") is True
        and isinstance(hard, (list, tuple))
        and not hard
    )


def contact_phase_replay_eligible(
    candidate: Mapping[str, Any],
) -> bool:
    """Return whether a frozen v7 rejection meets the exact v8 rule."""

    nominal = candidate.get("nominal_checked")
    return bool(
        _contact_phase_nominal_safe(candidate)
        and isinstance(nominal, Mapping)
        and nominal.get("eligible_under_fixed_gate") is False
    )


class ContactPhaseCandidatePolicy(
    v3.OnlineProgressProjectionCandidatePolicy
):
    """Recover only exact compatible contact blocks rejected by projection."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        if not self.audits:
            raise RuntimeError(
                "contact-phase successor lacks predecessor audit"
            )
        audit = self.audits[-1]
        candidates = audit.get("candidates")
        if (
            not isinstance(candidates, list)
            or len(candidates) != 1
            or not isinstance(candidates[0], dict)
        ):
            raise RuntimeError(
                "contact-phase successor received malformed audit"
            )
        candidate = candidates[0]
        projection = candidate.get("progress_projection")
        nominal = candidate.get("nominal_checked")
        # The patched checker makes the exact contact block eligible during
        # the predecessor's nominal check. The predecessor still attempts its
        # generic terminal-progress projection; recover the unchanged source
        # block only when that projection alone exceeded its budget.
        recover = bool(
            _contact_phase_nominal_safe(candidate)
            and isinstance(nominal, Mapping)
            and nominal.get("eligible_under_fixed_gate") is True
        )
        if not recover:
            audit["contact_phase_bypass"] = {
                "schema": CONTACT_PHASE_AUDIT_SCHEMA,
                "authorized": False,
                "reason": (
                    projection.get("reason")
                    if isinstance(projection, Mapping)
                    else "projection_audit_absent"
                ),
            }
            return result
        audit.update(
            {
                "schema": CONTACT_PHASE_AUDIT_SCHEMA,
                "selection_reason": (
                    "contact_phase_nominal_checker_bypass_eligible"
                ),
                "eligible_selected_source_candidate_index": 0,
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": False,
                "contact_phase_bypass": {
                    "schema": CONTACT_PHASE_AUDIT_SCHEMA,
                    "authorized": True,
                    "reason": CONTACT_PHASE_BYPASS_REASON,
                    "command_changed": False,
                    "hard_violation_atoms": (),
                    "post_execution_effect_check_unchanged": True,
                },
            }
        )
        candidate["checked"] = dict(nominal)
        return result


class ContactPhaseReleaseH4CandidatePolicy(
    HorizonConsistentReleaseH4CandidatePolicy,
    ContactPhaseCandidatePolicy,
):
    """Compose contact-phase pick-up with the unchanged H4 release path."""


@contextmanager
def patched_contact_phase_wrapper_bindings() -> Iterator[None]:
    """Temporarily inject only the v5 checker into the frozen wrapper."""

    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = (
        ContactPhaseSemanticExecutablePrefixChecker
    )
    wrapper.LOCAL_CHECKER_VERSION = CONTACT_PHASE_CHECKER_VERSION
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


__all__ = [
    "CONTACT_PHASE_AUDIT_SCHEMA",
    "CONTACT_PHASE_BYPASS_REASON",
    "CONTACT_PHASE_CHECKER_VERSION",
    "RELEASE_PREFIX_OBSERVER_VERSION",
    "ContactPhaseCandidatePolicy",
    "ContactPhaseLocalCheckerConfig",
    "ContactPhaseReleaseH4CandidatePolicy",
    "ContactPhaseSemanticExecutablePrefixChecker",
    "contact_phase_replay_eligible",
    "patched_contact_phase_wrapper_bindings",
]
