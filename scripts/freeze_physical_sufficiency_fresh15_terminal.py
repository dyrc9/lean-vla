#!/usr/bin/env python3
"""Freeze the terminal interpretation of the v10 fresh15 clean pilot."""

from __future__ import annotations

import argparse
from collections import Counter
from math import comb, sqrt
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
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_fresh15_cotenant_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_physical_sufficiency_fresh15_"
    "cotenant_20260729_fresh1"
)
RESULT_PATH = RESULT_ROOT / "pilot_evidence.json"
CHECKSUMS_PATH = RESULT_ROOT / "SHA256SUMS"
V9_RESULT_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_risk_selective_fresh15_cotenant_"
    "20260729_fresh1"
    / "pilot_evidence.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_fresh15_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_physical_sufficiency_fresh15_terminal.py"
)
SOURCE_PATHS = (
    "scripts/freeze_physical_sufficiency_fresh15_terminal.py",
    "tests/test_physical_sufficiency_fresh15_terminal.py",
)
CREATED_AT = "2026-07-29T19:00:00+08:00"
Z95 = 1.959963984540054


class PhysicalSufficiencyTerminalError(RuntimeError):
    """Raised when the v10 terminal evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PhysicalSufficiencyTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _wilson(successes: int, total: int) -> list[float]:
    rate = successes / total
    denominator = 1.0 + Z95 * Z95 / total
    center = (
        rate + Z95 * Z95 / (2.0 * total)
    ) / denominator
    half = (
        Z95
        * sqrt(
            rate * (1.0 - rate) / total
            + Z95 * Z95 / (4.0 * total * total)
        )
        / denominator
    )
    return [center - half, center + half]


def _paired_comparison(
    rows: dict[str, dict[str, bool]],
    treatment: str,
    control: str,
) -> dict[str, Any]:
    patterns = Counter(
        (
            int(values[treatment]),
            int(values[control]),
        )
        for values in rows.values()
    )
    treatment_only = patterns[(1, 0)]
    control_only = patterns[(0, 1)]
    discordant = treatment_only + control_only
    tail = (
        1.0
        if discordant == 0
        else min(
            1.0,
            2.0
            * sum(
                comb(discordant, index)
                for index in range(
                    min(treatment_only, control_only) + 1
                )
            )
            / (2**discordant),
        )
    )
    treatment_success = sum(
        values[treatment] for values in rows.values()
    )
    control_success = sum(
        values[control] for values in rows.values()
    )
    return {
        "treatment": treatment,
        "control": control,
        "pair_count": len(rows),
        "both_success": patterns[(1, 1)],
        "treatment_only_success": treatment_only,
        "control_only_success": control_only,
        "both_fail": patterns[(0, 0)],
        "risk_difference": (
            treatment_success - control_success
        )
        / len(rows),
        "two_sided_exact_mcnemar_p": tail,
    }


def build_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    result = load_json_object(RESULT_PATH)
    protocol = load_json_object(PROTOCOL_PATH)
    if (
        result.get("classification")
        != "physical_sufficiency_fresh15_clean_data_complete"
        or result.get("pilot_complete") is not True
        or result.get("aggregate", {}).get("episode_count") != 60
    ):
        raise PhysicalSufficiencyTerminalError(
            "v10 fresh15 evidence is not complete"
        )
    p0b.read_checksums(RESULT_ROOT)
    rows: dict[str, dict[str, bool]] = {}
    for row in result["per_episode"]:
        rows.setdefault(row["base_pair_id"], {})[row["arm"]] = bool(
            row["task_success"]
        )
    if len(rows) != 15 or any(len(values) != 4 for values in rows.values()):
        raise PhysicalSufficiencyTerminalError(
            "v10 paired result is incomplete"
        )
    success_table = {}
    for arm, values in result["by_arm"].items():
        successes = int(values["task_success_count"])
        total = int(values["episode_count"])
        success_table[arm] = {
            "successes": successes,
            "total": total,
            "rate": successes / total,
            "wilson_95": _wilson(successes, total),
        }
    suite_table = {}
    for suite in (
        "human_safety",
        "obstacle_avoidance",
        "obstacle_avoidance_human",
    ):
        suite_table[suite] = {
            arm: sum(
                bool(row["task_success"])
                for row in result["per_episode"]
                if row["suite"] == suite and row["arm"] == arm
            )
            for arm in result["by_arm"]
        }
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": (
            "proofalign.physical-sufficiency-fresh15-terminal.v1"
        ),
        "classification": (
            "physical_sufficiency_fresh15_data_complete"
        ),
        "created_at": created_at,
        "terminal": True,
        "data_complete": True,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "result": {
            "path": RESULT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(RESULT_PATH),
            "checksums_path": CHECKSUMS_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "checksums_sha256": file_sha256(CHECKSUMS_PATH),
        },
        "predecessor_v9_result": {
            "path": V9_RESULT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(V9_RESULT_PATH),
        },
        "success_table": success_table,
        "success_table_by_suite": suite_table,
        "paired_comparisons": {
            "semantic_vs_vla": _paired_comparison(
                rows, "semantic_only", "vla_only"
            ),
            "dual_vs_execution": _paired_comparison(
                rows, "dual", "execution_only"
            ),
            "dual_vs_vla": _paired_comparison(
                rows, "dual", "vla_only"
            ),
        },
        "mechanism": {
            key: result["aggregate"][key]
            for key in (
                "physical_sufficiency_audit_count",
                "unchanged_source_action_block_count",
                "paired_first_action_block_match_count",
                "physical_screened_semantic_unknown_count",
                "physical_risk_reject_count",
                "advisory_effect_replan_count",
                "effect_reject_count",
                "effect_unknown_count",
                "unsafe_cost_or_collision_count",
            )
        },
        "interpretation": {
            "nominal_policy_noninterference_observed": True,
            "clean_noninferiority_declared": False,
            "attacked_defense_evaluated": False,
            "confirmatory_claim_authorized": False,
            "causal_safety_claim_authorized": False,
            "next_primary_question": (
                "whether attacked physical-risk enrichment offsets the "
                "observed clean physical-gate utility cost"
            ),
        },
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
            "This terminal freezes a complete 60-episode clean exploratory "
            "v10 table. It supports nominal-policy non-interference and "
            "failure-partition claims, but not clean non-inferiority, "
            "attacked defense, confirmatory efficacy, causal safety, timing, "
            "deployment, or hardware generalization."
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
        source_commit = retained["source"]["repository_commit"]
    text = canonical_text(
        build_summary(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PhysicalSufficiencyTerminalError(
                f"v10 terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
