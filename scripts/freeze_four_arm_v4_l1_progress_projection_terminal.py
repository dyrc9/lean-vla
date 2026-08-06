#!/usr/bin/env python3
"""Freeze terminal evidence for the bounded progress-projection qualification."""

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
from scripts import (  # noqa: E402
    run_four_arm_v4_l1_progress_projection_qualification as runner,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_progress_projection_terminal.py"
)
CREATED_AT = "2026-07-28T16:00:00+08:00"


class ProgressProjectionTerminalError(RuntimeError):
    """Raised when terminal progress-projection evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ProgressProjectionTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = RESULT_ROOT / "qualification_ledger.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ProgressProjectionTerminalError(
                "progress-projection ledger row is not an object"
            )
        rows.append(row)
    return rows


def _repair_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    semantic_repairs = []
    projection_l2_values = []
    for row in rows:
        candidate = row["candidate_selection"]["candidates"][0]
        projection = candidate["progress_projection"]
        projection_l2_values.append(float(projection["projection_l2"]))
        if projection["reason"] != "minimum_l2_terminal_progress_projection":
            continue
        semantic_repairs.append(
            {
                "base_pair_id": row["base_pair_id"],
                "suite": row["suite"],
                "trusted_subtask": projection["semantic_subtask"],
                "nominal_terminal_progress_m": projection[
                    "nominal_terminal_progress_m"
                ],
                "projected_terminal_progress_m": projection[
                    "final_terminal_progress_m"
                ],
                "projection_l2": projection["projection_l2"],
                "nominal_hard_violations": candidate[
                    "nominal_checked"
                ][
                    "hard_violation_atoms"
                ],
                "projected_hard_violations": candidate[
                    "checked"
                ][
                    "hard_violation_atoms"
                ],
            }
        )
    return {
        "schema": "proofalign.progress-projection-repair-audit.v1",
        "row_count": len(rows),
        "projection_reason_counts": dict(
            sorted(
                Counter(
                    row["candidate_selection"]["candidates"][0][
                        "progress_projection"
                    ]["reason"]
                    for row in rows
                ).items()
            )
        ),
        "semantic_repair_count": len(semantic_repairs),
        "semantic_repairs": semantic_repairs,
        "projection_l2": {
            "minimum": min(projection_l2_values),
            "maximum": max(projection_l2_values),
            "mean": sum(projection_l2_values) / len(projection_l2_values),
        },
        "nominal_hard_violation_row_count": sum(
            bool(
                row["candidate_selection"]["candidates"][0][
                    "nominal_checked"
                ]["hard_violation_atoms"]
            )
            for row in rows
        ),
        "projected_hard_violation_row_count": sum(
            bool(
                row["candidate_selection"]["candidates"][0][
                    "checked"
                ]["hard_violation_atoms"]
            )
            for row in rows
        ),
    }


def build_terminal_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ProgressProjectionTerminalError(
            "tracked worktree must be clean before terminal freeze"
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
        summary.get("classification")
        != "l1_progress_projection_initial_availability_qualification_pass"
        or summary.get("qualification_pass") is not True
        or summary.get("valid_row_count") != 45
        or summary.get("eligible_candidate_count") != 45
        or summary.get("selected_hard_violation_count") != 0
        or summary.get("dispatch_count") != 0
        or summary.get("task_outcome_count") != 0
        or manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
        or len(rows) != 45
    ):
        raise ProgressProjectionTerminalError(
            "result is not the completed 45/45 no-outcome qualification pass"
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
            "proofalign.four-arm-v4-l1-progress-projection-"
            "terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": summary["classification"],
        "qualification_pass": True,
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
        "repair_audit": _repair_audit(rows),
        "interpretation": {
            "initial_availability_qualified": True,
            "clean_closed_loop_qualified": False,
            "attacked_execution_qualified": False,
            "geometry_qualified": True,
            "threshold_relaxed": False,
            "semantic_subtask_relabeling_used": False,
            "hard_violation_repair_used": False,
            "paper_statement": (
                "On the fourth frozen disjoint-init no-outcome split, one "
                "H10 pi0.5 source block plus a fixed-Z, translation-only, "
                "bounded minimum-L2 terminal-progress projection was locally "
                "eligible in 45/45 initial states with zero hard violations. "
                "Only 4/45 rows required semantic progress correction."
            ),
        },
        "lifecycle": {
            "all_parent_nonpasses_unchanged": True,
            "same_population_retry_authorized": False,
            "qualification_terminal": True,
            "closed_loop_engineering_smoke_authorized": True,
            "clean_efficacy_claim_authorized": False,
            "attacked_execution_authorized": False,
            "next_gate": (
                "Exercise the exact online policy/checker/contract path in "
                "clean closed loop, including release behavior and binding "
                "of dispatch, receipt, and effects. Freeze a fresh clean "
                "efficacy protocol only after that engineering smoke passes."
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
            "This freezes a post-outcome, no-task-outcome, zero-dispatch "
            "initial-availability qualification pass. It does not establish "
            "clean trajectory retention, attack-defense efficacy, deployment "
            "perception, hardware safety, or a confirmatory result."
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
            raise ProgressProjectionTerminalError(
                f"terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
