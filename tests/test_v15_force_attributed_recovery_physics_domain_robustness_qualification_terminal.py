from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_force_attributed_recovery_physics_domain_robustness_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_summary_preserves_registered_physics_nonpass(
    summary: dict,
) -> None:
    assert summary["registered_qualification_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == ["all_condition_registered_gates"]
    assert summary["completed_axes"] == {
        "all_condition_v15_3_joint_limit_proxy_containment": True,
        "all_condition_v15_3_availability_one": True,
        "all_condition_comparative_gates": True,
        "all_condition_active_warning_and_saturation_zero": True,
        "all_condition_registered_gates": False,
    }


def test_terminal_summary_keeps_force_and_identity_failures_visible(
    summary: dict,
) -> None:
    assert summary["cross_condition"][
        "recovery_attributable_force_pass_conditions"
    ] == ["arm_mass_0_8x"]
    assert summary["cross_condition"][
        "recovery_attributable_force_nonpass_conditions"
    ] == [
        "arm_friction_0_7x",
        "arm_friction_1_3x",
        "arm_mass_1_2x",
        "joint_damping_0_7x",
        "joint_damping_1_3x",
        "nominal",
    ]
    assert (
        summary["cross_condition"]["maximum_recovery_attributable_force"]
        == 1777.871598806514
    )
    assert (
        summary["cross_condition"]["maximum_recovery_attributable_force_condition"]
        == "joint_damping_0_7x"
    )
    assert summary["nonpass_axes"]["recovery_prevention_identity"] == [
        "joint_damping_1_3x"
    ]
    identity = summary["conditions"]["joint_damping_1_3x"][
        "deadlock_prevention_identity"
    ]
    assert identity["paired_identity"] is False
    assert identity["v14_deadlock_lane_count"] == 360
    assert identity["v15_internal_would_deadlock_lane_count"] == 359
    assert identity["v14_only_lane_ids"] == [
        "v15_3_physics_robust_obstacle_avoidance_human_task6_init5:"
        "joint_damping_1_3x:joint6:upper:medium"
    ]


def test_terminal_summary_binds_immutable_artifacts_and_nonclaims(
    summary: dict,
) -> None:
    assert summary["bindings"]["checksums"]["entry_count"] == 1
    assert summary["population"] == {
        "held_out_exact_task_init_pair_count": 18,
        "condition_count": 7,
        "stress_lane_count_per_condition": 756,
        "total_stress_lane_count": 5292,
        "baseline_count": 4,
        "total_baseline_lane_count": 21168,
        "all_prior_exact_pairs_excluded": True,
        "task_outcomes_read": False,
    }
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["next_stage_decision"] == {
        "physics_domain_robustness_claim_authorized": False,
        "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
        "proceed_to_new_component_ablation_population": True,
        "develop_force_bounded_successor_before_physics_requalification": True,
        "diagnose_joint_damping_1_3x_identity_lane": True,
        "model_mismatch_qualification_authorized": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
