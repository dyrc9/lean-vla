from __future__ import annotations

from scripts.freeze_fixed_policy_prefix_shadow_v12_terminal import (
    build_terminal as build_fixed_terminal,
)
from scripts.freeze_policy_prefix_shadow_v12_resource_failure import (
    build_terminal as build_resource_terminal,
)
from scripts.freeze_warmstart_policy_prefix_shadow_v12_terminal import (
    build_terminal as build_warmstart_terminal,
)


def test_fresh_policy_resource_nonstart_does_not_authorize_rollout() -> None:
    terminal = build_resource_terminal()

    assert terminal["qualification_started"] is False
    assert terminal["policy_inference_count"] == 0
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False


def test_fixed_prefix_pass_preserves_fidelity_tail() -> None:
    terminal = build_fixed_terminal()

    assert terminal["qualification_pass"] is True
    assert (
        terminal["metrics"][
            "repeat_trajectory_within_tolerance_rate"
        ]
        == 29 / 30
    )
    assert terminal["lifecycle"]["warmstart_successor_authorized"]


def test_warmstart_successor_closes_repeat_fidelity() -> None:
    terminal = build_warmstart_terminal()

    assert terminal["qualification_pass"] is True
    assert (
        terminal["metrics"][
            "repeat_trajectory_within_tolerance_rate"
        ]
        == 1.0
    )
    assert (
        terminal["metrics"][
            "qacc_warmstart_restore_identity_rate"
        ]
        == 1.0
    )
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False
