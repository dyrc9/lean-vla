from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_force_constrained_physics_development_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_registered_nonpass(summary: dict) -> None:
    assert summary["registered_development_pass"] is False
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == [
        "all_condition_registered_gates",
        "v15_5_dynamic_motion_generator_activated",
        "v15_5_dynamic_state_audit_coverage",
        "v15_5_force_constrained_audit_coverage",
    ]


def test_terminal_localizes_two_residual_deadlocks(summary: dict) -> None:
    assert summary["nonpass_axes"] == {
        "v15_3_recovery_prevention_identity": [
            "arm_friction_0_7x",
            "arm_mass_0_8x",
        ],
        "v15_3_zero_residual_deadlock": [
            "arm_friction_0_7x",
            "arm_mass_0_8x",
        ],
    }
    rows = summary["residual_deadlock_lanes"]
    assert len(rows) == 2
    assert {row["condition_id"] for row in rows} == {
        "arm_friction_0_7x",
        "arm_mass_0_8x",
    }
    assert all(
        row["stop_reason"]
        == "no_force_feasible_multijoint_guard_candidate"
        for row in rows
    )


def test_terminal_records_force_fix_and_mechanism_activation(summary: dict) -> None:
    assert summary["cross_condition"][
        "all_registered_force_envelopes_pass"
    ] is True
    assert summary["force_constrained_metrics"][
        "v15_5_force_rejected_base_eligible_candidate_count"
    ] == 255
    assert summary["force_constrained_metrics"][
        "v15_5_selected_force_infeasible_count"
    ] == 0
    assert summary["cross_condition"][
        "maximum_attributable_joint_force_increment"
    ] == pytest.approx(9873.452498347138)
    assert summary["cross_condition"][
        "maximum_recovery_post_step_positive_joint_increment"
    ] == pytest.approx(1199.808255051743)


def test_terminal_binds_nonclaims_and_next_stage(summary: dict) -> None:
    assert all(value is False for value in summary["explicit_nonclaims"].values())
    assert summary["predecessor_v15_4_nonpass_reinterpreted"] is False
    assert summary["next_stage_decision"] == {
        "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
        "develop_fail_safe_force_constrained_successor": True,
        "use_two_residual_deadlock_lanes_as_disclosed_development_cases": True,
        "fresh_requalification_authorized": False,
        "require_development_pass_before_requalification": True,
        "relax_registered_force_thresholds": False,
    }


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
