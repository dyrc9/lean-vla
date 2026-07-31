#!/usr/bin/env python3
"""Disabled-arm plumbing successor for the v14 all-joint runner.

Development1 completed two L2-enabled episodes, then failed before the first
disabled-arm rollout because the inherited v13 disabled path requested a
single target joint from the all-joint configuration.  This successor changes
only that disabled path.  L2 screening, guard selection, margins, thresholds,
actions, workloads, and seeds remain unchanged.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v14_"
    "multijoint_fresh2"
)
BRAKE_AUDIT_SCHEMA = predecessor.BRAKE_AUDIT_SCHEMA
JOINT_COUNT = predecessor.JOINT_COUNT
JOINT_SIDES = predecessor.JOINT_SIDES
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLREF = predecessor.GUARD_SOLREF
GUARD_SOLIMP = predecessor.GUARD_SOLIMP


class MultiJointPredictiveVirtualBrakeFresh2Environment(
    predecessor.MultiJointPredictiveVirtualBrakeEnvironment
):
    """Record disabled arms without invoking v13 single-target helpers."""

    def step(self, action: Any) -> Any:
        runner_step_id = self._call_index
        if self._enabled:
            return super().step(action)
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return self._env.step(action)

        _robot, qidx, _vidx, limits = self._arrays()
        action_digest = predecessor.core._action_digest(action)
        transition = self._env.step(action)
        actual = self._margin_matrix(qidx, limits)
        actual_minimum = float(np.min(actual))
        self.observations.append(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "runner_step_id": runner_step_id,
                "enabled": False,
                "screen_performed": False,
                "multi_joint_audit": True,
                "joint_side_scope_count": 14,
                "triggered": False,
                "intervened": False,
                "deadlock": False,
                "deadlock_reason": None,
                "source_action_digest": action_digest,
                "executed_action_digest": action_digest,
                "exact_action_identity": True,
                "current_joint_side_margins": None,
                "unguarded_predicted_joint_side_margins": None,
                "selected_predicted_joint_side_margins": None,
                "actual_joint_side_margins": (
                    predecessor._margin_rows(actual)
                ),
                "risk_sides": [],
                "current_target_margin_rad": None,
                "unguarded_predicted_minimum_margin_rad": None,
                "unguarded_predicted_target_margin_rad": None,
                "selected_guard_margin_rad": None,
                "selected_predicted_minimum_margin_rad": None,
                "selected_predicted_target_margin_rad": None,
                "actual_minimum_margin_rad": actual_minimum,
                "actual_target_margin_rad": actual_minimum,
                "actual_worst_margin_rad": actual_minimum,
                "prediction_execution_margin_error_rad": None,
                "shadow_restore_identity": None,
                "candidate_restore_identity": None,
                "guard_scope_restored": None,
                "candidate_count": 0,
                "eligible_candidate_count": 0,
                "shadow_env_step_count": 0,
                "screen_latency_seconds": 0.0,
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
        MultiJointPredictiveVirtualBrakeFresh2Environment
    )
    try:
        yield
    finally:
        predecessor.MultiJointPredictiveVirtualBrakeEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v14 with only its disabled-arm integration path replaced."""

    with _patched_predecessor_environment():
        payload = predecessor.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "v14_multijoint_fresh2_successor": True,
            "fresh2_disabled_arm_single_target_dependency_removed": True,
            "fresh2_scientific_parameters_changed": False,
            "fresh2_workload_seed_or_arm_order_changed": False,
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
                "Import through the separately frozen v14 Fresh2 "
                "development protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
