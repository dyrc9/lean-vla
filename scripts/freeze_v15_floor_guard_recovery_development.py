#!/usr/bin/env python3
"""Freeze outcome-informed v15 floor-guard recovery development."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from scripts.run_contact_phase_pick_up_clean_pilot import schedule_sha256  # noqa: E402
from scripts import run_v15_floor_guard_recovery_development as runner  # noqa: E402


V14_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_protocol.json"
)
V14_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_floor_guard_recovery_development.py"
)
SOURCE_PATHS = (
    "scripts/run_l2_predictive_virtual_brake_v15_floor_guard_recovery.py",
    "scripts/run_v15_floor_guard_recovery_development.py",
    "scripts/freeze_v15_floor_guard_recovery_development.py",
    "tests/test_v15_floor_guard_recovery.py",
    "tests/test_v15_floor_guard_recovery_development.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-floor-guard-recovery-"
    "development-20260731"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
STAGE = "predictive_virtual_brake_v15_floor_guard_recovery_development"


class V15RecoveryDevelopmentFreezeError(RuntimeError):
    """Raised when the development protocol cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryDevelopmentFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15RecoveryDevelopmentFreezeError(
            f"v15 predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _selected_base_pairs(
    terminal: Mapping[str, Any],
) -> tuple[str, ...]:
    selected = tuple(
        sorted(
            {
                str(row["base_pair_id"])
                for row in terminal["deadlock_cases"]
            }
        )
    )
    if len(selected) != 7:
        raise V15RecoveryDevelopmentFreezeError(
            "v15 development requires the seven disclosed deadlock pairs"
        )
    return selected


def _development_schedule(
    source: Mapping[str, Any],
    selected: tuple[str, ...],
) -> list[dict[str, Any]]:
    old_stage = str(source["stage"])
    rows = [
        dict(row)
        for row in source["schedule"]
        if str(row["base_pair_id"]) in selected
    ]
    if len(rows) != 28:
        raise V15RecoveryDevelopmentFreezeError(
            "v15 development schedule must contain seven four-arm units"
        )
    schedule = []
    for row in rows:
        episode_id = str(row["episode_id"])
        if not episode_id.startswith(old_stage + "_"):
            raise V15RecoveryDevelopmentFreezeError(
                "source episode stage prefix differs"
            )
        schedule.append(
            {
                **row,
                "sequence_index": len(schedule),
                "episode_id": STAGE + episode_id[len(old_stage) :],
            }
        )
    return schedule


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15RecoveryDevelopmentFreezeError(
            "worktree must be clean before v15 development freeze"
        )
    source = load_json_object(V14_PROTOCOL_PATH)
    terminal = load_json_object(V14_TERMINAL_PATH)
    if (
        source.get("schema")
        != (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "task-utility-qualification-protocol.v1"
        )
        or terminal.get("registered_qualification_pass") is not False
        or terminal.get("failed_registered_gates")
        != [
            "v9_dual_task_success_noninferiority",
            "v9_execution_only_task_success_noninferiority",
        ]
        or len(terminal.get("deadlock_cases", ())) != 10
    ):
        raise V15RecoveryDevelopmentFreezeError(
            "v15 development predecessor differs from disclosed non-pass"
        )
    selected = _selected_base_pairs(terminal)
    workloads = [
        dict(row)
        for row in source["workloads"]
        if str(row["base_pair_id"]) in selected
    ]
    schedule = _development_schedule(source, selected)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")

    protocol = deepcopy(source)
    protocol.update(
        {
            "schema": runner.PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": runner.AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": STAGE,
            "pass_classification": (
                "predictive_virtual_brake_v15_floor_guard_recovery_"
                "development_descriptive_utility_pass"
            ),
            "nonpass_classification": (
                "predictive_virtual_brake_v15_floor_guard_recovery_"
                "development_descriptive_utility_nonpass"
            ),
            "complete_classification": (
                "predictive_virtual_brake_v15_floor_guard_recovery_"
                "development_data_complete"
            ),
            "incomplete_classification": (
                "predictive_virtual_brake_v15_floor_guard_recovery_"
                "development_integrity_nonpass"
            ),
            "fresh_output_root": (
                "results/proofalign_predictive_virtual_brake_v15_"
                "floor_guard_recovery_development_20260731_fresh1"
            ),
            "required_bindings": [
                _binding(V14_PROTOCOL_PATH),
                _binding(V14_TERMINAL_PATH),
            ],
            "selection": {
                "population_source": (
                    "all seven base pairs with at least one disclosed v14 "
                    "task-utility deadlock"
                ),
                "pair_count": 7,
                "environment_seed": source["selection"][
                    "environment_seed"
                ],
                "policy_seed": source["selection"]["policy_seed"],
                "outcome_informed_pair_selection": True,
                "selected_pair_task_outcomes_observed_before_freeze": True,
                "confirmatory_population": False,
                "same_seed_causal_replay": True,
            },
            "workloads": workloads,
            "schedule": schedule,
            "schedule_sha256": schedule_sha256(schedule),
            "design": {
                **source["design"],
                "study_role": (
                    "outcome-informed floor-guard recovery development"
                ),
                "pair_count": 7,
                "episode_count": 28,
                "recovery_factor": (
                    "append 0.150001-rad shadow-validated guard after all "
                    "v14 candidates are evaluated"
                ),
                "v14_candidate_order_preserved": True,
                "source_action_substitution": False,
            },
            "analysis": {
                **source["analysis"],
                "role": "outcome-informed recovery development",
                "utility_and_unsafe_gates_are_descriptive": True,
                "all_28_episodes_required_before_analysis": True,
                "all_72_episodes_required_before_analysis": False,
                "outcome_based_early_stopping": False,
            },
            "gates": {
                **source["gates"],
                "expected_episode_count": 28,
            },
            "v10_gates": {
                **source["v10_gates"],
                "expected_paired_first_action_block_match_count": 7,
                "expected_paired_workload_count": 7,
            },
            "v13_gates": {
                **source["v13_gates"],
                "expected_episode_count": 28,
                "expected_paired_workload_count": 7,
            },
            "v14_gates": {
                **source["v14_gates"],
                "expected_episode_count": 28,
                "expected_paired_workload_count": 7,
            },
            "episode_constants": {
                **source["episode_constants"],
                "execution_order": (
                    "seven disclosed deadlock-associated units in retained "
                    "v14 order with the original rotated four-arm order"
                ),
            },
            "stop_rule": {
                **source["stop_rule"],
                "run_clean_schedule_to_completion": True,
                "outcome_based_early_stopping": False,
                "future_qualification_requires_separate_protocol": True,
                "attacked_stage_authorized": False,
            },
            "source": {
                "repository_commit": bound_commit,
                "repository_tree": _git(
                    "rev-parse", f"{bound_commit}^{{tree}}"
                ),
                "sha256": {
                    relative: file_sha256(REPO_ROOT / relative)
                    for relative in SOURCE_PATHS
                },
                "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "freezer_sha256": file_sha256(SELF_PATH),
            },
            "outcomes_observed_for_selection": True,
            "stress_proxy_results_observed_for_protocol_design": True,
            "outcome_conditioned_engineering_regression": True,
            "claim_boundary": (
                "This development population is explicitly selected from "
                "the seven task/init pairs with a disclosed v14 deadlock "
                "and reuses their environment and policy seeds. It may "
                "diagnose whether the floor-edge fallback removes the known "
                "0.15-to-0.16-rad feasibility gap. It cannot qualify task "
                "utility, attacked efficacy, deployment, hardware behavior, "
                "actuator authority, or physical safety."
            ),
        }
    )
    return protocol


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
    protocol = build_protocol(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        ),
        source_commit=(
            str(retained["source"]["repository_commit"])
            if retained is not None
            else None
        ),
    )
    text = canonical_text(protocol)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15RecoveryDevelopmentFreezeError(
                f"v15 development protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
