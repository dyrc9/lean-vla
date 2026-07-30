from __future__ import annotations

from scripts.run_joint_targeted_beam_recovery_pilot_v12 import (
    BEAM_WIDTH,
    MAX_DEPTH,
    MAX_POLICY_CANDIDATES,
    TARGET_JOINT_INDEX,
    TARGET_JOINT_SIDE,
    pilot_config,
)


def test_joint_targeted_beam_pilot_keeps_original_gates() -> None:
    config = pilot_config()

    assert TARGET_JOINT_INDEX == 1
    assert TARGET_JOINT_SIDE == "upper"
    assert BEAM_WIDTH == 24
    assert MAX_DEPTH == 10
    assert MAX_POLICY_CANDIDATES == 96
    assert len(config["generator"]["action_ids"]) == 13
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
