from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_adaptive_force_physics_development_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_latency_only_nonpass(summary: dict) -> None:
    assert summary["registered_development_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == [
        "all_condition_registered_gates"
    ]
    assert summary["nonpass_axes"] == {
        "v15_3_latency_max": ["arm_friction_0_7x"]
    }


def test_terminal_preserves_completed_safety_force_and_liveness(summary: dict) -> None:
    completed = summary["completed_axes"]
    assert completed[
        "all_condition_crossing_floor_deadlock_containment"
    ] is True
    assert completed["all_condition_availability_one"] is True
    assert completed["all_condition_registered_force_envelopes"] is True
    assert completed["all_condition_latency_p95"] is True
    assert completed["all_condition_100ms_miss_rate"] is True
    assert completed["all_condition_latency_max"] is False
    assert summary["cross_condition"]["total_residual_deadlock_lane_count"] == 0


def test_terminal_binds_incremental_search_latency_outlier(summary: dict) -> None:
    worst = summary["worst_latency_lane"]
    assert worst["latency_seconds"] == pytest.approx(0.2627424020320177)
    assert worst["condition_id"] == "arm_friction_0_7x"
    assert worst["runner_step_id"] == 1
    assert worst["extended_recovery_evaluated_count"] == 1
    assert worst["extended_recovery_selected_count"] == 1
    assert summary["cross_condition"]["worst_latency_p95_seconds"] < 0.1
    assert summary["cross_condition"]["worst_100ms_deadline_miss_rate"] < 0.025


def test_terminal_records_next_stage_and_nonclaims(summary: dict) -> None:
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["next_stage_decision"] == {
        "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
        "develop_incremental_extended_search_successor": True,
        "preserve_proactive_trigger_and_force_thresholds": True,
        "correct_extended_recovery_force_attribution": True,
        "fresh_requalification_authorized": False,
        "require_development_pass_before_requalification": True,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
