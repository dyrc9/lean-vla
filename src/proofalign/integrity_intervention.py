"""Optional intervention policies for the minimal integrity prototype.

Intervention is intentionally outside the two integrity relations.  The exact
prefix authorizer always checks the final command returned by a policy, so a
filter cannot inherit authorization issued for the nominal command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from proofalign.integrity_models import (
    ActionProposal,
    InterventionKind,
    InterventionResult,
    StateSnapshot,
    freeze_command,
)


class InterventionPolicy(Protocol):
    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        ...


@dataclass(frozen=True)
class PassThroughIntervention:
    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        del state
        return InterventionResult(
            kind=InterventionKind.PASS,
            nominal_command=proposal.command,
            final_command=proposal.command,
            reason="nominal_command_preserved",
        )


@dataclass(frozen=True)
class ProjectCommandIntervention:
    adjusted_command: tuple[float, ...]
    witness_digest: str
    reason: str = "consumer_checked_projection"

    def __post_init__(self) -> None:
        object.__setattr__(self, "adjusted_command", freeze_command(self.adjusted_command))

    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        del state
        return InterventionResult(
            kind=InterventionKind.PROJECT_OR_BRAKE,
            nominal_command=proposal.command,
            final_command=self.adjusted_command,
            reason=self.reason,
            witness_digest=self.witness_digest,
        )


@dataclass(frozen=True)
class ReplanIntervention:
    reason: str = "fresh_proposal_required"

    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        del state
        return InterventionResult(
            kind=InterventionKind.REPLAN,
            nominal_command=proposal.command,
            final_command=None,
            reason=self.reason,
        )


@dataclass(frozen=True)
class HardBlockIntervention:
    reason: str = "hard_invariant_or_tcb_failure"

    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        del state
        return InterventionResult(
            kind=InterventionKind.HARD_BLOCK,
            nominal_command=proposal.command,
            final_command=None,
            reason=self.reason,
        )


__all__ = [
    "HardBlockIntervention",
    "InterventionPolicy",
    "PassThroughIntervention",
    "ProjectCommandIntervention",
    "ReplanIntervention",
]
