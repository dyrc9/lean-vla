from __future__ import annotations

from scripts.run_safe_bridge_receding_horizon_pilot_v12 import (
    MAXIMUM_SAFE_BRIDGES_PER_CYCLE,
    SAFE_BRIDGE_SEED_STRIDE,
    pilot_config,
)


def test_safe_bridge_is_distinct_from_recovery_and_shadow_only() -> None:
    config = pilot_config()

    assert MAXIMUM_SAFE_BRIDGES_PER_CYCLE == 2
    assert SAFE_BRIDGE_SEED_STRIDE == 2_000
    assert (
        config["receding_horizon"][
            "maximum_recovery_escalations_per_cycle"
        ]
        == 0
    )
    assert len(config["receding_horizon"]["safe_bridge_action_ids"]) == 13
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["execution_boundary"][
            "typed_recovery_env_step_authorized"
        ]
        is False
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
