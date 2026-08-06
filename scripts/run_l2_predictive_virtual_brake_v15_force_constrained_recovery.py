#!/usr/bin/env python3
"""v15.5 force-constrained recovery with candidate post-force screening."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_dynamic_state_recovery as predecessor,
)


v14 = predecessor.predecessor.v14_core
priority = predecessor.predecessor.predecessor
current = priority.predecessor

RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_5_"
    "force_constrained_dynamic_state_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.5."
    "force-constrained-dynamic-state-recovery.step"
)
JOINT_COUNT = predecessor.JOINT_COUNT
JOINT_SIDES = predecessor.JOINT_SIDES
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLIMP = predecessor.GUARD_SOLIMP
RECOVERY_GUARD_MARGIN_RAD = predecessor.RECOVERY_GUARD_MARGIN_RAD
CURRENT_EDGE_EPSILON_RAD = predecessor.CURRENT_EDGE_EPSILON_RAD

FORCE_CONSTRAINED_GUARD_SOLREF = (0.006, 1.0)
MAXIMUM_ATTRIBUTABLE_JOINT_FORCE_INCREMENT = 10000.0
MAXIMUM_POST_STEP_ABSOLUTE_RISK_FORCE = 10000.0
MAXIMUM_POST_STEP_POSITIVE_JOINT_INCREMENT = 10000.0
MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT = 1250.0
MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT = 1250.0


class ForceConstrainedRecoveryError(RuntimeError):
    """Raised when v15.5 cannot bind force-aware candidate selection."""


class ForceConstrainedRecoveryConfig(
    priority.CurrentEdgePriorityRecoveryConfig
):
    """Preserve candidate order while using the developed soft profile."""

    def __init__(self, current_edge_margin_rad: float | None) -> None:
        edge = current_edge_margin_rad
        if edge is not None and not (
            np.isfinite(edge)
            and SAFE_MARGIN_FLOOR_RAD < edge < min(BRAKE_MARGINS_RAD)
        ):
            raise ValueError("invalid v15.5 current-edge margin")
        object.__setattr__(self, "current_edge_margin_rad", edge)
        object.__setattr__(self, "joint_indices", tuple(range(JOINT_COUNT)))
        object.__setattr__(self, "trigger_margin_rad", TRIGGER_MARGIN_RAD)
        object.__setattr__(self, "safe_margin_floor_rad", SAFE_MARGIN_FLOOR_RAD)
        object.__setattr__(
            self, "guard_solref", FORCE_CONSTRAINED_GUARD_SOLREF
        )
        object.__setattr__(self, "guard_solimp", GUARD_SOLIMP)

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        middle = (
            ()
            if self.current_edge_margin_rad is None
            else (self.current_edge_margin_rad,)
        )
        return (*BRAKE_MARGINS_RAD, *middle, RECOVERY_GUARD_MARGIN_RAD)


def _risk_force_metrics(
    *,
    pre: np.ndarray,
    post: np.ndarray,
    torque_audit: list[Mapping[str, Any]],
    risk_indices: tuple[int, ...],
) -> dict[str, float]:
    pre_values = np.asarray(pre, dtype=np.float64)
    post_values = np.asarray(post, dtype=np.float64)
    if (
        pre_values.shape != (JOINT_COUNT,)
        or post_values.shape != (JOINT_COUNT,)
        or not np.isfinite(pre_values).all()
        or not np.isfinite(post_values).all()
    ):
        raise ForceConstrainedRecoveryError(
            "v15.5 candidate force vectors are invalid"
        )
    scoped: dict[int, list[float]] = {index: [] for index in risk_indices}
    for controller_row in torque_audit:
        for side in controller_row["guarded_sides"]:
            index = int(side["joint_index"])
            value = float(side["dof_constraint_force"])
            if index not in scoped or not np.isfinite(value):
                raise ForceConstrainedRecoveryError(
                    "v15.5 scope force differs from risk identity"
                )
            scoped[index].append(value)
    if any(not values for values in scoped.values()):
        raise ForceConstrainedRecoveryError(
            "v15.5 candidate lacks a risk-joint force sample"
        )
    scope_abs = max(
        abs(value) for values in scoped.values() for value in values
    )
    scope_increment = max(
        max(0.0, max(abs(value) for value in scoped[index]) - abs(pre_values[index]))
        for index in risk_indices
    )
    post_abs = max(abs(float(post_values[index])) for index in risk_indices)
    post_increment = max(
        max(
            0.0,
            abs(float(post_values[index])) - abs(float(pre_values[index])),
        )
        for index in risk_indices
    )
    return {
        "scope_absolute_risk_force": float(scope_abs),
        "scope_positive_joint_increment": float(scope_increment),
        "post_step_absolute_risk_force": float(post_abs),
        "post_step_positive_joint_increment": float(post_increment),
    }


def _force_feasible(
    metrics: Mapping[str, float],
    *,
    recovery_candidate: bool,
) -> bool:
    feasible = bool(
        metrics["scope_positive_joint_increment"]
        <= MAXIMUM_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
        and metrics["post_step_absolute_risk_force"]
        <= MAXIMUM_POST_STEP_ABSOLUTE_RISK_FORCE
        and metrics["post_step_positive_joint_increment"]
        <= MAXIMUM_POST_STEP_POSITIVE_JOINT_INCREMENT
    )
    if recovery_candidate:
        feasible = bool(
            feasible
            and metrics["scope_positive_joint_increment"]
            <= MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
            and metrics["post_step_positive_joint_increment"]
            <= MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
        )
    return feasible


def _force_constrained_core_step(self: Any, action: Any) -> Any:
    runner_step_id = self._call_index
    if not self._enabled or runner_step_id < self._wait_steps:
        transition = v14.core.PredictiveVirtualBrakeEnvironment.step(
            self, action
        )
        if not self._enabled and runner_step_id >= self._wait_steps:
            _robot, qidx, _vidx, limits = self._arrays()
            actual = self._margin_matrix(qidx, limits)
            self.observations[-1].update(
                {
                    "schema": v14.BRAKE_AUDIT_SCHEMA,
                    "multi_joint_audit": True,
                    "joint_side_scope_count": 14,
                    "actual_joint_side_margins": v14._margin_rows(actual),
                    "actual_worst_margin_rad": float(np.min(actual)),
                    "risk_sides": [],
                }
            )
        return transition

    self._call_index += 1
    robot, qidx, vidx, limits = self._arrays()
    action_digest = v14.core._action_digest(action)
    screen_start = perf_counter()
    snapshot = v14.core.capture_warmstart_policy_shadow_snapshot(
        self._env,
        robot,
        source_id=f"v15.5:force-constrained:step{runner_step_id}",
    )
    current_margins = self._margin_matrix(qidx, limits)
    pre_force = np.asarray(
        self._env.sim.data.qfrc_constraint[vidx], dtype=np.float64
    ).copy()
    unguarded_transition = self._env.step(action)
    unguarded = self._margin_matrix(qidx, limits)
    shadow_restore = v14.core.restore_warmstart_policy_shadow_snapshot(
        self._env, robot, snapshot
    )
    shadow_restore_identity = v14.core._restore_identity(shadow_restore)
    risks = v14._risk_sides(
        current_margins,
        unguarded,
        trigger_margin_rad=self._config.trigger_margin_rad,
    )
    risk_indices = tuple(sorted({int(row["joint_index"]) for row in risks}))
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
                configuration["configuration_inside_guard_range"]
                for configuration in configurations
            )
            recovery_candidate = guard_margin not in BRAKE_MARGINS_RAD
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
                        "base_safety_eligible": False,
                        "force_feasible": False,
                        "recovery_candidate": recovery_candidate,
                        "eligible": False,
                    }
                )
                continue
            with v14._scoped_multi_joint_guards(
                self._env,
                robot,
                configurations=configurations,
            ) as torque_audit:
                self._env.step(action)
                candidate_margins = self._margin_matrix(qidx, limits)
            candidate_post_force = np.asarray(
                self._env.sim.data.qfrc_constraint[vidx], dtype=np.float64
            ).copy()
            scope_restored = v14._scope_restored(
                self._env, robot, configurations
            )
            torque_violations = sum(
                row["torque_bound_violation"] for row in torque_audit
            )
            metrics = _risk_force_metrics(
                pre=pre_force,
                post=candidate_post_force,
                torque_audit=torque_audit,
                risk_indices=risk_indices,
            )
            candidate_restore = (
                v14.core.restore_warmstart_policy_shadow_snapshot(
                    self._env, robot, snapshot
                )
            )
            candidate_restore_identity = v14.core._restore_identity(
                candidate_restore
            )
            all_candidate_restores = bool(
                all_candidate_restores and candidate_restore_identity
            )
            base_eligible = bool(
                all(
                    configuration["configuration_qpos_identity"]
                    and configuration["configuration_qvel_identity"]
                    for configuration in configurations
                )
                and scope_restored
                and candidate_restore_identity
                and torque_violations == 0
                and float(np.min(candidate_margins))
                >= self._config.safe_margin_floor_rad
            )
            force_feasible = _force_feasible(
                metrics, recovery_candidate=recovery_candidate
            )
            eligible = bool(base_eligible and force_feasible)
            row = {
                "guard_margin_rad": guard_margin,
                "configuration_inside_guard_ranges": True,
                "guarded_sides": [
                    {
                        "joint_index": int(
                            configuration["target_joint_index"]
                        ),
                        "side": str(configuration["target_joint_side"]),
                    }
                    for configuration in configurations
                ],
                "predicted_minimum_margin_rad": float(
                    np.min(candidate_margins)
                ),
                "predicted_joint_side_margins": v14._margin_rows(
                    candidate_margins
                ),
                "scope_restored": scope_restored,
                "restore_identity": candidate_restore_identity,
                "torque_bound_violation_count": torque_violations,
                "maximum_abs_constraint_force": metrics[
                    "scope_absolute_risk_force"
                ],
                "predicted_scope_positive_joint_increment": metrics[
                    "scope_positive_joint_increment"
                ],
                "predicted_post_step_maximum_abs_risk_constraint_force": (
                    metrics["post_step_absolute_risk_force"]
                ),
                "predicted_post_step_maximum_positive_joint_increment": (
                    metrics["post_step_positive_joint_increment"]
                ),
                "base_safety_eligible": base_eligible,
                "force_feasible": force_feasible,
                "recovery_candidate": recovery_candidate,
                "eligible": eligible,
            }
            candidates.append(row)
            if selected is None and eligible:
                selected = {**row, "configurations": configurations}

    deadlock_reason = None
    if not shadow_restore_identity:
        deadlock_reason = "shadow_restore_identity_failed"
    elif triggered and selected is None:
        deadlock_reason = "no_force_feasible_multijoint_guard_candidate"
    screen_latency = perf_counter() - screen_start

    actual_force = 0.0
    actual_torque_violations = 0
    scope_restored: bool | None = None
    selected_margins = None
    selected_margin = None
    prediction_error = None
    intervened = False
    if deadlock_reason is not None:
        transition = v14.fresh3._terminal_shadow_observation_deadlock_transition(
            self._env,
            unguarded_transition,
            reason=deadlock_reason,
        )
        actual = current_margins
    elif selected is None:
        transition = self._env.step(action)
        actual = self._margin_matrix(qidx, limits)
    else:
        configurations = self._configurations(
            qidx=qidx,
            vidx=vidx,
            risks=risks,
            guard_margin_rad=float(selected["guard_margin_rad"]),
        )
        with v14._scoped_multi_joint_guards(
            self._env,
            robot,
            configurations=configurations,
        ) as actual_torque_audit:
            transition = self._env.step(action)
            actual = self._margin_matrix(qidx, limits)
        scope_restored = v14._scope_restored(
            self._env, robot, configurations
        )
        actual_torque_violations = sum(
            row["torque_bound_violation"] for row in actual_torque_audit
        )
        actual_force = max(
            (
                abs(side["dof_constraint_force"])
                for row in actual_torque_audit
                for side in row["guarded_sides"]
            ),
            default=0.0,
        )
        selected_margins = selected["predicted_joint_side_margins"]
        selected_margin = float(selected["guard_margin_rad"])
        prediction_error = abs(
            float(np.min(actual))
            - float(selected["predicted_minimum_margin_rad"])
        )
        intervened = True

    actual_minimum = float(np.min(actual))
    unguarded_minimum = float(np.min(unguarded))
    self.observations.append(
        {
            "schema": v14.BRAKE_AUDIT_SCHEMA,
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
                action_digest if deadlock_reason is None else None
            ),
            "exact_action_identity": deadlock_reason is None,
            "current_joint_side_margins": v14._margin_rows(current_margins),
            "unguarded_predicted_joint_side_margins": v14._margin_rows(
                unguarded
            ),
            "selected_predicted_joint_side_margins": selected_margins,
            "actual_joint_side_margins": v14._margin_rows(actual),
            "risk_sides": risks,
            "current_target_margin_rad": float(np.min(current_margins)),
            "unguarded_predicted_minimum_margin_rad": unguarded_minimum,
            "unguarded_predicted_target_margin_rad": unguarded_minimum,
            "selected_guard_margin_rad": selected_margin,
            "selected_predicted_minimum_margin_rad": (
                float(selected["predicted_minimum_margin_rad"])
                if selected is not None
                else None
            ),
            "selected_predicted_target_margin_rad": (
                float(selected["predicted_minimum_margin_rad"])
                if selected is not None
                else None
            ),
            "actual_minimum_margin_rad": actual_minimum,
            "actual_target_margin_rad": actual_minimum,
            "actual_worst_margin_rad": actual_minimum,
            "prediction_execution_margin_error_rad": prediction_error,
            "shadow_restore_identity": shadow_restore_identity,
            "candidate_restore_identity": (
                all_candidate_restores if candidates else True
            ),
            "guard_scope_restored": scope_restored,
            "candidate_count": len(candidates),
            "eligible_candidate_count": sum(
                row["eligible"] for row in candidates
            ),
            "shadow_env_step_count": 1
            + sum(
                row["configuration_inside_guard_ranges"]
                for row in candidates
            ),
            "screen_latency_seconds": screen_latency,
            "maximum_abs_target_constraint_force": actual_force,
            "maximum_abs_guarded_constraint_force": actual_force,
            "torque_bound_violation_count": actual_torque_violations,
            "candidates": candidates,
        }
    )
    return transition


class MultiJointForceConstrainedRecoveryEnvironment(
    predecessor.MultiJointDynamicStateRecoveryEnvironment
):
    """Apply soft-profile and predicted-force eligibility before execution."""

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        original_step = v14.MultiJointPredictiveVirtualBrakeEnvironment.step
        original_config = priority.CurrentEdgePriorityRecoveryConfig
        v14.MultiJointPredictiveVirtualBrakeEnvironment.step = (
            _force_constrained_core_step
        )
        priority.CurrentEdgePriorityRecoveryConfig = (
            ForceConstrainedRecoveryConfig
        )
        try:
            transition = super().step(action)
        finally:
            priority.CurrentEdgePriorityRecoveryConfig = original_config
            v14.MultiJointPredictiveVirtualBrakeEnvironment.step = original_step
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise ForceConstrainedRecoveryError(
                "v15.5 environment produced a non-object audit"
            )
        candidates = audit.get("candidates", [])
        if not isinstance(candidates, list):
            raise ForceConstrainedRecoveryError(
                "v15.5 environment lacks candidate rows"
            )
        selected_margin = audit.get("selected_guard_margin_rad")
        selected_rows = [
            row
            for row in candidates
            if selected_margin is not None
            and float(row["guard_margin_rad"]) == float(selected_margin)
        ]
        if len(selected_rows) > 1:
            raise ForceConstrainedRecoveryError(
                "v15.5 selected candidate identity is ambiguous"
            )
        selected = selected_rows[0] if selected_rows else None
        prediction_identity = bool(
            selected is None
            or (
                np.isclose(
                    float(
                        selected[
                            "predicted_post_step_maximum_abs_risk_constraint_force"
                        ]
                    ),
                    float(
                        audit["post_step_maximum_abs_risk_constraint_force"]
                    ),
                    rtol=0.0,
                    atol=1e-12,
                )
                and np.isclose(
                    float(
                        selected[
                            "predicted_post_step_maximum_positive_joint_increment"
                        ]
                    ),
                    float(
                        audit[
                            "post_step_maximum_positive_joint_increment_over_pre_step"
                        ]
                    ),
                    rtol=0.0,
                    atol=1e-12,
                )
            )
        )
        if not prediction_identity:
            raise ForceConstrainedRecoveryError(
                "v15.5 predicted and executed post-step force differ"
            )
        standard_base_eligible = sum(
            row.get("base_safety_eligible") is True
            for row in candidates
            if float(row["guard_margin_rad"]) in BRAKE_MARGINS_RAD
        )
        baseline_would_deadlock = bool(
            audit.get("triggered") is True and standard_base_eligible == 0
        )
        edge = audit.get("current_edge_recovery_configured_margin_rad")
        floor_selected = bool(
            selected_margin is not None
            and float(selected_margin) == RECOVERY_GUARD_MARGIN_RAD
        )
        current_selected = bool(
            selected_margin is not None
            and edge is not None
            and float(selected_margin) == float(edge)
        )
        recovery_selected = bool(floor_selected or current_selected)
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "force_constrained_recovery_active": bool(
                    audit.get("enabled") is True
                ),
                "force_constrained_guard_solref": list(
                    FORCE_CONSTRAINED_GUARD_SOLREF
                ),
                "candidate_post_force_prediction_active": bool(
                    audit.get("enabled") is True
                ),
                "selected_post_force_prediction_execution_identity": (
                    prediction_identity
                ),
                "base_safety_eligible_candidate_count": sum(
                    row.get("base_safety_eligible") is True
                    for row in candidates
                ),
                "force_feasible_candidate_count": sum(
                    row.get("force_feasible") is True
                    and row.get("base_safety_eligible") is True
                    for row in candidates
                ),
                "force_rejected_base_eligible_candidate_count": sum(
                    row.get("base_safety_eligible") is True
                    and row.get("force_feasible") is not True
                    for row in candidates
                ),
                "selected_force_feasible": bool(
                    selected is None or selected.get("force_feasible") is True
                ),
                "v14_baseline_eligible_candidate_count": (
                    standard_base_eligible
                ),
                "v14_baseline_would_deadlock": baseline_would_deadlock,
                "floor_guard_recovery_selected": floor_selected,
                "current_edge_recovery_selected": current_selected,
                "floor_or_current_edge_recovery_selected": recovery_selected,
                "floor_or_current_edge_recovery_prevented_deadlock": bool(
                    baseline_would_deadlock
                    and recovery_selected
                    and audit.get("deadlock") is False
                ),
                "force_constraints_change_source_action": False,
                "force_constraints_task_outcome_informed": False,
                "force_constraints_physical_authority_claim": False,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointDynamicStateRecoveryEnvironment
    predecessor.MultiJointDynamicStateRecoveryEnvironment = (
        MultiJointForceConstrainedRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointDynamicStateRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.5 episode without changing the source policy action."""

    with _patched_predecessor_environment():
        payload = predecessor.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    l2_enabled = bool(metadata["l2_execution_integrity"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "force_constrained_recovery_active": l2_enabled,
            "force_constrained_guard_solref": (
                list(FORCE_CONSTRAINED_GUARD_SOLREF)
                if l2_enabled
                else None
            ),
            "candidate_post_force_prediction_active": l2_enabled,
            "force_constraints_change_source_action": False,
            "force_constraints_outcome_informed_successor": True,
            "force_constraints_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.5 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
