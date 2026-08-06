#!/usr/bin/env python3
"""Freeze v15.2 recovery stress calibration on disclosed environments."""

from __future__ import annotations

import argparse
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
from scripts import run_v15_current_edge_priority_recovery_stress_calibration as runner  # noqa: E402


V14_STRESS_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_protocol.json"
)
V14_STRESS_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_terminal_summary.json"
)
V15_2_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_development_protocol.json"
)
V15_2_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_development_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_priority_recovery_stress_calibration.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint_shadow_only.py",
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v14_multijoint_stress_development.py",
    "scripts/run_v14_multijoint_stress_qualification.py",
    "scripts/run_l2_predictive_virtual_brake_v15_floor_guard_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_calibration.py",
    "scripts/freeze_v15_current_edge_priority_recovery_stress_calibration.py",
    "tests/test_v15_current_edge_priority_recovery_stress_calibration.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-2-current-edge-priority-"
    "recovery-stress-calibration-20260731"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"


class V15RecoveryStressCalibrationFreezeError(RuntimeError):
    """Raised when recovery stress calibration cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryStressCalibrationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15RecoveryStressCalibrationFreezeError(
            f"calibration predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _calibration_environments(
    source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for source_row in source["environments"]:
        row = dict(source_row)
        source_id = str(row["environment_id"])
        if not source_id.startswith("v14_stress_dev_"):
            raise V15RecoveryStressCalibrationFreezeError(
                "v14 stress environment identity differs"
            )
        row["environment_id"] = (
            "v15_2_recovery_stress_cal_"
            + source_id.removeprefix("v14_stress_dev_")
        )
        row["environment_seed"] = 2509
        rows.append(row)
    if len(rows) != 12:
        raise V15RecoveryStressCalibrationFreezeError(
            "calibration requires twelve disclosed environments"
        )
    return rows


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15RecoveryStressCalibrationFreezeError(
            "worktree must be clean before calibration freeze"
        )
    v14_protocol = load_json_object(V14_STRESS_PROTOCOL_PATH)
    v14_terminal = load_json_object(V14_STRESS_TERMINAL_PATH)
    v15_protocol = load_json_object(V15_2_PROTOCOL_PATH)
    v15_terminal = load_json_object(V15_2_TERMINAL_PATH)
    if (
        v14_protocol.get("status")
        != "authorized_v14_multijoint_stress_development"
        or v14_terminal.get("registered_development_data_complete")
        is not False
        or v14_terminal.get("no_guard_shadow_identity_diagnostic", {}).get(
            "all_registered_threshold_classifications_identical"
        )
        is not True
        or v15_protocol.get("status")
        != "authorized_v15_current_edge_priority_recovery_development"
        or v15_terminal.get("development_selection", {}).get(
            "recovery_candidate_selected_for_stress_qualification"
        )
        is not True
        or v15_terminal.get("mechanism", {}).get(
            "residual_deadlock_count"
        )
        != 0
    ):
        raise V15RecoveryStressCalibrationFreezeError(
            "calibration predecessors differ from disclosed results"
        )
    environments = _calibration_environments(v14_protocol)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "outcome_disclosed_recovery_stress_calibration",
        "complete_classification": (
            "predictive_virtual_brake_v15_2_recovery_stress_"
            "calibration_data_complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v15_2_recovery_stress_"
            "calibration_integrity_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_2_"
            "recovery_stress_calibration_20260731_fresh1"
        ),
        "required_bindings": [
            _binding(V14_STRESS_PROTOCOL_PATH),
            _binding(V14_STRESS_TERMINAL_PATH),
            _binding(V15_2_PROTOCOL_PATH),
            _binding(V15_2_TERMINAL_PATH),
        ],
        "selection": {
            "source_population": (
                "the twelve outcome-disclosed v14 stress-development "
                "task/init identities"
            ),
            "environment_seed": 2509,
            "environment_count": len(environments),
            "stress_results_observed_before_freeze": True,
            "recovery_results_observed_before_freeze": True,
            "task_outcomes_used_for_selection": False,
            "held_out_population": False,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [dict(row) for row in runner.v14.pilot.DOSES],
            "baselines": list(runner.BASELINES),
            "horizon_steps": runner.v14.pilot.HORIZON_STEPS,
            "hold_action": runner.v14.pilot.HOLD_ACTION.tolist(),
            "primary_pair": [
                "v14_predictive_brake",
                "v15_2_recovery",
            ],
            "causal_controls": ["no_guard", "shadow_only"],
            "recovery_parameters_frozen": {
                "v14_guard_margins_rad": list(
                    runner.recovery.BRAKE_MARGINS_RAD
                ),
                "current_edge_epsilon_rad": (
                    runner.recovery.CURRENT_EDGE_EPSILON_RAD
                ),
                "floor_edge_margin_rad": (
                    runner.recovery.RECOVERY_GUARD_MARGIN_RAD
                ),
                "candidate_priority": runner.RECOVERY_PRIORITY,
                "source_action_substitution": False,
            },
        },
        "analysis": {
            "role": (
                "outcome-disclosed calibration used only to freeze a future "
                "held-out recovery stress qualification"
            ),
            "primary_estimands": [
                "paired v14 and v15.2 deadlock-lane counts",
                "v15.2 residual deadlock and executed-step availability",
                "v15.2 crossing and below-floor counts",
                "current-edge and floor-edge recovery selections",
            ],
            "system_estimands": [
                "p50/p95/p99/max screen latency and 50-ms miss rate",
                "maximum generalized constraint force",
                "active contact warnings and contact saturation",
                "prediction-execution margin error",
            ],
            "performance_gates_are_descriptive": True,
            "future_qualification_requires_new_population": True,
        },
        "gates": {
            "expected_environment_count": 12,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": 504,
            "expected_baseline_lane_count": 2016,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "selected_floor_violation_count_max": 0,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "control_period_seconds": 0.05,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
            "qualification_gate_selection": True,
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
            "This calibration reuses outcome-disclosed task/init identities "
            "and therefore cannot support a held-out or confirmatory claim. "
            "It loads no policy and reads no reward, done, task success, "
            "cost, or collision. It may be used to freeze recovery stress "
            "qualification gates for joint-limit-proxy containment, "
            "deadlock, availability, latency, simulator constraint force, "
            "and contact-capacity instrumentation. It cannot establish task "
            "utility, attacked efficacy, deployment, hardware behavior, "
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
            raise V15RecoveryStressCalibrationFreezeError(
                f"calibration protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
