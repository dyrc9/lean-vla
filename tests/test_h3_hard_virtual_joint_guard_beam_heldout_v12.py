from __future__ import annotations

from scripts.run_h3_hard_virtual_joint_guard_beam_heldout_v12 import (
    HELDOUT_LANE_BASE_SEEDS,
    pilot_config,
)


def test_heldout_contract_changes_only_unseen_lane_seeds() -> None:
    config = pilot_config()
    heldout = config["heldout_validation"]
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert HELDOUT_LANE_BASE_SEEDS == (20_509, 20_510)
    assert heldout["lane_base_seeds"] == [20_509, 20_510]
    assert heldout["seed_overlap_with_development"] is False
    assert heldout["method_or_threshold_change"] is False
    assert heldout["required_completed_cycles_per_lane"] == 5
    assert heldout["minimum_advanced_state_margin_rad"] == 0.15
    assert contract["method_frozen_before_heldout"] is True
    assert contract["virtual_joint_guard_margins_rad"] == [
        0.16,
        0.18,
        0.2,
        0.22,
    ]
    assert contract["virtual_joint_guard_solref"] == [0.004, 1.0]
    assert contract["virtual_joint_guard_solimp"] == [
        0.999,
        0.9999,
        0.001,
        0.5,
        2.0,
    ]
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
