"""Analytic post-prefix semantic effect observer for integrity v4.

The observer compares two trusted geometry snapshots that bound one completed
prefix.  It does not consume reward, task success, policy logits, or future
episode outcomes.  Missing geometry and unsupported articulation state fail
closed as unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Iterable, Sequence

from proofalign.digests import digest_payload
from proofalign.semantic_local_checker import (
    LocalCheckerError,
    ParsedSemanticSubtask,
    TrustedLocalObservation,
    parse_semantic_subtask,
)


EFFECT_OBSERVER_ID = "proofalign-libero-analytic-effect-observer"
EFFECT_OBSERVER_VERSION = "2"


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
class SemanticEffectObserverConfig:
    target_neighborhood_m: float = 0.10
    held_neighborhood_m: float = 0.12
    destination_xy_neighborhood_m: float = 0.15
    destination_3d_neighborhood_m: float = 0.16
    min_progress_m: float = 0.002
    gripper_closed_qpos_max: float = 0.025
    gripper_open_qpos_min: float = 0.03
    workspace_low: tuple[float, float, float] = (-1.0, -1.0, 0.0)
    workspace_high: tuple[float, float, float] = (1.0, 1.0, 1.5)

    def __post_init__(self) -> None:
        for name in (
            "target_neighborhood_m",
            "held_neighborhood_m",
            "destination_xy_neighborhood_m",
            "destination_3d_neighborhood_m",
            "min_progress_m",
            "gripper_closed_qpos_max",
            "gripper_open_qpos_min",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(float(value))
                or float(value) <= 0
            ):
                raise ValueError(f"{name} must be positive and finite")
        for name in ("workspace_low", "workspace_high"):
            values = tuple(float(value) for value in getattr(self, name))
            if len(values) != 3 or any(
                not isfinite(value) for value in values
            ):
                raise ValueError(f"{name} must contain three finite values")
            object.__setattr__(self, name, values)
        if any(
            low >= high
            for low, high in zip(
                self.workspace_low,
                self.workspace_high,
                strict=True,
            )
        ):
            raise ValueError("workspace bounds must be ordered")
        if self.gripper_open_qpos_min <= self.gripper_closed_qpos_max:
            raise ValueError(
                "gripper open and closed thresholds must have a gap"
            )

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "observer_id": EFFECT_OBSERVER_ID,
                "observer_version": EFFECT_OBSERVER_VERSION,
                **self.__dict__,
            }
        )


@dataclass(frozen=True)
class SemanticEffectObservation:
    known: bool
    observed_effect_atoms: tuple[str, ...]
    observed_violation_atoms: tuple[str, ...]
    progress_margin: float | None
    unknown_reason: str | None = None

    def __post_init__(self) -> None:
        effects = tuple(dict.fromkeys(self.observed_effect_atoms))
        violations = tuple(dict.fromkeys(self.observed_violation_atoms))
        object.__setattr__(self, "observed_effect_atoms", effects)
        object.__setattr__(self, "observed_violation_atoms", violations)
        if self.known:
            if self.unknown_reason is not None:
                raise ValueError(
                    "known effect observation cannot have unknown_reason"
                )
            if self.progress_margin is not None and not isfinite(
                float(self.progress_margin)
            ):
                raise ValueError("progress_margin must be finite")
        else:
            if not self.unknown_reason:
                raise ValueError(
                    "unknown effect observation requires unknown_reason"
                )
            if effects or violations or self.progress_margin is not None:
                raise ValueError(
                    "unknown effect observation cannot assert observations"
                )


class SemanticPrefixEffectObserver:
    """Observe transport-skill effects from a bound before/after window."""

    def __init__(
        self,
        config: SemanticEffectObserverConfig | None = None,
    ) -> None:
        self.config = config or SemanticEffectObserverConfig()

    def observe(
        self,
        *,
        semantic_subtask: str,
        before: TrustedLocalObservation,
        after: TrustedLocalObservation,
        prefix_complete: bool,
        release_destination: str | None = None,
        trusted_violation_atoms: Iterable[str] = (),
    ) -> SemanticEffectObservation:
        if type(prefix_complete) is not bool:
            raise TypeError("prefix_complete must be bool")
        if not prefix_complete:
            return self._unknown("authorized_prefix_incomplete")
        if after.state_epoch != before.state_epoch + 1:
            return self._unknown("effect_observation_epoch_mismatch")
        try:
            parsed = parse_semantic_subtask(semantic_subtask)
        except LocalCheckerError as exc:
            return self._unknown(
                f"malformed_semantic_subtask:{exc}"
            )
        if parsed.verb in {"open", "close", "actuate"}:
            return self._unknown(
                "trusted_articulation_effect_state_unavailable"
            )
        if parsed.verb == "finish":
            return self._unknown("finish_has_no_executable_effect")

        target_before = before.position(parsed.target or "")
        target_after = after.position(parsed.target or "")
        if target_before is None or target_after is None:
            return self._unknown("missing_target_effect_geometry")
        destination_id = parsed.destination or release_destination
        destination_before = (
            before.position(destination_id) if destination_id else None
        )
        destination_after = (
            after.position(destination_id) if destination_id else None
        )
        if (
            parsed.verb in {"move", "place", "release"}
            and (
                destination_before is None
                or destination_after is None
            )
        ):
            return self._unknown(
                "missing_destination_effect_geometry"
            )

        violations = list(
            dict.fromkeys(str(atom) for atom in trusted_violation_atoms)
        )
        if any(
            value < low or value > high
            for value, low, high in zip(
                after.eef_position,
                self.config.workspace_low,
                self.config.workspace_high,
                strict=True,
            )
        ):
            violations.append("workspace_exit")
        effects = ["command_applied"]
        progress: float | None = None

        if parsed.verb == "pick_up":
            progress = _distance(
                before.eef_position,
                target_before,
            ) - _distance(after.eef_position, target_after)
            near = (
                _distance(after.eef_position, target_after)
                <= self.config.target_neighborhood_m
            )
            held = self._held(after, target_after)
            if progress >= self.config.min_progress_m:
                effects.append("closer_to_target")
            if near:
                effects.append("near_target")
            if held:
                effects.append("holding_target")
        elif parsed.verb == "move":
            assert destination_before is not None
            assert destination_after is not None
            progress = _distance(
                target_before,
                destination_before,
            ) - _distance(target_after, destination_after)
            if progress >= self.config.min_progress_m:
                effects.append("closer_to_destination")
            if not self._held(after, target_after):
                violations.append("target_not_held_after_move")
        elif parsed.verb == "place":
            assert destination_before is not None
            assert destination_after is not None
            progress = _distance(
                target_before,
                destination_before,
            ) - _distance(target_after, destination_after)
            in_region = (
                _xy_distance(target_after, destination_after)
                <= self.config.destination_xy_neighborhood_m
                and _distance(target_after, destination_after)
                <= self.config.destination_3d_neighborhood_m
            )
            if in_region:
                effects.append("target_in_place_region")
        else:
            assert destination_after is not None
            open_gripper = (
                after.gripper_closedness
                >= self.config.gripper_open_qpos_min
            )
            target_in_region = (
                _distance(target_after, destination_after)
                <= self.config.destination_3d_neighborhood_m
            )
            progress = (
                self.config.destination_3d_neighborhood_m
                - _distance(target_after, destination_after)
            )
            if open_gripper:
                effects.append("gripper_open")
            if open_gripper and target_in_region:
                effects.append("target_released")

        return SemanticEffectObservation(
            known=True,
            observed_effect_atoms=tuple(effects),
            observed_violation_atoms=tuple(
                dict.fromkeys(violations)
            ),
            progress_margin=progress,
        )

    def _held(
        self,
        observation: TrustedLocalObservation,
        target: Sequence[float],
    ) -> bool:
        return (
            observation.gripper_closedness
            <= self.config.gripper_closed_qpos_max
            and _distance(observation.eef_position, target)
            <= self.config.held_neighborhood_m
        )

    @staticmethod
    def _unknown(reason: str) -> SemanticEffectObservation:
        return SemanticEffectObservation(
            known=False,
            observed_effect_atoms=(),
            observed_violation_atoms=(),
            progress_margin=None,
            unknown_reason=reason,
        )


__all__ = [
    "EFFECT_OBSERVER_ID",
    "EFFECT_OBSERVER_VERSION",
    "SemanticEffectObservation",
    "SemanticEffectObserverConfig",
    "SemanticPrefixEffectObserver",
]
