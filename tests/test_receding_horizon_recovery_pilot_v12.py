from __future__ import annotations

from scripts.run_receding_horizon_recovery_pilot_v12 import (
    LANE_BASE_SEEDS,
    RECEDING_CYCLE_COUNT,
    SEED_CYCLE_STRIDE,
    pilot_config,
)


def test_receding_horizon_pilot_is_one_step_shadow_only() -> None:
    config = pilot_config()

    assert LANE_BASE_SEEDS == (10_509, 10_510)
    assert RECEDING_CYCLE_COUNT == 5
    assert SEED_CYCLE_STRIDE == 100
    assert (
        config["receding_horizon"][
            "advanced_policy_action_steps_per_cycle"
        ]
        == 1
    )
    assert (
        config["receding_horizon"]["screened_policy_prefix_steps"]
        == 10
    )
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
