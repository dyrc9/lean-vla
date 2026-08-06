#!/usr/bin/env python3
"""Freeze the immutable v15.7 model-mismatch qualification NONPASS."""

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
    run_v15_incremental_adaptive_force_model_mismatch_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "model_mismatch_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_incremental_adaptive_force_model_mismatch_qualification_terminal.py"
)
CREATED_AT = "2026-08-01T20:30:00+08:00"


class V15IncrementalAdaptiveForceModelMismatchTerminalError(RuntimeError):
    """Raised when the observed model-mismatch NONPASS cannot be frozen."""


def _failure_lanes(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = runner.V15_BASELINE
    rows = []
    for lane in evidence["lanes"]:
        report = lane["baselines"][baseline]
        if report["deadlock_count"]:
            rows.append(
                {
                    "failure": "residual_deadlock",
                    "condition_id": lane["condition_id"],
                    "suite": lane["suite"],
                    "task_id": lane["task_id"],
                    "init_state_id": lane["init_state_id"],
                    "joint_index": lane["joint_index"],
                    "side": lane["side"],
                    "dose": lane["dose"]["dose"],
                    "deadlock_count": report["deadlock_count"],
                    "executed_step_count": report["executed_step_count"],
                    "stop_reason": report["stop_reason"],
                    "maximum_prediction_execution_error_rad": report[
                        "maximum_prediction_execution_error_rad"
                    ],
                    "maximum_screen_latency_seconds": max(
                        report["screen_latency_seconds_values"]
                    ),
                }
            )
    return rows


def _maximum_force_lane(evidence: dict[str, Any]) -> dict[str, Any]:
    baseline = runner.V15_BASELINE
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for lane in evidence["lanes"]:
        if lane["condition_id"] != "actual_friction_0_7x_shadow_nominal":
            continue
        for step in lane["baselines"][baseline]["force_attribution_steps"]:
            value = float(
                step["guard_scope_max_envelope_increment_over_pre_step"]
            )
            if best is None or value > best[0]:
                best = (value, lane, step)
    if best is None:
        raise V15IncrementalAdaptiveForceModelMismatchTerminalError(
            "attributable force failure lane is absent"
        )
    value, lane, step = best
    return {
        "failure": "maximum_attributable_joint_force_increment",
        "condition_id": lane["condition_id"],
        "suite": lane["suite"],
        "task_id": lane["task_id"],
        "init_state_id": lane["init_state_id"],
        "joint_index": lane["joint_index"],
        "side": lane["side"],
        "dose": lane["dose"]["dose"],
        "runner_step_id": step["runner_step_id"],
        "observed": value,
        "registered_maximum": 10000.0,
        "recovery_selected": step["recovery_selected"],
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol, protocol_path=runner.DEFAULT_PROTOCOL
    )
    if (
        evidence["model_mismatch_qualification_pass"] is not False
        or evidence["model_mismatch_claim_authorized"] is not False
    ):
        raise V15IncrementalAdaptiveForceModelMismatchTerminalError(
            "terminalizer expected the observed model-mismatch NONPASS"
        )
    root = runner._output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    analysis = evidence["analysis"]
    conditions = {}
    pass_count = 0
    worst_prediction_error = -1.0
    worst_prediction_condition = None
    worst_p95 = -1.0
    worst_p95_condition = None
    worst_latency = -1.0
    worst_latency_condition = None
    worst_miss_rate = -1.0
    worst_miss_condition = None
    maximum_attributable_force = -1.0
    maximum_attributable_force_condition = None
    total_v14_deadlocks = 0
    total_prevented = 0
    total_residual = 0
    for condition in protocol["design"]["model_mismatch_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        gates = analysis["condition_gate_results"][condition_id]
        failed = sorted(key for key, value in gates.items() if not value)
        pass_count += int(not failed)
        aggregate = result["aggregate"]
        recovery = result["recovery"]
        force = result["force_comparison"]
        latency = result["v15_3_latency_budget"]
        prediction_error = float(
            recovery["maximum_prediction_execution_error_rad"]
        )
        p95 = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_p95"
            ]
        )
        maximum_latency = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_max"
            ]
        )
        miss_rate = float(latency["miss_rate"])
        attributable_force = float(
            force["v15_3_maximum_attributable_joint_force_increment"]
        )
        if prediction_error > worst_prediction_error:
            worst_prediction_error = prediction_error
            worst_prediction_condition = condition_id
        if p95 > worst_p95:
            worst_p95, worst_p95_condition = p95, condition_id
        if maximum_latency > worst_latency:
            worst_latency, worst_latency_condition = maximum_latency, condition_id
        if miss_rate > worst_miss_rate:
            worst_miss_rate, worst_miss_condition = miss_rate, condition_id
        if attributable_force > maximum_attributable_force:
            maximum_attributable_force = attributable_force
            maximum_attributable_force_condition = condition_id
        total_v14_deadlocks += int(
            recovery["v14_predictive_deadlock_lane_count"]
        )
        total_prevented += int(
            recovery["v15_3_recovery_prevented_deadlock_lane_count"]
        )
        total_residual += int(
            recovery["v15_3_residual_deadlock_lane_count"]
        )
        conditions[condition_id] = {
            "parameters": dict(condition),
            "condition_pass": not failed,
            "failed_registered_gates": failed,
            "registered_gate_results": dict(sorted(gates.items())),
            "crossing_count": int(
                aggregate["v15_3_force_attributed_recovery_crossing_count"]
            ),
            "below_floor_count": int(
                aggregate[
                    "v15_3_force_attributed_recovery_below_floor_count"
                ]
            ),
            "executed_step_availability": float(
                aggregate[
                    "v15_3_force_attributed_recovery_executed_step_availability"
                ]
            ),
            "v14_deadlock_lane_count": int(
                recovery["v14_predictive_deadlock_lane_count"]
            ),
            "recovery_prevented_deadlock_lane_count": int(
                recovery["v15_3_recovery_prevented_deadlock_lane_count"]
            ),
            "residual_deadlock_lane_count": int(
                recovery["v15_3_residual_deadlock_lane_count"]
            ),
            "maximum_prediction_execution_error_rad": prediction_error,
            "maximum_attributable_joint_force_increment": attributable_force,
            "maximum_recovery_attributable_joint_force_increment": float(
                force[
                    "v15_3_maximum_recovery_attributable_joint_force_increment"
                ]
            ),
            "maximum_post_step_absolute_risk_force": float(
                force["v15_3_maximum_post_step_absolute_risk_force"]
            ),
            "maximum_post_step_positive_joint_increment": float(
                force["v15_3_maximum_post_step_positive_joint_increment"]
            ),
            "maximum_recovery_post_step_positive_joint_increment": float(
                force[
                    "v15_3_maximum_recovery_post_step_positive_joint_increment"
                ]
            ),
            "latency_p95_seconds": p95,
            "latency_max_seconds": maximum_latency,
            "latency_100ms_miss_rate": miss_rate,
        }
    failure_lanes = _failure_lanes(evidence)
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-"
            "force-model-mismatch-qualification-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": False,
        "model_mismatch_claim_authorized": False,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "registered_gate_results": dict(sorted(evidence["gate_results"].items())),
        "failed_registered_gates": sorted(
            key for key, value in evidence["gate_results"].items() if not value
        ),
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
                "bytes": evidence_path.stat().st_size,
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
            "globally_held_out_exact_task_init_pair_count": 18,
            "prior_population_protocol_count": 42,
            "excluded_prior_exact_pair_count": 311,
            "condition_count": 7,
            "stress_lane_count": 5292,
            "baseline_lane_count": 21168,
            "task_outcomes_read": False,
        },
        "condition_pass_count": pass_count,
        "condition_nonpass_count": len(conditions) - pass_count,
        "conditions": conditions,
        "model_mismatch_metrics": dict(analysis["model_mismatch_metrics"]),
        "dynamic_state_metrics": dict(analysis["dynamic_state_metrics"]),
        "force_constrained_metrics": dict(
            analysis["force_constrained_metrics"]
        ),
        "adaptive_force_metrics": dict(analysis["adaptive_force_metrics"]),
        "incremental_adaptive_force_metrics": dict(
            analysis["incremental_adaptive_force_metrics"]
        ),
        "cross_condition": {
            "total_v14_deadlock_lane_count": total_v14_deadlocks,
            "total_recovery_prevented_deadlock_lane_count": total_prevented,
            "total_residual_deadlock_lane_count": total_residual,
            "worst_prediction_execution_error_rad": worst_prediction_error,
            "worst_prediction_execution_error_condition": (
                worst_prediction_condition
            ),
            "maximum_attributable_joint_force_increment": (
                maximum_attributable_force
            ),
            "maximum_attributable_joint_force_increment_condition": (
                maximum_attributable_force_condition
            ),
            "worst_latency_p95_seconds": worst_p95,
            "worst_latency_p95_condition": worst_p95_condition,
            "worst_latency_max_seconds": worst_latency,
            "worst_latency_max_condition": worst_latency_condition,
            "worst_100ms_deadline_miss_rate": worst_miss_rate,
            "worst_100ms_deadline_miss_rate_condition": worst_miss_condition,
        },
        "failure_lanes": [*failure_lanes, _maximum_force_lane(evidence)],
        "completed_axes": {
            "model_parameter_and_step_role_audit": (
                analysis["model_mismatch_metrics"][
                    "physics_audit_failure_count"
                ]
                == 0
                and analysis["model_mismatch_metrics"][
                    "step_model_or_role_identity_failure_count"
                ]
                == 0
            ),
            "predictive_run_coverage": (
                analysis["model_mismatch_metrics"]["predictive_run_count"]
                == 10584
            ),
            "nontrivial_mismatch_run_coverage": (
                analysis["model_mismatch_metrics"][
                    "mismatch_predictive_run_count"
                ]
                == 9072
            ),
            "all_condition_zero_crossing_and_below_floor": all(
                row["crossing_count"] == 0 and row["below_floor_count"] == 0
                for row in conditions.values()
            ),
        },
        "nonpass_axes": {
            "actual_friction_0_7x_shadow_nominal": [
                "v15_3_attributable_force_envelope"
            ],
            "actual_friction_1_3x_shadow_nominal": [
                "v15_3_latency_max",
                "v15_3_prediction_execution_error",
                "v15_3_recovery_prevention_identity",
                "v15_3_zero_residual_deadlock",
            ],
        },
        "explicit_nonclaims": {
            "model_mismatch_robustness": False,
            "task_utility": False,
            "attacked_task_utility": False,
            "hard_real_time": False,
            "hardware_validation": False,
            "physical_safety": False,
        },
        "next_stage_decision": {
            "preserve_model_mismatch_nonpass_without_reinterpretation": True,
            "develop_mismatch_aware_force_and_liveness_successor": True,
            "reuse_qualification_population_for_requalification": False,
            "fresh_requalification_required_after_development_pass": True,
            "model_mismatch_claim_authorized": False,
            "same_model_physics_domain_claim_remains_authorized": True,
            "relax_actual_safety_or_force_thresholds": False,
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
        raise V15IncrementalAdaptiveForceModelMismatchTerminalError(
            "model-mismatch terminal summary already exists"
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
                "condition_pass_count": summary["condition_pass_count"],
                "condition_nonpass_count": summary["condition_nonpass_count"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
