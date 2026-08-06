from __future__ import annotations

from scripts import (
    freeze_v15_force_attributed_recovery_stress_qualification_terminal as terminal,
)


def test_terminal_preserves_registered_pass_and_claim_boundaries() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is True
    assert summary["registered_result_unchanged"] is True
    assert summary["failed_gates"] == []
    assert all(summary["registered_gate_results"].values())
    assert summary["population"] == {
        "environment_count": 18,
        "suite_count": 3,
        "stress_lane_count": 756,
        "baseline_lane_count": 2268,
        "prior_exact_pair_count_excluded": 81,
        "environment_seed": 4509,
        "held_out_exact_task_init_population": True,
        "task_outcomes_read": False,
    }
    assert summary["recovery"]["v14_predictive_deadlock_lane_count"] == 364
    assert summary["recovery"]["v15_3_residual_deadlock_lane_count"] == 0
    assert summary["recovery"]["recovery_prevented_deadlock_count"] == 1202
    force = summary["force_comparison"]
    assert force["v15_3_maximum_attributable_joint_force_increment"] < 10000
    assert force[
        "attributable_increment_to_v14_legacy_force_ratio"
    ] < 1.25
    assert force[
        "v15_3_maximum_recovery_attributable_joint_force_increment"
    ] < 1250
    worst = summary["force_worst_cases"]["legacy_total_maximum"]
    assert worst[
        "guard_scope_reported_maximum_abs_risk_constraint_force"
    ] > 10000
    assert worst[
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ] == 0
    assert summary["explicit_nonclaims"][
        "fresh2_nonpass_superseded"
    ] is False
    assert summary["explicit_nonclaims"][
        "exact_same_environment_shadow_trace_identity"
    ] is False
    assert summary["next_stage_decision"][
        "freeze_new_held_out_task_utility_protocol"
    ] is True
    assert summary["next_stage_decision"][
        "task_utility_claim_authorized_now"
    ] is False


def test_frozen_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
