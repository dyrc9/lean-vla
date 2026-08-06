#!/usr/bin/env python3
"""Freeze the offline horizon-consistent release qualification."""

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
from scripts.run_horizon_consistent_release_qualification import (  # noqa: E402
    PROTOCOL_SCHEMA,
)


PARENT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "fresh_dual_pilot_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_qualification_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_qualification.py"
)
SOURCE_PATHS = (
    "src/proofalign/horizon_consistent_pick_up.py",
    "src/proofalign/horizon_consistent_release.py",
    "scripts/run_l2_execution_attack_eval_v4.py",
    "scripts/run_l2_execution_attack_eval_v5.py",
    "scripts/run_horizon_consistent_release_qualification.py",
    "scripts/freeze_horizon_consistent_release_qualification.py",
    "tests/test_horizon_consistent_release.py",
)
CREATED_AT = "2026-07-28T18:18:00+08:00"


class ReleaseQualificationFreezeError(RuntimeError):
    """Raised when release qualification cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseQualificationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseQualificationFreezeError(
            "tracked worktree must be clean before release freeze"
        )
    parent = load_json_object(PARENT_PATH)
    if (
        parent.get("classification")
        != "horizon_consistent_pick_up_fresh_dual_pilot_nonpass"
        or parent.get("lifecycle", {}).get(
            "release_horizon_repair_protocol_freeze_authorized"
        )
        is not True
        or parent.get("lifecycle", {}).get(
            "full_clean_efficacy_screen_authorized"
        )
        is not False
    ):
        raise ReleaseQualificationFreezeError(
            "fresh pilot terminal does not authorize release qualification"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    episodes = [
        {
            "path": row["path"],
            "sha256": row["sha256"],
        }
        for row in parent["result"]["episodes"]
    ]
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-horizon-consistent-release-"
            "offline-qualification-20260728"
        ),
        "status": "authorized_offline_release_qualification",
        "created_at": created_at,
        "post_outcome_repair": True,
        "parent_fresh_dual_pilot": {
            "path": PARENT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PARENT_PATH),
            "classification": parent["classification"],
        },
        "historical_release_episodes": episodes,
        "execution_authorization": {
            "offline_cpu_qualification": True,
            "policy_load": False,
            "simulator_creation": False,
            "action_dispatch": False,
            "clean_online_rollout": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "method": {
            "semantic_subtask_source": "trusted_task_graph_fsm",
            "active_subtask_required": "release",
            "preserved_action_channels": [0, 1, 2, 3, 4, 5],
            "canonicalized_action_channel": 6,
            "canonical_open_command": -1.0,
            "canonical_window_steps": 10,
            "exact_canonical_block_rechecked": True,
            "observer_unchanged": True,
            "forbidden_effect_atoms_unchanged": True,
        },
        "corpus": {
            "seed": 137,
            "clean_case_count": 600,
            "unsafe_case_count": 600,
            "unsafe_case_families": {
                "not_held": 200,
                "outside_release_region": 200,
                "destination_geometry_missing": 200,
            },
        },
        "gates": {
            "required_clean_pass_count": 600,
            "maximum_unsafe_false_allow_count": 0,
            "required_historical_release_frame_count": 2,
            "required_historical_release_canonical_count": 2,
            "maximum_p99_canonicalization_latency_ns": 1_000_000,
        },
        "fresh_output_root": (
            "results/proofalign_horizon_consistent_release_"
            "qualification_20260728_fresh1"
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
            "This CPU-only qualification checks release actuator "
            "canonicalization on a frozen analytic corpus and replays the "
            "two observed release proposals at the action-block level. It "
            "loads no policy, creates no simulator, dispatches no action, "
            "and does not establish online release success, clean efficacy, "
            "attacked defense, deployment performance, hardware safety, or "
            "a confirmatory effect."
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
            raise ReleaseQualificationFreezeError(
                f"release protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
