#!/usr/bin/env python3
"""v15.9 pre-step observed-force calibrated shadow recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery as predecessor,
)


_INCREMENTAL_BASE_CLASS = (
    predecessor.predecessor.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
)
RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_9_"
    "pre_step_observed_force_calibrated_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.9."
    "pre-step-observed-force-calibrated-recovery.step"
)


class PreStepCalibratedRecoveryError(RuntimeError):
    """Raised when the v15.9 setup-calibration contract differs."""


def _attach_setup_calibration(
    audit: dict[str, Any], calibration: Mapping[str, Any]
) -> None:
    if (
        calibration.get("interface_available") is not True
        or calibration.get("active") is not True
        or calibration.get("bind_identity") is not True
        or int(calibration.get("candidate_count", 0))
        != len(predecessor.MODEL_BANK)
    ):
        raise PreStepCalibratedRecoveryError(
            "v15.9 setup calibration is unavailable or incomplete"
        )
    original_screen_latency = float(audit["screen_latency_seconds"])
    audit.update(
        {
            "schema": BRAKE_AUDIT_SCHEMA,
            "pre_step_shadow_calibration_active": True,
            "pre_step_shadow_calibration_reused": True,
            "pre_step_shadow_model_bank_candidate_count": int(
                calibration["candidate_count"]
            ),
            "pre_step_shadow_selected_candidate_id": calibration[
                "selected_candidate_id"
            ],
            "pre_step_shadow_selected_residual": calibration[
                "selected_residual"
            ],
            "pre_step_shadow_minimum_residual_candidate_count": int(
                calibration["minimum_residual_candidate_count"]
            ),
            "pre_step_shadow_bind_identity": True,
            "pre_step_shadow_calibration_latency_seconds": float(
                calibration["latency_seconds"]
            ),
            "pre_step_shadow_calibration_outside_action_critical_path": True,
            "pre_step_shadow_calibration_change_source_action": False,
            "pre_step_shadow_calibration_task_outcome_informed": False,
        }
    )
    if float(audit["screen_latency_seconds"]) != original_screen_latency:
        raise PreStepCalibratedRecoveryError(
            "v15.9 setup calibration changed action screen latency"
        )


class MultiJointPreStepCalibratedRecoveryEnvironment(
    predecessor.MultiJointObservedForceCalibratedRecoveryEnvironment
):
    """Bind one observed-force shadow model before action screening starts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pre_step_calibration = predecessor._calibrate_shadow_model(self._env)
        if self._pre_step_calibration["active"] is not True:
            raise PreStepCalibratedRecoveryError(
                "v15.9 runtime lacks the setup-calibration interface"
            )

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        transition = _INCREMENTAL_BASE_CLASS.step(self, action)
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise PreStepCalibratedRecoveryError(
                "v15.9 environment produced a non-object audit"
            )
        _attach_setup_calibration(audit, self._pre_step_calibration)
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointObservedForceCalibratedRecoveryEnvironment
    predecessor.MultiJointObservedForceCalibratedRecoveryEnvironment = (
        MultiJointPreStepCalibratedRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointObservedForceCalibratedRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.9 episode without changing the source policy action."""

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
            "pre_step_observed_force_shadow_calibration_active": l2_enabled,
            "pre_step_observed_force_shadow_calibration_interface": (
                predecessor.CALIBRATION_INTERFACE if l2_enabled else None
            ),
            "pre_step_observed_force_shadow_model_bank": (
                [dict(row) for row in predecessor.MODEL_BANK]
                if l2_enabled
                else None
            ),
            "pre_step_calibration_outside_action_critical_path": l2_enabled,
            "pre_step_calibration_change_source_action": False,
            "pre_step_calibration_outcome_informed_successor": True,
            "pre_step_calibration_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.9 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
