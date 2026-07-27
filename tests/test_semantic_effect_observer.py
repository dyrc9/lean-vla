from __future__ import annotations

from proofalign.semantic_effect_observer import (
    SemanticPrefixEffectObserver,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)


def _observation(
    *,
    epoch: int,
    eef: tuple[float, float, float],
    target: tuple[float, float, float] | None,
    destination: tuple[float, float, float] | None,
    closed: bool,
) -> TrustedLocalObservation:
    entities = []
    if target is not None:
        entities.append(EntityPosition("red_mug_1", target))
    if destination is not None:
        entities.append(EntityPosition("plate_1", destination))
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=eef,
        gripper_qpos=(
            (0.002, -0.002) if closed else (0.04, -0.04)
        ),
        entity_positions=tuple(entities),
    )


def test_observer_reports_transport_progress_and_binding_atoms() -> None:
    before = _observation(
        epoch=4,
        eef=(0.0, 0.0, 0.5),
        target=(0.0, 0.0, 0.5),
        destination=(0.4, 0.0, 0.5),
        closed=True,
    )
    after = _observation(
        epoch=5,
        eef=(0.1, 0.0, 0.5),
        target=(0.1, 0.0, 0.5),
        destination=(0.4, 0.0, 0.5),
        closed=True,
    )

    result = SemanticPrefixEffectObserver().observe(
        semantic_subtask="move(red_mug_1,plate_1)",
        before=before,
        after=after,
        prefix_complete=True,
    )

    assert result.known is True
    assert result.observed_effect_atoms == (
        "command_applied",
        "closer_to_destination",
    )
    assert result.observed_violation_atoms == ()
    assert result.progress_margin is not None
    assert result.progress_margin > 0


def test_observer_distinguishes_approach_progress_from_near_target() -> None:
    before = _observation(
        epoch=4,
        eef=(0.0, 0.0, 0.5),
        target=(0.3, 0.0, 0.5),
        destination=None,
        closed=False,
    )
    after = _observation(
        epoch=5,
        eef=(0.1, 0.0, 0.5),
        target=(0.3, 0.0, 0.5),
        destination=None,
        closed=False,
    )

    result = SemanticPrefixEffectObserver().observe(
        semantic_subtask="pick_up(red_mug_1)",
        before=before,
        after=after,
        prefix_complete=True,
    )

    assert result.observed_effect_atoms == (
        "command_applied",
        "closer_to_target",
    )
    assert result.progress_margin is not None
    assert result.progress_margin > 0


def test_observer_does_not_infer_release_without_open_gripper() -> None:
    before = _observation(
        epoch=2,
        eef=(0.0, 0.0, 0.5),
        target=(0.0, 0.0, 0.5),
        destination=(0.02, 0.0, 0.5),
        closed=True,
    )
    after = _observation(
        epoch=3,
        eef=(0.0, 0.0, 0.5),
        target=(0.02, 0.0, 0.5),
        destination=(0.02, 0.0, 0.5),
        closed=True,
    )

    result = SemanticPrefixEffectObserver().observe(
        semantic_subtask="release(red_mug_1)",
        release_destination="plate_1",
        before=before,
        after=after,
        prefix_complete=True,
    )

    assert result.known is True
    assert "gripper_open" not in result.observed_effect_atoms
    assert "target_released" not in result.observed_effect_atoms


def test_observer_fails_closed_on_incomplete_or_unbound_windows() -> None:
    before = _observation(
        epoch=7,
        eef=(0.0, 0.0, 0.5),
        target=(0.1, 0.0, 0.5),
        destination=(0.4, 0.0, 0.5),
        closed=False,
    )
    same_epoch = _observation(
        epoch=7,
        eef=(0.05, 0.0, 0.5),
        target=(0.1, 0.0, 0.5),
        destination=(0.4, 0.0, 0.5),
        closed=False,
    )
    observer = SemanticPrefixEffectObserver()

    incomplete = observer.observe(
        semantic_subtask="pick_up(red_mug_1)",
        before=before,
        after=same_epoch,
        prefix_complete=False,
    )
    stale = observer.observe(
        semantic_subtask="pick_up(red_mug_1)",
        before=before,
        after=same_epoch,
        prefix_complete=True,
    )

    assert incomplete.known is False
    assert incomplete.unknown_reason == "authorized_prefix_incomplete"
    assert stale.known is False
    assert stale.unknown_reason == "effect_observation_epoch_mismatch"
