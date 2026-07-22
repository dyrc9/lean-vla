from __future__ import annotations

import math

import pytest

from proofalign.benchmark.integrity_action_envelope import (
    ActionEnvelopeIntervention,
    command_l2,
    intervention_audit,
    project_command_l2,
)
from proofalign.integrity_models import ActionProposal, InterventionKind, StateSnapshot


def _proposal(command: tuple[float, ...]) -> ActionProposal:
    return ActionProposal(
        episode_nonce="envelope-test",
        proposal_index=0,
        proposed_at_ns=1,
        skill="vla_action_prefix",
        command=command,
    )


def _state() -> StateSnapshot:
    return StateSnapshot(
        episode_nonce="envelope-test",
        state_epoch=0,
        observed_at_ns=1,
        max_age_ns=10,
        state_digest="a" * 64,
        known=True,
    )


def test_envelope_preserves_commands_within_the_frozen_radius() -> None:
    policy = ActionEnvelopeIntervention(1.0)

    result = policy.apply(_proposal((0.6, 0.8)), _state())

    assert result.kind is InterventionKind.PASS
    assert result.final_command == (0.6, 0.8)
    assert result.witness_digest is None


def test_envelope_projects_outside_commands_with_a_bound_witness() -> None:
    policy = ActionEnvelopeIntervention(1.0)

    result = policy.apply(_proposal((3.0, 4.0)), _state())
    audit = intervention_audit(result, l2_limit=1.0)

    assert result.kind is InterventionKind.PROJECT_OR_BRAKE
    assert result.final_command == pytest.approx((0.6, 0.8))
    assert result.witness_digest is not None
    assert command_l2(result.final_command or ()) == pytest.approx(1.0)
    assert audit["nominal_action_l2"] == pytest.approx(5.0)
    assert audit["final_action_l2"] == pytest.approx(1.0)


def test_envelope_projection_is_idempotent_and_never_exceeds_its_limit() -> None:
    projected = project_command_l2((2.0, -3.0, 6.0), limit=1.0)

    assert command_l2(projected) <= 1.0 + 1e-12
    assert project_command_l2(projected, limit=1.0) == projected


@pytest.mark.parametrize("limit", (0, -1, math.inf, True))
def test_envelope_rejects_invalid_limits(limit: object) -> None:
    with pytest.raises(ValueError):
        ActionEnvelopeIntervention(limit)  # type: ignore[arg-type]
