#!/usr/bin/env python3
"""Freeze authorization for only the 60-episode clean screening stage."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from proofalign.benchmark.four_arm_v4_progress_clean import (  # noqa: E402
    validate_protocol,
)


DRAFT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_clean_draft.json"
)
QUALIFICATION_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)
SMOKE_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "smoke_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "clean_screening_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_progress_projection_clean_screening.py"
)
SOURCE_PATHS = (
    "src/proofalign/benchmark/four_arm_v4.py",
    "src/proofalign/benchmark/four_arm_v4_progress_clean.py",
    "src/proofalign/semantic_progress_projection.py",
    "scripts/run_liberosafety_pi05_openpi_eval.py",
    "scripts/run_l2_execution_attack_eval.py",
    "scripts/run_l2_execution_attack_eval_v2.py",
    "scripts/run_l2_execution_attack_eval_v3.py",
    "scripts/run_four_arm_v4_l1_progress_projection_clean.py",
    "scripts/run_proofalign_four_arm_v4_clean.py",
    "scripts/run_saber_threat_validation_r5.py",
    "scripts/prepare_four_arm_v4_l1_progress_projection_clean.py",
    "scripts/freeze_four_arm_v4_l1_progress_projection_clean_screening.py",
    "tests/test_four_arm_v4_progress_clean.py",
    "tests/test_four_arm_v4_progress_clean_runner.py",
    "tests/test_semantic_online_runner_v3.py",
)
CREATED_AT = "2026-07-28T17:45:00+08:00"
USER_AUTHORIZATION = (
    "2026-07-28 user instruction to continue advancing the experiment "
    "after disclosure that the closed-loop engineering smoke passed."
)


class ProgressCleanScreeningFreezeError(RuntimeError):
    """Raised when screening authorization cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ProgressCleanScreeningFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    user_authorization: str = USER_AUTHORIZATION,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ProgressCleanScreeningFreezeError(
            "tracked worktree must be clean before screening freeze"
        )
    draft = load_json_object(DRAFT_PATH)
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    terminal = load_json_object(SMOKE_TERMINAL_PATH)
    if (
        draft.get("status")
        != "draft_waiting_for_closed_loop_smoke_pass"
        or draft.get("execution_authorization")
        != {
            "screening_clean": False,
            "completion_clean": False,
            "attacked": False,
            "confirmatory_claim": False,
        }
        or terminal.get("classification")
        != "l1_progress_projection_closed_loop_smoke_pass"
        or terminal.get("smoke_pass") is not True
        or terminal.get("lifecycle", {}).get(
            "clean_screening_protocol_freeze_authorized"
        )
        is not True
        or terminal.get("lifecycle", {}).get(
            "clean_completion_authorized"
        )
        is not False
        or terminal.get("lifecycle", {}).get(
            "attacked_execution_authorized"
        )
        is not False
    ):
        raise ProgressCleanScreeningFreezeError(
            "draft or smoke lifecycle does not authorize screening freeze"
        )
    evidence_path = (
        REPO_ROOT
        / terminal["result"]["root"]
        / "smoke_evidence.json"
    )
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path)
        != terminal["result"]["sha256"]["smoke_evidence.json"]
    ):
        raise ProgressCleanScreeningFreezeError(
            "smoke evidence differs from terminal binding"
        )
    protocol = deepcopy(draft)
    protocol.update(
        {
            "status": "clean_screening_execution_authorized",
            "created_at": created_at,
            "user_authorization": user_authorization,
            "draft_parent": {
                "path": DRAFT_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(DRAFT_PATH),
                "status": draft["status"],
            },
            "required_smoke_successor": {
                "protocol_path": terminal["protocol"]["path"],
                "protocol_sha256": terminal["protocol"]["sha256"],
                "terminal_path": SMOKE_TERMINAL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "terminal_sha256": file_sha256(SMOKE_TERMINAL_PATH),
                "evidence_path": evidence_path.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "evidence_sha256": file_sha256(evidence_path),
                "required_classification": (
                    "l1_progress_projection_closed_loop_smoke_pass"
                ),
                "classification": terminal["classification"],
                "smoke_pass": True,
            },
            "execution_authorization": {
                "screening_clean": True,
                "completion_clean": False,
                "attacked": False,
                "confirmatory_claim": False,
            },
        }
    )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    bindings = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise ProgressCleanScreeningFreezeError(
                f"screening source is absent: {relative}"
            )
        bindings[relative] = file_sha256(path)
    protocol["source"] = {
        "repository_commit": bound_commit,
        "repository_tree": _git(
            "rev-parse", f"{bound_commit}^{{tree}}"
        ),
        "sha256": bindings,
        "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
        "freezer_sha256": file_sha256(SELF_PATH),
    }
    protocol["claim_boundary"] = (
        "This post-outcome exploratory protocol authorizes only the frozen "
        "60-episode clean four-arm screening stage on 15 fresh fifth-init "
        "pairs. It does not authorize the 120-episode completion, any attacked "
        "rollout, a deployment claim, hardware-safety claim, or confirmatory "
        "claim. A screening nonpass terminates this successor."
    )
    validate_protocol(
        protocol,
        qualification_protocol=qualification,
        allow_execution=True,
    )
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument(
        "--user-authorization",
        default=USER_AUTHORIZATION,
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source_commit = None
    if args.check and args.output.is_file():
        retained = load_json_object(args.output)
        source_commit = retained.get("source", {}).get(
            "repository_commit"
        )
    text = canonical_text(
        build_protocol(
            created_at=args.created_at,
            user_authorization=args.user_authorization,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise ProgressCleanScreeningFreezeError(
                f"screening protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
