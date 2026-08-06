from __future__ import annotations

from scripts import diagnose_v15_force_recovery_ordering as diagnostic


def _candidate(margin: float, force: float, *, eligible: bool) -> dict:
    return {
        "guard_margin_rad": margin,
        "configuration_inside_guard_ranges": True,
        "predicted_minimum_margin_rad": 0.151,
        "maximum_abs_constraint_force": force,
        "eligible": eligible,
    }


def _observation(
    *,
    step: int,
    force: float,
    deadlock: bool = False,
) -> dict:
    return {
        "runner_step_id": step,
        "triggered": True,
        "intervened": not deadlock,
        "deadlock": deadlock,
        "v14_baseline_would_deadlock": True,
        "floor_or_current_edge_recovery_selected": not deadlock,
        "floor_guard_recovery_selected": False,
        "current_edge_recovery_selected": not deadlock,
        "selected_guard_margin_rad": None if deadlock else 0.155,
        "current_target_margin_rad": 0.155001,
        "unguarded_predicted_minimum_margin_rad": 0.14,
        "selected_predicted_minimum_margin_rad": None if deadlock else 0.151,
        "actual_minimum_margin_rad": 0.155001 if deadlock else 0.151,
        "maximum_abs_guarded_constraint_force": force,
        "guard_scope_maximum_positive_joint_increment_over_pre_step": (
            force - 0.1
        ),
        "eligible_candidate_count": 2,
        "screen_latency_seconds": 0.02,
        "candidates": [
            _candidate(0.155, force, eligible=not deadlock),
            _candidate(0.150001, 900.0, eligible=not deadlock),
        ],
    }


def test_step_summary_exposes_force_feasible_alternative() -> None:
    row = diagnostic._step_summary(_observation(step=1, force=1800.0))

    assert row["recovery_selected"] is True
    assert row["selected_guard_scope_absolute_force"] == 1800.0
    assert row["force_feasible_candidate_count"] == 1
    assert row["minimum_eligible_candidate_force"] == 900.0
    assert row["minimum_force_feasible_guard_margin_rad"] == 0.150001
    assert row["candidates"][0]["selected"] is True
    assert row["candidates"][1]["force_feasible"] is True


def test_variant_summary_keeps_deadlock_out_of_executed_exposure() -> None:
    summary = diagnostic._variant_summary(
        [
            _observation(step=0, force=1800.0),
            _observation(step=1, force=0.0, deadlock=True),
        ]
    )

    assert summary["step_count"] == 2
    assert summary["executed_step_count"] == 1
    assert summary["deadlock_count"] == 1
    assert summary["below_floor_count"] == 0
    assert summary["maximum_selected_recovery_absolute_force"] == 1800.0
    assert summary["recovery_step_with_force_feasible_alternative_count"] == 1


def test_exactly_one_fails_closed() -> None:
    try:
        diagnostic._exactly_one(
            [{"id": 1}, {"id": 1}], field="id", value=1
        )
    except diagnostic.V15ForceRecoveryOrderingDiagnosticError:
        pass
    else:
        raise AssertionError("duplicate disclosed rows must fail closed")
