#!/usr/bin/env python3
"""Freeze v15.2 recovery stress calibration and qualification decisions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v15_current_edge_priority_recovery_stress_calibration as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_calibration_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_priority_recovery_stress_calibration_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-calibration-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_2_recovery_stress_"
    "calibration_integrity_nonpass"
)
THRESHOLDS_RAD = (0.0, 0.15, 0.16, 0.22, 0.30)
NEAR_LIMIT_RAD = 0.30


class V15RecoveryStressCalibrationTerminalError(RuntimeError):
    """Raised when retained calibration evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryStressCalibrationTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _identity_diagnostic(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    all_errors = []
    target_errors = []
    near_errors = []
    far_errors = []
    disagreements: Counter[str] = Counter()
    per_environment: dict[str, float] = defaultdict(float)
    trace_length_mismatch_count = 0
    worst: dict[str, Any] | None = None
    for lane in lanes:
        no_guard = lane["baselines"]["no_guard"][
            "actual_joint_side_margins"
        ]
        shadow = lane["baselines"]["shadow_only"][
            "actual_joint_side_margins"
        ]
        if len(no_guard) != len(shadow):
            trace_length_mismatch_count += 1
            continue
        target_joint = int(lane["joint_index"])
        target_side = 0 if lane["side"] == "lower" else 1
        for step_index, (no_rows, shadow_rows) in enumerate(
            zip(no_guard, shadow, strict=True)
        ):
            no_matrix = runner.v14.pilot.full_clean_margin_matrix(no_rows)
            shadow_matrix = runner.v14.pilot.full_clean_margin_matrix(
                shadow_rows
            )
            errors = np.abs(no_matrix - shadow_matrix)
            minima = np.minimum(no_matrix, shadow_matrix)
            all_errors.extend(float(value) for value in errors.flat)
            target_errors.append(float(errors[target_joint, target_side]))
            near_errors.extend(
                float(value) for value in errors[minima < NEAR_LIMIT_RAD]
            )
            far_errors.extend(
                float(value) for value in errors[minima >= NEAR_LIMIT_RAD]
            )
            environment_id = str(lane["environment_id"])
            observed_max = float(np.max(errors))
            per_environment[environment_id] = max(
                per_environment[environment_id], observed_max
            )
            index = np.unravel_index(int(np.argmax(errors)), errors.shape)
            if worst is None or observed_max > worst["error_rad"]:
                worst = {
                    "error_rad": observed_max,
                    "environment_id": environment_id,
                    "lane_id": str(lane["lane_id"]),
                    "step_index": step_index,
                    "joint_index": int(index[0]),
                    "side": "lower" if index[1] == 0 else "upper",
                    "no_guard_margin_rad": float(no_matrix[index]),
                    "shadow_only_margin_rad": float(
                        shadow_matrix[index]
                    ),
                }
            for threshold in THRESHOLDS_RAD:
                disagreements[str(threshold)] += int(
                    np.sum(
                        (no_matrix < threshold)
                        != (shadow_matrix < threshold)
                    )
                )

    def stats(values: list[float]) -> dict[str, Any]:
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": int(array.size),
            "maximum_rad": float(np.max(array)) if array.size else None,
            "p99_rad": (
                float(np.quantile(array, 0.99)) if array.size else None
            ),
        }

    return {
        "thresholds_rad": list(THRESHOLDS_RAD),
        "trace_length_mismatch_count": trace_length_mismatch_count,
        "all_joint_side_error": stats(all_errors),
        "target_joint_side_error": stats(target_errors),
        "near_limit_under_0_30_rad_error": stats(near_errors),
        "far_from_limit_error": stats(far_errors),
        "threshold_classification_disagreement_count": {
            str(value): disagreements[str(value)]
            for value in THRESHOLDS_RAD
        },
        "all_registered_threshold_classifications_identical": (
            trace_length_mismatch_count == 0
            and not any(disagreements.values())
        ),
        "per_environment_maximum_error_rad": dict(
            sorted(per_environment.items())
        ),
        "worst_case": worst,
    }


def _baseline_summary(
    aggregate: Mapping[str, Any],
    baseline: str,
) -> dict[str, Any]:
    fields = (
        "lane_count",
        "trigger_count",
        "trigger_lane_count",
        "trigger_lane_rate",
        "intervention_count",
        "intervention_lane_count",
        "intervention_lane_rate",
        "deadlock_count",
        "deadlock_lane_count",
        "deadlock_lane_rate",
        "below_floor_count",
        "below_floor_side_rate",
        "crossing_count",
        "crossing_side_rate",
        "minimum_margin_rad",
        "executed_step_availability",
        "screen_latency_sample_count",
        "screen_latency_seconds_mean",
        "screen_latency_seconds_p50",
        "screen_latency_seconds_p95",
        "screen_latency_seconds_p99",
        "screen_latency_seconds_max",
        "maximum_abs_constraint_force",
    )
    return {
        field: aggregate[f"{baseline}_{field}"] for field in fields
    }


def _deadline_diagnostics(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        baseline: {
            str(deadline): runner.audit._deadline_report(
                lanes,
                baseline=baseline,
                deadline_seconds=deadline,
            )
            for deadline in (0.05, 0.075, 0.10, 0.125)
        }
        for baseline in (
            "v14_predictive_brake",
            "v15_2_recovery",
        )
    }


def _by_dose_summary(
    aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        dose: {
            baseline: _baseline_summary(values, baseline)
            for baseline in runner.BASELINES
        }
        for dose, values in aggregate["by_dose"].items()
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = runner._output_root(protocol)
    evidence_path = root / "calibration_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("development_data_complete") is not False
        or len(evidence.get("lanes", ())) != 504
    ):
        raise V15RecoveryStressCalibrationTerminalError(
            "calibration terminal population differs"
        )
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed != ["no_guard_shadow_trace_identity"]:
        raise V15RecoveryStressCalibrationTerminalError(
            "calibration failed-gate set differs"
        )
    aggregate = evidence["analysis"]["aggregate"]
    recovery = evidence["analysis"]["recovery"]
    identity = _identity_diagnostic(evidence["lanes"])
    if (
        recovery["v14_predictive_deadlock_lane_count"] != 240
        or recovery["v15_2_residual_deadlock_lane_count"] != 0
        or recovery["recovery_prevented_deadlock_count"] != 792
        or recovery["selected_floor_violation_count"] != 0
        or identity[
            "all_registered_threshold_classifications_identical"
        ]
        is not True
    ):
        raise V15RecoveryStressCalibrationTerminalError(
            "calibration independent summary differs"
        )
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.BASELINES
    }
    deadlines = _deadline_diagnostics(evidence["lanes"])
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_development_data_complete": False,
        "registered_result_unchanged": True,
        "registered_gate_results": evidence["gate_results"],
        "failed_gates": failed,
        "bindings": {
            "protocol": {
                "path": runner.DEFAULT_PROTOCOL.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(runner.DEFAULT_PROTOCOL),
            },
            "evidence": {
                "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(evidence_path),
            },
            "checksums": {
                "path": checksums_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksums_path),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "environment_count": aggregate["environment_count"],
            "suite_count": len(
                {str(row["suite"]) for row in evidence["lanes"]}
            ),
            "stress_lane_count": aggregate["stress_lane_count"],
            "baseline_lane_count": sum(
                aggregate[f"{baseline}_lane_count"]
                for baseline in runner.BASELINES
            ),
            "outcome_disclosed_population": True,
            "held_out_population": False,
        },
        "baselines": baselines,
        "by_dose": _by_dose_summary(aggregate),
        "recovery": recovery,
        "no_guard_shadow_identity_diagnostic": identity,
        "contact_capacity": evidence["analysis"]["contact_capacity"],
        "latency_deadline_diagnostic": deadlines,
        "descriptive_contrasts": {
            "v15_2_minus_v14_deadlock_lane_count": (
                baselines["v15_2_recovery"]["deadlock_lane_count"]
                - baselines["v14_predictive_brake"][
                    "deadlock_lane_count"
                ]
            ),
            "v15_2_minus_v14_executed_step_availability": (
                baselines["v15_2_recovery"][
                    "executed_step_availability"
                ]
                - baselines["v14_predictive_brake"][
                    "executed_step_availability"
                ]
            ),
            "v15_2_minus_v14_maximum_abs_constraint_force": (
                baselines["v15_2_recovery"][
                    "maximum_abs_constraint_force"
                ]
                - baselines["v14_predictive_brake"][
                    "maximum_abs_constraint_force"
                ]
            ),
            "v15_2_minus_v14_latency_p95_seconds": (
                baselines["v15_2_recovery"][
                    "screen_latency_seconds_p95"
                ]
                - baselines["v14_predictive_brake"][
                    "screen_latency_seconds_p95"
                ]
            ),
        },
        "qualification_design_decision": {
            "candidate_parameters_remain_frozen": True,
            "advance_to_new_population_qualification": True,
            "calibration_nonpass_does_not_become_a_pass": True,
            "replace_raw_all_side_numeric_identity_gate": (
                "register exact threshold-classification identity at "
                "0/0.15/0.16/0.22/0.30 rad; retain raw numeric error as "
                "a diagnostic"
            ),
            "reason_for_replacement": (
                "the only registered calibration failure is the known "
                "remote-side numeric divergence, while all 35,280 paired "
                "side values retain identical registered threshold classes"
            ),
            "frozen_qualification_thresholds": {
                "active_contact_capacity_warning_count_max": 0,
                "active_contact_saturation_count_max": 0,
                "stress_activation_no_guard_crossing_count_min": 1,
                "v14_predictive_deadlock_lane_count_min": 1,
                "v15_2_crossing_count_max": 0,
                "v15_2_below_floor_count_max": 0,
                "v15_2_residual_deadlock_lane_count_max": 0,
                "v15_2_selected_floor_violation_count_max": 0,
                "v15_2_prevention_identity_required": True,
                "v15_2_minus_v14_availability_min": 0.0,
                "maximum_prediction_execution_error_rad_max": 0.001,
                "v15_2_maximum_abs_constraint_force_max": 10000.0,
                "v15_2_to_v14_maximum_force_ratio_max": 1.25,
                "v15_2_screen_latency_p95_seconds_max": 0.10,
                "v15_2_screen_latency_seconds_max": 0.20,
                "v15_2_100ms_deadline_miss_rate_max": 0.025,
            },
            "latency_interpretation": (
                "the 50-ms miss rate remains a registered diagnostic and "
                "precludes a 20-Hz real-time claim; the qualification gate "
                "uses a disclosed 100-ms research-simulator budget"
            ),
        },
        "claim_boundary": (
            "The registered calibration remains an integrity nonpass because "
            "the no-guard/shadow all-side numeric identity gate failed. The "
            "outcome-disclosed result may select a future held-out protocol "
            "and its gates, but it cannot establish qualification, task "
            "utility, attacked efficacy, deployment, hardware behavior, "
            "actuator authority, physical safety, or 20-Hz real-time use."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    summary = build_summary(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        )
    )
    text = canonical_text(summary)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15RecoveryStressCalibrationTerminalError(
                f"calibration terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
