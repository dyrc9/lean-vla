#!/usr/bin/env python3
"""Outcome-blind one-task pilot over all LIBERO arm joint limit sides.

This engineering pilot is intentionally not a qualification protocol.  It
measures whether the already frozen 13-action v12.1 primitive library has any
candidate for each of 7 joints x lower/upper synthetic near-limit states.
The selected pilot identity must be disclosed and excluded from the later
qualification population.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.escape_recovery_v12 import (  # noqa: E402
    EscapeRecoveryConfig,
    select_escape_recovery_candidate,
    trusted_joint_state_from_libero,
)
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.digests import digest_payload  # noqa: E402
from proofalign.prefix_escape_recovery_v12 import (  # noqa: E402
    select_prefix_escape_recovery_candidate,
)
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    RecoveryTransactionGate,
    ShadowJointTrajectory,
)
from proofalign.recovery_runtime_v12 import (  # noqa: E402
    AppliedRecoveryAction,
    RecoveryRuntimeCoordinator,
    RecoveryRuntimeVerdict,
    SingleUseRecoveryDispatchBoundary,
)
from scripts import saber_io  # noqa: E402
from scripts.freeze_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    build_protocol as build_v12_1_protocol,
)
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _minimum_margin,
    _reset_controller,
    _restore,
    _robot_arrays,
)


OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_escape_recovery_v12_multijoint_"
    "typed_prefix_engineering_pilot_20260729"
)
PILOT_PAIR = {
    "base_pair_id": "human_safety_task0_init2_multijoint_pilot",
    "suite": "human_safety",
    "task_id": 0,
    "init_state_id": 2,
    "bddl_path": (
        "external/LIBERO-Safety/libero/libero/bddl_files/human_safety/L0/"
        "pick_the_akita_black_bowl_next_to_the_cookies_box_and_bring_it_"
        "for_me.bddl"
    ),
}


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _select_gpu(gpu: int) -> dict[str, Any]:
    inventory = {
        int(row["index"]): row for row in saber_io.gpu_inventory()
    }
    selected = inventory.get(gpu)
    if selected is None:
        raise RuntimeError(f"GPU {gpu} is absent")
    if int(selected["memory_used_mib"]) >= 30000:
        raise RuntimeError("pilot GPU violates the <30000 MiB gate")
    return selected


class _SimulatorRecoverySink:
    sink_id = "libero-no-outcome-recovery-pilot-sink"

    def __init__(self, env: Any) -> None:
        self.env = env
        self.apply_count = 0

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        # Deliberately discard reward, done, info, success, cost, collision,
        # and every task-level outcome returned by the wrapper.
        self.env.step(np.asarray(action, dtype=np.float64))
        self.apply_count += 1
        return AppliedRecoveryAction(
            action=action,
            applied_at_ns=now_ns,
        )


def _run_injection(
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    *,
    joint_index: int,
    side: str,
    candidates: list[dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    if side not in {"lower", "upper"}:
        raise RuntimeError("unexpected joint side")
    canonical = env.sim.get_state()
    env.sim.data.qpos[qidx[joint_index]] = (
        limits[joint_index, 0] + 0.05
        if side == "lower"
        else limits[joint_index, 1] - 0.05
    )
    env.sim.data.qvel[vidx] = 0.0
    env.sim.forward()
    _reset_controller(robot)
    injected = env.sim.get_state()
    injected_flat = np.asarray(injected.flatten(), dtype=np.float64)
    trusted = trusted_joint_state_from_libero(
        env,
        state_epoch=joint_index * 2 + int(side == "upper"),
        source_id=(
            f"{PILOT_PAIR['base_pair_id']}:joint{joint_index}:{side}"
        ),
    )
    model_trigger = bool(robot.check_q_limits())
    recovery_candidates = []
    restore_identity = []
    shadow_steps = 0
    for spec in candidates:
        restore_identity.append(
            _restore(env, robot, injected, injected_flat)
        )
        action = np.asarray(spec["action"], dtype=np.float64)
        positions = []
        margins = []
        for _ in range(horizon):
            env.step(action)
            shadow_steps += 1
            qpos = np.asarray(env.sim.data.qpos[qidx], dtype=np.float64)
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
                "multijoint-engineering-pilot:"
                f"joint{joint_index}:{side}"
            ),
        )
        recovery_candidates.append(
            RecoveryCandidate(
                candidate_id=spec["candidate_id"],
                command=command,
                command_shape=(horizon, 7),
                trajectory=trajectory,
                hard_violation_atoms=(
                    ("joint_limit_crossed",)
                    if min(margins) < 0
                    else ()
                ),
            )
        )
    selection = select_prefix_escape_recovery_candidate(
        trusted,
        tuple(recovery_candidates),
        config=EscapeRecoveryConfig(),
    )
    selected_evaluation = next(
        (
            row
            for row in selection.evaluations
            if selection.selected is not None
            and row.candidate_id == selection.selected.candidate_id
        ),
        None,
    )
    replay_max_abs_qpos_error = None
    replay_terminal_margin = None
    recovery_completed = None
    receipt_identity = None
    old_policy_accepted = None
    fresh_policy_allowed = None
    recovery_sink_apply_count = 0
    if selection.selected is not None:
        restore_identity.append(
            _restore(env, robot, injected, injected_flat)
        )
        gate = RecoveryTransactionGate(
            safe_margin_rad=EscapeRecoveryConfig().safe_margin_rad
        )
        sink = _SimulatorRecoverySink(env)
        boundary = SingleUseRecoveryDispatchBoundary(sink)
        coordinator = RecoveryRuntimeCoordinator(
            gate=gate,
            boundary=boundary,
        )
        old_policy = digest_payload(
            {
                "pilot": PILOT_PAIR["base_pair_id"],
                "joint_index": joint_index,
                "side": side,
                "authorization": "revoked-policy",
            }
        )
        authorization, opened = coordinator.trigger_and_open(
            triggering_policy_authorization_digest=old_policy,
            trigger_state=trusted,
            selection=selection,
            now_ns=10_000,
        )
        if (
            opened.verdict is not RecoveryRuntimeVerdict.ALLOW
            or opened.session is None
        ):
            raise RuntimeError("typed recovery pilot failed to open")
        replay_positions = []
        for step_index in range(opened.session.action_count):
            result = boundary.dispatch_next(
                opened.session,
                opened.session.action_at(step_index),
                now_ns=10_001 + step_index,
            )
            if result.verdict is not RecoveryRuntimeVerdict.ALLOW:
                raise RuntimeError(
                    f"typed recovery pilot dispatch failed: {result.issues}"
                )
            replay_positions.append(
                tuple(
                    float(value)
                    for value in env.sim.data.qpos[qidx]
                )
            )
        replay = np.asarray(replay_positions, dtype=np.float64)
        predicted = np.asarray(
            selection.selected.trajectory.positions,
            dtype=np.float64,
        )
        replay_max_abs_qpos_error = float(
            np.max(np.abs(replay - predicted))
        )
        replay_terminal_margin = _minimum_margin(
            replay[-1], limits
        )
        post_state = trusted_joint_state_from_libero(
            env,
            state_epoch=trusted.state_epoch + 100,
            source_id=(
                f"{PILOT_PAIR['base_pair_id']}:joint{joint_index}:"
                f"{side}:recovery-terminal"
            ),
        )
        recovery_completed = coordinator.complete_recovery(
            opened.session,
            post_state,
        )
        receipt_identity = (
            len(opened.session.receipts)
            == opened.session.action_count
            and all(
                receipt.step_index == index
                and receipt.applied_action
                == opened.session.action_at(index)
                and receipt.recovery_authorization_digest
                == authorization.authorization_digest
                for index, receipt in enumerate(
                    opened.session.receipts
                )
            )
        )
        old_policy_accepted = gate.policy_authorization_allowed(
            old_policy
        )
        fresh_policy_allowed = (
            coordinator.fresh_policy_authorization_allowed(
                digest_payload(
                    {
                        "pilot": PILOT_PAIR["base_pair_id"],
                        "joint_index": joint_index,
                        "side": side,
                        "authorization": "fresh-policy",
                    }
                ),
                current_state=post_state,
            )
        )
        recovery_sink_apply_count = sink.apply_count
    env.sim.set_state(canonical)
    env.sim.forward()
    _reset_controller(robot)
    return {
        "joint_index": joint_index,
        "side": side,
        "valid": True,
        "baseline_margin": trusted.minimum_margin,
        "baseline_model_trigger": model_trigger,
        "selected_candidate_id": (
            selection.selected.candidate_id
            if selection.selected is not None
            else None
        ),
        "selected_minimum_margin": (
            selected_evaluation.minimum_margin
            if selected_evaluation is not None
            else None
        ),
        "selected_terminal_margin": (
            selected_evaluation.terminal_margin
            if selected_evaluation is not None
            else None
        ),
        "replay_max_abs_qpos_error": replay_max_abs_qpos_error,
        "replay_terminal_margin": replay_terminal_margin,
        "recovery_completed": recovery_completed,
        "receipt_identity": receipt_identity,
        "old_policy_authorization_accepted": old_policy_accepted,
        "fresh_policy_authorization_allowed": fresh_policy_allowed,
        "recovery_sink_apply_count": recovery_sink_apply_count,
        "eligible_candidate_ids": [
            row.candidate_id
            for row in selection.evaluations
            if row.eligible
        ],
        "rejection_reasons": {
            row.candidate_id: row.reasons
            for row in selection.evaluations
            if not row.eligible
        },
        "restore_identity": all(restore_identity),
        "shadow_env_step_count": shadow_steps,
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, required=True)
    args = parser.parse_args()
    if OUTPUT_ROOT.exists():
        raise SystemExit(f"refusing to overwrite pilot: {OUTPUT_ROOT}")
    selected_gpu = _select_gpu(args.gpu)
    frozen = build_v12_1_protocol()
    candidates = frozen["simulator"]["candidate_library"]
    horizon = int(frozen["simulator"]["shadow_horizon_steps"])
    _configure_environment(args.gpu)
    from scripts import run_liberosafety_pi05_openpi_eval as base

    runtime = base.load_libero_task_runtime(
        benchmark_name=PILOT_PAIR["suite"],
        task_id=PILOT_PAIR["task_id"],
        init_state_id=PILOT_PAIR["init_state_id"],
        bddl_file=PILOT_PAIR["bddl_path"],
    )
    env_args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=args.gpu,
        control_freq=20,
        # One environment is deliberately reused across 14 synthetic
        # injections and 13 x 10-step shadow candidates.  Keep the wrapper
        # horizon above that engineering-only total so restored simulator
        # states are not confused with task-episode termination.
        horizon=100_000,
        seed=433,
    )
    env = base.create_env(runtime, env_args)
    rows = []
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = _robot_arrays(env)
        for joint_index in range(len(qidx)):
            for side in ("lower", "upper"):
                row = _run_injection(
                    env,
                    robot,
                    qidx,
                    vidx,
                    limits,
                    joint_index=joint_index,
                    side=side,
                    candidates=candidates,
                    horizon=horizon,
                )
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "joint_index": joint_index,
                            "side": side,
                            "selected": row["selected_candidate_id"],
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    finally:
        env.close()
    covered = sum(
        row["selected_candidate_id"] is not None for row in rows
    )
    summary = {
        "schema": (
            "proofalign.escape-recovery-v12-multijoint-"
            "typed-prefix-pilot.v1"
        ),
        "classification": (
            "multijoint_pilot_full_coverage"
            if covered == len(rows)
            else "multijoint_pilot_partial_coverage"
        ),
        "pilot_pair": PILOT_PAIR,
        "selected_gpu": selected_gpu,
        "candidate_count": len(candidates),
        "shadow_horizon_steps": horizon,
        "joint_side_count": len(rows),
        "covered_joint_side_count": covered,
        "coverage": covered / len(rows),
        "rows": rows,
        "execution_boundary": {
            "simulator_create_count": 1,
            "shadow_env_step_count": sum(
                row["shadow_env_step_count"] for row in rows
            ),
            "recovery_sink_apply_count": sum(
                row["recovery_sink_apply_count"] for row in rows
            ),
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "outcome_read_count": 0,
        },
        "claim_boundary": (
            "Outcome-blind engineering pilot on one disclosed task/init. "
            "Used only to design a separately frozen multijoint successor; "
            "not qualification or efficacy evidence."
        ),
        "source": {
            "script": str(Path(__file__).relative_to(REPO_ROOT)),
            "script_sha256": _sha256(Path(__file__)),
            "v12_1_protocol_sha256": _sha256(
                REPO_ROOT
                / "experiments"
                / "proofalign_escape_recovery_v12_"
                "simulator_preflight_protocol.json"
            ),
        },
    }
    OUTPUT_ROOT.mkdir(parents=True)
    (OUTPUT_ROOT / "pilot.json").write_text(_canonical(summary))
    (OUTPUT_ROOT / "ledger.jsonl").write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows
        )
    )
    print(_canonical(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
