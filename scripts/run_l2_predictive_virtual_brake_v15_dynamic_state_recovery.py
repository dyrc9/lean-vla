#!/usr/bin/env python3
"""v15.4 recovery with gripper and dynamic-obstacle shadow state."""

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

from proofalign.policy_shadow_dynamic_state_v15 import (  # noqa: E402
    DynamicStatePolicyShadowRestoreAssessment,
    capture_dynamic_state_policy_shadow_snapshot,
    restore_dynamic_state_policy_shadow_snapshot,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_force_attributed_recovery as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_4_"
    "dynamic_state_force_attributed_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.4."
    "dynamic-state-force-attributed-recovery.step"
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
RECOVERY_GUARD_MARGIN_RAD = predecessor.RECOVERY_GUARD_MARGIN_RAD
RECOVERY_MARGIN_EPSILON_RAD = predecessor.RECOVERY_MARGIN_EPSILON_RAD
CURRENT_EDGE_EPSILON_RAD = predecessor.CURRENT_EDGE_EPSILON_RAD


class DynamicStateRecoveryError(RuntimeError):
    """Raised when a v15.4 shadow loses runtime-side state identity."""


def _gripper_action(robot: Any) -> list[float]:
    values = np.asarray(robot.gripper.current_action, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise DynamicStateRecoveryError(
            "v15.4 gripper current_action is malformed"
        )
    return [float(value) for value in values]


@contextmanager
def _patched_dynamic_state_shadow(
    assessments: list[DynamicStatePolicyShadowRestoreAssessment],
) -> Iterator[None]:
    """Route one v15.4 screen through the versioned dynamic snapshot."""

    core = predecessor.v14_core.core
    original_capture = core.capture_warmstart_policy_shadow_snapshot
    original_restore = core.restore_warmstart_policy_shadow_snapshot
    original_identity = core._restore_identity

    def capture(env: Any, robot: Any, *, source_id: str) -> Any:
        return capture_dynamic_state_policy_shadow_snapshot(
            env, robot, source_id=source_id
        )

    def restore(env: Any, robot: Any, snapshot: Any) -> Any:
        assessment = restore_dynamic_state_policy_shadow_snapshot(
            env, robot, snapshot
        )
        assessments.append(assessment)
        return assessment

    def identity(assessment: Any) -> bool:
        return bool(
            original_identity(assessment)
            and isinstance(
                assessment,
                DynamicStatePolicyShadowRestoreAssessment,
            )
            and assessment.runtime_side_state_identity
        )

    core.capture_warmstart_policy_shadow_snapshot = capture
    core.restore_warmstart_policy_shadow_snapshot = restore
    core._restore_identity = identity
    try:
        yield
    finally:
        core.capture_warmstart_policy_shadow_snapshot = original_capture
        core.restore_warmstart_policy_shadow_snapshot = original_restore
        core._restore_identity = original_identity


class MultiJointDynamicStateRecoveryEnvironment(
    predecessor.MultiJointForceAttributedRecoveryEnvironment
):
    """Preserve v15.3 control while restoring runtime-side shadow state."""

    def step(self, action: Any) -> Any:
        before_observation_count = len(self.observations)
        robot, _qidx, _vidx, _limits = self._arrays()
        pre_action = _gripper_action(robot)
        assessments: list[
            DynamicStatePolicyShadowRestoreAssessment
        ] = []
        with _patched_dynamic_state_shadow(assessments):
            transition = super().step(action)
        if len(self.observations) == before_observation_count:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise DynamicStateRecoveryError(
                "v15.4 environment produced a non-object audit"
            )
        expected_restore_count = int(audit["shadow_env_step_count"])
        if audit.get("enabled") is True and (
            len(assessments) != expected_restore_count
            or any(
                assessment.runtime_side_state_identity is not True
                for assessment in assessments
            )
        ):
            raise DynamicStateRecoveryError(
                "v15.4 dynamic restore count or identity differs"
            )
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "dynamic_state_shadow_active": bool(
                    audit.get("enabled") is True
                ),
                "pre_step_gripper_current_action": pre_action,
                "post_step_gripper_current_action": _gripper_action(robot),
                "dynamic_state_restore_assessment_count": len(assessments),
                "dynamic_motion_generator_count": (
                    assessments[0].dynamic_motion_generator_count
                    if assessments
                    else 0
                ),
                "dynamic_state_restore_identity": bool(
                    audit.get("enabled") is not True
                    or all(
                        assessment.runtime_side_state_identity
                        for assessment in assessments
                    )
                ),
                "dynamic_state_snapshot_changes_source_action": False,
                "dynamic_state_snapshot_task_outcome_informed": False,
                "dynamic_state_snapshot_physical_authority_claim": False,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointForceAttributedRecoveryEnvironment
    predecessor.MultiJointForceAttributedRecoveryEnvironment = (
        MultiJointDynamicStateRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointForceAttributedRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.4 episode without changing exact source actions."""

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
            "dynamic_state_shadow_active": l2_enabled,
            "dynamic_state_snapshot_successor": True,
            "dynamic_state_snapshot_changes_source_action": False,
            "dynamic_state_snapshot_outcome_informed_successor": True,
            "dynamic_state_snapshot_physical_authority_claim": False,
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
                "Import through a separately frozen v15.4 development "
                "protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
