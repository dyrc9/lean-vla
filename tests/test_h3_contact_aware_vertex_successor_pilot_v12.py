from __future__ import annotations

from scripts.run_h3_contact_aware_vertex_successor_pilot_v12 import (
    pilot_config,
)


def test_successor_contract_is_frozen_and_not_consumed() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    receding = config["receding_horizon"]

    assert contract["other_joint_vertex_count"] == 64
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["safe_successor_required"] is True
    assert contract["successor_consumed"] is False
    assert (
        receding["contact_aware_vertex_require_safe_successor"]
        is True
    )
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
