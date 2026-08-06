#!/usr/bin/env python3
"""v15.8 observed-force calibrated shadow recovery.

The method keeps the frozen v15.7 candidate search and registered force
thresholds.  When the runtime exposes the auditable shadow-calibration
interface, it selects the registered physics model whose pre-step constraint
force best matches the observed plant before any predictive rollout.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import math
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_incremental_adaptive_force_recovery as predecessor,
)


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_8_"
    "observed_force_calibrated_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.8."
    "observed-force-calibrated-recovery.step"
)
CALIBRATION_INTERFACE = "proofalign.observed-force-shadow-calibrator.v1"
MODEL_BANK = (
    {
        "candidate_id": "nominal",
        "parameter_family": "nominal",
        "scale": 1.0,
    },
    {
        "candidate_id": "arm_mass_0_8x",
        "parameter_family": "arm_mass",
        "scale": 0.8,
    },
    {
        "candidate_id": "arm_mass_1_2x",
        "parameter_family": "arm_mass",
        "scale": 1.2,
    },
    {
        "candidate_id": "joint_damping_0_7x",
        "parameter_family": "joint_damping",
        "scale": 0.7,
    },
    {
        "candidate_id": "joint_damping_1_3x",
        "parameter_family": "joint_damping",
        "scale": 1.3,
    },
    {
        "candidate_id": "arm_friction_0_7x",
        "parameter_family": "arm_sliding_friction",
        "scale": 0.7,
    },
    {
        "candidate_id": "arm_friction_1_3x",
        "parameter_family": "arm_sliding_friction",
        "scale": 1.3,
    },
)
CALIBRATION_TIE_TOLERANCE = 1e-9


class ObservedForceCalibratedRecoveryError(RuntimeError):
    """Raised when the v15.8 calibration contract differs."""


def _unavailable_calibration() -> dict[str, Any]:
    return {
        "interface_available": False,
        "active": False,
        "candidate_count": 0,
        "selected_candidate_id": None,
        "selected_residual": None,
        "minimum_residual_candidate_count": 0,
        "bind_identity": True,
        "latency_seconds": 0.0,
        "candidate_residuals": [],
    }


def _calibrate_shadow_model(env: Any) -> dict[str, Any]:
    calibrator = getattr(env, "proofalign_shadow_model_calibrator", None)
    if calibrator is None:
        return _unavailable_calibration()
    if (
        getattr(calibrator, "schema", None) != CALIBRATION_INTERFACE
        or not callable(getattr(calibrator, "evaluate", None))
        or not callable(getattr(calibrator, "bind", None))
    ):
        raise ObservedForceCalibratedRecoveryError(
            "v15.8 shadow calibration interface differs"
        )

    started = perf_counter()
    evaluations = calibrator.evaluate(MODEL_BANK)
    if not isinstance(evaluations, list):
        raise ObservedForceCalibratedRecoveryError(
            "v15.8 calibration evaluations are not a list"
        )
    expected_ids = [str(row["candidate_id"]) for row in MODEL_BANK]
    observed: dict[str, float] = {}
    for row in evaluations:
        if not isinstance(row, Mapping):
            raise ObservedForceCalibratedRecoveryError(
                "v15.8 calibration evaluation is not an object"
            )
        candidate_id = str(row.get("candidate_id"))
        residual = float(row.get("maximum_abs_force_residual", math.nan))
        if (
            candidate_id in observed
            or candidate_id not in expected_ids
            or not math.isfinite(residual)
            or residual < 0.0
        ):
            raise ObservedForceCalibratedRecoveryError(
                "v15.8 calibration evaluation identity differs"
            )
        observed[candidate_id] = residual
    if set(observed) != set(expected_ids):
        raise ObservedForceCalibratedRecoveryError(
            "v15.8 calibration model-bank coverage differs"
        )

    selected_id = min(expected_ids, key=lambda key: (observed[key], expected_ids.index(key)))
    selected_residual = observed[selected_id]
    tied = sum(
        residual <= selected_residual + CALIBRATION_TIE_TOLERANCE
        for residual in observed.values()
    )
    binding = calibrator.bind(selected_id)
    if (
        not isinstance(binding, Mapping)
        or binding.get("candidate_id") != selected_id
        or binding.get("bind_identity") is not True
        or binding.get("task_outcome_read") is not False
        or binding.get("actual_parameter_read_by_selector") is not False
    ):
        raise ObservedForceCalibratedRecoveryError(
            "v15.8 calibrated shadow binding differs"
        )
    latency = perf_counter() - started
    return {
        "interface_available": True,
        "active": True,
        "candidate_count": len(observed),
        "selected_candidate_id": selected_id,
        "selected_residual": selected_residual,
        "minimum_residual_candidate_count": tied,
        "bind_identity": True,
        "latency_seconds": latency,
        "candidate_residuals": [
            {
                "candidate_id": candidate_id,
                "maximum_abs_force_residual": observed[candidate_id],
            }
            for candidate_id in expected_ids
        ],
    }


class MultiJointObservedForceCalibratedRecoveryEnvironment(
    predecessor.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
):
    """Calibrate the registered shadow model before v15.7 screening."""

    def step(self, action: Any) -> Any:
        calibration = _calibrate_shadow_model(self._env)
        before = len(self.observations)
        transition = super().step(action)
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise ObservedForceCalibratedRecoveryError(
                "v15.8 environment produced a non-object audit"
            )
        calibration_latency = float(calibration["latency_seconds"])
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "observed_force_shadow_calibration_interface_available": bool(
                    calibration["interface_available"]
                ),
                "observed_force_shadow_calibration_active": bool(
                    calibration["active"]
                ),
                "observed_force_shadow_model_bank_candidate_count": int(
                    calibration["candidate_count"]
                ),
                "observed_force_shadow_selected_candidate_id": calibration[
                    "selected_candidate_id"
                ],
                "observed_force_shadow_selected_residual": calibration[
                    "selected_residual"
                ],
                "observed_force_shadow_minimum_residual_candidate_count": int(
                    calibration["minimum_residual_candidate_count"]
                ),
                "observed_force_shadow_bind_identity": bool(
                    calibration["bind_identity"]
                ),
                "observed_force_shadow_calibration_latency_seconds": (
                    calibration_latency
                ),
                "observed_force_shadow_candidate_residuals": calibration[
                    "candidate_residuals"
                ],
                "observed_force_shadow_calibration_change_source_action": False,
                "observed_force_shadow_calibration_task_outcome_informed": False,
            }
        )
        if "screen_latency_seconds" in audit:
            audit["screen_latency_seconds"] = (
                float(audit["screen_latency_seconds"]) + calibration_latency
            )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
    predecessor.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
        MultiJointObservedForceCalibratedRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.8 episode without changing the source policy action."""

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
            "observed_force_shadow_calibration_method_active": l2_enabled,
            "observed_force_shadow_calibration_interface": (
                CALIBRATION_INTERFACE if l2_enabled else None
            ),
            "observed_force_shadow_model_bank": (
                [dict(row) for row in MODEL_BANK] if l2_enabled else None
            ),
            "observed_force_shadow_calibration_change_source_action": False,
            "observed_force_shadow_calibration_outcome_informed_successor": True,
            "observed_force_shadow_calibration_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.8 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
