#!/usr/bin/env python3
"""Develop v15.10 rolling prebinding on disclosed mismatch environments."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_rolling_prebound_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_pre_step_calibrated_model_mismatch_development as predecessor,
)


SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.10-rolling-prebound-"
    "model-mismatch-development-evidence.v1"
)
RAW_V15_BASELINE = predecessor.RAW_V15_BASELINE


class V15RollingPreboundDevelopmentError(RuntimeError):
    """Raised when the v15.10 disclosed development contract differs."""


@contextmanager
def _patched_rolling_runtime() -> Iterator[None]:
    v158_development = predecessor.predecessor
    mismatch = v158_development.predecessor
    development = mismatch.predecessor.development
    v157_runner = development.recovery
    with v158_development._patched_calibrated_runtime():
        original_environment = (
            v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
        )
        original_schema = v157_runner.BRAKE_AUDIT_SCHEMA
        original_run_screened = development._run_screened
        captured: list[Any] = []

        class CaptureRollingEnvironment(
            recovery.MultiJointRollingPreboundRecoveryEnvironment
        ):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                captured.append(self)

        def run_screened(env: Any) -> dict[str, Any]:
            captured.clear()
            result = original_run_screened(env)
            if len(captured) != 1:
                raise V15RollingPreboundDevelopmentError(
                    "v15.10 screened wrapper creation count differs"
                )
            observations = captured[0].observations
            generations = [
                int(row["rolling_prebound_used_generation"])
                for row in observations
            ]
            if generations != list(range(len(observations))):
                raise V15RollingPreboundDevelopmentError(
                    "v15.10 rolling generation sequence differs"
                )
            result.update(
                {
                    "rolling_prebound_setup_calibration_count": 1,
                    "rolling_prebound_update_count": len(observations),
                    "rolling_prebound_inactive_count": sum(
                        row.get("rolling_prebound_shadow_calibration_active")
                        is not True
                        for row in observations
                    ),
                    "rolling_prebound_action_latency_contamination_count": sum(
                        row.get("rolling_prebound_update_outside_action_screen")
                        is not True
                        for row in observations
                    ),
                    "rolling_prebound_setup_latency_seconds": float(
                        observations[0][
                            "pre_step_shadow_calibration_latency_seconds"
                        ]
                    ),
                    "rolling_prebound_update_latency_seconds_values": [
                        float(row["rolling_prebound_update_latency_seconds"])
                        for row in observations
                    ],
                }
            )
            return result

        v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
            CaptureRollingEnvironment
        )
        v157_runner.BRAKE_AUDIT_SCHEMA = recovery.BRAKE_AUDIT_SCHEMA
        development._run_screened = run_screened
        try:
            yield
        finally:
            development._run_screened = original_run_screened
            v157_runner.BRAKE_AUDIT_SCHEMA = original_schema
            v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
                original_environment
            )


def _aggregate(
    rows: list[Mapping[str, Any]], audits: list[Mapping[str, Any]]
) -> dict[str, Any]:
    metrics = predecessor.predecessor._aggregate(rows, audits)
    reports = [row["baselines"][RAW_V15_BASELINE] for row in rows]
    setup_latencies = [
        float(report["rolling_prebound_setup_latency_seconds"])
        for report in reports
    ]
    update_latencies = [
        float(value)
        for report in reports
        for value in report["rolling_prebound_update_latency_seconds_values"]
    ]
    return {
        **metrics,
        "rolling_prebound_setup_calibration_count": sum(
            int(report["rolling_prebound_setup_calibration_count"])
            for report in reports
        ),
        "rolling_prebound_update_count": sum(
            int(report["rolling_prebound_update_count"]) for report in reports
        ),
        "rolling_prebound_inactive_count": sum(
            int(report["rolling_prebound_inactive_count"]) for report in reports
        ),
        "rolling_prebound_action_latency_contamination_count": sum(
            int(report["rolling_prebound_action_latency_contamination_count"])
            for report in reports
        ),
        "rolling_prebound_setup_latency_seconds_max": max(setup_latencies),
        "rolling_prebound_setup_latency_seconds_p95": float(
            np.quantile(setup_latencies, 0.95)
        ),
        "rolling_prebound_update_latency_seconds_max": max(update_latencies),
        "rolling_prebound_update_latency_seconds_p95": float(
            np.quantile(update_latencies, 0.95)
        ),
    }


def execute(*, gpu: int) -> dict[str, Any]:
    v158_development = predecessor.predecessor
    mismatch = v158_development.predecessor
    physics = mismatch.predecessor.development.v156.v155.v154.predecessor
    physics.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15RollingPreboundDevelopmentError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = physics.base.calibration.audit._WarningAudit()
    rows = []
    audits = []
    contacts = []
    mujoco.set_mju_user_warning(warnings)
    try:
        with _patched_rolling_runtime():
            with mismatch.predecessor.development._patched_runner_contract():
                with mismatch.predecessor.development.v156._patched_runtime():
                    with mismatch._patched_mismatch_runtime():
                        for condition in mismatch.COMPATIBILITY_CONDITIONS:
                            for spec in predecessor._disclosed_specs():
                                observed, failures, contact, audit = (
                                    physics._run_audited_environment(
                                        spec,
                                        condition,
                                        gpu=gpu,
                                        warnings=warnings,
                                    )
                                )
                                if failures != 0:
                                    raise V15RollingPreboundDevelopmentError(
                                        "v15.10 disclosed environment restore failure"
                                    )
                                rows.extend(observed)
                                contacts.append(contact)
                                audits.append(audit)
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    metrics = _aggregate(rows, audits)
    gates = {
        "expected_lane_count": metrics["lane_count"] == 1176,
        "zero_residual_deadlock": metrics["residual_deadlock_lane_count"] == 0,
        "zero_crossing": metrics["crossing_count"] == 0,
        "zero_below_floor": metrics["below_floor_count"] == 0,
        "prediction_execution_error": metrics[
            "maximum_prediction_execution_error_rad"
        ]
        <= 0.01,
        "force_envelope": metrics["maximum_abs_constraint_force"] <= 10000.0,
        "maximum_action_screen_latency": metrics[
            "maximum_screen_latency_seconds"
        ]
        <= 0.2,
        "p95_action_screen_latency": metrics["screen_latency_seconds_p95"]
        <= 0.1,
        "action_screen_100ms_miss_rate": metrics[
            "screen_latency_100ms_miss_rate"
        ]
        <= 0.025,
        "setup_calibration_lane_coverage": metrics[
            "rolling_prebound_setup_calibration_count"
        ]
        == metrics["lane_count"],
        "rolling_update_step_coverage": metrics[
            "rolling_prebound_update_count"
        ]
        == metrics["policy_step_count"],
        "calibration_evaluation_coverage": metrics["calibration_evaluation_count"]
        == metrics["lane_count"] + metrics["policy_step_count"]
        == metrics["calibration_bind_count"],
        "rolling_calibration_active": metrics["rolling_prebound_inactive_count"]
        == 0,
        "rolling_update_outside_action_latency": metrics[
            "rolling_prebound_action_latency_contamination_count"
        ]
        == 0,
        "setup_calibration_latency": metrics[
            "rolling_prebound_setup_latency_seconds_max"
        ]
        <= 0.5,
        "rolling_update_latency": metrics[
            "rolling_prebound_update_latency_seconds_max"
        ]
        <= 0.5,
        "rolling_update_latency_p95": metrics[
            "rolling_prebound_update_latency_seconds_p95"
        ]
        <= 0.1,
        "calibration_minimum_residual_identity": metrics[
            "calibration_nonminimum_bind_count"
        ]
        == 0,
        "calibration_nominal_residual_dominance": metrics[
            "calibration_selected_residual_exceeds_nominal_count"
        ]
        == 0,
    }
    passed = all(gates.values())
    return {
        "schema": SCHEMA,
        "classification": (
            "outcome_disclosed_development_pass"
            if passed
            else "outcome_disclosed_development_nonpass"
        ),
        "development_pass": passed,
        "qualification_claim_authorized": False,
        "model_mismatch_claim_authorized": False,
        "task_utility_claim_authorized": False,
        "task_outcome_read": False,
        "policy_loaded": False,
        "source_protocols": [
            predecessor.OLD_SOURCE_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
            predecessor.NEW_SOURCE_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
        ],
        "disclosed_environment_ids": list(
            predecessor.DISCLOSED_ENVIRONMENT_IDS
        ),
        "registered_force_thresholds_unchanged": True,
        "model_bank": [
            dict(row) for row in recovery.predecessor.predecessor.MODEL_BANK
        ],
        "metrics": metrics,
        "gate_results": gates,
        "physics_parameter_audits": audits,
        "contact_reports": contacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = execute(gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0 if payload["development_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
