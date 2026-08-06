#!/usr/bin/env python3
"""Freeze the immutable terminal record of v15.6 development."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v15_adaptive_force_physics_development as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_adaptive_force_"
    "physics_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_adaptive_force_physics_development_terminal.py"
)
CREATED_AT = "2026-08-01T11:00:00+08:00"


class V15AdaptiveForcePhysicsDevelopmentTerminalError(RuntimeError):
    """Raised when the v15.6 terminal record cannot be frozen."""


def _failed(mapping: Mapping[str, Any]) -> list[str]:
    return sorted(name for name, passed in mapping.items() if passed is not True)


def _worst_latency_lane(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    worst = None
    for row in rows:
        report = row["baselines"][runner.V15_BASELINE]
        for step_id, latency in enumerate(report["screen_latency_seconds_values"]):
            value = float(latency)
            if worst is None or value > worst["latency_seconds"]:
                worst = {
                    "latency_seconds": value,
                    "runner_step_id": step_id,
                    "lane_id": str(row["lane_id"]),
                    "condition_id": str(row["condition_id"]),
                    "suite": str(row["suite"]),
                    "task_id": int(row["task_id"]),
                    "init_state_id": int(row["init_state_id"]),
                    "joint_index": int(row["joint_index"]),
                    "side": str(row["side"]),
                    "dose": str(row["dose"]["dose"]),
                    "extended_recovery_evaluated_count": int(
                        report["extended_recovery_evaluated_count"]
                    ),
                    "extended_recovery_selected_count": int(
                        report["extended_recovery_selected_count"]
                    ),
                }
    if worst is None:
        raise V15AdaptiveForcePhysicsDevelopmentTerminalError(
            "v15.6 evidence has no latency samples"
        )
    return worst


def _force_summary(result: Mapping[str, Any]) -> dict[str, float]:
    force = result["force_comparison"]
    return {
        "maximum_attributable_joint_force_increment": float(
            force["v15_3_maximum_attributable_joint_force_increment"]
        ),
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
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol, protocol_path=runner.DEFAULT_PROTOCOL
    )
    if evidence["development_pass"] is not False:
        raise V15AdaptiveForcePhysicsDevelopmentTerminalError(
            "v15.6 terminalizer expected the observed development NONPASS"
        )
    root = runner._output_root(protocol)
    evidence_path = root / "development_evidence.json"
    checksums_path = root / "SHA256SUMS"
    analysis = evidence["analysis"]
    conditions = {}
    nonpass_axes: dict[str, list[str]] = {}
    total_deadlocks = 0
    maxima: dict[str, float] = {}
    maximum_conditions: dict[str, str] = {}
    worst_p95 = -1.0
    worst_p95_condition = None
    worst_max = -1.0
    worst_max_condition = None
    worst_miss_rate = -1.0
    worst_miss_condition = None
    for condition in protocol["design"]["physics_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        gates = analysis["condition_gate_results"][condition_id]
        failed = _failed(gates)
        for name in failed:
            nonpass_axes.setdefault(name, []).append(condition_id)
        aggregate = result["aggregate"]
        recovery_result = result["recovery"]
        total_deadlocks += int(
            recovery_result["v15_3_residual_deadlock_lane_count"]
        )
        force = _force_summary(result)
        for name, value in force.items():
            if name not in maxima or value > maxima[name]:
                maxima[name] = value
                maximum_conditions[name] = condition_id
        latency = result["v15_3_latency_budget"]
        p95 = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_p95"
            ]
        )
        maximum = float(
            aggregate[
                "v15_3_force_attributed_recovery_screen_latency_seconds_max"
            ]
        )
        miss_rate = float(latency["miss_rate"])
        if p95 > worst_p95:
            worst_p95, worst_p95_condition = p95, condition_id
        if maximum > worst_max:
            worst_max, worst_max_condition = maximum, condition_id
        if miss_rate > worst_miss_rate:
            worst_miss_rate, worst_miss_condition = miss_rate, condition_id
        conditions[condition_id] = {
            "physics_parameters": dict(condition),
            "registered_gate_results": dict(sorted(gates.items())),
            "failed_registered_gates": failed,
            "comparative_gate_results": dict(
                sorted(
                    analysis["comparative_gate_results"][condition_id].items()
                )
            ),
            "crossing_count": int(
                aggregate["v15_3_force_attributed_recovery_crossing_count"]
            ),
            "below_floor_count": int(
                aggregate[
                    "v15_3_force_attributed_recovery_below_floor_count"
                ]
            ),
            "residual_deadlock_lane_count": int(
                recovery_result["v15_3_residual_deadlock_lane_count"]
            ),
            "executed_step_availability": float(
                aggregate[
                    "v15_3_force_attributed_recovery_executed_step_availability"
                ]
            ),
            "force": force,
            "latency": {
                "p50_seconds": aggregate[
                    "v15_3_force_attributed_recovery_screen_latency_seconds_p50"
                ],
                "p95_seconds": p95,
                "p99_seconds": aggregate[
                    "v15_3_force_attributed_recovery_screen_latency_seconds_p99"
                ],
                "max_seconds": maximum,
                "deadline_seconds": latency["deadline_seconds"],
                "miss_count": latency["miss_count"],
                "miss_rate": miss_rate,
                "sample_count": latency["sample_count"],
            },
        }
    force_gate_names = (
        "v15_3_attributable_force_envelope",
        "v15_3_post_step_absolute_force_envelope",
        "v15_3_post_step_increment_envelope",
        "v15_3_recovery_attributable_force_envelope",
        "v15_3_recovery_post_step_increment_envelope",
    )
    all_force = all(
        all(gates[name] for name in force_gate_names)
        for gates in analysis["condition_gate_results"].values()
    )
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.6-adaptive-force-"
            "physics-development-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_development_pass": False,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "registered_gate_results": dict(sorted(evidence["gate_results"].items())),
        "failed_registered_gates": _failed(evidence["gate_results"]),
        "bindings": {
            "protocol": {
                "path": runner.DEFAULT_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(runner.DEFAULT_PROTOCOL),
            },
            "evidence": {
                "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(evidence_path),
            },
            "checksums": {
                "path": checksums_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksums_path),
                "entry_count": len(
                    checksums_path.read_text(encoding="utf-8").splitlines()
                ),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "outcome_disclosed_exact_task_init_pair_count": len(
                protocol["environments"]
            ),
            "condition_count": len(conditions),
            "total_stress_lane_count": protocol["gates"][
                "expected_total_stress_lane_count"
            ],
            "total_baseline_lane_count": protocol["gates"][
                "expected_total_baseline_lane_count"
            ],
            "development_population_outcome_disclosed": True,
            "task_outcomes_read": False,
        },
        "conditions": conditions,
        "nonpass_axes": {
            name: sorted(condition_ids)
            for name, condition_ids in sorted(nonpass_axes.items())
        },
        "worst_latency_lane": _worst_latency_lane(evidence["lanes"]),
        "dynamic_state_metrics": dict(analysis["dynamic_state_metrics"]),
        "force_constrained_metrics": dict(
            analysis["force_constrained_metrics"]
        ),
        "adaptive_force_metrics": dict(analysis["adaptive_force_metrics"]),
        "cross_condition": {
            "total_residual_deadlock_lane_count": total_deadlocks,
            "all_crossing_floor_deadlock_containment": all(
                row["crossing_count"] == 0
                and row["below_floor_count"] == 0
                and row["residual_deadlock_lane_count"] == 0
                for row in conditions.values()
            ),
            "all_executed_step_availability_one": all(
                row["executed_step_availability"] == 1.0
                for row in conditions.values()
            ),
            "all_registered_force_envelopes_pass": all_force,
            "worst_latency_p95_seconds": worst_p95,
            "worst_latency_p95_condition": worst_p95_condition,
            "worst_latency_max_seconds": worst_max,
            "worst_latency_max_condition": worst_max_condition,
            "worst_100ms_deadline_miss_rate": worst_miss_rate,
            "worst_100ms_deadline_miss_rate_condition": worst_miss_condition,
            **maxima,
            **{
                f"{name}_condition": condition
                for name, condition in maximum_conditions.items()
            },
        },
        "completed_axes": {
            "all_condition_crossing_floor_deadlock_containment": (
                total_deadlocks == 0
                and all(
                    row["crossing_count"] == 0
                    and row["below_floor_count"] == 0
                    for row in conditions.values()
                )
            ),
            "all_condition_availability_one": all(
                row["executed_step_availability"] == 1.0
                for row in conditions.values()
            ),
            "all_condition_registered_force_envelopes": all_force,
            "all_condition_latency_p95": worst_p95 < 0.1,
            "all_condition_100ms_miss_rate": worst_miss_rate < 0.025,
            "all_condition_latency_max": worst_max < 0.2,
            "all_dynamic_state_restores_exact": (
                analysis["dynamic_state_metrics"][
                    "v15_6_dynamic_state_restore_failure_count"
                ]
                == 0
            ),
            "all_condition_comparative_gates": evidence["gate_results"][
                "all_condition_comparative_gates"
            ],
            "all_condition_registered_gates": evidence["gate_results"][
                "all_condition_registered_gates"
            ],
        },
        "predecessor_nonpass_reinterpreted": False,
        "explicit_nonclaims": {
            "qualification_pass": False,
            "physics_domain_robustness": False,
            "model_mismatch_robustness": False,
            "task_utility": False,
            "hard_real_time": False,
            "hardware_validation": False,
            "physical_safety": False,
        },
        "next_stage_decision": {
            "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
            "develop_incremental_extended_search_successor": True,
            "preserve_proactive_trigger_and_force_thresholds": True,
            "correct_extended_recovery_force_attribution": True,
            "fresh_requalification_authorized": False,
            "require_development_pass_before_requalification": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15AdaptiveForcePhysicsDevelopmentTerminalError(
            "v15.6 terminal summary already exists"
        )
    summary = build_summary(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(summary), encoding="utf-8")
    print(
        canonical_text(
            {
                "terminal_path": output.relative_to(REPO_ROOT).as_posix(),
                "terminal_sha256": file_sha256(output),
                "registered_development_pass": False,
                "worst_latency_seconds": summary["worst_latency_lane"][
                    "latency_seconds"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
