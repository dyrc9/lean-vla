"""Bind the stateful gripper action accumulator to simulator shadows.

The Panda gripper maps one policy action into a two-actuator command through
``gripper.current_action``.  That value accumulates on every ``env.step`` and
is not part of MuJoCo ``MjSimState`` or the robot arm controller.  A shadow
restore that omits it can therefore report exact simulator/controller/input
identity while replaying a different gripper command.

This versioned wrapper adds only that missing state to the already frozen
warm-start-complete snapshot.  It does not mutate the predecessor module or
claim that every possible environment-side cache is captured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from proofalign.digests import digest_payload
from proofalign.policy_prefix_shadow_warmstart_v12 import (
    WarmstartPolicyShadowRestoreAssessment,
    WarmstartPolicyShadowSnapshot,
    capture_warmstart_policy_shadow_snapshot,
    restore_warmstart_policy_shadow_snapshot,
)
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
)


GRIPPER_STATE_SHADOW_SCHEMA = (
    "proofalign.policy-shadow-gripper-state.v15.4"
)


def _gripper_identity(gripper: Any) -> str:
    cls = type(gripper)
    return f"{cls.__module__}.{cls.__qualname__}"


def _current_action(gripper: Any) -> tuple[float, ...]:
    values = np.asarray(
        getattr(gripper, "current_action", None), dtype=np.float64
    )
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise RecoverableAlignmentV12Error(
            "stateful gripper current_action is unavailable or malformed"
        )
    return tuple(float(value) for value in values)


@dataclass(frozen=True)
class GripperStatePolicyShadowSnapshot:
    """Warm-start snapshot plus the exact gripper action accumulator."""

    base: WarmstartPolicyShadowSnapshot = field(
        repr=False, compare=False
    )
    gripper_class: str
    gripper_current_action: tuple[float, ...]
    source_id: str
    schema: str = GRIPPER_STATE_SHADOW_SCHEMA + ".snapshot"
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.gripper_current_action)
        if (
            not self.gripper_class
            or not self.source_id
            or not values
            or not np.isfinite(np.asarray(values)).all()
        ):
            raise RecoverableAlignmentV12Error(
                "gripper-state snapshot identity is invalid"
            )
        object.__setattr__(self, "gripper_current_action", values)
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "base_snapshot_digest": self.base.snapshot_digest,
                    "gripper_class": self.gripper_class,
                    "gripper_current_action": values,
                    "source_id": self.source_id,
                }
            ),
        )


@dataclass(frozen=True)
class GripperStatePolicyShadowRestoreAssessment:
    """Audit the predecessor restore and the gripper accumulator separately."""

    base: WarmstartPolicyShadowRestoreAssessment = field(
        repr=False, compare=False
    )
    snapshot_digest: str
    gripper_class_identity: bool
    gripper_current_action_identity: bool
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": GRIPPER_STATE_SHADOW_SCHEMA
                    + ".restore-assessment",
                    "base_assessment_digest": self.base.assessment_digest,
                    "snapshot_digest": self.snapshot_digest,
                    "gripper_class_identity": self.gripper_class_identity,
                    "gripper_current_action_identity": (
                        self.gripper_current_action_identity
                    ),
                }
            ),
        )

    @property
    def gripper_state_identity(self) -> bool:
        return bool(
            self.gripper_class_identity
            and self.gripper_current_action_identity
        )

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


def capture_gripper_state_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    *,
    source_id: str,
) -> GripperStatePolicyShadowSnapshot:
    """Capture the frozen warm-start boundary and current gripper command."""

    gripper = getattr(robot, "gripper", None)
    if gripper is None:
        raise RecoverableAlignmentV12Error(
            "gripper-state shadow requires exactly one robot gripper"
        )
    return GripperStatePolicyShadowSnapshot(
        base=capture_warmstart_policy_shadow_snapshot(
            env, robot, source_id=source_id + ":warmstart"
        ),
        gripper_class=_gripper_identity(gripper),
        gripper_current_action=_current_action(gripper),
        source_id=source_id,
    )


def restore_gripper_state_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    snapshot: GripperStatePolicyShadowSnapshot,
) -> GripperStatePolicyShadowRestoreAssessment:
    """Restore the predecessor boundary and exact gripper accumulator."""

    gripper = getattr(robot, "gripper", None)
    if gripper is None:
        raise RecoverableAlignmentV12Error(
            "gripper-state shadow requires exactly one robot gripper"
        )
    class_identity = _gripper_identity(gripper) == snapshot.gripper_class
    if not class_identity:
        raise RecoverableAlignmentV12Error(
            "gripper class differs from gripper-state snapshot"
        )
    base = restore_warmstart_policy_shadow_snapshot(
        env, robot, snapshot.base
    )
    target = np.asarray(
        snapshot.gripper_current_action, dtype=np.float64
    )
    gripper.current_action = target.copy()
    observed = _current_action(gripper)
    return GripperStatePolicyShadowRestoreAssessment(
        base=base,
        snapshot_digest=snapshot.snapshot_digest,
        gripper_class_identity=class_identity,
        gripper_current_action_identity=bool(
            observed == snapshot.gripper_current_action
        ),
    )


__all__ = [
    "GRIPPER_STATE_SHADOW_SCHEMA",
    "GripperStatePolicyShadowRestoreAssessment",
    "GripperStatePolicyShadowSnapshot",
    "capture_gripper_state_policy_shadow_snapshot",
    "restore_gripper_state_policy_shadow_snapshot",
]
