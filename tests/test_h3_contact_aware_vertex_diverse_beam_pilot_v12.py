from __future__ import annotations

from scripts.run_h3_contact_aware_vertex_diverse_beam_pilot_v12 import (
    BEAM_WIDTH,
    MARGIN_QUOTA,
    RETENTION_STRATEGY,
    VELOCITY_QUOTA,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _retain_contact_aware_beam,
)


def _node(index: int) -> dict[str, object]:
    return {
        "sequence": (index,),
        "trajectory_minimum_margin_rad": 1.0 - index / 100.0,
        "terminal_target_joint_margin_rad": (
            1.0 - index / 100.0
        ),
        "terminal_toward_limit_velocity_rad_s": (
            1.0 - index / 100.0
        ),
    }


def test_diverse_beam_contract_splits_the_frozen_width() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert contract["beam_retention_strategy"] == (
        RETENTION_STRATEGY
    )
    assert contract["beam_width"] == BEAM_WIDTH == 64
    assert contract["beam_margin_quota"] == MARGIN_QUOTA == 32
    assert contract["beam_velocity_quota"] == VELOCITY_QUOTA == 32
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_diverse_retention_keeps_margin_and_velocity_extremes() -> None:
    expansions = [_node(index) for index in range(100)]
    margin, margin_audit = _retain_contact_aware_beam(
        expansions,
        beam_width=8,
        strategy="trajectory_margin",
    )
    diverse, diverse_audit = _retain_contact_aware_beam(
        expansions,
        beam_width=8,
        strategy=RETENTION_STRATEGY,
    )

    assert [node["sequence"] for node in margin] == [
        (index,) for index in range(8)
    ]
    assert [node["sequence"] for node in diverse] == [
        (0,),
        (1,),
        (2,),
        (3,),
        (96,),
        (97,),
        (98,),
        (99,),
    ]
    assert margin_audit["velocity_quota"] == 0
    assert diverse_audit["margin_quota"] == 4
    assert diverse_audit["velocity_quota"] == 4
    assert diverse_audit["retained_margin_top_count"] == 4
    assert diverse_audit["retained_velocity_top_count"] == 4
