#!/usr/bin/env python3
"""Freeze v15.1 current-edge development without revising its non-pass."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import subprocess
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
from scripts import freeze_v15_floor_guard_recovery_development_terminal as floor_terminal  # noqa: E402
from scripts import run_v15_current_edge_recovery_development as runner  # noqa: E402


FLOOR_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_protocol.json"
)
FLOOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_20260731_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "recovery_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_recovery_development_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-recovery-"
    "development-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_current_edge_recovery_"
    "development_integrity_nonpass"
)
EXPECTED_FAILED_GATES = (
    "v15_recovery_prevention_identity",
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_task_success_noninferiority",
)
L2_ARMS = {"execution_only", "dual"}


class V15CurrentEdgeTerminalError(RuntimeError):
    """Raised when retained v15.1 evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15CurrentEdgeTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _scan(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    rows = {}
    residual = []
    total_floor = 0
    total_edge = 0
    total_selected = 0
    total_prevented = 0
    minimum = math.inf
    floor_violations = 0
    exact_mismatches = 0

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        if arm not in L2_ARMS:
            continue
        path = REPO_ROOT / str(artifact["path"])
        if file_sha256(path) != artifact["sha256"]:
            raise V15CurrentEdgeTerminalError(
                f"v15.1 episode hash differs: {episode_id}"
            )
        episode = load_json_object(path)
        audits = [
            row["predictive_virtual_brake"]
            for row in episode["trace"]
            if row.get("phase") == "policy"
        ]
        floor_count = sum(
            int(audit.get("floor_guard_recovery_selected") is True)
            for audit in audits
        )
        edge_count = sum(
            int(audit.get("current_edge_recovery_selected") is True)
            for audit in audits
        )
        selected_count = sum(
            int(
                audit.get("floor_or_current_edge_recovery_selected")
                is True
            )
            for audit in audits
        )
        prevented_count = sum(
            int(
                audit.get(
                    "floor_or_current_edge_recovery_prevented_deadlock"
                )
                is True
            )
            for audit in audits
        )
        for audit in audits:
            if (
                audit.get("floor_or_current_edge_recovery_selected")
                is True
            ):
                observed = float(audit["actual_worst_margin_rad"])
                minimum = min(minimum, observed)
                floor_violations += int(observed < 0.15)
                exact_mismatches += int(
                    audit.get("exact_action_identity") is not True
                )
            if audit.get("deadlock") is True:
                residual.append(
                    {
                        "base_pair_id": str(spec["base_pair_id"]),
                        "arm": arm,
                        "runner_step_id": int(audit["runner_step_id"]),
                        "current_minimum_margin_rad": float(
                            audit["current_target_margin_rad"]
                        ),
                        "unguarded_predicted_minimum_margin_rad": float(
                            audit[
                                "unguarded_predicted_minimum_margin_rad"
                            ]
                        ),
                        "current_edge_margin_rad": audit[
                            "current_edge_recovery_configured_margin_rad"
                        ],
                        "current_edge_eligible": audit[
                            "current_edge_recovery_eligible"
                        ],
                    }
                )
        total_floor += floor_count
        total_edge += edge_count
        total_selected += selected_count
        total_prevented += prevented_count
        rows[(str(spec["base_pair_id"]), arm)] = {
            "decision": str(episode["decision"]),
            "task_success": bool(episode["task_success"]),
            "policy_step_count": len(audits),
            "deadlock_count": sum(
                int(audit["deadlock"]) for audit in audits
            ),
            "floor_selected_count": floor_count,
            "current_edge_selected_count": edge_count,
        }
    return {
        "rows": rows,
        "floor_selected_count": total_floor,
        "current_edge_selected_count": total_edge,
        "total_recovery_selected_count": total_selected,
        "total_recovery_prevented_deadlock_count": total_prevented,
        "selected_minimum_actual_margin_rad": minimum,
        "selected_floor_violation_count": floor_violations,
        "selected_exact_action_mismatch_count": exact_mismatches,
        "residual_deadlocks": sorted(
            residual, key=lambda row: (row["base_pair_id"], row["arm"])
        ),
    }


def _comparison(
    current: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    floor_protocol = load_json_object(FLOOR_PROTOCOL_PATH)
    floor_evidence = load_json_object(FLOOR_ROOT / "pilot_evidence.json")
    previous = floor_terminal._episode_rows(
        floor_protocol, floor_evidence
    )
    selected = {key[0] for key in current}
    original = floor_terminal._v14_comparator_rows(selected)
    if set(current) != set(previous) or set(current) != set(original):
        raise V15CurrentEdgeTerminalError(
            "v14/v15/v15.1 comparison population differs"
        )

    def summary(
        rows: Mapping[tuple[str, str], Mapping[str, Any]],
    ) -> dict[str, int]:
        return {
            "deadlock_episode_count": sum(
                int(row["deadlock_count"] > 0) for row in rows.values()
            ),
            "task_success_count": sum(
                int(row["task_success"]) for row in rows.values()
            ),
        }

    changes = []
    for key in sorted(current):
        before = previous[key]
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
                    "floor_decision": before["decision"],
                    "current_edge_decision": after["decision"],
                    "floor_task_success": before["task_success"],
                    "current_edge_task_success": after["task_success"],
                    "floor_policy_step_count": before[
                        "policy_step_count"
                    ],
                    "current_edge_policy_step_count": after[
                        "policy_step_count"
                    ],
                }
            )
    return {
        "paired_l2_episode_count": len(current),
        "v14": summary(original),
        "floor_edge": summary(previous),
        "current_edge": summary(current),
        "floor_to_current_edge_changes": changes,
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
        or evidence.get("development_data_complete") is not False
        or evidence.get("pilot_complete") is not False
        or len(evidence.get("episodes", ())) != 28
        or manifest.get("status") != "complete"
        or len(manifest.get("completed_episode_ids", ())) != 28
        or manifest.get("error") is not None
        or len(entries) != 31
    ):
        raise V15CurrentEdgeTerminalError(
            "v15.1 terminal population differs"
        )
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15CurrentEdgeTerminalError(
                f"v15.1 checksum differs: {relative}"
            )
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed != list(EXPECTED_FAILED_GATES):
        raise V15CurrentEdgeTerminalError(
            "v15.1 failed-gate set differs"
        )
    scan = _scan(protocol, evidence)
    comparison = _comparison(scan["rows"])
    compatible_data_gates = {
        name: passed
        for name, passed in evidence["gate_results"].items()
        if name
        not in {
            *runner._UTILITY_GATES,
            "v15_recovery_prevention_identity",
        }
    }
    aggregate = evidence["aggregate"]
    if (
        not compatible_data_gates
        or not all(
            passed is True for passed in compatible_data_gates.values()
        )
        or scan["total_recovery_selected_count"] != 118
        or scan["current_edge_selected_count"] != 61
        or len(scan["residual_deadlocks"]) != 6
        or scan["selected_floor_violation_count"] != 0
        or scan["selected_exact_action_mismatch_count"] != 0
        or comparison["current_edge"]
        != {"deadlock_episode_count": 6, "task_success_count": 5}
    ):
        raise V15CurrentEdgeTerminalError(
            "v15.1 independent diagnostic differs"
        )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_development_data_complete": evidence[
            "development_data_complete"
        ],
        "registered_failed_gates": failed,
        "registered_result_unchanged": True,
        "diagnostic_classification": (
            "v15_1_current_edge_registered_inherited_identity_nonpass_"
            "compatible_data_axes_complete_utility_nonpass"
        ),
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
            "floor_selected_count": scan["floor_selected_count"],
            "current_edge_selected_count": scan[
                "current_edge_selected_count"
            ],
            "total_recovery_selected_count": scan[
                "total_recovery_selected_count"
            ],
            "total_recovery_prevented_deadlock_count": scan[
                "total_recovery_prevented_deadlock_count"
            ],
            "residual_deadlock_count": len(
                scan["residual_deadlocks"]
            ),
            "selected_minimum_actual_margin_rad": scan[
                "selected_minimum_actual_margin_rad"
            ],
            "selected_floor_violation_count": scan[
                "selected_floor_violation_count"
            ],
            "maximum_prediction_execution_side_error_rad": aggregate[
                "v14_maximum_prediction_execution_side_error_rad"
            ],
            "maximum_abs_constraint_force": aggregate[
                "maximum_abs_target_constraint_force"
            ],
            "screen_latency_seconds_max": aggregate[
                "screen_latency_seconds_max"
            ],
        },
        "same_seed_comparison": comparison,
        "residual_deadlocks": scan["residual_deadlocks"],
        "registered_gate_diagnostic": {
            "failed_gate": "v15_recovery_prevention_identity",
            "cause": (
                "the inherited floor-only identity compares its floor-only "
                "prevented flag against the successor's corrected v14 "
                "baseline deadlock field when current-edge is selected"
            ),
            "successor_native_prevention_identity_passed": evidence[
                "gate_results"
            ]["v15_1_recovery_prevention_identity"],
            "compatible_nonutility_data_gates_complete": True,
            "does_not_revise_registered_nonpass": True,
        },
        "runtime_observation_disclosure": {
            "console_joint_limit_warnings_observed": True,
            "console_contact_capacity_warnings_observed": True,
            "warning_counts_bound_to_retained_artifact": False,
        },
        "interpretation": {
            "same_seed_deadlock_reduction_vs_v14": 4,
            "same_seed_task_success_gain_vs_v14": 2,
            "repeated_floor_clamping_observed": True,
            "recovery_development_success": False,
            "next_factor": (
                "evaluate current-edge before floor-edge so the fallback "
                "preserves margin buffer rather than first draining it to "
                "the numerical floor"
            ),
        },
        "claim_boundary": (
            "The registered v15.1 development remains an integrity non-pass "
            "because one inherited floor-only identity gate is incompatible "
            "with current-edge selections. Independent checksum-bound "
            "diagnostics show deadlock episodes fell from ten to six and L2 "
            "task successes rose from three to five, while all recovery "
            "selected steps remained at or above the simulator floor. The "
            "two task-success non-inferiority gates still fail. This cannot "
            "qualify task utility, attacked efficacy, deployment, hardware "
            "behavior, actuator authority, or physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V15CurrentEdgeTerminalError(
            "tracked worktree must be clean before v15.1 terminal freeze"
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
            raise V15CurrentEdgeTerminalError(
                f"v15.1 terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
