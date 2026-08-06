from __future__ import annotations

from scripts.run_h3_contact_aware_vertex_receding_floor_pilot_v12 import (
    pilot_config,
)


def test_receding_floor_changes_only_terminal_proxy_gate() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    receding = config["receding_horizon"]

    assert contract["other_joint_vertex_count"] == 64
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["terminal_non_toward_velocity_required"] is False
    assert (
        receding[
            "contact_aware_vertex_require_terminal_non_toward_velocity"
        ]
        is False
    )
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
