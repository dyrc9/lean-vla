from __future__ import annotations

from scripts.run_h3_backup_viable_exact_h1_pilot_v12 import (
    MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE,
    RESET_EXACT_H1_REQUIRE_BACKUP_VIABILITY,
    pilot_config,
)


def test_backup_viability_preserves_exact_policy_success_boundary() -> None:
    config = pilot_config()
    contract = config["controller_reset_exact_h1_contract"]

    assert RESET_EXACT_H1_REQUIRE_BACKUP_VIABILITY is True
    assert MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE == 2
    assert (
        contract["type"]
        == "backup_viable_reset_guarded_exact_h1"
    )
    assert contract["backup_viability_required"] is True
    assert contract["backup_action_library_count"] == 61
    assert contract["backup_action_steps"] == 1
    assert contract["reserve_counts_as_policy_advance"] is False
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["simulator_qpos_modified_by_reset"] is False
    assert contract["simulator_qvel_modified_by_reset"] is False
    assert contract["recovery_contract_reused"] is False
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["recovery"]["max_transient_margin_loss_rad"] == 0.005
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
