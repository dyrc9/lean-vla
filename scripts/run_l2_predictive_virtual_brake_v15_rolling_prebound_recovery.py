#!/usr/bin/env python3
"""v15.10 rolling prebound observed-force shadow recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_pre_step_calibrated_recovery as predecessor,
)


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_10_"
    "rolling_prebound_observed_force_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.10."
    "rolling-prebound-observed-force-recovery.step"
)


class RollingPreboundRecoveryError(RuntimeError):
    """Raised when the v15.10 rolling calibration contract differs."""


class MultiJointRollingPreboundRecoveryEnvironment(
    predecessor.MultiJointPreStepCalibratedRecoveryEnvironment
):
    """Use a prebound shadow, then prepare the next step after execution."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._prebound_generation = 0

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        used_calibration = self._pre_step_calibration
        used_generation = self._prebound_generation
        transition = predecessor._INCREMENTAL_BASE_CLASS.step(self, action)
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise RollingPreboundRecoveryError(
                "v15.10 environment produced a non-object audit"
            )
        predecessor._attach_setup_calibration(audit, used_calibration)
        next_calibration = (
            predecessor.predecessor._calibrate_shadow_model(self._env)
        )
        if next_calibration["active"] is not True:
            raise RollingPreboundRecoveryError(
                "v15.10 rolling calibration is unavailable"
            )
        self._pre_step_calibration = next_calibration
        self._prebound_generation += 1
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "rolling_prebound_shadow_calibration_active": True,
                "rolling_prebound_used_generation": used_generation,
                "rolling_prebound_next_generation": self._prebound_generation,
                "rolling_prebound_next_selected_candidate_id": next_calibration[
                    "selected_candidate_id"
                ],
                "rolling_prebound_next_selected_residual": next_calibration[
                    "selected_residual"
                ],
                "rolling_prebound_update_latency_seconds": float(
                    next_calibration["latency_seconds"]
                ),
                "rolling_prebound_update_outside_action_screen": True,
                "rolling_prebound_change_source_action": False,
                "rolling_prebound_task_outcome_informed": False,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointPreStepCalibratedRecoveryEnvironment
    predecessor.MultiJointPreStepCalibratedRecoveryEnvironment = (
        MultiJointRollingPreboundRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointPreStepCalibratedRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.10 episode without changing the source policy action."""

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
            "rolling_prebound_shadow_calibration_active": l2_enabled,
            "rolling_prebound_update_outside_action_screen": l2_enabled,
            "rolling_prebound_change_source_action": False,
            "rolling_prebound_outcome_informed_successor": True,
            "rolling_prebound_hard_real_time_claim": False,
            "rolling_prebound_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.10 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
