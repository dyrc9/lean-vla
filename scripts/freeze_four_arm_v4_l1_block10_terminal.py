#!/usr/bin/env python3
"""Freeze the Block-10 qualification nonpass and matched-size ablation."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
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
from scripts import run_four_arm_v4_l1_block10_qualification as runner  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_block10_qualification_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_block10_terminal.py"
)
CREATED_AT = "2026-07-28T11:30:00+08:00"


class Block10TerminalError(RuntimeError):
    """Raised when Block-10 terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Block10TerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _rows() -> list[dict[str, Any]]:
    values = []
    path = RESULT_ROOT / "qualification_ledger.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Block10TerminalError(
                    "Block-10 ledger row is not an object"
                )
            values.append(value)
    return values


def _assessment(row: dict[str, Any], steps: int) -> dict[str, Any]:
    return row["candidate_selection"]["matched_block_size_shadow"][
        "assessments"
    ][str(steps)]


def _eligible(row: dict[str, Any], steps: int) -> bool:
    return bool(
        _assessment(row, steps)["eligible_under_fixed_gate"]
    )


def _matched_ablation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sizes = (2, 5, 10)
    by_size = {}
    for steps in sizes:
        eligible = sum(_eligible(row, steps) for row in rows)
        margins = [
            float(_assessment(row, steps)["progress_margin"])
            for row in rows
        ]
        suites = {}
        for suite in sorted({row["suite"] for row in rows}):
            suite_rows = [
                row for row in rows if row["suite"] == suite
            ]
            count = sum(
                _eligible(row, steps) for row in suite_rows
            )
            suites[suite] = {
                "eligible": count,
                "total": len(suite_rows),
                "eligible_rate": count / len(suite_rows),
            }
        by_size[str(steps)] = {
            "eligible": eligible,
            "total": len(rows),
            "eligible_rate": eligible / len(rows),
            "suite_rates": suites,
            "progress_m": {
                "min": min(margins),
                "median": statistics.median(margins),
                "mean": statistics.mean(margins),
                "max": max(margins),
            },
            "hard_violation_candidate_count": sum(
                bool(
                    _assessment(row, steps)[
                        "hard_violation_atoms"
                    ]
                )
                for row in rows
            ),
        }
    patterns = Counter(
        "".join(
            "1" if _eligible(row, steps) else "0"
            for steps in sizes
        )
        for row in rows
    )
    h5_gain_h2 = sum(
        _eligible(row, 5) and not _eligible(row, 2)
        for row in rows
    )
    h5_loss_h2 = sum(
        _eligible(row, 2) and not _eligible(row, 5)
        for row in rows
    )
    h10_gain_h5 = sum(
        _eligible(row, 10) and not _eligible(row, 5)
        for row in rows
    )
    h10_loss_h5 = sum(
        _eligible(row, 5) and not _eligible(row, 10)
        for row in rows
    )
    return {
        "schema": (
            "proofalign.four-arm-v4-matched-block-size-ablation.v1"
        ),
        "paired_unit": "task/init/source-policy-chunk",
        "task_outcomes_observed": False,
        "primary_gate_steps": 10,
        "shadow_only_steps": [2, 5],
        "fixed_min_progress_m": 0.002,
        "fixed_max_projection_l2": 0.5,
        "by_size": by_size,
        "eligibility_pattern_h2_h5_h10_counts": dict(
            sorted(patterns.items())
        ),
        "paired_changes": {
            "h5_minus_h2": {
                "gains": h5_gain_h2,
                "losses": h5_loss_h2,
                "rate_difference": (
                    by_size["5"]["eligible_rate"]
                    - by_size["2"]["eligible_rate"]
                ),
            },
            "h10_minus_h5": {
                "gains": h10_gain_h5,
                "losses": h10_loss_h5,
                "rate_difference": (
                    by_size["10"]["eligible_rate"]
                    - by_size["5"]["eligible_rate"]
                ),
            },
        },
        "interpretation_boundary": (
            "This matched no-outcome shadow isolates checker availability "
            "across nested prefixes from one source chunk. It is not a "
            "trajectory success, safety, attack efficacy, or confirmatory "
            "block-length result."
        ),
    }


def build_terminal_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise Block10TerminalError(
            "tracked worktree must be clean before Block-10 terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    runner._install_block10_runtime()
    summary = runner.base.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    rows = _rows()
    if (
        summary["classification"]
        != "l1_block10_initial_availability_qualification_nonpass"
        or summary["qualification_pass"] is not False
        or len(rows) != 45
        or manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
    ):
        raise Block10TerminalError(
            "Block-10 result is not the completed 45-row nonpass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    result_bindings = {}
    for name in (
        "SHA256SUMS",
        "qualification_ledger.jsonl",
        "run_manifest.json",
        "summary.json",
    ):
        result_bindings[name] = file_sha256(RESULT_ROOT / name)
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-block10-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": summary["classification"],
        "qualification_pass": False,
        "confirmatory_claim_authorized": False,
        "post_outcome_repair": True,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "result": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "sha256": result_bindings,
            "summary": summary,
        },
        "matched_block_size_ablation": _matched_ablation(rows),
        "interpretation": {
            "longer_block_increased_initial_availability": True,
            "block10_qualified": False,
            "geometry_qualified": True,
            "selected_hard_violation_count": 0,
            "threshold_relaxed": False,
            "paper_statement": (
                "On the frozen disjoint-init successor split, matched "
                "availability increased monotonically from H=2 to H=5 to "
                "H=10, but H=10 reached only 36/45 and the worst suite "
                "reached 11/15, below the frozen 90% and 80% gates."
            ),
        },
        "lifecycle": {
            "parent_block5_k4_nonpass_unchanged": True,
            "block10_terminal": True,
            "same_population_retry_authorized": False,
            "clean_execution_authorized": False,
            "attacked_execution_authorized": False,
            "longer_than_10_source_block_supported": False,
            "reason": (
                "The frozen public policy returns ten actions. Extending "
                "beyond H=10 would require a different policy interface or "
                "stitched future observations and is not this ablation."
            ),
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "generator": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "generator_sha256": file_sha256(SELF_PATH),
        },
        "claim_boundary": (
            "This terminal artifact freezes a post-outcome, no-task-outcome, "
            "zero-dispatch Block-10 qualification nonpass and a matched "
            "nested-prefix availability ablation. It establishes no clean "
            "trajectory retention, attack-defense efficacy, deployment "
            "perception, hardware safety, or confirmatory result."
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
        build_terminal_summary(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise Block10TerminalError(
                f"Block-10 terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
