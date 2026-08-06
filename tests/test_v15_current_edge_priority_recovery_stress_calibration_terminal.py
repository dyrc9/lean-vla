from __future__ import annotations

from scripts import (
    freeze_v15_current_edge_priority_recovery_stress_calibration_terminal as terminal,
)


def test_terminal_preserves_nonpass_and_freezes_next_stage() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_development_data_complete"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["failed_gates"] == [
        "no_guard_shadow_trace_identity"
    ]
    assert summary["population"] == {
        "environment_count": 12,
        "suite_count": 3,
        "stress_lane_count": 504,
        "baseline_lane_count": 2016,
        "outcome_disclosed_population": True,
        "held_out_population": False,
    }
    assert summary["baselines"]["v14_predictive_brake"][
        "deadlock_lane_count"
    ] == 240
    assert summary["baselines"]["v15_2_recovery"][
        "deadlock_lane_count"
    ] == 0
    assert summary["recovery"]["recovery_prevented_deadlock_count"] == 792
    assert summary["recovery"]["selected_floor_violation_count"] == 0
    identity = summary["no_guard_shadow_identity_diagnostic"]
    assert identity["all_joint_side_error"]["maximum_rad"] > 0.001
    assert identity[
        "all_registered_threshold_classifications_identical"
    ] is True
    assert not any(
        identity["threshold_classification_disagreement_count"].values()
    )
    assert summary["latency_deadline_diagnostic"]["v15_2_recovery"][
        "0.05"
    ]["miss_rate"] > 0.20
    assert summary["latency_deadline_diagnostic"]["v15_2_recovery"][
        "0.1"
    ]["miss_rate"] < 0.01
    decision = summary["qualification_design_decision"]
    assert decision["candidate_parameters_remain_frozen"] is True
    assert decision["advance_to_new_population_qualification"] is True
    assert decision["calibration_nonpass_does_not_become_a_pass"] is True


def test_frozen_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
