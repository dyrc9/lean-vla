from __future__ import annotations

from scripts.run_bounded_h1_replan_recovery_pilot_v12 import (
    REPLAN_ATTEMPTS_PER_CYCLE,
    SEED_ATTEMPT_STRIDE,
    pilot_config,
)


def test_bounded_h1_replan_keeps_exact_one_step_gate() -> None:
    config = pilot_config()

    assert REPLAN_ATTEMPTS_PER_CYCLE == 8
    assert SEED_ATTEMPT_STRIDE == 10
    assert (
        config["receding_horizon"]["replan_attempts_per_cycle"]
        == 8
    )
    assert (
        config["receding_horizon"][
            "advanced_policy_action_steps_per_cycle"
        ]
        == 1
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
