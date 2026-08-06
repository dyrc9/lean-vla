#!/usr/bin/env python3
"""Freeze outcome-informed v15.3 force-attribution development."""

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
from scripts import run_v15_force_attribution_stress_development as runner  # noqa: E402


FRESH2_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_protocol.json"
)
FRESH2_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attribution_stress_development.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_force_attributed_recovery.py",
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v15_force_attribution_stress_development.py",
    "scripts/freeze_v15_force_attribution_stress_development.py",
    "tests/test_v15_force_attributed_recovery.py",
    "tests/test_v15_force_attribution_stress_development.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-3-force-attribution-"
    "stress-development-20260731"
)
CREATED_AT = "2026-07-31T21:45:00+08:00"


class V15ForceAttributionStressDevelopmentFreezeError(RuntimeError):
    """Raised when v15.3 force development cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15ForceAttributionStressDevelopmentFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15ForceAttributionStressDevelopmentFreezeError(
            f"force-development predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15ForceAttributionStressDevelopmentFreezeError(
            "worktree must be clean before force-development freeze"
        )
    source = load_json_object(FRESH2_PROTOCOL_PATH)
    terminal = load_json_object(FRESH2_TERMINAL_PATH)
    if (
        source.get("status")
        != (
            "authorized_v15_2_recovery_stress_qualification_fresh2"
        )
        or terminal.get("registered_qualification_pass") is not False
        or terminal.get("registered_result_unchanged") is not True
        or terminal.get("next_stage_decision", {}).get(
            "develop_versioned_force_bounded_successor"
        )
        is not True
        or len(source.get("environments", ())) != 18
    ):
        raise V15ForceAttributionStressDevelopmentFreezeError(
            "force-development predecessors differ"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "outcome_informed_force_attribution_stress_development",
        "complete_classification": (
            "predictive_virtual_brake_v15_3_force_attribution_"
            "stress_development_data_complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v15_3_force_attribution_"
            "stress_development_integrity_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_3_"
            "force_attribution_stress_development_20260731_fresh1"
        ),
        "required_bindings": [
            _binding(FRESH2_PROTOCOL_PATH),
            _binding(FRESH2_TERMINAL_PATH),
        ],
        "selection": {
            "source_population": (
                "all eighteen outcome-disclosed v15.2 fresh2 "
                "qualification environments"
            ),
            "environment_count": 18,
            "environment_seed": 3509,
            "qualification_results_observed_before_freeze": True,
            "task_outcomes_used_for_selection": False,
            "held_out_population": False,
        },
        "environments": deepcopy(source["environments"]),
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [
                dict(row) for row in runner.calibration.v14.pilot.DOSES
            ],
            "baseline": runner.BASELINE,
            "horizon_steps": runner.calibration.v14.pilot.HORIZON_STEPS,
            "hold_action": runner.calibration.v14.pilot.HOLD_ACTION.tolist(),
            "mechanism_parameters_unchanged_from_v15_2": True,
            "candidate_priority_unchanged": True,
            "source_action_substitution": False,
            "new_force_attribution": [
                "pre-step maximum absolute force on risk DOFs",
                "per-risk-DOF guard-scope peak over controller substeps",
                "guard-scope reported maximum identity recomputation",
                "post-step maximum absolute force on risk DOFs",
                "per-risk-DOF positive guard-scope increment over pre-step",
                "per-risk-DOF positive post-step increment over pre-step",
                "maximum-envelope deltas retained as diagnostics",
            ],
        },
        "analysis": {
            "role": (
                "outcome-informed force-metric development after registered "
                "v15.2 force-envelope nonpass"
            ),
            "performance_axes_are_descriptive": True,
            "future_force_qualification_requires_new_population": True,
            "legacy_total_constraint_force_retained_as_diagnostic": True,
            "causal_shadow_identity_is_out_of_scope": True,
        },
        "gates": {
            "expected_environment_count": 18,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": 756,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "selected_floor_violation_count_max": 0,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
            "force_metric_development": True,
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
        "claim_boundary": (
            "This outcome-informed development reuses all disclosed fresh2 "
            "qualification environments. It changes no mechanism parameter "
            "and may only develop force-attribution estimands and future "
            "gates. It loads no policy and reads no reward, done, task "
            "success, cost, or collision. It cannot establish qualification, "
            "task utility, real-time use, deployment, hardware behavior, "
            "actuator authority, or physical safety."
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
            raise V15ForceAttributionStressDevelopmentFreezeError(
                f"force-development protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
