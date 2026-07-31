#!/usr/bin/env python3
"""Outcome-capable predictive hard virtual-brake successor.

This runner replaces the historical L2 transaction boundary for L2-enabled
arms with an exact-action, simulator-shadow virtual brake.  Each policy step
is first replayed from a warm-start-complete snapshot.  If the unguarded
one-step prediction would put the frozen target joint inside the trigger
margin, the runner evaluates the already-frozen v12.37 hard-stop margins and
executes the weakest candidate that satisfies the safety floor.

The wrapper never substitutes an action.  It changes only the scoped MuJoCo
joint-limit range and solver profile around the selected ``env.step`` call.
"""

from __future__ import annotations

import argparse
from copy import copy
from dataclasses import dataclass
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.policy_prefix_shadow_warmstart_v12 import (  # noqa: E402
    capture_warmstart_policy_shadow_snapshot,
    restore_warmstart_policy_shadow_snapshot,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v10 as v10  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _robot_arrays,
)
from scripts.run_h3_hard_virtual_joint_guard_beam_pilot_v12 import (  # noqa: E402
    GUARD_SOLIMP,
    GUARD_SOLREF,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    _configure_virtual_joint_guard,
    _scoped_virtual_joint_guard,
)


RUNNER_VARIANT = "proofalign_l2_predictive_hard_virtual_brake_v13"
BRAKE_AUDIT_SCHEMA = "proofalign.predictive-hard-virtual-brake.v13.step"
BRAKE_MARGINS_RAD = (0.16, 0.18, 0.20, 0.22)
TRIGGER_MARGIN_RAD = 0.15
SAFE_MARGIN_FLOOR_RAD = 0.15
TARGET_JOINT_INDEX = 1
TARGET_JOINT_SIDE = "upper"
DEADLOCK_INFO_KEY = "proofalign_predictive_virtual_brake_deadlock"


class PredictiveVirtualBrakeV13Error(RuntimeError):
    """Raised when the v13 execution boundary cannot remain auditable."""


@dataclass(frozen=True)
class PredictiveVirtualBrakeConfig:
    """Frozen target and simulator-brake parameters."""

    target_joint_index: int = TARGET_JOINT_INDEX
    target_joint_side: str = TARGET_JOINT_SIDE
    trigger_margin_rad: float = TRIGGER_MARGIN_RAD
    safe_margin_floor_rad: float = SAFE_MARGIN_FLOOR_RAD
    guard_margins_rad: tuple[float, ...] = BRAKE_MARGINS_RAD
    guard_solref: tuple[float, float] = GUARD_SOLREF
    guard_solimp: tuple[float, float, float, float, float] = GUARD_SOLIMP

    def __post_init__(self) -> None:
        if (
            self.target_joint_index < 0
            or self.target_joint_index >= 7
            or self.target_joint_side not in {"lower", "upper"}
            or not np.isfinite(self.trigger_margin_rad)
            or not np.isfinite(self.safe_margin_floor_rad)
            or self.trigger_margin_rad <= 0
            or self.safe_margin_floor_rad < 0
            or not self.guard_margins_rad
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
                for value in (*self.guard_solref, *self.guard_solimp)
            )
        ):
            raise ValueError("invalid predictive virtual-brake configuration")


def _restore_identity(assessment: Any) -> bool:
    return bool(
        assessment.trusted_arm_bitwise_identity
        and assessment.controller_state_identity
        and assessment.simulator_input_identity
        and assessment.environment_clock_identity
        and assessment.qacc_warmstart_identity
    )


def _minimum_margin(
    qpos: np.ndarray,
    limits: np.ndarray,
) -> float:
    return float(
        np.min(
            np.minimum(
                qpos - limits[:, 0],
                limits[:, 1] - qpos,
            )
        )
    )


def _target_margin(
    qpos: np.ndarray,
    limits: np.ndarray,
    *,
    joint_index: int,
    side: str,
) -> float:
    limit = float(limits[joint_index, 1 if side == "upper" else 0])
    position = float(qpos[joint_index])
    return limit - position if side == "upper" else position - limit


def _action_digest(action: Any) -> str:
    values = np.asarray(action, dtype=np.float64).reshape(-1)
    if values.shape != (7,) or not np.isfinite(values).all():
        raise PredictiveVirtualBrakeV13Error(
            "predictive virtual brake requires one finite 7-DoF action"
        )
    return command_digest(tuple(float(value) for value in values))


def _scope_restored(
    env: Any,
    robot: Any,
    configuration: Mapping[str, Any],
) -> bool:
    model = env.sim.model
    joint_id = int(configuration["model_joint_id"])
    return bool(
        "run_controller" not in robot.controller.__dict__
        and np.array_equal(
            np.asarray(model.jnt_range[joint_id]),
            np.asarray(configuration["original_joint_range"]),
        )
        and np.array_equal(
            np.asarray(model.jnt_solref[joint_id]),
            np.asarray(configuration["original_joint_solref"]),
        )
        and np.array_equal(
            np.asarray(model.jnt_solimp[joint_id]),
            np.asarray(configuration["original_joint_solimp"]),
        )
    )


def _current_observation(env: Any) -> Any:
    for name in ("get_observation", "_get_observations"):
        method = getattr(env, name, None)
        if callable(method):
            return method()
    return base.get_observation(env)


def _deadlock_transition(
    env: Any,
    template: Any,
    *,
    reason: str,
) -> Any:
    if not isinstance(template, tuple) or len(template) not in {4, 5}:
        raise PredictiveVirtualBrakeV13Error(
            "cannot synthesize a fail-closed transition"
        )
    observation = _current_observation(env)
    info = dict(template[-1] or {})
    info[DEADLOCK_INFO_KEY] = reason
    if len(template) == 4:
        return observation, 0.0, True, info
    return observation, 0.0, True, False, info


class PredictiveVirtualBrakeEnvironment:
    """Shadow, select, and scope the hard virtual brake per policy step."""

    def __init__(
        self,
        env: Any,
        *,
        wait_steps: int,
        enabled: bool,
        config: PredictiveVirtualBrakeConfig,
    ) -> None:
        if type(wait_steps) is not int or wait_steps < 0:
            raise ValueError("wait_steps must be a non-negative integer")
        self._env = env
        self._wait_steps = wait_steps
        self._enabled = enabled
        self._config = config
        self._call_index = 0
        self._robot: Any | None = None
        self._qidx: np.ndarray | None = None
        self._vidx: np.ndarray | None = None
        self._limits: np.ndarray | None = None
        self.observations: list[dict[str, Any]] = []

    def _arrays(
        self,
    ) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray]:
        if self._robot is None:
            (
                self._robot,
                self._qidx,
                self._vidx,
                self._limits,
            ) = _robot_arrays(self._env)
        assert self._qidx is not None
        assert self._vidx is not None
        assert self._limits is not None
        return self._robot, self._qidx, self._vidx, self._limits

    def _post_state(
        self,
        qidx: np.ndarray,
        limits: np.ndarray,
    ) -> tuple[float, float]:
        qpos = np.asarray(
            self._env.sim.data.qpos[qidx], dtype=np.float64
        )
        return (
            _minimum_margin(qpos, limits),
            _target_margin(
                qpos,
                limits,
                joint_index=self._config.target_joint_index,
                side=self._config.target_joint_side,
            ),
        )

    def step(self, action: Any) -> Any:
        runner_step_id = self._call_index
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return self._env.step(action)

        robot, qidx, vidx, limits = self._arrays()
        action_digest = _action_digest(action)
        if not self._enabled:
            transition = self._env.step(action)
            actual_minimum, actual_target = self._post_state(
                qidx, limits
            )
            self.observations.append(
                {
                    "schema": BRAKE_AUDIT_SCHEMA,
                    "runner_step_id": runner_step_id,
                    "enabled": False,
                    "screen_performed": False,
                    "triggered": False,
                    "intervened": False,
                    "deadlock": False,
                    "deadlock_reason": None,
                    "source_action_digest": action_digest,
                    "executed_action_digest": action_digest,
                    "exact_action_identity": True,
                    "unguarded_predicted_minimum_margin_rad": None,
                    "unguarded_predicted_target_margin_rad": None,
                    "selected_guard_margin_rad": None,
                    "selected_predicted_minimum_margin_rad": None,
                    "selected_predicted_target_margin_rad": None,
                    "actual_minimum_margin_rad": actual_minimum,
                    "actual_target_margin_rad": actual_target,
                    "prediction_execution_margin_error_rad": None,
                    "shadow_restore_identity": None,
                    "candidate_restore_identity": None,
                    "guard_scope_restored": None,
                    "candidate_count": 0,
                    "eligible_candidate_count": 0,
                    "shadow_env_step_count": 0,
                    "screen_latency_seconds": 0.0,
                    "maximum_abs_target_constraint_force": 0.0,
                    "torque_bound_violation_count": 0,
                    "candidates": [],
                }
            )
            return transition

        screen_start = perf_counter()
        snapshot = capture_warmstart_policy_shadow_snapshot(
            self._env,
            robot,
            source_id=(
                f"v13:predictive-virtual-brake:step{runner_step_id}"
            ),
        )
        current_qpos = np.asarray(
            self._env.sim.data.qpos[qidx], dtype=np.float64
        ).copy()
        current_target = _target_margin(
            current_qpos,
            limits,
            joint_index=self._config.target_joint_index,
            side=self._config.target_joint_side,
        )
        unguarded_transition = self._env.step(action)
        unguarded_minimum, unguarded_target = self._post_state(
            qidx, limits
        )
        shadow_restore = restore_warmstart_policy_shadow_snapshot(
            self._env, robot, snapshot
        )
        shadow_restore_identity = _restore_identity(shadow_restore)
        triggered = bool(
            current_target <= self._config.trigger_margin_rad
            or unguarded_target < self._config.trigger_margin_rad
        )
        candidates: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        all_candidate_restores = True

        if shadow_restore_identity and triggered:
            for guard_margin in self._config.guard_margins_rad:
                configuration = _configure_virtual_joint_guard(
                    env=self._env,
                    qidx=qidx,
                    vidx=vidx,
                    target_joint_index=(
                        self._config.target_joint_index
                    ),
                    target_joint_side=self._config.target_joint_side,
                    guard_margin_rad=guard_margin,
                    guard_solref=self._config.guard_solref,
                    guard_solimp=self._config.guard_solimp,
                )
                if not configuration[
                    "configuration_inside_guard_range"
                ]:
                    candidates.append(
                        {
                            "guard_margin_rad": guard_margin,
                            "configuration_inside_guard_range": False,
                            "predicted_minimum_margin_rad": None,
                            "predicted_target_margin_rad": None,
                            "scope_restored": True,
                            "restore_identity": True,
                            "torque_bound_violation_count": 0,
                            "maximum_abs_target_constraint_force": 0.0,
                            "eligible": False,
                        }
                    )
                    continue
                with _scoped_virtual_joint_guard(
                    self._env,
                    robot,
                    configuration=configuration,
                ) as torque_audit:
                    self._env.step(action)
                    candidate_minimum, candidate_target = (
                        self._post_state(qidx, limits)
                    )
                scope_restored = _scope_restored(
                    self._env, robot, configuration
                )
                torque_violations = sum(
                    bool(row["torque_bound_violation"])
                    for row in torque_audit
                )
                maximum_force = max(
                    (
                        abs(
                            float(
                                row[
                                    "target_dof_constraint_force"
                                ]
                            )
                        )
                        for row in torque_audit
                    ),
                    default=0.0,
                )
                candidate_restore = (
                    restore_warmstart_policy_shadow_snapshot(
                        self._env, robot, snapshot
                    )
                )
                candidate_restore_identity = _restore_identity(
                    candidate_restore
                )
                all_candidate_restores = bool(
                    all_candidate_restores
                    and candidate_restore_identity
                )
                eligible = bool(
                    configuration["configuration_qpos_identity"]
                    and configuration["configuration_qvel_identity"]
                    and scope_restored
                    and candidate_restore_identity
                    and torque_violations == 0
                    and candidate_minimum
                    >= self._config.safe_margin_floor_rad
                )
                row = {
                    "guard_margin_rad": guard_margin,
                    "configuration_inside_guard_range": True,
                    "predicted_minimum_margin_rad": candidate_minimum,
                    "predicted_target_margin_rad": candidate_target,
                    "scope_restored": scope_restored,
                    "restore_identity": candidate_restore_identity,
                    "torque_bound_violation_count": torque_violations,
                    "maximum_abs_target_constraint_force": (
                        maximum_force
                    ),
                    "eligible": eligible,
                }
                candidates.append(row)
                if selected is None and eligible:
                    selected = {
                        **row,
                        "configuration": configuration,
                    }

        deadlock_reason = None
        if not shadow_restore_identity:
            deadlock_reason = "shadow_restore_identity_failed"
        elif triggered and selected is None:
            deadlock_reason = "no_safe_guard_candidate"
        screen_latency_seconds = perf_counter() - screen_start

        if deadlock_reason is not None:
            transition = _deadlock_transition(
                self._env,
                unguarded_transition,
                reason=deadlock_reason,
            )
            actual_minimum, actual_target = (
                _minimum_margin(current_qpos, limits),
                current_target,
            )
            actual_force = 0.0
            actual_torque_violations = 0
            scope_restored = None
            selected_minimum = None
            selected_target = None
            selected_margin = None
            prediction_error = None
            intervened = False
        elif selected is None:
            transition = self._env.step(action)
            actual_minimum, actual_target = self._post_state(
                qidx, limits
            )
            actual_force = 0.0
            actual_torque_violations = 0
            scope_restored = None
            selected_minimum = None
            selected_target = None
            selected_margin = None
            prediction_error = None
            intervened = False
        else:
            configuration = _configure_virtual_joint_guard(
                env=self._env,
                qidx=qidx,
                vidx=vidx,
                target_joint_index=self._config.target_joint_index,
                target_joint_side=self._config.target_joint_side,
                guard_margin_rad=float(selected["guard_margin_rad"]),
                guard_solref=self._config.guard_solref,
                guard_solimp=self._config.guard_solimp,
            )
            with _scoped_virtual_joint_guard(
                self._env,
                robot,
                configuration=configuration,
            ) as actual_torque_audit:
                transition = self._env.step(action)
                actual_minimum, actual_target = self._post_state(
                    qidx, limits
                )
            scope_restored = _scope_restored(
                self._env, robot, configuration
            )
            actual_torque_violations = sum(
                bool(row["torque_bound_violation"])
                for row in actual_torque_audit
            )
            actual_force = max(
                (
                    abs(
                        float(
                            row["target_dof_constraint_force"]
                        )
                    )
                    for row in actual_torque_audit
                ),
                default=0.0,
            )
            selected_minimum = float(
                selected["predicted_minimum_margin_rad"]
            )
            selected_target = float(
                selected["predicted_target_margin_rad"]
            )
            selected_margin = float(selected["guard_margin_rad"])
            prediction_error = abs(
                actual_minimum - selected_minimum
            )
            intervened = True

        self.observations.append(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "runner_step_id": runner_step_id,
                "enabled": True,
                "screen_performed": True,
                "triggered": triggered,
                "intervened": intervened,
                "deadlock": deadlock_reason is not None,
                "deadlock_reason": deadlock_reason,
                "source_action_digest": action_digest,
                "executed_action_digest": (
                    action_digest if deadlock_reason is None else None
                ),
                "exact_action_identity": deadlock_reason is None,
                "current_target_margin_rad": current_target,
                "unguarded_predicted_minimum_margin_rad": (
                    unguarded_minimum
                ),
                "unguarded_predicted_target_margin_rad": (
                    unguarded_target
                ),
                "selected_guard_margin_rad": selected_margin,
                "selected_predicted_minimum_margin_rad": (
                    selected_minimum
                ),
                "selected_predicted_target_margin_rad": selected_target,
                "actual_minimum_margin_rad": actual_minimum,
                "actual_target_margin_rad": actual_target,
                "prediction_execution_margin_error_rad": (
                    prediction_error
                ),
                "shadow_restore_identity": shadow_restore_identity,
                "candidate_restore_identity": (
                    all_candidate_restores
                    if candidates
                    else True
                ),
                "guard_scope_restored": scope_restored,
                "candidate_count": len(candidates),
                "eligible_candidate_count": sum(
                    bool(row["eligible"]) for row in candidates
                ),
                "shadow_env_step_count": 1
                + sum(
                    bool(row["configuration_inside_guard_range"])
                    for row in candidates
                ),
                "screen_latency_seconds": (
                    screen_latency_seconds
                ),
                "maximum_abs_target_constraint_force": (
                    actual_force
                ),
                "torque_bound_violation_count": (
                    actual_torque_violations
                ),
                "candidates": candidates,
            }
        )
        return transition

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)


def _bind_brake_trace(
    payload: dict[str, Any],
    observations: list[dict[str, Any]],
) -> None:
    policy_rows = [
        row
        for row in payload.get("trace", ())
        if row.get("phase") == "policy"
    ]
    if len(policy_rows) != len(observations):
        raise PredictiveVirtualBrakeV13Error(
            "virtual-brake observations do not cover every policy step"
        )
    for trace_row, observation in zip(
        policy_rows, observations, strict=True
    ):
        if trace_row.get("step_id") != observation["runner_step_id"]:
            raise PredictiveVirtualBrakeV13Error(
                "virtual-brake step identity differs from trace"
            )
        trace_row["predictive_virtual_brake"] = observation
    if observations and observations[-1]["deadlock"]:
        payload["decision"] = "predictive_virtual_brake_deadlock"
        payload["success_by_done"] = False


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one four-arm episode with the legacy L2 path replaced by v13."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, l2_enabled = v1._arm_switches(args)
    inner_args = copy(args)
    if l2_enabled:
        inner_args.l2_execution_integrity = "off"
    original_create_env = base.create_env
    wrapped_envs: list[PredictiveVirtualBrakeEnvironment] = []

    def create_braked_env(
        *create_args: Any,
        **create_kwargs: Any,
    ) -> PredictiveVirtualBrakeEnvironment:
        wrapped = PredictiveVirtualBrakeEnvironment(
            original_create_env(*create_args, **create_kwargs),
            wait_steps=int(args.num_steps_wait),
            enabled=l2_enabled,
            config=PredictiveVirtualBrakeConfig(),
        )
        wrapped_envs.append(wrapped)
        return wrapped

    base.create_env = create_braked_env
    try:
        payload = v10.run_episode(
            **{**kwargs, "args": inner_args}
        )
    finally:
        base.create_env = original_create_env
    if len(wrapped_envs) != 1:
        raise PredictiveVirtualBrakeV13Error(
            "v13 expected exactly one episode environment"
        )
    _bind_brake_trace(payload, wrapped_envs[0].observations)
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "four_arm_label": (
                "dual"
                if l1_enabled and l2_enabled
                else "semantic_only"
                if l1_enabled
                else "execution_only"
                if l2_enabled
                else "vla_only"
            ),
            "l1_semantic_alignment": l1_enabled,
            "l2_execution_integrity": l2_enabled,
            "legacy_l2_execution_integrity_active": False,
            "predictive_virtual_brake_active": l2_enabled,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "predictive_virtual_brake_target_joint_index": (
                TARGET_JOINT_INDEX if l2_enabled else None
            ),
            "predictive_virtual_brake_target_joint_side": (
                TARGET_JOINT_SIDE if l2_enabled else None
            ),
            "predictive_virtual_brake_trigger_margin_rad": (
                TRIGGER_MARGIN_RAD if l2_enabled else None
            ),
            "predictive_virtual_brake_safe_margin_floor_rad": (
                SAFE_MARGIN_FLOOR_RAD if l2_enabled else None
            ),
            "predictive_virtual_brake_guard_margins_rad": (
                list(BRAKE_MARGINS_RAD) if l2_enabled else None
            ),
            "predictive_virtual_brake_guard_solref": (
                list(GUARD_SOLREF) if l2_enabled else None
            ),
            "predictive_virtual_brake_guard_solimp": (
                list(GUARD_SOLIMP) if l2_enabled else None
            ),
            "predictive_virtual_brake_exact_action_only": (
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
            "note": (
                "Import run_episode through a separately frozen v13 "
                "task-outcome protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
