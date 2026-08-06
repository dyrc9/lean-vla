#!/usr/bin/env python3
"""v15.11 bounded state-triggered observed-force shadow recovery.

The v15.8 qualification established that repeated simulator rollouts, rather
than observed-force calibration, dominate the action-screen latency.  This
successor removes the unconditional unguarded rollout and admits at most two
guarded candidate rollouts.  Triggering depends only on the current fourteen
joint-side margins; candidate safety and force feasibility are still checked
against the calibrated shadow before execution.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterator

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_rolling_prebound_recovery as predecessor,
)


pre_step = predecessor.predecessor
observed_force = pre_step.predecessor
incremental = observed_force.predecessor
adaptive = incremental.predecessor
force_constrained = adaptive.predecessor
v14 = adaptive.v14

RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_11_"
    "bounded_state_triggered_observed_force_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.11."
    "bounded-state-triggered-observed-force-recovery.step"
)
# The disclosed stress protocol starts at no more than 0.24 rad.  A 0.22-rad
# state-only trigger missed a one-step 0.24 -> 0.13826 transition under the
# registered 0.7x-friction condition, so the bounded screen covers the whole
# registered initial-margin envelope.
STATE_TRIGGER_MARGIN_RAD = 0.24
MAX_GUARDED_CANDIDATE_ROLLOUTS = 2
STATE_TARGET_OFFSET_RAD = 0.04


class BoundedStateTriggeredRecoveryError(RuntimeError):
    """Raised when the v15.11 bounded-screen contract differs."""


def _placeholder_candidate(
    spec: dict[str, Any], *, precheck_inside: bool
) -> dict[str, Any]:
    return {
        "guard_margin_rad": float(spec["guard_margin_rad"]),
        "guard_solref": list(spec["guard_solref"]),
        "candidate_profile_id": str(spec["profile_id"]),
        "fallback_profile": bool(spec["fallback_profile"]),
        "recovery_candidate": bool(spec["recovery_candidate"]),
        "candidate_screened": False,
        "configuration_precheck_inside_guard_ranges": precheck_inside,
        # This compatibility field means that a scoped simulator evaluation
        # occurred.  The v15.3 attribution layer counts it exactly.
        "configuration_inside_guard_ranges": False,
        "predicted_minimum_margin_rad": None,
        "predicted_joint_side_margins": None,
        "scope_restored": True,
        "restore_identity": True,
        "torque_bound_violation_count": 0,
        "maximum_abs_constraint_force": 0.0,
        "base_safety_eligible": False,
        "force_feasible": False,
        "eligible": False,
    }


def _bounded_state_triggered_core_step(self: Any, action: Any) -> Any:
    runner_step_id = self._call_index
    if not self._enabled or runner_step_id < self._wait_steps:
        transition = v14.core.PredictiveVirtualBrakeEnvironment.step(self, action)
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
    current_margins = self._margin_matrix(qidx, limits)
    pre_force = np.asarray(
        self._env.sim.data.qfrc_constraint[vidx], dtype=np.float64
    ).copy()
    risks = v14._risk_sides(
        current_margins,
        current_margins,
        trigger_margin_rad=STATE_TRIGGER_MARGIN_RAD,
    )
    risk_indices = tuple(sorted({int(row["joint_index"]) for row in risks}))
    triggered = bool(risks)

    candidates: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    candidate_transition: Any | None = None
    all_candidate_restores = True
    evaluated_candidate_count = 0
    snapshot = None
    if triggered:
        snapshot = v14.core.capture_warmstart_policy_shadow_snapshot(
            self._env,
            robot,
            source_id=f"v15.11:bounded-state-trigger:step{runner_step_id}",
        )
        candidate_groups = adaptive._candidate_groups(self._config)
        primary_group = candidate_groups[0]
        floor_margin = float(adaptive.RECOVERY_GUARD_MARGIN_RAD)
        stiff_floor_rows = [
            row
            for group in candidate_groups[1:]
            for row in group
            if row["fallback_profile"] is True
            and float(row["guard_margin_rad"]) == floor_margin
        ]
        if len(stiff_floor_rows) != 1:
            raise BoundedStateTriggeredRecoveryError(
                "v15.11 requires one registered stiff floor fallback"
            )
        standard_specs = tuple(
            row for row in primary_group if row["recovery_candidate"] is False
        )
        current_edge_specs = tuple(
            row
            for row in primary_group
            if row["recovery_candidate"] is True
            and float(row["guard_margin_rad"]) != floor_margin
        )
        extended_recovery_specs = tuple(
            row
            for group in candidate_groups[1:]
            for row in group
            if row["profile_id"] == "soft_extended_recovery"
        )
        if current_edge_specs:
            # Below 0.16 rad, the current-edge recovery is the only soft
            # candidate that can be configured without moving the state.
            first_soft = current_edge_specs[0]
            remaining = (
                *extended_recovery_specs,
                *current_edge_specs[1:],
                *standard_specs,
            )
        else:
            target_margin = (
                float(np.min(current_margins)) - STATE_TARGET_OFFSET_RAD
            )
            ranked_standards = tuple(
                sorted(
                    standard_specs,
                    key=lambda row: (
                        abs(
                            float(row["guard_margin_rad"])
                            - target_margin
                        ),
                        -float(row["guard_margin_rad"]),
                    ),
                )
            )
            first_soft = ranked_standards[0]
            remaining = ranked_standards[1:]
        screening_order = (
            first_soft,
            *remaining,
            stiff_floor_rows[0],
        )
        for spec in screening_order:
            margin = float(spec["guard_margin_rad"])
            solref = tuple(spec["guard_solref"])
            configurations = adaptive._profile_configurations(
                self,
                qidx=qidx,
                vidx=vidx,
                risks=risks,
                guard_margin_rad=margin,
                guard_solref=solref,
            )
            inside = all(
                configuration["configuration_inside_guard_range"]
                for configuration in configurations
            )
            if (
                not inside
                or selected is not None
                or evaluated_candidate_count
                >= MAX_GUARDED_CANDIDATE_ROLLOUTS
            ):
                candidates.append(
                    _placeholder_candidate(spec, precheck_inside=inside)
                )
                continue

            evaluated_candidate_count += 1
            with v14._scoped_multi_joint_guards(
                self._env,
                robot,
                configurations=configurations,
            ) as torque_audit:
                candidate_transition = (
                    self._env.step(action)
                )
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
            metrics = force_constrained._risk_force_metrics(
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
            force_feasible = force_constrained._force_feasible(
                metrics,
                recovery_candidate=bool(spec["recovery_candidate"]),
            )
            eligible = bool(base_eligible and force_feasible)
            row = {
                "guard_margin_rad": margin,
                "guard_solref": list(solref),
                "candidate_profile_id": str(spec["profile_id"]),
                "fallback_profile": bool(spec["fallback_profile"]),
                "recovery_candidate": bool(spec["recovery_candidate"]),
                "candidate_screened": True,
                "configuration_precheck_inside_guard_ranges": True,
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
                "eligible": eligible,
            }
            candidates.append(row)
            if eligible:
                selected = {**row, "configurations": configurations}

    deadlock_reason = None
    if triggered and not all_candidate_restores:
        deadlock_reason = "shadow_restore_identity_failed"
    elif triggered and selected is None:
        deadlock_reason = "no_bounded_force_feasible_guard_candidate"
    screen_latency = perf_counter() - screen_start

    actual_force = 0.0
    actual_torque_violations = 0
    scope_restored: bool | None = None
    selected_margins = None
    selected_margin = None
    selected_profile = None
    prediction_error = None
    intervened = False
    if deadlock_reason is not None:
        if candidate_transition is None:
            raise BoundedStateTriggeredRecoveryError(
                "v15.11 deadlock lacks a bounded shadow transition: "
                f"runner_step_id={runner_step_id}, "
                f"current_minimum_margin_rad={float(np.min(current_margins))}, "
                f"risk_side_count={len(risks)}, "
                f"candidate_count={len(candidates)}"
            )
        transition = v14.fresh3._terminal_shadow_observation_deadlock_transition(
            self._env, candidate_transition, reason=deadlock_reason
        )
        actual = current_margins
    elif selected is None:
        transition = self._env.step(action)
        actual = self._margin_matrix(qidx, limits)
    else:
        configurations = selected["configurations"]
        with v14._scoped_multi_joint_guards(
            self._env, robot, configurations=configurations
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
        selected_profile = str(selected["candidate_profile_id"])
        prediction_error = abs(
            float(np.min(actual))
            - float(selected["predicted_minimum_margin_rad"])
        )
        intervened = True

    actual_minimum = float(np.min(actual))
    current_minimum = float(np.min(current_margins))
    extended_recovery_evaluated = any(
        row.get("candidate_screened") is True
        and row.get("candidate_profile_id") == "soft_extended_recovery"
        for row in candidates
    )
    fallback_profile_evaluated = any(
        row.get("candidate_screened") is True
        and row.get("fallback_profile") is True
        for row in candidates
    )
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
            # Retained only for old audit consumers.  v15.11 explicitly labels
            # this as a state reference, not an unguarded prediction.
            "unguarded_predicted_joint_side_margins": v14._margin_rows(
                current_margins
            ),
            "selected_predicted_joint_side_margins": selected_margins,
            "actual_joint_side_margins": v14._margin_rows(actual),
            "risk_sides": risks,
            "current_target_margin_rad": current_minimum,
            "unguarded_predicted_minimum_margin_rad": current_minimum,
            "unguarded_predicted_target_margin_rad": current_minimum,
            "selected_guard_margin_rad": selected_margin,
            "selected_candidate_profile_id": selected_profile,
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
            "shadow_restore_identity": all_candidate_restores,
            "candidate_restore_identity": all_candidate_restores,
            "guard_scope_restored": scope_restored,
            "candidate_count": len(candidates),
            "eligible_candidate_count": sum(
                row["eligible"] for row in candidates
            ),
            "shadow_env_step_count": evaluated_candidate_count,
            "screen_latency_seconds": screen_latency,
            "maximum_abs_target_constraint_force": actual_force,
            "maximum_abs_guarded_constraint_force": actual_force,
            "torque_bound_violation_count": actual_torque_violations,
            "fallback_profile_evaluated": fallback_profile_evaluated,
            "extended_recovery_evaluated": extended_recovery_evaluated,
            "_adaptive_all_evaluated_candidates": candidates,
            "candidates": candidates,
            "state_triggered_screen_active": True,
            "state_trigger_reference": "current_joint_side_margins",
            "state_trigger_margin_rad": STATE_TRIGGER_MARGIN_RAD,
            "unguarded_shadow_rollout_performed": False,
            "bounded_guarded_candidate_rollout_budget": (
                MAX_GUARDED_CANDIDATE_ROLLOUTS
            ),
            "bounded_guarded_candidate_rollout_count": (
                evaluated_candidate_count
            ),
            "bounded_candidate_priority": (
                "state_offset_ranked_standard_then_registered_recovery"
            ),
            "bounded_state_target_offset_rad": STATE_TARGET_OFFSET_RAD,
        }
    )
    return transition


class MultiJointBoundedStateTriggeredRecoveryEnvironment(
    predecessor.MultiJointRollingPreboundRecoveryEnvironment
):
    """Use state triggering and no more than two calibrated rollouts."""

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        original_core = adaptive._adaptive_force_core_step
        adaptive._adaptive_force_core_step = _bounded_state_triggered_core_step
        try:
            transition = super().step(action)
        finally:
            adaptive._adaptive_force_core_step = original_core
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise BoundedStateTriggeredRecoveryError(
                "v15.11 environment produced a non-object audit"
            )
        rollout_count = int(audit["bounded_guarded_candidate_rollout_count"])
        if rollout_count > MAX_GUARDED_CANDIDATE_ROLLOUTS:
            raise BoundedStateTriggeredRecoveryError(
                "v15.11 exceeded its candidate rollout budget"
            )
        screened_extended_count = sum(
            row.get("candidate_screened") is True
            and row.get("candidate_profile_id")
            == "soft_extended_recovery"
            for row in audit.get("candidates", ())
        )
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "adaptive_proactive_trigger_margin_rad": (
                    STATE_TRIGGER_MARGIN_RAD
                ),
                "bounded_state_triggered_recovery_active": True,
                "bounded_state_triggered_change_source_action": False,
                "bounded_state_triggered_task_outcome_informed": False,
                "adaptive_extended_recovery_evaluated": bool(
                    screened_extended_count
                ),
                "incremental_extended_candidate_evaluated_count": (
                    screened_extended_count
                ),
                "incremental_extended_search_short_circuit_identity": (
                    screened_extended_count <= 1
                ),
                "bounded_candidate_priority": (
                    "state_offset_ranked_standard_then_registered_recovery"
                ),
                "bounded_state_target_offset_rad": STATE_TARGET_OFFSET_RAD,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointRollingPreboundRecoveryEnvironment
    predecessor.MultiJointRollingPreboundRecoveryEnvironment = (
        MultiJointBoundedStateTriggeredRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointRollingPreboundRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.11 episode without changing the source policy action."""

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
            "bounded_state_triggered_recovery_active": l2_enabled,
            "bounded_state_trigger_margin_rad": (
                STATE_TRIGGER_MARGIN_RAD if l2_enabled else None
            ),
            "bounded_guarded_candidate_rollout_budget": (
                MAX_GUARDED_CANDIDATE_ROLLOUTS if l2_enabled else None
            ),
            "bounded_state_target_offset_rad": (
                STATE_TARGET_OFFSET_RAD if l2_enabled else None
            ),
            "unguarded_shadow_rollout_active": False,
            "bounded_state_triggered_change_source_action": False,
            "bounded_state_triggered_outcome_informed_successor": True,
            "bounded_state_triggered_hard_real_time_claim": False,
            "bounded_state_triggered_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.11 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
