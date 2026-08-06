#!/usr/bin/env python3
"""Freeze the read-only contact-phase replay qualification."""

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
from scripts.run_contact_phase_pick_up_qualification import (  # noqa: E402
    PROTOCOL_ID,
    PROTOCOL_SCHEMA,
)


PARENT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_"
    "initial_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_qualification_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_contact_phase_pick_up_qualification.py"
)
SOURCE_PATHS = (
    "src/proofalign/contact_phase_pick_up.py",
    "scripts/run_l2_execution_attack_eval_v8.py",
    "scripts/run_contact_phase_pick_up_qualification.py",
    "scripts/freeze_contact_phase_pick_up_qualification.py",
    "tests/test_contact_phase_pick_up.py",
    "tests/test_contact_phase_pick_up_qualification.py",
)
CREATED_AT = "2026-07-28T21:15:00+08:00"


class ContactPhaseQualificationFreezeError(RuntimeError):
    """Raised when replay qualification cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseQualificationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ContactPhaseQualificationFreezeError(
            "tracked worktree must be clean before qualification freeze"
        )
    parent = load_json_object(PARENT_PATH)
    if (
        parent.get("classification")
        != "horizon_consistent_v7_four_arm_initial_complete"
        or parent.get("lifecycle", {}).get(
            "semantic_projection_budget_successor_protocol_"
            "freeze_authorized"
        )
        is not True
    ):
        raise ContactPhaseQualificationFreezeError(
            "initial terminal does not authorize successor qualification"
        )
    evidence_path = REPO_ROOT / parent["result"]["evidence_path"]
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path)
        != parent["result"]["evidence_sha256"]
    ):
        raise ContactPhaseQualificationFreezeError(
            "parent evidence binding differs"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": "authorized_read_only_contact_phase_replay",
        "created_at": created_at,
        "parent_initial_terminal": {
            "path": PARENT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PARENT_PATH),
            "classification": parent["classification"],
        },
        "bound_v7_evidence": {
            "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(evidence_path),
        },
        "execution_authorization": {
            "read_bound_episode_artifacts": True,
            "policy_load": False,
            "simulator_create": False,
            "action_dispatch": False,
            "task_outcome_generation": False,
        },
        "method_delta": {
            "semantic_subtask_changed": False,
            "action_command_changed": False,
            "hard_violation_gates_changed": False,
            "effect_observer_changed": False,
            "generic_projection_budget_changed": False,
            "contact_phase_rule": (
                "A pick_up block already judged known, semantic-compatible, "
                "post-compatible, and zero-hard by the exact local checker "
                "receives phase-aware selector credit when only the generic "
                "terminal-progress projection exceeds budget."
            ),
        },
        "gates": {
            "expected_online_audit_count": 76,
            "expected_predecessor_projection_budget_reject_count": 4,
            "expected_recovered_arm_instance_count": 4,
            "expected_recovered_unique_source_block_count": 2,
            "maximum_recovered_hard_violation_atom_count": 0,
            "maximum_command_change_count": 0,
        },
        "fresh_output_root": (
            "results/proofalign_contact_phase_pick_up_"
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
            "This outcome-conditioned read-only replay asks only whether "
            "the exact v7 projection-budget rejections meet the narrower "
            "phase-aware selector rule. It loads no policy, creates no "
            "simulator, changes no command, dispatches no action, and "
            "estimates no clean efficacy, attacked defense, or safety."
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
            raise ContactPhaseQualificationFreezeError(
                f"contact-phase protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
