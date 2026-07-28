#!/usr/bin/env python3
"""Freeze fresh3 after the disclosed zero-row EGL launch failure."""

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
    USER_AUTHORIZATION,
)
from scripts.freeze_four_arm_v4_l1_repair_qualification_fresh2 import (  # noqa: E402
    OUTPUT_PATH as FRESH2_PROTOCOL_PATH,
    build_protocol as build_fresh2_protocol,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_fresh3_protocol.json"
)
FAILED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_l1_repair_qualification_20260728_fresh2"
)
FAILED_MANIFEST_PATH = FAILED_ROOT / "run_manifest.json"
FAILED_SUMS_PATH = FAILED_ROOT / "SHA256SUMS"
LEDGER_PATH = FAILED_ROOT / "qualification_ledger.jsonl"
SUMMARY_PATH = FAILED_ROOT / "summary.json"
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_four_arm_v4_l1_repair_qualification_fresh3.py"
)
V2_RUNNER_PATH = (
    REPO_ROOT
    / "scripts"
    / "run_four_arm_v4_l1_repair_qualification_v2.py"
)
V2_TEST_PATH = (
    REPO_ROOT / "tests" / "test_l1_repair_qualification_v2.py"
)
CREATED_AT = "2026-07-28T12:55:00+08:00"


class Fresh3FreezeError(RuntimeError):
    """Raised when the fresh3 retry cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Fresh3FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _validate_failed_fresh2() -> dict[str, Any]:
    if not FAILED_MANIFEST_PATH.is_file() or not FAILED_SUMS_PATH.is_file():
        raise Fresh3FreezeError("sealed fresh2 failure evidence is absent")
    manifest = load_json_object(FAILED_MANIFEST_PATH)
    if (
        manifest.get("status") != "terminal_failed_closed"
        or manifest.get("outcomes_observed") is not False
        or manifest.get("error")
        != (
            "LiberoRuntimeError: Could not import LIBERO/LIBERO-Safety; "
            "restore the pinned external checkout"
        )
        or LEDGER_PATH.exists()
        or SUMMARY_PATH.exists()
    ):
        raise Fresh3FreezeError(
            "fresh2 is not the disclosed zero-row EGL launch failure"
        )
    return manifest


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    user_authorization: str = USER_AUTHORIZATION,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise Fresh3FreezeError(
            "tracked worktree must be clean before fresh3 freeze"
        )
    failed_manifest = _validate_failed_fresh2()
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    protocol = build_fresh2_protocol(
        created_at=created_at,
        user_authorization=user_authorization,
        source_commit=bound_commit,
    )
    protocol["protocol_id"] = (
        "proofalign-four-arm-v4-l1-repair-qualification-fresh3-20260728"
    )
    protocol["protocol_status"] = (
        "post_egl_launch_failure_no_outcome_qualification_authorized"
    )
    protocol["parent_retry_protocol"] = {
        "path": FRESH2_PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(FRESH2_PROTOCOL_PATH),
    }
    protocol["failed_fresh2"] = {
        "root": FAILED_ROOT.relative_to(REPO_ROOT).as_posix(),
        "run_manifest_sha256": file_sha256(FAILED_MANIFEST_PATH),
        "sha256sums_sha256": file_sha256(FAILED_SUMS_PATH),
        "status": failed_manifest["status"],
        "normalized_error": failed_manifest["error"],
        "qualification_ledger_created": False,
        "summary_created": False,
        "candidate_rows_observed": 0,
        "task_outcomes_observed": False,
        "reuse_or_resume_allowed": False,
        "diagnosed_cause": (
            "the v1 single-GPU launcher set CUDA_VISIBLE_DEVICES=3 but "
            "MUJOCO_EGL_DEVICE_ID=0; vendored robosuite requires the exact "
            "EGL ordinal to occur in the textual CUDA list"
        ),
    }
    protocol["fresh_output_root"] = (
        "results/proofalign_four_arm_v4_l1_repair_qualification_"
        "20260728_fresh3"
    )
    protocol["required_runtime_interpreter"]["launch_rule"] = (
        "invoke scripts/run_four_arm_v4_l1_repair_qualification_v2.py "
        "directly with external/openpi/.venv/bin/python; its preflight must "
        "bind physical CUDA GPU 3 to exact EGL ordinal 3 before output creation"
    )
    protocol["qualification_runner"] = {
        "path": V2_RUNNER_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(V2_RUNNER_PATH),
        "launch_fix_only": True,
        "scientific_parameters_changed": False,
    }
    for path in (SELF_PATH, V2_RUNNER_PATH, V2_TEST_PATH):
        protocol["source"]["sha256"][
            path.relative_to(REPO_ROOT).as_posix()
        ] = file_sha256(path)
    protocol["retry_boundary"] = (
        "fresh3 changes only fail-closed interpreter and physical-CUDA/EGL "
        "device selection around the unchanged v1 qualification. Population, "
        "seeds, K=4 repair, 2 mm checker threshold, gates, stabilization, "
        "zero policy-conditioned steps, zero dispatch, and no-outcome claim "
        "boundary are unchanged. Both prior zero-row roots remain sealed and "
        "are excluded from rates."
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
            raise Fresh3FreezeError(
                f"fresh3 protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
