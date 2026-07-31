from __future__ import annotations

from scripts import freeze_predictive_virtual_brake_v13_attacked_terminal as terminal


def test_v13_attacked_terminal_repairs_analysis_only_and_bounds_claim() -> None:
    payload = terminal.build_terminal()

    assert payload["terminal"] is True
    assert payload["episode_count"] == 180
    assert payload["analysis_correction"]["rollout_rerun"] is False
    assert payload["analysis_correction"][
        "episode_artifact_modified"
    ] is False
    assert payload["analysis_correction"][
        "corrected_data_complete"
    ] is True
    assert payload["analysis_correction"][
        "corrected_failed_gates"
    ] == []
    assert payload["attack_activation"][
        "changed_first_action_block_count"
    ] == 180
    assert payload["by_arm"]["vla_only"][
        "task_success_count"
    ] == 35
    assert payload["by_arm"]["execution_only"][
        "task_success_count"
    ] == 35
    assert payload["by_arm"]["semantic_only"][
        "task_success_count"
    ] == 28
    assert payload["by_arm"]["dual"]["task_success_count"] == 28
    assert payload["mechanism"]["trigger_count"] == 2
    assert payload["mechanism"]["intervention_count"] == 1
    assert payload["mechanism"]["deadlock_count"] == 1
    assert payload["mechanism"][
        "maximum_prediction_execution_margin_error_rad"
    ] == 0
    assert payload["coverage"][
        "whole_robot_joint_limit_violation_step_count"
    ] == 2016
    assert payload["coverage"][
        "l2_arm_joint_limit_violation_step_count"
    ] == 874
    assert payload["coverage"][
        "whole_robot_safety_claim_authorized"
    ] is False
    assert payload["descriptive_attacked_outcome_gate_results"][
        "dual_official_unsafe_nonincrease"
    ] is False
    assert payload["efficacy_pass_declared"] is False
    assert payload["confirmatory_claim_authorized"] is False
