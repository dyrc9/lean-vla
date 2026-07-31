#!/usr/bin/env python3
"""Shadow-and-restore-only causal ablation for the v13 execution path."""

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
from scripts import run_l2_predictive_virtual_brake_v13 as core  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v13_fresh3 as fresh3  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_virtual_brake_v13_shadow_only"
)
BRAKE_AUDIT_SCHEMA = core.BRAKE_AUDIT_SCHEMA
BRAKE_MARGINS_RAD = core.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = core.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = core.SAFE_MARGIN_FLOOR_RAD
TARGET_JOINT_INDEX = core.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = core.TARGET_JOINT_SIDE
DEADLOCK_INFO_KEY = core.DEADLOCK_INFO_KEY
GUARD_SOLREF = core.GUARD_SOLREF
GUARD_SOLIMP = core.GUARD_SOLIMP
PredictiveVirtualBrakeConfig = core.PredictiveVirtualBrakeConfig


class ShadowOnlyPredictiveEnvironment(
    core.PredictiveVirtualBrakeEnvironment
):
    """Replay and restore once, then dispatch nominally without a guard."""

    def step(self, action: Any) -> Any:
        if not self._enabled:
            return super().step(action)
        runner_step_id = self._call_index
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return self._env.step(action)

        robot, qidx, _vidx, limits = self._arrays()
        action_digest = core._action_digest(action)
        screen_start = perf_counter()
        snapshot = core.capture_warmstart_policy_shadow_snapshot(
            self._env,
            robot,
            source_id=(
                "v13:predictive-virtual-brake-shadow-only:"
                f"step{runner_step_id}"
            ),
        )
        current_qpos = np.asarray(
            self._env.sim.data.qpos[qidx], dtype=np.float64
        ).copy()
        current_target = core._target_margin(
            current_qpos,
            limits,
            joint_index=self._config.target_joint_index,
            side=self._config.target_joint_side,
        )
        shadow_transition = self._env.step(action)
        predicted_minimum, predicted_target = self._post_state(
            qidx, limits
        )
        restore = core.restore_warmstart_policy_shadow_snapshot(
            self._env,
            robot,
            snapshot,
        )
        restore_identity = core._restore_identity(restore)
        counterfactual_triggered = bool(
            current_target <= self._config.trigger_margin_rad
            or predicted_target < self._config.trigger_margin_rad
        )
        screen_latency = perf_counter() - screen_start
        if restore_identity:
            transition = self._env.step(action)
            actual_minimum, actual_target = self._post_state(
                qidx, limits
            )
            deadlock_reason = None
        else:
            transition = (
                fresh3._terminal_shadow_observation_deadlock_transition(
                    self._env,
                    shadow_transition,
                    reason="shadow_restore_identity_failed",
                )
            )
            actual_minimum = core._minimum_margin(
                current_qpos, limits
            )
            actual_target = current_target
            deadlock_reason = "shadow_restore_identity_failed"

        self.observations.append(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "runner_step_id": runner_step_id,
                "enabled": True,
                "screen_performed": True,
                "triggered": False,
                "intervened": False,
                "deadlock": deadlock_reason is not None,
                "deadlock_reason": deadlock_reason,
                "source_action_digest": action_digest,
                "executed_action_digest": (
                    action_digest
                    if deadlock_reason is None
                    else None
                ),
                "exact_action_identity": deadlock_reason is None,
                "current_target_margin_rad": current_target,
                "unguarded_predicted_minimum_margin_rad": (
                    predicted_minimum
                ),
                "unguarded_predicted_target_margin_rad": (
                    predicted_target
                ),
                "selected_guard_margin_rad": None,
                "selected_predicted_minimum_margin_rad": None,
                "selected_predicted_target_margin_rad": None,
                "actual_minimum_margin_rad": actual_minimum,
                "actual_target_margin_rad": actual_target,
                "prediction_execution_margin_error_rad": None,
                "shadow_restore_identity": restore_identity,
                "candidate_restore_identity": True,
                "guard_scope_restored": None,
                "candidate_count": 0,
                "eligible_candidate_count": 0,
                "shadow_env_step_count": 1,
                "screen_latency_seconds": screen_latency,
                "maximum_abs_target_constraint_force": 0.0,
                "torque_bound_violation_count": 0,
                "candidates": [],
                "shadow_only_ablation": True,
                "counterfactual_brake_triggered": (
                    counterfactual_triggered
                ),
                "guard_candidate_evaluation_enabled": False,
            }
        )
        return transition


@contextmanager
def _patched_environment() -> Iterator[None]:
    original = core.PredictiveVirtualBrakeEnvironment
    core.PredictiveVirtualBrakeEnvironment = (
        ShadowOnlyPredictiveEnvironment
    )
    try:
        yield
    finally:
        core.PredictiveVirtualBrakeEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run the same execution path with guard selection disabled."""

    with _patched_environment():
        payload = core.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "shadow_only_ablation_active": metadata[
                "l2_execution_integrity"
            ],
            "predictive_virtual_brake_guard_intervention_enabled": (
                False
            ),
            "predictive_virtual_brake_counterfactual_trigger_only": (
                metadata["l2_execution_integrity"]
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
                "Import through the separately frozen v13 shadow-only "
                "ablation protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
