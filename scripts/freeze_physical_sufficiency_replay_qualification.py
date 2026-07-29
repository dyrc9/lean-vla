#!/usr/bin/env python3
"""Freeze the read-only v10 mechanism replay protocol."""

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
from scripts.run_physical_sufficiency_replay_qualification import (  # noqa: E402
    PROTOCOL_ID,
    PROTOCOL_SCHEMA,
)


V9_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_risk_selective_fresh15_cotenant_protocol.json"
)
V9_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_risk_selective_fresh15_cotenant_20260729_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_replay_qualification_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_physical_sufficiency_replay_qualification.py"
)
SOURCE_PATHS = (
    "src/proofalign/physical_sufficiency_semantic.py",
    "scripts/run_l2_execution_attack_eval_v10.py",
    "scripts/run_physical_sufficiency_replay_qualification.py",
    "scripts/freeze_physical_sufficiency_replay_qualification.py",
    "tests/test_physical_sufficiency_semantic.py",
    "tests/test_physical_sufficiency_replay_qualification.py",
)
CREATED_AT = "2026-07-29T17:15:00+08:00"


class PhysicalSufficiencyReplayFreezeError(RuntimeError):
    """Raised when the v10 replay protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PhysicalSufficiencyReplayFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise PhysicalSufficiencyReplayFreezeError(
            "tracked worktree must be clean before replay freeze"
        )
    evidence_path = V9_ROOT / "pilot_evidence.json"
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("classification")
        != "risk_selective_fresh15_clean_data_complete"
        or evidence.get("pilot_complete") is not True
    ):
        raise PhysicalSufficiencyReplayFreezeError(
            "v9 fresh15 evidence is not complete"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": "authorized_read_only_physical_sufficiency_replay",
        "created_at": created_at,
        "parent_v9_protocol": {
            "path": V9_PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(V9_PROTOCOL_PATH),
        },
        "bound_v9_evidence": {
            "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(evidence_path),
            "classification": evidence["classification"],
        },
        "execution_authorization": {
            "read_bound_episode_artifacts": True,
            "policy_load": False,
            "simulator_create": False,
            "action_dispatch": False,
            "task_outcome_generation": False,
        },
        "method_delta": {
            "articulation_unknown": (
                "run available velocity/workspace/contact screens; make "
                "only the unavailable task-state predicate advisory"
            ),
            "target_not_held_after_move": "advisory replan",
            "physical_risk": "unchanged hard reject",
            "cost_collision_and_integrity": "unchanged fail closed",
            "source_action_block": "unchanged",
        },
        "gates": {
            "semantic_episode_count": 30,
            "nominal_audit_count": 656,
            "unchanged_source_action_block_count": 656,
            "physical_screened_semantic_unknown_count": 6,
            "successor_nominal_eligible_count": 653,
            "successor_physical_or_unknown_reject_count": 3,
            "predecessor_terminal_action_reject_count": 9,
            "successor_recovered_semantic_unknown_count": 6,
            "successor_retained_physical_reject_count": 3,
            "predecessor_effect_reject_count": 11,
            "successor_effect_replan_count": 4,
            "successor_retained_effect_reject_count": 7,
        },
        "fresh_output_root": (
            "results/proofalign_physical_sufficiency_replay_"
            "qualification_20260729_fresh1"
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
            "This post-v9 outcome-conditioned read-only replay validates "
            "only the v10 mechanism partition on retained traces. It loads "
            "no policy, creates no simulator, dispatches no action, computes "
            "no counterfactual success rate, and makes no clean efficacy, "
            "attacked-defense, causal-safety, timing, deployment, or "
            "hardware claim."
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
            raise PhysicalSufficiencyReplayFreezeError(
                f"v10 replay protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
