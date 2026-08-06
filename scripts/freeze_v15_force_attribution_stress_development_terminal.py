#!/usr/bin/env python3
"""Freeze v15.3 force-attribution development and future gates."""

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
from scripts import run_v15_force_attribution_stress_development as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attribution_"
    "stress_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attribution_stress_development_terminal.py"
)
CREATED_AT = "2026-07-31T22:35:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attribution-"
    "stress-development-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_3_force_attribution_"
    "stress_development_data_complete"
)


class V15ForceAttributionStressDevelopmentTerminalError(RuntimeError):
    """Raised when retained v15.3 development evidence differs."""


def _step_rows(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for lane in evidence["lanes"]:
        report = lane["baselines"][runner.BASELINE]
        for step in report["force_attribution_steps"]:
            rows.append(
                {
                    "lane_id": str(lane["lane_id"]),
                    "environment_id": str(lane["environment_id"]),
                    "suite": str(lane["suite"]),
                    "task_id": int(lane["task_id"]),
                    "init_state_id": int(lane["init_state_id"]),
                    "joint_index": int(lane["joint_index"]),
                    "side": str(lane["side"]),
                    "dose": str(lane["dose"]["dose"]),
                    **dict(step),
                }
            )
    return rows


def _stats(
    rows: list[Mapping[str, Any]],
    field: str,
) -> dict[str, Any]:
    values = np.asarray(
        [float(row[field]) for row in rows], dtype=np.float64
    )
    if not values.size or not np.isfinite(values).all():
        raise V15ForceAttributionStressDevelopmentTerminalError(
            f"force development field is empty or nonfinite: {field}"
        )
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)),
        "p50": float(np.quantile(values, 0.50)),
        "p95": float(np.quantile(values, 0.95)),
        "p99": float(np.quantile(values, 0.99)),
        "maximum": float(np.max(values)),
    }


def _group_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    fields = (
        "pre_step_maximum_abs_risk_constraint_force",
        "guard_scope_reported_maximum_abs_risk_constraint_force",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
        "post_step_maximum_abs_risk_constraint_force",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    return {field: _stats(rows, field) for field in fields}


def _diagnostic_row(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "lane_id",
        "environment_id",
        "suite",
        "task_id",
        "init_state_id",
        "joint_index",
        "side",
        "dose",
        "runner_step_id",
        "recovery_selected",
        "pre_step_maximum_abs_risk_constraint_force",
        "guard_scope_reported_maximum_abs_risk_constraint_force",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
        "post_step_maximum_abs_risk_constraint_force",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    return {field: row[field] for field in fields}


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = runner._output_root(protocol)
    evidence_path = root / "development_evidence.json"
    checksums_path = root / "SHA256SUMS"
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    recovery = evidence["analysis"]["recovery"]
    force = evidence["analysis"]["force_attribution"]
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("development_data_complete") is not True
        or evidence.get("qualification_claim_authorized") is not False
        or len(evidence.get("lanes", ())) != 756
        or failed
        or recovery["v14_baseline_would_deadlock_count"] != 1206
        or recovery["recovery_prevented_deadlock_count"] != 1206
        or recovery["deadlock_count"] != 0
        or recovery["below_floor_count"] != 0
        or recovery["crossing_count"] != 0
        or force["guard_scope_legacy_force_recomputed_mismatch_count"] != 0
    ):
        raise V15ForceAttributionStressDevelopmentTerminalError(
            "v15.3 force-development result differs"
        )

    steps = _step_rows(evidence)
    interventions = [row for row in steps if row["intervened"] is True]
    recovery_steps = [
        row for row in interventions if row["recovery_selected"] is True
    ]
    standard_steps = [
        row for row in interventions if row["recovery_selected"] is False
    ]
    if (
        len(steps) != 3780
        or len(interventions) != 1609
        or len(recovery_steps) != 1206
        or len(standard_steps) != 403
    ):
        raise V15ForceAttributionStressDevelopmentTerminalError(
            "v15.3 force-development intervention partition differs"
        )
    increment_field = (
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    )
    post_increment_field = (
        "post_step_maximum_positive_joint_increment_over_pre_step"
    )
    legacy_field = (
        "guard_scope_reported_maximum_abs_risk_constraint_force"
    )
    legacy_maximum = max(interventions, key=lambda row: row[legacy_field])
    if (
        float(legacy_maximum[legacy_field]) <= 10000.0
        or float(legacy_maximum[increment_field]) != 0.0
        or float(legacy_maximum[
            "pre_step_maximum_abs_risk_constraint_force"
        ])
        <= float(legacy_maximum[legacy_field])
    ):
        raise V15ForceAttributionStressDevelopmentTerminalError(
            "legacy force-envelope attribution differs"
        )
    top_increments = sorted(
        interventions,
        key=lambda row: float(row[increment_field]),
        reverse=True,
    )[:10]
    top_post_increments = sorted(
        interventions,
        key=lambda row: float(row[post_increment_field]),
        reverse=True,
    )[:10]
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "development_data_complete": True,
        "registered_as_qualification_pass": False,
        "registered_result_unchanged": True,
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
            "environment_count": 18,
            "suite_count": 3,
            "stress_lane_count": 756,
            "step_count": len(steps),
            "intervention_step_count": len(interventions),
            "standard_guard_intervention_step_count": len(standard_steps),
            "recovery_intervention_step_count": len(recovery_steps),
            "held_out_population": False,
            "outcome_disclosed_before_protocol": True,
            "task_outcomes_read": False,
        },
        "integrity_gate_results": evidence["gate_results"],
        "recovery": recovery,
        "force_groups": {
            "all_interventions": _group_summary(interventions),
            "standard_guard_interventions": _group_summary(standard_steps),
            "recovery_interventions": _group_summary(recovery_steps),
        },
        "legacy_force_envelope_diagnostic": {
            "old_absolute_gate": 10000.0,
            "old_gate_exceeded": True,
            "maximum_legacy_total_step": _diagnostic_row(legacy_maximum),
            "interpretation": (
                "The legacy scalar includes force already present before "
                "the guarded step. At its maximum, the attributable "
                "per-joint increment is zero and the post-step force is "
                "lower than the pre-step force. The registered fresh2 "
                "nonpass remains unchanged."
            ),
        },
        "top_attributable_increment_steps": [
            _diagnostic_row(row) for row in top_increments
        ],
        "top_post_step_increment_steps": [
            _diagnostic_row(row) for row in top_post_increments
        ],
        "future_qualification_design": {
            "stage": (
                "held-out-v15.3-force-attributed-recovery-stress-"
                "qualification"
            ),
            "new_exact_task_init_population_required": True,
            "development_environment_seed_excluded": 3509,
            "qualification_environment_seed": 4509,
            "environment_count": 18,
            "environment_count_per_suite": 6,
            "stress_lane_count": 756,
            "baselines": [
                "no_guard",
                "v14_predictive_brake",
                "v15_3_force_attributed_recovery",
            ],
            "baseline_lane_count": 2268,
            "task_outcomes_read": False,
            "same_environment_shadow_trace_identity_claim": False,
            "legacy_fresh2_nonpass_superseded": False,
        },
        "frozen_future_qualification_gates": {
            "expected_environment_count": 18,
            "expected_stress_lane_count": 756,
            "expected_baseline_lane_count": 2268,
            "no_guard_crossing_count_min": 1,
            "no_guard_below_floor_count_min": 1,
            "v14_deadlock_lane_count_min": 1,
            "v15_3_residual_deadlock_lane_count_max": 0,
            "v15_3_crossing_count_max": 0,
            "v15_3_below_floor_count_max": 0,
            "v15_3_selected_floor_violation_count_max": 0,
            "v15_3_exact_action_mismatch_count_max": 0,
            "restore_failure_count_max": 0,
            "force_recomputation_mismatch_count_max": 0,
            "recovery_prevention_identity_required": True,
            "v15_3_availability_not_below_v14": True,
            "prediction_execution_error_rad_max": 0.001,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "maximum_attributable_joint_force_increment": 10000.0,
            "maximum_attributable_increment_to_v14_legacy_force_ratio": 1.25,
            "maximum_post_step_absolute_risk_force": 10000.0,
            "maximum_post_step_positive_joint_increment": 10000.0,
            "maximum_recovery_attributable_joint_force_increment": 1250.0,
            "maximum_recovery_post_step_positive_joint_increment": 1250.0,
            "screen_latency_seconds_p95_max": 0.1,
            "screen_latency_seconds_max": 0.2,
            "screen_latency_100ms_miss_rate_max": 0.025,
        },
        "next_stage_decision": {
            "force_metric_development_complete": True,
            "freeze_new_held_out_qualification_protocol": True,
            "qualification_claim_authorized_now": False,
            "advance_directly_to_task_utility": False,
        },
        "claim_boundary": (
            "This is outcome-informed metric development on disclosed "
            "fresh2 environments. It establishes an auditable force "
            "estimand and freezes gates for a new population, but does "
            "not establish qualification, task utility, exact causal "
            "shadow-trace identity, real-time use, deployment, hardware "
            "behavior, actuator authority, or physical safety."
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
            raise V15ForceAttributionStressDevelopmentTerminalError(
                f"force-development terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
