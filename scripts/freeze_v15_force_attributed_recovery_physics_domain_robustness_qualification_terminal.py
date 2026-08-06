#!/usr/bin/env python3
"""Freeze the immutable terminal record of the v15.3 physics qualification."""

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
    run_v15_force_attributed_recovery_physics_domain_robustness_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_recovery_"
    "physics_domain_robustness_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attributed_recovery_physics_domain_robustness_"
    "qualification_terminal.py"
)
CREATED_AT = "2026-08-01T00:20:00+08:00"


class V15PhysicsDomainTerminalError(RuntimeError):
    """Raised when the physics-domain terminal summary cannot be frozen."""


def _baseline_summary(aggregate: Mapping[str, Any], baseline: str) -> dict[str, Any]:
    return {
        "lane_count": aggregate[f"{baseline}_lane_count"],
        "crossing_count": aggregate[f"{baseline}_crossing_count"],
        "below_floor_count": aggregate[f"{baseline}_below_floor_count"],
        "deadlock_lane_count": aggregate[f"{baseline}_deadlock_lane_count"],
        "executed_step_availability": aggregate[
            f"{baseline}_executed_step_availability"
        ],
        "minimum_margin_rad": aggregate[f"{baseline}_minimum_margin_rad"],
        "maximum_abs_constraint_force": aggregate[
            f"{baseline}_maximum_abs_constraint_force"
        ],
        "screen_latency_sample_count": aggregate[
            f"{baseline}_screen_latency_sample_count"
        ],
        "screen_latency_seconds_p50": aggregate[
            f"{baseline}_screen_latency_seconds_p50"
        ],
        "screen_latency_seconds_p95": aggregate[
            f"{baseline}_screen_latency_seconds_p95"
        ],
        "screen_latency_seconds_p99": aggregate[
            f"{baseline}_screen_latency_seconds_p99"
        ],
        "screen_latency_seconds_max": aggregate[
            f"{baseline}_screen_latency_seconds_max"
        ],
    }


def _worst_recovery_attributable(
    rows: list[Mapping[str, Any]], condition_id: str
) -> dict[str, Any] | None:
    worst = None
    for row in rows:
        if row["condition_id"] != condition_id:
            continue
        report = row["baselines"][runner.V15_BASELINE]
        for step in report["force_attribution_steps"]:
            if step["recovery_selected"] is not True:
                continue
            value = float(
                step["guard_scope_maximum_positive_joint_increment_over_pre_step"]
            )
            if worst is None or value > worst["value"]:
                worst = {
                    "value": value,
                    "lane_id": str(row["lane_id"]),
                    "suite": str(row["suite"]),
                    "task_id": int(row["task_id"]),
                    "init_state_id": int(row["init_state_id"]),
                    "joint_index": int(row["joint_index"]),
                    "side": str(row["side"]),
                    "dose": str(row["dose"]["dose"]),
                    "runner_step_id": int(step["runner_step_id"]),
                    "pre_step_absolute_risk_force": float(
                        step["pre_step_maximum_abs_risk_constraint_force"]
                    ),
                    "guard_scope_absolute_risk_force": float(
                        step["guard_scope_reported_maximum_abs_risk_constraint_force"]
                    ),
                    "post_step_absolute_risk_force": float(
                        step["post_step_maximum_abs_risk_constraint_force"]
                    ),
                    "post_step_positive_joint_increment": float(
                        step["post_step_maximum_positive_joint_increment_over_pre_step"]
                    ),
                }
    return worst


def _deadlock_identity(
    rows: list[Mapping[str, Any]], condition_id: str
) -> dict[str, Any]:
    v14 = set()
    internal = set()
    prevented = set()
    for row in rows:
        if row["condition_id"] != condition_id:
            continue
        lane_id = str(row["lane_id"])
        if row["baselines"]["v14_predictive_brake"]["deadlock_count"] > 0:
            v14.add(lane_id)
        report = row["baselines"][runner.V15_BASELINE]
        if report["v14_baseline_would_deadlock_count"] > 0:
            internal.add(lane_id)
        if report["recovery_prevented_deadlock_count"] > 0:
            prevented.add(lane_id)
    return {
        "paired_identity": v14 == internal == prevented,
        "v14_deadlock_lane_count": len(v14),
        "v15_internal_would_deadlock_lane_count": len(internal),
        "v15_recovery_prevented_deadlock_lane_count": len(prevented),
        "v14_only_lane_ids": sorted(v14 - internal),
        "v15_internal_only_lane_ids": sorted(internal - v14),
        "internal_not_prevented_lane_ids": sorted(internal - prevented),
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(protocol, protocol_path=runner.DEFAULT_PROTOCOL)
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if evidence["qualification_pass"] is not False:
        raise V15PhysicsDomainTerminalError(
            "physics-domain terminalizer expected the observed nonpass"
        )
    analysis = evidence["analysis"]
    failed_overall = sorted(
        name for name, passed in evidence["gate_results"].items() if not passed
    )
    conditions = {}
    maximum_recovery_force = None
    maximum_recovery_force_condition = None
    total_deadline_misses = 0
    total_latency_samples = 0
    for condition in protocol["design"]["physics_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        aggregate = result["aggregate"]
        gates = analysis["condition_gate_results"][condition_id]
        force = result["force_comparison"]
        observed_force = force[
            "v15_3_maximum_recovery_attributable_joint_force_increment"
        ]
        if maximum_recovery_force is None or observed_force > maximum_recovery_force:
            maximum_recovery_force = observed_force
            maximum_recovery_force_condition = condition_id
        latency = result["v15_3_latency_budget"]
        total_deadline_misses += int(latency["miss_count"])
        total_latency_samples += int(latency["sample_count"])
        recovery = result["recovery"]
        contacts = result["contact_capacity"]
        conditions[condition_id] = {
            "physics_parameters": dict(condition),
            "registered_gate_results": dict(sorted(gates.items())),
            "failed_registered_gates": sorted(
                name for name, passed in gates.items() if not passed
            ),
            "comparative_gate_results": dict(
                sorted(analysis["comparative_gate_results"][condition_id].items())
            ),
            "baselines": {
                baseline: _baseline_summary(aggregate, baseline)
                for baseline in runner.BASELINES
            },
            "recovery": {
                "v14_predictive_deadlock_lane_count": recovery[
                    "v14_predictive_deadlock_lane_count"
                ],
                "v15_3_residual_deadlock_lane_count": recovery[
                    "v15_3_residual_deadlock_lane_count"
                ],
                "selected_recovery_count": recovery["selected_recovery_count"],
                "recovery_prevented_deadlock_count": recovery[
                    "recovery_prevented_deadlock_count"
                ],
                "current_edge_selected_count": recovery["current_edge_selected_count"],
                "floor_edge_selected_count": recovery["floor_edge_selected_count"],
                "selected_floor_violation_count": recovery[
                    "selected_floor_violation_count"
                ],
                "maximum_prediction_execution_error_rad": recovery[
                    "maximum_prediction_execution_error_rad"
                ],
            },
            "deadlock_prevention_identity": _deadlock_identity(
                evidence["lanes"], condition_id
            ),
            "force_comparison": dict(force),
            "worst_recovery_attributable_force": (
                _worst_recovery_attributable(evidence["lanes"], condition_id)
            ),
            "latency_budget": dict(latency),
            "active_contact_capacity": dict(contacts["phases"]["active"]),
        }
    all_v15_contained = all(
        row["baselines"][runner.V15_BASELINE]["crossing_count"] == 0
        and row["baselines"][runner.V15_BASELINE]["below_floor_count"] == 0
        and row["baselines"][runner.V15_BASELINE]["deadlock_lane_count"] == 0
        for row in conditions.values()
    )
    all_comparative = all(
        all(row["comparative_gate_results"].values()) for row in conditions.values()
    )
    force_pass_conditions = sorted(
        condition_id
        for condition_id, row in conditions.items()
        if row["registered_gate_results"]["v15_3_recovery_attributable_force_envelope"]
        is True
    )
    force_nonpass_conditions = sorted(set(conditions) - set(force_pass_conditions))
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
            "recovery-physics-domain-robustness-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": False,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "registered_gate_results": dict(sorted(evidence["gate_results"].items())),
        "failed_registered_gates": failed_overall,
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
            "held_out_exact_task_init_pair_count": len(protocol["environments"]),
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
            "all_prior_exact_pairs_excluded": True,
            "task_outcomes_read": False,
        },
        "conditions": conditions,
        "cross_condition": {
            "all_v15_3_crossing_floor_deadlock_containment": all_v15_contained,
            "all_comparative_gates_passed": all_comparative,
            "physics_parameter_audit_failure_count": analysis[
                "physics_parameter_audit_failure_count"
            ],
            "paired_lane_identity_across_conditions": analysis[
                "paired_lane_identity_across_conditions"
            ],
            "recovery_attributable_force_threshold": protocol["gates"][
                "maximum_recovery_attributable_joint_force_increment"
            ],
            "recovery_attributable_force_pass_conditions": force_pass_conditions,
            "recovery_attributable_force_nonpass_conditions": (
                force_nonpass_conditions
            ),
            "maximum_recovery_attributable_force": maximum_recovery_force,
            "maximum_recovery_attributable_force_condition": (
                maximum_recovery_force_condition
            ),
            "total_100ms_deadline_miss_count": total_deadline_misses,
            "total_latency_sample_count": total_latency_samples,
            "total_100ms_deadline_miss_rate": (
                total_deadline_misses / total_latency_samples
            ),
        },
        "completed_axes": {
            "all_condition_v15_3_joint_limit_proxy_containment": (all_v15_contained),
            "all_condition_v15_3_availability_one": all(
                row["baselines"][runner.V15_BASELINE]["executed_step_availability"]
                == 1.0
                for row in conditions.values()
            ),
            "all_condition_comparative_gates": all_comparative,
            "all_condition_active_warning_and_saturation_zero": all(
                row["active_contact_capacity"]["contact_capacity_warning_count"] == 0
                and row["active_contact_capacity"]["contact_saturation_count"] == 0
                for row in conditions.values()
            ),
            "all_condition_registered_gates": False,
        },
        "nonpass_axes": {
            "recovery_attributable_force_envelope": force_nonpass_conditions,
            "recovery_prevention_identity": [
                condition_id
                for condition_id, row in conditions.items()
                if row["registered_gate_results"]["v15_3_recovery_prevention_identity"]
                is False
            ],
        },
        "claim_boundary": protocol["claim_boundary"],
        "explicit_nonclaims": {
            "full_physics_domain_robustness_qualification_pass": False,
            "task_utility": False,
            "attacked_efficacy": False,
            "model_mismatch_robustness": False,
            "hard_real_time": False,
            "hardware_behavior": False,
            "actuator_authority": False,
            "physical_safety": False,
            "threshold_relaxation": False,
        },
        "next_stage_decision": {
            "physics_domain_robustness_claim_authorized": False,
            "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
            "proceed_to_new_component_ablation_population": True,
            "develop_force_bounded_successor_before_physics_requalification": (True),
            "diagnose_joint_damping_1_3x_identity_lane": True,
            "model_mismatch_qualification_authorized": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15PhysicsDomainTerminalError(
            "physics-domain terminal summary already exists"
        )
    summary = build_summary(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(summary), encoding="utf-8")
    print(
        canonical_text(
            {
                "terminal_summary_path": output.relative_to(REPO_ROOT).as_posix(),
                "terminal_summary_sha256": file_sha256(output),
                "registered_classification": summary["registered_classification"],
                "registered_qualification_pass": summary[
                    "registered_qualification_pass"
                ],
                "failed_registered_gates": summary["failed_registered_gates"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
