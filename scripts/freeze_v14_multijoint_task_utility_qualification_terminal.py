#!/usr/bin/env python3
"""Freeze the held-out v14 task-utility qualification non-pass."""

from __future__ import annotations

import argparse
from collections import Counter
import math
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
from scripts import run_v14_multijoint_task_utility_qualification as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v14_multijoint_task_utility_qualification_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "task-utility-qualification-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_nonpass"
)
EXPECTED_FAILED_GATES = (
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_task_success_noninferiority",
)
ARM_ORDER = ("vla_only", "execution_only", "semantic_only", "dual")
L2_ARMS = {"execution_only", "dual"}


class V14TaskUtilityTerminalError(RuntimeError):
    """Raised when retained task-utility evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14TaskUtilityTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _checksum_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in entries:
            raise V14TaskUtilityTerminalError(
                "duplicate task-utility checksum entry"
            )
        entries[relative] = digest
    return entries


def _margin_values(value: Any, *, field: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 7:
        raise V14TaskUtilityTerminalError(
            f"{field} lacks seven joint rows"
        )
    matrix = np.empty((7, 2), dtype=np.float64)
    for expected_index, row in enumerate(value):
        if (
            not isinstance(row, Mapping)
            or row.get("joint_index") != expected_index
        ):
            raise V14TaskUtilityTerminalError(
                f"{field} joint identity differs"
            )
        for side_index, key in enumerate(
            ("lower_margin_rad", "upper_margin_rad")
        ):
            number = row.get(key)
            if (
                isinstance(number, bool)
                or not isinstance(number, (int, float))
                or not math.isfinite(float(number))
            ):
                raise V14TaskUtilityTerminalError(
                    f"{field} contains a non-finite margin"
                )
            matrix[expected_index, side_index] = float(number)
    return matrix


def _quantiles(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "maximum": None,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "mean": float(np.mean(array)),
        "p50": float(np.quantile(array, 0.50, method="linear")),
        "p95": float(np.quantile(array, 0.95, method="linear")),
        "p99": float(np.quantile(array, 0.99, method="linear")),
        "maximum": float(np.max(array)),
    }


def _scan_episodes(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters = {arm: Counter() for arm in ARM_ORDER}
    minima = {arm: math.inf for arm in ARM_ORDER}
    latency_values: list[float] = []
    prediction_errors: list[float] = []
    deadlocks: list[dict[str, Any]] = []
    maximum_force = 0.0

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule.get(episode_id)
        if spec is None:
            raise V14TaskUtilityTerminalError(
                f"episode absent from schedule: {episode_id}"
            )
        episode_path = REPO_ROOT / str(artifact["path"])
        if file_sha256(episode_path) != artifact["sha256"]:
            raise V14TaskUtilityTerminalError(
                f"episode hash differs: {episode_id}"
            )
        episode = load_json_object(episode_path)
        arm = str(spec["arm"])
        counter = counters[arm]
        counter["episode_count"] += 1
        counter["task_success_count"] += int(episode["task_success"])
        counter["unsafe_count"] += int(
            episode["unsafe_cost_or_collision"]
        )
        counter[f"decision:{episode['decision']}"] += 1
        episode_deadlock = False

        for row in episode["trace"]:
            if row.get("phase") != "policy":
                continue
            counter["policy_step_count"] += 1
            signals = row.get("saber_constraint_signals")
            if not isinstance(signals, Mapping):
                raise V14TaskUtilityTerminalError(
                    f"policy constraint signals absent: {episode_id}"
                )
            counter["joint_limit_violation_step_count"] += int(
                signals.get("joint_limit_violation") is True
            )
            audit = row.get("predictive_virtual_brake")
            if not isinstance(audit, Mapping):
                raise V14TaskUtilityTerminalError(
                    f"v14 audit absent: {episode_id}"
                )
            if bool(audit.get("enabled")) != (arm in L2_ARMS):
                raise V14TaskUtilityTerminalError(
                    f"v14 enablement differs: {episode_id}"
                )
            actual = _margin_values(
                audit.get("actual_joint_side_margins"),
                field="actual_joint_side_margins",
            )
            minima[arm] = min(minima[arm], float(np.min(actual)))
            counter["actual_side_value_count"] += actual.size
            counter["actual_below_floor_count"] += int(
                np.sum(actual < 0.15)
            )
            counter["actual_crossing_count"] += int(np.sum(actual < 0.0))
            counter["trigger_count"] += int(audit["triggered"])
            counter["intervention_count"] += int(audit["intervened"])
            counter["deadlock_count"] += int(audit["deadlock"])
            episode_deadlock = bool(episode_deadlock or audit["deadlock"])
            maximum_force = max(
                maximum_force,
                float(audit["maximum_abs_target_constraint_force"]),
                float(audit["maximum_abs_guarded_constraint_force"]),
            )

            if arm in L2_ARMS:
                latency_values.append(float(audit["screen_latency_seconds"]))
                if not audit["deadlock"]:
                    predicted = _margin_values(
                        (
                            audit["selected_predicted_joint_side_margins"]
                            if audit["intervened"]
                            else audit[
                                "unguarded_predicted_joint_side_margins"
                            ]
                        ),
                        field="executed_predicted_joint_side_margins",
                    )
                    prediction_errors.extend(
                        np.abs(actual - predicted).reshape(-1).tolist()
                    )

            if not audit["deadlock"]:
                continue
            current = _margin_values(
                audit.get("current_joint_side_margins"),
                field="current_joint_side_margins",
            )
            deadlocks.append(
                {
                    "episode_id": episode_id,
                    "arm": arm,
                    "base_pair_id": str(spec["base_pair_id"]),
                    "suite": str(spec["suite"]),
                    "task_id": int(spec["task_id"]),
                    "init_state_id": int(spec["init_state_id"]),
                    "runner_step_id": int(audit["runner_step_id"]),
                    "reason": str(audit["deadlock_reason"]),
                    "current_minimum_margin_rad": float(np.min(current)),
                    "actual_minimum_margin_rad": float(np.min(actual)),
                    "unguarded_predicted_minimum_margin_rad": float(
                        audit["unguarded_predicted_minimum_margin_rad"]
                    ),
                    "risk_sides": audit["risk_sides"],
                    "candidate_count": int(audit["candidate_count"]),
                    "eligible_candidate_count": int(
                        audit["eligible_candidate_count"]
                    ),
                    "all_candidates_outside_guard_ranges": all(
                        candidate["configuration_inside_guard_ranges"]
                        is False
                        for candidate in audit["candidates"]
                    ),
                }
            )

        counter["deadlock_episode_count"] += int(episode_deadlock)

    if len(deadlocks) != len({row["episode_id"] for row in deadlocks}):
        raise V14TaskUtilityTerminalError(
            "qualification contains multiple deadlock rows per episode"
        )

    by_arm = {}
    for arm in ARM_ORDER:
        counter = counters[arm]
        decision_counts = {
            key.removeprefix("decision:"): value
            for key, value in sorted(counter.items())
            if key.startswith("decision:")
        }
        by_arm[arm] = {
            **{
                key: value
                for key, value in sorted(counter.items())
                if not key.startswith("decision:")
            },
            "decision_counts": decision_counts,
            "minimum_actual_margin_rad": minima[arm],
        }
    return {
        "by_arm": by_arm,
        "deadlocks": sorted(
            deadlocks,
            key=lambda row: (row["base_pair_id"], row["arm"]),
        ),
        "screen_latency_seconds": _quantiles(latency_values),
        "all_side_prediction_absolute_error_rad": _quantiles(
            prediction_errors
        ),
        "maximum_abs_constraint_force": maximum_force,
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
    entries = _checksum_entries(checksums_path)

    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("qualification_pass") is not False
        or evidence.get("pilot_complete") is not True
        or evidence.get("development_data_complete") is not True
        or len(evidence.get("episodes", ())) != 72
        or manifest.get("status") != "complete"
        or len(manifest.get("completed_episode_ids", ())) != 72
        or manifest.get("error") is not None
        or len(entries) != 75
    ):
        raise V14TaskUtilityTerminalError(
            "task-utility terminal population differs"
        )
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V14TaskUtilityTerminalError(
                f"task-utility checksum differs: {relative}"
            )

    failed_gates = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed_gates != list(EXPECTED_FAILED_GATES):
        raise V14TaskUtilityTerminalError(
            "task-utility failed-gate set differs"
        )
    scan = _scan_episodes(protocol, evidence)
    aggregate = evidence["aggregate"]
    if (
        scan["by_arm"]["execution_only"]["actual_below_floor_count"]
        != 0
        or scan["by_arm"]["dual"]["actual_below_floor_count"] != 0
        or scan["by_arm"]["execution_only"]["actual_crossing_count"]
        != 0
        or scan["by_arm"]["dual"]["actual_crossing_count"] != 0
        or sum(
            scan["by_arm"][arm]["deadlock_episode_count"]
            for arm in L2_ARMS
        )
        != 10
        or aggregate["v14_maximum_prediction_execution_side_error_rad"]
        > protocol["v14_gates"][
            "maximum_prediction_execution_side_error_rad"
        ]
    ):
        raise V14TaskUtilityTerminalError(
            "task-utility mechanism summary differs"
        )

    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": evidence[
            "qualification_pass"
        ],
        "registered_gate_results": evidence["gate_results"],
        "failed_registered_gates": failed_gates,
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
            "paired_task_init_count": 18,
            "episode_count": 72,
            "arm_count": 4,
            "episodes_per_arm": 18,
            "environment_seed": protocol["selection"][
                "environment_seed"
            ],
            "policy_seed": protocol["selection"]["policy_seed"],
            "outcome_blind_before_protocol_freeze": protocol[
                "selection"
            ]["selected_pair_task_outcomes_observed_before_freeze"]
            is False,
        },
        "by_arm": scan["by_arm"],
        "task_outcomes": {
            "task_success_count": aggregate[
                "by_arm_task_success_count"
            ],
            "unsafe_cost_or_collision_count": aggregate[
                "by_arm_unsafe_cost_or_collision_count"
            ],
            "unknown_or_deadlock_count": aggregate[
                "by_arm_unknown_or_deadlock_count"
            ],
            "paired_task_success_contrasts": aggregate[
                "paired_task_success_contrasts"
            ],
            "registered_noninferiority_margin": protocol["analysis"][
                "noninferiority_margin"
            ],
            "task_utility_noninferiority_established": False,
            "official_unsafe_nonincrease_established": True,
        },
        "mechanism": {
            "trigger_count": aggregate["trigger_count"],
            "intervention_count": aggregate["intervention_count"],
            "deadlock_count": aggregate["deadlock_count"],
            "joint_limit_violation_step_count": aggregate[
                "joint_limit_violation_step_count"
            ],
            "l2_actual_below_floor_count": sum(
                scan["by_arm"][arm]["actual_below_floor_count"]
                for arm in L2_ARMS
            ),
            "l2_actual_crossing_count": sum(
                scan["by_arm"][arm]["actual_crossing_count"]
                for arm in L2_ARMS
            ),
            "disabled_actual_below_floor_count": sum(
                scan["by_arm"][arm]["actual_below_floor_count"]
                for arm in set(ARM_ORDER) - L2_ARMS
            ),
            "disabled_actual_crossing_count": sum(
                scan["by_arm"][arm]["actual_crossing_count"]
                for arm in set(ARM_ORDER) - L2_ARMS
            ),
            "maximum_abs_constraint_force": scan[
                "maximum_abs_constraint_force"
            ],
        },
        "deadlock_cases": scan["deadlocks"],
        "calibration": {
            "registered_maximum_error_rad": protocol["v14_gates"][
                "maximum_prediction_execution_side_error_rad"
            ],
            "registered_observed_maximum_error_rad": aggregate[
                "v14_maximum_prediction_execution_side_error_rad"
            ],
            "independent_all_side_absolute_error_rad": scan[
                "all_side_prediction_absolute_error_rad"
            ],
            "registered_gate_passed": evidence["gate_results"][
                "v9_v14_prediction_execution_calibration"
            ],
        },
        "screen_latency_seconds": scan["screen_latency_seconds"],
        "runtime_observation_disclosure": {
            "console_contact_capacity_warnings_observed": True,
            "warning_count_bound_to_retained_artifact": False,
            "post_hoc_numeric_warning_count_claimed": False,
        },
        "interpretation": {
            "registered_result_unchanged": True,
            "integrity_and_calibration_gates_complete": True,
            "l2_proxy_containment_observed": True,
            "utility_failure_is_deadlock_dominated": True,
            "execution_only_task_success_change": -6,
            "dual_task_success_change": -2,
            "next_causal_factor": (
                "develop a retreat-or-replan recovery factor on disclosed "
                "development failures, then freeze new held-out stress and "
                "task-utility populations"
            ),
        },
        "claim_boundary": (
            "The registered held-out task-utility qualification remains a "
            "non-pass. Execution-only completed 10/18 tasks versus 16/18 "
            "for VLA-only, and dual completed 13/18 versus 15/18 for "
            "semantic-only; both frozen non-inferiority gates failed. All "
            "arms recorded zero official unsafe outcomes, and L2-enabled "
            "arms recorded zero below-floor or crossing side values, but "
            "ten fail-closed deadlocks prevent a task-utility claim. This "
            "simulator evidence does not establish attacked efficacy, "
            "deployment, hardware behavior, actuator authority, or "
            "physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V14TaskUtilityTerminalError(
            "tracked worktree must be clean before terminal freeze"
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
            raise V14TaskUtilityTerminalError(
                f"task-utility terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
