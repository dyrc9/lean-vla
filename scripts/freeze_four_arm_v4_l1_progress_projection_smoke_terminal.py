#!/usr/bin/env python3
"""Freeze terminal evidence for the progress-projection closed-loop smoke."""

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
    validate_four_arm_v4_l1_progress_projection_smoke_v2 as validator,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_smoke_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "smoke_20260728_fresh1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "smoke_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_progress_projection_smoke_terminal.py"
)
EPISODE_RELATIVE = (
    "dual_task0_init23/episodes/"
    "obstacle_avoidance_task0_init23.json"
)
CREATED_AT = "2026-07-28T17:30:00+08:00"


class ProgressProjectionSmokeTerminalError(RuntimeError):
    """Raised when smoke terminal evidence is inconsistent."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ProgressProjectionSmokeTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_terminal(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ProgressProjectionSmokeTerminalError(
            "tracked worktree must be clean before smoke terminal freeze"
        )
    validation = validator.validate(protocol_path=PROTOCOL_PATH)
    evidence = load_json_object(RESULT_ROOT / "smoke_evidence.json")
    manifest = load_json_object(RESULT_ROOT / "run_manifest.json")
    if (
        validation.get("classification")
        != "l1_progress_projection_closed_loop_smoke_pass"
        or validation.get("smoke_pass") is not True
        or validation.get("normalized_recomputation_matches") is not True
        or validation.get("checksums_valid") is not True
        or manifest.get("status") != "complete"
        or evidence.get("smoke_pass") is not True
        or any(
            value is not True
            for value in evidence["gate_results"].values()
        )
    ):
        raise ProgressProjectionSmokeTerminalError(
            "smoke is not the completed normalized-validation pass"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    result_sha256 = {
        relative: file_sha256(RESULT_ROOT / relative)
        for relative in (
            "SHA256SUMS",
            "run_manifest.json",
            "smoke_evidence.json",
            EPISODE_RELATIVE,
        )
    }
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-progress-projection-"
            "smoke-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": evidence["classification"],
        "smoke_pass": True,
        "confirmatory_claim_authorized": False,
        "clean_efficacy_estimated": False,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": evidence["protocol_id"],
        },
        "result": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "sha256": result_sha256,
            "observed": evidence["observed"],
            "gate_results": evidence["gate_results"],
        },
        "validation": {
            "schema": validation["schema"],
            "validator": (
                "scripts/"
                "validate_four_arm_v4_l1_progress_projection_smoke_v2.py"
            ),
            "validator_sha256": file_sha256(
                REPO_ROOT
                / "scripts"
                / "validate_four_arm_v4_l1_progress_projection_smoke_v2.py"
            ),
            "checksums_valid": True,
            "normalized_recomputation_matches": True,
            "frozen_v1_validation_issue": (
                "The retained deterministic release audit encoded tuples as "
                "JSON arrays, while the in-memory recomputation retained "
                "tuples. V2 normalizes the recomputation through JSON before "
                "exact comparison; no protocol, episode, evidence, checksum, "
                "gate, or outcome was changed."
            ),
        },
        "interpretation": {
            "online_policy_checker_contract_path_qualified": True,
            "dispatch_receipt_effect_path_qualified": True,
            "release_branch_gate_qualified": True,
            "task_success_required": False,
            "paper_statement": (
                "The clean dual-arm engineering smoke completed two H10 "
                "semantic transactions with 20 bound dispatch receipts, two "
                "allow effect verdicts, zero effect rejects, zero selected "
                "hard violations, and no unsafe cost or collision."
            ),
        },
        "lifecycle": {
            "terminal": True,
            "same_root_retry_authorized": False,
            "smoke_rerun_authorized": False,
            "clean_screening_protocol_freeze_authorized": True,
            "clean_screening_execution_automatically_authorized": False,
            "clean_completion_authorized": False,
            "attacked_execution_authorized": False,
            "next_gate": (
                "Freeze a separate fresh fifth-init four-arm protocol that "
                "authorizes only the 60-episode clean screening stage."
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
            "This freezes one engineering smoke pass. It validates online "
            "wiring but does not estimate clean task efficacy, attacked "
            "defense, deployment perception, hardware safety, or a "
            "confirmatory effect."
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
            raise ProgressProjectionSmokeTerminalError(
                f"smoke terminal is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
