from __future__ import annotations

from scripts.run_h3_sequence_bridge_pilot_v12 import (
    ANTI_POLICY_SCALES,
    BRIDGE_BEAM_WIDTH,
    BRIDGE_MAXIMUM_DEPTH,
    GATE_HORIZON_STEPS,
    MAXIMUM_POLICY_CANDIDATES,
    pilot_config,
)


def test_h3_sequence_bridge_preserves_independent_safety_contract() -> None:
    config = pilot_config()
    contract = config["bridge_contract"]

    assert GATE_HORIZON_STEPS == 3
    assert BRIDGE_MAXIMUM_DEPTH == 3
    assert BRIDGE_BEAM_WIDTH == 96
    assert MAXIMUM_POLICY_CANDIDATES == 192
    assert ANTI_POLICY_SCALES == (0.25, 0.5, 0.75, 1.0)
    assert contract["type"] == "controller_aware_sequence_bridge"
    assert contract["terminal_margin_floor_rad"] == 0.15
    assert contract["strict_no_crossing"] is True
    assert contract["consume_same_authorized_prefix"] is True
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
