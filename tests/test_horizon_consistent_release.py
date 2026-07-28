from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.horizon_consistent_release import (
    HorizonConsistentReleaseCandidatePolicy,
    canonicalize_release_action_block,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)
from scripts import run_l2_execution_attack_eval_v3 as runner_v3
from scripts import run_l2_execution_attack_eval_v5 as runner_v5


def _release_observation() -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=4,
        eef_position=(0.39, 0.0, 0.26),
        gripper_qpos=(0.0, 0.0),
        entity_positions=(
            EntityPosition("red_mug_1", (0.39, 0.0, 0.26)),
            EntityPosition("plate_1", (0.40, 0.0, 0.25)),
        ),
    )


def test_release_canonicalization_preserves_pose_and_opens_full_h10() -> None:
    source = np.zeros((10, 7), dtype=np.float64)
    source[:, :6] = np.arange(60, dtype=np.float64).reshape(10, 6) / 100
    source[:8, 6] = 1.0
    source[8:, 6] = -1.0

    final, audit = canonicalize_release_action_block(source)

    assert np.array_equal(final[:, :6], source[:, :6])
    assert np.array_equal(final[:, 6], np.full(10, -1.0))
    assert audit["changed_gripper_step_count"] == 8
    assert audit["terminal_open_command_count"] == 10
    assert audit["cartesian_rotation_channels_preserved"] is True


def test_canonical_release_passes_exact_local_recheck() -> None:
    source = np.zeros((10, 7), dtype=np.float64)
    source[:, 6] = 1.0
    final, _audit = canonicalize_release_action_block(source)

    assessment = SemanticExecutablePrefixChecker().assess(
        semantic_subtask="release(red_mug_1)",
        observation=_release_observation(),
        command=tuple(float(value) for value in final.reshape(-1)),
        command_shape=(10, 7),
        expected_state_epoch=4,
        release_destination="plate_1",
    )

    assert assessment.semantic_compatible is True
    assert assessment.violation_atoms == ()
    assert assessment.predicted_effect_atoms == (
        "gripper_open",
        "target_released",
    )


def test_v5_runner_injects_release_successor_only_for_l1(
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
        runner_v5.v4,
        "run_episode",
        fake_v4_run_episode,
    )
    payload = runner_v5.run_episode(
        args=SimpleNamespace(
            semantic_runtime=True,
            l1_semantic_alignment="on",
            l2_execution_integrity="on",
        )
    )

    assert observed["policy"] is HorizonConsistentReleaseCandidatePolicy
    assert runner_v3.OnlineProgressProjectionCandidatePolicy is original
    assert payload["metadata"]["runner_variant"] == (
        "proofalign_l2_execution_attack_successor_v5"
    )
    assert payload["metadata"][
        "horizon_consistent_release_active"
    ] is True
