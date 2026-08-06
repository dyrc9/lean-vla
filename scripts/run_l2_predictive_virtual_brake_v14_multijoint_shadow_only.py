#!/usr/bin/env python3
"""Same-schedule shadow-only ablation for the v14 all-joint brake.

For L2-labelled arms, every policy action is shadowed once and the complete
fourteen-side margin audit is retained.  The snapshot is then restored and
the exact source action is dispatched without candidate evaluation, virtual
guarding, intervention, or deadlock synthesis.  Disabled arms retain the
Fresh2 direct post-state audit.

This is an outcome-disclosed causal-development control.  It isolates the
effect of applying the virtual brake from the effect of shadow execution and
snapshot restoration; it is not an independent qualification experiment.
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
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as predecessor  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_fresh2 as fresh2  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v14_"
    "multijoint_shadow_only"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v14."
    "multijoint-shadow-only.step"
)
JOINT_COUNT = predecessor.JOINT_COUNT
JOINT_SIDES = predecessor.JOINT_SIDES
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLREF = predecessor.GUARD_SOLREF
GUARD_SOLIMP = predecessor.GUARD_SOLIMP


class PredictiveVirtualBrakeV14ShadowOnlyError(RuntimeError):
    """Raised when the shadow-only causal control is not auditable."""


class MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment(
    fresh2.MultiJointPredictiveVirtualBrakeFresh2Environment
):
    """Shadow and restore each L2 action, then dispatch it unguarded."""

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
                self.observations[-1].update(
                    {
                        "schema": BRAKE_AUDIT_SCHEMA,
                        "shadow_only": False,
                        "intervention_authority_enabled": False,
                        "guard_candidate_evaluation_performed": False,
                    }
                )
            return transition

        self._call_index += 1
        robot, qidx, _vidx, limits = self._arrays()
        action_digest = predecessor.core._action_digest(action)
        screen_start = perf_counter()
        snapshot = (
            predecessor.core.capture_warmstart_policy_shadow_snapshot(
                self._env,
                robot,
                source_id=(
                    "v14:multijoint-shadow-only:"
                    f"step{runner_step_id}"
                ),
            )
        )
        current = self._margin_matrix(qidx, limits)
        self._env.step(action)
        unguarded = self._margin_matrix(qidx, limits)
        shadow_restore = (
            predecessor.core.restore_warmstart_policy_shadow_snapshot(
                self._env,
                robot,
                snapshot,
            )
        )
        shadow_restore_identity = predecessor.core._restore_identity(
            shadow_restore
        )
        screen_latency = perf_counter() - screen_start
        if not shadow_restore_identity:
            raise PredictiveVirtualBrakeV14ShadowOnlyError(
                "shadow-only snapshot restoration lost identity"
            )

        risks = predecessor._risk_sides(
            current,
            unguarded,
            trigger_margin_rad=self._config.trigger_margin_rad,
        )
        transition = self._env.step(action)
        actual = self._margin_matrix(qidx, limits)
        errors = np.abs(actual - unguarded)
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
                "shadow_only": True,
                "intervention_authority_enabled": False,
                "guard_candidate_evaluation_performed": False,
                "triggered": bool(risks),
                "intervened": False,
                "deadlock": False,
                "deadlock_reason": None,
                "source_action_digest": action_digest,
                "executed_action_digest": action_digest,
                "exact_action_identity": True,
                "current_joint_side_margins": (
                    predecessor._margin_rows(current)
                ),
                "unguarded_predicted_joint_side_margins": (
                    predecessor._margin_rows(unguarded)
                ),
                "selected_predicted_joint_side_margins": None,
                "actual_joint_side_margins": (
                    predecessor._margin_rows(actual)
                ),
                "risk_sides": risks,
                "current_target_margin_rad": float(np.min(current)),
                "unguarded_predicted_minimum_margin_rad": (
                    unguarded_minimum
                ),
                "unguarded_predicted_target_margin_rad": (
                    unguarded_minimum
                ),
                "selected_guard_margin_rad": None,
                "selected_predicted_minimum_margin_rad": None,
                "selected_predicted_target_margin_rad": None,
                "actual_minimum_margin_rad": actual_minimum,
                "actual_target_margin_rad": actual_minimum,
                "actual_worst_margin_rad": actual_minimum,
                "prediction_execution_margin_error_rad": float(
                    abs(actual_minimum - unguarded_minimum)
                ),
                "prediction_execution_maximum_side_error_rad": float(
                    np.max(errors)
                ),
                "shadow_restore_identity": True,
                "candidate_restore_identity": True,
                "guard_scope_restored": None,
                "candidate_count": 0,
                "eligible_candidate_count": 0,
                "shadow_env_step_count": 1,
                "screen_latency_seconds": screen_latency,
                "maximum_abs_target_constraint_force": 0.0,
                "maximum_abs_guarded_constraint_force": 0.0,
                "torque_bound_violation_count": 0,
                "candidates": [],
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointPredictiveVirtualBrakeEnvironment
    predecessor.MultiJointPredictiveVirtualBrakeEnvironment = (
        MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointPredictiveVirtualBrakeEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v14 episode with observation but no brake authority."""

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
            "predictive_virtual_brake_active": l2_enabled,
            "predictive_virtual_brake_simultaneous_guarding": False,
            "predictive_virtual_brake_shadow_monitor_active": l2_enabled,
            "predictive_virtual_brake_shadow_only": l2_enabled,
            "predictive_virtual_brake_intervention_authority": False,
            "predictive_virtual_brake_guard_candidate_evaluation": False,
            "shadow_only_same_schedule_causal_control": True,
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
            "shadow_only": True,
            "note": (
                "Import through the separately frozen v14 shadow-only "
                "causal-development protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
