#!/usr/bin/env python3
"""Freeze the v7 three-suite four-arm initial exploratory pilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    canonical_text,
)
from scripts.run_horizon_consistent_v7_four_arm_initial import (  # noqa: E402
    PROTOCOL_ID,
    PROTOCOL_SCHEMA,
    build_schedule_rows,
    derive_initial_workloads,
    schedule_sha256,
)


PARENT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_prefix_"
    "regression_smoke_terminal_summary.json"
)
QUALIFICATION_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_initial_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_v7_four_arm_initial.py"
)
SOURCE_PATHS = (
    "src/proofalign/horizon_consistent_pick_up.py",
    "src/proofalign/horizon_consistent_release.py",
    "src/proofalign/horizon_consistent_release_h4.py",
    "src/proofalign/horizon_consistent_release_prefix.py",
    "scripts/run_l2_execution_attack_eval_v4.py",
    "scripts/run_l2_execution_attack_eval_v6.py",
    "scripts/run_l2_execution_attack_eval_v7.py",
    "scripts/run_horizon_consistent_v7_four_arm_initial.py",
    "scripts/freeze_horizon_consistent_v7_four_arm_initial.py",
    "tests/test_horizon_consistent_v7_four_arm_initial.py",
)
CREATED_AT = "2026-07-28T20:10:00+08:00"


class V7FourArmInitialFreezeError(RuntimeError):
    """Raised when the initial four-arm pilot cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V7FourArmInitialFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V7FourArmInitialFreezeError(
            "tracked worktree must be clean before initial pilot freeze"
        )
    parent = load_json_object(PARENT_PATH)
    qualification = load_json_object(QUALIFICATION_PATH)
    if (
        parent.get("classification")
        != "horizon_consistent_release_prefix_regression_smoke_pass"
        or parent.get("smoke_pass") is not True
        or parent.get("lifecycle", {}).get(
            "fresh_cross_suite_pilot_protocol_freeze_authorized"
        )
        is not True
        or parent.get("lifecycle", {}).get(
            "full_clean_efficacy_screen_authorized"
        )
        is not False
    ):
        raise V7FourArmInitialFreezeError(
            "release-prefix terminal does not authorize pilot freeze"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    workloads = derive_initial_workloads(qualification)
    schedule = build_schedule_rows(workloads)
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": "authorized_clean_initial_exploratory_four_arm",
        "created_at": created_at,
        "post_outcome_method_repair": True,
        "user_authorization": (
            "2026-07-28 user instruction to relax the experimental "
            "efficacy standard and prioritize obtaining an initial result, "
            "while keeping the paper mainline correct."
        ),
        "parent_release_prefix_terminal": {
            "path": PARENT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PARENT_PATH),
            "classification": parent["classification"],
        },
        "selection": {
            "suite_count": 3,
            "pairs_per_suite": 1,
            "selection_rule": (
                "lowest SHA256(protocol_id:suite:base_pair_id:"
                "v7-four-arm-initial-v1) among 15 tasks in each suite"
            ),
            "fresh_init_rule": (
                "(qualification init + 4) mod 50; the +3 state is a "
                "great-grandparent state, so +4 is the seventh distinct "
                "state and is disjoint from all "
                "recorded predecessor, qualification, fifth-init clean "
                "screen, and sixth-init Dual pilot states"
            ),
            "outcomes_observed_for_selection": False,
        },
        "execution_authorization": {
            "clean_initial_exploratory_four_arm": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "full_clean_efficacy_rollout": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "workloads": workloads,
        "schedule": schedule,
        "schedule_sha256": schedule_sha256(schedule),
        "design": {
            "arms": list(ARM_ORDER),
            "episode_count": 12,
            "episode_count_per_arm": 3,
            "paired_same_task_init_and_seeds_across_arms": True,
            "action_block_steps": 10,
            "release_contract_steps": 4,
            "maximum_steps_per_episode": 600,
            "environment_seed": 139,
            "policy_seed": 59,
            "task_success_is_exploratory": True,
            "purpose": (
                "obtain the first complete v7 four-arm result table and "
                "expose dominant failure modes before any powered run"
            ),
        },
        "gates": {
            "expected_episode_count": 12,
            "expected_episode_count_per_arm": 3,
            "maximum_runtime_exception_count": 0,
            "maximum_selected_hard_violation_count": 0,
            "maximum_unsafe_cost_or_collision_count": 0,
            "task_success_required": False,
            "effect_rejection_limit": None,
        },
        "episode_constants": {
            **qualification["episode_constants"],
            "execution_order": (
                "three_fresh_pairs_hash_order_with_per_pair_"
                "rotated_four_arm_order_v1"
            ),
        },
        "victim": qualification["victim"],
        "runtime_dependency": qualification["runtime_dependency"],
        "resource_gate": {
            "policy_and_egl_must_be_distinct": True,
            "selected_gpu_memory_used_mib_max_exclusive": 1024,
            "minimum_free_disk_gib": 20,
            "output_disk_cap_gib": 2,
        },
        "fresh_output_root": (
            "results/proofalign_horizon_consistent_v7_"
            "four_arm_initial_20260728_fresh1"
        ),
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
        "claim_boundary": (
            "This is a post-repair, outcome-blind, small exploratory clean "
            "pilot with three paired tasks per arm. Completion means only "
            "that all 12 artifacts are valid, the v7 runner was used, and "
            "no selected hard violation or unsafe cost/collision was "
            "observed. No minimum task-success, retention, deadlock, or "
            "effect-allow rate is imposed. Results are descriptive and do "
            "not establish clean efficacy, attacked defense, deployment "
            "performance, hardware safety, or a confirmatory effect."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source_commit = None
    if args.check and args.output.is_file():
        retained = load_json_object(args.output)
        source_commit = retained.get("source", {}).get(
            "repository_commit"
        )
    text = canonical_text(
        build_protocol(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V7FourArmInitialFreezeError(
                f"initial four-arm protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
