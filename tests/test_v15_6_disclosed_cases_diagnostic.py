from __future__ import annotations

from scripts import diagnose_v15_6_disclosed_cases as diagnostic


def test_summary_separates_recovery_and_fallback_metrics() -> None:
    result = {
        "executed_step_count": 2,
        "deadlock_count": 0,
        "crossing_count": 0,
        "below_floor_count": 0,
        "steps": [
            {
                "runner_step_id": 0,
                "deadlock": False,
                "recovery_selected": False,
                "selected_guard_margin_rad": 0.16,
                "selected_candidate_profile_id": "soft_primary",
                "actual_minimum_margin_rad": 0.158,
                "guard_scope_maximum_positive_joint_increment_over_pre_step": 900.0,
                "post_step_maximum_abs_risk_constraint_force": 1000.0,
                "post_step_maximum_positive_joint_increment_over_pre_step": 800.0,
            },
            {
                "runner_step_id": 1,
                "deadlock": False,
                "recovery_selected": True,
                "selected_guard_margin_rad": 0.155,
                "selected_candidate_profile_id": "stiff_recovery_fallback_0_004",
                "actual_minimum_margin_rad": 0.156,
                "guard_scope_maximum_positive_joint_increment_over_pre_step": 200.0,
                "post_step_maximum_abs_risk_constraint_force": 300.0,
                "post_step_maximum_positive_joint_increment_over_pre_step": 100.0,
            },
        ],
    }

    summary = diagnostic._summary(result)

    assert summary["minimum_margin_rad"] == 0.156
    assert summary["maximum_attributable_force"] == 900.0
    assert summary["maximum_recovery_attributable_force"] == 200.0
    assert summary["fallback_selected_step_count"] == 1
