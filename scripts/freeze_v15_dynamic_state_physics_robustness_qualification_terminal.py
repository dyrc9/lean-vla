#!/usr/bin/env python3
"""Freeze the immutable v15.4 held-out physics qualification result."""

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
    freeze_v15_dynamic_state_physics_development_terminal as development_terminal,
)
from scripts import (  # noqa: E402
    run_v15_dynamic_state_physics_robustness_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_domain_robustness_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_dynamic_state_physics_robustness_qualification_terminal.py"
)
CREATED_AT = "2026-08-01T04:00:00+08:00"


class V15DynamicStatePhysicsQualificationTerminalError(RuntimeError):
    """Raised when the v15.4 qualification terminal record cannot freeze."""


def _worst_force_step(
    rows: list[Mapping[str, Any]],
    condition_id: str,
    field: str,
    *,
    recovery_only: bool = False,
) -> dict[str, Any] | None:
    worst = None
    for row in rows:
        if row["condition_id"] != condition_id:
            continue
        report = row["baselines"][runner.V15_BASELINE]
        for step in report["force_attribution_steps"]:
            if recovery_only and step["recovery_selected"] is not True:
                continue
            value = float(step[field])
            if worst is None or value > worst["value"]:
                worst = {
                    "value": value,
                    "field": field,
                    "lane_id": str(row["lane_id"]),
                    "suite": str(row["suite"]),
                    "task_id": int(row["task_id"]),
                    "init_state_id": int(row["init_state_id"]),
                    "joint_index": int(row["joint_index"]),
                    "side": str(row["side"]),
                    "dose": str(row["dose"]["dose"]),
                    "runner_step_id": int(step["runner_step_id"]),
                    "recovery_selected": bool(step["recovery_selected"]),
                    "guard_scope_attributable_increment": float(
                        step[
                            "guard_scope_maximum_positive_joint_increment_over_pre_step"
                        ]
                    ),
                    "guard_scope_absolute_risk_force": float(
                        step[
                            "guard_scope_reported_maximum_abs_risk_constraint_force"
                        ]
                    ),
                    "pre_step_absolute_risk_force": float(
                        step["pre_step_maximum_abs_risk_constraint_force"]
                    ),
                    "post_step_absolute_risk_force": float(
                        step["post_step_maximum_abs_risk_constraint_force"]
                    ),
                    "post_step_positive_joint_increment": float(
                        step[
                            "post_step_maximum_positive_joint_increment_over_pre_step"
                        ]
                    ),
                }
    return worst


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol, protocol_path=runner.DEFAULT_PROTOCOL
    )
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if evidence["qualification_pass"] is not False:
        raise V15DynamicStatePhysicsQualificationTerminalError(
            "v15.4 qualification terminalizer expected observed nonpass"
        )
    analysis = evidence["analysis"]
    failed_overall = sorted(
        name for name, passed in evidence["gate_results"].items() if not passed
    )
    conditions = {}
    nonpass_axes: dict[str, list[str]] = {}
    maximum_recovery_force = -1.0
    maximum_recovery_force_condition = None
    maximum_all_attributable_force = -1.0
    maximum_all_attributable_force_condition = None
    maximum_post_absolute_force = -1.0
    maximum_post_absolute_force_condition = None
    maximum_post_increment = -1.0
    maximum_post_increment_condition = None
    maximum_recovery_post_increment = -1.0
    maximum_recovery_post_increment_condition = None
    total_v14_deadlock_lanes = 0
    total_recovery_selected = 0
    for condition in protocol["design"]["physics_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        aggregate = result["aggregate"]
        gates = analysis["condition_gate_results"][condition_id]
        failed = sorted(name for name, passed in gates.items() if not passed)
        for name in failed:
            nonpass_axes.setdefault(name, []).append(condition_id)
        force = result["force_comparison"]
        force_values = {
            "recovery": float(
                force[
                    "v15_4_maximum_recovery_attributable_joint_force_increment"
                ]
            ),
            "all_attributable": float(
                force["v15_4_maximum_attributable_joint_force_increment"]
            ),
            "post_absolute": float(
                force["v15_4_maximum_post_step_absolute_risk_force"]
            ),
            "post_increment": float(
                force["v15_4_maximum_post_step_positive_joint_increment"]
            ),
            "recovery_post_increment": float(
                force[
                    "v15_4_maximum_recovery_post_step_positive_joint_increment"
                ]
            ),
        }
        if force_values["recovery"] > maximum_recovery_force:
            maximum_recovery_force = force_values["recovery"]
            maximum_recovery_force_condition = condition_id
        if force_values["all_attributable"] > maximum_all_attributable_force:
            maximum_all_attributable_force = force_values["all_attributable"]
            maximum_all_attributable_force_condition = condition_id
        if force_values["post_absolute"] > maximum_post_absolute_force:
            maximum_post_absolute_force = force_values["post_absolute"]
            maximum_post_absolute_force_condition = condition_id
        if force_values["post_increment"] > maximum_post_increment:
            maximum_post_increment = force_values["post_increment"]
            maximum_post_increment_condition = condition_id
        if (
            force_values["recovery_post_increment"]
            > maximum_recovery_post_increment
        ):
            maximum_recovery_post_increment = force_values[
                "recovery_post_increment"
            ]
            maximum_recovery_post_increment_condition = condition_id
        recovery = result["recovery"]
        total_v14_deadlock_lanes += int(
            recovery["v14_predictive_deadlock_lane_count"]
        )
        total_recovery_selected += int(recovery["selected_recovery_count"])
        contacts = result["contact_capacity"]
        conditions[condition_id] = {
            "physics_parameters": dict(condition),
            "registered_gate_results": dict(sorted(gates.items())),
            "failed_registered_gates": failed,
            "comparative_gate_results": dict(
                sorted(
                    analysis["comparative_gate_results"][condition_id].items()
                )
            ),
            "baselines": {
                baseline: development_terminal._baseline_summary(
                    aggregate, baseline
                )
                for baseline in runner.BASELINES
            },
            "recovery": {
                "v14_predictive_deadlock_lane_count": recovery[
                    "v14_predictive_deadlock_lane_count"
                ],
                "v15_4_residual_deadlock_lane_count": recovery[
                    "v15_4_residual_deadlock_lane_count"
                ],
                "selected_recovery_count": recovery[
                    "selected_recovery_count"
                ],
                "recovery_prevented_deadlock_count": recovery[
                    "recovery_prevented_deadlock_count"
                ],
                "selected_floor_violation_count": recovery[
                    "selected_floor_violation_count"
                ],
                "maximum_prediction_execution_error_rad": recovery[
                    "maximum_prediction_execution_error_rad"
                ],
            },
            "deadlock_prevention_identity": (
                development_terminal._deadlock_identity(
                    evidence["lanes"], condition_id
                )
            ),
            "force_comparison": dict(force),
            "worst_all_attributable_force": _worst_force_step(
                evidence["lanes"],
                condition_id,
                "guard_scope_maximum_positive_joint_increment_over_pre_step",
            ),
            "worst_post_step_absolute_force": _worst_force_step(
                evidence["lanes"],
                condition_id,
                "post_step_maximum_abs_risk_constraint_force",
            ),
            "worst_post_step_increment": _worst_force_step(
                evidence["lanes"],
                condition_id,
                "post_step_maximum_positive_joint_increment_over_pre_step",
            ),
            "worst_recovery_post_step_increment": _worst_force_step(
                evidence["lanes"],
                condition_id,
                "post_step_maximum_positive_joint_increment_over_pre_step",
                recovery_only=True,
            ),
            "latency_budget": dict(result["v15_4_latency_budget"]),
            "active_contact_capacity": dict(contacts["phases"]["active"]),
        }
    all_v15_contained = all(
        row["baselines"][runner.V15_BASELINE]["crossing_count"] == 0
        and row["baselines"][runner.V15_BASELINE]["below_floor_count"] == 0
        and row["baselines"][runner.V15_BASELINE]["deadlock_lane_count"] == 0
        for row in conditions.values()
    )
    all_comparative = all(
        all(row["comparative_gate_results"].values())
        for row in conditions.values()
    )
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.4-dynamic-state-"
            "physics-domain-robustness-qualification-terminal.v1"
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
            "globally_held_out_exact_task_init_pair_count": len(
                protocol["environments"]
            ),
            "excluded_prior_exact_pair_count": protocol["selection"][
                "prior_exact_pair_count"
            ],
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
        "dynamic_state_metrics": dict(analysis["dynamic_state_metrics"]),
        "conditions": conditions,
        "cross_condition": {
            "all_v15_4_crossing_floor_deadlock_containment": all_v15_contained,
            "all_comparative_gates_passed": all_comparative,
            "physics_parameter_audit_failure_count": analysis[
                "physics_parameter_audit_failure_count"
            ],
            "paired_lane_identity_across_conditions": analysis[
                "paired_lane_identity_across_conditions"
            ],
            "total_v14_deadlock_lane_count": total_v14_deadlock_lanes,
            "total_v15_4_residual_deadlock_lane_count": 0,
            "total_recovery_selected_count": total_recovery_selected,
            "maximum_recovery_attributable_force": maximum_recovery_force,
            "maximum_recovery_attributable_force_condition": (
                maximum_recovery_force_condition
            ),
            "maximum_all_attributable_force": maximum_all_attributable_force,
            "maximum_all_attributable_force_condition": (
                maximum_all_attributable_force_condition
            ),
            "maximum_post_step_absolute_force": maximum_post_absolute_force,
            "maximum_post_step_absolute_force_condition": (
                maximum_post_absolute_force_condition
            ),
            "maximum_post_step_increment": maximum_post_increment,
            "maximum_post_step_increment_condition": (
                maximum_post_increment_condition
            ),
            "maximum_recovery_post_step_increment": (
                maximum_recovery_post_increment
            ),
            "maximum_recovery_post_step_increment_condition": (
                maximum_recovery_post_increment_condition
            ),
        },
        "completed_axes": {
            "all_condition_v15_4_joint_limit_proxy_containment": (
                all_v15_contained
            ),
            "all_condition_v15_4_availability_one": all(
                row["baselines"][runner.V15_BASELINE][
                    "executed_step_availability"
                ]
                == 1.0
                for row in conditions.values()
            ),
            "all_condition_recovery_attributable_force_envelope": all(
                row["registered_gate_results"][
                    "v15_4_recovery_attributable_force_envelope"
                ]
                for row in conditions.values()
            ),
            "all_condition_latency_gates": all(
                row["registered_gate_results"]["v15_4_latency_p95"]
                and row["registered_gate_results"]["v15_4_latency_max"]
                and row["registered_gate_results"][
                    "v15_4_100ms_deadline_miss_rate"
                ]
                for row in conditions.values()
            ),
            "all_dynamic_state_restores_exact": analysis[
                "dynamic_state_metrics"
            ]["v15_4_dynamic_state_restore_failure_count"]
            == 0,
            "all_condition_comparative_gates": all_comparative,
            "all_condition_registered_gates": False,
        },
        "nonpass_axes": dict(sorted(nonpass_axes.items())),
        "claim_boundary": protocol["claim_boundary"],
        "explicit_nonclaims": {
            "full_physics_domain_robustness_qualification_pass": False,
            "model_mismatch_robustness": False,
            "task_utility": False,
            "attacked_efficacy": False,
            "hard_real_time": False,
            "hardware_behavior": False,
            "actuator_authority": False,
            "physical_safety": False,
            "threshold_relaxation": False,
        },
        "next_stage_decision": {
            "physics_domain_robustness_claim_authorized": False,
            "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
            "develop_force_constrained_successor": True,
            "use_human_safety_task13_init10_as_disclosed_development_case": True,
            "require_new_population_for_requalification": True,
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
        raise V15DynamicStatePhysicsQualificationTerminalError(
            "v15.4 qualification terminal summary already exists"
        )
    summary = build_summary(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(summary), encoding="utf-8")
    print(
        canonical_text(
            {
                "terminal_summary_path": output.relative_to(REPO_ROOT).as_posix(),
                "terminal_summary_sha256": file_sha256(output),
                "registered_classification": summary[
                    "registered_classification"
                ],
                "registered_qualification_pass": summary[
                    "registered_qualification_pass"
                ],
                "failed_registered_gates": summary[
                    "failed_registered_gates"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
