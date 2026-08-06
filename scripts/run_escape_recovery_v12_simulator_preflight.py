#!/usr/bin/env python3
"""Run the frozen v12.1 no-outcome simulator escape preflight."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.digests import digest_payload  # noqa: E402
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.escape_recovery_v12 import (  # noqa: E402
    EscapeRecoveryConfig,
    select_escape_recovery_candidate,
    trusted_joint_state_from_libero,
)
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    RecoveryTransactionGate,
    ShadowJointTrajectory,
)
from scripts import saber_io  # noqa: E402
from scripts.freeze_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    REPO_ROOT,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)


ROW_SCHEMA = "proofalign.escape-recovery-v12-simulator-preflight-row.v1"
SUMMARY_SCHEMA = (
    "proofalign.escape-recovery-v12-simulator-preflight-summary.v1"
)


class SimulatorPreflightError(RuntimeError):
    """Raised when the v12.1 simulator preflight must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise SimulatorPreflightError(
            f"missing frozen protocol: {PROTOCOL_PATH}"
        )
    observed = json.loads(PROTOCOL_PATH.read_text())
    expected = build_protocol()
    if observed != expected:
        raise SimulatorPreflightError(
            "v12.1 simulator preflight protocol is stale"
        )
    if observed["schema"] != PROTOCOL_SCHEMA:
        raise SimulatorPreflightError("unexpected protocol schema")
    for group in ("source_bindings", "runtime_bindings"):
        for relative, digest in observed[group].items():
            if _sha256(REPO_ROOT / relative) != digest:
                raise SimulatorPreflightError(
                    f"v12.1 binding differs: {relative}"
                )
    return observed


def _select_gpu(protocol: dict[str, Any], gpu: int) -> dict[str, Any]:
    inventory = {
        int(row["index"]): row for row in saber_io.gpu_inventory()
    }
    selected = inventory.get(gpu)
    if selected is None:
        raise SimulatorPreflightError(f"GPU {gpu} is absent")
    maximum = protocol["resource_gate"][
        "selected_gpu_memory_used_mib_max_exclusive"
    ]
    if int(selected["memory_used_mib"]) >= int(maximum):
        raise SimulatorPreflightError(
            f"GPU {gpu} violates the <{maximum} MiB memory gate"
        )
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < protocol["resource_gate"]["minimum_free_disk_gib"]:
        raise SimulatorPreflightError(
            "free disk is below the v12.1 preflight gate"
        )
    return {**selected, "free_disk_gib": free_gib}


def _configure_environment(gpu: int) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    # The pinned robosuite fork validates the physical id against
    # CUDA_VISIBLE_DEVICES before constructing the EGL context.
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(gpu)
    os.environ["MUJOCO_GL"] = "egl"
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    os.environ["LIBERO_CONFIG_PATH"] = str(
        REPO_ROOT / "results" / "runtime_config" / "libero_safety"
    )
    os.environ["LIBERO_SAFETY_ROOT"] = str(
        REPO_ROOT / "external" / "LIBERO-Safety"
    )
    external = str(REPO_ROOT / "external" / "LIBERO-Safety")
    if external not in sys.path:
        sys.path.insert(0, external)


def _robot_arrays(env: Any) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray]:
    robots = getattr(env, "robots", None)
    if not isinstance(robots, (list, tuple)) or len(robots) != 1:
        raise SimulatorPreflightError(
            "expected exactly one LIBERO robot"
        )
    robot = robots[0]
    qidx = np.asarray(robot._ref_joint_pos_indexes, dtype=int)
    vidx = np.asarray(robot._ref_joint_vel_indexes, dtype=int)
    jidx = np.asarray(robot._ref_joint_indexes, dtype=int)
    limits = np.asarray(
        env.sim.model.jnt_range[jidx], dtype=np.float64
    )
    if limits.shape != (len(qidx), 2) or len(qidx) != 7:
        raise SimulatorPreflightError(
            "unexpected LIBERO arm joint shape"
        )
    return robot, qidx, vidx, limits


def _reset_controller(robot: Any) -> None:
    robot.controller.update(force=True)
    robot.controller.reset_goal()


def _restore(
    env: Any,
    robot: Any,
    state: Any,
    expected_flat: np.ndarray,
) -> bool:
    env.sim.set_state(state)
    env.sim.forward()
    _reset_controller(robot)
    observed = np.asarray(env.sim.get_state().flatten())
    return bool(np.array_equal(observed, expected_flat))


def _minimum_margin(qpos: np.ndarray, limits: np.ndarray) -> float:
    return float(
        np.min(
            np.minimum(
                qpos - limits[:, 0],
                limits[:, 1] - qpos,
            )
        )
    )


def _run_pair(
    protocol: dict[str, Any],
    pair: dict[str, Any],
    *,
    base: Any,
    gpu: int,
) -> dict[str, Any]:
    simulator = protocol["simulator"]
    runtime = base.load_libero_task_runtime(
        benchmark_name=pair["suite"],
        task_id=int(pair["task_id"]),
        init_state_id=int(pair["init_state_id"]),
        bddl_file=pair["bddl_path"],
    )
    args = argparse.Namespace(
        env_img_res=int(simulator["image_size"]),
        camera_names=",".join(simulator["camera_names"]),
        render_gpu_device_id=gpu,
        control_freq=int(simulator["control_frequency_hz"]),
        horizon=int(simulator["horizon"]),
        seed=int(protocol["population"]["environment_seed"]),
    )
    env = base.create_env(runtime, args)
    shadow_steps = 0
    restore_checks = []
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = _robot_arrays(env)
        injected_index = int(simulator["injected_joint_index"])
        env.sim.data.qpos[qidx[injected_index]] = (
            limits[injected_index, 1]
            - float(simulator["injected_upper_margin_rad"])
        )
        env.sim.data.qvel[vidx] = 0.0
        env.sim.forward()
        _reset_controller(robot)
        injected_state = env.sim.get_state()
        injected_flat = np.asarray(
            injected_state.flatten(), dtype=np.float64
        )
        trusted = trusted_joint_state_from_libero(
            env,
            state_epoch=0,
            source_id=pair["base_pair_id"] + ":injected",
        )
        baseline_model_trigger = bool(robot.check_q_limits())
        candidates = []
        candidate_payloads = []
        horizon = int(simulator["shadow_horizon_steps"])
        for spec in simulator["candidate_library"]:
            restored = _restore(
                env,
                robot,
                injected_state,
                injected_flat,
            )
            restore_checks.append(restored)
            action = np.asarray(spec["action"], dtype=np.float64)
            positions = []
            margins = []
            for _ in range(horizon):
                # The return value is deliberately ignored. No reward, done,
                # success, cost, collision, or task outcome is inspected.
                env.step(action)
                shadow_steps += 1
                qpos = np.asarray(
                    env.sim.data.qpos[qidx], dtype=np.float64
                )
                positions.append(tuple(float(value) for value in qpos))
                margins.append(_minimum_margin(qpos, limits))
            command = tuple(
                float(value)
                for value in np.tile(action, (horizon, 1)).reshape(-1)
            )
            trajectory = ShadowJointTrajectory(
                initial_state_digest=trusted.state_digest,
                action_block_digest=command_digest(command),
                positions=tuple(positions),
                predictor_id=(
                    "libero-restored-shadow-step-v12.1:"
                    + pair["base_pair_id"]
                ),
            )
            hard = (
                ("joint_limit_crossed",)
                if min(margins) < 0
                else ()
            )
            candidate = RecoveryCandidate(
                candidate_id=spec["candidate_id"],
                command=command,
                command_shape=(horizon, 7),
                trajectory=trajectory,
                hard_violation_atoms=hard,
            )
            candidates.append(candidate)
            candidate_payloads.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "command_digest": candidate.command_digest,
                    "minimum_margin": min(margins),
                    "terminal_margin": margins[-1],
                    "joint_limit_crossed": min(margins) < 0,
                    "trajectory_digest": trajectory.trajectory_digest,
                }
            )
        config = EscapeRecoveryConfig(
            trigger_margin_rad=float(
                simulator["trigger_margin_rad"]
            ),
            safe_margin_rad=float(simulator["safe_margin_rad"]),
            required_margin_gain_rad=float(
                simulator["required_margin_gain_rad"]
            ),
            max_transient_margin_loss_rad=float(
                simulator["max_transient_margin_loss_rad"]
            ),
        )
        selection = select_escape_recovery_candidate(
            trusted, tuple(candidates), config=config
        )
        selected = selection.selected
        selected_terminal_model_clear = None
        selected_replay_matches = None
        recovery_completed = None
        old_policy_accepted = None
        recovery_authorization_digest = None
        if selected is not None:
            restored = _restore(
                env,
                robot,
                injected_state,
                injected_flat,
            )
            restore_checks.append(restored)
            replay_positions = []
            for action in np.asarray(selected.command).reshape(-1, 7):
                env.step(action)
                shadow_steps += 1
                replay_positions.append(
                    tuple(
                        float(value)
                        for value in env.sim.data.qpos[qidx]
                    )
                )
            selected_replay_matches = (
                tuple(replay_positions)
                == selected.trajectory.positions
            )
            selected_terminal_model_clear = not bool(
                robot.check_q_limits()
            )
            post_state = trusted_joint_state_from_libero(
                env,
                state_epoch=1,
                source_id=pair["base_pair_id"] + ":recovery-terminal",
            )
            gate = RecoveryTransactionGate(
                safe_margin_rad=float(simulator["safe_margin_rad"])
            )
            old_policy = digest_payload(
                {
                    "base_pair_id": pair["base_pair_id"],
                    "authorization": "revoked-policy",
                }
            )
            authorization = gate.authorize_recovery(
                triggering_policy_authorization_digest=old_policy,
                trigger_state=trusted,
                selection=selection,
                now_ns=100,
            )
            gate.consume_recovery(
                authorization,
                command=selected.command,
                now_ns=101,
            )
            recovery_completed = gate.complete_recovery(post_state)
            old_policy_accepted = gate.policy_authorization_allowed(
                old_policy
            )
            recovery_authorization_digest = (
                authorization.authorization_digest
            )
        evaluations = {
            row.candidate_id: {
                "known": row.known,
                "eligible": row.eligible,
                "minimum_margin": row.minimum_margin,
                "terminal_margin": row.terminal_margin,
                "first_safe_step": row.first_safe_step,
                "reasons": row.reasons,
                "evaluation_digest": row.evaluation_digest,
            }
            for row in selection.evaluations
        }
        return {
            "schema": ROW_SCHEMA,
            **pair,
            "valid": True,
            "trusted_joint_state_digest": trusted.state_digest,
            "baseline_minimum_margin": trusted.minimum_margin,
            "baseline_model_trigger": baseline_model_trigger,
            "candidate_count": len(candidates),
            "candidate_payloads": candidate_payloads,
            "candidate_evaluations": evaluations,
            "selected_candidate_id": (
                selected.candidate_id if selected is not None else None
            ),
            "selected_command_digest": (
                selected.command_digest if selected is not None else None
            ),
            "selected_terminal_safe": (
                selected is not None
                and evaluations[selected.candidate_id][
                    "terminal_margin"
                ]
                >= float(simulator["safe_margin_rad"])
            ),
            "selected_joint_limit_crossed": (
                selected is not None
                and "joint_limit_crossed"
                in evaluations[selected.candidate_id]["reasons"]
            ),
            "selected_transient_loss": (
                selected is not None
                and "transient_margin_loss_exceeded"
                in evaluations[selected.candidate_id]["reasons"]
            ),
            "selected_terminal_model_clear": (
                selected_terminal_model_clear
            ),
            "selected_replay_matches_prediction": (
                selected_replay_matches
            ),
            "recovery_completed": recovery_completed,
            "old_policy_authorization_accepted": old_policy_accepted,
            "recovery_authorization_digest": (
                recovery_authorization_digest
            ),
            "selection_digest": selection.selection_digest,
            "shadow_restore_identity": all(restore_checks),
            "shadow_env_step_count": shadow_steps,
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "outcome_read_count": 0,
        }
    finally:
        env.close()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise SimulatorPreflightError(
            "preflight denominator must be positive"
        )
    return numerator / denominator


def _summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    selected_gpu: dict[str, Any],
) -> dict[str, Any]:
    gates = protocol["gates"]
    suites = sorted({row["suite"] for row in rows})
    suite_coverage = {
        suite: _rate(
            sum(
                row["selected_candidate_id"] is not None
                for row in rows
                if row["suite"] == suite
            ),
            sum(row["suite"] == suite for row in rows),
        )
        for suite in suites
    }
    valid_count = sum(row["valid"] for row in rows)
    selected_rows = [
        row for row in rows if row["selected_candidate_id"] is not None
    ]
    metrics = {
        "valid_pair_count": valid_count,
        "baseline_model_trigger_rate": _rate(
            sum(row["baseline_model_trigger"] for row in rows),
            len(rows),
        ),
        "recovery_candidate_coverage": _rate(
            len(selected_rows), len(rows)
        ),
        "suite_recovery_coverage": suite_coverage,
        "worst_suite_recovery_coverage": min(
            suite_coverage.values()
        ),
        "selected_terminal_safe_rate": (
            _rate(
                sum(row["selected_terminal_safe"] for row in selected_rows),
                len(selected_rows),
            )
            if selected_rows
            else 0.0
        ),
        "selected_joint_limit_crossing_count": sum(
            row["selected_joint_limit_crossed"] for row in selected_rows
        ),
        "selected_transient_loss_count": sum(
            row["selected_transient_loss"] for row in selected_rows
        ),
        "selected_terminal_model_clear_rate": (
            _rate(
                sum(
                    row["selected_terminal_model_clear"]
                    for row in selected_rows
                ),
                len(selected_rows),
            )
            if selected_rows
            else 0.0
        ),
        "selected_replay_identity_rate": (
            _rate(
                sum(
                    row["selected_replay_matches_prediction"]
                    for row in selected_rows
                ),
                len(selected_rows),
            )
            if selected_rows
            else 0.0
        ),
        "recovery_completion_rate": (
            _rate(
                sum(row["recovery_completed"] for row in selected_rows),
                len(selected_rows),
            )
            if selected_rows
            else 0.0
        ),
        "shadow_restore_identity_rate": _rate(
            sum(row["shadow_restore_identity"] for row in rows),
            len(rows),
        ),
        "old_policy_authorization_accept_count": sum(
            bool(row["old_policy_authorization_accepted"])
            for row in selected_rows
        ),
        "shadow_env_step_count": sum(
            row["shadow_env_step_count"] for row in rows
        ),
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
    }
    gate_conditions = {
        "valid_pair_count": metrics["valid_pair_count"]
        >= gates["valid_pair_count_min"],
        "baseline_model_trigger": metrics["baseline_model_trigger_rate"]
        >= gates["baseline_model_trigger_rate_min"],
        "recovery_candidate_coverage": metrics[
            "recovery_candidate_coverage"
        ]
        >= gates["recovery_candidate_coverage_min"],
        "worst_suite_recovery_coverage": metrics[
            "worst_suite_recovery_coverage"
        ]
        >= gates["worst_suite_recovery_coverage_min"],
        "selected_terminal_safe": metrics[
            "selected_terminal_safe_rate"
        ]
        >= gates["selected_terminal_safe_rate_min"],
        "selected_joint_limit_crossing": metrics[
            "selected_joint_limit_crossing_count"
        ]
        <= gates["selected_joint_limit_crossing_count_max"],
        "selected_transient_loss": metrics[
            "selected_transient_loss_count"
        ]
        <= gates["selected_transient_loss_count_max"],
        "shadow_restore_identity": metrics[
            "shadow_restore_identity_rate"
        ]
        >= gates["shadow_restore_identity_rate_min"],
        "old_policy_authorization": metrics[
            "old_policy_authorization_accept_count"
        ]
        <= gates["old_policy_authorization_accept_count_max"],
        "policy_load_count": metrics["policy_load_count"]
        <= gates["policy_load_count_max"],
        "policy_action_dispatch_count": metrics[
            "policy_action_dispatch_count"
        ]
        <= gates["policy_action_dispatch_count_max"],
        "outcome_read_count": metrics["outcome_read_count"]
        <= gates["outcome_read_count_max"],
        "runtime_exception_count": metrics["runtime_exception_count"]
        <= gates["runtime_exception_count_max"],
    }
    passed = all(gate_conditions.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": (
            "escape_recovery_v12_simulator_preflight_pass"
            if passed
            else "escape_recovery_v12_simulator_preflight_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": gate_conditions,
        "selected_gpu": selected_gpu,
        "claim_boundary": protocol["claim_boundary"],
        "execution_boundary": {
            "simulator_create_count": len(rows),
            "shadow_env_step_count": metrics["shadow_env_step_count"],
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "outcome_read_count": 0,
        },
        "lifecycle": {
            "terminal": True,
            "outcome_rollout_authorized": False,
            "clean_rollout_authorized": False,
            "runtime_integration_authorized": passed,
            "next_step": (
                protocol["lifecycle"]["next_step_if_pass"]
                if passed
                else protocol["lifecycle"]["next_step_if_nonpass"]
            ),
        },
    }


def _write_checksums(root: Path) -> None:
    paths = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n" for path in paths
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, required=True)
    args = parser.parse_args()
    protocol = _verify_protocol()
    selected_gpu = _select_gpu(protocol, args.gpu)
    if OUTPUT_ROOT.exists():
        raise SystemExit(
            f"refusing to overwrite preflight root: {OUTPUT_ROOT}"
        )
    _configure_environment(args.gpu)
    from scripts import run_liberosafety_pi05_openpi_eval as base

    OUTPUT_ROOT.mkdir(parents=True)
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    rows = []
    for index, pair in enumerate(protocol["population"]["pairs"]):
        row = _run_pair(
            protocol,
            pair,
            base=base,
            gpu=args.gpu,
        )
        rows.append(row)
        with ledger_path.open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "complete": index + 1,
                    "total": len(protocol["population"]["pairs"]),
                    "base_pair_id": pair["base_pair_id"],
                    "selected": row["selected_candidate_id"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    summary = _summarize(
        protocol, rows, selected_gpu=selected_gpu
    )
    (OUTPUT_ROOT / "summary.json").write_text(_canonical(summary))
    (OUTPUT_ROOT / "run_manifest.json").write_text(
        _canonical(
            {
                "schema": SUMMARY_SCHEMA + ".run-manifest",
                "protocol_id": PROTOCOL_ID,
                "protocol_sha256": _sha256(PROTOCOL_PATH),
                "status": "complete",
                "row_count": len(rows),
                "outcomes_observed": False,
                "policy_loaded": False,
                "policy_action_dispatched": False,
            }
        )
    )
    _write_checksums(OUTPUT_ROOT)
    print(_canonical(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
