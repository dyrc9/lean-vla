from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_physics_development_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_complete_registered_pass(summary: dict) -> None:
    assert summary["registered_development_pass"] is True
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == []
    assert all(summary["registered_gate_results"].values())
    assert all(summary["completed_axes"].values())


def test_terminal_records_cross_condition_worst_cases(summary: dict) -> None:
    cross = summary["cross_condition"]
    assert cross["total_v14_deadlock_lane_count"] == 2541
    assert cross["total_recovery_selected_count"] == 9266
    assert cross["total_recovery_prevented_deadlock_lane_count"] == 2541
    assert cross["total_residual_deadlock_lane_count"] == 0
    assert cross["maximum_recovery_attributable_joint_force_increment"] == pytest.approx(
        105.95974002950243
    )
    assert cross[
        "maximum_recovery_post_step_positive_joint_increment"
    ] == pytest.approx(1199.808255051743)
    assert cross["worst_latency_p95_seconds"] < 0.1
    assert cross["worst_latency_max_seconds"] < 0.2
    assert cross["worst_100ms_deadline_miss_rate"] < 0.025


def test_terminal_records_incremental_identity_and_activation(summary: dict) -> None:
    metrics = summary["incremental_adaptive_force_metrics"]
    assert metrics["v15_7_incremental_adaptive_force_audit_count"] == 26460
    assert metrics[
        "v15_7_incremental_force_attribution_identity_failure_count"
    ] == 0
    assert metrics["v15_7_incremental_short_circuit_identity_failure_count"] == 0
    assert metrics[
        "v15_7_maximum_incremental_extended_candidate_evaluated_count"
    ] == 1
    assert summary["adaptive_force_metrics"][
        "v15_7_extended_recovery_selected_count"
    ] == 1


def test_terminal_binds_population_nonclaims_and_next_stage(summary: dict) -> None:
    assert summary["bindings"]["evidence"]["bytes"] == 188284451
    assert summary["population"]["total_stress_lane_count"] == 5292
    assert summary["population"]["total_baseline_lane_count"] == 21168
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["next_stage_decision"] == {
        "select_v15_7_for_fresh_held_out_physics_qualification": True,
        "fresh_held_out_protocol_freeze_authorized": True,
        "reuse_development_population_for_qualification": False,
        "preserve_v15_4_v15_5_v15_6_nonpass_without_reinterpretation": True,
        "model_mismatch_claim_authorized": False,
        "task_utility_claim_authorized": False,
        "relax_registered_thresholds": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
