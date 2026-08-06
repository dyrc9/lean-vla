#!/usr/bin/env python3
"""Freeze the release-prefix progress regression smoke."""

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
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts.run_horizon_consistent_release_prefix_regression_smoke import (  # noqa: E402
    PROTOCOL_SCHEMA,
)


PARENT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_h4_"
    "regression_smoke_terminal_summary.json"
)
BASE_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_h4_"
    "regression_smoke_v2_protocol.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_prefix_"
    "regression_smoke_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_prefix_regression_smoke.py"
)
SOURCE_PATHS = (
    "src/proofalign/horizon_consistent_pick_up.py",
    "src/proofalign/horizon_consistent_release.py",
    "src/proofalign/horizon_consistent_release_h4.py",
    "src/proofalign/horizon_consistent_release_prefix.py",
    "scripts/run_l2_execution_attack_eval_v4.py",
    "scripts/run_l2_execution_attack_eval_v6.py",
    "scripts/run_l2_execution_attack_eval_v7.py",
    "scripts/run_horizon_consistent_release_prefix_regression_smoke.py",
    "scripts/freeze_horizon_consistent_release_prefix_regression_smoke.py",
    "tests/test_horizon_consistent_release_prefix.py",
)
CREATED_AT = "2026-07-28T18:56:00+08:00"


class ReleasePrefixFreezeError(RuntimeError):
    """Raised when release-prefix regression cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleasePrefixFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleasePrefixFreezeError(
            "tracked worktree must be clean before prefix freeze"
        )
    parent = load_json_object(PARENT_PATH)
    base = load_json_object(BASE_PROTOCOL_PATH)
    if (
        parent.get("classification")
        != "horizon_consistent_release_h4_regression_smoke_nonpass"
        or parent.get("lifecycle", {}).get(
            "release_prefix_progress_protocol_freeze_authorized"
        )
        is not True
        or parent.get("lifecycle", {}).get(
            "full_clean_efficacy_screen_authorized"
        )
        is not False
    ):
        raise ReleasePrefixFreezeError(
            "H4 terminal does not authorize prefix freeze"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = {
        **base,
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-horizon-consistent-release-prefix-"
            "regression-smoke-20260728"
        ),
        "status": "authorized_release_prefix_progress_regression_smoke",
        "created_at": created_at,
        "parent_h4_terminal": {
            "path": PARENT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PARENT_PATH),
            "classification": parent["classification"],
        },
        "execution_authorization": {
            "clean_dual_release_prefix_regression_smoke": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "clean_efficacy_rollout": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "design": {
            **base["design"],
            "finite_release_promised_effect": (
                "release_prefix_progress"
            ),
            "release_prefix_progress_threshold": (
                "trusted gripper opening delta >= 0.002"
            ),
            "completed_release_not_promised_by_h4": True,
            "task_graph_completion_guard_unchanged": True,
            "benchmark_reward_used_as_effect_atom": False,
            "observer_terminal_open_threshold_unchanged": True,
            "forbidden_effect_atoms_unchanged": True,
        },
        "fresh_output_root": (
            "results/proofalign_horizon_consistent_release_"
            "prefix_regression_smoke_20260728_fresh1"
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
            "This outcome-conditioned regression tests only whether a "
            "complete H4 release block makes trusted gripper-opening progress "
            "that satisfies its finite-horizon contract. It does not use "
            "benchmark reward as an effect, does not weaken the task-graph "
            "completion guard or forbidden effects, and does not estimate "
            "clean efficacy, attacked defense, deployment performance, "
            "hardware safety, or a confirmatory effect."
        ),
    }
    return protocol


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
            raise ReleasePrefixFreezeError(
                f"release-prefix protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
