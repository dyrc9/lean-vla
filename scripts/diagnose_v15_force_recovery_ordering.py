#!/usr/bin/env python3
"""Diagnose recovery ordering on the disclosed v15.3 worst-force lane.

This is an outcome-disclosed development diagnostic, not a qualification
runner.  Every (physics condition, recovery variant) cell creates a fresh
simulator environment so that candidate order and force observations are not
confounded by sequential baseline replay in one environment.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as priority  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_recovery as current  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_floor_guard_recovery as floor  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_force_attributed_recovery as attributed  # noqa: E402
from scripts import run_v15_force_attributed_recovery_physics_domain_robustness_qualification as physics  # noqa: E402


SCHEMA = "proofalign.v15-force-recovery-ordering-diagnostic.v1"
DEFAULT_SOURCE_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_physics_domain_robustness_qualification_protocol.json"
)
DISCLOSED_ENVIRONMENT_ID = (
    "v15_3_physics_robust_obstacle_avoidance_human_task6_init5"
)
DISCLOSED_JOINT_INDEX = 6
DISCLOSED_SIDE = "lower"
DISCLOSED_DOSE = "low"
FORCE_THRESHOLD = 1250.0
VARIANTS = (
    (
        "v15_floor_edge_only",
        floor.MultiJointFloorGuardRecoveryEnvironment,
    ),
    (
        "v15_1_floor_then_current_edge",
        current.MultiJointCurrentEdgeRecoveryEnvironment,
    ),
    (
        "v15_2_current_then_floor_edge",
        priority.MultiJointCurrentEdgePriorityRecoveryEnvironment,
    ),
    (
        "v15_3_force_attributed_current_then_floor_edge",
        attributed.MultiJointForceAttributedRecoveryEnvironment,
    ),
)


class V15ForceRecoveryOrderingDiagnosticError(RuntimeError):
    """Raised when the disclosed diagnostic identity is unavailable."""


def _exactly_one(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    value: Any,
) -> Mapping[str, Any]:
    matches = [row for row in rows if row.get(field) == value]
    if len(matches) != 1:
        raise V15ForceRecoveryOrderingDiagnosticError(
            f"expected one disclosed row for {field}={value!r}"
        )
    return matches[0]


def _candidate_summary(
    row: Mapping[str, Any],
    *,
    selected_margin: float | None,
) -> dict[str, Any]:
    margin = float(row["guard_margin_rad"])
    force = float(row["maximum_abs_constraint_force"])
    eligible = bool(row["eligible"] is True)
    return {
        "guard_margin_rad": margin,
        "configuration_inside_guard_ranges": bool(
            row["configuration_inside_guard_ranges"] is True
        ),
        "predicted_minimum_margin_rad": (
            None
            if row["predicted_minimum_margin_rad"] is None
            else float(row["predicted_minimum_margin_rad"])
        ),
        "maximum_abs_constraint_force": force,
        "eligible": eligible,
        "force_feasible": bool(eligible and force <= FORCE_THRESHOLD),
        "selected": bool(
            selected_margin is not None and margin == selected_margin
        ),
    }


def _step_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    selected_margin = (
        None
        if row["selected_guard_margin_rad"] is None
        else float(row["selected_guard_margin_rad"])
    )
    candidates = [
        _candidate_summary(candidate, selected_margin=selected_margin)
        for candidate in row["candidates"]
    ]
    recovery_selected = bool(
        row.get("floor_or_current_edge_recovery_selected") is True
        or row.get("floor_guard_recovery_selected") is True
    )
    eligible_forces = [
        float(candidate["maximum_abs_constraint_force"])
        for candidate in candidates
        if candidate["eligible"] is True
    ]
    force_feasible = [
        candidate
        for candidate in candidates
        if candidate["force_feasible"] is True
    ]
    return {
        "runner_step_id": int(row["runner_step_id"]),
        "triggered": bool(row["triggered"] is True),
        "intervened": bool(row["intervened"] is True),
        "deadlock": bool(row["deadlock"] is True),
        "v14_baseline_would_deadlock": bool(
            row.get("v14_baseline_would_deadlock") is True
        ),
        "recovery_selected": recovery_selected,
        "floor_edge_selected": bool(
            row.get("floor_guard_recovery_selected") is True
        ),
        "current_edge_selected": bool(
            row.get("current_edge_recovery_selected") is True
        ),
        "selected_guard_margin_rad": selected_margin,
        "current_minimum_margin_rad": float(
            row["current_target_margin_rad"]
        ),
        "unguarded_predicted_minimum_margin_rad": float(
            row["unguarded_predicted_minimum_margin_rad"]
        ),
        "selected_predicted_minimum_margin_rad": (
            None
            if row["selected_predicted_minimum_margin_rad"] is None
            else float(row["selected_predicted_minimum_margin_rad"])
        ),
        "actual_minimum_margin_rad": float(
            row["actual_minimum_margin_rad"]
        ),
        "selected_guard_scope_absolute_force": float(
            row["maximum_abs_guarded_constraint_force"]
        ),
        "selected_guard_scope_attributable_force": (
            None
            if row.get(
                "guard_scope_maximum_positive_joint_increment_over_pre_step"
            )
            is None
            else float(
                row[
                    "guard_scope_maximum_positive_joint_increment_over_pre_step"
                ]
            )
        ),
        "eligible_candidate_count": sum(
            candidate["eligible"] is True for candidate in candidates
        ),
        "force_feasible_candidate_count": len(force_feasible),
        "minimum_eligible_candidate_force": (
            min(eligible_forces) if eligible_forces else None
        ),
        "minimum_force_feasible_guard_margin_rad": (
            min(
                force_feasible,
                key=lambda candidate: (
                    candidate["maximum_abs_constraint_force"],
                    candidate["guard_margin_rad"],
                ),
            )["guard_margin_rad"]
            if force_feasible
            else None
        ),
        "screen_latency_seconds": float(row["screen_latency_seconds"]),
        "candidates": candidates,
    }


def _variant_summary(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    steps = [_step_summary(row) for row in observations]
    recovery = [row for row in steps if row["recovery_selected"] is True]
    executed = [row for row in steps if row["deadlock"] is False]
    return {
        "step_count": len(steps),
        "executed_step_count": len(executed),
        "deadlock_count": sum(row["deadlock"] is True for row in steps),
        "crossing_count": sum(
            row["actual_minimum_margin_rad"] < 0.0 for row in executed
        ),
        "below_floor_count": sum(
            row["actual_minimum_margin_rad"]
            < attributed.SAFE_MARGIN_FLOOR_RAD
            for row in executed
        ),
        "minimum_actual_margin_rad": (
            min(row["actual_minimum_margin_rad"] for row in executed)
            if executed
            else None
        ),
        "recovery_selected_count": len(recovery),
        "maximum_selected_recovery_absolute_force": (
            max(
                row["selected_guard_scope_absolute_force"]
                for row in recovery
            )
            if recovery
            else None
        ),
        "maximum_selected_recovery_attributable_force": (
            max(
                row["selected_guard_scope_attributable_force"]
                for row in recovery
                if row["selected_guard_scope_attributable_force"] is not None
            )
            if any(
                row["selected_guard_scope_attributable_force"] is not None
                for row in recovery
            )
            else None
        ),
        "recovery_step_with_force_feasible_alternative_count": sum(
            row["force_feasible_candidate_count"] > 0 for row in recovery
        ),
        "maximum_screen_latency_seconds": max(
            (row["screen_latency_seconds"] for row in steps),
            default=0.0,
        ),
        "steps": steps,
    }


def _run_cell(
    spec: Mapping[str, Any],
    condition: Mapping[str, Any],
    dose: Mapping[str, Any],
    wrapper_class: type[Any],
    *,
    gpu: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    v14 = physics.base.calibration.v14
    runtime = v14.base.load_libero_task_runtime(
        benchmark_name=str(spec["suite"]),
        task_id=int(spec["task_id"]),
        init_state_id=int(spec["init_state_id"]),
        bddl_file=str(REPO_ROOT / str(spec["bddl_path"])),
    )
    args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=gpu,
        control_freq=20,
        horizon=1000,
        seed=int(spec["environment_seed"]),
    )
    env = v14.base.create_env(runtime, args)
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = v14._robot_arrays(env)
        physics_audit = physics._apply_physics_condition(
            env, robot, vidx, condition
        )
        v14.pilot._inject(
            env,
            robot,
            qidx,
            vidx,
            limits,
            joint_index=DISCLOSED_JOINT_INDEX,
            side=DISCLOSED_SIDE,
            dose=dose,
        )
        initial = v14.pilot._margin_matrix(env, qidx, limits)
        wrapper = wrapper_class(
            env,
            wait_steps=0,
            enabled=True,
            config=None,
        )
        for _ in range(v14.pilot.HORIZON_STEPS):
            wrapper.step(v14.pilot.HOLD_ACTION)
            if wrapper.observations[-1]["deadlock"] is True:
                break
        summary = _variant_summary(deepcopy(wrapper.observations))
        summary["initial_minimum_margin_rad"] = float(np.min(initial))
        return summary, physics_audit
    finally:
        if hasattr(env, "close"):
            env.close()


def execute(
    protocol: Mapping[str, Any],
    *,
    gpu: int,
) -> dict[str, Any]:
    spec = _exactly_one(
        protocol["environments"],
        field="environment_id",
        value=DISCLOSED_ENVIRONMENT_ID,
    )
    dose = _exactly_one(
        protocol["design"]["doses"],
        field="dose",
        value=DISCLOSED_DOSE,
    )
    conditions = [dict(row) for row in protocol["design"]["physics_conditions"]]
    if conditions != [dict(row) for row in physics.PHYSICS_CONDITIONS]:
        raise V15ForceRecoveryOrderingDiagnosticError(
            "physics condition identity differs from disclosed protocol"
        )
    physics.base.calibration.v14._configure_environment(gpu)
    cells = []
    for condition in conditions:
        for variant, wrapper_class in VARIANTS:
            summary, audit = _run_cell(
                spec,
                condition,
                dose,
                wrapper_class,
                gpu=gpu,
            )
            cells.append(
                {
                    "condition_id": str(condition["condition_id"]),
                    "variant": variant,
                    "summary": summary,
                    "physics_parameter_audit": audit,
                }
            )
    return {
        "schema": SCHEMA,
        "classification": "outcome_disclosed_development_diagnostic",
        "qualification_claim_authorized": False,
        "task_outcome_read": False,
        "policy_loaded": False,
        "fresh_environment_per_cell": True,
        "source_protocol": DEFAULT_SOURCE_PROTOCOL.relative_to(
            REPO_ROOT
        ).as_posix(),
        "disclosed_lane": {
            "environment_id": DISCLOSED_ENVIRONMENT_ID,
            "joint_index": DISCLOSED_JOINT_INDEX,
            "side": DISCLOSED_SIDE,
            "dose": dict(dose),
        },
        "force_threshold": FORCE_THRESHOLD,
        "cells": cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-protocol",
        type=Path,
        default=DEFAULT_SOURCE_PROTOCOL,
    )
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol = load_json_object(args.source_protocol.resolve())
    payload = execute(protocol, gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
