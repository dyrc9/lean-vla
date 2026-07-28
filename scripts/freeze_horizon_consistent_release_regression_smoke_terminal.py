#!/usr/bin/env python3
"""Freeze the v5 release regression terminal-censoring nonpass."""

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
    run_horizon_consistent_release_regression_smoke as runner,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_regression_smoke_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_release_"
    "regression_smoke_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_"
    "regression_smoke_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_"
    "regression_smoke_terminal.py"
)
CREATED_AT = "2026-07-28T18:33:00+08:00"


class ReleaseRegressionTerminalError(RuntimeError):
    """Raised when the v5 regression terminal is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseRegressionTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_terminal(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseRegressionTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = runner.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    row = evidence["release_rows"][0]
    observed = evidence["observed"]
    episode = load_json_object(REPO_ROOT / evidence["episode"]["path"])
    release_frame = next(
        frame
        for frame in episode["observation_frame_audits"]
        if str(
            (frame.get("semantic_preparation") or {}).get(
                "semantic_subtask", ""
            )
        ).startswith("release(")
    )
    receipt_count = len(
        release_frame["semantic_transaction"]["step_receipts"]
    )
    if (
        evidence.get("classification")
        != "horizon_consistent_release_regression_smoke_nonpass"
        or evidence.get("smoke_pass") is not False
        or observed.get("task_success") is not True
        or observed.get("decision") != "env_done"
        or observed.get("release_canonicalization_count") != 1
        or row.get("canonical_open_command_count") != 10
        or row.get("dispatch_status") != "incomplete"
        or row.get("effect_issues")
        != ["authorized prefix was not completely consumed"]
        or receipt_count != 4
        or observed.get("selected_hard_violation_count") != 0
        or observed.get("unsafe_cost_or_collision") is not False
    ):
        raise ReleaseRegressionTerminalError(
            "v5 release regression is not the expected terminal nonpass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": (
            "proofalign.horizon-consistent-release-"
            "regression-smoke-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": evidence["classification"],
        "smoke_pass": False,
        "task_success_observed": True,
        "confirmatory_claim_authorized": False,
        "clean_efficacy_estimated": False,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
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
            "episode": evidence["episode"],
            "observed": observed,
            "gate_results": evidence["gate_results"],
            "release_row": row,
            "release_receipt_count": receipt_count,
        },
        "interpretation": {
            "release_canonicalization_reached_online_execution": True,
            "benchmark_task_succeeded": True,
            "h10_effect_transaction_completed": False,
            "failure_class": "terminal_success_censoring",
            "reward_used_as_defense_evidence": False,
            "next_repair": (
                "Use a verb-specific H4 release micro-block, matching the "
                "four observed receipts before terminal success, while "
                "retaining H10 for spatial motion. Recheck the exact H4 "
                "block and do not treat benchmark reward as an effect atom."
            ),
        },
        "lifecycle": {
            "terminal": True,
            "same_root_retry_authorized": False,
            "v5_regression_rerun_authorized": False,
            "h4_release_regression_protocol_freeze_authorized": True,
            "h4_release_regression_execution_automatically_authorized": False,
            "full_clean_efficacy_screen_authorized": False,
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
            "This freezes an outcome-conditioned nonpass in which the "
            "benchmark terminated successfully after four of ten authorized "
            "release steps. The task reward is recorded but not used as "
            "semantic effect evidence. This does not estimate clean efficacy, "
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
            raise ReleaseRegressionTerminalError(
                f"release terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
