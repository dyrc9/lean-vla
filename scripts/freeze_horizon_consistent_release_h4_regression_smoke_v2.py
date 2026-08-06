#!/usr/bin/env python3
"""Freeze H4 fresh2 after the short-policy-chunk harness failure."""

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
from scripts import (  # noqa: E402
    freeze_horizon_consistent_release_h4_regression_smoke as v1,
)


V1_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_h4_"
    "regression_smoke_protocol.json"
)
V1_MANIFEST_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_release_h4_"
    "regression_smoke_20260728_fresh1"
    / "run_manifest.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_h4_"
    "regression_smoke_v2_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_horizon_consistent_release_h4_regression_smoke_v2.py"
)
CREATED_AT = "2026-07-28T18:44:00+08:00"


class ReleaseH4RegressionV2FreezeError(RuntimeError):
    """Raised when the H4 fresh2 protocol cannot be frozen."""


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if v1._git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseH4RegressionV2FreezeError(
            "tracked worktree must be clean before H4 fresh2 freeze"
        )
    manifest = load_json_object(V1_MANIFEST_PATH)
    if (
        manifest.get("status") != "terminal_failed_closed"
        or manifest.get("error")
        != (
            "RuntimeError: Policy returned 4 actions, fewer than "
            "replan_steps=10."
        )
    ):
        raise ReleaseH4RegressionV2FreezeError(
            "H4 fresh1 failure binding differs"
        )
    protocol = v1.build_protocol(
        created_at=created_at,
        source_commit=source_commit,
    )
    protocol.update(
        {
            "protocol_id": (
                "proofalign-horizon-consistent-release-"
                "h4-regression-smoke-v2-20260728"
            ),
            "superseded_attempt": {
                "protocol_path": V1_PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "protocol_sha256": file_sha256(V1_PROTOCOL_PATH),
                "manifest_path": V1_MANIFEST_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "manifest_sha256": file_sha256(V1_MANIFEST_PATH),
                "status": manifest["status"],
                "failure": manifest["error"],
                "release_action_dispatched": False,
                "episode_artifact_written": False,
                "usable_as_regression_result": False,
            },
            "fresh_output_root": (
                "results/proofalign_horizon_consistent_release_"
                "h4_regression_smoke_20260728_fresh2"
            ),
        }
    )
    protocol["design"].update(
        {
            "policy_interface_action_block_steps": 10,
            "trusted_release_contract_steps": 4,
            "short_policy_chunk_returned": False,
        }
    )
    protocol["source"]["sha256"][
        "scripts/freeze_horizon_consistent_release_h4_regression_smoke_v2.py"
    ] = file_sha256(SELF_PATH)
    protocol["source"].update(
        {
            "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        }
    )
    protocol["claim_boundary"] = (
        "This fresh2 outcome-conditioned H4 regression supersedes a "
        "fail-closed fresh1 harness attempt that returned a four-row policy "
        "chunk to an H10 policy interface and dispatched no release action. "
        "Fresh2 keeps the H10 policy interface and compiles only the trusted "
        "release contract to H4. It does not estimate clean efficacy, "
        "attacked defense, deployment performance, hardware safety, or a "
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
            raise ReleaseH4RegressionV2FreezeError(
                f"H4 fresh2 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
