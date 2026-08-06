#!/usr/bin/env python3
"""Freeze the registered v15.3 recovery stress qualification pass."""

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
from scripts import run_v15_force_attributed_recovery_stress_qualification as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_stress_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attributed_recovery_stress_qualification_terminal.py"
)
CREATED_AT = "2026-07-31T23:35:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-stress-qualification-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_3_force_attributed_"
    "recovery_stress_qualification_pass"
)


class V15ForceAttributedRecoveryQualificationTerminalError(RuntimeError):
    """Raised when registered v15.3 qualification evidence differs."""


def _baseline_summary(
    aggregate: Mapping[str, Any],
    baseline: str,
) -> dict[str, Any]:
    fields = (
        "lane_count",
        "trigger_count",
        "intervention_count",
        "deadlock_count",
        "deadlock_lane_count",
        "below_floor_count",
        "crossing_count",
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


def _force_rows(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for lane in evidence["lanes"]:
        report = lane["baselines"][runner.V15_BASELINE]
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
                    "runner_step_id": int(step["runner_step_id"]),
                    "intervened": bool(step["intervened"]),
                    "recovery_selected": bool(
                        step["recovery_selected"]
                    ),
                    "pre_step_maximum_abs_risk_constraint_force": float(
                        step[
                            "pre_step_maximum_abs_risk_constraint_force"
                        ]
                    ),
                    "guard_scope_reported_maximum_abs_risk_constraint_force": float(
                        step[
                            "guard_scope_reported_maximum_abs_risk_constraint_force"
                        ]
                    ),
                    "guard_scope_maximum_positive_joint_increment_over_pre_step": float(
                        step[
                            "guard_scope_maximum_positive_joint_increment_over_pre_step"
                        ]
                    ),
                    "post_step_maximum_abs_risk_constraint_force": float(
                        step["post_step_maximum_abs_risk_constraint_force"]
                    ),
                    "post_step_maximum_positive_joint_increment_over_pre_step": float(
                        step[
                            "post_step_maximum_positive_joint_increment_over_pre_step"
                        ]
                    ),
                }
            )
    return rows


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    analysis = evidence["analysis"]
    aggregate = analysis["aggregate"]
    recovery = analysis["recovery"]
    force = analysis["force_comparison"]
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("qualification_pass") is not True
        or evidence.get("held_out_mechanism_claim_authorized") is not True
        or evidence.get("task_utility_claim_authorized") is not False
        or evidence.get(
            "same_environment_shadow_trace_identity_claim_authorized"
        )
        is not False
        or len(evidence.get("lanes", ())) != 756
        or failed
        or recovery["v14_predictive_deadlock_lane_count"] != 364
        or recovery["v15_3_residual_deadlock_lane_count"] != 0
        or recovery["recovery_prevented_deadlock_count"] != 1202
        or aggregate[f"{runner.V15_BASELINE}_crossing_count"] != 0
        or aggregate[f"{runner.V15_BASELINE}_below_floor_count"] != 0
        or force[
            "v15_3_maximum_recovery_attributable_joint_force_increment"
        ]
        > 1250.0
        or force[
            "v15_3_maximum_recovery_post_step_positive_joint_increment"
        ]
        > 1250.0
    ):
        raise V15ForceAttributedRecoveryQualificationTerminalError(
            "v15.3 registered qualification result differs"
        )
    rows = _force_rows(evidence)
    interventions = [row for row in rows if row["intervened"]]
    recovery_rows = [row for row in rows if row["recovery_selected"]]
    legacy_field = (
        "guard_scope_reported_maximum_abs_risk_constraint_force"
    )
    increment_field = (
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    )
    post_increment_field = (
        "post_step_maximum_positive_joint_increment_over_pre_step"
    )
    legacy_max = max(interventions, key=lambda row: row[legacy_field])
    attributable_max = max(
        interventions, key=lambda row: row[increment_field]
    )
    recovery_attributable_max = max(
        recovery_rows, key=lambda row: row[increment_field]
    )
    recovery_post_max = max(
        recovery_rows, key=lambda row: row[post_increment_field]
    )
    if (
        legacy_max[legacy_field] <= 10000.0
        or legacy_max[increment_field] != 0.0
        or legacy_max[
            "pre_step_maximum_abs_risk_constraint_force"
        ]
        <= legacy_max[legacy_field]
    ):
        raise V15ForceAttributedRecoveryQualificationTerminalError(
            "v15.3 legacy force attribution differs"
        )
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.BASELINES
    }
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": True,
        "registered_result_unchanged": True,
        "failed_gates": failed,
        "registered_gate_results": evidence["gate_results"],
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
                int(aggregate[f"{baseline}_lane_count"])
                for baseline in runner.BASELINES
            ),
            "prior_exact_pair_count_excluded": protocol["selection"][
                "prior_exact_pair_count"
            ],
            "environment_seed": protocol["selection"][
                "environment_seed"
            ],
            "held_out_exact_task_init_population": True,
            "task_outcomes_read": False,
        },
        "baselines": baselines,
        "recovery": recovery,
        "force_attribution": analysis["force_attribution"],
        "force_comparison": force,
        "force_worst_cases": {
            "legacy_total_maximum": legacy_max,
            "attributable_increment_maximum": attributable_max,
            "recovery_attributable_increment_maximum": (
                recovery_attributable_max
            ),
            "recovery_post_step_increment_maximum": recovery_post_max,
        },
        "latency": {
            "aggregate_p95_seconds": aggregate[
                f"{runner.V15_BASELINE}_screen_latency_seconds_p95"
            ],
            "aggregate_max_seconds": aggregate[
                f"{runner.V15_BASELINE}_screen_latency_seconds_max"
            ],
            "registered_100ms_budget": analysis[
                "v15_3_latency_budget"
            ],
            "real_time_claim": False,
        },
        "contact_capacity": analysis["contact_capacity"],
        "qualified_claims": {
            "held_out_simulator_joint_limit_proxy_containment": True,
            "held_out_v14_deadlock_recovery": True,
            "held_out_executed_step_availability": True,
            "held_out_attributable_constraint_force_envelope": True,
            "held_out_research_simulator_100ms_latency_envelope": True,
        },
        "explicit_nonclaims": {
            "fresh2_nonpass_superseded": False,
            "exact_same_environment_shadow_trace_identity": False,
            "task_utility": False,
            "attacked_efficacy": False,
            "real_time_deployment": False,
            "hardware_behavior": False,
            "actuator_authority": False,
            "physical_safety": False,
        },
        "next_stage_decision": {
            "held_out_recovery_stress_qualification_complete": True,
            "freeze_new_held_out_task_utility_protocol": True,
            "task_utility_claim_authorized_now": False,
            "modify_v15_3_mechanism_before_task_utility": False,
        },
        "claim_boundary": protocol["claim_boundary"],
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
            raise V15ForceAttributedRecoveryQualificationTerminalError(
                f"v15.3 qualification terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
