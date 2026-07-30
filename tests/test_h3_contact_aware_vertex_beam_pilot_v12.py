from __future__ import annotations

from scripts.run_h3_contact_aware_vertex_beam_pilot_v12 import (
    BEAM_WIDTH,
    MAX_BEAM_HORIZON,
    pilot_config,
)


def test_beam_contract_covers_remaining_cycles_without_tail_use() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    receding = config["receding_horizon"]

    assert contract["other_joint_vertex_count"] == 64
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["beam_width"] == BEAM_WIDTH == 64
    assert contract["maximum_beam_horizon"] == (
        MAX_BEAM_HORIZON
    ) == 4
    assert contract["beam_tail_consumed"] is False
    assert receding["contact_aware_vertex_beam_width"] == 64
    assert receding["contact_aware_vertex_beam_max_horizon"] == 4
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
