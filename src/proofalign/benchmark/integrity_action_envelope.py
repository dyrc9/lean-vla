"""Deterministic action-envelope intervention for Integrity v1 experiments.

This module deliberately implements only a low-level execution intervention.
It is not a semantic/intent defense and must not be presented as a Full CTDA
implementation.  The envelope is supplied by a frozen experiment protocol;
the code never infers or tunes it from episode outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Iterable

from proofalign.ctda import digest_payload
from proofalign.integrity_models import (
    ActionProposal,
    InterventionKind,
    InterventionResult,
    StateSnapshot,
    freeze_command,
)


def command_l2(command: Iterable[float]) -> float:
    """Return the Euclidean norm of a finite command."""

    frozen = freeze_command(command)
    return sqrt(sum(component * component for component in frozen))


def project_command_l2(command: Iterable[float], *, limit: float) -> tuple[float, ...]:
    """Project a command onto the closed L2 ball with ``limit`` radius."""

    if (
        not isinstance(limit, (int, float))
        or isinstance(limit, bool)
        or not isfinite(limit)
        or limit <= 0
    ):
        raise ValueError("action envelope limit must be a positive number")
    frozen = freeze_command(command)
    norm = command_l2(frozen)
    if norm <= float(limit):
        return frozen
    scale = float(limit) / norm
    return tuple(component * scale for component in frozen)


@dataclass(frozen=True)
class ActionEnvelopeIntervention:
    """Project only commands outside a protocol-frozen L2 envelope.

    Every projection carries a deterministic witness that binds the nominal
    command, exact projected command, and the frozen radius.  The generic
    Integrity authorizer re-authorizes that projected command before dispatch.
    """

    l2_limit: float
    reason: str = "protocol_frozen_raw_action_l2_envelope"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.l2_limit, (int, float))
            or isinstance(self.l2_limit, bool)
            or not isfinite(self.l2_limit)
            or self.l2_limit <= 0
        ):
            raise ValueError("l2_limit must be a positive number")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")

    def apply(
        self,
        proposal: ActionProposal,
        state: StateSnapshot,
    ) -> InterventionResult:
        del state
        nominal = proposal.command
        projected = project_command_l2(nominal, limit=float(self.l2_limit))
        if projected == nominal:
            return InterventionResult(
                kind=InterventionKind.PASS,
                nominal_command=nominal,
                final_command=nominal,
                reason="nominal_command_within_protocol_frozen_envelope",
            )
        witness_digest = digest_payload(
            {
                "schema": "proofalign.integrity-action-envelope-witness.v1",
                "l2_limit": float(self.l2_limit),
                "nominal_command": nominal,
                "nominal_l2": command_l2(nominal),
                "projected_command": projected,
                "projected_l2": command_l2(projected),
            }
        )
        return InterventionResult(
            kind=InterventionKind.PROJECT_OR_BRAKE,
            nominal_command=nominal,
            final_command=projected,
            reason=self.reason,
            witness_digest=witness_digest,
        )


def intervention_audit(result: InterventionResult, *, l2_limit: float) -> dict[str, object]:
    """Return the stable per-action evidence recorded by the simulator adapter."""

    return {
        "schema": "proofalign.integrity-action-envelope-audit.v1",
        "l2_limit": float(l2_limit),
        "intervention_kind": result.kind.value,
        "reason": result.reason,
        "nominal_action_l2": command_l2(result.nominal_command),
        "final_action_l2": (
            None if result.final_command is None else command_l2(result.final_command)
        ),
        "nominal_command": list(result.nominal_command),
        "final_command": (
            None if result.final_command is None else list(result.final_command)
        ),
        "witness_digest": result.witness_digest,
        "intervention_digest": result.result_digest,
    }


__all__ = [
    "ActionEnvelopeIntervention",
    "command_l2",
    "intervention_audit",
    "project_command_l2",
]
