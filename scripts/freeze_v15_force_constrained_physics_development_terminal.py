#!/usr/bin/env python3
"""Freeze the immutable terminal record of v15.5 physics development."""

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
from scripts import (  # noqa: E402
    run_v15_force_constrained_physics_development as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_constrained_"
    "physics_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_constrained_physics_development_terminal.py"
)
CREATED_AT = "2026-08-01T07:00:00+08:00"


class V15ForceConstrainedPhysicsDevelopmentTerminalError(RuntimeError):
    """Raised when the v15.5 terminal record cannot be frozen."""


def _failed(mapping: Mapping[str, Any]) -> list[str]:
    return sorted(name for name, passed in mapping.items() if passed is not True)


def _deadlock_lanes(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deadlocks = []
    for row in rows:
        report = row["baselines"][runner.V15_BASELINE]
        if int(report["deadlock_count"]) == 0:
            continue
        deadlocks.append(
            {
                "lane_id": str(row["lane_id"]),
                "condition_id": str(row["condition_id"]),
                "suite": str(row["suite"]),
                "task_id": int(row["task_id"]),
                "init_state_id": int(row["init_state_id"]),
                "joint_index": int(row["joint_index"]),
                "side": str(row["side"]),
                "dose": str(row["dose"]["dose"]),
                "policy_decision_count": int(report["policy_decision_count"]),
                "executed_step_count": int(report["executed_step_count"]),
                "stop_reason": str(report["stop_reason"]),
                "force_rejected_base_eligible_candidate_count": int(
                    report["force_rejected_base_eligible_candidate_count"]
                ),
                "minimum_margin_rad": float(report["minimum_margin_rad"]),
            }
        )
    return sorted(deadlocks, key=lambda row: row["lane_id"])


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
        raise V15ForceConstrainedPhysicsDevelopmentTerminalError(
            "v15.5 terminalizer expected the observed development NONPASS"
        )
    root = runner._output_root(protocol)
    evidence_path = root / "development_evidence.json"
    checksums_path = root / "SHA256SUMS"
    analysis = evidence["analysis"]
    conditions = {}
    nonpass_axes: dict[str, list[str]] = {}
    maxima = {
        "maximum_attributable_joint_force_increment": -1.0,
        "maximum_recovery_attributable_joint_force_increment": -1.0,
        "maximum_post_step_absolute_risk_force": -1.0,
        "maximum_post_step_positive_joint_increment": -1.0,
        "maximum_recovery_post_step_positive_joint_increment": -1.0,
    }
    maximum_conditions: dict[str, str | None] = {
        name: None for name in maxima
    }
    total_v14_deadlocks = 0
    total_residual_deadlocks = 0
    total_recovery_selected = 0
    for condition in protocol["design"]["physics_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        gates = analysis["condition_gate_results"][condition_id]
        failed = _failed(gates)
        for name in failed:
            nonpass_axes.setdefault(name, []).append(condition_id)
        recovery = result["recovery"]
        total_v14_deadlocks += int(
            recovery["v14_predictive_deadlock_lane_count"]
        )
        total_residual_deadlocks += int(
            recovery["v15_3_residual_deadlock_lane_count"]
        )
        total_recovery_selected += int(recovery["selected_recovery_count"])
        force = _force_summary(result)
        for name, value in force.items():
            if value > maxima[name]:
                maxima[name] = value
                maximum_conditions[name] = condition_id
        aggregate = result["aggregate"]
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
                aggregate[
                    "v15_3_force_attributed_recovery_crossing_count"
                ]
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
            "minimum_margin_rad": float(
                aggregate[
                    "v15_3_force_attributed_recovery_minimum_margin_rad"
                ]
            ),
            "v14_deadlock_lane_count": int(
                recovery["v14_predictive_deadlock_lane_count"]
            ),
            "v15_5_residual_deadlock_lane_count": int(
                recovery["v15_3_residual_deadlock_lane_count"]
            ),
            "recovery_prevented_deadlock_lane_count": int(
                recovery["v15_3_recovery_prevented_deadlock_lane_count"]
            ),
            "force": force,
            "latency_budget": dict(result["v15_3_latency_budget"]),
            "screen_latency_seconds_p95": float(
                aggregate[
                    "v15_3_force_attributed_recovery_screen_latency_seconds_p95"
                ]
            ),
            "screen_latency_seconds_max": float(
                aggregate[
                    "v15_3_force_attributed_recovery_screen_latency_seconds_max"
                ]
            ),
        }
    deadlocks = _deadlock_lanes(evidence["lanes"])
    force_metrics = dict(analysis["force_constrained_metrics"])
    all_force_envelopes_pass = all(
        all(
            gates[name]
            for name in (
                "v15_3_attributable_force_envelope",
                "v15_3_post_step_absolute_force_envelope",
                "v15_3_post_step_increment_envelope",
                "v15_3_recovery_attributable_force_envelope",
                "v15_3_recovery_post_step_increment_envelope",
            )
        )
        for gates in analysis["condition_gate_results"].values()
    )
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.5-force-constrained-"
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
            "stress_lane_count_per_condition": protocol["gates"][
                "expected_stress_lane_count"
            ],
            "total_stress_lane_count": protocol["gates"][
                "expected_total_stress_lane_count"
            ],
            "baseline_count": len(runner.BASELINES),
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
        "residual_deadlock_lanes": deadlocks,
        "dynamic_state_metrics": dict(analysis["dynamic_state_metrics"]),
        "force_constrained_metrics": force_metrics,
        "cross_condition": {
            "total_v14_deadlock_lane_count": total_v14_deadlocks,
            "total_v15_5_residual_deadlock_lane_count": total_residual_deadlocks,
            "total_recovery_selected_count": total_recovery_selected,
            "all_v15_5_crossing_and_floor_containment": all(
                row["crossing_count"] == 0 and row["below_floor_count"] == 0
                for row in conditions.values()
            ),
            "all_registered_force_envelopes_pass": all_force_envelopes_pass,
            "all_comparative_gates_pass": all(
                all(row["comparative_gate_results"].values())
                for row in conditions.values()
            ),
            **maxima,
            **{
                f"{name}_condition": condition
                for name, condition in maximum_conditions.items()
            },
        },
        "completed_axes": {
            "all_condition_crossing_and_floor_containment": all(
                row["crossing_count"] == 0 and row["below_floor_count"] == 0
                for row in conditions.values()
            ),
            "all_condition_registered_force_envelopes": all_force_envelopes_pass,
            "all_selected_candidates_force_feasible": evidence["gate_results"][
                "v15_5_selected_force_feasible"
            ],
            "all_selected_post_force_predictions_exact": evidence[
                "gate_results"
            ]["v15_5_selected_post_force_prediction_identity"],
            "force_rejection_activated": evidence["gate_results"][
                "v15_5_force_rejection_activated"
            ],
            "soft_profile_identity": evidence["gate_results"][
                "v15_5_soft_profile_identity"
            ],
            "all_dynamic_state_restores_exact": (
                analysis["dynamic_state_metrics"][
                    "v15_5_dynamic_state_restore_failure_count"
                ]
                == 0
            ),
            "all_condition_comparative_gates": evidence["gate_results"][
                "all_condition_comparative_gates"
            ],
            "zero_residual_deadlock": total_residual_deadlocks == 0,
            "all_condition_registered_gates": evidence["gate_results"][
                "all_condition_registered_gates"
            ],
        },
        "compatibility_label_note": (
            "Condition-level inherited v15_3 analysis field names refer to the "
            "executed v15.5 baseline through the frozen compatibility adapter."
        ),
        "predecessor_v15_4_nonpass_reinterpreted": False,
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
            "develop_fail_safe_force_constrained_successor": True,
            "use_two_residual_deadlock_lanes_as_disclosed_development_cases": True,
            "fresh_requalification_authorized": False,
            "require_development_pass_before_requalification": True,
            "relax_registered_force_thresholds": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15ForceConstrainedPhysicsDevelopmentTerminalError(
            "v15.5 terminal summary already exists"
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
                "residual_deadlock_lane_count": len(
                    summary["residual_deadlock_lanes"]
                ),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
