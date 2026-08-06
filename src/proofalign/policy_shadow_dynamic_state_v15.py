"""Bind LIBERO-Safety dynamic-motion phase to policy shadow snapshots.

LIBERO-Safety advances each dynamic obstacle by calling ``next`` on a Python
motion-generator object before every ``env.step``.  MuJoCo mocap inputs are
already restored by the predecessor snapshot, but the generator phase is not
part of MuJoCo state.  Replaying a shadow without this layer therefore moves
the obstacle to a different phase on the next step.

The supported generator classes and their mutable fields are explicit.  An
unknown generator fails closed instead of being silently treated as static.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from proofalign.digests import digest_payload
from proofalign.policy_shadow_gripper_state_v15 import (
    GripperStatePolicyShadowRestoreAssessment,
    GripperStatePolicyShadowSnapshot,
    capture_gripper_state_policy_shadow_snapshot,
    restore_gripper_state_policy_shadow_snapshot,
)
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
)


DYNAMIC_STATE_SHADOW_SCHEMA = (
    "proofalign.policy-shadow-dynamic-state.v15.4"
)
_DYNAMIC_FIELDS = {
    "LinearMotionGenerator": ("pos", "quat", "forward", "step_count"),
    "CircularMotionGenerator": ("angle",),
    "SmoothWaypointMotionGenerator": (
        "direction",
        "seg_idx",
        "step_idx",
        "current_quat",
    ),
    "ParabolicMotionGenerator": ("pos", "quat", "t"),
}


def _unwrapped_env(env: Any) -> Any:
    current = env
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        candidate = getattr(current, "_env", None)
        if candidate is None:
            candidate = getattr(current, "env", None)
        if candidate is None or candidate is current:
            return current
        current = candidate
    raise RecoverableAlignmentV12Error(
        "environment wrapper cycle prevents dynamic-state snapshot"
    )


def _class_identity(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


@dataclass(frozen=True)
class DynamicMotionValue:
    """One finite scalar or array from a supported motion generator."""

    name: str
    kind: str
    dtype: str | None
    shape: tuple[int, ...]
    values: tuple[float | bool, ...]
    value_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in {"array", "bool", "int", "float"}:
            raise RecoverableAlignmentV12Error(
                "unsupported dynamic motion value kind"
            )
        if self.kind == "array":
            if (
                self.dtype is None
                or not self.shape
                or int(np.prod(self.shape)) != len(self.values)
            ):
                raise RecoverableAlignmentV12Error(
                    "dynamic motion array shape differs"
                )
        elif self.dtype is not None or self.shape or len(self.values) != 1:
            raise RecoverableAlignmentV12Error(
                "dynamic motion scalar shape differs"
            )
        if any(
            isinstance(value, float) and not np.isfinite(value)
            for value in self.values
        ):
            raise RecoverableAlignmentV12Error(
                "dynamic motion value must be finite"
            )
        object.__setattr__(
            self,
            "value_digest",
            digest_payload(
                {
                    "schema": DYNAMIC_STATE_SHADOW_SCHEMA + ".value",
                    "name": self.name,
                    "kind": self.kind,
                    "dtype": self.dtype,
                    "shape": self.shape,
                    "values": self.values,
                }
            ),
        )


def _capture_value(name: str, value: Any) -> DynamicMotionValue:
    if isinstance(value, (bool, np.bool_)):
        return DynamicMotionValue(name, "bool", None, (), (bool(value),))
    if isinstance(value, (int, np.integer)):
        return DynamicMotionValue(
            name, "int", None, (), (float(int(value)),)
        )
    if isinstance(value, (float, np.floating)):
        return DynamicMotionValue(
            name, "float", None, (), (float(value),)
        )
    array = np.asarray(value)
    if (
        array.ndim == 0
        or not np.issubdtype(array.dtype, np.number)
        or not np.isfinite(array).all()
    ):
        raise RecoverableAlignmentV12Error(
            f"unsupported dynamic motion state: {name}"
        )
    return DynamicMotionValue(
        name=name,
        kind="array",
        dtype=str(array.dtype),
        shape=tuple(int(item) for item in array.shape),
        values=tuple(
            float(item)
            for item in np.asarray(array, dtype=np.float64).reshape(-1)
        ),
    )


def _restore_value(value: DynamicMotionValue) -> Any:
    if value.kind == "bool":
        return bool(value.values[0])
    if value.kind == "int":
        return int(value.values[0])
    if value.kind == "float":
        return float(value.values[0])
    assert value.dtype is not None
    return np.asarray(value.values, dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True)
class DynamicMotionGeneratorState:
    name: str
    generator_class: str
    values: tuple[DynamicMotionValue, ...]
    state_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.name or not self.generator_class or not self.values:
            raise RecoverableAlignmentV12Error(
                "dynamic motion generator state is incomplete"
            )
        object.__setattr__(
            self,
            "state_digest",
            digest_payload(
                {
                    "schema": DYNAMIC_STATE_SHADOW_SCHEMA + ".generator",
                    "name": self.name,
                    "generator_class": self.generator_class,
                    "values": tuple(
                        value.value_digest for value in self.values
                    ),
                }
            ),
        )


def _generator_states(env: Any) -> tuple[DynamicMotionGeneratorState, ...]:
    raw = _unwrapped_env(env)
    generators = getattr(raw, "mocap_motion_generators", {})
    if not isinstance(generators, Mapping):
        raise RecoverableAlignmentV12Error(
            "dynamic motion generator registry is malformed"
        )
    states = []
    for name in sorted(generators):
        generator = generators[name]
        class_name = type(generator).__name__
        fields = _DYNAMIC_FIELDS.get(class_name)
        if fields is None:
            raise RecoverableAlignmentV12Error(
                f"unsupported dynamic motion generator: {class_name}"
            )
        values = tuple(
            _capture_value(field_name, getattr(generator, field_name))
            for field_name in fields
        )
        states.append(
            DynamicMotionGeneratorState(
                name=str(name),
                generator_class=_class_identity(generator),
                values=values,
            )
        )
    return tuple(states)


@dataclass(frozen=True)
class DynamicStatePolicyShadowSnapshot:
    base: GripperStatePolicyShadowSnapshot = field(
        repr=False, compare=False
    )
    motion_generators: tuple[DynamicMotionGeneratorState, ...]
    source_id: str
    schema: str = DYNAMIC_STATE_SHADOW_SCHEMA + ".snapshot"
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.source_id:
            raise RecoverableAlignmentV12Error(
                "dynamic-state snapshot source is empty"
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "base_snapshot_digest": self.base.snapshot_digest,
                    "motion_generators": tuple(
                        state.state_digest for state in self.motion_generators
                    ),
                    "source_id": self.source_id,
                }
            ),
        )


@dataclass(frozen=True)
class DynamicStatePolicyShadowRestoreAssessment:
    base: GripperStatePolicyShadowRestoreAssessment = field(
        repr=False, compare=False
    )
    snapshot_digest: str
    dynamic_motion_generator_count: int
    dynamic_motion_registry_identity: bool
    dynamic_motion_state_identity: bool
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.dynamic_motion_generator_count < 0:
            raise RecoverableAlignmentV12Error(
                "dynamic motion generator count cannot be negative"
            )
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": DYNAMIC_STATE_SHADOW_SCHEMA
                    + ".restore-assessment",
                    "base_assessment_digest": self.base.assessment_digest,
                    "snapshot_digest": self.snapshot_digest,
                    "dynamic_motion_generator_count": (
                        self.dynamic_motion_generator_count
                    ),
                    "dynamic_motion_registry_identity": (
                        self.dynamic_motion_registry_identity
                    ),
                    "dynamic_motion_state_identity": (
                        self.dynamic_motion_state_identity
                    ),
                }
            ),
        )

    @property
    def runtime_side_state_identity(self) -> bool:
        return bool(
            self.base.gripper_state_identity
            and self.dynamic_motion_registry_identity
            and self.dynamic_motion_state_identity
        )

    @property
    def gripper_state_identity(self) -> bool:
        return self.base.gripper_state_identity

    @property
    def full_simulator_state_bitwise_identity(self) -> bool:
        return self.base.full_simulator_state_bitwise_identity

    @property
    def trusted_arm_bitwise_identity(self) -> bool:
        return self.base.trusted_arm_bitwise_identity

    @property
    def controller_state_identity(self) -> bool:
        return self.base.controller_state_identity

    @property
    def simulator_input_identity(self) -> bool:
        return self.base.simulator_input_identity

    @property
    def environment_clock_identity(self) -> bool:
        return self.base.environment_clock_identity

    @property
    def qacc_warmstart_identity(self) -> bool:
        return self.base.qacc_warmstart_identity

    @property
    def full_simulator_state_max_abs_error(self) -> float:
        return self.base.full_simulator_state_max_abs_error

    @property
    def full_simulator_state_differing_value_count(self) -> int:
        return self.base.full_simulator_state_differing_value_count


def capture_dynamic_state_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    *,
    source_id: str,
) -> DynamicStatePolicyShadowSnapshot:
    return DynamicStatePolicyShadowSnapshot(
        base=capture_gripper_state_policy_shadow_snapshot(
            env, robot, source_id=source_id + ":gripper"
        ),
        motion_generators=_generator_states(env),
        source_id=source_id,
    )


def restore_dynamic_state_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    snapshot: DynamicStatePolicyShadowSnapshot,
) -> DynamicStatePolicyShadowRestoreAssessment:
    base = restore_gripper_state_policy_shadow_snapshot(
        env, robot, snapshot.base
    )
    raw = _unwrapped_env(env)
    generators = getattr(raw, "mocap_motion_generators", {})
    expected_names = tuple(state.name for state in snapshot.motion_generators)
    observed_names = tuple(sorted(generators))
    registry_identity = expected_names == observed_names
    if not registry_identity:
        raise RecoverableAlignmentV12Error(
            "dynamic motion generator registry differs from snapshot"
        )
    for state in snapshot.motion_generators:
        generator = generators[state.name]
        if _class_identity(generator) != state.generator_class:
            raise RecoverableAlignmentV12Error(
                "dynamic motion generator class differs from snapshot"
            )
        for value in state.values:
            setattr(generator, value.name, _restore_value(value))
    observed = _generator_states(env)
    state_identity = observed == snapshot.motion_generators
    return DynamicStatePolicyShadowRestoreAssessment(
        base=base,
        snapshot_digest=snapshot.snapshot_digest,
        dynamic_motion_generator_count=len(snapshot.motion_generators),
        dynamic_motion_registry_identity=registry_identity,
        dynamic_motion_state_identity=state_identity,
    )


__all__ = [
    "DYNAMIC_STATE_SHADOW_SCHEMA",
    "DynamicMotionGeneratorState",
    "DynamicMotionValue",
    "DynamicStatePolicyShadowRestoreAssessment",
    "DynamicStatePolicyShadowSnapshot",
    "capture_dynamic_state_policy_shadow_snapshot",
    "restore_dynamic_state_policy_shadow_snapshot",
]
