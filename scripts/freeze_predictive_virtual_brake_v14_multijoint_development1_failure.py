#!/usr/bin/env python3
"""Freeze the two-outcome v14 development1 integration failure."""

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


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_20260731_development1"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "development1_runner_failure.json"
)
CREATED_AT = "2026-07-31T16:06:00+08:00"
EXPECTED_ERROR = (
    "AttributeError: 'MultiJointBrakeConfig' object has no attribute "
    "'target_joint_index'"
)
CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_development1_"
    "partial_outcome_runner_failure"
)


class PredictiveVirtualBrakeV14FailureError(RuntimeError):
    """Raised when the retained development1 failure differs."""


def _checksum_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in entries:
            raise PredictiveVirtualBrakeV14FailureError(
                "duplicate development1 checksum entry"
            )
        entries[relative] = digest
    return entries


def build_report(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(PROTOCOL_PATH)
    manifest_path = RESULT_ROOT / "run_manifest.json"
    checksums_path = RESULT_ROOT / "SHA256SUMS"
    if not manifest_path.is_file() or not checksums_path.is_file():
        raise PredictiveVirtualBrakeV14FailureError(
            "development1 terminal artifacts are absent"
        )
    manifest = load_json_object(manifest_path)
    expected_completed = [
        str(row["episode_id"]) for row in protocol["schedule"][:2]
    ]
    failed_spec = protocol["schedule"][2]
    if (
        manifest.get("status") != "terminal_failed_closed"
        or manifest.get("error") != EXPECTED_ERROR
        or manifest.get("completed_episode_ids")
        != expected_completed
        or failed_spec.get("arm") != "vla_only"
        or protocol.get("fresh_output_root")
        != RESULT_ROOT.relative_to(REPO_ROOT).as_posix()
    ):
        raise PredictiveVirtualBrakeV14FailureError(
            "development1 failure boundary differs"
        )

    entries = _checksum_entries(checksums_path)
    if len(entries) != 4:
        raise PredictiveVirtualBrakeV14FailureError(
            "development1 checksum entry count differs"
        )
    for relative, expected in entries.items():
        path = RESULT_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise PredictiveVirtualBrakeV14FailureError(
                f"development1 checksum differs: {relative}"
            )

    outcomes = []
    for spec in protocol["schedule"][:2]:
        episode_path = (
            RESULT_ROOT
            / str(spec["episode_id"])
            / "episodes"
            / (
                f"{spec['suite']}_task{spec['task_id']}_"
                f"init{spec['init_state_id']}.json"
            )
        )
        episode = load_json_object(episode_path)
        metadata = episode["metadata"]
        if (
            metadata.get("runner_variant")
            != (
                "proofalign_l2_predictive_hard_virtual_brake_"
                "v14_multijoint"
            )
            or metadata.get("four_arm_label") != spec["arm"]
        ):
            raise PredictiveVirtualBrakeV14FailureError(
                "development1 completed episode identity differs"
            )
        outcomes.append(
            {
                "sequence_index": int(spec["sequence_index"]),
                "episode_id": str(spec["episode_id"]),
                "arm": str(spec["arm"]),
                "task_success": bool(episode["task_success"]),
                "unsafe_cost_or_collision": bool(
                    episode["unsafe_cost_or_collision"]
                ),
                "decision": str(episode["decision"]),
                "path": episode_path.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(episode_path),
            }
        )

    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "development1-runner-failure.v1"
        ),
        "classification": CLASSIFICATION,
        "created_at": created_at,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
            "source_commit": protocol["source"][
                "repository_commit"
            ],
        },
        "terminal_state": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "manifest_path": manifest_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "manifest_sha256": file_sha256(manifest_path),
            "checksums_path": checksums_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "checksums_sha256": file_sha256(checksums_path),
            "checksum_entry_count": len(entries),
            "completed_episode_count": 2,
            "completed_episode_ids": expected_completed,
            "failed_sequence_index": 2,
            "failed_episode_id": str(failed_spec["episode_id"]),
            "failed_arm": str(failed_spec["arm"]),
            "failure_before_failed_episode_artifact": True,
            "error": EXPECTED_ERROR,
        },
        "observed_outcomes": outcomes,
        "scientific_status": {
            "all_180_episodes_complete": False,
            "coverage_estimable": False,
            "task_utility_estimable": False,
            "attacked_stage_authorized": False,
            "confirmatory_claim_authorized": False,
            "partial_outcomes_may_select_workloads_seeds_or_thresholds": (
                False
            ),
            "fresh_successor_must_repeat_all_180_episodes": True,
            "development1_artifacts_reusable_in_successor": False,
        },
        "failure_cause": {
            "scope": "disabled-arm audit plumbing",
            "l2_guard_or_threshold_failure": False,
            "completed_l2_episode_count": 2,
            "disabled_arm_episode_completed": False,
            "detail": (
                "The inherited v13 disabled-arm path requested "
                "config.target_joint_index before the v14 wrapper could "
                "replace its audit with fourteen-side margins."
            ),
        },
        "claim_boundary": (
            "Development1 is terminal incomplete after two L2-enabled "
            "task outcomes. It cannot estimate coverage, utility, safety "
            "efficacy, or any registered gate. The retained root and "
            "checksums are not reused. A Fresh2 successor may change only "
            "the disabled-arm audit plumbing, must disclose both observed "
            "outcomes, preserve all 180 schedule rows, arms, workloads, "
            "seeds, guard parameters, thresholds, estimands, and gates, "
            "and repeat the complete schedule in a new output root."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    text = canonical_text(
        build_report(
            created_at=(
                str(retained["created_at"])
                if retained is not None
                else args.created_at
            )
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PredictiveVirtualBrakeV14FailureError(
                f"development1 failure artifact is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
