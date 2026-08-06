from __future__ import annotations

from scripts.run_predictive_recovery_escalation_pilot_v12 import (
    MAXIMUM_RECOVERY_ESCALATIONS_PER_CYCLE,
    RECOVERY_ROUND_SEED_STRIDE,
    REPLAN_ATTEMPTS_PER_ROUND,
    pilot_config,
)


def test_predictive_escalation_keeps_recovery_and_h1_gates() -> None:
    config = pilot_config()

    assert REPLAN_ATTEMPTS_PER_ROUND == 1
    assert MAXIMUM_RECOVERY_ESCALATIONS_PER_CYCLE == 2
    assert RECOVERY_ROUND_SEED_STRIDE == 1_000
    assert len(config["recovery"]["candidate_library"]) == 13
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["recovery"]["max_transient_margin_loss_rad"] == 0.005
    )
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
