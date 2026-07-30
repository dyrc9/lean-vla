from __future__ import annotations

from scripts.run_h3_two_step_backup_exact_h1_pilot_v12 import (
    BACKUP_CERTIFICATE_DEPTH,
    pilot_config,
)


def test_two_step_backup_uses_same_frozen_safety_boundary() -> None:
    config = pilot_config()
    contract = config["controller_reset_exact_h1_contract"]

    assert BACKUP_CERTIFICATE_DEPTH == 2
    assert contract["backup_certificate_depth"] == 2
    assert contract["backup_successor_required"] is True
    assert contract["reserve_successor_required"] is True
    assert contract["backup_action_library_count"] == 61
    assert contract["maximum_reset_reserve_bridges_per_cycle"] == 2
    assert contract["reserve_counts_as_policy_advance"] is False
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["recovery"]["max_transient_margin_loss_rad"] == 0.005
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
