"""Bounded minimum-norm progress projection for a fixed semantic subtask.

The projector does not infer or change the semantic subtask.  It only adjusts
the translational channels of a finite LIBERO ActionBlock so that its terminal
displacement makes a protocol-frozen amount of progress toward the target
defined by the already-issued semantic subtask.  Callers must re-run the local
checker on the exact projected block before authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
from typing import Iterable, Sequence

from proofalign.digests import digest_payload
from proofalign.semantic_local_checker import (
    LocalCheckerError,
    TrustedLocalObservation,
    parse_semantic_subtask,
)


PROJECTION_SCHEMA = "proofalign.semantic-progress-projection.v1"


class SemanticProgressProjectionError(ValueError):
    """Raised when a progress-projection input is malformed."""


def _finite_tuple(
    values: Iterable[float],
    *,
    name: str,
) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise SemanticProgressProjectionError(
            f"{name} must be numeric"
        ) from exc
    if not frozen or any(not isfinite(value) for value in frozen):
        raise SemanticProgressProjectionError(
            f"{name} must be non-empty and finite"
        )
    return frozen


def _distance(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    return sqrt(
        sum(
            (float(left[index]) - float(right[index])) ** 2
            for index in range(3)
        )
    )


def _l2(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    return sqrt(
        sum(
            (float(right_value) - float(left_value)) ** 2
            for left_value, right_value in zip(left, right, strict=True)
        )
    )


def _terminal_progress(
    *,
    mover_start: Sequence[float],
    goal: Sequence[float],
    command: Sequence[float],
    command_shape: tuple[int, int],
    translation_scale_m: float,
) -> float:
    steps, width = command_shape
    displacement = [
        translation_scale_m
        * sum(command[step * width + axis] for step in range(steps))
        for axis in range(3)
    ]
    terminal = tuple(
        float(mover_start[axis]) + displacement[axis]
        for axis in range(3)
    )
    return _distance(mover_start, goal) - _distance(terminal, goal)


def _minimum_l2_bounded_offsets(
    values: Sequence[float],
    *,
    required_sum: float,
    lower: float,
    upper: float,
) -> tuple[float, ...] | None:
    """Solve min ||x||_2 with sum(x)=required_sum and box bounds."""

    lowers = tuple(lower - float(value) for value in values)
    uppers = tuple(upper - float(value) for value in values)
    minimum = sum(lowers)
    maximum = sum(uppers)
    tolerance = 1.0e-12
    if abs(required_sum) <= tolerance:
        return (0.0,) * len(values)
    if required_sum < minimum - tolerance or required_sum > maximum + tolerance:
        return None
    required = min(max(float(required_sum), minimum), maximum)
    low = min(lowers)
    high = max(uppers)
    for _ in range(100):
        midpoint = (low + high) / 2.0
        total = sum(
            min(max(midpoint, item_low), item_high)
            for item_low, item_high in zip(lowers, uppers, strict=True)
        )
        if total < required:
            low = midpoint
        else:
            high = midpoint
    level = (low + high) / 2.0
    offsets = [
        min(max(level, item_low), item_high)
        for item_low, item_high in zip(lowers, uppers, strict=True)
    ]
    residual = required - sum(offsets)
    if abs(residual) > tolerance:
        for index in range(len(offsets)):
            room = (
                uppers[index] - offsets[index]
                if residual > 0
                else offsets[index] - lowers[index]
            )
            change = min(abs(residual), room)
            offsets[index] += change if residual > 0 else -change
            residual += -change if residual > 0 else change
            if abs(residual) <= tolerance:
                break
    if abs(required - sum(offsets)) > 1.0e-9:
        return None
    return tuple(offsets)


@dataclass(frozen=True)
class SemanticProgressProjectionConfig:
    """Protocol-frozen limits for the semantic progress projector."""

    min_terminal_progress_m: float = 0.002
    max_projection_l2: float = 0.05
    translation_scale_m: float = 0.05
    action_low: float = -1.0
    action_high: float = 1.0
    supported_verbs: tuple[str, ...] = ("pick_up", "move", "place")

    def __post_init__(self) -> None:
        numeric = {
            "min_terminal_progress_m": self.min_terminal_progress_m,
            "max_projection_l2": self.max_projection_l2,
            "translation_scale_m": self.translation_scale_m,
            "action_low": self.action_low,
            "action_high": self.action_high,
        }
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not isfinite(float(value))
            for value in numeric.values()
        ):
            raise SemanticProgressProjectionError(
                "projection config values must be finite numbers"
            )
        if (
            self.min_terminal_progress_m <= 0
            or self.max_projection_l2 <= 0
            or self.translation_scale_m <= 0
            or self.action_low >= self.action_high
        ):
            raise SemanticProgressProjectionError(
                "projection config limits are invalid"
            )
        verbs = tuple(self.supported_verbs)
        if (
            not verbs
            or len(verbs) != len(set(verbs))
            or any(not isinstance(verb, str) or not verb for verb in verbs)
        ):
            raise SemanticProgressProjectionError(
                "supported_verbs must be unique non-empty strings"
            )
        object.__setattr__(self, "supported_verbs", verbs)

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "schema": PROJECTION_SCHEMA,
                "min_terminal_progress_m": float(
                    self.min_terminal_progress_m
                ),
                "max_projection_l2": float(self.max_projection_l2),
                "translation_scale_m": float(self.translation_scale_m),
                "action_low": float(self.action_low),
                "action_high": float(self.action_high),
                "supported_verbs": self.supported_verbs,
                "translation_only": True,
                "preserve_rotation_and_gripper_after_envelope": True,
            }
        )


@dataclass(frozen=True)
class SemanticProgressProjection:
    """Auditable result of one fixed-subtask projection attempt."""

    accepted: bool
    projected: bool
    reason: str
    semantic_subtask: str
    observation_digest: str
    command_shape: tuple[int, int]
    nominal_command: tuple[float, ...]
    envelope_command: tuple[float, ...]
    final_command: tuple[float, ...] | None
    nominal_terminal_progress_m: float | None
    final_terminal_progress_m: float | None
    projection_l2: float | None
    config_digest: str
    goal_entity_id: str | None
    witness_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "witness_digest",
            digest_payload(
                {
                    "schema": PROJECTION_SCHEMA,
                    "accepted": self.accepted,
                    "projected": self.projected,
                    "reason": self.reason,
                    "semantic_subtask": self.semantic_subtask,
                    "observation_digest": self.observation_digest,
                    "command_shape": self.command_shape,
                    "nominal_command": self.nominal_command,
                    "envelope_command": self.envelope_command,
                    "final_command": self.final_command,
                    "nominal_terminal_progress_m": (
                        self.nominal_terminal_progress_m
                    ),
                    "final_terminal_progress_m": (
                        self.final_terminal_progress_m
                    ),
                    "projection_l2": self.projection_l2,
                    "config_digest": self.config_digest,
                    "goal_entity_id": self.goal_entity_id,
                }
            ),
        )

    def audit_payload(self) -> dict[str, object]:
        return {
            "schema": PROJECTION_SCHEMA,
            "accepted": self.accepted,
            "projected": self.projected,
            "reason": self.reason,
            "semantic_subtask": self.semantic_subtask,
            "observation_digest": self.observation_digest,
            "command_shape": self.command_shape,
            "nominal_terminal_progress_m": (
                self.nominal_terminal_progress_m
            ),
            "final_terminal_progress_m": self.final_terminal_progress_m,
            "projection_l2": self.projection_l2,
            "config_digest": self.config_digest,
            "goal_entity_id": self.goal_entity_id,
            "witness_digest": self.witness_digest,
        }


def _rejected(
    *,
    reason: str,
    semantic_subtask: str,
    observation: TrustedLocalObservation,
    shape: tuple[int, int],
    nominal: tuple[float, ...],
    envelope: tuple[float, ...],
    config: SemanticProgressProjectionConfig,
    goal_entity_id: str | None = None,
    nominal_progress: float | None = None,
) -> SemanticProgressProjection:
    return SemanticProgressProjection(
        accepted=False,
        projected=False,
        reason=reason,
        semantic_subtask=semantic_subtask,
        observation_digest=observation.observation_digest,
        command_shape=shape,
        nominal_command=nominal,
        envelope_command=envelope,
        final_command=None,
        nominal_terminal_progress_m=nominal_progress,
        final_terminal_progress_m=None,
        projection_l2=None,
        config_digest=config.config_digest,
        goal_entity_id=goal_entity_id,
    )


def project_semantic_progress(
    *,
    semantic_subtask: str,
    observation: TrustedLocalObservation,
    nominal_command: Iterable[float],
    command_shape: Sequence[int],
    config: SemanticProgressProjectionConfig | None = None,
) -> SemanticProgressProjection:
    """Return the exact bounded block or a fail-closed rejection witness."""

    selected_config = config or SemanticProgressProjectionConfig()
    nominal = _finite_tuple(nominal_command, name="nominal_command")
    shape = tuple(command_shape)
    if (
        len(shape) != 2
        or any(type(value) is not int or value <= 0 for value in shape)
        or shape[0] * shape[1] != len(nominal)
        or shape[1] != 7
    ):
        raise SemanticProgressProjectionError(
            "LIBERO command_shape must be (steps, 7)"
        )
    envelope = tuple(
        min(
            max(value, selected_config.action_low),
            selected_config.action_high,
        )
        for value in nominal
    )
    try:
        subtask = parse_semantic_subtask(semantic_subtask)
    except LocalCheckerError as exc:
        return _rejected(
            reason=f"malformed_semantic_subtask:{exc}",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
        )
    if subtask.verb not in selected_config.supported_verbs:
        return _rejected(
            reason=f"unsupported_projection_verb:{subtask.verb}",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
        )
    target = observation.position(subtask.target or "")
    if target is None:
        return _rejected(
            reason="missing_projection_target_geometry",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
            goal_entity_id=subtask.target,
        )
    if subtask.verb == "pick_up":
        mover_start = observation.eef_position
        goal = target
        goal_entity_id = subtask.target
    else:
        destination = observation.position(subtask.destination or "")
        if destination is None:
            return _rejected(
                reason="missing_projection_destination_geometry",
                semantic_subtask=semantic_subtask,
                observation=observation,
                shape=shape,
                nominal=nominal,
                envelope=envelope,
                config=selected_config,
                goal_entity_id=subtask.destination,
            )
        mover_start = target
        goal = destination
        goal_entity_id = subtask.destination
    initial_distance = _distance(mover_start, goal)
    nominal_progress = _terminal_progress(
        mover_start=mover_start,
        goal=goal,
        command=envelope,
        command_shape=shape,
        translation_scale_m=selected_config.translation_scale_m,
    )
    if initial_distance <= selected_config.min_terminal_progress_m:
        return _rejected(
            reason="insufficient_goal_distance_for_progress_projection",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
            goal_entity_id=goal_entity_id,
            nominal_progress=nominal_progress,
        )
    if (
        nominal_progress
        >= selected_config.min_terminal_progress_m - 1.0e-12
    ):
        projection = _l2(nominal, envelope)
        if projection > selected_config.max_projection_l2:
            return _rejected(
                reason="numeric_envelope_exceeds_projection_budget",
                semantic_subtask=semantic_subtask,
                observation=observation,
                shape=shape,
                nominal=nominal,
                envelope=envelope,
                config=selected_config,
                goal_entity_id=goal_entity_id,
                nominal_progress=nominal_progress,
            )
        return SemanticProgressProjection(
            accepted=True,
            projected=envelope != nominal,
            reason=(
                "numeric_envelope_only"
                if envelope != nominal
                else "nominal_terminal_progress_sufficient"
            ),
            semantic_subtask=semantic_subtask,
            observation_digest=observation.observation_digest,
            command_shape=shape,
            nominal_command=nominal,
            envelope_command=envelope,
            final_command=envelope,
            nominal_terminal_progress_m=nominal_progress,
            final_terminal_progress_m=nominal_progress,
            projection_l2=projection,
            config_digest=selected_config.config_digest,
            goal_entity_id=goal_entity_id,
        )

    steps, width = shape
    nominal_displacement = tuple(
        selected_config.translation_scale_m
        * sum(envelope[step * width + axis] for step in range(steps))
        for axis in range(3)
    )
    nominal_terminal = tuple(
        float(mover_start[axis]) + nominal_displacement[axis]
        for axis in range(3)
    )
    terminal_to_goal = tuple(
        nominal_terminal[axis] - float(goal[axis])
        for axis in range(3)
    )
    terminal_distance = _distance(nominal_terminal, goal)
    desired_radius = max(
        0.0,
        initial_distance
        - selected_config.min_terminal_progress_m
        - 1.0e-10,
    )
    if terminal_distance == 0.0:
        desired_terminal = nominal_terminal
    else:
        desired_terminal = tuple(
            float(goal[axis])
            + terminal_to_goal[axis]
            * desired_radius
            / terminal_distance
            for axis in range(3)
        )
    required_normalized = tuple(
        (desired_terminal[axis] - nominal_terminal[axis])
        / selected_config.translation_scale_m
        for axis in range(3)
    )
    offsets_by_axis = []
    for axis in range(3):
        values = tuple(
            envelope[step * width + axis] for step in range(steps)
        )
        offsets = _minimum_l2_bounded_offsets(
            values,
            required_sum=required_normalized[axis],
            lower=selected_config.action_low,
            upper=selected_config.action_high,
        )
        if offsets is None:
            return _rejected(
                reason="action_bounds_make_projection_infeasible",
                semantic_subtask=semantic_subtask,
                observation=observation,
                shape=shape,
                nominal=nominal,
                envelope=envelope,
                config=selected_config,
                goal_entity_id=goal_entity_id,
                nominal_progress=nominal_progress,
            )
        offsets_by_axis.append(offsets)
    final = list(envelope)
    for step in range(steps):
        for axis in range(3):
            final[step * width + axis] += offsets_by_axis[axis][step]
    frozen_final = tuple(final)
    projection = _l2(nominal, frozen_final)
    final_progress = _terminal_progress(
        mover_start=mover_start,
        goal=goal,
        command=frozen_final,
        command_shape=shape,
        translation_scale_m=selected_config.translation_scale_m,
    )
    if projection > selected_config.max_projection_l2 + 1.0e-12:
        return _rejected(
            reason="semantic_projection_budget_exceeded",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
            goal_entity_id=goal_entity_id,
            nominal_progress=nominal_progress,
        )
    if (
        final_progress
        < selected_config.min_terminal_progress_m - 1.0e-9
    ):
        return _rejected(
            reason="projected_terminal_progress_below_threshold",
            semantic_subtask=semantic_subtask,
            observation=observation,
            shape=shape,
            nominal=nominal,
            envelope=envelope,
            config=selected_config,
            goal_entity_id=goal_entity_id,
            nominal_progress=nominal_progress,
        )
    return SemanticProgressProjection(
        accepted=True,
        projected=True,
        reason="minimum_l2_terminal_progress_projection",
        semantic_subtask=semantic_subtask,
        observation_digest=observation.observation_digest,
        command_shape=shape,
        nominal_command=nominal,
        envelope_command=envelope,
        final_command=frozen_final,
        nominal_terminal_progress_m=nominal_progress,
        final_terminal_progress_m=final_progress,
        projection_l2=projection,
        config_digest=selected_config.config_digest,
        goal_entity_id=goal_entity_id,
    )


__all__ = [
    "PROJECTION_SCHEMA",
    "SemanticProgressProjection",
    "SemanticProgressProjectionConfig",
    "SemanticProgressProjectionError",
    "project_semantic_progress",
]
