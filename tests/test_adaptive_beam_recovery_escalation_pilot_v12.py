from __future__ import annotations

from scripts.run_adaptive_beam_recovery_escalation_pilot_v12 import (
    pilot_config,
)


def test_adaptive_beam_escalation_keeps_all_safety_gates() -> None:
    config = pilot_config()

    assert (
        config["receding_horizon"][
            "escalation_candidate_generator"
        ]
        == "frozen primitives first, joint-targeted beam fallback"
    )
    assert len(config["recovery"]["candidate_library"]) == 13
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["recovery"]["required_margin_gain_rad"] == 0.02
    )
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
