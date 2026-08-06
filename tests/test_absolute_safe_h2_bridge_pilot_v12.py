from __future__ import annotations

from scripts.run_absolute_safe_h2_bridge_pilot_v12 import (
    BRIDGE_FLOOR_MODE,
    CONSUME_BRIDGE_AUTHORIZED_PREFIX,
    GATE_HORIZON_STEPS,
    pilot_config,
)


def test_absolute_safe_h2_bridge_is_independent_from_recovery() -> None:
    config = pilot_config()
    contract = config["bridge_contract"]

    assert BRIDGE_FLOOR_MODE == "absolute_safe_margin"
    assert CONSUME_BRIDGE_AUTHORIZED_PREFIX is True
    assert GATE_HORIZON_STEPS == 2
    assert contract["type"] == "independent_controller_bridge"
    assert contract["terminal_margin_floor_rad"] == 0.15
    assert contract["strict_no_crossing"] is True
    assert contract["consume_same_authorized_prefix"] is True
    assert contract["recovery_contract_reused"] is False
    assert len(config["recovery"]["candidate_library"]) == 61
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
