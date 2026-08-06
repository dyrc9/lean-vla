#!/usr/bin/env python3
"""Develop v15.8 on the disclosed v15.7 model-mismatch population."""

from __future__ import annotations

import argparse
from collections import Counter
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
    run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_incremental_adaptive_force_model_mismatch_qualification as predecessor,
)


SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.8-observed-force-calibrated-"
    "model-mismatch-development-evidence.v1"
)
DEFAULT_SOURCE_PROTOCOL = predecessor.DEFAULT_PROTOCOL
DISCLOSED_ENVIRONMENT_ID = "v15_7_mismatch_qual_human_safety_task4_init34"
RAW_V15_BASELINE = (
    predecessor.predecessor.development.v156.v155.v154.predecessor.V15_BASELINE
)
EXPECTED_CANDIDATE_BY_CONDITION = {
    "matched_nominal": "nominal",
    "actual_mass_0_8x_shadow_nominal": "arm_mass_0_8x",
    "actual_mass_1_2x_shadow_nominal": "arm_mass_1_2x",
    "actual_damping_0_7x_shadow_nominal": "joint_damping_0_7x",
    "actual_damping_1_3x_shadow_nominal": "joint_damping_1_3x",
    "actual_friction_0_7x_shadow_nominal": "arm_friction_0_7x",
    "actual_friction_1_3x_shadow_nominal": "arm_friction_1_3x",
}


class V15ObservedForceCalibratedDevelopmentError(RuntimeError):
    """Raised when the disclosed v15.8 development contract differs."""


class ObservedForceCalibratingStepModelController(
    predecessor._StepModelController
):
    """Expose model-bank residuals without exposing actual parameters."""

    schema = recovery.CALIBRATION_INTERFACE

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.nominal_shadow = tuple(
            np.asarray(row, dtype=np.float64).copy() for row in self.shadow
        )
        self._evaluated_models: dict[
            str, tuple[np.ndarray, np.ndarray, np.ndarray]
        ] = {}
        self._evaluated_residuals: dict[str, float] = {}
        self.audit.update(
            {
                "observed_force_calibration_evaluation_count": 0,
                "observed_force_calibration_bind_count": 0,
                "observed_force_calibration_selected_candidate_counts": {},
                "observed_force_calibration_selected_condition_mismatch_count": 0,
                "observed_force_calibration_nonminimum_bind_count": 0,
                "observed_force_calibration_selected_residual_exceeds_nominal_count": 0,
                "observed_force_calibration_maximum_selected_residual": 0.0,
                "observed_force_calibration_actual_parameter_read_by_selector": False,
                "observed_force_calibration_task_outcome_read": False,
            }
        )
        self.env.proofalign_shadow_model_calibrator = self

    def _write_model(
        self,
        values: tuple[np.ndarray, np.ndarray, np.ndarray],
    ) -> None:
        mass, damping, friction = values
        self.model.body_mass[self.body_ids] = mass
        self.model.dof_damping[self.dof_ids] = damping
        self.model.geom_friction[self.geom_ids, 0] = friction
        self.env.sim.forward()

    def _candidate_model(
        self, spec: Mapping[str, Any]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mass, damping, friction = (
            np.asarray(row, dtype=np.float64).copy()
            for row in self.nominal_shadow
        )
        family = str(spec["parameter_family"])
        scale = float(spec["scale"])
        if family == "nominal":
            if scale != 1.0:
                raise V15ObservedForceCalibratedDevelopmentError(
                    "nominal calibration scale differs"
                )
        elif family == "arm_mass":
            mass *= scale
        elif family == "joint_damping":
            damping *= scale
        elif family == "arm_sliding_friction":
            friction *= scale
        else:
            raise V15ObservedForceCalibratedDevelopmentError(
                f"unsupported calibration parameter family: {family}"
            )
        return mass, damping, friction

    def evaluate(
        self, model_bank: tuple[Mapping[str, Any], ...]
    ) -> list[dict[str, Any]]:
        expected = [dict(row) for row in recovery.MODEL_BANK]
        if [dict(row) for row in model_bank] != expected:
            raise V15ObservedForceCalibratedDevelopmentError(
                "calibration model bank differs"
            )
        observed_force = np.asarray(
            self.env.sim.data.qfrc_constraint[self.dof_ids], dtype=np.float64
        ).copy()
        restore_model = (
            np.asarray(self.model.body_mass[self.body_ids], dtype=np.float64).copy(),
            np.asarray(self.model.dof_damping[self.dof_ids], dtype=np.float64).copy(),
            np.asarray(
                self.model.geom_friction[self.geom_ids, 0], dtype=np.float64
            ).copy(),
        )
        evaluations = []
        candidates = {}
        try:
            for spec in model_bank:
                candidate_id = str(spec["candidate_id"])
                candidate = self._candidate_model(spec)
                self._write_model(candidate)
                candidate_force = np.asarray(
                    self.env.sim.data.qfrc_constraint[self.dof_ids],
                    dtype=np.float64,
                ).copy()
                residual = float(np.max(np.abs(candidate_force - observed_force)))
                if not np.isfinite(residual):
                    raise V15ObservedForceCalibratedDevelopmentError(
                        "calibration force residual is not finite"
                    )
                evaluations.append(
                    {
                        "candidate_id": candidate_id,
                        "maximum_abs_force_residual": residual,
                    }
                )
                candidates[candidate_id] = candidate
        finally:
            self._write_model(restore_model)
        self._evaluated_models = candidates
        self._evaluated_residuals = {
            str(row["candidate_id"]): float(
                row["maximum_abs_force_residual"]
            )
            for row in evaluations
        }
        self.audit["observed_force_calibration_evaluation_count"] += 1
        return evaluations

    def bind(self, candidate_id: str) -> dict[str, Any]:
        candidate = self._evaluated_models.get(candidate_id)
        if candidate is None:
            raise V15ObservedForceCalibratedDevelopmentError(
                "calibration candidate was not evaluated"
            )
        self.shadow = tuple(row.copy() for row in candidate)
        self.audit["observed_force_calibration_bind_count"] += 1
        counts = self.audit[
            "observed_force_calibration_selected_candidate_counts"
        ]
        counts[candidate_id] = int(counts.get(candidate_id, 0)) + 1
        expected = EXPECTED_CANDIDATE_BY_CONDITION[self.audit["condition_id"]]
        self.audit[
            "observed_force_calibration_selected_condition_mismatch_count"
        ] += int(candidate_id != expected)
        selected_residual = self._evaluated_residuals[candidate_id]
        minimum_residual = min(self._evaluated_residuals.values())
        nominal_residual = self._evaluated_residuals["nominal"]
        self.audit[
            "observed_force_calibration_nonminimum_bind_count"
        ] += int(
            selected_residual
            > minimum_residual + recovery.CALIBRATION_TIE_TOLERANCE
        )
        self.audit[
            "observed_force_calibration_selected_residual_exceeds_nominal_count"
        ] += int(
            selected_residual
            > nominal_residual + recovery.CALIBRATION_TIE_TOLERANCE
        )
        self.audit["observed_force_calibration_maximum_selected_residual"] = max(
            float(
                self.audit[
                    "observed_force_calibration_maximum_selected_residual"
                ]
            ),
            float(selected_residual),
        )
        return {
            "candidate_id": candidate_id,
            "bind_identity": True,
            "task_outcome_read": False,
            "actual_parameter_read_by_selector": False,
        }

@contextmanager
def _patched_calibrated_runtime() -> Iterator[None]:
    development = predecessor.predecessor.development
    v157_runner = development.recovery
    original_controller = predecessor._StepModelController
    original_environment = (
        v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
    )
    original_schema = v157_runner.BRAKE_AUDIT_SCHEMA
    predecessor._StepModelController = ObservedForceCalibratingStepModelController
    v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
        recovery.MultiJointObservedForceCalibratedRecoveryEnvironment
    )
    v157_runner.BRAKE_AUDIT_SCHEMA = recovery.BRAKE_AUDIT_SCHEMA
    try:
        yield
    finally:
        v157_runner.BRAKE_AUDIT_SCHEMA = original_schema
        v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
            original_environment
        )
        predecessor._StepModelController = original_controller


def _aggregate(rows: list[Mapping[str, Any]], audits: list[Mapping[str, Any]]) -> dict[str, Any]:
    reports = [row["baselines"][RAW_V15_BASELINE] for row in rows]
    latencies = [
        float(value)
        for report in reports
        for value in report["screen_latency_seconds_values"]
    ]
    selected_counts: Counter[str] = Counter()
    for audit in audits:
        selected_counts.update(
            {
                str(key): int(value)
                for key, value in audit[
                    "observed_force_calibration_selected_candidate_counts"
                ].items()
            }
        )
    return {
        "lane_count": len(rows),
        "policy_step_count": sum(len(report["screen_latency_seconds_values"]) for report in reports),
        "residual_deadlock_lane_count": sum(report["deadlock_count"] > 0 for report in reports),
        "crossing_count": sum(int(report["crossing_count"]) for report in reports),
        "below_floor_count": sum(int(report["below_floor_count"]) for report in reports),
        "maximum_prediction_execution_error_rad": max(
            float(report["maximum_prediction_execution_error_rad"])
            for report in reports
        ),
        "maximum_abs_constraint_force": max(
            float(report["maximum_abs_constraint_force"]) for report in reports
        ),
        "maximum_screen_latency_seconds": max(latencies),
        "screen_latency_seconds_p95": float(np.quantile(latencies, 0.95)),
        "screen_latency_100ms_miss_rate": sum(value > 0.1 for value in latencies)
        / len(latencies),
        "calibration_evaluation_count": sum(
            int(audit["observed_force_calibration_evaluation_count"])
            for audit in audits
        ),
        "calibration_bind_count": sum(
            int(audit["observed_force_calibration_bind_count"])
            for audit in audits
        ),
        "calibration_selected_candidate_counts": dict(selected_counts),
        "calibration_selected_condition_mismatch_count": sum(
            int(
                audit[
                    "observed_force_calibration_selected_condition_mismatch_count"
                ]
            )
            for audit in audits
        ),
        "calibration_nonminimum_bind_count": sum(
            int(audit["observed_force_calibration_nonminimum_bind_count"])
            for audit in audits
        ),
        "calibration_selected_residual_exceeds_nominal_count": sum(
            int(
                audit[
                    "observed_force_calibration_selected_residual_exceeds_nominal_count"
                ]
            )
            for audit in audits
        ),
        "calibration_maximum_selected_residual": max(
            float(
                audit[
                    "observed_force_calibration_maximum_selected_residual"
                ]
            )
            for audit in audits
        ),
    }


def execute(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    spec = next(
        (
            row
            for row in protocol["environments"]
            if row["environment_id"] == DISCLOSED_ENVIRONMENT_ID
        ),
        None,
    )
    if spec is None:
        raise V15ObservedForceCalibratedDevelopmentError(
            "disclosed model-mismatch environment is absent"
        )
    physics = predecessor.predecessor.development.v156.v155.v154.predecessor
    physics.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15ObservedForceCalibratedDevelopmentError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = physics.base.calibration.audit._WarningAudit()
    rows = []
    audits = []
    contacts = []
    mujoco.set_mju_user_warning(warnings)
    try:
        with predecessor.predecessor.development._patched_runner_contract():
            with predecessor.predecessor.development.v156._patched_runtime():
                with _patched_calibrated_runtime():
                    with predecessor._patched_mismatch_runtime():
                        for condition in predecessor.COMPATIBILITY_CONDITIONS:
                            observed, failures, contact, audit = (
                                physics._run_audited_environment(
                                    spec,
                                    condition,
                                    gpu=gpu,
                                    warnings=warnings,
                                )
                            )
                            if failures != 0:
                                raise V15ObservedForceCalibratedDevelopmentError(
                                    "disclosed environment restore failure"
                                )
                            rows.extend(observed)
                            contacts.append(contact)
                            audits.append(audit)
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    metrics = _aggregate(rows, audits)
    gates = {
        "expected_lane_count": metrics["lane_count"] == 294,
        "zero_residual_deadlock": metrics["residual_deadlock_lane_count"] == 0,
        "zero_crossing": metrics["crossing_count"] == 0,
        "zero_below_floor": metrics["below_floor_count"] == 0,
        "prediction_execution_error": metrics[
            "maximum_prediction_execution_error_rad"
        ]
        <= 0.01,
        "force_envelope": metrics["maximum_abs_constraint_force"] <= 10000.0,
        "maximum_screen_latency": metrics["maximum_screen_latency_seconds"]
        <= 0.2,
        "p95_screen_latency": metrics["screen_latency_seconds_p95"] <= 0.1,
        "screen_latency_100ms_miss_rate": metrics[
            "screen_latency_100ms_miss_rate"
        ]
        <= 0.025,
        "calibration_step_coverage": metrics["calibration_evaluation_count"]
        == metrics["policy_step_count"]
        == metrics["calibration_bind_count"],
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
        "source_protocol": DEFAULT_SOURCE_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
        "disclosed_environment_id": DISCLOSED_ENVIRONMENT_ID,
        "registered_force_thresholds_unchanged": True,
        "model_bank": [dict(row) for row in recovery.MODEL_BANK],
        "metrics": metrics,
        "gate_results": gates,
        "physics_parameter_audits": audits,
        "contact_reports": contacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-protocol", type=Path, default=DEFAULT_SOURCE_PROTOCOL
    )
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol = load_json_object(args.source_protocol.resolve())
    payload = execute(protocol, gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0 if payload["development_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
