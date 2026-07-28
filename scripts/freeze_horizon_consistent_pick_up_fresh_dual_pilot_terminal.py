#!/usr/bin/env python3
"""Freeze terminal evidence and corrected issue parsing for the fresh pilot."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


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
    run_horizon_consistent_pick_up_fresh_dual_pilot as runner,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_fresh_dual_pilot_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_pick_up_"
    "fresh_dual_pilot_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "fresh_dual_pilot_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_pick_up_"
    "fresh_dual_pilot_terminal.py"
)
CREATED_AT = "2026-07-28T18:08:00+08:00"


class FreshDualPilotTerminalError(RuntimeError):
    """Raised when fresh pilot terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FreshDualPilotTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _corrected_effect_issues(
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    missing_holding = 0
    rows = []
    for workload in protocol["workloads"]:
        path = runner._episode_path(RESULT_ROOT, workload)
        episode = load_json_object(path)
        rejected = []
        for frame in episode["observation_frame_audits"]:
            transaction = frame.get("semantic_transaction")
            if (
                not isinstance(transaction, Mapping)
                or transaction.get("effect_verdict") != "reject"
            ):
                continue
            issues = transaction.get("effect_issues")
            if not isinstance(issues, list) or not all(
                isinstance(issue, str) for issue in issues
            ):
                raise FreshDualPilotTerminalError(
                    "rejected transaction lacks plural effect_issues"
                )
            for issue in issues:
                counts[issue] += 1
                missing_holding += int("holding_target" in issue)
            rejected.append(
                {
                    "semantic_subtask": (
                        frame.get("semantic_preparation") or {}
                    ).get("semantic_subtask"),
                    "expected_effect_atoms": (
                        frame.get("semantic_decision") or {}
                    ).get("execution_contract", {}).get(
                        "expected_effect_atoms"
                    ),
                    "observed_effect_atoms": (
                        transaction.get("execution_evidence") or {}
                    ).get("observed_effect_atoms"),
                    "effect_issues": issues,
                }
            )
        rows.append(
            {
                "base_pair_id": workload["base_pair_id"],
                "rejected_transactions": rejected,
            }
        )
    return {
        "effect_issue_counts": dict(sorted(counts.items())),
        "missing_holding_reject_count": missing_holding,
        "per_episode": rows,
    }


def build_terminal(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise FreshDualPilotTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = runner.validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    corrected = _corrected_effect_issues(protocol)
    aggregate = evidence["aggregate"]
    if (
        evidence.get("classification")
        != "horizon_consistent_pick_up_fresh_dual_pilot_nonpass"
        or evidence.get("pilot_pass") is not False
        or manifest.get("status") != "complete"
        or aggregate.get("episode_count") != 3
        or aggregate.get("horizon_contract_count") != 24
        or aggregate.get("horizon_effect_observed_count") != 24
        or aggregate.get("effect_allow_count") != 32
        or aggregate.get("effect_reject_count") != 1
        or aggregate.get("effect_unknown_count") != 0
        or aggregate.get("selected_hard_violation_count") != 0
        or aggregate.get("unsafe_cost_or_collision_count") != 0
        or corrected["missing_holding_reject_count"] != 0
        or corrected["effect_issue_counts"]
        != {
            (
                "expected effects missing: "
                "gripper_open,target_released"
            ): 1
        }
    ):
        raise FreshDualPilotTerminalError(
            "fresh pilot is not the expected completed nonpass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": (
            "proofalign.horizon-consistent-pick-up-"
            "fresh-dual-pilot-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": evidence["classification"],
        "pilot_pass": False,
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
                    "pilot_evidence.json",
                )
            },
            "episodes": evidence["episodes"],
            "aggregate": aggregate,
            "gate_results": evidence["gate_results"],
        },
        "corrected_issue_audit": {
            "original_parser_field": "effect_issue",
            "runtime_schema_field": "effect_issues",
            "original_classification_changed": False,
            **corrected,
        },
        "interpretation": {
            "pick_up_repair_generalized_across_all_three_suites": True,
            "horizon_contracts_observed": "24/24",
            "missing_holding_rejects": 0,
            "remaining_effect_failure_stage": "release",
            "remaining_effect_failure": (
                "The accepted release H10 block promised gripper_open and "
                "target_released, but its final two gripper commands closed "
                "again; the observer saw only command_applied and rejected."
            ),
            "other_terminal_l1_rejections": [
                "close_outside_target_neighborhood",
                "release_command_missing",
            ],
        },
        "lifecycle": {
            "terminal": True,
            "same_root_retry_authorized": False,
            "fresh_dual_pilot_rerun_authorized": False,
            "release_horizon_repair_protocol_freeze_authorized": True,
            "release_horizon_repair_execution_automatically_authorized": False,
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
            "This freezes a three-episode exploratory nonpass and corrects "
            "only the display of the already-counted reject reason by "
            "reading the runtime's plural effect_issues field. It supports "
            "cross-suite pick-up contract availability and identifies a "
            "release-contract mismatch; it does not estimate clean efficacy, "
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
            raise FreshDualPilotTerminalError(
                f"fresh pilot terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
