#!/usr/bin/env python3
"""Freeze the H10×K4 qualification and matched candidate-count ablation."""

from __future__ import annotations

import argparse
from collections import Counter
import json
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
from scripts import run_four_arm_v4_l1_block10_k4_qualification as runner  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_k4_qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_block10_k4_qualification_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_block10_k4_terminal.py"
)
CREATED_AT = "2026-07-28T12:30:00+08:00"


class Block10K4TerminalError(RuntimeError):
    """Raised when H10×K4 terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Block10K4TerminalError(
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
                raise Block10K4TerminalError(
                    "H10×K4 ledger row is not an object"
                )
            values.append(value)
    return values


def _candidate_ablation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = (1, 2, 4)

    def eligible(row: dict[str, Any], count: int) -> bool:
        return bool(
            row["candidate_selection"][
                "matched_candidate_count_shadow"
            ]["cumulative"][str(count)]["at_least_one_eligible"]
        )

    by_count = {}
    for count in counts:
        total = sum(eligible(row, count) for row in rows)
        suites = {}
        for suite in sorted({row["suite"] for row in rows}):
            suite_rows = [
                row for row in rows if row["suite"] == suite
            ]
            suite_total = sum(
                eligible(row, count) for row in suite_rows
            )
            suites[suite] = {
                "eligible": suite_total,
                "total": len(suite_rows),
                "eligible_rate": suite_total / len(suite_rows),
            }
        by_count[str(count)] = {
            "eligible": total,
            "total": len(rows),
            "eligible_rate": total / len(rows),
            "suite_rates": suites,
        }
    patterns = Counter(
        "".join(
            "1" if eligible(row, count) else "0"
            for count in counts
        )
        for row in rows
    )
    return {
        "schema": (
            "proofalign.four-arm-v4-matched-h10-candidate-count-"
            "ablation.v1"
        ),
        "action_block_steps": 10,
        "paired_unit": "task/init/ordered-source-candidates",
        "task_outcomes_observed": False,
        "by_candidate_count": by_count,
        "eligibility_pattern_k1_k2_k4_counts": dict(
            sorted(patterns.items())
        ),
        "k4_incremental_eligible_rows_over_k1": (
            by_count["4"]["eligible"] - by_count["1"]["eligible"]
        ),
        "four_unique_source_chunk_hashes_per_row_count": sum(
            len(
                {
                    candidate["source_policy_chunk_sha256"]
                    for candidate in row["candidate_selection"][
                        "candidates"
                    ]
                }
            )
            == 4
            for row in rows
        ),
        "interpretation_boundary": (
            "This matched no-outcome ablation measures initial checker "
            "availability only. It does not measure trajectory success, "
            "attack defense, safety, or confirmatory efficacy."
        ),
    }


def build_terminal_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise Block10K4TerminalError(
            "tracked worktree must be clean before H10×K4 terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    runner._install_runtime()
    summary = runner.base.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    rows = _rows()
    if (
        summary["classification"]
        != "l1_block10_k4_initial_availability_qualification_nonpass"
        or summary["qualification_pass"] is not False
        or len(rows) != 45
        or manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
    ):
        raise Block10K4TerminalError(
            "H10×K4 result is not the completed 45-row nonpass"
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
    ablation = _candidate_ablation(rows)
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-block10-k4-terminal-summary.v1"
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
        "matched_candidate_count_ablation": ablation,
        "interpretation": {
            "h10_k4_qualified": False,
            "geometry_qualified": True,
            "selected_hard_violation_count": 0,
            "threshold_relaxed": False,
            "blind_resampling_materially_improved_coverage": False,
            "paper_statement": (
                "On the third frozen disjoint-init successor split, H10 "
                "coverage was 35/45 at K=1 and 36/45 at K=4 despite four "
                "unique source chunks per row. Blind stochastic resampling "
                "therefore added only one initial state and did not pass "
                "the overall or worst-suite gates."
            ),
        },
        "lifecycle": {
            "all_parent_nonpasses_unchanged": True,
            "h10_k4_terminal": True,
            "same_population_retry_authorized": False,
            "additional_blind_horizon_or_candidate_search_authorized": False,
            "clean_execution_authorized": False,
            "attacked_execution_authorized": False,
            "next_method_boundary": (
                "Further progress requires a materially different action "
                "generator, trained semantic conditioning, or feedback-aware "
                "policy interface; it cannot be claimed from longer stale "
                "open-loop concatenation or more IID source samples."
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
            "This freezes a third post-outcome, no-task-outcome, "
            "zero-dispatch qualification nonpass and matched candidate-count "
            "availability ablation. It establishes no clean trajectory "
            "retention, attack-defense efficacy, deployment perception, "
            "hardware safety, or confirmatory result."
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
            raise Block10K4TerminalError(
                f"H10×K4 terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
