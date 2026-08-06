#!/usr/bin/env python3
"""Diagnose the two disclosed v15.4 held-out force failures."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_dynamic_state_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_dynamic_state_physics_development as development,
)


SCHEMA = "proofalign.v15.4-disclosed-force-nonpass-diagnostic.v1"
DEFAULT_SOURCE_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_domain_robustness_qualification_protocol.json"
)
DISCLOSED_ENVIRONMENT_ID = "v15_4_physics_qual_human_safety_task13_init10"
DISCLOSED_JOINT_INDEX = 1
DISCLOSED_SIDE = "upper"
CASES = (
    {
        "case_id": "low_friction_standard_guard_force",
        "condition_id": "arm_friction_0_7x",
        "dose": "low",
    },
    {
        "case_id": "high_friction_recovery_post_force",
        "condition_id": "arm_friction_1_3x",
        "dose": "high",
    },
)
RECOVERY_LADDER_FRACTIONS = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)
SOLVER_PROFILES = (
    {"profile_id": "solref_0_004", "guard_solref": (0.004, 1.0)},
    {"profile_id": "solref_0_006", "guard_solref": (0.006, 1.0)},
    {"profile_id": "solref_0_008", "guard_solref": (0.008, 1.0)},
    {"profile_id": "solref_0_012", "guard_solref": (0.012, 1.0)},
    {"profile_id": "solref_0_020", "guard_solref": (0.020, 1.0)},
    {"profile_id": "solref_0_040", "guard_solref": (0.040, 1.0)},
    {"profile_id": "solref_0_080", "guard_solref": (0.080, 1.0)},
)
_ACTIVE_GUARD_SOLREF = recovery.GUARD_SOLREF


class V154ForceNonpassDiagnosticError(RuntimeError):
    """Raised when the disclosed v15.4 force case cannot be reproduced."""


class DiagnosticRecoveryLadderConfig(
    recovery.predecessor.predecessor.CurrentEdgePriorityRecoveryConfig
):
    """Expose intermediate recovery margins without selecting them first."""

    def __init__(self, current_edge_margin_rad: float | None) -> None:
        edge = current_edge_margin_rad
        if edge is not None and not (
            np.isfinite(edge)
            and recovery.SAFE_MARGIN_FLOOR_RAD < edge
            < min(recovery.BRAKE_MARGINS_RAD)
        ):
            raise ValueError("invalid diagnostic current-edge margin")
        object.__setattr__(self, "current_edge_margin_rad", edge)
        object.__setattr__(self, "joint_indices", tuple(range(7)))
        object.__setattr__(self, "trigger_margin_rad", recovery.TRIGGER_MARGIN_RAD)
        object.__setattr__(
            self, "safe_margin_floor_rad", recovery.SAFE_MARGIN_FLOOR_RAD
        )
        object.__setattr__(self, "guard_solref", _ACTIVE_GUARD_SOLREF)
        object.__setattr__(self, "guard_solimp", recovery.GUARD_SOLIMP)

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        edge = self.current_edge_margin_rad
        if edge is None:
            ladder: tuple[float, ...] = ()
        else:
            floor = recovery.RECOVERY_GUARD_MARGIN_RAD
            ladder = tuple(
                edge - fraction * (edge - floor)
                for fraction in RECOVERY_LADDER_FRACTIONS
            )
        middle = () if edge is None else (edge, *ladder)
        return (
            *recovery.BRAKE_MARGINS_RAD,
            *middle,
            recovery.RECOVERY_GUARD_MARGIN_RAD,
        )


@contextmanager
def _patched_diagnostic_recovery_ladder(
    guard_solref: tuple[float, float],
) -> Iterator[None]:
    global _ACTIVE_GUARD_SOLREF
    priority = recovery.predecessor.predecessor
    original = priority.CurrentEdgePriorityRecoveryConfig
    original_solref = _ACTIVE_GUARD_SOLREF
    _ACTIVE_GUARD_SOLREF = guard_solref
    priority.CurrentEdgePriorityRecoveryConfig = DiagnosticRecoveryLadderConfig
    try:
        yield
    finally:
        priority.CurrentEdgePriorityRecoveryConfig = original
        _ACTIVE_GUARD_SOLREF = original_solref


def _exactly_one(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    value: Any,
) -> Mapping[str, Any]:
    matches = [row for row in rows if row.get(field) == value]
    if len(matches) != 1:
        raise V154ForceNonpassDiagnosticError(
            f"expected one disclosed row for {field}={value!r}"
        )
    return matches[0]


def _candidate_summary(
    candidate: Mapping[str, Any],
    *,
    selected_margin: float | None,
    selected_profile: str | None,
) -> dict[str, Any]:
    margin = float(candidate["guard_margin_rad"])
    force = float(candidate["maximum_abs_constraint_force"])
    candidate_profile = candidate.get("candidate_profile_id")
    return {
        "guard_margin_rad": margin,
        "predicted_minimum_margin_rad": (
            None
            if candidate["predicted_minimum_margin_rad"] is None
            else float(candidate["predicted_minimum_margin_rad"])
        ),
        "maximum_abs_constraint_force": force,
        "configuration_inside_guard_ranges": bool(
            candidate["configuration_inside_guard_ranges"] is True
        ),
        "eligible": bool(candidate["eligible"] is True),
        "base_safety_eligible": bool(
            candidate.get("base_safety_eligible", candidate["eligible"])
            is True
        ),
        "force_feasible": bool(
            candidate.get("force_feasible", True) is True
        ),
        "recovery_candidate": bool(
            candidate.get("recovery_candidate", False) is True
        ),
        "candidate_profile_id": candidate_profile,
        "fallback_profile": bool(
            candidate.get("fallback_profile", False) is True
        ),
        "predicted_scope_positive_joint_increment": candidate.get(
            "predicted_scope_positive_joint_increment"
        ),
        "predicted_post_step_maximum_abs_risk_constraint_force": (
            candidate.get(
                "predicted_post_step_maximum_abs_risk_constraint_force"
            )
        ),
        "predicted_post_step_maximum_positive_joint_increment": (
            candidate.get(
                "predicted_post_step_maximum_positive_joint_increment"
            )
        ),
        "selected": bool(
            selected_margin is not None
            and margin == selected_margin
            and (
                selected_profile is None
                or candidate_profile == selected_profile
            )
        ),
    }


@contextmanager
def _capture_scope_post_forces(
    sink: list[np.ndarray],
) -> Iterator[None]:
    """Capture the seven-joint force after every shadow/actual guard scope."""

    core = recovery.predecessor.v14_core
    original = core._scoped_multi_joint_guards

    @contextmanager
    def captured(
        env: Any,
        robot: Any,
        *,
        configurations: list[dict[str, Any]],
    ) -> Iterator[list[dict[str, Any]]]:
        with original(
            env,
            robot,
            configurations=configurations,
        ) as audit:
            yield audit
        vidx = np.asarray(robot._ref_joint_vel_indexes, dtype=int)
        force = np.asarray(
            env.sim.data.qfrc_constraint[vidx], dtype=np.float64
        ).copy()
        if force.shape != (7,) or not np.isfinite(force).all():
            raise V154ForceNonpassDiagnosticError(
                "guard scope produced an invalid post-step force vector"
            )
        sink.append(force)

    core._scoped_multi_joint_guards = captured
    try:
        yield
    finally:
        core._scoped_multi_joint_guards = original


def _attach_candidate_post_forces(
    observation: dict[str, Any],
    scope_post_forces: Sequence[np.ndarray],
) -> None:
    candidates = observation["candidates"]
    inside = [
        row
        for row in candidates
        if row["configuration_inside_guard_ranges"] is True
    ]
    expected = len(inside) + int(observation["intervened"] is True)
    if len(scope_post_forces) != expected:
        raise V154ForceNonpassDiagnosticError(
            "candidate post-force capture count differs"
        )
    risk_indices = sorted(
        {int(row["joint_index"]) for row in observation["risk_sides"]}
    )
    pre = {
        int(row["joint_index"]): float(row["dof_constraint_force"])
        for row in observation["pre_step_joint_constraint_force"]
    }
    for candidate, force in zip(
        inside, scope_post_forces[: len(inside)], strict=True
    ):
        post_abs = max(
            (abs(float(force[index])) for index in risk_indices),
            default=0.0,
        )
        increment = max(
            (
                max(0.0, abs(float(force[index])) - abs(pre[index]))
                for index in risk_indices
            ),
            default=0.0,
        )
        candidate[
            "predicted_post_step_maximum_abs_risk_constraint_force"
        ] = post_abs
        candidate[
            "predicted_post_step_maximum_positive_joint_increment"
        ] = increment
    if observation["intervened"] is True:
        actual = scope_post_forces[-1]
        retained = {
            int(row["joint_index"]): float(row["dof_constraint_force"])
            for row in observation["post_step_joint_constraint_force"]
        }
        if any(
            not np.isclose(
                float(actual[index]), retained[index], rtol=0.0, atol=1e-12
            )
            for index in range(7)
        ):
            raise V154ForceNonpassDiagnosticError(
                "captured actual post force differs from retained audit"
            )


def _step_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    selected_margin = (
        None
        if row["selected_guard_margin_rad"] is None
        else float(row["selected_guard_margin_rad"])
    )
    selected_profile = row.get("selected_candidate_profile_id")
    candidates = [
        _candidate_summary(
            candidate,
            selected_margin=selected_margin,
            selected_profile=selected_profile,
        )
        for candidate in row["candidates"]
    ]
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    selected = [candidate for candidate in candidates if candidate["selected"]]
    if len(selected) > 1:
        raise V154ForceNonpassDiagnosticError(
            "multiple candidates match the selected guard margin"
        )
    selected_force = (
        selected[0]["maximum_abs_constraint_force"] if selected else None
    )
    minimum_force = (
        min(candidate["maximum_abs_constraint_force"] for candidate in eligible)
        if eligible
        else None
    )
    return {
        "runner_step_id": int(row["runner_step_id"]),
        "triggered": bool(row["triggered"] is True),
        "intervened": bool(row["intervened"] is True),
        "deadlock": bool(row["deadlock"] is True),
        "deadlock_reason": row.get("deadlock_reason"),
        "recovery_selected": bool(
            row.get("floor_or_current_edge_recovery_selected") is True
        ),
        "selected_guard_margin_rad": selected_margin,
        "selected_candidate_profile_id": selected_profile,
        "base_safety_eligible_candidate_count": sum(
            candidate["base_safety_eligible"] for candidate in candidates
        ),
        "force_feasible_base_candidate_count": sum(
            candidate["base_safety_eligible"]
            and candidate["force_feasible"]
            for candidate in candidates
        ),
        "force_rejected_base_eligible_candidate_count": sum(
            candidate["base_safety_eligible"]
            and not candidate["force_feasible"]
            for candidate in candidates
        ),
        "selected_candidate_force": selected_force,
        "minimum_eligible_candidate_force": minimum_force,
        "lower_force_eligible_candidate_exists": bool(
            selected_force is not None
            and minimum_force is not None
            and minimum_force < selected_force
        ),
        "current_minimum_margin_rad": float(row["current_target_margin_rad"]),
        "unguarded_predicted_minimum_margin_rad": float(
            row["unguarded_predicted_minimum_margin_rad"]
        ),
        "selected_predicted_minimum_margin_rad": (
            None
            if row["selected_predicted_minimum_margin_rad"] is None
            else float(row["selected_predicted_minimum_margin_rad"])
        ),
        "actual_minimum_margin_rad": float(row["actual_minimum_margin_rad"]),
        "prediction_execution_error_rad": row[
            "prediction_execution_margin_error_rad"
        ],
        "screen_latency_seconds": float(row.get("screen_latency_seconds", 0.0)),
        "pre_step_maximum_abs_risk_constraint_force": float(
            row["pre_step_maximum_abs_risk_constraint_force"]
        ),
        "guard_scope_maximum_positive_joint_increment_over_pre_step": float(
            row[
                "guard_scope_maximum_positive_joint_increment_over_pre_step"
            ]
        ),
        "guard_scope_reported_maximum_abs_risk_constraint_force": float(
            row["guard_scope_reported_maximum_abs_risk_constraint_force"]
        ),
        "post_step_maximum_abs_risk_constraint_force": float(
            row["post_step_maximum_abs_risk_constraint_force"]
        ),
        "post_step_maximum_positive_joint_increment_over_pre_step": float(
            row[
                "post_step_maximum_positive_joint_increment_over_pre_step"
            ]
        ),
        "risk_sides": deepcopy(row["risk_sides"]),
        "pre_step_joint_constraint_force": deepcopy(
            row["pre_step_joint_constraint_force"]
        ),
        "post_step_joint_constraint_force": deepcopy(
            row["post_step_joint_constraint_force"]
        ),
        "candidates": candidates,
    }


def _run_case(
    spec: Mapping[str, Any],
    condition: Mapping[str, Any],
    dose: Mapping[str, Any],
    *,
    gpu: int,
    guard_solref: tuple[float, float] = recovery.GUARD_SOLREF,
    wrapper_class: type[Any] = recovery.MultiJointDynamicStateRecoveryEnvironment,
) -> dict[str, Any]:
    physics = development.predecessor
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
        observations = []
        for _ in range(v14.pilot.HORIZON_STEPS):
            scope_post_forces: list[np.ndarray] = []
            with _patched_diagnostic_recovery_ladder(guard_solref):
                with _capture_scope_post_forces(scope_post_forces):
                    wrapper.step(v14.pilot.HOLD_ACTION)
            observation = deepcopy(wrapper.observations[-1])
            _attach_candidate_post_forces(observation, scope_post_forces)
            observations.append(observation)
            if observation["deadlock"] is True:
                break
        steps = [_step_summary(row) for row in observations]
        return {
            "guard_solref": list(guard_solref),
            "physics_parameter_audit": physics_audit,
            "initial_minimum_margin_rad": float(np.min(initial)),
            "executed_step_count": sum(not row["deadlock"] for row in steps),
            "deadlock_count": sum(row["deadlock"] for row in steps),
            "crossing_count": sum(
                row["actual_minimum_margin_rad"] < 0.0
                for row in steps
                if not row["deadlock"]
            ),
            "below_floor_count": sum(
                row["actual_minimum_margin_rad"]
                < recovery.SAFE_MARGIN_FLOOR_RAD
                for row in steps
                if not row["deadlock"]
            ),
            "steps": steps,
        }
    finally:
        if hasattr(env, "close"):
            env.close()


def execute(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    spec = _exactly_one(
        protocol["environments"],
        field="environment_id",
        value=DISCLOSED_ENVIRONMENT_ID,
    )
    development.predecessor.base.calibration.v14._configure_environment(gpu)
    rows = []
    resolved_cases = []
    for case in CASES:
        condition = _exactly_one(
            protocol["design"]["physics_conditions"],
            field="condition_id",
            value=case["condition_id"],
        )
        dose = _exactly_one(
            protocol["design"]["doses"],
            field="dose",
            value=case["dose"],
        )
        resolved_cases.append((case, condition, dose))
        rows.append(
            {
                **dict(case),
                "result": _run_case(
                    spec,
                    condition,
                    dose,
                    gpu=gpu,
                ),
            }
        )
    solver_profile_cells = []
    for profile in SOLVER_PROFILES:
        for case, condition, dose in resolved_cases:
            guard_solref = tuple(profile["guard_solref"])
            solver_profile_cells.append(
                {
                    "profile_id": str(profile["profile_id"]),
                    "guard_solref": list(guard_solref),
                    **dict(case),
                    "result": _run_case(
                        spec,
                        condition,
                        dose,
                        gpu=gpu,
                        guard_solref=guard_solref,
                    ),
                }
            )
    return {
        "schema": SCHEMA,
        "classification": "outcome_disclosed_development_diagnostic",
        "qualification_claim_authorized": False,
        "task_outcome_read": False,
        "policy_loaded": False,
        "fresh_environment_per_case": True,
        "diagnostic_recovery_ladder_fractions": list(
            RECOVERY_LADDER_FRACTIONS
        ),
        "source_protocol": DEFAULT_SOURCE_PROTOCOL.relative_to(
            REPO_ROOT
        ).as_posix(),
        "disclosed_environment_id": DISCLOSED_ENVIRONMENT_ID,
        "joint_index": DISCLOSED_JOINT_INDEX,
        "side": DISCLOSED_SIDE,
        "cases": rows,
        "solver_profile_cells": solver_profile_cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-protocol", type=Path, default=DEFAULT_SOURCE_PROTOCOL
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
