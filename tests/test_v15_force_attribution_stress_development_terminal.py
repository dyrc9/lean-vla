from __future__ import annotations

from scripts import (
    freeze_v15_force_attribution_stress_development_terminal as terminal,
)


def test_terminal_freezes_attributable_force_and_future_gates() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["development_data_complete"] is True
    assert summary["registered_as_qualification_pass"] is False
    assert summary["population"]["stress_lane_count"] == 756
    assert summary["population"]["intervention_step_count"] == 1609
    assert summary["population"]["recovery_intervention_step_count"] == 1206
    assert summary["recovery"]["deadlock_count"] == 0
    assert summary["recovery"]["crossing_count"] == 0
    recovery = summary["force_groups"]["recovery_interventions"]
    assert recovery[
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] < 1000.0
    assert recovery[
        "post_step_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] < 1000.0
    legacy = summary["legacy_force_envelope_diagnostic"]
    assert legacy["old_gate_exceeded"] is True
    maximum = legacy["maximum_legacy_total_step"]
    assert maximum[
        "guard_scope_reported_maximum_abs_risk_constraint_force"
    ] > 10000.0
    assert maximum[
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ] == 0.0
    gates = summary["frozen_future_qualification_gates"]
    assert gates["maximum_attributable_joint_force_increment"] == 10000.0
    assert gates[
        "maximum_attributable_increment_to_v14_legacy_force_ratio"
    ] == 1.25
    assert gates[
        "maximum_recovery_attributable_joint_force_increment"
    ] == 1250.0
    decision = summary["next_stage_decision"]
    assert decision["freeze_new_held_out_qualification_protocol"] is True
    assert decision["qualification_claim_authorized_now"] is False


def test_frozen_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
