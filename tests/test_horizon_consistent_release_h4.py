from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.horizon_consistent_release import (
    canonicalize_release_action_block,
)
from proofalign.horizon_consistent_release_h4 import (
    HorizonConsistentReleaseH4CandidatePolicy,
    RELEASE_MICRO_BLOCK_STEPS,
)
from scripts import run_l2_execution_attack_eval_v3 as runner_v3
from scripts import run_l2_execution_attack_eval_v6 as runner_v6


def test_h4_release_preserves_pose_and_opens_four_steps() -> None:
    source = np.zeros((10, 7), dtype=np.float64)
    source[:, :6] = 0.05
    source[:, 6] = 1.0

    final, audit = canonicalize_release_action_block(
        source,
        block_steps=RELEASE_MICRO_BLOCK_STEPS,
    )

    assert final.shape == (10, 7)
    assert np.array_equal(final[:4, :6], source[:4, :6])
    assert np.array_equal(final[:4, 6], np.full(4, -1.0))
    assert audit["terminal_open_command_count"] == 4
    assert audit["block_steps"] == 4


def test_v6_runner_injects_h4_policy_and_restores(
    monkeypatch,
) -> None:
    original = runner_v3.OnlineProgressProjectionCandidatePolicy
    observed = {}

    def fake_v4_run_episode(**_kwargs):
        observed["policy"] = (
            runner_v3.OnlineProgressProjectionCandidatePolicy
        )
        return {"metadata": {}}

    monkeypatch.setattr(
        runner_v6.v4,
        "run_episode",
        fake_v4_run_episode,
    )
    payload = runner_v6.run_episode(
        args=SimpleNamespace(
            semantic_runtime=True,
            l1_semantic_alignment="on",
            l2_execution_integrity="on",
        )
    )

    assert observed["policy"] is HorizonConsistentReleaseH4CandidatePolicy
    assert runner_v3.OnlineProgressProjectionCandidatePolicy is original
    assert payload["metadata"]["runner_variant"] == (
        "proofalign_l2_execution_attack_successor_v6"
    )
    assert payload["metadata"][
        "release_authorized_action_block_steps"
    ] == 4
