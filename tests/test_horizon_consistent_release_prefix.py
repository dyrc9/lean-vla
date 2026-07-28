from __future__ import annotations

from proofalign.horizon_consistent_release_prefix import (
    RELEASE_PREFIX_PROGRESS_EFFECT,
    ReleasePrefixSemanticEffectObserver,
    ReleasePrefixSemanticExecutablePrefixChecker,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)


def _observation(
    *,
    epoch: int,
    gripper: tuple[float, float],
) -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=(0.10, 0.0, 0.30),
        gripper_qpos=gripper,
        entity_positions=(
            EntityPosition("target_1", (0.10, 0.0, 0.30)),
            EntityPosition("destination_1", (0.11, 0.0, 0.30)),
        ),
    )


def test_release_checker_promises_prefix_not_completed_release() -> None:
    command = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0) * 4
    result = ReleasePrefixSemanticExecutablePrefixChecker().assess(
        semantic_subtask="release(target_1)",
        observation=_observation(
            epoch=0,
            gripper=(0.002, -0.002),
        ),
        command=command,
        command_shape=(4, 7),
        expected_state_epoch=0,
        release_destination="destination_1",
    )

    assert result.semantic_compatible is True
    assert result.predicted_effect_atoms == (
        RELEASE_PREFIX_PROGRESS_EFFECT,
    )
    assert "target_released" not in result.predicted_effect_atoms


def test_release_observer_accepts_opening_progress_without_full_open() -> None:
    result = ReleasePrefixSemanticEffectObserver().observe(
        semantic_subtask="release(target_1)",
        release_destination="destination_1",
        before=_observation(
            epoch=0,
            gripper=(0.002, -0.002),
        ),
        after=_observation(
            epoch=1,
            gripper=(0.008, -0.008),
        ),
        prefix_complete=True,
    )

    assert RELEASE_PREFIX_PROGRESS_EFFECT in (
        result.observed_effect_atoms
    )
    assert "gripper_open" not in result.observed_effect_atoms
    assert "target_released" not in result.observed_effect_atoms
