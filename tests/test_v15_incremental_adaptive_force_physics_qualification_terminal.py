from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_physics_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_complete_registered_pass(summary: dict) -> None:
    assert summary["registered_qualification_pass"] is True
    assert summary["physics_domain_robustness_claim_authorized"] is True
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == []
    assert all(summary["registered_gate_results"].values())
    assert all(summary["completed_axes"].values())


def test_terminal_records_held_out_population(summary: dict) -> None:
    population = summary["population"]
    assert population["globally_held_out_exact_task_init_pair_count"] == 18
    assert population["prior_population_protocol_count"] == 41
    assert population["excluded_prior_exact_pair_count"] == 293
    assert population["all_prior_exact_pairs_excluded"] is True
    assert population["stress_lane_count"] == 5292
    assert population["baseline_lane_count"] == 21168
    assert population["dynamic_environment_count"] == 15


def test_terminal_records_cross_condition_worst_cases(summary: dict) -> None:
    cross = summary["cross_condition"]
    assert cross["total_v14_deadlock_lane_count"] == 2562
    assert cross["total_recovery_selected_count"] == 9347
    assert cross["total_recovery_prevented_deadlock_lane_count"] == 2562
    assert cross["total_residual_deadlock_lane_count"] == 0
    assert cross["maximum_attributable_joint_force_increment"] == pytest.approx(
        9903.253919286271
    )
    assert cross[
        "maximum_recovery_attributable_joint_force_increment"
    ] == pytest.approx(131.7250605739805)
    assert cross[
        "maximum_recovery_post_step_positive_joint_increment"
    ] == pytest.approx(1216.791415543652)
    assert cross["worst_latency_p95_seconds"] == pytest.approx(
        0.08344237990968395
    )
    assert cross["worst_latency_max_seconds"] == pytest.approx(
        0.15027742099482566
    )
    assert cross["worst_100ms_deadline_miss_rate"] == pytest.approx(
        0.005555555555555556
    )


def test_terminal_records_identity_and_bindings(summary: dict) -> None:
    metrics = summary["incremental_adaptive_force_metrics"]
    assert metrics["v15_7_incremental_adaptive_force_audit_count"] == 26460
    assert metrics[
        "v15_7_incremental_force_attribution_identity_failure_count"
    ] == 0
    assert metrics["v15_7_incremental_short_circuit_identity_failure_count"] == 0
    assert metrics[
        "v15_7_maximum_incremental_extended_candidate_evaluated_count"
    ] == 1
    assert summary["bindings"]["evidence"]["bytes"] == 188109739
    assert summary["bindings"]["evidence"]["sha256"] == (
        "2fddb688ce06065971e3ba4d3e931e9f246003eaacfc948d6294011bd66acdbc"
    )


def test_terminal_bounds_claim_and_authorizes_fresh_mismatch(summary: dict) -> None:
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["next_stage_decision"] == {
        "same_model_physics_domain_claim_authorized": True,
        "freeze_fresh_model_mismatch_protocol": True,
        "reuse_physics_qualification_population_for_model_mismatch": False,
        "model_mismatch_claim_authorized": False,
        "task_utility_claim_authorized": False,
        "preserve_v15_4_v15_5_v15_6_nonpass_without_reinterpretation": True,
        "relax_registered_thresholds": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
