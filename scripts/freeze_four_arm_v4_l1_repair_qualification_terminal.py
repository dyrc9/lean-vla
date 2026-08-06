#!/usr/bin/env python3
"""Freeze the completed L1 repair qualification and its diagnostics."""

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
from scripts import run_four_arm_v4_l1_repair_qualification as runner  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_fresh3_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_repair_qualification_20260728_fresh3"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_repair_qualification_terminal.py"
)
CREATED_AT = "2026-07-28T13:15:00+08:00"


class QualificationTerminalError(RuntimeError):
    """Raised when terminal qualification evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise QualificationTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _rows() -> list[dict[str, Any]]:
    path = RESULT_ROOT / "qualification_ledger.jsonl"
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise QualificationTerminalError(
                    "qualification ledger row is not an object"
                )
            values.append(value)
    return values


def _candidate_eligible(candidate: dict[str, Any]) -> bool:
    checked = candidate["checked"]
    return bool(
        checked["known"]
        and checked["semantic_compatible"]
        and checked["post_projection_compatible"]
        and not checked["hard_violation_atoms"]
        and checked["progress_margin"] >= 0.002
        and checked["projection_l2"] <= 0.5
    )


def _diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cumulative = {}
    for candidate_count in range(1, 5):
        count = sum(
            any(
                _candidate_eligible(candidate)
                for candidate in row["candidate_selection"]["candidates"][
                    :candidate_count
                ]
            )
            for row in rows
        )
        cumulative[str(candidate_count)] = {
            "eligible_row_count": count,
            "eligible_row_rate": count / len(rows),
        }
    failed = [
        row for row in rows if not row["eligible_candidate_selected"]
    ]
    failed_max_progress = [
        max(
            candidate["checked"]["progress_margin"]
            for candidate in row["candidate_selection"]["candidates"]
        )
        for row in failed
    ]
    all_candidates = [
        candidate
        for row in rows
        for candidate in row["candidate_selection"]["candidates"]
    ]
    geometry_sources: Counter[str] = Counter()
    for row in rows:
        for source, count in row["geometry_audit"][
            "source_counts"
        ].items():
            geometry_sources[source.rsplit(":", 1)[-1]] += int(count)
    failed_destinations = Counter(
        row["geometry_audit"]["required_entity_ids"][0]
        for row in failed
    )
    selected_indices = Counter(
        (
            "none"
            if row["candidate_selection"][
                "eligible_selected_source_candidate_index"
            ]
            is None
            else str(
                row["candidate_selection"][
                    "eligible_selected_source_candidate_index"
                ]
            )
        )
        for row in rows
    )
    return {
        "candidate_row_count": len(rows),
        "candidate_total_count": len(all_candidates),
        "four_unique_chunk_hashes_per_row_count": sum(
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
        "cumulative_availability_by_k": cumulative,
        "k4_incremental_eligible_rows_over_k1": (
            cumulative["4"]["eligible_row_count"]
            - cumulative["1"]["eligible_row_count"]
        ),
        "semantic_compatible_candidate_count": sum(
            candidate["checked"]["semantic_compatible"]
            for candidate in all_candidates
        ),
        "hard_violation_candidate_count": sum(
            bool(candidate["checked"]["hard_violation_atoms"])
            for candidate in all_candidates
        ),
        "selected_source_candidate_index_counts": dict(
            sorted(selected_indices.items())
        ),
        "geometry_source_counts": dict(sorted(geometry_sources.items())),
        "failed_row_count": len(failed),
        "failed_row_best_progress_m": {
            "min": min(failed_max_progress),
            "median": statistics.median(failed_max_progress),
            "max": max(failed_max_progress),
            "frozen_min_progress_m": 0.002,
            "at_or_above_frozen_min_count": sum(
                value >= 0.002 for value in failed_max_progress
            ),
        },
        "failed_destination_counts": dict(
            sorted(failed_destinations.items())
        ),
    }


def build_terminal_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise QualificationTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    summary = runner.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    rows = _rows()
    if (
        summary["classification"]
        != "l1_repair_initial_availability_qualification_nonpass"
        or summary["qualification_pass"] is not False
        or len(rows) != 45
        or manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
    ):
        raise QualificationTerminalError(
            "qualification is not the completed 45-row nonpass"
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
        path = RESULT_ROOT / name
        result_bindings[name] = file_sha256(path)
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-repair-qualification-terminal.v1"
        ),
        "created_at": created_at,
        "classification": summary["classification"],
        "qualification_pass": False,
        "confirmatory_claim_authorized": False,
        "post_outcome_repair": True,
        "parent_support45_result_unchanged": True,
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
        "diagnostics": _diagnostics(rows),
        "interpretation": {
            "privileged_geometry_repair_qualified": True,
            "k4_candidate_availability_qualified": False,
            "k4_improved_population_coverage_over_k1": False,
            "threshold_relaxation_permitted": False,
            "clean_rollout_authorized": False,
            "attacked_rollout_authorized": False,
            "paper_statement": (
                "The post-outcome oracle-geometry repair closed the initial "
                "destination-geometry gap, but four distinct sequential "
                "policy samples did not expand initial feasible-state "
                "coverage beyond K=1. The current public policy/checker "
                "composition therefore remains fail-closed and unavailable "
                "for a new clean efficacy stage."
            ),
        },
        "lifecycle": {
            "fresh1_and_fresh2_zero_row_failures_remain_sealed": True,
            "fresh3_terminal": True,
            "same_population_retry_authorized": False,
            "additional_clean_execution_authorized": False,
            "attacked_execution_authorized": False,
            "future_redesign_requirement": (
                "A materially new L1 mechanism must be labeled post-outcome "
                "exploratory, preserve the 2 mm checker threshold and the "
                "original support45 nonpass, and use a newly frozen "
                "qualification population/seed before any efficacy rollout."
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
            "This is a post-outcome, no-task-outcome, zero-dispatch "
            "qualification nonpass. It does not overwrite the original "
            "support45 clean nonpass and establishes neither trajectory-level "
            "clean retention, attack-defense efficacy, deployment perception, "
            "hardware safety, nor a confirmatory result."
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
            raise QualificationTerminalError(
                f"terminal summary is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
