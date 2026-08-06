#!/usr/bin/env python3
"""Freeze the data-complete v15 floor-guard recovery development result."""

from __future__ import annotations

import argparse
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
from scripts import run_v15_floor_guard_recovery_development as runner  # noqa: E402


V14_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_20260731_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_floor_guard_recovery_development_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-floor-guard-recovery-"
    "development-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_floor_guard_recovery_"
    "development_data_complete"
)
EXPECTED_FAILED_GATES = (
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_task_success_noninferiority",
)
L2_ARMS = {"execution_only", "dual"}


class V15RecoveryDevelopmentTerminalError(RuntimeError):
    """Raised when retained v15 development evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryDevelopmentTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _checksum_entries(path: Path) -> dict[str, str]:
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in entries:
            raise V15RecoveryDevelopmentTerminalError(
                "duplicate v15 development checksum entry"
            )
        entries[relative] = digest
    return entries


def _episode_rows(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    rows = {}
    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        if arm not in L2_ARMS:
            continue
        path = REPO_ROOT / str(artifact["path"])
        if file_sha256(path) != artifact["sha256"]:
            raise V15RecoveryDevelopmentTerminalError(
                f"v15 episode hash differs: {episode_id}"
            )
        episode = load_json_object(path)
        audits = [
            row["predictive_virtual_brake"]
            for row in episode["trace"]
            if row.get("phase") == "policy"
        ]
        key = (str(spec["base_pair_id"]), arm)
        rows[key] = {
            "episode_id": episode_id,
            "base_pair_id": key[0],
            "arm": arm,
            "decision": str(episode["decision"]),
            "task_success": bool(episode["task_success"]),
            "unsafe_cost_or_collision": bool(
                episode["unsafe_cost_or_collision"]
            ),
            "policy_step_count": len(audits),
            "trigger_count": sum(
                int(audit["triggered"]) for audit in audits
            ),
            "intervention_count": sum(
                int(audit["intervened"]) for audit in audits
            ),
            "deadlock_count": sum(
                int(audit["deadlock"]) for audit in audits
            ),
            "recovery_selected_count": sum(
                int(
                    audit.get("floor_guard_recovery_selected") is True
                )
                for audit in audits
            ),
            "recovery_prevented_deadlock_count": sum(
                int(
                    audit.get(
                        "floor_guard_recovery_prevented_deadlock"
                    )
                    is True
                )
                for audit in audits
            ),
        }
    return rows


def _v14_comparator_rows(
    selected_pairs: set[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    evidence = load_json_object(V14_ROOT / "pilot_evidence.json")
    rows = {}
    for artifact in evidence["episodes"]:
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        metadata = episode["metadata"]
        arm = str(metadata["four_arm_label"])
        pair = (
            f"{metadata['benchmark_name']}_task{metadata['task_id']}_"
            f"init{metadata['init_state_id']}"
        )
        if arm not in L2_ARMS or pair not in selected_pairs:
            continue
        audits = [
            row["predictive_virtual_brake"]
            for row in episode["trace"]
            if row.get("phase") == "policy"
        ]
        rows[(pair, arm)] = {
            "decision": str(episode["decision"]),
            "task_success": bool(episode["task_success"]),
            "policy_step_count": len(audits),
            "deadlock_count": sum(
                int(audit["deadlock"]) for audit in audits
            ),
        }
    return rows


def _causal_comparison(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    current = _episode_rows(protocol, evidence)
    selected_pairs = {key[0] for key in current}
    original = _v14_comparator_rows(selected_pairs)
    if set(current) != set(original) or len(current) != 14:
        raise V15RecoveryDevelopmentTerminalError(
            "same-seed v14/v15 comparator population differs"
        )
    changes = []
    for key in sorted(current):
        before = original[key]
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
                    "v14_decision": before["decision"],
                    "v15_decision": after["decision"],
                    "v14_task_success": before["task_success"],
                    "v15_task_success": after["task_success"],
                    "v14_policy_step_count": before[
                        "policy_step_count"
                    ],
                    "v15_policy_step_count": after[
                        "policy_step_count"
                    ],
                    "v15_recovery_selected_count": after[
                        "recovery_selected_count"
                    ],
                }
            )
    return {
        "paired_l2_episode_count": len(current),
        "v14_deadlock_episode_count": sum(
            int(row["deadlock_count"] > 0) for row in original.values()
        ),
        "v15_deadlock_episode_count": sum(
            int(row["deadlock_count"] > 0) for row in current.values()
        ),
        "v14_task_success_count": sum(
            int(row["task_success"]) for row in original.values()
        ),
        "v15_task_success_count": sum(
            int(row["task_success"]) for row in current.values()
        ),
        "changed_episode_count": len(changes),
        "changes": changes,
    }


def _residual_deadlocks(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    rows = []
    for artifact in evidence["episodes"]:
        spec = schedule[str(artifact["episode_id"])]
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        for trace in episode["trace"]:
            if trace.get("phase") != "policy":
                continue
            audit = trace["predictive_virtual_brake"]
            if audit["deadlock"] is not True:
                continue
            recovery = next(
                candidate
                for candidate in audit["candidates"]
                if candidate["guard_margin_rad"] == 0.150001
            )
            rows.append(
                {
                    "base_pair_id": str(spec["base_pair_id"]),
                    "arm": str(spec["arm"]),
                    "runner_step_id": int(audit["runner_step_id"]),
                    "current_minimum_margin_rad": float(
                        audit["current_target_margin_rad"]
                    ),
                    "unguarded_predicted_minimum_margin_rad": float(
                        audit[
                            "unguarded_predicted_minimum_margin_rad"
                        ]
                    ),
                    "recovery_configuration_inside_guard_ranges": (
                        recovery["configuration_inside_guard_ranges"]
                    ),
                    "recovery_predicted_minimum_margin_rad": recovery[
                        "predicted_minimum_margin_rad"
                    ],
                    "recovery_eligible": recovery["eligible"],
                }
            )
    return sorted(rows, key=lambda row: (row["base_pair_id"], row["arm"]))


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
    entries = _checksum_entries(checksums_path)
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
        raise V15RecoveryDevelopmentTerminalError(
            "v15 recovery development population differs"
        )
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15RecoveryDevelopmentTerminalError(
                f"v15 development checksum differs: {relative}"
            )
    failed_gates = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed_gates != list(EXPECTED_FAILED_GATES):
        raise V15RecoveryDevelopmentTerminalError(
            "v15 development failed-gate set differs"
        )
    aggregate = evidence["aggregate"]
    comparison = _causal_comparison(protocol, evidence)
    residual = _residual_deadlocks(protocol, evidence)
    if (
        aggregate["recovery_selected_count"] != 12
        or aggregate["recovery_prevented_deadlock_count"] != 12
        or aggregate["residual_deadlock_count"] != 8
        or len(residual) != 8
        or comparison["v14_deadlock_episode_count"] != 10
        or comparison["v15_deadlock_episode_count"] != 8
        or comparison["v14_task_success_count"]
        != comparison["v15_task_success_count"]
    ):
        raise V15RecoveryDevelopmentTerminalError(
            "v15 recovery causal summary differs"
        )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "classification": evidence["classification"],
        "development_data_complete": True,
        "descriptive_clean_utility_gate_passed": False,
        "failed_gates": failed_gates,
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
            "same_environment_and_policy_seeds_as_v14": True,
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
        },
        "mechanism": {
            "trigger_count": aggregate["trigger_count"],
            "v14_baseline_would_deadlock_count": aggregate[
                "v14_baseline_would_deadlock_count"
            ],
            "recovery_attempt_count": aggregate[
                "recovery_attempt_count"
            ],
            "recovery_eligible_count": aggregate[
                "recovery_eligible_count"
            ],
            "recovery_selected_count": aggregate[
                "recovery_selected_count"
            ],
            "recovery_prevented_deadlock_count": aggregate[
                "recovery_prevented_deadlock_count"
            ],
            "residual_deadlock_count": aggregate[
                "residual_deadlock_count"
            ],
            "recovery_selected_minimum_actual_margin_rad": aggregate[
                "recovery_selected_minimum_actual_margin_rad"
            ],
            "recovery_selected_floor_violation_count": aggregate[
                "recovery_selected_floor_violation_count"
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
        "same_seed_v14_comparison": comparison,
        "residual_deadlocks": residual,
        "runtime_observation_disclosure": {
            "console_joint_limit_warnings_observed": True,
            "console_contact_capacity_warnings_observed": True,
            "warning_counts_bound_to_retained_artifact": False,
            "post_hoc_numeric_warning_counts_claimed": False,
        },
        "interpretation": {
            "single_step_feasibility_gap_partially_closed": True,
            "same_seed_deadlock_episode_reduction": 2,
            "same_seed_task_success_gain": 0,
            "recovery_development_success": False,
            "registered_v14_nonpass_unchanged": True,
            "next_factor": (
                "append a current-edge shadow candidate after the floor-edge "
                "candidate, then require fresh policy replanning if bounded "
                "guard continuation still cannot restore task progress"
            ),
        },
        "claim_boundary": (
            "This outcome-informed same-seed development replay is data "
            "complete, but it is not a recovery success. Twelve floor-edge "
            "steps safely continued transitions that the v14 candidate set "
            "would have terminated, reducing deadlock episodes from ten to "
            "eight, while producing no task-success gain. It cannot qualify "
            "task utility, attacked efficacy, deployment, hardware behavior, "
            "actuator authority, or physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V15RecoveryDevelopmentTerminalError(
            "tracked worktree must be clean before v15 terminal freeze"
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
            raise V15RecoveryDevelopmentTerminalError(
                f"v15 development terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
