from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_recovery_component_ablation_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_component_ablation_nonpass(summary: dict) -> None:
    assert summary["registered_qualification_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == [
        "no_guard_shadow_trace_identity",
        "v15_2_v15_3_margin_trace_identity",
        "v15_2_v15_3_scalar_identity",
        "v15_3_100ms_deadline_miss_rate",
    ]
    assert summary["completed_axes"] == {
        "all_recovery_variants_crossing_and_floor_containment": True,
        "floor_recovery_reduces_observed_deadlock_lanes": True,
        "current_edge_not_above_floor_deadlocks": True,
        "priority_zero_residual_deadlock": True,
        "force_envelopes": True,
        "strict_same_environment_trace_identity": False,
        "registered_latency_miss_rate": False,
        "all_registered_gates": False,
    }


def test_terminal_records_incremental_deadlock_trend(summary: dict) -> None:
    assert summary["deadlock_ablation_sequence"] == [
        {
            "baseline": "v14_predictive_brake",
            "deadlock_lane_count": 359,
            "executed_step_availability": 0.685978835978836,
        },
        {
            "baseline": "v15_floor_edge_recovery",
            "deadlock_lane_count": 342,
            "executed_step_availability": 0.6992063492063492,
        },
        {
            "baseline": "v15_1_current_edge_recovery",
            "deadlock_lane_count": 15,
            "executed_step_availability": 0.9920634920634921,
        },
        {
            "baseline": "v15_2_current_edge_priority_recovery",
            "deadlock_lane_count": 0,
            "executed_step_availability": 1.0,
        },
        {
            "baseline": "v15_3_force_attributed_recovery",
            "deadlock_lane_count": 0,
            "executed_step_availability": 1.0,
        },
    ]
    assert summary["descriptive_incremental_deadlock_changes"] == {
        "floor_minus_v14": -17,
        "current_minus_floor": -327,
        "priority_minus_current": -15,
        "v15_3_minus_priority": 0,
        "registered_as_strict_paired_component_claim": False,
    }


def test_terminal_keeps_identity_latency_and_force_boundaries(summary: dict) -> None:
    identity = summary["execution_identity"]
    assert identity["no_guard_shadow_nonzero_trace_lane_count"] == 48
    assert identity["no_guard_shadow_maximum_actual_margin_trace_error_rad"] == (
        0.21771378124250163
    )
    assert identity["v15_2_v15_3_nonzero_trace_lane_count"] == 30
    assert identity["v15_2_v15_3_scalar_mismatch_lane_count"] == 1
    assert identity["v15_2_v15_3"]["scalar_mismatch_count"] == 2
    assert (
        identity["v15_2_v15_3"]["maximum_actual_margin_trace_error_rad"]
        == 0.20665975962065275
    )
    assert (
        summary["force_comparison"][
            "v15_3_maximum_recovery_attributable_joint_force_increment"
        ]
        == 851.6028891217397
    )
    assert summary["latency"]["deadline_miss_count"] == 105
    assert summary["latency"]["deadline_sample_count"] == 3780
    assert summary["latency"]["deadline_miss_rate"] == 0.027777777777777776
    assert summary["latency"]["registered_miss_rate_max"] == 0.025


def test_terminal_binds_artifacts_and_explicit_nonclaims(summary: dict) -> None:
    assert summary["bindings"]["checksums"]["entry_count"] == 1
    assert summary["population"] == {
        "held_out_exact_task_init_pair_count": 18,
        "stress_lane_count": 756,
        "baseline_count": 8,
        "baseline_lane_count": 6048,
        "all_prior_exact_pairs_excluded": True,
        "paired_same_injected_state_design": True,
        "task_outcomes_read": False,
    }
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert (
        summary["next_stage_decision"][
            "preserve_nonpass_without_rerun_or_threshold_relaxation"
        ]
        is True
    )
    assert (
        summary["next_stage_decision"][
            "new_successor_must_use_new_held_out_requalification_population"
        ]
        is True
    )


def test_committed_component_terminal_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
