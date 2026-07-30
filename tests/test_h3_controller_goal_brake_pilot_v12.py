from __future__ import annotations

from scripts.run_h3_controller_goal_brake_pilot_v12 import (
    CONTROLLER_GOAL_RESET_BEFORE_BRIDGE,
    GATE_HORIZON_STEPS,
    pilot_config,
)


def test_controller_goal_brake_does_not_change_recovery_contract() -> None:
    config = pilot_config()
    contract = config["bridge_contract"]

    assert CONTROLLER_GOAL_RESET_BEFORE_BRIDGE is True
    assert GATE_HORIZON_STEPS == 3
    assert contract["type"] == "controller_goal_reset_brake"
    assert contract["controller_goal_rebound_to_current_pose"] is True
    assert contract["simulator_qpos_modified_by_reset"] is False
    assert contract["simulator_qvel_modified_by_reset"] is False
    assert contract["terminal_margin_floor_rad"] == 0.15
    assert contract["bridge_action_library_count"] == 61
    assert contract["bridge_action_count"] == 1
    assert contract["recovery_contract_reused"] is False
    assert config["recovery"]["safe_margin_rad"] == 0.15
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
