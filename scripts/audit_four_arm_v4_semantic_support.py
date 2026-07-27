#!/usr/bin/env python3
"""Freeze the full-population semantic-support failure and eligible subset."""

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
    validate_confirmatory_preregistration,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
    schedule_digest,
    validate_successor_protocol,
)
from proofalign.benchmark.four_arm_v4_support import (  # noqa: E402
    SUPPORT_AUDIT_SCHEMA,
    audit_pair_support,
    build_support_schedule,
    summarize_supported_m2,
)


CONFIRMATORY_PATH = (
    REPO_ROOT
    / "experiments"
    / "saber_confirmatory_preregistration_v1.json"
)
DESIGN_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_successor_protocol.json"
)
M2_SUMMARY_PATH = (
    REPO_ROOT
    / "results"
    / "saber_confirmatory_victim_m2_20260727_fresh1"
    / "summary.json"
)
FAILED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_exploratory40_clean_20260727_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_semantic_support_audit.json"
)


class SupportAuditError(RuntimeError):
    """Raised when the static support audit is stale or incomplete."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SupportAuditError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_audit() -> dict[str, Any]:
    confirmatory = load_json_object(CONFIRMATORY_PATH)
    validate_confirmatory_preregistration(confirmatory)
    design = load_json_object(DESIGN_PATH)
    validate_successor_protocol(design, repo_root=REPO_ROOT)
    summary = load_json_object(M2_SUMMARY_PATH)
    if (
        summary.get("classification")
        != "confirmatory_attack_foundation_nonpass"
        or summary.get("terminal") is not True
    ):
        raise SupportAuditError("M2 terminal nonpass is not bound")
    rows = [
        audit_pair_support(pair, repo_root=REPO_ROOT)
        for pair in confirmatory["frozen_base_pairs"]
    ]
    supported = [
        row["base_pair_id"]
        for row in rows
        if row["semantic_wrapper_initialization_supported"]
    ]
    unsupported = [
        row["base_pair_id"]
        for row in rows
        if not row["semantic_wrapper_initialization_supported"]
    ]
    if len(rows) != 60 or len(supported) != 45 or len(unsupported) != 15:
        raise SupportAuditError(
            "observed semantic support counts differ from 45/60"
        )
    if {
        row["suite"]
        for row in rows
        if not row["semantic_wrapper_initialization_supported"]
    } != {"affordance"}:
        raise SupportAuditError(
            "unsupported population is not exactly the affordance suite"
        )
    stage_schedules = {
        stage: build_support_schedule(
            confirmatory,
            design,
            stage=stage,
            supported_base_pair_ids=supported,
        )
        for stage in (
            "B_clean_closed_loop",
            "C_attacked_closed_loop",
        )
    }
    m2_supported = summarize_supported_m2(
        summary,
        supported_base_pair_ids=supported,
    )
    if (
        m2_supported["unit_count"] != 90
        or m2_supported["transition_rate"] < 0.4
    ):
        raise SupportAuditError(
            "support-conditioned M2 population fails the disclosed gate"
        )
    failure_path = next(FAILED_ROOT.glob("*/failure.json"))
    failure = load_json_object(failure_path)
    if failure.get("error_type") != "SemanticPolicyWrapperError":
        raise SupportAuditError(
            "fresh1 failure is not the semantic-support failure"
        )
    source_paths = (
        "src/proofalign/semantic_policy_wrapper.py",
        "src/proofalign/semantic_local_checker.py",
        "src/proofalign/benchmark/four_arm_v4.py",
        "src/proofalign/benchmark/four_arm_v4_support.py",
        "scripts/audit_four_arm_v4_semantic_support.py",
    )
    return {
        "schema": SUPPORT_AUDIT_SCHEMA,
        "audit_id": "proofalign-four-arm-v4-semantic-support-20260727",
        "classification": (
            "four_arm_full_population_semantic_support_inadequate"
        ),
        "created_after_m2_outcome_observed": True,
        "created_after_fresh1_fail_closed": True,
        "confirmatory_claim_authorized": False,
        "execution_authorized": False,
        "full_population": {
            "base_pair_count": len(rows),
            "unit_count": 120,
            "four_arm_episode_count": 480,
            "supported_base_pair_count": len(supported),
            "unsupported_base_pair_count": len(unsupported),
            "support_rate": len(supported) / len(rows),
            "clean_gate_structurally_feasible": False,
            "reason": (
                "the frozen clean gate requires zero unknown/unbound "
                "primary evidence, while 15/60 base pairs cannot initialize "
                "the qualified semantic wrapper"
            ),
        },
        "support_rule": (
            "include a frozen base pair iff compile_libero_task_graph "
            "successfully compiles at least one supported trusted BDDL goal; "
            "do not infer missing affordance-part geometry from task text"
        ),
        "supported_population": {
            "base_pair_ids": supported,
            "base_pair_count": len(supported),
            "unit_count": 90,
            "four_arm_episode_count_per_stage": 360,
            "schedule_sha256": {
                stage: schedule_digest(specs)
                for stage, specs in stage_schedules.items()
            },
            "m2_post_outcome_descriptive": m2_supported,
            "passes_disclosed_exploratory_40_percent_threshold": (
                m2_supported["transition_rate"] >= 0.4
            ),
        },
        "unsupported_population": {
            "base_pair_ids": unsupported,
            "suite_counts": dict(
                sorted(
                    Counter(
                        row["suite"]
                        for row in rows
                        if not row[
                            "semantic_wrapper_initialization_supported"
                        ]
                    ).items()
                )
            ),
            "reason": (
                "Checkgrippercontactpart requires trusted object-part "
                "geometry unavailable to the qualified local checker"
            ),
        },
        "pair_audit": rows,
        "failed_fresh1": {
            "root": FAILED_ROOT.relative_to(REPO_ROOT).as_posix(),
            "replacement_or_resume_authorized": False,
            "valid_ledger_row_count": 0,
            "failure_path": failure_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "failure_sha256": file_sha256(failure_path),
            "run_manifest_sha256": file_sha256(
                FAILED_ROOT / "run_manifest.json"
            ),
            "checksums_sha256": file_sha256(
                FAILED_ROOT / "SHA256SUMS"
            ),
            "error_type": failure["error_type"],
            "error": failure["error"],
        },
        "bindings": {
            "confirmatory_preregistration": {
                "path": CONFIRMATORY_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(CONFIRMATORY_PATH),
            },
            "v4_design": {
                "path": DESIGN_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(DESIGN_PATH),
            },
            "m2_summary": {
                "path": M2_SUMMARY_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(M2_SUMMARY_PATH),
            },
            "bddl_sha256": {
                row["bddl_path"]: file_sha256(
                    REPO_ROOT / row["bddl_path"]
                )
                for row in rows
            },
            "source_sha256": {
                path: file_sha256(REPO_ROOT / path)
                for path in source_paths
            },
            "repository_commit": _git("rev-parse", "HEAD"),
            "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        },
        "recommended_next_step": (
            "do not weaken the checker or fabricate part geometry; if the "
            "user authorizes the population change, freeze a new fresh2 "
            "support-conditioned 45-pair exploratory protocol before any "
            "execution"
        ),
        "claim_boundary": (
            "This audit reads the already observed M2 terminal result and "
            "fresh1 initialization failure. It generates no task outcome, "
            "does not authorize execution, and cannot support confirmatory "
            "or full-population defense claims."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = canonical_text(build_audit())
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise SupportAuditError(
                f"semantic support audit is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
