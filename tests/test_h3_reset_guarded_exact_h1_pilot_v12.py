from __future__ import annotations

from scripts.run_h3_reset_guarded_exact_h1_pilot_v12 import (
    CONTROLLER_RESET_EXACT_H1_FALLBACK,
    GATE_HORIZON_STEPS,
    pilot_config,
)


def test_reset_guarded_h1_preserves_exact_policy_action() -> None:
    config = pilot_config()
    contract = config["controller_reset_exact_h1_contract"]

    assert CONTROLLER_RESET_EXACT_H1_FALLBACK is True
    assert GATE_HORIZON_STEPS == 3
    assert contract["type"] == "reset_guarded_exact_h1"
    assert contract["fallback_action_steps"] == 1
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert contract["simulator_qpos_modified_by_reset"] is False
    assert contract["simulator_qvel_modified_by_reset"] is False
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["strict_no_crossing"] is True
    assert contract["fresh_replan_after_each_advance"] is True
    assert contract["recovery_contract_reused"] is False
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["recovery"]["max_transient_margin_loss_rad"] == 0.005
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
