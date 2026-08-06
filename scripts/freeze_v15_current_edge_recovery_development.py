#!/usr/bin/env python3
"""Freeze v15.1 current-edge recovery development successor."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from scripts.run_contact_phase_pick_up_clean_pilot import schedule_sha256  # noqa: E402
from scripts import run_v15_current_edge_recovery_development as runner  # noqa: E402


PREDECESSOR_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_protocol.json"
)
PREDECESSOR_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_recovery_development.py"
)
SOURCE_PATHS = (
    "scripts/run_l2_predictive_virtual_brake_v15_floor_guard_recovery.py",
    "scripts/run_v15_floor_guard_recovery_development.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_recovery.py",
    "scripts/run_v15_current_edge_recovery_development.py",
    "scripts/freeze_v15_current_edge_recovery_development.py",
    "tests/test_v15_current_edge_recovery.py",
    "tests/test_v15_current_edge_recovery_development.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-current-edge-recovery-"
    "development-20260731"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
STAGE = (
    "predictive_virtual_brake_v15_current_edge_recovery_development"
)


class V15CurrentEdgeFreezeError(RuntimeError):
    """Raised when v15.1 development cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15CurrentEdgeFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15CurrentEdgeFreezeError(
            f"v15.1 predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _successor_schedule(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    old_stage = str(source["stage"])
    schedule = []
    for source_row in source["schedule"]:
        row = dict(source_row)
        episode_id = str(row["episode_id"])
        if not episode_id.startswith(old_stage + "_"):
            raise V15CurrentEdgeFreezeError(
                "predecessor episode stage prefix differs"
            )
        schedule.append(
            {
                **row,
                "sequence_index": len(schedule),
                "episode_id": STAGE + episode_id[len(old_stage) :],
            }
        )
    if len(schedule) != 28:
        raise V15CurrentEdgeFreezeError(
            "v15.1 schedule must retain all twenty-eight episodes"
        )
    return schedule


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15CurrentEdgeFreezeError(
            "worktree must be clean before v15.1 development freeze"
        )
    source = load_json_object(PREDECESSOR_PROTOCOL_PATH)
    terminal = load_json_object(PREDECESSOR_TERMINAL_PATH)
    if (
        source.get("schema")
        != (
            "proofalign.predictive-virtual-brake-v15-floor-guard-"
            "recovery-development-protocol.v1"
        )
        or terminal.get("development_data_complete") is not True
        or terminal.get("interpretation", {}).get(
            "recovery_development_success"
        )
        is not False
        or terminal.get("mechanism", {}).get(
            "residual_deadlock_count"
        )
        != 8
    ):
        raise V15CurrentEdgeFreezeError(
            "v15.1 predecessor differs from disclosed partial recovery"
        )
    schedule = _successor_schedule(source)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = deepcopy(source)
    protocol.update(
        {
            "schema": runner.PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": runner.AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": STAGE,
            "pass_classification": (
                "predictive_virtual_brake_v15_current_edge_recovery_"
                "development_descriptive_utility_pass"
            ),
            "nonpass_classification": (
                "predictive_virtual_brake_v15_current_edge_recovery_"
                "development_descriptive_utility_nonpass"
            ),
            "complete_classification": (
                "predictive_virtual_brake_v15_current_edge_recovery_"
                "development_data_complete"
            ),
            "incomplete_classification": (
                "predictive_virtual_brake_v15_current_edge_recovery_"
                "development_integrity_nonpass"
            ),
            "fresh_output_root": (
                "results/proofalign_predictive_virtual_brake_v15_"
                "current_edge_recovery_development_20260731_fresh1"
            ),
            "required_bindings": [
                _binding(PREDECESSOR_PROTOCOL_PATH),
                _binding(PREDECESSOR_TERMINAL_PATH),
            ],
            "schedule": schedule,
            "schedule_sha256": schedule_sha256(schedule),
            "design": {
                **source["design"],
                "study_role": (
                    "outcome-informed current-edge recovery development"
                ),
                "recovery_factor": (
                    "preserve v14 candidates, then 0.150001-rad floor "
                    "candidate, then current minimum margin minus 1e-9 rad"
                ),
                "v14_and_floor_candidate_order_preserved": True,
                "source_action_substitution": False,
            },
            "analysis": {
                **source["analysis"],
                "role": "outcome-informed current-edge recovery development",
            },
            "episode_constants": {
                **source["episode_constants"],
                "execution_order": (
                    "same seven outcome-disclosed units, seeds, and rotated "
                    "four-arm order as floor-edge development"
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
            "outcomes_observed_for_selection": True,
            "outcome_conditioned_engineering_regression": True,
            "claim_boundary": (
                "This second outcome-informed development successor retains "
                "the same seven disclosed deadlock pairs and the same seeds. "
                "It may diagnose whether a strongest-current-feasible shadow "
                "candidate closes the eight residual floor-edge deadlocks. "
                "It cannot qualify task utility, attacked efficacy, "
                "deployment, hardware behavior, actuator authority, or "
                "physical safety."
            ),
        }
    )
    return protocol


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
    protocol = build_protocol(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        ),
        source_commit=(
            str(retained["source"]["repository_commit"])
            if retained is not None
            else None
        ),
    )
    text = canonical_text(protocol)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15CurrentEdgeFreezeError(
                f"v15.1 development protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
