from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_dynamic_state_physics_development_terminal as terminal


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_summary_preserves_registered_development_pass(
    summary: dict,
) -> None:
    assert summary["registered_development_pass"] is True
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == []
    assert all(summary["registered_gate_results"].values())
    assert all(summary["completed_axes"].values())


def test_terminal_summary_records_cross_condition_worst_cases(
    summary: dict,
) -> None:
    cross = summary["cross_condition"]
    assert cross["total_v14_deadlock_lane_count"] == 2527
    assert cross["total_v15_4_residual_deadlock_lane_count"] == 0
    assert cross["total_recovery_selected_count"] == 8287
    assert cross["maximum_recovery_attributable_force"] == pytest.approx(
        860.9151210124872
    )
    assert cross["maximum_recovery_attributable_force_condition"] == (
        "arm_mass_0_8x"
    )
    assert cross["worst_latency_seconds_p95"] < 0.1
    assert cross["worst_latency_seconds_max"] < 0.2
    assert cross["worst_100ms_deadline_miss_rate"] < 0.025


def test_terminal_summary_records_dynamic_state_identity_and_nonclaims(
    summary: dict,
) -> None:
    assert summary["dynamic_state_metrics"] == {
        "v15_4_dynamic_motion_generator_step_count": 22050,
        "v15_4_dynamic_state_audit_count": 26460,
        "v15_4_dynamic_state_restore_assessment_count": 49308,
        "v15_4_dynamic_state_restore_failure_count": 0,
    }
    assert summary["predecessor_v15_3_nonpass_reinterpreted"] is False
    assert all(
        value is False for value in summary["explicit_nonclaims"].values()
    )
    assert summary["next_stage_decision"] == {
        "select_v15_4_for_fresh_held_out_physics_qualification": True,
        "fresh_held_out_protocol_freeze_authorized": True,
        "model_mismatch_claim_authorized": False,
        "task_utility_claim_authorized": False,
        "preserve_v15_3_nonpass_without_reinterpretation": True,
        "reuse_development_population_for_qualification": False,
        "relax_registered_thresholds": False,
    }


def test_terminal_summary_binds_immutable_artifacts(summary: dict) -> None:
    assert summary["bindings"]["checksums"]["entry_count"] == 1
    assert summary["population"] == {
        "outcome_disclosed_exact_task_init_pair_count": 18,
        "condition_count": 7,
        "stress_lane_count_per_condition": 756,
        "total_stress_lane_count": 5292,
        "baseline_count": 4,
        "total_baseline_lane_count": 21168,
        "development_population_outcome_disclosed": True,
        "task_outcomes_read_during_execution": False,
    }
    assert all(
        not row["failed_registered_gates"]
        for row in summary["conditions"].values()
    )
    assert all(
        row["deadlock_prevention_identity"]["paired_identity"] is True
        for row in summary["conditions"].values()
    )


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
