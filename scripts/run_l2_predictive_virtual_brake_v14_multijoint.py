#!/usr/bin/env python3
"""All-arm predictive simulator virtual brake with 14-side auditing.

This v14 engineering successor generalizes the v13 single joint/side
mechanism.  Every L2 policy action is shadowed once, and lower/upper margins
for all seven arm joints are recorded.  If any current or predicted side is
inside the frozen trigger margin, all independently at-risk joints are
guarded together.  Uniform guard margins are evaluated from weakest to
strongest, and a candidate is eligible only when the global seven-joint
minimum remains above the frozen floor.

The source policy action is never changed.  The mechanism remains a MuJoCo
simulator virtual stop, not an actuator-authority or hardware-safety claim.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sys
from time import perf_counter
from types import MethodType
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v13 as core  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v13_fresh3 as fresh3  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v14_multijoint"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v14.multijoint.step"
)
JOINT_COUNT = 7
JOINT_SIDES = ("lower", "upper")
# Compatibility fields used by the inherited v13 outcome analyzer.  A v14
# episode has no distinguished target joint or side; protocol-level checks
# additionally require the explicit fourteen-side scope metadata below.
TARGET_JOINT_INDEX = None
TARGET_JOINT_SIDE = None
BRAKE_MARGINS_RAD = core.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = core.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = core.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLREF = core.GUARD_SOLREF
GUARD_SOLIMP = core.GUARD_SOLIMP


class PredictiveVirtualBrakeV14Error(RuntimeError):
    """Raised when the multi-joint brake cannot remain auditable."""


@dataclass(frozen=True)
class MultiJointBrakeConfig:
    """Frozen all-arm virtual-stop configuration."""

    joint_indices: tuple[int, ...] = tuple(range(JOINT_COUNT))
    trigger_margin_rad: float = TRIGGER_MARGIN_RAD
    safe_margin_floor_rad: float = SAFE_MARGIN_FLOOR_RAD
    guard_margins_rad: tuple[float, ...] = BRAKE_MARGINS_RAD
    guard_solref: tuple[float, float] = GUARD_SOLREF
    guard_solimp: tuple[float, float, float, float, float] = GUARD_SOLIMP

    def __post_init__(self) -> None:
        if (
            self.joint_indices != tuple(range(JOINT_COUNT))
            or not np.isfinite(self.trigger_margin_rad)
            or not np.isfinite(self.safe_margin_floor_rad)
            or self.trigger_margin_rad <= 0
            or self.safe_margin_floor_rad < 0
            or tuple(sorted(set(self.guard_margins_rad)))
            != self.guard_margins_rad
            or any(
                not np.isfinite(value)
                or value <= self.safe_margin_floor_rad
                for value in self.guard_margins_rad
            )
            or len(self.guard_solref) != 2
            or len(self.guard_solimp) != 5
            or any(
                not np.isfinite(value)
                for value in (
                    *self.guard_solref,
                    *self.guard_solimp,
                )
            )
        ):
            raise ValueError("invalid multi-joint brake configuration")


def _joint_side_margins(
    qpos: np.ndarray,
    limits: np.ndarray,
) -> np.ndarray:
    positions = np.asarray(qpos, dtype=np.float64).reshape(-1)
    bounds = np.asarray(limits, dtype=np.float64)
    if (
        positions.shape != (JOINT_COUNT,)
        or bounds.shape != (JOINT_COUNT, 2)
        or not np.isfinite(positions).all()
        or not np.isfinite(bounds).all()
        or np.any(bounds[:, 0] >= bounds[:, 1])
    ):
        raise PredictiveVirtualBrakeV14Error(
            "invalid seven-joint state or limits"
        )
    return np.column_stack(
        (
            positions - bounds[:, 0],
            bounds[:, 1] - positions,
        )
    )


def _margin_rows(margins: np.ndarray) -> list[dict[str, Any]]:
    values = np.asarray(margins, dtype=np.float64)
    if values.shape != (JOINT_COUNT, 2):
        raise PredictiveVirtualBrakeV14Error(
            "invalid joint-side margin matrix"
        )
    return [
        {
            "joint_index": joint_index,
            "lower_margin_rad": float(values[joint_index, 0]),
            "upper_margin_rad": float(values[joint_index, 1]),
        }
        for joint_index in range(JOINT_COUNT)
    ]


def _risk_sides(
    current: np.ndarray,
    predicted: np.ndarray,
    *,
    trigger_margin_rad: float,
) -> list[dict[str, Any]]:
    current_values = np.asarray(current, dtype=np.float64)
    predicted_values = np.asarray(predicted, dtype=np.float64)
    if (
        current_values.shape != (JOINT_COUNT, 2)
        or predicted_values.shape != (JOINT_COUNT, 2)
    ):
        raise PredictiveVirtualBrakeV14Error(
            "invalid risk-side margin matrices"
        )
    rows = []
    for joint_index in range(JOINT_COUNT):
        eligible = []
        for side_index, side in enumerate(JOINT_SIDES):
            current_margin = float(
                current_values[joint_index, side_index]
            )
            predicted_margin = float(
                predicted_values[joint_index, side_index]
            )
            if (
                current_margin <= trigger_margin_rad
                or predicted_margin < trigger_margin_rad
            ):
                eligible.append(
                    {
                        "joint_index": joint_index,
                        "side": side,
                        "current_margin_rad": current_margin,
                        "predicted_margin_rad": predicted_margin,
                        "risk_margin_rad": min(
                            current_margin,
                            predicted_margin,
                        ),
                    }
                )
        if eligible:
            # A physically valid joint cannot be near both sides at the
            # frozen margin.  Retaining the lower score also fails closed
            # for synthetic narrow-range tests.
            rows.append(
                min(
                    eligible,
                    key=lambda row: (
                        row["risk_margin_rad"],
                        row["side"],
                    ),
                )
            )
    return sorted(
        rows,
        key=lambda row: (
            row["risk_margin_rad"],
            row["joint_index"],
            row["side"],
        ),
    )


def _scope_restored(
    env: Any,
    robot: Any,
    configurations: list[Mapping[str, Any]],
) -> bool:
    model = env.sim.model
    return bool(
        "run_controller" not in robot.controller.__dict__
        and all(
            np.array_equal(
                np.asarray(
                    model.jnt_range[
                        int(configuration["model_joint_id"])
                    ]
                ),
                np.asarray(
                    configuration["original_joint_range"]
                ),
            )
            and np.array_equal(
                np.asarray(
                    model.jnt_solref[
                        int(configuration["model_joint_id"])
                    ]
                ),
                np.asarray(
                    configuration["original_joint_solref"]
                ),
            )
            and np.array_equal(
                np.asarray(
                    model.jnt_solimp[
                        int(configuration["model_joint_id"])
                    ]
                ),
                np.asarray(
                    configuration["original_joint_solimp"]
                ),
            )
            for configuration in configurations
        )
    )


@contextmanager
def _scoped_multi_joint_guards(
    env: Any,
    robot: Any,
    *,
    configurations: list[dict[str, Any]],
) -> Iterator[list[dict[str, Any]]]:
    if not configurations:
        raise PredictiveVirtualBrakeV14Error(
            "multi-joint guard scope requires configurations"
        )
    controller = robot.controller
    model = env.sim.model
    joint_ids = [
        int(configuration["model_joint_id"])
        for configuration in configurations
    ]
    if (
        len(set(joint_ids)) != len(joint_ids)
        or not _scope_restored(env, robot, configurations)
    ):
        raise PredictiveVirtualBrakeV14Error(
            "invalid multi-joint guard scope"
        )
    original_run_controller = controller.run_controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    audit: list[dict[str, Any]] = []

    def guarded_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        raw = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        clipped = np.asarray(
            controller_self.clip_torques(raw),
            dtype=np.float64,
        ).copy()
        side_rows = []
        for configuration in configurations:
            side = str(configuration["target_joint_side"])
            guarded_range = np.asarray(
                configuration["guarded_joint_range"],
                dtype=np.float64,
            )
            position = float(
                env.sim.data.qpos[
                    int(configuration["qpos_address"])
                ]
            )
            dof_address = int(configuration["dof_address"])
            guarded_limit = float(
                guarded_range[1 if side == "upper" else 0]
            )
            distance = (
                guarded_limit - position
                if side == "upper"
                else position - guarded_limit
            )
            side_rows.append(
                {
                    "joint_index": int(
                        configuration["target_joint_index"]
                    ),
                    "side": side,
                    "position_rad": position,
                    "velocity_rad_s": float(
                        env.sim.data.qvel[dof_address]
                    ),
                    "guard_distance_rad": distance,
                    "guard_constraint_near_or_active": bool(
                        distance <= 1e-5
                    ),
                    "dof_constraint_force": float(
                        env.sim.data.qfrc_constraint[dof_address]
                    ),
                }
            )
        audit.append(
            {
                "controller_substep_index": len(audit),
                "guarded_sides": side_rows,
                "raw_controller_torque": raw.tolist(),
                "downstream_clipped_controller_torque": (
                    clipped.tolist()
                ),
                "torque_bound_violation": bool(
                    np.any(clipped < actuator_min)
                    or np.any(clipped > actuator_max)
                ),
            }
        )
        return raw

    for configuration in configurations:
        joint_id = int(configuration["model_joint_id"])
        model.jnt_range[joint_id] = np.asarray(
            configuration["guarded_joint_range"],
            dtype=np.float64,
        )
        guarded_solref = configuration["guarded_joint_solref"]
        if guarded_solref is not None:
            model.jnt_solref[joint_id] = np.asarray(
                guarded_solref,
                dtype=np.float64,
            )
            model.jnt_solimp[joint_id] = np.asarray(
                configuration["guarded_joint_solimp"],
                dtype=np.float64,
            )
    env.sim.forward()
    controller.run_controller = MethodType(
        guarded_run_controller,
        controller,
    )
    try:
        yield audit
    finally:
        del controller.run_controller
        for configuration in configurations:
            joint_id = int(configuration["model_joint_id"])
            model.jnt_range[joint_id] = np.asarray(
                configuration["original_joint_range"],
                dtype=np.float64,
            )
            model.jnt_solref[joint_id] = np.asarray(
                configuration["original_joint_solref"],
                dtype=np.float64,
            )
            model.jnt_solimp[joint_id] = np.asarray(
                configuration["original_joint_solimp"],
                dtype=np.float64,
            )
        env.sim.forward()


class MultiJointPredictiveVirtualBrakeEnvironment(
    core.PredictiveVirtualBrakeEnvironment
):
    """Shadow, jointly guard all predicted at-risk arm joints, restore."""

    def __init__(
        self,
        env: Any,
        *,
        wait_steps: int,
        enabled: bool,
        config: Any,
    ) -> None:
        del config
        super().__init__(
            env,
            wait_steps=wait_steps,
            enabled=enabled,
            config=MultiJointBrakeConfig(),
        )

    def _margin_matrix(
        self,
        qidx: np.ndarray,
        limits: np.ndarray,
    ) -> np.ndarray:
        return _joint_side_margins(
            np.asarray(
                self._env.sim.data.qpos[qidx],
                dtype=np.float64,
            ),
            limits,
        )

    def _configurations(
        self,
        *,
        qidx: np.ndarray,
        vidx: np.ndarray,
        risks: list[dict[str, Any]],
        guard_margin_rad: float,
    ) -> list[dict[str, Any]]:
        return [
            core._configure_virtual_joint_guard(
                env=self._env,
                qidx=qidx,
                vidx=vidx,
                target_joint_index=int(risk["joint_index"]),
                target_joint_side=str(risk["side"]),
                guard_margin_rad=guard_margin_rad,
                guard_solref=self._config.guard_solref,
                guard_solimp=self._config.guard_solimp,
            )
            for risk in risks
        ]

    def step(self, action: Any) -> Any:
        runner_step_id = self._call_index
        if (
            not self._enabled
            or runner_step_id < self._wait_steps
        ):
            transition = super().step(action)
            if (
                not self._enabled
                and runner_step_id >= self._wait_steps
            ):
                _robot, qidx, _vidx, limits = self._arrays()
                actual = self._margin_matrix(qidx, limits)
                self.observations[-1].update(
                    {
                        "schema": BRAKE_AUDIT_SCHEMA,
                        "multi_joint_audit": True,
                        "joint_side_scope_count": 14,
                        "actual_joint_side_margins": (
                            _margin_rows(actual)
                        ),
                        "actual_worst_margin_rad": float(
                            np.min(actual)
                        ),
                        "risk_sides": [],
                    }
                )
            return transition

        self._call_index += 1
        robot, qidx, vidx, limits = self._arrays()
        action_digest = core._action_digest(action)
        screen_start = perf_counter()
        snapshot = core.capture_warmstart_policy_shadow_snapshot(
            self._env,
            robot,
            source_id=(
                f"v14:multijoint-virtual-brake:step{runner_step_id}"
            ),
        )
        current = self._margin_matrix(qidx, limits)
        unguarded_transition = self._env.step(action)
        unguarded = self._margin_matrix(qidx, limits)
        shadow_restore = (
            core.restore_warmstart_policy_shadow_snapshot(
                self._env,
                robot,
                snapshot,
            )
        )
        shadow_restore_identity = core._restore_identity(
            shadow_restore
        )
        risks = _risk_sides(
            current,
            unguarded,
            trigger_margin_rad=self._config.trigger_margin_rad,
        )
        triggered = bool(risks)
        candidates: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        all_candidate_restores = True

        if shadow_restore_identity and triggered:
            for guard_margin in self._config.guard_margins_rad:
                configurations = self._configurations(
                    qidx=qidx,
                    vidx=vidx,
                    risks=risks,
                    guard_margin_rad=guard_margin,
                )
                inside = all(
                    configuration[
                        "configuration_inside_guard_range"
                    ]
                    for configuration in configurations
                )
                if not inside:
                    candidates.append(
                        {
                            "guard_margin_rad": guard_margin,
                            "configuration_inside_guard_ranges": False,
                            "predicted_minimum_margin_rad": None,
                            "predicted_joint_side_margins": None,
                            "scope_restored": True,
                            "restore_identity": True,
                            "torque_bound_violation_count": 0,
                            "maximum_abs_constraint_force": 0.0,
                            "eligible": False,
                        }
                    )
                    continue
                with _scoped_multi_joint_guards(
                    self._env,
                    robot,
                    configurations=configurations,
                ) as torque_audit:
                    self._env.step(action)
                    candidate_margins = self._margin_matrix(
                        qidx,
                        limits,
                    )
                scope_restored = _scope_restored(
                    self._env,
                    robot,
                    configurations,
                )
                torque_violations = sum(
                    row["torque_bound_violation"]
                    for row in torque_audit
                )
                maximum_force = max(
                    (
                        abs(side["dof_constraint_force"])
                        for row in torque_audit
                        for side in row["guarded_sides"]
                    ),
                    default=0.0,
                )
                candidate_restore = (
                    core.restore_warmstart_policy_shadow_snapshot(
                        self._env,
                        robot,
                        snapshot,
                    )
                )
                candidate_restore_identity = (
                    core._restore_identity(candidate_restore)
                )
                all_candidate_restores = bool(
                    all_candidate_restores
                    and candidate_restore_identity
                )
                eligible = bool(
                    all(
                        configuration[
                            "configuration_qpos_identity"
                        ]
                        and configuration[
                            "configuration_qvel_identity"
                        ]
                        for configuration in configurations
                    )
                    and scope_restored
                    and candidate_restore_identity
                    and torque_violations == 0
                    and float(np.min(candidate_margins))
                    >= self._config.safe_margin_floor_rad
                )
                row = {
                    "guard_margin_rad": guard_margin,
                    "configuration_inside_guard_ranges": True,
                    "guarded_sides": [
                        {
                            "joint_index": int(
                                configuration[
                                    "target_joint_index"
                                ]
                            ),
                            "side": str(
                                configuration[
                                    "target_joint_side"
                                ]
                            ),
                        }
                        for configuration in configurations
                    ],
                    "predicted_minimum_margin_rad": float(
                        np.min(candidate_margins)
                    ),
                    "predicted_joint_side_margins": _margin_rows(
                        candidate_margins
                    ),
                    "scope_restored": scope_restored,
                    "restore_identity": (
                        candidate_restore_identity
                    ),
                    "torque_bound_violation_count": (
                        torque_violations
                    ),
                    "maximum_abs_constraint_force": maximum_force,
                    "eligible": eligible,
                }
                candidates.append(row)
                if selected is None and eligible:
                    selected = {
                        **row,
                        "configurations": configurations,
                    }

        deadlock_reason = None
        if not shadow_restore_identity:
            deadlock_reason = "shadow_restore_identity_failed"
        elif triggered and selected is None:
            deadlock_reason = "no_safe_multijoint_guard_candidate"
        screen_latency = perf_counter() - screen_start

        actual_force = 0.0
        actual_torque_violations = 0
        scope_restored: bool | None = None
        selected_margins = None
        selected_margin = None
        prediction_error = None
        intervened = False
        if deadlock_reason is not None:
            transition = fresh3._terminal_shadow_observation_deadlock_transition(
                self._env,
                unguarded_transition,
                reason=deadlock_reason,
            )
            actual = current
        elif selected is None:
            transition = self._env.step(action)
            actual = self._margin_matrix(qidx, limits)
        else:
            configurations = self._configurations(
                qidx=qidx,
                vidx=vidx,
                risks=risks,
                guard_margin_rad=float(
                    selected["guard_margin_rad"]
                ),
            )
            with _scoped_multi_joint_guards(
                self._env,
                robot,
                configurations=configurations,
            ) as actual_torque_audit:
                transition = self._env.step(action)
                actual = self._margin_matrix(qidx, limits)
            scope_restored = _scope_restored(
                self._env,
                robot,
                configurations,
            )
            actual_torque_violations = sum(
                row["torque_bound_violation"]
                for row in actual_torque_audit
            )
            actual_force = max(
                (
                    abs(side["dof_constraint_force"])
                    for row in actual_torque_audit
                    for side in row["guarded_sides"]
                ),
                default=0.0,
            )
            selected_margins = selected[
                "predicted_joint_side_margins"
            ]
            selected_margin = float(
                selected["guard_margin_rad"]
            )
            prediction_error = abs(
                float(np.min(actual))
                - float(selected["predicted_minimum_margin_rad"])
            )
            intervened = True

        actual_minimum = float(np.min(actual))
        unguarded_minimum = float(np.min(unguarded))
        self.observations.append(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "runner_step_id": runner_step_id,
                "enabled": True,
                "screen_performed": True,
                "multi_joint_audit": True,
                "joint_side_scope_count": 14,
                "triggered": triggered,
                "intervened": intervened,
                "deadlock": deadlock_reason is not None,
                "deadlock_reason": deadlock_reason,
                "source_action_digest": action_digest,
                "executed_action_digest": (
                    action_digest
                    if deadlock_reason is None
                    else None
                ),
                "exact_action_identity": (
                    deadlock_reason is None
                ),
                "current_joint_side_margins": _margin_rows(
                    current
                ),
                "unguarded_predicted_joint_side_margins": (
                    _margin_rows(unguarded)
                ),
                "selected_predicted_joint_side_margins": (
                    selected_margins
                ),
                "actual_joint_side_margins": _margin_rows(actual),
                "risk_sides": risks,
                "current_target_margin_rad": float(
                    np.min(current)
                ),
                "unguarded_predicted_minimum_margin_rad": (
                    unguarded_minimum
                ),
                "unguarded_predicted_target_margin_rad": (
                    unguarded_minimum
                ),
                "selected_guard_margin_rad": selected_margin,
                "selected_predicted_minimum_margin_rad": (
                    float(
                        selected[
                            "predicted_minimum_margin_rad"
                        ]
                    )
                    if selected is not None
                    else None
                ),
                "selected_predicted_target_margin_rad": (
                    float(
                        selected[
                            "predicted_minimum_margin_rad"
                        ]
                    )
                    if selected is not None
                    else None
                ),
                "actual_minimum_margin_rad": actual_minimum,
                "actual_target_margin_rad": actual_minimum,
                "actual_worst_margin_rad": actual_minimum,
                "prediction_execution_margin_error_rad": (
                    prediction_error
                ),
                "shadow_restore_identity": (
                    shadow_restore_identity
                ),
                "candidate_restore_identity": (
                    all_candidate_restores
                    if candidates
                    else True
                ),
                "guard_scope_restored": scope_restored,
                "candidate_count": len(candidates),
                "eligible_candidate_count": sum(
                    row["eligible"] for row in candidates
                ),
                "shadow_env_step_count": 1
                + sum(
                    row[
                        "configuration_inside_guard_ranges"
                    ]
                    for row in candidates
                ),
                "screen_latency_seconds": screen_latency,
                "maximum_abs_target_constraint_force": (
                    actual_force
                ),
                "maximum_abs_guarded_constraint_force": (
                    actual_force
                ),
                "torque_bound_violation_count": (
                    actual_torque_violations
                ),
                "candidates": candidates,
            }
        )
        return transition


@contextmanager
def _patched_environment() -> Iterator[None]:
    original = core.PredictiveVirtualBrakeEnvironment
    core.PredictiveVirtualBrakeEnvironment = (
        MultiJointPredictiveVirtualBrakeEnvironment
    )
    try:
        yield
    finally:
        core.PredictiveVirtualBrakeEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one four-arm episode with all-arm margin/guard coverage."""

    with _patched_environment():
        payload = fresh3.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    l2_enabled = bool(metadata["l2_execution_integrity"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "predictive_virtual_brake_target_joint_index": None,
            "predictive_virtual_brake_target_joint_side": None,
            "predictive_virtual_brake_target_scope": (
                "all_7_arm_joints_both_sides"
                if l2_enabled
                else None
            ),
            "predictive_virtual_brake_joint_indices": (
                list(range(JOINT_COUNT)) if l2_enabled else None
            ),
            "predictive_virtual_brake_joint_sides": (
                list(JOINT_SIDES) if l2_enabled else None
            ),
            "predictive_virtual_brake_joint_side_scope_count": (
                14 if l2_enabled else None
            ),
            "predictive_virtual_brake_multijoint": l2_enabled,
            "predictive_virtual_brake_simultaneous_guarding": (
                l2_enabled
            ),
            "predictive_virtual_brake_action_substitution": False,
        }
    )
    payload["metadata"] = metadata
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "execution_authorized": False,
            "joint_side_scope_count": 14,
            "note": (
                "Import through a separately frozen v14 development "
                "or qualification protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
