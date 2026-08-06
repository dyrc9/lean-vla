from __future__ import annotations

import pytest

from scripts import diagnose_v15_5_deadlock_nonpass as diagnostic


def test_deadlock_summary_requires_and_retains_one_deadlock() -> None:
    result = {
        "deadlock_count": 1,
        "steps": [
            {
                "runner_step_id": 2,
                "deadlock": True,
                "deadlock_reason": "no_force_feasible_multijoint_guard_candidate",
                "current_minimum_margin_rad": 0.155,
                "unguarded_predicted_minimum_margin_rad": 0.149,
                "base_safety_eligible_candidate_count": 2,
                "force_feasible_base_candidate_count": 0,
                "force_rejected_base_eligible_candidate_count": 2,
                "candidates": [{"guard_margin_rad": 0.16}],
            }
        ],
    }

    summary = diagnostic._deadlock_summary(result)

    assert summary["runner_step_id"] == 2
    assert summary["base_safety_eligible_candidate_count"] == 2
    assert summary["force_feasible_base_candidate_count"] == 0
    assert summary["candidate_count"] == 1


def test_deadlock_summary_fails_closed_without_exactly_one() -> None:
    with pytest.raises(diagnostic.V155DeadlockNonpassDiagnosticError):
        diagnostic._deadlock_summary({"deadlock_count": 0, "steps": []})


def test_expanded_candidate_ladder_stays_between_edge_and_floor() -> None:
    edge = 0.159
    with diagnostic._patched_expanded_candidates((0.004, 1.0)):
        config = diagnostic.recovery.ForceConstrainedRecoveryConfig(edge)
        margins = config.guard_margins_rad

    ladder = margins[len(diagnostic.recovery.BRAKE_MARGINS_RAD) + 1 : -1]
    assert config.guard_solref == (0.004, 1.0)
    assert margins[:4] == diagnostic.recovery.BRAKE_MARGINS_RAD
    assert margins[4] == edge
    assert margins[-1] == diagnostic.recovery.RECOVERY_GUARD_MARGIN_RAD
    assert len(ladder) == len(diagnostic.RECOVERY_LADDER_FRACTIONS)
    assert all(
        diagnostic.recovery.RECOVERY_GUARD_MARGIN_RAD < value < edge
        for value in ladder
    )
