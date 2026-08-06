#!/usr/bin/env python3
"""Freeze the immutable fresh held-out v15.7 qualification PASS."""

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
    freeze_v15_incremental_adaptive_force_physics_qualification as freezer,
)
from scripts import (  # noqa: E402
    run_v15_incremental_adaptive_force_physics_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "physics_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_incremental_adaptive_force_physics_qualification_terminal.py"
)
CREATED_AT = "2026-08-01T17:00:00+08:00"


class V15IncrementalAdaptiveForcePhysicsQualificationTerminalError(
    RuntimeError
):
    """Raised when the observed qualification PASS cannot be frozen."""


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
    if (
        evidence["qualification_pass"] is not True
        or evidence["physics_domain_robustness_claim_authorized"] is not True
    ):
        raise V15IncrementalAdaptiveForcePhysicsQualificationTerminalError(
            "terminalizer expected the observed v15.7 qualification PASS"
        )
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    analysis = evidence["analysis"]
    conditions = {}
    maxima: dict[str, float] = {}
    maximum_conditions: dict[str, str] = {}
    worst_p95 = -1.0
    worst_p95_condition = None
    worst_max = -1.0
    worst_max_condition = None
    worst_miss_rate = -1.0
    worst_miss_condition = None
    total_v14_deadlocks = 0
    total_recovery_selected = 0
    total_prevented = 0
    total_residual = 0
    for condition in protocol["design"]["physics_conditions"]:
        condition_id = str(condition["condition_id"])
        result = analysis["condition_results"][condition_id]
        gates = analysis["condition_gate_results"][condition_id]
        if not all(gates.values()):
            raise V15IncrementalAdaptiveForcePhysicsQualificationTerminalError(
                f"qualification condition unexpectedly failed: {condition_id}"
            )
        aggregate = result["aggregate"]
        recovery = result["recovery"]
        total_v14_deadlocks += int(
            recovery["v14_predictive_deadlock_lane_count"]
        )
        total_recovery_selected += int(recovery["selected_recovery_count"])
        total_prevented += int(
            recovery["v15_3_recovery_prevented_deadlock_lane_count"]
        )
        total_residual += int(
            recovery["v15_3_residual_deadlock_lane_count"]
        )
        force = _force_summary(result)
        for name, value in force.items():
            if name not in maxima or value > maxima[name]:
                maxima[name] = value
                maximum_conditions[name] = condition_id
        latency_budget = result["v15_3_latency_budget"]
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
        miss_rate = float(latency_budget["miss_rate"])
        if p95 > worst_p95:
            worst_p95, worst_p95_condition = p95, condition_id
        if maximum > worst_max:
            worst_max, worst_max_condition = maximum, condition_id
        if miss_rate > worst_miss_rate:
            worst_miss_rate, worst_miss_condition = miss_rate, condition_id
        conditions[condition_id] = {
            "physics_parameters": dict(condition),
            "registered_gate_results": dict(sorted(gates.items())),
            "failed_registered_gates": [],
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
                recovery["v15_3_residual_deadlock_lane_count"]
            ),
            "executed_step_availability": float(
                aggregate[
                    "v15_3_force_attributed_recovery_executed_step_availability"
                ]
            ),
            "v14_deadlock_lane_count": int(
                recovery["v14_predictive_deadlock_lane_count"]
            ),
            "recovery_selected_count": int(recovery["selected_recovery_count"]),
            "recovery_prevented_deadlock_lane_count": int(
                recovery["v15_3_recovery_prevented_deadlock_lane_count"]
            ),
            "force": force,
            "latency": {
                "p95_seconds": p95,
                "max_seconds": maximum,
                "deadline_seconds": latency_budget["deadline_seconds"],
                "miss_count": latency_budget["miss_count"],
                "miss_rate": miss_rate,
                "sample_count": latency_budget["sample_count"],
            },
        }
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.7-incremental-"
            "adaptive-force-physics-qualification-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": True,
        "physics_domain_robustness_claim_authorized": True,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "registered_gate_results": dict(sorted(evidence["gate_results"].items())),
        "failed_registered_gates": [],
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
            "prior_population_protocol_count": protocol["selection"][
                "prior_population_protocol_count"
            ],
            "excluded_prior_exact_pair_count": protocol["selection"][
                "prior_exact_pair_count"
            ],
            "all_prior_exact_pairs_excluded": protocol["selection"][
                "all_prior_exact_task_init_pairs_excluded"
            ],
            "condition_count": len(conditions),
            "stress_lane_count": protocol["gates"][
                "expected_total_stress_lane_count"
            ],
            "baseline_lane_count": protocol["gates"][
                "expected_total_baseline_lane_count"
            ],
            "dynamic_environment_count": protocol["design"][
                "dynamic_environment_count"
            ],
            "task_outcomes_used_for_selection": False,
            "task_outcomes_read": False,
        },
        "conditions": conditions,
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
            "total_recovery_selected_count": total_recovery_selected,
            "total_recovery_prevented_deadlock_lane_count": total_prevented,
            "total_residual_deadlock_lane_count": total_residual,
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
            "all_condition_crossing_floor_deadlock_containment": True,
            "all_condition_availability_one": True,
            "all_condition_registered_force_envelopes": True,
            "all_condition_latency_p95": worst_p95 < 0.1,
            "all_condition_latency_max": worst_max < 0.2,
            "all_condition_100ms_miss_rate": worst_miss_rate < 0.025,
            "all_dynamic_state_restores_exact": (
                analysis["dynamic_state_metrics"][
                    "v15_5_dynamic_state_restore_failure_count"
                ]
                == 0
            ),
            "incremental_short_circuit_identity": evidence["gate_results"][
                "v15_7_incremental_short_circuit_identity"
            ],
            "incremental_force_attribution_identity": evidence["gate_results"][
                "v15_7_incremental_force_attribution_identity"
            ],
            "all_condition_comparative_gates": evidence["gate_results"][
                "all_condition_comparative_gates"
            ],
            "all_condition_registered_gates": evidence["gate_results"][
                "all_condition_registered_gates"
            ],
        },
        "compatibility_label_note": (
            "Inherited v15_3 condition fields and v15_5 dynamic/force metric "
            "labels refer to the executed v15.7 baseline through frozen adapters. "
            "The inherited development_population_outcome_disclosed analysis "
            "marker describes adapter lineage, not this qualification population; "
            "the bound protocol proves all 18 pairs were globally held out."
        ),
        "predecessor_nonpass_reinterpreted": False,
        "explicit_nonclaims": {
            "model_mismatch_robustness": False,
            "task_utility": False,
            "attacked_task_utility": False,
            "hard_real_time": False,
            "hardware_validation": False,
            "physical_safety": False,
        },
        "next_stage_decision": {
            "same_model_physics_domain_claim_authorized": True,
            "freeze_fresh_model_mismatch_protocol": True,
            "reuse_physics_qualification_population_for_model_mismatch": False,
            "model_mismatch_claim_authorized": False,
            "task_utility_claim_authorized": False,
            "preserve_v15_4_v15_5_v15_6_nonpass_without_reinterpretation": True,
            "relax_registered_thresholds": False,
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
        raise V15IncrementalAdaptiveForcePhysicsQualificationTerminalError(
            "v15.7 qualification terminal summary already exists"
        )
    summary = build_summary(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(summary), encoding="utf-8")
    print(
        canonical_text(
            {
                "terminal_path": output.relative_to(REPO_ROOT).as_posix(),
                "terminal_sha256": file_sha256(output),
                "registered_qualification_pass": True,
                "total_prevented_deadlock_lane_count": summary[
                    "cross_condition"
                ]["total_recovery_prevented_deadlock_lane_count"],
                "worst_latency_max_seconds": summary["cross_condition"][
                    "worst_latency_max_seconds"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

