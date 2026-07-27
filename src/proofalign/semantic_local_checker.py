"""Analytic ``SemanticSubtask -> executable prefix`` checker.

The checker consumes only a trusted, current LIBERO geometry snapshot, one
canonical semantic subtask, and the exact prefix that would be executed.  It
does not read the policy-facing prompt, reward, success, cost, collision, or a
future observation.

The first implementation intentionally supports transport skills
(``pick_up``, ``move``, ``place``, and ``release``).  Articulation skills fail
closed until a trusted joint/part-state observation is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
import re
from typing import Any, Iterable, Mapping, Sequence

from proofalign.digests import digest_payload
from proofalign.semantic_action_selection import CheckedActionBlock


LOCAL_CHECKER_ID = "proofalign-libero-analytic-local-checker"
LOCAL_CHECKER_VERSION = "1"
LOCAL_OBSERVATION_SCHEMA = "proofalign.libero-trusted-local-observation.v1"


class LocalCheckerError(ValueError):
    """Raised when a checker input is structurally invalid."""


def _finite_tuple(
    values: Iterable[float], *, name: str, length: int | None = None
) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise LocalCheckerError(f"{name} must be numeric") from exc
    if (
        not frozen
        or any(not isfinite(value) for value in frozen)
        or (length is not None and len(frozen) != length)
    ):
        suffix = f" with length {length}" if length is not None else ""
        raise LocalCheckerError(f"{name} must be non-empty and finite{suffix}")
    return frozen


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sqrt(
        sum(
            (float(left[index]) - float(right[index])) ** 2
            for index in range(3)
        )
    )


def _xy_distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sqrt(
        sum(
            (float(left[index]) - float(right[index])) ** 2
            for index in range(2)
        )
    )


@dataclass(frozen=True)
class EntityPosition:
    entity_id: str
    position: tuple[float, float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise LocalCheckerError("entity_id must be a non-empty string")
        frozen = _finite_tuple(self.position, name="position", length=3)
        object.__setattr__(self, "position", frozen)


@dataclass(frozen=True)
class TrustedLocalObservation:
    """Current trusted robot/object geometry used by the local checker."""

    state_epoch: int
    eef_position: tuple[float, float, float]
    gripper_qpos: tuple[float, ...]
    entity_positions: tuple[EntityPosition, ...]
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.state_epoch) is not int or self.state_epoch < 0:
            raise LocalCheckerError("state_epoch must be a non-negative integer")
        eef = _finite_tuple(self.eef_position, name="eef_position", length=3)
        gripper = _finite_tuple(self.gripper_qpos, name="gripper_qpos")
        positions = tuple(self.entity_positions)
        if any(not isinstance(item, EntityPosition) for item in positions):
            raise LocalCheckerError(
                "entity_positions must contain EntityPosition values"
            )
        ids = [item.entity_id for item in positions]
        if len(ids) != len(set(ids)):
            raise LocalCheckerError("entity_positions contains duplicate ids")
        positions = tuple(sorted(positions, key=lambda item: item.entity_id))
        object.__setattr__(self, "eef_position", eef)
        object.__setattr__(self, "gripper_qpos", gripper)
        object.__setattr__(self, "entity_positions", positions)
        object.__setattr__(
            self,
            "observation_digest",
            digest_payload(
                {
                    "schema": LOCAL_OBSERVATION_SCHEMA,
                    "state_epoch": self.state_epoch,
                    "eef_position": eef,
                    "gripper_qpos": gripper,
                    "entity_positions": positions,
                }
            ),
        )

    @classmethod
    def from_libero_observation(
        cls,
        observation: Mapping[str, Any],
        *,
        state_epoch: int,
    ) -> "TrustedLocalObservation":
        """Extract only current robot/object geometry from a raw LIBERO view."""

        try:
            eef = observation["robot0_eef_pos"]
            gripper = observation["robot0_gripper_qpos"]
        except KeyError as exc:
            raise LocalCheckerError(
                f"trusted observation is missing {exc.args[0]}"
            ) from exc
        entities = []
        for key, value in observation.items():
            if (
                not isinstance(key, str)
                or not key.endswith("_pos")
                or key.startswith("robot0_")
                or "_to_robot" in key
                or key == "world_pose_in_gripper"
            ):
                continue
            try:
                position = _finite_tuple(
                    value, name=f"observation[{key!r}]", length=3
                )
            except (LocalCheckerError, TypeError):
                continue
            entities.append(EntityPosition(key[:-4], position))
        return cls(
            state_epoch=state_epoch,
            eef_position=tuple(eef),
            gripper_qpos=tuple(gripper),
            entity_positions=tuple(entities),
        )

    @property
    def gripper_closedness(self) -> float:
        return sum(abs(value) for value in self.gripper_qpos) / len(
            self.gripper_qpos
        )

    def position(self, entity_id: str) -> tuple[float, float, float] | None:
        positions = {item.entity_id: item.position for item in self.entity_positions}
        if entity_id in positions:
            return positions[entity_id]
        # BDDL destinations are frequently object sites such as
        # ``microwave_1_heating_region``.  Bind them conservatively to the
        # longest observed fixture/object prefix when no site pose is exposed.
        prefixes = [
            (name, position)
            for name, position in positions.items()
            if entity_id.startswith(name + "_")
        ]
        if not prefixes:
            return None
        return max(prefixes, key=lambda item: len(item[0]))[1]


@dataclass(frozen=True)
class LocalCheckerConfig:
    translation_scale_m: float = 0.05
    rotation_scale_rad: float = 0.5
    max_normalized_translation_norm: float = 1.6
    max_normalized_rotation_norm: float = 1.6
    workspace_low: tuple[float, float, float] = (-1.0, -1.0, 0.0)
    workspace_high: tuple[float, float, float] = (1.0, 1.0, 1.5)
    target_neighborhood_m: float = 0.10
    held_neighborhood_m: float = 0.12
    destination_neighborhood_m: float = 0.15
    release_neighborhood_m: float = 0.16
    contact_neighborhood_m: float = 0.035
    min_progress_m: float = 0.002
    gripper_closed_qpos_max: float = 0.025
    close_command_threshold: float = 0.2
    open_command_threshold: float = -0.2

    def __post_init__(self) -> None:
        positive = (
            "translation_scale_m",
            "rotation_scale_rad",
            "max_normalized_translation_norm",
            "max_normalized_rotation_norm",
            "target_neighborhood_m",
            "held_neighborhood_m",
            "destination_neighborhood_m",
            "release_neighborhood_m",
            "contact_neighborhood_m",
            "min_progress_m",
            "gripper_closed_qpos_max",
        )
        for name in positive:
            value = getattr(self, name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(float(value))
                or float(value) <= 0
            ):
                raise LocalCheckerError(f"{name} must be positive and finite")
        low = _finite_tuple(self.workspace_low, name="workspace_low", length=3)
        high = _finite_tuple(self.workspace_high, name="workspace_high", length=3)
        if any(lower >= upper for lower, upper in zip(low, high, strict=True)):
            raise LocalCheckerError("workspace bounds must be ordered")
        for name in ("close_command_threshold", "open_command_threshold"):
            value = getattr(self, name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(float(value))
            ):
                raise LocalCheckerError(f"{name} must be finite")
        object.__setattr__(self, "workspace_low", low)
        object.__setattr__(self, "workspace_high", high)

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": LOCAL_CHECKER_VERSION,
                **self.__dict__,
            }
        )


@dataclass(frozen=True)
class ParsedSemanticSubtask:
    verb: str
    target: str | None
    destination: str | None = None
    part: str | None = None


_SUBTASK_PATTERN = re.compile(
    r"^(?P<verb>pick_up|move|place|release|open|close|actuate|finish)"
    r"\((?P<arguments>[^()]*)\)$"
)


def parse_semantic_subtask(value: str) -> ParsedSemanticSubtask:
    if not isinstance(value, str):
        raise LocalCheckerError("semantic subtask must be a string")
    match = _SUBTASK_PATTERN.fullmatch(value.strip())
    if match is None:
        raise LocalCheckerError("semantic subtask is not canonical")
    verb = match.group("verb")
    arguments = tuple(
        item.strip()
        for item in match.group("arguments").split(",")
        if item.strip()
    )
    expected = {
        "pick_up": 1,
        "move": 2,
        "place": 2,
        "release": 1,
        "open": 1,
        "close": 1,
        "actuate": 2,
        "finish": 0,
    }[verb]
    if len(arguments) != expected:
        raise LocalCheckerError(
            f"{verb} requires {expected} canonical argument(s)"
        )
    return ParsedSemanticSubtask(
        verb=verb,
        target=arguments[0] if arguments else None,
        destination=arguments[1] if verb in {"move", "place"} else None,
        part=arguments[1] if verb == "actuate" else None,
    )


@dataclass(frozen=True)
class LocalActionAssessment:
    known: bool
    semantic_compatible: bool
    motion_atoms: tuple[str, ...]
    precondition_atoms: tuple[str, ...]
    predicted_effect_atoms: tuple[str, ...]
    violation_atoms: tuple[str, ...]
    progress_margin: float | None
    target: str | None
    part: str | None
    region: str | None
    unknown_reason: str | None = None


class SemanticExecutablePrefixChecker:
    """Deterministic local kinematic/geometry checker for a frozen ``Z_t``."""

    def __init__(self, config: LocalCheckerConfig | None = None) -> None:
        self.config = config or LocalCheckerConfig()

    def assess(
        self,
        *,
        semantic_subtask: str,
        observation: TrustedLocalObservation,
        command: Iterable[float],
        command_shape: Sequence[int],
        expected_state_epoch: int,
        release_destination: str | None = None,
    ) -> LocalActionAssessment:
        if observation.state_epoch != expected_state_epoch:
            return self._unknown(
                "stale_observation_state_epoch",
                target=None,
                region=release_destination,
            )
        try:
            subtask = parse_semantic_subtask(semantic_subtask)
            steps = self._steps(command, command_shape)
        except LocalCheckerError as exc:
            return self._unknown(
                f"malformed_checker_input:{exc}",
                target=None,
                region=release_destination,
            )
        if subtask.verb in {"open", "close", "actuate"}:
            return self._unknown(
                "trusted_articulation_state_unavailable",
                target=subtask.target,
                part=subtask.part,
            )
        if subtask.verb == "finish":
            return self._unknown(
                "finish_has_no_executable_prefix",
                target=None,
            )
        target_position = observation.position(subtask.target or "")
        if target_position is None:
            return self._unknown(
                "missing_target_geometry",
                target=subtask.target,
                region=subtask.destination or release_destination,
            )
        destination_id = subtask.destination or release_destination
        destination_position = (
            observation.position(destination_id) if destination_id else None
        )
        if subtask.verb in {"move", "place", "release"} and destination_position is None:
            return self._unknown(
                "missing_destination_geometry",
                target=subtask.target,
                region=destination_id,
            )

        allowed_contact_entities = {
            value
            for value in (
                subtask.target,
                subtask.destination,
                release_destination,
            )
            if value is not None
        }
        violations = list(
            self._hard_violations(
                observation,
                steps,
                allowed_contact_entities=allowed_contact_entities,
            )
        )
        held = (
            observation.gripper_closedness <= self.config.gripper_closed_qpos_max
            and _distance(observation.eef_position, target_position)
            <= self.config.held_neighborhood_m
        )
        if subtask.verb == "pick_up":
            assessment = self._assess_pick_up(
                observation, target_position, steps, held=held
            )
        elif subtask.verb == "move":
            assessment = self._assess_move(
                observation,
                target_position,
                destination_position,
                steps,
                held=held,
            )
        elif subtask.verb == "place":
            assessment = self._assess_place(
                observation,
                target_position,
                destination_position,
                steps,
                held=held,
            )
        else:
            assessment = self._assess_release(
                observation,
                target_position,
                destination_position,
                steps,
                held=held,
            )
        combined = tuple(dict.fromkeys((*violations, *assessment.violation_atoms)))
        return LocalActionAssessment(
            known=True,
            semantic_compatible=assessment.semantic_compatible and not combined,
            motion_atoms=assessment.motion_atoms,
            precondition_atoms=assessment.precondition_atoms,
            predicted_effect_atoms=assessment.predicted_effect_atoms,
            violation_atoms=combined,
            progress_margin=assessment.progress_margin,
            target=subtask.target,
            part=subtask.part,
            region=destination_id,
        )

    def checked_candidate(
        self,
        *,
        candidate_index: int,
        semantic_subtask_digest: str,
        semantic_subtask: str,
        observation: TrustedLocalObservation,
        nominal_command: Iterable[float],
        final_command: Iterable[float],
        command_shape: Sequence[int],
        expected_state_epoch: int,
        release_destination: str | None = None,
    ) -> tuple[CheckedActionBlock, LocalActionAssessment]:
        nominal = tuple(nominal_command)
        final = tuple(final_command)
        nominal_result = self.assess(
            semantic_subtask=semantic_subtask,
            observation=observation,
            command=nominal,
            command_shape=command_shape,
            expected_state_epoch=expected_state_epoch,
            release_destination=release_destination,
        )
        final_result = self.assess(
            semantic_subtask=semantic_subtask,
            observation=observation,
            command=final,
            command_shape=command_shape,
            expected_state_epoch=expected_state_epoch,
            release_destination=release_destination,
        )
        violations = tuple(
            dict.fromkeys(
                (
                    *nominal_result.violation_atoms,
                    *final_result.violation_atoms,
                )
            )
        )
        checked = CheckedActionBlock(
            candidate_index=candidate_index,
            semantic_subtask_digest=semantic_subtask_digest,
            nominal_command=nominal,
            final_command=final,
            command_shape=tuple(command_shape),
            known=nominal_result.known and final_result.known,
            semantic_compatible=nominal_result.semantic_compatible,
            post_projection_compatible=final_result.semantic_compatible,
            hard_violation_atoms=violations,
            progress_margin=(
                final_result.progress_margin
                if final_result.progress_margin is not None
                else -1.0e30
            ),
        )
        return checked, final_result

    def _steps(
        self,
        command: Iterable[float],
        command_shape: Sequence[int],
    ) -> tuple[tuple[float, ...], ...]:
        flat = _finite_tuple(command, name="command")
        shape = tuple(command_shape)
        if (
            len(shape) != 2
            or any(type(value) is not int or value <= 0 for value in shape)
            or shape[0] * shape[1] != len(flat)
            or shape[1] != 7
        ):
            raise LocalCheckerError(
                "LIBERO executable prefix shape must be (steps, 7)"
            )
        return tuple(
            flat[index * 7 : (index + 1) * 7] for index in range(shape[0])
        )

    def _trajectory(
        self,
        start: Sequence[float],
        steps: Sequence[Sequence[float]],
    ) -> tuple[tuple[float, float, float], ...]:
        current = tuple(float(value) for value in start)
        positions = []
        for step in steps:
            current = tuple(
                current[index]
                + float(step[index]) * self.config.translation_scale_m
                for index in range(3)
            )
            positions.append(current)
        return tuple(positions)

    def _hard_violations(
        self,
        observation: TrustedLocalObservation,
        steps: Sequence[Sequence[float]],
        *,
        allowed_contact_entities: set[str],
    ) -> tuple[str, ...]:
        violations = []
        for step in steps:
            translation_norm = sqrt(sum(float(value) ** 2 for value in step[:3]))
            rotation_norm = sqrt(sum(float(value) ** 2 for value in step[3:6]))
            if translation_norm > self.config.max_normalized_translation_norm:
                violations.append("translation_velocity_limit")
            if rotation_norm > self.config.max_normalized_rotation_norm:
                violations.append("rotation_velocity_limit")
        trajectory = self._trajectory(observation.eef_position, steps)
        for position in trajectory:
            if any(
                value < lower or value > upper
                for value, lower, upper in zip(
                    position,
                    self.config.workspace_low,
                    self.config.workspace_high,
                    strict=True,
                )
            ):
                violations.append("workspace_exit")
            for entity in observation.entity_positions:
                if any(
                    entity.entity_id == allowed
                    or allowed.startswith(entity.entity_id + "_")
                    for allowed in allowed_contact_entities
                ):
                    continue
                if (
                    _distance(position, entity.position)
                    <= self.config.contact_neighborhood_m
                ):
                    violations.append(
                        f"unexpected_contact_neighborhood:{entity.entity_id}"
                    )
        return tuple(dict.fromkeys(violations))

    def _assess_pick_up(
        self,
        observation: TrustedLocalObservation,
        target: Sequence[float],
        steps: Sequence[Sequence[float]],
        *,
        held: bool,
    ) -> LocalActionAssessment:
        trajectory = self._trajectory(observation.eef_position, steps)
        initial_distance = _distance(observation.eef_position, target)
        closest_distance = min(_distance(position, target) for position in trajectory)
        progress = initial_distance - closest_distance
        violations = []
        for position, step in zip(trajectory, steps, strict=True):
            if (
                step[6] > self.config.close_command_threshold
                and _distance(position, target) > self.config.target_neighborhood_m
            ):
                violations.append("close_outside_target_neighborhood")
        closes_near = any(
            step[6] > self.config.close_command_threshold
            and _distance(position, target) <= self.config.target_neighborhood_m
            for position, step in zip(trajectory, steps, strict=True)
        )
        lifts_held = held and trajectory[-1][2] > observation.eef_position[2]
        compatible = (
            progress >= self.config.min_progress_m or closes_near or lifts_held
        )
        motion = (
            ("lift",)
            if lifts_held
            else ("grasp",)
            if closes_near
            else ("approach",)
        )
        effects = (
            ("holding_target",)
            if closes_near or lifts_held
            else ("near_target",)
        )
        return LocalActionAssessment(
            known=True,
            semantic_compatible=compatible,
            motion_atoms=motion,
            precondition_atoms=("target_geometry_known",),
            predicted_effect_atoms=effects,
            violation_atoms=tuple(dict.fromkeys(violations)),
            progress_margin=progress,
            target=None,
            part=None,
            region=None,
        )

    def _assess_move(
        self,
        observation: TrustedLocalObservation,
        target: Sequence[float],
        destination: Sequence[float] | None,
        steps: Sequence[Sequence[float]],
        *,
        held: bool,
    ) -> LocalActionAssessment:
        assert destination is not None
        trajectory = self._trajectory(observation.eef_position, steps)
        displacement = tuple(
            trajectory[-1][index] - observation.eef_position[index]
            for index in range(3)
        )
        predicted_target = tuple(
            target[index] + displacement[index] for index in range(3)
        )
        progress = _distance(target, destination) - _distance(
            predicted_target, destination
        )
        violations = []
        if not held:
            violations.append("move_without_held_target")
        if any(step[6] < self.config.open_command_threshold for step in steps):
            violations.append("release_during_move")
        return LocalActionAssessment(
            known=True,
            semantic_compatible=held and progress >= self.config.min_progress_m,
            motion_atoms=("transport",),
            precondition_atoms=("holding_target",),
            predicted_effect_atoms=("closer_to_destination",),
            violation_atoms=tuple(violations),
            progress_margin=progress,
            target=None,
            part=None,
            region=None,
        )

    def _assess_place(
        self,
        observation: TrustedLocalObservation,
        target: Sequence[float],
        destination: Sequence[float] | None,
        steps: Sequence[Sequence[float]],
        *,
        held: bool,
    ) -> LocalActionAssessment:
        assert destination is not None
        trajectory = self._trajectory(observation.eef_position, steps)
        displacement = tuple(
            trajectory[-1][index] - observation.eef_position[index]
            for index in range(3)
        )
        predicted_target = tuple(
            target[index] + displacement[index] for index in range(3)
        )
        initial = _distance(target, destination)
        final = _distance(predicted_target, destination)
        progress = initial - final
        descends = trajectory[-1][2] < observation.eef_position[2]
        violations = []
        if not held:
            violations.append("place_without_held_target")
        for position, step in zip(trajectory, steps, strict=True):
            if (
                step[6] < self.config.open_command_threshold
                and _distance(position, destination)
                > self.config.release_neighborhood_m
            ):
                violations.append("release_outside_valid_place_region")
        compatible = held and (
            progress >= self.config.min_progress_m
            or (
                _xy_distance(target, destination)
                <= self.config.destination_neighborhood_m
                and descends
            )
        )
        return LocalActionAssessment(
            known=True,
            semantic_compatible=compatible,
            motion_atoms=("place", "lower" if descends else "align"),
            precondition_atoms=("holding_target", "destination_geometry_known"),
            predicted_effect_atoms=("target_in_place_region",),
            violation_atoms=tuple(dict.fromkeys(violations)),
            progress_margin=progress,
            target=None,
            part=None,
            region=None,
        )

    def _assess_release(
        self,
        observation: TrustedLocalObservation,
        target: Sequence[float],
        destination: Sequence[float] | None,
        steps: Sequence[Sequence[float]],
        *,
        held: bool,
    ) -> LocalActionAssessment:
        assert destination is not None
        trajectory = self._trajectory(observation.eef_position, steps)
        releases = [
            _distance(position, destination)
            for position, step in zip(trajectory, steps, strict=True)
            if step[6] < self.config.open_command_threshold
        ]
        valid_release = bool(releases) and min(releases) <= (
            self.config.release_neighborhood_m
        )
        violations = []
        if not held:
            violations.append("release_without_held_target")
        if releases and not valid_release:
            violations.append("release_outside_valid_place_region")
        if not releases:
            violations.append("release_command_missing")
        margin = (
            self.config.release_neighborhood_m - min(releases)
            if releases
            else -self.config.release_neighborhood_m
        )
        return LocalActionAssessment(
            known=True,
            semantic_compatible=held and valid_release,
            motion_atoms=("release",),
            precondition_atoms=("holding_target", "target_in_place_region"),
            predicted_effect_atoms=("gripper_open", "target_released"),
            violation_atoms=tuple(violations),
            progress_margin=margin,
            target=None,
            part=None,
            region=None,
        )

    @staticmethod
    def _unknown(
        reason: str,
        *,
        target: str | None,
        part: str | None = None,
        region: str | None = None,
    ) -> LocalActionAssessment:
        return LocalActionAssessment(
            known=False,
            semantic_compatible=False,
            motion_atoms=(),
            precondition_atoms=(),
            predicted_effect_atoms=(),
            violation_atoms=(),
            progress_margin=None,
            target=target,
            part=part,
            region=region,
            unknown_reason=reason,
        )


__all__ = [
    "LOCAL_CHECKER_ID",
    "LOCAL_CHECKER_VERSION",
    "EntityPosition",
    "LocalActionAssessment",
    "LocalCheckerConfig",
    "LocalCheckerError",
    "ParsedSemanticSubtask",
    "SemanticExecutablePrefixChecker",
    "TrustedLocalObservation",
    "parse_semantic_subtask",
]
