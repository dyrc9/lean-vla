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
from scripts import run_policy_prefix_shadow_v12_qualification as fresh_runner
from proofalign.policy_prefix_shadow_warmstart_v12 import (
    capture_warmstart_policy_shadow_snapshot,
    restore_warmstart_policy_shadow_snapshot,
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


def test_fresh_policy_runner_uses_warmstart_complete_snapshot() -> None:
    assert (
        fresh_runner.capture_warmstart_policy_shadow_snapshot
        is capture_warmstart_policy_shadow_snapshot
    )
    assert (
        fresh_runner.restore_warmstart_policy_shadow_snapshot
        is restore_warmstart_policy_shadow_snapshot
    )
