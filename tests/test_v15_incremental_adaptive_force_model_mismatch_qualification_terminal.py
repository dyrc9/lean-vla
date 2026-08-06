from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_model_mismatch_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_registered_nonpass(summary: dict) -> None:
    assert summary["registered_qualification_pass"] is False
    assert summary["model_mismatch_claim_authorized"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["condition_pass_count"] == 5
    assert summary["condition_nonpass_count"] == 2


def test_terminal_records_real_nonpass_axes(summary: dict) -> None:
    assert summary["nonpass_axes"] == {
        "actual_friction_0_7x_shadow_nominal": [
            "v15_3_attributable_force_envelope"
        ],
        "actual_friction_1_3x_shadow_nominal": [
            "v15_3_latency_max",
            "v15_3_prediction_execution_error",
            "v15_3_recovery_prevention_identity",
            "v15_3_zero_residual_deadlock",
        ],
    }
    cross = summary["cross_condition"]
    assert cross["total_residual_deadlock_lane_count"] == 2
    assert cross["maximum_attributable_joint_force_increment"] == pytest.approx(
        19597.7038897504
    )
    assert cross["worst_prediction_execution_error_rad"] == pytest.approx(
        0.02856686475227832
    )
    assert cross["worst_latency_max_seconds"] == pytest.approx(
        0.4786518389591947
    )


def test_terminal_records_exact_failure_lanes(summary: dict) -> None:
    lanes = summary["failure_lanes"]
    assert len(lanes) == 3
    assert all(row["suite"] == "human_safety" for row in lanes)
    assert all(row["task_id"] == 4 for row in lanes)
    assert all(row["init_state_id"] == 34 for row in lanes)
    assert all(row["joint_index"] == 1 for row in lanes)
    assert all(row["side"] == "upper" for row in lanes)
    assert {row["dose"] for row in lanes} == {"medium", "high"}


def test_terminal_records_complete_model_role_audit(summary: dict) -> None:
    metrics = summary["model_mismatch_metrics"]
    assert metrics["physics_audit_count"] == 126
    assert metrics["physics_audit_failure_count"] == 0
    assert metrics["predictive_run_count"] == 10584
    assert metrics["mismatch_predictive_run_count"] == 9072
    assert metrics["step_model_or_role_identity_failure_count"] == 0
    assert metrics["post_force_prediction_comparison_count"] == 25102
    assert metrics["post_force_prediction_identity_failure_count"] == 107
    assert all(summary["completed_axes"].values())


def test_terminal_binds_evidence_and_next_stage(summary: dict) -> None:
    assert summary["bindings"]["evidence"]["bytes"] == 189858073
    assert summary["bindings"]["evidence"]["sha256"] == (
        "623924217ceb1d37186a6e8b2e4ff5d7cbb03f7b8821a228d51da872b20f3e6c"
    )
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["next_stage_decision"] == {
        "preserve_model_mismatch_nonpass_without_reinterpretation": True,
        "develop_mismatch_aware_force_and_liveness_successor": True,
        "reuse_qualification_population_for_requalification": False,
        "fresh_requalification_required_after_development_pass": True,
        "model_mismatch_claim_authorized": False,
        "same_model_physics_domain_claim_remains_authorized": True,
        "relax_actual_safety_or_force_thresholds": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
