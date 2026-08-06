#!/usr/bin/env python3
"""Freeze fresh2 after the fresh1 checksum-writer harness failure."""

from __future__ import annotations

import argparse
from pathlib import Path
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
from scripts import freeze_horizon_consistent_release_qualification as v1  # noqa: E402


V1_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_qualification_protocol.json"
)
V1_RESULT_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_release_"
    "qualification_20260728_fresh1"
    / "qualification.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_qualification_v2_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_qualification_v2.py"
)
CREATED_AT = "2026-07-28T18:21:00+08:00"


class ReleaseQualificationV2FreezeError(RuntimeError):
    """Raised when the fresh2 protocol cannot be frozen."""


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if v1._git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseQualificationV2FreezeError(
            "tracked worktree must be clean before fresh2 freeze"
        )
    if not V1_RESULT_PATH.is_file():
        raise ReleaseQualificationV2FreezeError(
            "fresh1 incomplete qualification artifact is absent"
        )
    v1_protocol = load_json_object(V1_PROTOCOL_PATH)
    if v1_protocol.get("status") != (
        "authorized_offline_release_qualification"
    ):
        raise ReleaseQualificationV2FreezeError(
            "fresh1 protocol binding differs"
        )
    protocol = v1.build_protocol(
        created_at=created_at,
        source_commit=source_commit,
    )
    protocol.update(
        {
            "protocol_id": (
                "proofalign-horizon-consistent-release-"
                "offline-qualification-v2-20260728"
            ),
            "status": "authorized_offline_release_qualification",
            "superseded_attempt": {
                "protocol_path": V1_PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "protocol_sha256": file_sha256(V1_PROTOCOL_PATH),
                "result_path": V1_RESULT_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "result_sha256": file_sha256(V1_RESULT_PATH),
                "checksum_manifest_written": False,
                "failure": (
                    "AttributeError: scripts.saber_io has no attribute "
                    "write_checksums"
                ),
                "policy_loaded": False,
                "simulator_created": False,
                "actions_dispatched": False,
                "usable_as_qualification_result": False,
            },
            "fresh_output_root": (
                "results/proofalign_horizon_consistent_release_"
                "qualification_20260728_fresh2"
            ),
        }
    )
    protocol["source"]["sha256"][
        "scripts/freeze_horizon_consistent_release_qualification_v2.py"
    ] = file_sha256(SELF_PATH)
    protocol["source"].update(
        {
            "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        }
    )
    protocol["claim_boundary"] = (
        "This fresh2 CPU-only qualification supersedes a fresh1 harness "
        "attempt that wrote an unbound JSON artifact but failed before its "
        "checksum manifest. It checks release actuator canonicalization on "
        "the same frozen analytic corpus and historical action blocks. It "
        "loads no policy, creates no simulator, dispatches no action, and "
        "does not establish online release success, clean efficacy, attacked "
        "defense, deployment performance, hardware safety, or a "
        "confirmatory effect."
    )
    return protocol


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
        build_protocol(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise ReleaseQualificationV2FreezeError(
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
