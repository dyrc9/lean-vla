from __future__ import annotations

from scripts import freeze_v14_multijoint_stress_design_pilot as freezer


def test_completed_stress_pilot_selects_three_dose_roles() -> None:
    if not freezer.pilot.DEFAULT_OUTPUT.is_file():
        return

    summary = freezer.build_summary()

    assert summary["pilot_complete"] is True
    assert summary["stress_gradient_observed"] is True
    assert [
        row["role"] for row in summary["selected_development_doses"]
    ] == [
        "negative_control",
        "moderate_activation",
        "high_activation",
    ]
    assert summary["by_dose"]["low"]["baselines"]["no_guard"][
        "crossing_count"
    ] == 0
    assert summary["by_dose"]["medium"]["baselines"]["no_guard"][
        "crossing_count"
    ] > 0
    assert summary["by_dose"]["high"]["baselines"]["no_guard"][
        "crossing_count"
    ] > summary["by_dose"]["medium"]["baselines"]["no_guard"][
        "crossing_count"
    ]
    assert summary["by_dose"]["medium"]["baselines"][
        "predictive_brake"
    ]["crossing_count"] == 0
    assert summary["by_dose"]["high"]["baselines"][
        "predictive_brake"
    ]["crossing_count"] == 0
    assert summary["development_matrix_contract"][
        "expected_baseline_lane_count"
    ] == 2016
