from __future__ import annotations

from scripts import (
    freeze_v15_current_edge_priority_recovery_stress_qualification_fresh2_terminal as terminal,
)


def test_terminal_preserves_nonpass_and_failure_diagnostics() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["failed_gates"] == [
        "threshold_classification_identity",
        "v15_2_absolute_force_envelope",
        "v15_2_relative_force_envelope",
    ]
    assert summary["population"] == {
        "environment_count": 18,
        "suite_count": 3,
        "stress_lane_count": 756,
        "baseline_lane_count": 3024,
        "held_out_exact_task_init_population": True,
        "task_outcomes_read": False,
    }
    signal = summary["descriptive_mechanism_signal"]
    assert signal["v14_deadlock_lane_count"] == 364
    assert signal["v15_2_residual_deadlock_lane_count"] == 0
    assert signal["recovery_prevented_deadlock_count"] == 1205
    assert signal["v15_2_crossing_count"] == 0
    assert signal["v15_2_below_floor_count"] == 0
    assert signal["registered_as_qualification_pass"] is False
    assert len(
        summary["threshold_identity"]["disagreements_at_0_22_rad"]
    ) == 2
    force = summary["force_diagnostic"]
    assert force["v15_2_force_over_10000_lane_count"] == 1
    assert force["top_v15_2_force_lanes"][0][
        "v15_2_maximum_abs_constraint_force"
    ] > 10000
    decision = summary["next_stage_decision"]
    assert decision[
        "held_out_mechanism_qualification_claim_authorized"
    ] is False
    assert decision["advance_directly_to_confirmatory_task_utility"] is False
    assert decision["develop_versioned_force_bounded_successor"] is True


def test_frozen_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
