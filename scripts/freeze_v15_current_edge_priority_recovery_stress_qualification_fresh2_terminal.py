#!/usr/bin/env python3
"""Freeze the registered v15.2 recovery stress qualification nonpass."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
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
from scripts import run_v15_current_edge_priority_recovery_stress_qualification_fresh2 as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_priority_recovery_stress_qualification_fresh2_terminal.py"
)
CREATED_AT = "2026-07-31T21:30:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-qualification-fresh2-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_2_recovery_stress_qualification_nonpass"
)
EXPECTED_FAILED_GATES = (
    "threshold_classification_identity",
    "v15_2_absolute_force_envelope",
    "v15_2_relative_force_envelope",
)


class V15RecoveryStressQualificationFresh2TerminalError(RuntimeError):
    """Raised when retained fresh2 evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryStressQualificationFresh2TerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _baseline_summary(
    aggregate: Mapping[str, Any],
    baseline: str,
) -> dict[str, Any]:
    fields = (
        "lane_count",
        "trigger_count",
        "trigger_lane_count",
        "trigger_lane_rate",
        "intervention_count",
        "intervention_lane_count",
        "intervention_lane_rate",
        "deadlock_count",
        "deadlock_lane_count",
        "deadlock_lane_rate",
        "below_floor_count",
        "below_floor_side_rate",
        "crossing_count",
        "crossing_side_rate",
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


def _threshold_disagreements(
    lanes: list[Mapping[str, Any]],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    disagreements = []
    for lane in lanes:
        no_guard = lane["baselines"]["no_guard"][
            "actual_joint_side_margins"
        ]
        shadow = lane["baselines"]["shadow_only"][
            "actual_joint_side_margins"
        ]
        for step_index, (no_rows, shadow_rows) in enumerate(
            zip(no_guard, shadow, strict=True)
        ):
            no_matrix = (
                runner.predecessor.calibration.v14.pilot.
                full_clean_margin_matrix(no_rows)
            )
            shadow_matrix = (
                runner.predecessor.calibration.v14.pilot.
                full_clean_margin_matrix(shadow_rows)
            )
            for joint_index, side_index in np.argwhere(
                (no_matrix < threshold) != (shadow_matrix < threshold)
            ):
                disagreements.append(
                    {
                        "environment_id": str(lane["environment_id"]),
                        "suite": str(lane["suite"]),
                        "task_id": int(lane["task_id"]),
                        "init_state_id": int(lane["init_state_id"]),
                        "lane_id": str(lane["lane_id"]),
                        "dose": str(lane["dose"]["dose"]),
                        "target_joint_index": int(lane["joint_index"]),
                        "target_side": str(lane["side"]),
                        "step_index": step_index,
                        "disagreement_joint_index": int(joint_index),
                        "disagreement_side": (
                            "lower" if side_index == 0 else "upper"
                        ),
                        "threshold_rad": threshold,
                        "no_guard_margin_rad": float(
                            no_matrix[joint_index, side_index]
                        ),
                        "shadow_only_margin_rad": float(
                            shadow_matrix[joint_index, side_index]
                        ),
                        "absolute_error_rad": float(
                            abs(
                                no_matrix[joint_index, side_index]
                                - shadow_matrix[joint_index, side_index]
                            )
                        ),
                    }
                )
    return disagreements


def _force_diagnostic(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = []
    for lane in lanes:
        v14_force = float(
            lane["baselines"]["v14_predictive_brake"][
                "maximum_abs_constraint_force"
            ]
        )
        v15_force = float(
            lane["baselines"]["v15_2_recovery"][
                "maximum_abs_constraint_force"
            ]
        )
        rows.append(
            {
                "lane_id": str(lane["lane_id"]),
                "suite": str(lane["suite"]),
                "task_id": int(lane["task_id"]),
                "init_state_id": int(lane["init_state_id"]),
                "dose": str(lane["dose"]["dose"]),
                "joint_index": int(lane["joint_index"]),
                "side": str(lane["side"]),
                "v14_maximum_abs_constraint_force": v14_force,
                "v15_2_maximum_abs_constraint_force": v15_force,
                "v15_2_minus_v14_force": v15_force - v14_force,
                "selected_recovery_count": int(
                    lane["baselines"]["v15_2_recovery"][
                        "selected_recovery_count"
                    ]
                ),
            }
        )
    forces = np.asarray(
        [row["v15_2_maximum_abs_constraint_force"] for row in rows],
        dtype=np.float64,
    )
    increases = np.asarray(
        [row["v15_2_minus_v14_force"] for row in rows],
        dtype=np.float64,
    )
    return {
        "lane_count": len(rows),
        "v15_2_force_over_10000_lane_count": int(
            np.sum(forces > 10000.0)
        ),
        "v15_2_force_quantiles": {
            "p50": float(np.quantile(forces, 0.50)),
            "p95": float(np.quantile(forces, 0.95)),
            "p99": float(np.quantile(forces, 0.99)),
            "maximum": float(np.max(forces)),
        },
        "v15_2_minus_v14_force_quantiles": {
            "p50": float(np.quantile(increases, 0.50)),
            "p95": float(np.quantile(increases, 0.95)),
            "p99": float(np.quantile(increases, 0.99)),
            "maximum": float(np.max(increases)),
        },
        "top_v15_2_force_lanes": sorted(
            rows,
            key=lambda row: row[
                "v15_2_maximum_abs_constraint_force"
            ],
            reverse=True,
        )[:10],
        "top_force_increase_lanes": sorted(
            rows,
            key=lambda row: row["v15_2_minus_v14_force"],
            reverse=True,
        )[:10],
    }


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
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("qualification_pass") is not False
        or evidence.get("fresh1_abort_acknowledged") is not True
        or evidence.get("analysis_compatibility_aliases_only") is not True
        or len(evidence.get("lanes", ())) != 756
        or failed != list(EXPECTED_FAILED_GATES)
    ):
        raise V15RecoveryStressQualificationFresh2TerminalError(
            "fresh2 terminal population or result differs"
        )
    analysis = evidence["analysis"]
    aggregate = analysis["aggregate"]
    recovery = analysis["recovery"]
    disagreements = _threshold_disagreements(
        evidence["lanes"], threshold=0.22
    )
    force = _force_diagnostic(evidence["lanes"])
    if (
        len(disagreements) != 2
        or recovery["v14_predictive_deadlock_lane_count"] != 364
        or recovery["v15_2_residual_deadlock_lane_count"] != 0
        or recovery["recovery_prevented_deadlock_count"] != 1205
        or recovery["selected_floor_violation_count"] != 0
        or force["v15_2_force_over_10000_lane_count"] != 1
    ):
        raise V15RecoveryStressQualificationFresh2TerminalError(
            "fresh2 independent diagnostics differ"
        )
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.predecessor.calibration.BASELINES
    }
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": False,
        "registered_result_unchanged": True,
        "failed_gates": failed,
        "registered_gate_results": evidence["gate_results"],
        "bindings": {
            "fresh1_abort": protocol["fresh1_abort"],
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
                aggregate[f"{baseline}_lane_count"]
                for baseline in runner.predecessor.calibration.BASELINES
            ),
            "held_out_exact_task_init_population": True,
            "task_outcomes_read": False,
        },
        "baselines": baselines,
        "recovery": recovery,
        "force_comparison": analysis["force_comparison"],
        "force_diagnostic": force,
        "threshold_identity": {
            "registered": analysis["registered_threshold_identity"],
            "disagreements_at_0_22_rad": disagreements,
        },
        "latency": {
            "registered_100ms_budget": analysis[
                "v15_2_latency_budget"
            ],
            "diagnostic_50ms_deadline": analysis[
                "fifty_ms_deadline_diagnostic"
            ],
            "v15_2_p50_seconds": aggregate[
                "v15_2_recovery_screen_latency_seconds_p50"
            ],
            "v15_2_p95_seconds": aggregate[
                "v15_2_recovery_screen_latency_seconds_p95"
            ],
            "v15_2_p99_seconds": aggregate[
                "v15_2_recovery_screen_latency_seconds_p99"
            ],
            "v15_2_maximum_seconds": aggregate[
                "v15_2_recovery_screen_latency_seconds_max"
            ],
        },
        "contact_capacity": analysis["contact_capacity"],
        "descriptive_mechanism_signal": {
            "v14_deadlock_lane_count": recovery[
                "v14_predictive_deadlock_lane_count"
            ],
            "v15_2_residual_deadlock_lane_count": recovery[
                "v15_2_residual_deadlock_lane_count"
            ],
            "recovery_prevented_deadlock_count": recovery[
                "recovery_prevented_deadlock_count"
            ],
            "v15_2_crossing_count": aggregate[
                "v15_2_recovery_crossing_count"
            ],
            "v15_2_below_floor_count": aggregate[
                "v15_2_recovery_below_floor_count"
            ],
            "v15_2_executed_step_availability": aggregate[
                "v15_2_recovery_executed_step_availability"
            ],
            "registered_as_qualification_pass": False,
        },
        "next_stage_decision": {
            "held_out_mechanism_qualification_claim_authorized": False,
            "advance_directly_to_confirmatory_task_utility": False,
            "thresholds_must_not_be_relaxed_post_result": True,
            "develop_versioned_force_bounded_successor": True,
            "diagnose_shadow_identity_on_disclosed_low_dose_lane": True,
            "force_successor_target": (
                "preserve zero crossing, zero below-floor, zero residual "
                "deadlock, and exact source actions while bringing the "
                "registered absolute and relative force envelopes below "
                "their unchanged thresholds"
            ),
        },
        "claim_boundary": (
            "Fresh2 is a registered held-out qualification nonpass. Its "
            "descriptive mechanism signal is strong, but the two force "
            "envelopes and the 0.22-rad causal-control threshold identity "
            "failed. No held-out mechanism qualification, task utility, "
            "real-time, deployment, hardware, actuator-authority, physical-"
            "safety, or confirmatory claim is authorized. Any successor is "
            "outcome-informed and requires a new population."
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
            raise V15RecoveryStressQualificationFresh2TerminalError(
                f"fresh2 terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
