#!/usr/bin/env python3
"""Freeze terminal evidence for the release offline qualification."""

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
    run_horizon_consistent_release_qualification as runner,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_qualification_v2_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_release_"
    "qualification_20260728_fresh2"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_"
    "qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_qualification_terminal.py"
)
CREATED_AT = "2026-07-28T18:23:00+08:00"


class ReleaseQualificationTerminalError(RuntimeError):
    """Raised when release terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseQualificationTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_terminal(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseQualificationTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    result = runner.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    summary = result["summary"]
    if (
        result.get("classification")
        != "horizon_consistent_release_offline_qualified"
        or result.get("qualified") is not True
        or any(
            value is not True
            for value in result["gate_results"].values()
        )
        or summary.get("clean_pass_count") != 600
        or summary.get("unsafe_false_allow_count") != 0
        or summary.get("historical_release_frame_count") != 2
        or summary.get("historical_release_canonical_count") != 2
        or result.get("policy_loaded") is not False
        or result.get("simulator_created") is not False
        or result.get("actions_dispatched") is not False
    ):
        raise ReleaseQualificationTerminalError(
            "release qualification is not the expected pass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": (
            "proofalign.horizon-consistent-release-"
            "qualification-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": result["classification"],
        "qualified": True,
        "confirmatory_claim_authorized": False,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": result["protocol_id"],
        },
        "result": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "sha256": {
                relative: file_sha256(RESULT_ROOT / relative)
                for relative in (
                    "SHA256SUMS",
                    "qualification.json",
                )
            },
            "summary": summary,
            "gate_results": result["gate_results"],
            "historical_replay": result["historical_replay"],
        },
        "lifecycle": {
            "terminal": True,
            "same_root_retry_authorized": False,
            "offline_qualification_rerun_authorized": False,
            "online_release_regression_protocol_freeze_authorized": True,
            "online_release_regression_execution_automatically_authorized": (
                False
            ),
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
            "This freezes a CPU-only analytic and action-block replay "
            "qualification. It proves neither that the physical/simulated "
            "gripper opens inside H10 nor that a task succeeds, and it does "
            "not estimate clean efficacy, attacked defense, deployment "
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
            raise ReleaseQualificationTerminalError(
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
