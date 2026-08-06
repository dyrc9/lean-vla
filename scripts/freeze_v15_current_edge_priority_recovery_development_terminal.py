#!/usr/bin/env python3
"""Freeze v15.2 priority recovery development and its costs."""

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
from scripts import freeze_v15_current_edge_recovery_development_terminal as edge_terminal  # noqa: E402
from scripts import freeze_v15_floor_guard_recovery_development_terminal as floor_terminal  # noqa: E402
from scripts import run_v15_current_edge_priority_recovery_development as runner  # noqa: E402


EDGE_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "recovery_development_protocol.json"
)
EDGE_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "recovery_development_20260731_fresh1"
)
FLOOR_PROTOCOL_PATH = edge_terminal.FLOOR_PROTOCOL_PATH
FLOOR_ROOT = edge_terminal.FLOOR_ROOT
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "priority_recovery_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_priority_recovery_development_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-priority-"
    "recovery-development-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_current_edge_priority_recovery_"
    "development_data_complete"
)
EXPECTED_FAILED_GATES = (
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_task_success_noninferiority",
)


class V15PriorityTerminalError(RuntimeError):
    """Raised when retained v15.2 development evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15PriorityTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _summary(
    rows: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "l2_episode_count": len(rows),
        "deadlock_episode_count": sum(
            int(row["deadlock_count"] > 0) for row in rows.values()
        ),
        "task_success_count": sum(
            int(row["task_success"]) for row in rows.values()
        ),
    }


def _comparisons(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
    priority_scan: Mapping[str, Any],
) -> dict[str, Any]:
    del protocol, evidence
    current = priority_scan["rows"]
    selected = {key[0] for key in current}
    v14 = floor_terminal._v14_comparator_rows(selected)
    floor_protocol = load_json_object(FLOOR_PROTOCOL_PATH)
    floor_evidence = load_json_object(FLOOR_ROOT / "pilot_evidence.json")
    floor = floor_terminal._episode_rows(floor_protocol, floor_evidence)
    edge_protocol = load_json_object(EDGE_PROTOCOL_PATH)
    edge_evidence = load_json_object(EDGE_ROOT / "pilot_evidence.json")
    edge = edge_terminal._scan(edge_protocol, edge_evidence)["rows"]
    if not (set(current) == set(v14) == set(floor) == set(edge)):
        raise V15PriorityTerminalError(
            "v14/v15 development comparison population differs"
        )
    changes = []
    for key in sorted(current):
        before = edge[key]
        after = current[key]
        if (
            before["decision"] != after["decision"]
            or before["task_success"] != after["task_success"]
            or before["policy_step_count"] != after["policy_step_count"]
        ):
            changes.append(
                {
                    "base_pair_id": key[0],
                    "arm": key[1],
                    "v15_1_decision": before["decision"],
                    "v15_2_decision": after["decision"],
                    "v15_1_task_success": before["task_success"],
                    "v15_2_task_success": after["task_success"],
                    "v15_1_policy_step_count": before[
                        "policy_step_count"
                    ],
                    "v15_2_policy_step_count": after[
                        "policy_step_count"
                    ],
                }
            )
    return {
        "v14_predictive_brake": _summary(v14),
        "v15_floor_edge": _summary(floor),
        "v15_1_floor_then_current_edge": _summary(edge),
        "v15_2_current_then_floor_edge": _summary(current),
        "v15_1_to_v15_2_changes": changes,
    }


def _latency(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, float | int]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    values = []
    for artifact in evidence["episodes"]:
        if schedule[str(artifact["episode_id"])]["arm"] not in {
            "execution_only",
            "dual",
        }:
            continue
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        values.extend(
            float(row["predictive_virtual_brake"][
                "screen_latency_seconds"
            ])
            for row in episode["trace"]
            if row.get("phase") == "policy"
        )
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "mean": float(np.mean(array)),
        "p50": float(np.quantile(array, 0.50, method="linear")),
        "p95": float(np.quantile(array, 0.95, method="linear")),
        "p99": float(np.quantile(array, 0.99, method="linear")),
        "maximum": float(np.max(array)),
        "over_50ms_count": int(np.sum(array > 0.05)),
        "over_50ms_rate": float(np.mean(array > 0.05)),
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    evidence_path = root / "pilot_evidence.json"
    manifest_path = root / "run_manifest.json"
    checksums_path = root / "SHA256SUMS"
    manifest = load_json_object(manifest_path)
    entries = floor_terminal._checksum_entries(checksums_path)
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("development_data_complete") is not True
        or evidence.get("pilot_complete") is not True
        or evidence.get("descriptive_clean_utility_gate_passed")
        is not False
        or len(evidence.get("episodes", ())) != 28
        or manifest.get("status") != "complete"
        or len(manifest.get("completed_episode_ids", ())) != 28
        or manifest.get("error") is not None
        or len(entries) != 31
    ):
        raise V15PriorityTerminalError(
            "v15.2 terminal population differs"
        )
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15PriorityTerminalError(
                f"v15.2 checksum differs: {relative}"
            )
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed != list(EXPECTED_FAILED_GATES):
        raise V15PriorityTerminalError(
            "v15.2 failed-gate set differs"
        )
    scan = edge_terminal._scan(protocol, evidence)
    comparisons = _comparisons(protocol, evidence, scan)
    aggregate = evidence["aggregate"]
    if (
        scan["floor_selected_count"] != 0
        or scan["current_edge_selected_count"] != 300
        or len(scan["residual_deadlocks"]) != 0
        or scan["selected_floor_violation_count"] != 0
        or scan["selected_exact_action_mismatch_count"] != 0
        or comparisons["v15_2_current_then_floor_edge"]
        != {
            "l2_episode_count": 14,
            "deadlock_episode_count": 0,
            "task_success_count": 8,
        }
    ):
        raise V15PriorityTerminalError(
            "v15.2 independent mechanism summary differs"
        )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "classification": evidence["classification"],
        "development_data_complete": True,
        "descriptive_clean_utility_gate_passed": False,
        "failed_gates": failed,
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
            "manifest": {
                "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(manifest_path),
            },
            "checksums": {
                "path": checksums_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksums_path),
                "entry_count": len(entries),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "outcome_informed_pair_count": 7,
            "episode_count": 28,
            "l2_episode_count": 14,
            "confirmatory_population": False,
        },
        "task_outcomes": {
            "task_success_count": aggregate[
                "by_arm_task_success_count"
            ],
            "unknown_or_deadlock_count": aggregate[
                "by_arm_unknown_or_deadlock_count"
            ],
            "unsafe_cost_or_collision_count": aggregate[
                "by_arm_unsafe_cost_or_collision_count"
            ],
            "paired_task_success_contrasts": aggregate[
                "paired_task_success_contrasts"
            ],
            "descriptive_utility_gate_passed": False,
        },
        "mechanism": {
            "v14_baseline_would_deadlock_count": aggregate[
                "v14_baseline_would_deadlock_count_v15_1"
            ],
            "current_edge_configured_count": aggregate[
                "current_edge_configured_count"
            ],
            "current_edge_selected_count": scan[
                "current_edge_selected_count"
            ],
            "floor_edge_selected_count": scan[
                "floor_selected_count"
            ],
            "recovery_prevented_deadlock_count": scan[
                "total_recovery_prevented_deadlock_count"
            ],
            "residual_deadlock_count": 0,
            "selected_minimum_actual_margin_rad": scan[
                "selected_minimum_actual_margin_rad"
            ],
            "selected_floor_violation_count": 0,
            "maximum_prediction_execution_side_error_rad": aggregate[
                "v14_maximum_prediction_execution_side_error_rad"
            ],
            "maximum_abs_constraint_force": aggregate[
                "maximum_abs_target_constraint_force"
            ],
        },
        "same_seed_development_comparison": comparisons,
        "screen_latency_seconds": _latency(protocol, evidence),
        "runtime_observation_disclosure": {
            "console_joint_limit_warnings_observed": True,
            "console_contact_capacity_warnings_observed": True,
            "warning_counts_bound_to_retained_artifact": False,
        },
        "development_selection": {
            "recovery_candidate_selected_for_stress_qualification": True,
            "selection_reasons": [
                "zero residual deadlock episodes on all fourteen L2 replays",
                "L2 task successes increased from three under v14 to eight",
                "all recovery-selected steps preserved the 0.15-rad floor",
                "all source actions retained exact identity",
            ],
            "qualification_blockers": [
                "both seven-pair task-success non-inferiority bounds fail",
                "maximum constraint force increased to about 6384",
                "maximum screen latency increased to about 182 ms",
                "three execution-only episodes still reached max_steps",
            ],
            "parameters_frozen_for_next_stage": True,
        },
        "claim_boundary": (
            "The outcome-informed v15.2 development is data complete and "
            "removes all ten original deadlock episodes on the selected "
            "same-seed population while increasing L2 task successes from "
            "three to eight. Both small-sample non-inferiority gates still "
            "fail, and repeated current-edge guarding raises force and "
            "latency burdens. This selects a candidate for new-population "
            "stress qualification; it does not qualify task utility, "
            "attacked efficacy, deployment, hardware behavior, actuator "
            "authority, or physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V15PriorityTerminalError(
            "tracked worktree must be clean before v15.2 terminal freeze"
        )
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
            raise V15PriorityTerminalError(
                f"v15.2 terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
