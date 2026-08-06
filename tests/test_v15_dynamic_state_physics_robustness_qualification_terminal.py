from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_dynamic_state_physics_robustness_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_registered_nonpass_and_completed_axes(
    summary: dict,
) -> None:
    assert summary["registered_qualification_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == [
        "all_condition_registered_gates"
    ]
    assert summary["completed_axes"] == {
        "all_condition_v15_4_joint_limit_proxy_containment": True,
        "all_condition_v15_4_availability_one": True,
        "all_condition_recovery_attributable_force_envelope": True,
        "all_condition_latency_gates": True,
        "all_dynamic_state_restores_exact": True,
        "all_condition_comparative_gates": True,
        "all_condition_registered_gates": False,
    }


def test_terminal_localizes_registered_force_failures(summary: dict) -> None:
    assert summary["nonpass_axes"] == {
        "v15_4_attributable_force_envelope": [
            "arm_friction_0_7x",
            "arm_friction_1_3x",
        ],
        "v15_4_post_step_absolute_force_envelope": [
            "arm_friction_0_7x"
        ],
        "v15_4_post_step_increment_envelope": ["arm_friction_0_7x"],
        "v15_4_recovery_post_step_increment_envelope": [
            "arm_friction_1_3x"
        ],
    }
    cross = summary["cross_condition"]
    assert cross["maximum_all_attributable_force"] == pytest.approx(
        34906.32957305903
    )
    assert cross["maximum_post_step_absolute_force"] == pytest.approx(
        16614.24141554819
    )
    assert cross["maximum_post_step_increment"] == pytest.approx(
        14891.684855795487
    )
    assert cross["maximum_recovery_post_step_increment"] == pytest.approx(
        1357.4463456181547
    )


def test_terminal_binds_worst_disclosed_lane(summary: dict) -> None:
    low = summary["conditions"]["arm_friction_0_7x"]
    high = summary["conditions"]["arm_friction_1_3x"]
    assert low["worst_all_attributable_force"]["lane_id"] == (
        "v15_4_physics_qual_human_safety_task13_init10:"
        "arm_friction_0_7x:joint1:upper:low"
    )
    assert low["worst_all_attributable_force"]["recovery_selected"] is False
    assert high["worst_recovery_post_step_increment"]["lane_id"] == (
        "v15_4_physics_qual_human_safety_task13_init10:"
        "arm_friction_1_3x:joint1:upper:high"
    )
    assert high["worst_recovery_post_step_increment"][
        "recovery_selected"
    ] is True


def test_terminal_binds_population_nonclaims_and_next_stage(
    summary: dict,
) -> None:
    assert summary["population"] == {
        "globally_held_out_exact_task_init_pair_count": 18,
        "excluded_prior_exact_pair_count": 275,
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
        "develop_force_constrained_successor": True,
        "use_human_safety_task13_init10_as_disclosed_development_case": True,
        "require_new_population_for_requalification": True,
        "model_mismatch_qualification_authorized": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
