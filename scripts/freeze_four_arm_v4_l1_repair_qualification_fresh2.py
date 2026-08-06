#!/usr/bin/env python3
"""Freeze the disclosed fresh2 retry after a zero-outcome runtime failure."""

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
from scripts.freeze_four_arm_v4_l1_repair_qualification import (  # noqa: E402
    CREATED_AT as PARENT_CREATED_AT,
    OUTPUT_PATH as PARENT_PROTOCOL_PATH,
    USER_AUTHORIZATION,
    build_protocol as build_parent_protocol,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_fresh2_protocol.json"
)
FAILED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_repair_qualification_20260728_fresh1"
)
FAILED_MANIFEST_PATH = FAILED_ROOT / "run_manifest.json"
FAILED_SUMS_PATH = FAILED_ROOT / "SHA256SUMS"
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_repair_qualification_fresh2.py"
)
CREATED_AT = "2026-07-28T12:42:00+08:00"


class Fresh2FreezeError(RuntimeError):
    """Raised when the fresh2 retry cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Fresh2FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _validate_failed_fresh1() -> dict[str, Any]:
    if not FAILED_MANIFEST_PATH.is_file() or not FAILED_SUMS_PATH.is_file():
        raise Fresh2FreezeError("sealed fresh1 failure evidence is absent")
    manifest = load_json_object(FAILED_MANIFEST_PATH)
    if (
        manifest.get("status") != "terminal_failed_closed"
        or manifest.get("outcomes_observed") is not False
        or manifest.get("error")
        != "ModuleNotFoundError: No module named 'jax'"
    ):
        raise Fresh2FreezeError(
            "fresh1 is not the disclosed zero-outcome interpreter failure"
        )
    return manifest


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    user_authorization: str = USER_AUTHORIZATION,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise Fresh2FreezeError(
            "tracked worktree must be clean before fresh2 freeze"
        )
    failed_manifest = _validate_failed_fresh1()
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    protocol = build_parent_protocol(
        created_at=created_at,
        user_authorization=user_authorization,
        source_commit=bound_commit,
    )
    protocol["protocol_id"] = (
        "proofalign-four-arm-v4-l1-repair-qualification-fresh2-20260728"
    )
    protocol["protocol_status"] = (
        "post_engineering_failure_no_outcome_qualification_authorized"
    )
    protocol["parent_qualification_protocol"] = {
        "path": PARENT_PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(PARENT_PROTOCOL_PATH),
        "created_at": PARENT_CREATED_AT,
    }
    protocol["failed_fresh1"] = {
        "root": FAILED_ROOT.relative_to(REPO_ROOT).as_posix(),
        "run_manifest_sha256": file_sha256(FAILED_MANIFEST_PATH),
        "sha256sums_sha256": file_sha256(FAILED_SUMS_PATH),
        "status": failed_manifest["status"],
        "error": failed_manifest["error"],
        "policy_loaded": False,
        "simulator_created": False,
        "candidate_rows_observed": 0,
        "task_outcomes_observed": False,
        "reuse_or_resume_allowed": False,
        "disclosure": (
            "fresh1 failed before policy import because it was launched with "
            "the repository utility interpreter rather than the frozen "
            "OpenPI environment. It is sealed and excluded from all rates."
        ),
    }
    protocol["required_runtime_interpreter"] = {
        "path": "external/openpi/.venv/bin/python",
        "required_import": "jax",
        "observed_jax_version_before_freeze": "0.5.3",
        "launch_rule": (
            "invoke the unchanged qualification runner directly with this "
            "interpreter; fail closed before output creation otherwise"
        ),
    }
    protocol["fresh_output_root"] = (
        "results/proofalign_four_arm_v4_l1_repair_qualification_"
        "20260728_fresh2"
    )
    protocol["source"]["sha256"][
        SELF_PATH.relative_to(REPO_ROOT).as_posix()
    ] = file_sha256(SELF_PATH)
    protocol["retry_boundary"] = (
        "fresh2 changes only the Python runtime used to launch the unchanged "
        "qualification code. Population, seeds, K=4 repair, frozen checker "
        "threshold, gates, and zero-dispatch/no-outcome boundary are unchanged."
    )
    protocol["claim_boundary"] = (
        protocol["claim_boundary"]
        + " The sealed fresh1 engineering failure contributes no scientific "
        "observation and is not pooled with fresh2."
    )
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument(
        "--user-authorization", default=USER_AUTHORIZATION
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
            raise Fresh2FreezeError(
                f"fresh2 protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
