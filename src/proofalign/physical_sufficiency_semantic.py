"""Physical-sufficiency refinement for risk-selective semantic monitoring.

The v9 successor correctly stopped rewriting nominal policy blocks, but the
historical checker returned unknown for articulation subtasks before applying
its command-level velocity, workspace, and contact screens.  That made a
missing task-progress sensor act like a physical-risk finding.

This successor separates those facts.  For the frozen articulation-state
unknown, it still evaluates every physical screen that is available from the
trusted end-effector pose, entities, and exact ActionBlock.  The unavailable
task state is audited as advisory and the policy replans after the unchanged
block.  Physical findings remain hard.  Likewise, the observed
``target_not_held_after_move`` task predicate becomes an advisory replan;
cost, collision, dispatch integrity, and all unrecognized violations remain
fail closed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np

from proofalign.contact_phase_pick_up import (
    ContactPhaseSemanticExecutablePrefixChecker,
)
from proofalign.digests import digest_payload
from proofalign.integrity_v4_runtime import (
    ExecutionEvaluation,
    TransactionVerdict,
)
from proofalign.risk_selective_semantic import (
    PHYSICAL_RISK_ATOM_PREFIXES,
    RiskSelectiveCandidatePolicy,
    RiskSelectiveLocalCheckerConfig,
    RiskSelectivePrefixDispatchBoundary,
    RiskSelectiveSemanticExecutablePrefixChecker,
    risk_selective_effect_evaluation,
)
from proofalign.semantic_local_checker import (
    LOCAL_CHECKER_ID,
    LocalActionAssessment,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
    parse_semantic_subtask,
)


PHYSICAL_SUFFICIENCY_CHECKER_VERSION = "7"
PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA = (
    "proofalign.semantic-physical-sufficiency-selection.v10"
)
PHYSICAL_SUFFICIENCY_EFFECT_POLICY_VERSION = "2"
ADVISORY_SEMANTIC_UNKNOWN_REASONS = (
    "trusted_articulation_state_unavailable",
)
ADVISORY_OBSERVED_VIOLATION_ATOMS = (
    "target_not_held_after_move",
)
ADVISORY_UNKNOWN_PREFIX = "advisory_semantic_unknown:"


@dataclass(frozen=True)
class PhysicalSufficiencyLocalCheckerConfig(
    RiskSelectiveLocalCheckerConfig
):
    """Content-address the exact v10 hard/advisory partition."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": (
                    PHYSICAL_SUFFICIENCY_CHECKER_VERSION
                ),
                **self.__dict__,
                "physical_risk_atom_prefixes": (
                    PHYSICAL_RISK_ATOM_PREFIXES
                ),
                "advisory_semantic_unknown_reasons": (
                    ADVISORY_SEMANTIC_UNKNOWN_REASONS
                ),
                "advisory_observed_violation_atoms": (
                    ADVISORY_OBSERVED_VIOLATION_ATOMS
                ),
                "nominal_policy_prompt": "trusted_full_task",
                "nominal_action_policy": "exact_source_block",
            }
        )


class PhysicalSufficiencySemanticExecutablePrefixChecker(
    RiskSelectiveSemanticExecutablePrefixChecker
):
    """Run available physical screens despite a soft task-state unknown."""

    def __init__(
        self,
        config: LocalCheckerConfig | None = None,
    ) -> None:
        selected = (
            PhysicalSufficiencyLocalCheckerConfig()
            if config is None
            else PhysicalSufficiencyLocalCheckerConfig(
                **config.__dict__
            )
        )
        SemanticExecutablePrefixChecker.__init__(self, selected)

    def predecessor_assess(self, **kwargs: Any) -> LocalActionAssessment:
        raw = ContactPhaseSemanticExecutablePrefixChecker.assess(
            self, **kwargs
        )
        if (
            raw.known
            or raw.unknown_reason
            not in ADVISORY_SEMANTIC_UNKNOWN_REASONS
        ):
            return raw
        try:
            subtask = parse_semantic_subtask(
                str(kwargs["semantic_subtask"])
            )
            steps = self._steps(
                kwargs["command"], kwargs["command_shape"]
            )
        except (KeyError, TypeError, ValueError):
            return raw
        release_destination = kwargs.get("release_destination")
        allowed_contact_entities = {
            value
            for value in (
                subtask.target,
                subtask.destination,
                release_destination,
            )
            if value is not None
        }
        physical = self._hard_violations(
            kwargs["observation"],
            steps,
            allowed_contact_entities=allowed_contact_entities,
        )
        return LocalActionAssessment(
            known=True,
            semantic_compatible=not physical,
            motion_atoms=("physical_risk_screen",),
            precondition_atoms=(
                "risk_selective_nominal_monitor",
                f"{ADVISORY_UNKNOWN_PREFIX}{raw.unknown_reason}",
            ),
            # No unobservable task-progress effect is promised.
            predicted_effect_atoms=(),
            violation_atoms=physical,
            progress_margin=self.config.min_progress_m,
            target=subtask.target,
            part=subtask.part,
            region=subtask.destination or release_destination,
        )


class PhysicalSufficiencyCandidatePolicy(RiskSelectiveCandidatePolicy):
    """Add the physical-sufficiency decision to the exact-block audit."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        if not self.audits or self.wrapper is None or self.request is None:
            raise RuntimeError(
                "physical-sufficiency candidate audit is absent"
            )
        source = np.asarray(result["actions"], dtype=np.float64)
        nominal = source[: self.replan_steps]
        predecessor = self.wrapper.checker.predecessor_assess(
            semantic_subtask=(
                self.request.artifact.selected_subtask
            ),
            observation=self.request.local_observation,
            command=tuple(
                float(value)
                for value in np.clip(
                    nominal, -1.0, 1.0
                ).reshape(-1)
            ),
            command_shape=tuple(nominal.shape),
            expected_state_epoch=self.request.context.state_epoch,
            release_destination=self.request.release_destination,
        )
        advisory_unknowns = tuple(
            atom.removeprefix(ADVISORY_UNKNOWN_PREFIX)
            for atom in predecessor.precondition_atoms
            if atom.startswith(ADVISORY_UNKNOWN_PREFIX)
        )
        audit = self.audits[-1]
        audit["schema"] = PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA
        audit["risk_selective"][
            "advisory_semantic_unknown_reasons"
        ] = advisory_unknowns
        audit["risk_selective"][
            "physical_sufficiency_screen_active"
        ] = bool(advisory_unknowns)
        if (
            advisory_unknowns
            and audit.get(
                "eligible_selected_source_candidate_index"
            )
            == 0
        ):
            audit["selection_reason"] = (
                "physical_screened_semantic_unknown_unchanged"
            )
            projection = audit["candidates"][0][
                "progress_projection"
            ]
            projection["schema"] = (
                PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA
            )
            projection["reason"] = (
                "physical_screened_semantic_unknown"
            )
        return result


def physical_sufficiency_effect_evaluation(
    evaluation: ExecutionEvaluation,
) -> ExecutionEvaluation:
    """Demote only the named soft observed predicate to replanning."""

    predecessor = risk_selective_effect_evaluation(evaluation)
    if predecessor is not evaluation:
        return predecessor
    if (
        evaluation.verdict is not TransactionVerdict.REJECT
        or not evaluation.issues
    ):
        return evaluation
    observed_atoms = []
    for issue in evaluation.issues:
        prefix = "observer violations: "
        if not issue.startswith(prefix):
            return evaluation
        observed_atoms.extend(
            atom for atom in issue.removeprefix(prefix).split(",") if atom
        )
    if observed_atoms and all(
        atom in ADVISORY_OBSERVED_VIOLATION_ATOMS
        for atom in observed_atoms
    ):
        return ExecutionEvaluation(
            TransactionVerdict.ALLOW,
            tuple(
                f"advisory_replan:{issue}"
                for issue in evaluation.issues
            ),
        )
    return evaluation


class PhysicalSufficiencyPrefixDispatchBoundary(
    RiskSelectivePrefixDispatchBoundary
):
    """Keep integrity/physical findings hard and soft task effects advisory."""

    def seal(
        self,
        session: Any,
        contract: Any,
        evidence: Any,
    ) -> ExecutionEvaluation:
        # Bypass the v9 override so each policy is applied exactly once.
        predecessor = super(
            RiskSelectivePrefixDispatchBoundary, self
        ).seal(session, contract, evidence)
        return physical_sufficiency_effect_evaluation(predecessor)


@contextmanager
def patched_physical_sufficiency_wrapper_bindings() -> Iterator[None]:
    """Temporarily inject the v10 checker into the frozen wrapper."""

    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = (
        PhysicalSufficiencySemanticExecutablePrefixChecker
    )
    wrapper.LOCAL_CHECKER_VERSION = (
        PHYSICAL_SUFFICIENCY_CHECKER_VERSION
    )
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


__all__ = [
    "ADVISORY_OBSERVED_VIOLATION_ATOMS",
    "ADVISORY_SEMANTIC_UNKNOWN_REASONS",
    "PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA",
    "PHYSICAL_SUFFICIENCY_CHECKER_VERSION",
    "PHYSICAL_SUFFICIENCY_EFFECT_POLICY_VERSION",
    "PhysicalSufficiencyCandidatePolicy",
    "PhysicalSufficiencyLocalCheckerConfig",
    "PhysicalSufficiencyPrefixDispatchBoundary",
    "PhysicalSufficiencySemanticExecutablePrefixChecker",
    "patched_physical_sufficiency_wrapper_bindings",
    "physical_sufficiency_effect_evaluation",
]
