#!/usr/bin/env python3
"""Develop v15.9 on four disclosed model-mismatch environments."""

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

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_pre_step_calibrated_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_observed_force_calibrated_model_mismatch_development as predecessor,
)


SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.9-pre-step-calibrated-"
    "model-mismatch-development-evidence.v1"
)
OLD_SOURCE_PROTOCOL = predecessor.DEFAULT_SOURCE_PROTOCOL
NEW_SOURCE_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_observed_force_calibrated_"
    "model_mismatch_qualification_protocol.json"
)
DISCLOSED_ENVIRONMENT_IDS = (
    "v15_7_mismatch_qual_human_safety_task4_init34",
    "v15_8_mismatch_qual_obstacle_avoidance_human_task12_init8",
    "v15_8_mismatch_qual_human_safety_task9_init49",
    "v15_8_mismatch_qual_human_safety_task3_init45",
)
RAW_V15_BASELINE = predecessor.RAW_V15_BASELINE


class V15PreStepCalibratedDevelopmentError(RuntimeError):
    """Raised when the v15.9 disclosed development contract differs."""


def _disclosed_specs() -> list[dict[str, Any]]:
    protocols = (
        load_json_object(OLD_SOURCE_PROTOCOL),
        load_json_object(NEW_SOURCE_PROTOCOL),
    )
    by_id = {
        str(row["environment_id"]): dict(row)
        for protocol in protocols
        for row in protocol["environments"]
    }
    try:
        return [by_id[environment_id] for environment_id in DISCLOSED_ENVIRONMENT_IDS]
    except KeyError as exc:
        raise V15PreStepCalibratedDevelopmentError(
            "disclosed v15.9 environment is absent"
        ) from exc


@contextmanager
def _patched_pre_step_runtime() -> Iterator[None]:
    mismatch = predecessor.predecessor
    development = mismatch.predecessor.development
    v157_runner = development.recovery
    with predecessor._patched_calibrated_runtime():
        original_environment = (
            v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
        )
        original_schema = v157_runner.BRAKE_AUDIT_SCHEMA
        original_run_screened = development._run_screened
        captured: list[Any] = []

        class CapturePreStepEnvironment(
            recovery.MultiJointPreStepCalibratedRecoveryEnvironment
        ):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                captured.append(self)

        def run_screened(env: Any) -> dict[str, Any]:
            captured.clear()
            result = original_run_screened(env)
            if len(captured) != 1:
                raise V15PreStepCalibratedDevelopmentError(
                    "v15.9 screened wrapper creation count differs"
                )
            observations = captured[0].observations
            setup_latencies = {
                float(row["pre_step_shadow_calibration_latency_seconds"])
                for row in observations
            }
            selected_ids = {
                str(row["pre_step_shadow_selected_candidate_id"])
                for row in observations
            }
            if len(setup_latencies) != 1 or len(selected_ids) != 1:
                raise V15PreStepCalibratedDevelopmentError(
                    "v15.9 setup calibration was not fixed across action steps"
                )
            result.update(
                {
                    "pre_step_calibration_count": 1,
                    "pre_step_calibration_reuse_step_count": len(observations),
                    "pre_step_calibration_inactive_count": sum(
                        row.get("pre_step_shadow_calibration_active") is not True
                        for row in observations
                    ),
                    "pre_step_calibration_bind_identity_failure_count": sum(
                        row.get("pre_step_shadow_bind_identity") is not True
                        for row in observations
                    ),
                    "pre_step_calibration_action_latency_contamination_count": sum(
                        row.get(
                            "pre_step_shadow_calibration_outside_action_critical_path"
                        )
                        is not True
                        for row in observations
                    ),
                    "pre_step_calibration_latency_seconds": next(
                        iter(setup_latencies)
                    ),
                    "pre_step_calibration_selected_candidate_id": next(
                        iter(selected_ids)
                    ),
                }
            )
            return result

        v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
            CapturePreStepEnvironment
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
    metrics = predecessor._aggregate(rows, audits)
    reports = [row["baselines"][RAW_V15_BASELINE] for row in rows]
    setup_latencies = [
        float(report["pre_step_calibration_latency_seconds"])
        for report in reports
    ]
    return {
        **metrics,
        "pre_step_calibration_count": sum(
            int(report["pre_step_calibration_count"]) for report in reports
        ),
        "pre_step_calibration_reuse_step_count": sum(
            int(report["pre_step_calibration_reuse_step_count"])
            for report in reports
        ),
        "pre_step_calibration_inactive_count": sum(
            int(report["pre_step_calibration_inactive_count"])
            for report in reports
        ),
        "pre_step_calibration_bind_identity_failure_count": sum(
            int(report["pre_step_calibration_bind_identity_failure_count"])
            for report in reports
        ),
        "pre_step_calibration_action_latency_contamination_count": sum(
            int(report["pre_step_calibration_action_latency_contamination_count"])
            for report in reports
        ),
        "pre_step_calibration_latency_seconds_max": max(setup_latencies),
        "pre_step_calibration_latency_seconds_p95": float(
            np.quantile(setup_latencies, 0.95)
        ),
    }


def execute(*, gpu: int) -> dict[str, Any]:
    mismatch = predecessor.predecessor
    physics = mismatch.predecessor.development.v156.v155.v154.predecessor
    physics.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15PreStepCalibratedDevelopmentError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = physics.base.calibration.audit._WarningAudit()
    rows = []
    audits = []
    contacts = []
    mujoco.set_mju_user_warning(warnings)
    try:
        with _patched_pre_step_runtime():
            with mismatch.predecessor.development._patched_runner_contract():
                with mismatch.predecessor.development.v156._patched_runtime():
                    with mismatch._patched_mismatch_runtime():
                        for condition in mismatch.COMPATIBILITY_CONDITIONS:
                            for spec in _disclosed_specs():
                                observed, failures, contact, audit = (
                                    physics._run_audited_environment(
                                        spec,
                                        condition,
                                        gpu=gpu,
                                        warnings=warnings,
                                    )
                                )
                                if failures != 0:
                                    raise V15PreStepCalibratedDevelopmentError(
                                        "v15.9 disclosed environment restore failure"
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
        "setup_calibration_lane_coverage": metrics["pre_step_calibration_count"]
        == metrics["lane_count"]
        == metrics["calibration_evaluation_count"]
        == metrics["calibration_bind_count"],
        "setup_calibration_step_reuse": metrics[
            "pre_step_calibration_reuse_step_count"
        ]
        == metrics["policy_step_count"],
        "setup_calibration_active_and_bound": metrics[
            "pre_step_calibration_inactive_count"
        ]
        == 0
        and metrics["pre_step_calibration_bind_identity_failure_count"] == 0,
        "setup_calibration_outside_action_latency": metrics[
            "pre_step_calibration_action_latency_contamination_count"
        ]
        == 0,
        "setup_calibration_latency": metrics[
            "pre_step_calibration_latency_seconds_max"
        ]
        <= 0.5,
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
            OLD_SOURCE_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
            NEW_SOURCE_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
        ],
        "disclosed_environment_ids": list(DISCLOSED_ENVIRONMENT_IDS),
        "registered_force_thresholds_unchanged": True,
        "model_bank": [dict(row) for row in recovery.predecessor.MODEL_BANK],
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
