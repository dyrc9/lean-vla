#!/usr/bin/env python3
"""Freeze terminal evidence for the v3 pick-up regression smoke."""

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
from scripts import (  # noqa: E402
    run_horizon_consistent_pick_up_regression_smoke as runner,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "regression_smoke_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_pick_up_"
    "regression_smoke_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "regression_smoke_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_pick_up_"
    "regression_smoke_terminal.py"
)
CREATED_AT = "2026-07-28T17:43:00+08:00"


class HorizonPickUpSmokeTerminalError(RuntimeError):
    """Raised when regression terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise HorizonPickUpSmokeTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_terminal(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise HorizonPickUpSmokeTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = runner.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    observed = evidence["observed"]
    if (
        evidence.get("classification")
        != "horizon_consistent_pick_up_regression_smoke_pass"
        or evidence.get("smoke_pass") is not True
        or any(
            value is not True
            for value in evidence["gate_results"].values()
        )
        or manifest.get("status") != "complete"
        or observed.get("complete_transaction_count") != 8
        or observed.get("effect_allow_count") != 8
        or observed.get("effect_reject_count") != 0
        or observed.get("horizon_without_holding_count") != 7
    ):
        raise HorizonPickUpSmokeTerminalError(
            "regression smoke is not the expected completed pass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    episode_relative = evidence["episode"]["path"]
    return {
        "schema": (
            "proofalign.horizon-consistent-pick-up-"
            "regression-smoke-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": evidence["classification"],
        "smoke_pass": True,
        "confirmatory_claim_authorized": False,
        "clean_efficacy_estimated": False,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": evidence["protocol_id"],
        },
        "result": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "sha256": {
                relative: file_sha256(RESULT_ROOT / relative)
                for relative in (
                    "SHA256SUMS",
                    "run_manifest.json",
                    "smoke_evidence.json",
                )
            },
            "episode_path": episode_relative,
            "episode_sha256": file_sha256(
                REPO_ROOT / episode_relative
            ),
            "observed": observed,
            "gate_results": evidence["gate_results"],
        },
        "interpretation": {
            "old_sixth_block_effect_rejection_crossed": True,
            "eight_h10_transactions_complete": True,
            "holding_observed_on_final_transaction": True,
            "closed_loop_move_transition_observed": False,
            "paper_statement": (
                "On the exact clean pair where v2 rejected its sixth "
                "pick-up block for missing holding_target, the versioned v3 "
                "runner completed eight H10 transactions with 80 bound "
                "receipts, eight effect allows, zero effect rejects, zero "
                "selected hard violations, and no unsafe cost or collision. "
                "Seven allowed prefixes made progress or ended near the "
                "target without claiming holding; the eighth observed a "
                "trusted held state."
            ),
        },
        "lifecycle": {
            "terminal": True,
            "same_root_retry_authorized": False,
            "regression_smoke_rerun_authorized": False,
            "phase_transition_protocol_freeze_authorized": True,
            "phase_transition_execution_automatically_authorized": False,
            "fresh_clean_efficacy_screen_authorized": False,
            "attacked_execution_authorized": False,
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "generator": SELF_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "generator_sha256": file_sha256(SELF_PATH),
        },
        "claim_boundary": (
            "This freezes an outcome-conditioned regression pass on one "
            "reused clean pair. It validates the repaired block/effect "
            "contract path but not clean efficacy, attacked defense, "
            "deployment performance, hardware safety, or a confirmatory "
            "effect."
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
        build_terminal(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise HorizonPickUpSmokeTerminalError(
                f"regression terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
