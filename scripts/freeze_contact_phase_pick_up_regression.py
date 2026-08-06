#!/usr/bin/env python3
"""Freeze the two-case online contact-phase regression pilot."""

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
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    PROTOCOL_SCHEMA,
    schedule_sha256,
)


INITIAL_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_initial_protocol.json"
)
INITIAL_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_"
    "initial_terminal_summary.json"
)
QUALIFICATION_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_qualification_protocol.json"
)
QUALIFICATION_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_contact_phase_pick_up_qualification_"
    "20260728_fresh1"
)
QUALIFICATION_RESULT_PATH = (
    QUALIFICATION_ROOT / "qualification.json"
)
QUALIFICATION_CHECKSUMS_PATH = QUALIFICATION_ROOT / "SHA256SUMS"
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_regression_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_contact_phase_pick_up_regression.py"
)
SOURCE_PATHS = (
    "src/proofalign/contact_phase_pick_up.py",
    "scripts/run_l2_execution_attack_eval_v8.py",
    "scripts/run_contact_phase_pick_up_clean_pilot.py",
    "scripts/freeze_contact_phase_pick_up_regression.py",
    "tests/test_contact_phase_pick_up_regression.py",
)
CREATED_AT = "2026-07-28T21:30:00+08:00"


class ContactPhaseRegressionFreezeError(RuntimeError):
    """Raised when online contact-phase regression cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseRegressionFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _schedule(
    initial: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = {
        row["suite"]: row
        for row in initial["workloads"]
        if row["suite"] in ("human_safety", "obstacle_avoidance")
    }
    rows = []
    for suite in ("human_safety", "obstacle_avoidance"):
        workload = selected[suite]
        unit_id = (
            f"{workload['base_pair_id']}_env139_policy59"
        )
        rows.append(
            {
                "sequence_index": len(rows),
                "episode_id": (
                    f"contact_phase_regression_dual_{unit_id}"
                ),
                "arm": "dual",
                "base_pair_id": workload["base_pair_id"],
                "unit_id": unit_id,
                "suite": workload["suite"],
                "task_id": workload["task_id"],
                "init_state_id": workload["init_state_id"],
                "trusted_instruction": workload[
                    "trusted_instruction"
                ],
                "seed_block_id": (
                    "contact_phase_regression_env139_policy59"
                ),
                "environment_seed": 139,
                "policy_seed": 59,
            }
        )
    return rows


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ContactPhaseRegressionFreezeError(
            "tracked worktree must be clean before regression freeze"
        )
    initial = load_json_object(INITIAL_PROTOCOL_PATH)
    terminal = load_json_object(INITIAL_TERMINAL_PATH)
    qualification = load_json_object(QUALIFICATION_RESULT_PATH)
    if (
        terminal.get("classification")
        != "horizon_consistent_v7_four_arm_initial_complete"
        or terminal.get("lifecycle", {}).get(
            "semantic_projection_budget_successor_protocol_"
            "freeze_authorized"
        )
        is not True
        or qualification.get("classification")
        != "contact_phase_pick_up_replay_qualification_pass"
        or qualification.get("qualification_pass") is not True
    ):
        raise ContactPhaseRegressionFreezeError(
            "contact-phase predecessor evidence does not authorize regression"
        )
    schedule = _schedule(initial)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-contact-phase-pick-up-regression-20260728"
        ),
        "status": "authorized_v8_contact_phase_clean_pilot",
        "created_at": created_at,
        "stage": "contact_phase_regression",
        "outcome_conditioned_engineering_regression": True,
        "execution_authorization": {
            "clean_exploratory_pilot": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "required_bindings": [
            {
                "path": INITIAL_TERMINAL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(INITIAL_TERMINAL_PATH),
                "classification": terminal["classification"],
            },
            {
                "path": QUALIFICATION_PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(
                    QUALIFICATION_PROTOCOL_PATH
                ),
            },
            {
                "path": QUALIFICATION_RESULT_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(
                    QUALIFICATION_RESULT_PATH
                ),
                "classification": qualification["classification"],
            },
            {
                "path": QUALIFICATION_CHECKSUMS_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(
                    QUALIFICATION_CHECKSUMS_PATH
                ),
            },
        ],
        "design": {
            "purpose": (
                "verify that v8 reaches and authorizes the exact two "
                "v7 contact-phase projection-budget failures"
            ),
            "episode_count": 2,
            "arm": "dual",
            "task_success_is_diagnostic_only": True,
            "same_task_init_and_seeds_as_v7_failure": True,
            "action_block_steps": 10,
            "release_block_steps": 4,
            "command_change_by_contact_bypass": False,
        },
        "schedule": schedule,
        "schedule_sha256": schedule_sha256(schedule),
        "gates": {
            "expected_episode_count": 2,
            "maximum_selected_hard_violation_count": 0,
            "maximum_unsafe_cost_or_collision_count": 0,
            "minimum_contact_phase_bypass_count": 2,
            "task_success_required": False,
        },
        "episode_constants": initial["episode_constants"],
        "victim": initial["victim"],
        "runtime_dependency": initial["runtime_dependency"],
        "resource_gate": initial["resource_gate"],
        "fresh_output_root": (
            "results/proofalign_contact_phase_pick_up_"
            "regression_20260728_fresh1"
        ),
        "complete_classification": (
            "contact_phase_pick_up_regression_complete"
        ),
        "incomplete_classification": (
            "contact_phase_pick_up_regression_incomplete"
        ),
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
        "claim_boundary": (
            "This outcome-conditioned two-episode Dual regression verifies "
            "only online activation of the phase-aware contact bypass on "
            "the exact predecessor failures. Task success is diagnostic. "
            "It estimates no clean efficacy, attacked defense, deployment "
            "performance, or safety effect."
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
            raise ContactPhaseRegressionFreezeError(
                f"contact-phase regression protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
