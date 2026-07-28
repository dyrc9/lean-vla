from __future__ import annotations

import math

import pytest

from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)
from proofalign.semantic_progress_projection import (
    SemanticProgressProjectionConfig,
    SemanticProgressProjectionError,
    project_semantic_progress,
)


def _observation(
    *,
    eef: tuple[float, float, float] = (0.0, 0.0, 0.5),
    target: tuple[float, float, float] = (0.1, 0.0, 0.5),
    destination: tuple[float, float, float] = (0.2, 0.0, 0.5),
) -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=0,
        eef_position=eef,
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target", target),
            EntityPosition("destination", destination),
        ),
    )


def _zeros(steps: int = 10) -> tuple[float, ...]:
    return (0.0,) * (steps * 7)


def test_projection_adds_minimum_uniform_pick_progress() -> None:
    result = project_semantic_progress(
        semantic_subtask="pick_up(target)",
        observation=_observation(),
        nominal_command=_zeros(),
        command_shape=(10, 7),
    )

    assert result.accepted
    assert result.projected
    assert result.reason == "minimum_l2_terminal_progress_projection"
    assert result.final_command is not None
    assert result.final_terminal_progress_m == pytest.approx(
        0.0020000001,
        abs=1.0e-9,
    )
    x_values = result.final_command[0::7]
    assert len(set(round(value, 12) for value in x_values)) == 1
    assert sum(x_values) == pytest.approx(0.040000002, abs=1.0e-8)
    assert result.projection_l2 == pytest.approx(
        math.sqrt(10) * x_values[0]
    )
    for step in range(10):
        assert result.final_command[step * 7 + 3 : step * 7 + 7] == (
            0.0,
            0.0,
            0.0,
            0.0,
        )


def test_projection_uses_destination_for_held_motion() -> None:
    result = project_semantic_progress(
        semantic_subtask="move(target,destination)",
        observation=_observation(
            eef=(0.1, 0.0, 0.5),
            target=(0.1, 0.0, 0.5),
            destination=(0.1, 0.2, 0.5),
        ),
        nominal_command=_zeros(),
        command_shape=(10, 7),
    )

    assert result.accepted
    assert result.final_command is not None
    assert result.goal_entity_id == "destination"
    assert sum(result.final_command[1::7]) > 0
    assert result.final_terminal_progress_m is not None
    assert result.final_terminal_progress_m >= 0.002


def test_projection_preserves_sufficient_nominal_block() -> None:
    command = list(_zeros())
    for step in range(10):
        command[step * 7] = 0.01
        command[step * 7 + 4] = 0.25
        command[step * 7 + 6] = -1.0
    result = project_semantic_progress(
        semantic_subtask="pick_up(target)",
        observation=_observation(),
        nominal_command=command,
        command_shape=(10, 7),
    )

    assert result.accepted
    assert not result.projected
    assert result.reason == "nominal_terminal_progress_sufficient"
    assert result.final_command == tuple(command)
    assert result.projection_l2 == 0.0


def test_projection_rejects_release_instead_of_changing_gripper() -> None:
    result = project_semantic_progress(
        semantic_subtask="release(target)",
        observation=_observation(),
        nominal_command=_zeros(),
        command_shape=(10, 7),
    )

    assert not result.accepted
    assert result.final_command is None
    assert result.reason == "unsupported_projection_verb:release"


def test_projection_rejects_when_small_budget_cannot_repair() -> None:
    result = project_semantic_progress(
        semantic_subtask="pick_up(target)",
        observation=_observation(),
        nominal_command=_zeros(),
        command_shape=(10, 7),
        config=SemanticProgressProjectionConfig(
            max_projection_l2=0.001
        ),
    )

    assert not result.accepted
    assert result.final_command is None
    assert result.reason == "semantic_projection_budget_exceeded"


def test_projection_witness_is_deterministic_and_observation_bound() -> None:
    kwargs = {
        "semantic_subtask": "pick_up(target)",
        "observation": _observation(),
        "nominal_command": _zeros(),
        "command_shape": (10, 7),
    }
    left = project_semantic_progress(**kwargs)
    right = project_semantic_progress(**kwargs)
    moved = project_semantic_progress(
        **{
            **kwargs,
            "observation": _observation(eef=(0.0, 0.01, 0.5)),
        }
    )

    assert left.witness_digest == right.witness_digest
    assert left.witness_digest != moved.witness_digest


def test_projection_rejects_non_libero_shape() -> None:
    with pytest.raises(SemanticProgressProjectionError):
        project_semantic_progress(
            semantic_subtask="pick_up(target)",
            observation=_observation(),
            nominal_command=(0.0,) * 60,
            command_shape=(10, 6),
        )
