from __future__ import annotations

from dataclasses import replace

from proofalign.semantic_local_checker import (
    EntityPosition,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
    parse_semantic_subtask,
)


SUBTASK_DIGEST = "a" * 64


def _observation(
    *,
    epoch: int = 4,
    eef: tuple[float, float, float] = (0.0, 0.0, 0.25),
    gripper: tuple[float, float] = (0.04, -0.04),
    target: tuple[float, float, float] = (0.15, 0.0, 0.25),
    destination: tuple[float, float, float] = (0.40, 0.0, 0.25),
) -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=eef,
        gripper_qpos=gripper,
        entity_positions=(
            EntityPosition("red_mug_1", target),
            EntityPosition("plate_1", destination),
            EntityPosition("microwave_1", (0.5, 0.1, 0.3)),
        ),
    )


def _flat(*steps: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(value for step in steps for value in step)


def _checker(**changes: object) -> SemanticExecutablePrefixChecker:
    config = LocalCheckerConfig()
    if changes:
        config = replace(config, **changes)
    return SemanticExecutablePrefixChecker(config)


def test_canonical_subtask_parser_keeps_target_destination_and_part() -> None:
    move = parse_semantic_subtask("move(red_mug_1,plate_1)")
    actuate = parse_semantic_subtask("actuate(flat_stove_1,knob)")

    assert (move.verb, move.target, move.destination) == (
        "move",
        "red_mug_1",
        "plate_1",
    )
    assert (actuate.target, actuate.part) == ("flat_stove_1", "knob")


def test_pick_up_accepts_approach_progress() -> None:
    result = _checker().assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=_observation(),
        command=_flat((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert result.known
    assert result.semantic_compatible
    assert result.motion_atoms == ("approach",)
    assert result.predicted_effect_atoms == ("closer_to_target",)
    assert result.progress_margin is not None and result.progress_margin > 0


def test_pick_up_rejects_close_outside_target_neighborhood() -> None:
    result = _checker().assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=_observation(target=(0.5, 0.0, 0.25)),
        command=_flat((0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)),
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert not result.semantic_compatible
    assert "close_outside_target_neighborhood" in result.violation_atoms


def test_move_requires_held_target_and_progress_toward_destination() -> None:
    command = _flat((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))
    not_held = _checker().assess(
        semantic_subtask="move(red_mug_1,plate_1)",
        observation=_observation(),
        command=command,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )
    held = _checker().assess(
        semantic_subtask="move(red_mug_1,plate_1)",
        observation=_observation(
            eef=(0.15, 0.0, 0.25),
            target=(0.15, 0.0, 0.25),
            gripper=(0.0, 0.0),
        ),
        command=command,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert "move_without_held_target" in not_held.violation_atoms
    assert not not_held.semantic_compatible
    assert held.semantic_compatible


def test_place_and_release_fail_closed_outside_destination_region() -> None:
    observation = _observation(
        eef=(0.15, 0.0, 0.25),
        target=(0.15, 0.0, 0.25),
        destination=(0.6, 0.0, 0.25),
        gripper=(0.0, 0.0),
    )
    opens = _flat((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))

    place = _checker().assess(
        semantic_subtask="place(red_mug_1,plate_1)",
        observation=observation,
        command=opens,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )
    release = _checker().assess(
        semantic_subtask="release(red_mug_1)",
        observation=observation,
        command=opens,
        command_shape=(1, 7),
        expected_state_epoch=4,
        release_destination="plate_1",
    )

    assert "release_outside_valid_place_region" in place.violation_atoms
    assert "release_outside_valid_place_region" in release.violation_atoms
    assert not place.semantic_compatible
    assert not release.semantic_compatible


def test_release_accepts_open_command_in_bound_destination_region() -> None:
    observation = _observation(
        eef=(0.39, 0.0, 0.26),
        target=(0.39, 0.0, 0.26),
        destination=(0.40, 0.0, 0.25),
        gripper=(0.0, 0.0),
    )
    result = _checker().assess(
        semantic_subtask="release(red_mug_1)",
        observation=observation,
        command=_flat((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
        command_shape=(1, 7),
        expected_state_epoch=4,
        release_destination="plate_1",
    )

    assert result.semantic_compatible
    assert result.predicted_effect_atoms == ("gripper_open", "target_released")


def test_missing_geometry_stale_epoch_and_articulation_are_unknown() -> None:
    observation = TrustedLocalObservation(
        state_epoch=4,
        eef_position=(0.0, 0.0, 0.25),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(),
    )
    command = _flat((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    checker = _checker()

    missing = checker.assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=observation,
        command=command,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )
    stale = checker.assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=_observation(),
        command=command,
        command_shape=(1, 7),
        expected_state_epoch=5,
    )
    articulation = checker.assess(
        semantic_subtask="open(microwave_1)",
        observation=_observation(),
        command=command,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert missing.unknown_reason == "missing_target_geometry"
    assert stale.unknown_reason == "stale_observation_state_epoch"
    assert articulation.unknown_reason == "trusted_articulation_state_unavailable"


def test_workspace_translation_and_rotation_hard_violations() -> None:
    observation = _observation(
        eef=(0.99, 0.0, 0.25),
        target=(0.99, 0.0, 0.25),
    )
    result = _checker().assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=observation,
        command=_flat((2.0, 0.0, 0.0, 2.0, 0.0, 0.0, 1.0)),
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert "translation_velocity_limit" in result.violation_atoms
    assert "rotation_velocity_limit" in result.violation_atoms
    assert "workspace_exit" in result.violation_atoms
    assert not result.semantic_compatible


def test_unexpected_non_target_contact_neighborhood_is_hard_violation() -> None:
    observation = TrustedLocalObservation(
        state_epoch=4,
        eef_position=(0.0, 0.0, 0.25),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("red_mug_1", (0.15, 0.0, 0.25)),
            EntityPosition("knife_1", (0.05, 0.0, 0.25)),
        ),
    )
    result = _checker().assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=observation,
        command=_flat((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert "unexpected_contact_neighborhood:knife_1" in result.violation_atoms
    assert not result.semantic_compatible


def test_checked_candidate_records_post_projection_semantic_mismatch() -> None:
    observation = _observation()
    checker = _checker()
    nominal = _flat((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    projected_wrong_way = _flat(
        (-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
    )

    checked, final = checker.checked_candidate(
        candidate_index=0,
        semantic_subtask_digest=SUBTASK_DIGEST,
        semantic_subtask="pick_up(red_mug_1)",
        observation=observation,
        nominal_command=nominal,
        final_command=projected_wrong_way,
        command_shape=(1, 7),
        expected_state_epoch=4,
    )

    assert checked.semantic_compatible
    assert not checked.post_projection_compatible
    assert not final.semantic_compatible


def test_region_site_falls_back_to_longest_observed_entity_prefix() -> None:
    observation = _observation()

    assert observation.position("microwave_1_heating_region") == (
        0.5,
        0.1,
        0.3,
    )
