#!/usr/bin/env python3
"""Outcome-free trigger-rich design pilot for v14 safety baselines.

The pilot injects controlled near-limit position, outward velocity, and
generalized-force doses into every arm-joint side of one disclosed LIBERO
environment.  Four fixed baselines then receive the same five-step hold
command: no guard, post-step reactive stop, one-step shadow-only monitoring,
and the v14 predictive virtual brake.

No policy is loaded and no reward, task success, cost, collision, or
environment-done value is inspected.  Results may select stress doses for a
separately frozen development matrix, but are not qualification evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as full  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_shadow_only as shadow  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _reset_controller,
    _robot_arrays,
)


SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-design-pilot.v1"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_"
    "multijoint_stress_design_pilot_20260731"
)
DEFAULT_OUTPUT = OUTPUT_ROOT / "pilot_evidence.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
PILOT_IDENTITY = {
    "suite": "human_safety",
    "task_id": 0,
    "init_state_id": 2,
}
DOSES = (
    {
        "dose": "low",
        "initial_margin_rad": 0.24,
        "outward_velocity_rad_s": 0.4,
        "outward_generalized_force": 0.0,
    },
    {
        "dose": "medium",
        "initial_margin_rad": 0.20,
        "outward_velocity_rad_s": 0.8,
        "outward_generalized_force": 25.0,
    },
    {
        "dose": "high",
        "initial_margin_rad": 0.17,
        "outward_velocity_rad_s": 1.2,
        "outward_generalized_force": 50.0,
    },
)
BASELINES = (
    "no_guard",
    "reactive_stop",
    "shadow_only",
    "predictive_brake",
)
HOLD_ACTION = np.asarray(
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
    dtype=np.float64,
)
HORIZON_STEPS = 5


class V14StressDesignPilotError(RuntimeError):
    """Raised when the outcome-free stress pilot is not auditable."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressDesignPilotError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _canonical(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _margin_matrix(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
) -> np.ndarray:
    return full._joint_side_margins(
        np.asarray(env.sim.data.qpos[qidx], dtype=np.float64),
        limits,
    )


def _margin_rows(matrix: np.ndarray) -> list[dict[str, Any]]:
    return full._margin_rows(matrix)


def _exposure(
    matrices: list[np.ndarray],
) -> dict[str, Any]:
    values = (
        np.stack(matrices)
        if matrices
        else np.empty((0, full.JOINT_COUNT, 2))
    )
    return {
        "observed_state_count": len(matrices),
        "observed_side_value_count": int(values.size),
        "below_floor_count": int(
            np.sum(values < full.SAFE_MARGIN_FLOOR_RAD)
        ),
        "crossing_count": int(np.sum(values < 0.0)),
        "minimum_margin_rad": (
            float(np.min(values)) if values.size else None
        ),
    }


def _run_direct(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    *,
    reactive: bool,
) -> dict[str, Any]:
    matrices = []
    stop_reason = None
    maximum_constraint_force = 0.0
    for _ in range(HORIZON_STEPS):
        # Deliberately discard transition values, including reward/done/info.
        env.step(HOLD_ACTION)
        actual = _margin_matrix(env, qidx, limits)
        matrices.append(actual)
        maximum_constraint_force = max(
            maximum_constraint_force,
            float(
                np.max(
                    np.abs(
                        np.asarray(
                            env.sim.data.qfrc_constraint,
                            dtype=np.float64,
                        )
                    )
                )
            ),
        )
        if (
            reactive
            and float(np.min(actual))
            < full.SAFE_MARGIN_FLOOR_RAD
        ):
            stop_reason = "post_step_below_floor"
            break
    return {
        "executed_step_count": len(matrices),
        "policy_decision_count": len(matrices),
        "trigger_count": int(stop_reason is not None),
        "intervention_count": 0,
        "deadlock_count": 0,
        "reactive_stop_count": int(stop_reason is not None),
        "stop_reason": stop_reason,
        "shadow_env_step_count": 0,
        "restore_failure_count": 0,
        "exact_action_mismatch_count": 0,
        "maximum_abs_constraint_force": (
            maximum_constraint_force
        ),
        "actual_joint_side_margins": [
            _margin_rows(matrix) for matrix in matrices
        ],
        **_exposure(matrices),
    }


def _run_screened(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    *,
    baseline: str,
) -> dict[str, Any]:
    wrapper_class = (
        shadow.MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment
        if baseline == "shadow_only"
        else full.MultiJointPredictiveVirtualBrakeEnvironment
    )
    wrapper = wrapper_class(
        env,
        wait_steps=0,
        enabled=True,
        config=None,
    )
    matrices = []
    maximum_constraint_force = 0.0
    for _ in range(HORIZON_STEPS):
        # The wrapped transition remains deliberately uninspected.
        wrapper.step(HOLD_ACTION)
        audit = wrapper.observations[-1]
        maximum_constraint_force = max(
            maximum_constraint_force,
            float(
                audit["maximum_abs_guarded_constraint_force"]
            ),
        )
        if audit["deadlock"] is not True:
            matrices.append(
                full_clean_margin_matrix(
                    audit["actual_joint_side_margins"]
                )
            )
        if audit["deadlock"] is True:
            break
    audits = wrapper.observations
    return {
        "executed_step_count": sum(
            audit["deadlock"] is not True for audit in audits
        ),
        "policy_decision_count": len(audits),
        "trigger_count": sum(
            audit["triggered"] is True for audit in audits
        ),
        "intervention_count": sum(
            audit["intervened"] is True for audit in audits
        ),
        "deadlock_count": sum(
            audit["deadlock"] is True for audit in audits
        ),
        "reactive_stop_count": 0,
        "stop_reason": (
            str(audits[-1]["deadlock_reason"])
            if audits and audits[-1]["deadlock"]
            else None
        ),
        "shadow_env_step_count": sum(
            int(audit["shadow_env_step_count"])
            for audit in audits
        ),
        "restore_failure_count": sum(
            audit["shadow_restore_identity"] is not True
            for audit in audits
        ),
        "exact_action_mismatch_count": sum(
            audit["deadlock"] is not True
            and audit["exact_action_identity"] is not True
            for audit in audits
        ),
        "maximum_abs_constraint_force": (
            maximum_constraint_force
        ),
        "actual_joint_side_margins": [
            _margin_rows(matrix) for matrix in matrices
        ],
        **_exposure(matrices),
    }


def full_clean_margin_matrix(value: Any) -> np.ndarray:
    if not isinstance(value, list) or len(value) != full.JOINT_COUNT:
        raise V14StressDesignPilotError(
            "screened audit lacks seven margin rows"
        )
    matrix = np.empty((full.JOINT_COUNT, 2), dtype=np.float64)
    for index, row in enumerate(value):
        if row.get("joint_index") != index:
            raise V14StressDesignPilotError(
                "screened margin ordering differs"
            )
        matrix[index] = (
            float(row["lower_margin_rad"]),
            float(row["upper_margin_rad"]),
        )
    return matrix


def _inject(
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    *,
    joint_index: int,
    side: str,
    dose: Mapping[str, Any],
) -> None:
    sign = 1.0 if side == "upper" else -1.0
    env.sim.data.qpos[qidx[joint_index]] = (
        limits[joint_index, 1]
        - float(dose["initial_margin_rad"])
        if side == "upper"
        else limits[joint_index, 0]
        + float(dose["initial_margin_rad"])
    )
    env.sim.data.qvel[vidx] = 0.0
    env.sim.data.qvel[vidx[joint_index]] = (
        sign * float(dose["outward_velocity_rad_s"])
    )
    env.sim.data.qfrc_applied[:] = 0.0
    env.sim.data.qfrc_applied[vidx[joint_index]] = (
        sign * float(dose["outward_generalized_force"])
    )
    env.sim.data.qacc_warmstart[:] = 0.0
    env.sim.forward()
    _reset_controller(robot)


def run_pilot(*, gpu: int) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V14StressDesignPilotError(
            "tracked worktree must be clean before the stress pilot"
        )
    _configure_environment(gpu)
    runtime = base.load_libero_task_runtime(**PILOT_IDENTITY)
    args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=gpu,
        control_freq=20,
        horizon=1000,
        seed=509,
    )
    env = base.create_env(runtime, args)
    rows = []
    counters: Counter[str] = Counter()
    no_guard_shadow_max_error = 0.0
    restore_failure_count = 0
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = _robot_arrays(env)
        canonical = (
            full.core.capture_warmstart_policy_shadow_snapshot(
                env,
                robot,
                source_id="v14-stress-pilot:canonical",
            )
        )
        for joint_index in range(full.JOINT_COUNT):
            for side in full.JOINT_SIDES:
                for dose in DOSES:
                    canonical_restore = (
                        full.core.restore_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            canonical,
                        )
                    )
                    if not full.core._restore_identity(
                        canonical_restore
                    ):
                        raise V14StressDesignPilotError(
                            "canonical restore lost identity"
                        )
                    _inject(
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=joint_index,
                        side=side,
                        dose=dose,
                    )
                    injected = (
                        full.core.capture_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            source_id=(
                                "v14-stress-pilot:"
                                f"joint{joint_index}:{side}:"
                                f"{dose['dose']}"
                            ),
                        )
                    )
                    initial = _margin_matrix(env, qidx, limits)
                    lane_results = {}
                    for baseline in BASELINES:
                        restored = (
                            full.core.restore_warmstart_policy_shadow_snapshot(
                                env,
                                robot,
                                injected,
                            )
                        )
                        restore_identity = full.core._restore_identity(
                            restored
                        )
                        restore_failure_count += int(
                            not restore_identity
                        )
                        if not restore_identity:
                            raise V14StressDesignPilotError(
                                "baseline restore lost identity"
                            )
                        if baseline == "no_guard":
                            result = _run_direct(
                                env,
                                qidx,
                                limits,
                                reactive=False,
                            )
                        elif baseline == "reactive_stop":
                            result = _run_direct(
                                env,
                                qidx,
                                limits,
                                reactive=True,
                            )
                        else:
                            result = _run_screened(
                                env,
                                qidx,
                                limits,
                                baseline=baseline,
                            )
                        lane_results[baseline] = result
                        counters[
                            f"{baseline}_lane_count"
                        ] += 1
                        for field in (
                            "trigger_count",
                            "intervention_count",
                            "deadlock_count",
                            "reactive_stop_count",
                            "below_floor_count",
                            "crossing_count",
                        ):
                            counters[f"{baseline}_{field}"] += int(
                                result[field]
                            )
                    no_guard_values = lane_results["no_guard"][
                        "actual_joint_side_margins"
                    ]
                    shadow_values = lane_results["shadow_only"][
                        "actual_joint_side_margins"
                    ]
                    if len(no_guard_values) == len(shadow_values):
                        for no_guard_row, shadow_row in zip(
                            no_guard_values,
                            shadow_values,
                            strict=True,
                        ):
                            no_guard_shadow_max_error = max(
                                no_guard_shadow_max_error,
                                float(
                                    np.max(
                                        np.abs(
                                            full_clean_margin_matrix(
                                                no_guard_row
                                            )
                                            - full_clean_margin_matrix(
                                                shadow_row
                                            )
                                        )
                                    )
                                ),
                            )
                    else:
                        counters[
                            "no_guard_shadow_trace_length_mismatch_count"
                        ] += 1
                    rows.append(
                        {
                            "lane_id": (
                                f"joint{joint_index}:{side}:"
                                f"{dose['dose']}"
                            ),
                            "joint_index": joint_index,
                            "side": side,
                            "dose": dict(dose),
                            "initial_joint_side_margins": (
                                _margin_rows(initial)
                            ),
                            "baselines": lane_results,
                        }
                    )
    finally:
        if hasattr(env, "close"):
            env.close()
    expected_lanes = full.JOINT_COUNT * 2 * len(DOSES)
    return {
        "schema": SCHEMA,
        "classification": (
            "v14_multijoint_stress_design_pilot_complete"
            if len(rows) == expected_lanes
            and restore_failure_count == 0
            else "v14_multijoint_stress_design_pilot_incomplete"
        ),
        "pilot_role": "outcome-free stress-dose design",
        "pilot_identity": PILOT_IDENTITY,
        "source": {
            "repository_commit": _git("rev-parse", "HEAD"),
            "repository_tree": _git("rev-parse", "HEAD^{tree}"),
            "runner": str(
                Path(__file__).resolve().relative_to(REPO_ROOT)
            ),
            "runner_sha256": _sha256(Path(__file__).resolve()),
        },
        "design": {
            "joint_count": full.JOINT_COUNT,
            "joint_side_count": full.JOINT_COUNT * 2,
            "doses": [dict(row) for row in DOSES],
            "baselines": list(BASELINES),
            "horizon_steps": HORIZON_STEPS,
            "hold_action": HOLD_ACTION.tolist(),
            "expected_stress_lane_count": expected_lanes,
            "expected_baseline_lane_count": (
                expected_lanes * len(BASELINES)
            ),
        },
        "integrity": {
            "stress_lane_count": len(rows),
            "restore_failure_count": restore_failure_count,
            "no_guard_shadow_trace_length_mismatch_count": (
                counters[
                    "no_guard_shadow_trace_length_mismatch_count"
                ]
            ),
            "no_guard_shadow_maximum_side_error_rad": (
                no_guard_shadow_max_error
            ),
            "policy_loaded": False,
            "reward_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
            "environment_done_read": False,
        },
        "aggregate": dict(sorted(counters.items())),
        "lanes": rows,
        "claim_boundary": (
            "This disclosed one-environment pilot may select stress doses "
            "for a separately frozen development matrix. It does not "
            "measure task utility, attacked efficacy, generalization, "
            "hardware behavior, or physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.output.exists() or CHECKSUMS_PATH.exists():
        raise V14StressDesignPilotError(
            "stress pilot output already exists"
        )
    report = run_pilot(gpu=args.gpu)
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(_canonical(report), encoding="utf-8")
    CHECKSUMS_PATH.write_text(
        f"{_sha256(args.output)}  {args.output.name}\n",
        encoding="utf-8",
    )
    print(_canonical(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
