from __future__ import annotations

from scripts import freeze_predictive_virtual_brake_v13_attacked_shadow_terminal as terminal


def test_attacked_shadow_terminal_identifies_one_bounded_tradeoff() -> None:
    payload = terminal.build_terminal()

    assert payload["terminal"] is True
    assert payload["episode_count"] == 180
    assert payload["failed_gates"] == []
    assert payload["episode_level_difference_count"] == 1
    assert payload["episode_level_difference_keys"] == [
        {
            "base_pair_id": "human_safety_task4_init32",
            "arm": "dual",
        }
    ]
    assert payload["full_by_arm"]["dual"][
        "task_success_count"
    ] == 28
    assert payload["shadow_by_arm"]["dual"][
        "task_success_count"
    ] == 29
    assert payload["full_minus_shadow_by_arm"]["dual"][
        "joint_limit_violation_step_count"
    ] == -7
    assert payload["full_minus_shadow_by_arm"]["dual"][
        "target_margin_below_floor_step_count"
    ] == -23
    causal = payload["causal_case"]
    assert causal["pre_intervention_policy_step_identity_count"] == 236
    assert causal["first_risk_runner_step_id"] == 246
    assert causal["first_risk_source_action_identity"] is True
    assert causal["full_task_success"] is False
    assert causal["shadow_task_success"] is True
    assert causal["full_joint_limit_violation_step_count"] == 0
    assert causal["shadow_joint_limit_violation_step_count"] == 7
    assert causal["shadow_counterfactual_trigger_count"] == 25
    assert payload["efficacy_pass_declared"] is False
    assert payload["confirmatory_claim_authorized"] is False
