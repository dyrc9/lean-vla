from __future__ import annotations

from scripts.run_h3_nullspace_exact_h1_pilot_v12 import (
    NULLSPACE_RETREAT_OFFSETS_RAD,
    TARGET_JOINT_INDEX,
    TARGET_JOINT_SIDE,
    pilot_config,
)


def test_nullspace_fallback_preserves_exact_action_and_sim_state() -> None:
    config = pilot_config()
    contract = config["controller_nullspace_exact_h1_contract"]

    assert TARGET_JOINT_INDEX == 1
    assert TARGET_JOINT_SIDE == "upper"
    assert NULLSPACE_RETREAT_OFFSETS_RAD == (
        0.05,
        0.10,
        0.20,
        0.30,
        0.50,
    )
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        contract["simulator_qpos_modified_by_configuration"] is False
    )
    assert (
        contract["simulator_qvel_modified_by_configuration"] is False
    )
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["strict_no_crossing"] is True
    assert contract["recovery_contract_reused"] is False
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["recovery"]["max_transient_margin_loss_rad"] == 0.005
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
