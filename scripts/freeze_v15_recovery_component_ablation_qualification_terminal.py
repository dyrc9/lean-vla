#!/usr/bin/env python3
"""Freeze the terminal record of the held-out v15 component ablation."""

from __future__ import annotations

import argparse
from pathlib import Path
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
from scripts import (  # noqa: E402
    run_v15_recovery_component_ablation_qualification as runner,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_recovery_component_"
    "ablation_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_recovery_component_ablation_qualification_terminal.py"
)
CREATED_AT = "2026-08-01T00:50:00+08:00"


class V15ComponentAblationTerminalError(RuntimeError):
    """Raised when the component-ablation terminal cannot be frozen."""


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


def _identity_worst_cases(
    rows: list[Mapping[str, Any]], *, limit: int = 10
) -> dict[str, Any]:
    scalar_fields = (
        "executed_step_count",
        "policy_decision_count",
        "trigger_count",
        "intervention_count",
        "deadlock_count",
        "reactive_stop_count",
        "shadow_env_step_count",
        "restore_failure_count",
        "exact_action_mismatch_count",
        "below_floor_count",
        "crossing_count",
        "observed_state_count",
        "observed_side_value_count",
        "current_edge_selected_count",
        "floor_edge_selected_count",
        "selected_recovery_count",
        "selected_floor_violation_count",
    )
    v15_rows = []
    shadow_rows = []
    for row in rows:
        baselines = row["baselines"]
        priority = baselines[runner.PRIORITY_BASELINE]
        attributed = baselines[runner.V15_3_BASELINE]
        priority_trace = runner._margin_trace(priority)
        attributed_trace = runner._margin_trace(attributed)
        margin_error = None
        if priority_trace.shape == attributed_trace.shape and priority_trace.size:
            margin_error = float(np.max(np.abs(priority_trace - attributed_trace)))
        mismatches = {
            field: [priority.get(field), attributed.get(field)]
            for field in scalar_fields
            if priority.get(field) != attributed.get(field)
        }
        if mismatches or (margin_error is not None and margin_error > 0):
            v15_rows.append(
                {
                    "lane_id": str(row["lane_id"]),
                    "scalar_mismatches": mismatches,
                    "maximum_actual_margin_trace_error_rad": margin_error,
                    "v15_2_minimum_margin_rad": priority["minimum_margin_rad"],
                    "v15_3_minimum_margin_rad": attributed["minimum_margin_rad"],
                }
            )
        no_guard = runner._margin_trace(baselines["no_guard"])
        shadow = runner._margin_trace(baselines["shadow_only"])
        shadow_error = None
        if no_guard.shape == shadow.shape and no_guard.size:
            shadow_error = float(np.max(np.abs(no_guard - shadow)))
        if shadow_error is not None and shadow_error > 0:
            shadow_rows.append(
                {
                    "lane_id": str(row["lane_id"]),
                    "maximum_actual_margin_trace_error_rad": shadow_error,
                    "no_guard_minimum_margin_rad": baselines["no_guard"][
                        "minimum_margin_rad"
                    ],
                    "shadow_only_minimum_margin_rad": baselines["shadow_only"][
                        "minimum_margin_rad"
                    ],
                }
            )
    v15_rows.sort(
        key=lambda row: row["maximum_actual_margin_trace_error_rad"] or -1,
        reverse=True,
    )
    shadow_rows.sort(
        key=lambda row: row["maximum_actual_margin_trace_error_rad"],
        reverse=True,
    )
    return {
        "v15_2_v15_3_nonzero_trace_lane_count": len(v15_rows),
        "v15_2_v15_3_scalar_mismatch_lane_count": sum(
            bool(row["scalar_mismatches"]) for row in v15_rows
        ),
        "v15_2_v15_3_worst_lanes": v15_rows[:limit],
        "no_guard_shadow_nonzero_trace_lane_count": len(shadow_rows),
        "no_guard_shadow_worst_lanes": shadow_rows[:limit],
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(protocol, protocol_path=runner.DEFAULT_PROTOCOL)
    if evidence["qualification_pass"] is not False:
        raise V15ComponentAblationTerminalError(
            "component-ablation terminalizer expected the observed nonpass"
        )
    analysis = evidence["analysis"]
    aggregate = analysis["aggregate"]
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    failed = sorted(
        name for name, passed in evidence["gate_results"].items() if not passed
    )
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.BASELINES
    }
    deadlock_sequence = [
        {
            "baseline": baseline,
            "deadlock_lane_count": int(baselines[baseline]["deadlock_lane_count"]),
            "executed_step_availability": baselines[baseline][
                "executed_step_availability"
            ],
        }
        for baseline in (
            "v14_predictive_brake",
            runner.FLOOR_BASELINE,
            runner.CURRENT_BASELINE,
            runner.PRIORITY_BASELINE,
            runner.V15_3_BASELINE,
        )
    ]
    identity_worst = _identity_worst_cases(evidence["lanes"])
    identity = analysis["v15_2_v15_3_execution_identity"]
    force = analysis["force_comparison"]
    latency = analysis["v15_3_latency_budget"]
    all_recovery_contained = all(
        baselines[baseline]["crossing_count"] == 0
        and baselines[baseline]["below_floor_count"] == 0
        for baseline in runner.RECOVERY_BASELINES
    )
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15-recovery-component-"
            "ablation-qualification-terminal.v1"
        ),
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": False,
        "registered_result_unchanged": True,
        "registered_data_complete": True,
        "registered_gate_results": dict(sorted(evidence["gate_results"].items())),
        "failed_registered_gates": failed,
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
            "stress_lane_count": protocol["gates"]["expected_stress_lane_count"],
            "baseline_count": len(runner.BASELINES),
            "baseline_lane_count": protocol["gates"]["expected_baseline_lane_count"],
            "all_prior_exact_pairs_excluded": True,
            "paired_same_injected_state_design": True,
            "task_outcomes_read": False,
        },
        "baselines": baselines,
        "components": analysis["components"],
        "deadlock_ablation_sequence": deadlock_sequence,
        "descriptive_incremental_deadlock_changes": {
            "floor_minus_v14": (
                int(baselines[runner.FLOOR_BASELINE]["deadlock_lane_count"])
                - int(baselines["v14_predictive_brake"]["deadlock_lane_count"])
            ),
            "current_minus_floor": (
                int(baselines[runner.CURRENT_BASELINE]["deadlock_lane_count"])
                - int(baselines[runner.FLOOR_BASELINE]["deadlock_lane_count"])
            ),
            "priority_minus_current": (
                int(baselines[runner.PRIORITY_BASELINE]["deadlock_lane_count"])
                - int(baselines[runner.CURRENT_BASELINE]["deadlock_lane_count"])
            ),
            "v15_3_minus_priority": (
                int(baselines[runner.V15_3_BASELINE]["deadlock_lane_count"])
                - int(baselines[runner.PRIORITY_BASELINE]["deadlock_lane_count"])
            ),
            "registered_as_strict_paired_component_claim": False,
        },
        "execution_identity": {
            "no_guard_shadow_maximum_actual_margin_trace_error_rad": aggregate[
                "no_guard_shadow_maximum_side_error_rad"
            ],
            "v15_2_v15_3": identity,
            **identity_worst,
        },
        "force_comparison": force,
        "latency": {
            "v15_3_screen_latency_seconds_p50": baselines[runner.V15_3_BASELINE][
                "screen_latency_seconds_p50"
            ],
            "v15_3_screen_latency_seconds_p95": baselines[runner.V15_3_BASELINE][
                "screen_latency_seconds_p95"
            ],
            "v15_3_screen_latency_seconds_p99": baselines[runner.V15_3_BASELINE][
                "screen_latency_seconds_p99"
            ],
            "v15_3_screen_latency_seconds_max": baselines[runner.V15_3_BASELINE][
                "screen_latency_seconds_max"
            ],
            "deadline_seconds": latency["deadline_seconds"],
            "deadline_miss_count": latency["miss_count"],
            "deadline_sample_count": latency["sample_count"],
            "deadline_miss_rate": latency["miss_rate"],
            "registered_miss_rate_max": protocol["gates"][
                "screen_latency_100ms_miss_rate_max"
            ],
        },
        "completed_axes": {
            "all_recovery_variants_crossing_and_floor_containment": (
                all_recovery_contained
            ),
            "floor_recovery_reduces_observed_deadlock_lanes": evidence["gate_results"][
                "floor_recovery_reduces_deadlock_lanes"
            ],
            "current_edge_not_above_floor_deadlocks": evidence["gate_results"][
                "current_edge_deadlock_not_above_floor"
            ],
            "priority_zero_residual_deadlock": evidence["gate_results"][
                "priority_zero_residual_deadlock"
            ],
            "force_envelopes": all(
                evidence["gate_results"][name]
                for name in (
                    "v15_3_attributable_force_envelope",
                    "v15_3_relative_attributable_force_envelope",
                    "v15_3_post_step_absolute_force_envelope",
                    "v15_3_post_step_increment_envelope",
                    "v15_3_recovery_attributable_force_envelope",
                    "v15_3_recovery_post_step_increment_envelope",
                )
            ),
            "strict_same_environment_trace_identity": False,
            "registered_latency_miss_rate": False,
            "all_registered_gates": False,
        },
        "nonpass_axes": {
            "no_guard_shadow_trace_identity": {
                "observed_maximum_error_rad": aggregate[
                    "no_guard_shadow_maximum_side_error_rad"
                ],
                "threshold_rad": protocol["gates"][
                    "shadow_trace_maximum_side_error_rad"
                ],
            },
            "v15_2_v15_3_execution_identity": identity,
            "v15_3_100ms_deadline_miss_rate": {
                "observed": latency["miss_rate"],
                "threshold": protocol["gates"]["screen_latency_100ms_miss_rate_max"],
            },
        },
        "claim_boundary": protocol["claim_boundary"],
        "explicit_nonclaims": {
            "strict_paired_component_ablation_qualification_pass": False,
            "exact_same_environment_shadow_trace_identity": False,
            "force_attribution_trace_noninterference": False,
            "registered_latency_budget_pass": False,
            "task_utility": False,
            "attacked_efficacy": False,
            "physics_domain_robustness": False,
            "model_mismatch_robustness": False,
            "hard_real_time": False,
            "hardware_behavior": False,
            "physical_safety": False,
            "threshold_relaxation": False,
        },
        "next_stage_decision": {
            "paired_component_ablation_claim_authorized": False,
            "preserve_nonpass_without_rerun_or_threshold_relaxation": True,
            "retain_descriptive_incremental_deadlock_table": True,
            "develop_force_bounded_successor_on_disclosed_physics_lanes": True,
            "diagnose_same_environment_restore_nondeterminism": True,
            "do_not_require_trace_identity_for_force_audit_semantic_claim": True,
            "new_successor_must_use_new_held_out_requalification_population": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15ComponentAblationTerminalError(
            "component-ablation terminal summary already exists"
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
