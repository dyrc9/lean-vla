#!/usr/bin/env python3
"""v15.6 adaptive force-constrained recovery with a bounded fallback search."""

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
    run_l2_predictive_virtual_brake_v15_force_constrained_recovery as predecessor,
)


v14 = predecessor.v14
priority = predecessor.priority
RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_6_"
    "adaptive_force_constrained_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.6."
    "adaptive-force-constrained-recovery.step"
)
JOINT_COUNT = predecessor.JOINT_COUNT
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
PROACTIVE_TRIGGER_MARGIN_RAD = 0.16
GUARD_SOLIMP = predecessor.GUARD_SOLIMP
RECOVERY_GUARD_MARGIN_RAD = predecessor.RECOVERY_GUARD_MARGIN_RAD
SOFT_GUARD_SOLREF = predecessor.FORCE_CONSTRAINED_GUARD_SOLREF
FALLBACK_GUARD_SOLREFS = ((0.004, 1.0),)
FALLBACK_GUARD_SOLREF = FALLBACK_GUARD_SOLREFS[0]
RECOVERY_LADDER_FRACTIONS = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)


class AdaptiveForceRecoveryError(RuntimeError):
    """Raised when v15.6 cannot bind its auditable candidate search."""


class AdaptiveForceRecoveryConfig(predecessor.ForceConstrainedRecoveryConfig):
    """Expose a fixed recovery ladder while keeping registered thresholds."""

    def __init__(self, current_edge_margin_rad: float | None) -> None:
        super().__init__(current_edge_margin_rad)
        object.__setattr__(
            self, "trigger_margin_rad", PROACTIVE_TRIGGER_MARGIN_RAD
        )

    @property
    def recovery_margins_rad(self) -> tuple[float, ...]:
        edge = self.current_edge_margin_rad
        if edge is None:
            return (RECOVERY_GUARD_MARGIN_RAD,)
        ladder = tuple(
            edge - fraction * (edge - RECOVERY_GUARD_MARGIN_RAD)
            for fraction in RECOVERY_LADDER_FRACTIONS
        )
        return (edge, *ladder, RECOVERY_GUARD_MARGIN_RAD)

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        return (*BRAKE_MARGINS_RAD, *self.recovery_margins_rad)


def _candidate_groups(
    config: AdaptiveForceRecoveryConfig,
) -> tuple[tuple[dict[str, Any], ...], ...]:
    primary_recovery = (
        config.recovery_margins_rad
        if len(config.recovery_margins_rad) == 1
        else (
            config.recovery_margins_rad[0],
            config.recovery_margins_rad[-1],
        )
    )
    primary = tuple(
        {
            "guard_margin_rad": margin,
            "guard_solref": SOFT_GUARD_SOLREF,
            "profile_id": "soft_primary",
            "recovery_candidate": margin not in BRAKE_MARGINS_RAD,
            "fallback_profile": False,
        }
        for margin in (*BRAKE_MARGINS_RAD, *primary_recovery)
    )
    extended = tuple(
        {
            "guard_margin_rad": margin,
            "guard_solref": SOFT_GUARD_SOLREF,
            "profile_id": "soft_extended_recovery",
            "recovery_candidate": True,
            "fallback_profile": False,
        }
        for margin in config.recovery_margins_rad[1:-1]
    )
    fallbacks = tuple(
        tuple(
            {
                "guard_margin_rad": margin,
                "guard_solref": solref,
                "profile_id": (
                    "stiff_recovery_fallback_"
                    + str(solref[0]).replace(".", "_")
                ),
                "recovery_candidate": True,
                "fallback_profile": True,
            }
            for margin in config.recovery_margins_rad
        )
        for solref in FALLBACK_GUARD_SOLREFS
    )
    groups = [primary]
    if extended:
        groups.append(extended)
    groups.extend(fallbacks)
    return tuple(groups)


def _profile_configurations(
    self: Any,
    *,
    qidx: np.ndarray,
    vidx: np.ndarray,
    risks: list[dict[str, Any]],
    guard_margin_rad: float,
    guard_solref: tuple[float, float],
) -> list[dict[str, Any]]:
    return [
        v14.core._configure_virtual_joint_guard(
            env=self._env,
            qidx=qidx,
            vidx=vidx,
            target_joint_index=int(risk["joint_index"]),
            target_joint_side=str(risk["side"]),
            guard_margin_rad=guard_margin_rad,
            guard_solref=guard_solref,
            guard_solimp=self._config.guard_solimp,
        )
        for risk in risks
    ]


def _adaptive_force_core_step(self: Any, action: Any) -> Any:
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
    snapshot = v14.core.capture_warmstart_policy_shadow_snapshot(
        self._env,
        robot,
        source_id=f"v15.6:adaptive-force:step{runner_step_id}",
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
    evaluated_candidates: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    all_candidate_restores = True
    fallback_profile_evaluated = False
    extended_recovery_evaluated = False
    evaluated_inside_candidate_count = 0

    if shadow_restore_identity and triggered:
        for group_index, group in enumerate(_candidate_groups(self._config)):
            if group_index >= 1 and selected is not None:
                break
            group_is_fallback = bool(
                group and group[0]["fallback_profile"] is True
            )
            group_is_extended = bool(
                group
                and group[0]["profile_id"] == "soft_extended_recovery"
            )
            if group_is_extended:
                extended_recovery_evaluated = True
            if group_is_fallback:
                # The inherited recovery enrichers require one row per margin.
                # Give failed soft-recovery attempts unique compatibility-only
                # margins while the fallback rows pass through the old layers.
                # Their physical margins are restored before the final audit is
                # returned to the caller.
                for index, row in enumerate(candidates):
                    if row["recovery_candidate"] is True:
                        if "physical_guard_margin_rad" not in row:
                            row["physical_guard_margin_rad"] = row[
                                "guard_margin_rad"
                            ]
                        row["guard_margin_rad"] = -1000.0 - float(index)
            fallback_profile_evaluated = group_is_fallback
            for spec in group:
                margin = float(spec["guard_margin_rad"])
                solref = tuple(spec["guard_solref"])
                configurations = _profile_configurations(
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
                common = {
                    "guard_margin_rad": margin,
                    "guard_solref": list(solref),
                    "candidate_profile_id": str(spec["profile_id"]),
                    "fallback_profile": bool(spec["fallback_profile"]),
                    "recovery_candidate": bool(spec["recovery_candidate"]),
                }
                if not inside:
                    row = {
                            **common,
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
                    candidates.append(row)
                    evaluated_candidates.append(row)
                    continue
                evaluated_inside_candidate_count += 1
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
                metrics = predecessor._risk_force_metrics(
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
                force_feasible = predecessor._force_feasible(
                    metrics,
                    recovery_candidate=bool(spec["recovery_candidate"]),
                )
                eligible = bool(base_eligible and force_feasible)
                row = {
                    **common,
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
                evaluated_candidates.append(row)
                if selected is None and eligible:
                    selected = {**row, "configurations": configurations}

    deadlock_reason = None
    if not shadow_restore_identity:
        deadlock_reason = "shadow_restore_identity_failed"
    elif triggered and selected is None:
        deadlock_reason = "no_adaptive_force_feasible_guard_candidate"
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
        transition = v14.fresh3._terminal_shadow_observation_deadlock_transition(
            self._env, unguarded_transition, reason=deadlock_reason
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
        scope_restored = v14._scope_restored(self._env, robot, configurations)
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
            "executed_action_digest": action_digest if deadlock_reason is None else None,
            "exact_action_identity": deadlock_reason is None,
            "current_joint_side_margins": v14._margin_rows(current_margins),
            "unguarded_predicted_joint_side_margins": v14._margin_rows(unguarded),
            "selected_predicted_joint_side_margins": selected_margins,
            "actual_joint_side_margins": v14._margin_rows(actual),
            "risk_sides": risks,
            "current_target_margin_rad": float(np.min(current_margins)),
            "unguarded_predicted_minimum_margin_rad": unguarded_minimum,
            "unguarded_predicted_target_margin_rad": unguarded_minimum,
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
            "shadow_restore_identity": shadow_restore_identity,
            "candidate_restore_identity": all_candidate_restores if candidates else True,
            "guard_scope_restored": scope_restored,
            "candidate_count": len(evaluated_candidates),
            "eligible_candidate_count": sum(
                row["eligible"] for row in evaluated_candidates
            ),
            "shadow_env_step_count": 1
            + evaluated_inside_candidate_count,
            "screen_latency_seconds": screen_latency,
            "maximum_abs_target_constraint_force": actual_force,
            "maximum_abs_guarded_constraint_force": actual_force,
            "torque_bound_violation_count": actual_torque_violations,
            "fallback_profile_evaluated": fallback_profile_evaluated,
            "extended_recovery_evaluated": extended_recovery_evaluated,
            "_adaptive_all_evaluated_candidates": evaluated_candidates,
            "candidates": candidates,
        }
    )
    return transition


class MultiJointAdaptiveForceRecoveryEnvironment(
    predecessor.predecessor.MultiJointDynamicStateRecoveryEnvironment
):
    """Search soft recovery candidates, then a bounded stiff fallback."""

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        original_step = v14.MultiJointPredictiveVirtualBrakeEnvironment.step
        original_config = priority.CurrentEdgePriorityRecoveryConfig
        v14.MultiJointPredictiveVirtualBrakeEnvironment.step = (
            _adaptive_force_core_step
        )
        priority.CurrentEdgePriorityRecoveryConfig = AdaptiveForceRecoveryConfig
        try:
            transition = super().step(action)
        finally:
            priority.CurrentEdgePriorityRecoveryConfig = original_config
            v14.MultiJointPredictiveVirtualBrakeEnvironment.step = original_step
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise AdaptiveForceRecoveryError(
                "v15.6 environment produced a non-object audit"
            )
        candidates = audit.get("candidates", [])
        all_candidates = audit.pop(
            "_adaptive_all_evaluated_candidates", candidates
        )
        if not isinstance(candidates, list) or not isinstance(
            all_candidates, list
        ):
            raise AdaptiveForceRecoveryError("v15.6 environment lacks candidates")
        selected_margin = audit.get("selected_guard_margin_rad")
        selected_profile = audit.get("selected_candidate_profile_id")
        selected_rows = [
            row
            for row in all_candidates
            if selected_margin is not None
            and float(row["guard_margin_rad"]) == float(selected_margin)
            and row["candidate_profile_id"] == selected_profile
        ]
        if len(selected_rows) > 1:
            raise AdaptiveForceRecoveryError(
                "v15.6 selected candidate identity is ambiguous"
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
                    float(audit["post_step_maximum_abs_risk_constraint_force"]),
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
            raise AdaptiveForceRecoveryError(
                "v15.6 predicted and executed post-step force differ"
            )
        standard_base_eligible = sum(
            row.get("base_safety_eligible") is True
            for row in all_candidates
            if row.get("recovery_candidate") is not True
        )
        baseline_would_deadlock = bool(
            audit.get("triggered") is True and standard_base_eligible == 0
        )
        current_edge = audit.get(
            "current_edge_recovery_configured_margin_rad"
        )
        recovery_selected = bool(
            selected is not None and selected["recovery_candidate"] is True
        )
        fallback_selected = bool(
            selected is not None and selected["fallback_profile"] is True
        )
        extended_selected = bool(
            selected is not None
            and selected["candidate_profile_id"]
            == "soft_extended_recovery"
        )
        for row in all_candidates:
            if "physical_guard_margin_rad" in row:
                row["compatibility_guard_margin_rad"] = row[
                    "guard_margin_rad"
                ]
                row["guard_margin_rad"] = row.pop(
                    "physical_guard_margin_rad"
                )
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "force_constrained_recovery_active": bool(
                    audit.get("enabled") is True
                ),
                "adaptive_force_recovery_active": bool(
                    audit.get("enabled") is True
                ),
                "adaptive_proactive_trigger_margin_rad": (
                    PROACTIVE_TRIGGER_MARGIN_RAD
                ),
                "force_constrained_guard_solref": (
                    list(selected["guard_solref"])
                    if selected is not None
                    else list(SOFT_GUARD_SOLREF)
                ),
                "candidate_post_force_prediction_active": bool(
                    audit.get("enabled") is True
                ),
                "selected_post_force_prediction_execution_identity": (
                    prediction_identity
                ),
                "base_safety_eligible_candidate_count": sum(
                    row.get("base_safety_eligible") is True
                    for row in all_candidates
                ),
                "force_feasible_candidate_count": sum(
                    row.get("force_feasible") is True
                    and row.get("base_safety_eligible") is True
                    for row in all_candidates
                ),
                "force_rejected_base_eligible_candidate_count": sum(
                    row.get("base_safety_eligible") is True
                    and row.get("force_feasible") is not True
                    for row in all_candidates
                ),
                "selected_force_feasible": bool(
                    selected is None or selected.get("force_feasible") is True
                ),
                "v14_baseline_eligible_candidate_count": standard_base_eligible,
                "v14_baseline_would_deadlock": baseline_would_deadlock,
                "floor_guard_recovery_selected": bool(
                    selected_margin is not None
                    and float(selected_margin) == RECOVERY_GUARD_MARGIN_RAD
                ),
                "current_edge_recovery_selected": bool(
                    recovery_selected
                    and selected_margin is not None
                    and current_edge is not None
                    and np.isclose(
                        float(selected_margin),
                        float(current_edge),
                        rtol=0.0,
                        atol=predecessor.CURRENT_EDGE_EPSILON_RAD * 2.0,
                    )
                ),
                "floor_or_current_edge_recovery_selected": recovery_selected,
                "floor_or_current_edge_recovery_prevented_deadlock": bool(
                    baseline_would_deadlock
                    and recovery_selected
                    and audit.get("deadlock") is False
                ),
                "adaptive_recovery_ladder_active": True,
                "adaptive_extended_recovery_evaluated": bool(
                    audit.get("extended_recovery_evaluated") is True
                ),
                "adaptive_extended_recovery_selected": extended_selected,
                "adaptive_fallback_profile_evaluated": bool(
                    audit.get("fallback_profile_evaluated") is True
                ),
                "adaptive_fallback_profile_selected": fallback_selected,
                "selected_candidate_profile_id": selected_profile,
                "force_constraints_change_source_action": False,
                "force_constraints_task_outcome_informed": False,
                "force_constraints_physical_authority_claim": False,
                "candidates": all_candidates,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.predecessor.MultiJointDynamicStateRecoveryEnvironment
    predecessor.predecessor.MultiJointDynamicStateRecoveryEnvironment = (
        MultiJointAdaptiveForceRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.predecessor.MultiJointDynamicStateRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.6 episode without changing the source policy action."""

    with _patched_predecessor_environment():
        payload = predecessor.predecessor.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    l2_enabled = bool(metadata["l2_execution_integrity"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "adaptive_force_recovery_active": l2_enabled,
            "adaptive_soft_guard_solref": (
                list(SOFT_GUARD_SOLREF) if l2_enabled else None
            ),
            "adaptive_fallback_guard_solref": (
                [list(row) for row in FALLBACK_GUARD_SOLREFS]
                if l2_enabled
                else None
            ),
            "adaptive_recovery_ladder_fractions": (
                list(RECOVERY_LADDER_FRACTIONS) if l2_enabled else None
            ),
            "adaptive_proactive_trigger_margin_rad": (
                PROACTIVE_TRIGGER_MARGIN_RAD if l2_enabled else None
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
            "note": "Import through a separately frozen v15.6 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
