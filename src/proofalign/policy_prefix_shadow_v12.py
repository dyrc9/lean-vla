"""Bound policy-prefix shadow decisions and controller-aware snapshots.

The v12.3 simulator snapshot separates trusted arm state from unrelated
MuJoCo diagnostic values.  A nominal policy-prefix shadow needs one additional
boundary: restoring only ``MjSimState`` is insufficient when the robot
controller retains goals or cached update state from a prior probe.

This module therefore provides:

* a pure, digest-bound decision over one trusted joint state and one exact
  policy ActionBlock trajectory;
* an explicit snapshot of simulator, controller, simulator-input, and
  environment-clock state for read-only policy-prefix probes.

It does not load a policy, step an environment, dispatch an action, or read a
task outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Iterable

import numpy as np

from proofalign.digests import digest_payload
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
    ShadowJointAssessment,
    ShadowJointTrajectory,
    TrustedJointState,
    assess_shadow_joint_trajectory,
)
from proofalign.simulator_snapshot_v12 import (
    SimulatorSnapshot,
    capture_simulator_snapshot,
)


POLICY_PREFIX_SHADOW_SCHEMA = "proofalign.policy-prefix-shadow.v12.4"
_CONTROLLER_FIELDS = (
    "action_scale",
    "action_input_transform",
    "action_output_transform",
    "ee_pos",
    "ee_ori_mat",
    "ee_pos_vel",
    "ee_ori_vel",
    "joint_pos",
    "joint_vel",
    "J_pos",
    "J_ori",
    "J_full",
    "mass_matrix",
    "torques",
    "initial_joint",
    "initial_ee_pos",
    "initial_ee_ori_mat",
    "goal_pos",
    "goal_ori",
    "relative_ori",
    "ori_ref",
    "kp",
    "kd",
    "new_update",
)
_SIMULATOR_INPUT_FIELDS = (
    "ctrl",
    "qfrc_applied",
    "xfrc_applied",
    "mocap_pos",
    "mocap_quat",
)


class PolicyPrefixShadowVerdict(str, Enum):
    """Allowed transitions at the pre-dispatch policy-prefix boundary."""

    ALLOW_EXACT = "allow_exact"
    BLOCK_REPLAN = "block_replan"
    RECOVERY_REQUIRED = "recovery_required"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PolicyPrefixShadowDecision:
    """One exact policy-prefix decision bound to state and trajectory bytes."""

    verdict: PolicyPrefixShadowVerdict
    current_state_triggered: bool
    risk_predicted: bool
    initial_state_digest: str
    action_block_digest: str
    trajectory_digest: str
    assessment_digest: str
    authorized_action_block_digest: str | None
    issues: tuple[str, ...]
    schema: str = POLICY_PREFIX_SHADOW_SCHEMA + ".decision"
    decision_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema != POLICY_PREFIX_SHADOW_SCHEMA + ".decision":
            raise RecoverableAlignmentV12Error(
                "unsupported policy-prefix decision schema"
            )
        if self.verdict is PolicyPrefixShadowVerdict.ALLOW_EXACT:
            if (
                self.risk_predicted
                or self.current_state_triggered
                or self.authorized_action_block_digest
                != self.action_block_digest
            ):
                raise RecoverableAlignmentV12Error(
                    "allow-exact must preserve a non-risk prefix digest"
                )
        elif self.authorized_action_block_digest is not None:
            raise RecoverableAlignmentV12Error(
                "blocked policy prefixes cannot be authorized"
            )
        if (
            self.verdict is PolicyPrefixShadowVerdict.UNKNOWN
            and not self.issues
        ):
            raise RecoverableAlignmentV12Error(
                "unknown policy-prefix decision requires an issue"
            )
        object.__setattr__(
            self,
            "decision_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "verdict": self.verdict.value,
                    "current_state_triggered": (
                        self.current_state_triggered
                    ),
                    "risk_predicted": self.risk_predicted,
                    "initial_state_digest": self.initial_state_digest,
                    "action_block_digest": self.action_block_digest,
                    "trajectory_digest": self.trajectory_digest,
                    "assessment_digest": self.assessment_digest,
                    "authorized_action_block_digest": (
                        self.authorized_action_block_digest
                    ),
                    "issues": self.issues,
                }
            ),
        )


def decide_policy_prefix_shadow(
    state: TrustedJointState,
    trajectory: ShadowJointTrajectory,
    *,
    trigger_margin_rad: float = 0.1,
) -> tuple[PolicyPrefixShadowDecision, ShadowJointAssessment]:
    """Classify an exact source prefix without modifying its command bytes."""

    assessment = assess_shadow_joint_trajectory(
        state,
        trajectory,
        trigger_margin_rad=trigger_margin_rad,
    )
    current_triggered = state.minimum_margin <= trigger_margin_rad
    if not assessment.known:
        verdict = PolicyPrefixShadowVerdict.UNKNOWN
        authorized = None
    elif current_triggered:
        verdict = PolicyPrefixShadowVerdict.RECOVERY_REQUIRED
        authorized = None
    elif assessment.risk_predicted:
        verdict = PolicyPrefixShadowVerdict.BLOCK_REPLAN
        authorized = None
    else:
        verdict = PolicyPrefixShadowVerdict.ALLOW_EXACT
        authorized = trajectory.action_block_digest
    return (
        PolicyPrefixShadowDecision(
            verdict=verdict,
            current_state_triggered=current_triggered,
            risk_predicted=assessment.risk_predicted,
            initial_state_digest=state.state_digest,
            action_block_digest=trajectory.action_block_digest,
            trajectory_digest=trajectory.trajectory_digest,
            assessment_digest=assessment.assessment_digest,
            authorized_action_block_digest=authorized,
            issues=assessment.issues,
        ),
        assessment,
    )


@dataclass(frozen=True)
class NumericStateValue:
    """Canonical numeric/boolean/None value used by runtime snapshots."""

    name: str
    kind: str
    dtype: str | None
    shape: tuple[int, ...]
    values: tuple[float | bool, ...]
    value_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise RecoverableAlignmentV12Error(
                "snapshot value name must be non-empty"
            )
        if self.kind not in {"none", "array", "bool", "int", "float"}:
            raise RecoverableAlignmentV12Error(
                f"unsupported snapshot value kind: {self.kind}"
            )
        if self.kind == "none":
            if self.dtype is not None or self.shape or self.values:
                raise RecoverableAlignmentV12Error(
                    "None snapshot value has payload"
                )
        elif self.kind == "array":
            if self.dtype is None or not self.shape:
                raise RecoverableAlignmentV12Error(
                    "array snapshot value lacks dtype or shape"
                )
            if int(np.prod(self.shape)) != len(self.values):
                raise RecoverableAlignmentV12Error(
                    "array snapshot shape differs from values"
                )
        elif self.shape or len(self.values) != 1:
            raise RecoverableAlignmentV12Error(
                "scalar snapshot value has invalid shape"
            )
        if any(
            isinstance(value, float) and not isfinite(value)
            for value in self.values
        ):
            raise RecoverableAlignmentV12Error(
                "snapshot value must be finite"
            )
        object.__setattr__(
            self,
            "value_digest",
            digest_payload(
                {
                    "schema": POLICY_PREFIX_SHADOW_SCHEMA + ".value",
                    "name": self.name,
                    "kind": self.kind,
                    "dtype": self.dtype,
                    "shape": self.shape,
                    "values": self.values,
                }
            ),
        )


def _capture_value(name: str, value: Any) -> NumericStateValue:
    if value is None:
        return NumericStateValue(name, "none", None, (), ())
    if isinstance(value, (bool, np.bool_)):
        return NumericStateValue(
            name, "bool", None, (), (bool(value),)
        )
    if isinstance(value, (int, np.integer)):
        return NumericStateValue(
            name, "int", None, (), (float(int(value)),)
        )
    if isinstance(value, (float, np.floating)):
        return NumericStateValue(
            name, "float", None, (), (float(value),)
        )
    array = np.asarray(value)
    if (
        array.ndim == 0
        or not np.issubdtype(array.dtype, np.number)
        or not np.isfinite(array).all()
    ):
        raise RecoverableAlignmentV12Error(
            f"unsupported controller snapshot value: {name}"
        )
    return NumericStateValue(
        name=name,
        kind="array",
        dtype=str(array.dtype),
        shape=tuple(int(item) for item in array.shape),
        values=tuple(
            float(item)
            for item in np.asarray(array, dtype=np.float64).reshape(-1)
        ),
    )


def _restore_value(value: NumericStateValue) -> Any:
    if value.kind == "none":
        return None
    if value.kind == "bool":
        return bool(value.values[0])
    if value.kind == "int":
        return int(value.values[0])
    if value.kind == "float":
        return float(value.values[0])
    assert value.dtype is not None
    return np.asarray(value.values, dtype=value.dtype).reshape(value.shape)


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
        "environment wrapper cycle prevents snapshot"
    )


@dataclass(frozen=True)
class PolicyShadowRuntimeSnapshot:
    """Complete state required to replay a policy prefix read-only.

    Cached controller kinematics are included deliberately. Restoring
    ``new_update=False`` without the corresponding cached end-effector,
    Jacobian, mass-matrix, and joint values would make the first control
    substep reuse terminal values from the preceding shadow probe.
    """

    simulator: SimulatorSnapshot = field(repr=False, compare=False)
    controller_class: str
    controller_values: tuple[NumericStateValue, ...]
    simulator_inputs: tuple[NumericStateValue, ...]
    environment_clock: tuple[NumericStateValue, ...]
    source_id: str
    schema: str = POLICY_PREFIX_SHADOW_SCHEMA + ".runtime-snapshot"
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.controller_class or not self.source_id:
            raise RecoverableAlignmentV12Error(
                "runtime snapshot identity must be non-empty"
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "simulator_snapshot_digest": (
                        self.simulator.snapshot_digest
                    ),
                    "controller_class": self.controller_class,
                    "controller_values": tuple(
                        value.value_digest
                        for value in self.controller_values
                    ),
                    "simulator_inputs": tuple(
                        value.value_digest
                        for value in self.simulator_inputs
                    ),
                    "environment_clock": tuple(
                        value.value_digest
                        for value in self.environment_clock
                    ),
                    "source_id": self.source_id,
                }
            ),
        )


@dataclass(frozen=True)
class PolicyShadowRestoreAssessment:
    snapshot_digest: str
    full_simulator_state_bitwise_identity: bool
    trusted_arm_bitwise_identity: bool
    controller_state_identity: bool
    simulator_input_identity: bool
    environment_clock_identity: bool
    full_simulator_state_max_abs_error: float
    full_simulator_state_differing_value_count: int
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": POLICY_PREFIX_SHADOW_SCHEMA
                    + ".restore-assessment",
                    **{
                        name: getattr(self, name)
                        for name in (
                            "snapshot_digest",
                            "full_simulator_state_bitwise_identity",
                            "trusted_arm_bitwise_identity",
                            "controller_state_identity",
                            "simulator_input_identity",
                            "environment_clock_identity",
                            "full_simulator_state_max_abs_error",
                            "full_simulator_state_differing_value_count",
                        )
                    },
                }
            ),
        )


def _controller_identity(controller: Any) -> str:
    cls = type(controller)
    return f"{cls.__module__}.{cls.__qualname__}"


def capture_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    *,
    source_id: str,
) -> PolicyShadowRuntimeSnapshot:
    """Capture the state required for a deterministic policy-prefix probe."""

    controller = robot.controller
    if (
        getattr(controller, "interpolator_pos", None) is not None
        or getattr(controller, "interpolator_ori", None) is not None
    ):
        raise RecoverableAlignmentV12Error(
            "interpolated controllers require a separately qualified snapshot"
        )
    qpos_indexes = tuple(
        int(value) for value in robot._ref_joint_pos_indexes
    )
    qvel_indexes = tuple(
        int(value) for value in robot._ref_joint_vel_indexes
    )
    simulator = capture_simulator_snapshot(
        env,
        arm_qpos_indexes=qpos_indexes,
        arm_qvel_indexes=qvel_indexes,
        source_id=source_id + ":simulator",
    )
    controller_values = tuple(
        _capture_value(name, getattr(controller, name))
        for name in _CONTROLLER_FIELDS
    )
    simulator_inputs = tuple(
        _capture_value(name, getattr(env.sim.data, name))
        for name in _SIMULATOR_INPUT_FIELDS
    )
    raw = _unwrapped_env(env)
    environment_clock = tuple(
        _capture_value(name, getattr(raw, name))
        for name in ("timestep", "cur_time", "done")
    )
    return PolicyShadowRuntimeSnapshot(
        simulator=simulator,
        controller_class=_controller_identity(controller),
        controller_values=controller_values,
        simulator_inputs=simulator_inputs,
        environment_clock=environment_clock,
        source_id=source_id,
    )


def _values_equal(
    expected: Iterable[NumericStateValue],
    observed: Iterable[NumericStateValue],
) -> bool:
    return tuple(expected) == tuple(observed)


def restore_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    snapshot: PolicyShadowRuntimeSnapshot,
) -> PolicyShadowRestoreAssessment:
    """Restore simulator, controller, input, and environment-clock state."""

    controller = robot.controller
    if _controller_identity(controller) != snapshot.controller_class:
        raise RecoverableAlignmentV12Error(
            "controller class differs from policy-shadow snapshot"
        )
    env.sim.set_state(snapshot.simulator.state)
    for value in snapshot.simulator_inputs:
        target = getattr(env.sim.data, value.name)
        target[...] = _restore_value(value)
    env.sim.forward()
    for value in snapshot.controller_values:
        setattr(controller, value.name, _restore_value(value))
    raw = _unwrapped_env(env)
    for value in snapshot.environment_clock:
        setattr(raw, value.name, _restore_value(value))

    observed_flat = np.asarray(
        env.sim.get_state().flatten(), dtype=np.float64
    )
    expected_flat = np.asarray(
        snapshot.simulator.flat_state, dtype=np.float64
    )
    if observed_flat.shape != expected_flat.shape:
        raise RecoverableAlignmentV12Error(
            "restored policy-shadow simulator shape differs"
        )
    observed_qpos = tuple(
        float(value)
        for value in env.sim.data.qpos[
            list(snapshot.simulator.arm_qpos_indexes)
        ]
    )
    observed_qvel = tuple(
        float(value)
        for value in env.sim.data.qvel[
            list(snapshot.simulator.arm_qvel_indexes)
        ]
    )
    observed_controller = tuple(
        _capture_value(value.name, getattr(controller, value.name))
        for value in snapshot.controller_values
    )
    observed_inputs = tuple(
        _capture_value(value.name, getattr(env.sim.data, value.name))
        for value in snapshot.simulator_inputs
    )
    observed_clock = tuple(
        _capture_value(value.name, getattr(raw, value.name))
        for value in snapshot.environment_clock
    )
    differences = np.abs(observed_flat - expected_flat)
    return PolicyShadowRestoreAssessment(
        snapshot_digest=snapshot.snapshot_digest,
        full_simulator_state_bitwise_identity=bool(
            np.array_equal(observed_flat, expected_flat)
        ),
        trusted_arm_bitwise_identity=(
            observed_qpos == snapshot.simulator.arm_qpos
            and observed_qvel == snapshot.simulator.arm_qvel
        ),
        controller_state_identity=_values_equal(
            snapshot.controller_values, observed_controller
        ),
        simulator_input_identity=_values_equal(
            snapshot.simulator_inputs, observed_inputs
        ),
        environment_clock_identity=_values_equal(
            snapshot.environment_clock, observed_clock
        ),
        full_simulator_state_max_abs_error=float(
            np.max(differences)
        ),
        full_simulator_state_differing_value_count=int(
            np.count_nonzero(observed_flat != expected_flat)
        ),
    )


__all__ = [
    "POLICY_PREFIX_SHADOW_SCHEMA",
    "NumericStateValue",
    "PolicyPrefixShadowDecision",
    "PolicyPrefixShadowVerdict",
    "PolicyShadowRestoreAssessment",
    "PolicyShadowRuntimeSnapshot",
    "capture_policy_shadow_snapshot",
    "decide_policy_prefix_shadow",
    "restore_policy_shadow_snapshot",
]
