#!/usr/bin/env python3
"""Freeze the immutable v15.8 model-mismatch qualification NONPASS."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_v15_observed_force_calibrated_model_mismatch_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_observed_force_calibrated_"
    "model_mismatch_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_observed_force_calibrated_model_mismatch_qualification_terminal.py"
)
CREATED_AT = "2026-08-05T18:00:00+08:00"


class V15ObservedForceCalibratedTerminalError(RuntimeError):
    """Raised when the v15.8 NONPASS cannot be frozen."""


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol, protocol_path=runner.DEFAULT_PROTOCOL
    )
    if (
        evidence["model_mismatch_qualification_pass"] is not False
        or evidence["model_mismatch_claim_authorized"] is not False
    ):
        raise V15ObservedForceCalibratedTerminalError(
            "terminalizer expected the observed v15.8 NONPASS"
        )
    analysis = evidence["analysis"]
    conditions = {}
    total_residual = 0
    maximum_force = 0.0
    maximum_error = 0.0
    maximum_latency = 0.0
    maximum_miss_rate = 0.0
    for condition in protocol["design"]["model_mismatch_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        gates = analysis["condition_gate_results"][condition_id]
        aggregate = result["aggregate"]
        recovery = result["recovery"]
        force = result["force_comparison"]
        latency = result["v15_3_latency_budget"]
        residual = int(recovery["v15_3_residual_deadlock_lane_count"])
        error = float(recovery["maximum_prediction_execution_error_rad"])
        attributable = float(
            force["v15_3_maximum_attributable_joint_force_increment"]
        )
        latency_max = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_max"
            ]
        )
        latency_p95 = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_p95"
            ]
        )
        miss_rate = float(latency["miss_rate"])
        total_residual += residual
        maximum_force = max(maximum_force, attributable)
        maximum_error = max(maximum_error, error)
        maximum_latency = max(maximum_latency, latency_max)
        maximum_miss_rate = max(maximum_miss_rate, miss_rate)
        conditions[condition_id] = {
            "condition_pass": all(gates.values()),
            "failed_registered_gates": sorted(
                key for key, value in gates.items() if not value
            ),
            "crossing_count": int(
                aggregate["v15_3_force_attributed_recovery_crossing_count"]
            ),
            "below_floor_count": int(
                aggregate[
                    "v15_3_force_attributed_recovery_below_floor_count"
                ]
            ),
            "residual_deadlock_lane_count": residual,
            "maximum_prediction_execution_error_rad": error,
            "maximum_attributable_joint_force_increment": attributable,
            "maximum_recovery_attributable_joint_force_increment": float(
                force[
                    "v15_3_maximum_recovery_attributable_joint_force_increment"
                ]
            ),
            "latency_max_seconds": latency_max,
            "latency_p95_seconds": latency_p95,
            "latency_100ms_miss_rate": miss_rate,
        }
    root = runner._output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    checksum_path = root / "SHA256SUMS"
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.8-observed-force-"
            "calibrated-model-mismatch-qualification-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": False,
        "model_mismatch_claim_authorized": False,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "failed_registered_gates": sorted(
            key for key, value in evidence["gate_results"].items() if not value
        ),
        "bindings": {
            "protocol": {
                "path": runner.DEFAULT_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(runner.DEFAULT_PROTOCOL),
            },
            "evidence": {
                "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(evidence_path),
                "bytes": evidence_path.stat().st_size,
            },
            "checksums": {
                "path": checksum_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksum_path),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "globally_held_out_exact_task_init_pair_count": 18,
            "excluded_prior_exact_pair_count": int(
                protocol["selection"]["prior_exact_pair_count"]
            ),
            "condition_count": 7,
            "stress_lane_count": 5292,
            "baseline_lane_count": 21168,
            "task_outcomes_read": False,
        },
        "conditions": conditions,
        "cross_condition": {
            "total_residual_deadlock_lane_count": total_residual,
            "maximum_prediction_execution_error_rad": maximum_error,
            "maximum_attributable_joint_force_increment": maximum_force,
            "worst_latency_max_seconds": maximum_latency,
            "worst_100ms_deadline_miss_rate": maximum_miss_rate,
        },
        "model_mismatch_metrics": dict(analysis["model_mismatch_metrics"]),
        "observed_force_calibration_metrics": dict(
            analysis["observed_force_calibration_metrics"]
        ),
        "completed_axes": {
            "zero_crossing_all_conditions": all(
                row["crossing_count"] == 0 for row in conditions.values()
            ),
            "zero_below_floor_all_conditions": all(
                row["below_floor_count"] == 0 for row in conditions.values()
            ),
            "zero_residual_deadlock_all_conditions": total_residual == 0,
            "prediction_error_within_registered_bound": maximum_error <= 0.01,
            "force_within_registered_bound": maximum_force <= 10000.0,
            "calibration_full_step_coverage": analysis[
                "observed_force_calibration_metrics"
            ]["evaluation_count"]
            == 26460,
            "selector_noninterference": analysis[
                "observed_force_calibration_metrics"
            ]["actual_parameter_read_by_selector_count"]
            == 0
            and analysis["observed_force_calibration_metrics"][
                "task_outcome_read_count"
            ]
            == 0,
        },
        "nonpass_axes": {
            "all_conditions": [
                "screen_latency_seconds_max",
                "screen_latency_100ms_miss_rate",
            ],
            "cross_condition_compatibility": [
                "selected_post_force_prediction_identity"
            ],
        },
        "next_stage_decision": {
            "preserve_v15_8_nonpass_without_reinterpretation": True,
            "move_calibration_out_of_per_action_critical_path": True,
            "reuse_v15_8_population_for_requalification": False,
            "fresh_requalification_required_after_successor_development": True,
            "relax_safety_force_or_latency_thresholds": False,
            "model_mismatch_claim_authorized": False,
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15ObservedForceCalibratedTerminalError(
            "v15.8 model-mismatch terminal summary already exists"
        )
    summary = build_summary(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(summary), encoding="utf-8")
    print(
        canonical_text(
            {
                "terminal_path": output.relative_to(REPO_ROOT).as_posix(),
                "terminal_sha256": file_sha256(output),
                "registered_qualification_pass": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
