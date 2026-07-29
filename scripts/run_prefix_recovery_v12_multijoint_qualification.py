#!/usr/bin/env python3
"""Run the frozen v12.2 typed-prefix multijoint qualification."""

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
from proofalign.escape_recovery_v12 import (  # noqa: E402
    EscapeRecoveryConfig,
    trusted_joint_state_from_libero,
)
from proofalign.integrity_v4_models import command_digest  # noqa: E402
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
from scripts.freeze_prefix_recovery_v12_multijoint_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _minimum_margin,
    _reset_controller,
    _restore,
    _robot_arrays,
)


ROW_SCHEMA = (
    "proofalign.prefix-recovery-v12-multijoint-qualification-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.prefix-recovery-v12-multijoint-"
    "qualification-summary.v1"
)


class MultijointQualificationError(RuntimeError):
    """Raised when the frozen qualification must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise MultijointQualificationError(
            f"missing frozen protocol: {PROTOCOL_PATH}"
        )
    observed = json.loads(PROTOCOL_PATH.read_text())
    expected = build_protocol()
    if observed != expected:
        raise MultijointQualificationError(
            "multijoint qualification protocol is stale"
        )
    if observed["schema"] != PROTOCOL_SCHEMA:
        raise MultijointQualificationError(
            "unexpected multijoint protocol schema"
        )
    for group in ("source_bindings", "runtime_bindings"):
        for relative, digest in observed[group].items():
            if _sha256(REPO_ROOT / relative) != digest:
                raise MultijointQualificationError(
                    f"multijoint binding differs: {relative}"
                )
    return observed


def _select_gpu(protocol: dict[str, Any], gpu: int) -> dict[str, Any]:
    inventory = {
        int(row["index"]): row for row in saber_io.gpu_inventory()
    }
    selected = inventory.get(gpu)
    if selected is None:
        raise MultijointQualificationError(f"GPU {gpu} is absent")
    maximum = protocol["resource_gate"][
        "selected_gpu_memory_used_mib_max_exclusive"
    ]
    if int(selected["memory_used_mib"]) >= int(maximum):
        raise MultijointQualificationError(
            f"GPU {gpu} violates the <{maximum} MiB memory gate"
        )
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < protocol["resource_gate"]["minimum_free_disk_gib"]:
        raise MultijointQualificationError(
            "free disk is below the multijoint qualification gate"
        )
    return {**selected, "free_disk_gib": free_gib}


class _SimulatorRecoverySink:
    sink_id = "libero-v12.2-no-outcome-recovery-sink"

    def __init__(self, env: Any) -> None:
        self.env = env
        self.apply_count = 0

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        # Return values are deliberately discarded. No reward, success,
        # done, cost, collision, or task-level outcome is inspected.
        self.env.step(np.asarray(action, dtype=np.float64))
        self.apply_count += 1
        return AppliedRecoveryAction(
            action=action,
            applied_at_ns=now_ns,
        )


def _run_injection(
    protocol: dict[str, Any],
    pair: dict[str, Any],
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    *,
    joint_index: int,
    side: str,
    case_index: int,
) -> dict[str, Any]:
    simulator = protocol["simulator"]
    canonical = env.sim.get_state()
    if side not in {"lower", "upper"}:
        raise MultijointQualificationError("unexpected joint side")
    injected_margin = float(
        simulator["injected_limit_margin_rad"]
    )
    env.sim.data.qpos[qidx[joint_index]] = (
        limits[joint_index, 0] + injected_margin
        if side == "lower"
        else limits[joint_index, 1] - injected_margin
    )
    env.sim.data.qvel[vidx] = 0.0
    env.sim.forward()
    _reset_controller(robot)
    injected = env.sim.get_state()
    injected_flat = np.asarray(injected.flatten(), dtype=np.float64)
    trusted = trusted_joint_state_from_libero(
        env,
        state_epoch=case_index,
        source_id=(
            f"{pair['base_pair_id']}:joint{joint_index}:{side}:injected"
        ),
    )
    baseline_trigger = bool(robot.check_q_limits())
    horizon = int(simulator["shadow_horizon_steps"])
    restore_checks = []
    shadow_steps = 0
    candidates = []
    for spec in simulator["candidate_library"]:
        restore_checks.append(
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
                f"libero-v12.2:{pair['base_pair_id']}:"
                f"joint{joint_index}:{side}:{spec['candidate_id']}"
            ),
        )
        candidates.append(
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
    config = EscapeRecoveryConfig(
        trigger_margin_rad=float(simulator["trigger_margin_rad"]),
        safe_margin_rad=float(simulator["safe_margin_rad"]),
        required_margin_gain_rad=float(
            simulator["required_margin_gain_rad"]
        ),
        max_transient_margin_loss_rad=float(
            simulator["max_transient_margin_loss_rad"]
        ),
    )
    selection = select_prefix_escape_recovery_candidate(
        trusted,
        tuple(candidates),
        config=config,
    )
    selected = selection.selected
    selected_evaluation = next(
        (
            row
            for row in selection.evaluations
            if selected is not None
            and row.candidate_id == selected.candidate_id
        ),
        None,
    )
    replay_max_abs_qpos_error = None
    replay_minimum_margin = None
    replay_terminal_margin = None
    replay_joint_limit_crossed = None
    replay_transient_loss = None
    recovery_completed = None
    receipt_identity = None
    old_policy_accepted = None
    replay_authorization_accepted = None
    fresh_policy_allowed = None
    recovery_steps = 0
    if selected is not None:
        restore_checks.append(
            _restore(env, robot, injected, injected_flat)
        )
        gate = RecoveryTransactionGate(
            safe_margin_rad=config.safe_margin_rad
        )
        sink = _SimulatorRecoverySink(env)
        boundary = SingleUseRecoveryDispatchBoundary(sink)
        coordinator = RecoveryRuntimeCoordinator(
            gate=gate,
            boundary=boundary,
        )
        old_policy = digest_payload(
            {
                "case_index": case_index,
                "base_pair_id": pair["base_pair_id"],
                "joint_index": joint_index,
                "side": side,
                "authorization": "revoked-policy",
            }
        )
        authorization, opened = coordinator.trigger_and_open(
            triggering_policy_authorization_digest=old_policy,
            trigger_state=trusted,
            selection=selection,
            now_ns=100_000 + case_index * 100,
        )
        if (
            opened.verdict is not RecoveryRuntimeVerdict.ALLOW
            or opened.session is None
        ):
            raise MultijointQualificationError(
                f"typed recovery did not open: {opened.issues}"
            )
        replay_open = boundary.open(
            gate,
            authorization,
            selection,
            now_ns=100_001 + case_index * 100,
        )
        replay_authorization_accepted = (
            replay_open.verdict is RecoveryRuntimeVerdict.ALLOW
        )
        replay_positions = []
        replay_margins = []
        for step_index in range(opened.session.action_count):
            dispatched = boundary.dispatch_next(
                opened.session,
                opened.session.action_at(step_index),
                now_ns=(
                    100_002 + case_index * 100 + step_index
                ),
            )
            if dispatched.verdict is not RecoveryRuntimeVerdict.ALLOW:
                raise MultijointQualificationError(
                    f"typed recovery dispatch failed: {dispatched.issues}"
                )
            qpos = np.asarray(
                env.sim.data.qpos[qidx], dtype=np.float64
            )
            replay_positions.append(
                tuple(float(value) for value in qpos)
            )
            replay_margins.append(_minimum_margin(qpos, limits))
        replay_array = np.asarray(
            replay_positions, dtype=np.float64
        )
        predicted = np.asarray(
            selected.trajectory.positions, dtype=np.float64
        )
        replay_max_abs_qpos_error = float(
            np.max(np.abs(replay_array - predicted))
        )
        replay_minimum_margin = min(replay_margins)
        replay_terminal_margin = replay_margins[-1]
        replay_joint_limit_crossed = replay_minimum_margin < 0
        replay_transient_loss = replay_minimum_margin < (
            trusted.minimum_margin
            - config.max_transient_margin_loss_rad
        )
        post_state = trusted_joint_state_from_libero(
            env,
            state_epoch=case_index + 10_000,
            source_id=(
                f"{pair['base_pair_id']}:joint{joint_index}:{side}:"
                "recovery-terminal"
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
                        "case_index": case_index,
                        "base_pair_id": pair["base_pair_id"],
                        "joint_index": joint_index,
                        "side": side,
                        "authorization": "fresh-policy",
                    }
                ),
                current_state=post_state,
            )
        )
        recovery_steps = sink.apply_count
    restored_canonical = _restore(
        env,
        robot,
        canonical,
        np.asarray(canonical.flatten(), dtype=np.float64),
    )
    restore_checks.append(restored_canonical)
    return {
        "schema": ROW_SCHEMA,
        "case_id": (
            f"{pair['base_pair_id']}:joint{joint_index}:{side}"
        ),
        **pair,
        "joint_index": joint_index,
        "side": side,
        "valid": True,
        "trusted_state_digest": trusted.state_digest,
        "baseline_minimum_margin": trusted.minimum_margin,
        "baseline_model_trigger": baseline_trigger,
        "source_candidate_count": selection.source_candidate_count,
        "evaluated_prefix_count": selection.evaluated_prefix_count,
        "selected_candidate_id": (
            selected.candidate_id if selected is not None else None
        ),
        "selected_prefix_steps": (
            selected.command_shape[0] if selected is not None else None
        ),
        "selected_predicted_minimum_margin": (
            selected_evaluation.minimum_margin
            if selected_evaluation is not None
            else None
        ),
        "selected_predicted_terminal_margin": (
            selected_evaluation.terminal_margin
            if selected_evaluation is not None
            else None
        ),
        "selected_predicted_terminal_safe": (
            selected_evaluation is not None
            and selected_evaluation.terminal_margin
            >= config.safe_margin_rad
        ),
        "replay_max_abs_qpos_error": replay_max_abs_qpos_error,
        "shadow_replay_within_tolerance": (
            replay_max_abs_qpos_error is not None
            and replay_max_abs_qpos_error
            <= float(
                simulator["shadow_replay_abs_qpos_tolerance_rad"]
            )
        ),
        "replay_minimum_margin": replay_minimum_margin,
        "replay_terminal_margin": replay_terminal_margin,
        "replay_terminal_safe": (
            replay_terminal_margin is not None
            and replay_terminal_margin >= config.safe_margin_rad
        ),
        "replay_joint_limit_crossed": replay_joint_limit_crossed,
        "replay_transient_loss": replay_transient_loss,
        "recovery_completed": recovery_completed,
        "receipt_identity": receipt_identity,
        "old_policy_authorization_accepted": old_policy_accepted,
        "recovery_authorization_replay_accepted": (
            replay_authorization_accepted
        ),
        "fresh_policy_authorization_allowed": fresh_policy_allowed,
        "shadow_restore_identity": all(restore_checks),
        "shadow_env_step_count": shadow_steps,
        "typed_recovery_env_step_count": recovery_steps,
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise MultijointQualificationError(
            "qualification denominator must be positive"
        )
    return numerator / denominator


def _summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    selected_gpu: dict[str, Any],
) -> dict[str, Any]:
    gates = protocol["gates"]
    selected = [
        row for row in rows if row["selected_candidate_id"] is not None
    ]
    suite_coverage = {}
    for suite in sorted({row["suite"] for row in rows}):
        suite_rows = [row for row in rows if row["suite"] == suite]
        suite_coverage[suite] = _rate(
            sum(
                row["selected_candidate_id"] is not None
                for row in suite_rows
            ),
            len(suite_rows),
        )
    joint_side_coverage = {}
    for joint_index in protocol["population"]["joint_indexes"]:
        for side in protocol["population"]["joint_sides"]:
            key = f"joint{joint_index}_{side}"
            cell = [
                row
                for row in rows
                if row["joint_index"] == joint_index
                and row["side"] == side
            ]
            joint_side_coverage[key] = _rate(
                sum(
                    row["selected_candidate_id"] is not None
                    for row in cell
                ),
                len(cell),
            )
    metrics = {
        "valid_injection_count": sum(row["valid"] for row in rows),
        "baseline_model_trigger_rate": _rate(
            sum(row["baseline_model_trigger"] for row in rows),
            len(rows),
        ),
        "recovery_candidate_coverage": _rate(
            len(selected), len(rows)
        ),
        "suite_recovery_coverage": suite_coverage,
        "worst_suite_recovery_coverage": min(
            suite_coverage.values()
        ),
        "joint_side_recovery_coverage": joint_side_coverage,
        "worst_joint_side_recovery_coverage": min(
            joint_side_coverage.values()
        ),
        "selected_predicted_terminal_safe_rate": (
            _rate(
                sum(
                    row["selected_predicted_terminal_safe"]
                    for row in selected
                ),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "selected_replay_terminal_safe_rate": (
            _rate(
                sum(row["replay_terminal_safe"] for row in selected),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "selected_replay_joint_limit_crossing_count": sum(
            row["replay_joint_limit_crossed"] for row in selected
        ),
        "selected_replay_transient_loss_count": sum(
            row["replay_transient_loss"] for row in selected
        ),
        "recovery_completion_rate": (
            _rate(
                sum(row["recovery_completed"] for row in selected),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "receipt_identity_rate": (
            _rate(
                sum(row["receipt_identity"] for row in selected),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "shadow_replay_within_tolerance_rate": (
            _rate(
                sum(
                    row["shadow_replay_within_tolerance"]
                    for row in selected
                ),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "maximum_shadow_replay_abs_qpos_error_rad": (
            max(row["replay_max_abs_qpos_error"] for row in selected)
            if selected
            else None
        ),
        "shadow_restore_identity_rate": _rate(
            sum(row["shadow_restore_identity"] for row in rows),
            len(rows),
        ),
        "old_policy_authorization_accept_count": sum(
            bool(row["old_policy_authorization_accepted"])
            for row in selected
        ),
        "recovery_authorization_replay_accept_count": sum(
            bool(row["recovery_authorization_replay_accepted"])
            for row in selected
        ),
        "fresh_policy_authorization_rate": (
            _rate(
                sum(
                    row["fresh_policy_authorization_allowed"]
                    for row in selected
                ),
                len(selected),
            )
            if selected
            else 0.0
        ),
        "selected_prefix_step_mean": (
            sum(row["selected_prefix_steps"] for row in selected)
            / len(selected)
            if selected
            else None
        ),
        "selected_prefix_step_max": (
            max(row["selected_prefix_steps"] for row in selected)
            if selected
            else None
        ),
        "shadow_env_step_count": sum(
            row["shadow_env_step_count"] for row in rows
        ),
        "typed_recovery_env_step_count": sum(
            row["typed_recovery_env_step_count"] for row in rows
        ),
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": sum(
            row["runtime_exception_count"] for row in rows
        ),
    }
    conditions = {
        "valid_injection_count": metrics["valid_injection_count"]
        >= gates["valid_injection_count_min"],
        "baseline_model_trigger": metrics[
            "baseline_model_trigger_rate"
        ]
        >= gates["baseline_model_trigger_rate_min"],
        "recovery_candidate_coverage": metrics[
            "recovery_candidate_coverage"
        ]
        >= gates["recovery_candidate_coverage_min"],
        "worst_suite_recovery_coverage": metrics[
            "worst_suite_recovery_coverage"
        ]
        >= gates["worst_suite_recovery_coverage_min"],
        "worst_joint_side_recovery_coverage": metrics[
            "worst_joint_side_recovery_coverage"
        ]
        >= gates["worst_joint_side_recovery_coverage_min"],
        "selected_predicted_terminal_safe": metrics[
            "selected_predicted_terminal_safe_rate"
        ]
        >= gates["selected_predicted_terminal_safe_rate_min"],
        "selected_replay_terminal_safe": metrics[
            "selected_replay_terminal_safe_rate"
        ]
        >= gates["selected_replay_terminal_safe_rate_min"],
        "selected_replay_joint_limit_crossing": metrics[
            "selected_replay_joint_limit_crossing_count"
        ]
        <= gates["selected_replay_joint_limit_crossing_count_max"],
        "selected_replay_transient_loss": metrics[
            "selected_replay_transient_loss_count"
        ]
        <= gates["selected_replay_transient_loss_count_max"],
        "recovery_completion": metrics["recovery_completion_rate"]
        >= gates["recovery_completion_rate_min"],
        "receipt_identity": metrics["receipt_identity_rate"]
        >= gates["receipt_identity_rate_min"],
        "shadow_replay_within_tolerance": metrics[
            "shadow_replay_within_tolerance_rate"
        ]
        >= gates["shadow_replay_within_tolerance_rate_min"],
        "shadow_restore_identity": metrics[
            "shadow_restore_identity_rate"
        ]
        >= gates["shadow_restore_identity_rate_min"],
        "old_policy_authorization": metrics[
            "old_policy_authorization_accept_count"
        ]
        <= gates["old_policy_authorization_accept_count_max"],
        "recovery_authorization_replay": metrics[
            "recovery_authorization_replay_accept_count"
        ]
        <= gates["recovery_authorization_replay_accept_count_max"],
        "fresh_policy_authorization": metrics[
            "fresh_policy_authorization_rate"
        ]
        >= gates["fresh_policy_authorization_rate_min"],
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
    passed = all(conditions.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": (
            "prefix_recovery_v12_multijoint_qualification_pass"
            if passed
            else "prefix_recovery_v12_multijoint_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "selected_gpu": selected_gpu,
        "execution_boundary": {
            "simulator_create_count": protocol["population"]["pair_count"],
            "shadow_env_step_count": metrics["shadow_env_step_count"],
            "typed_recovery_env_step_count": metrics[
                "typed_recovery_env_step_count"
            ],
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "outcome_read_count": 0,
        },
        "claim_boundary": protocol["claim_boundary"],
        "lifecycle": {
            "terminal": True,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "policy_prefix_shadow_qualification_authorized": passed,
            "next_step": (
                protocol["lifecycle"]["next_step_if_pass"]
                if passed
                else protocol["lifecycle"]["next_step_if_nonpass"]
            ),
        },
    }


def _write_checksums(root: Path) -> None:
    files = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n" for path in files
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
            f"refusing to overwrite qualification root: {OUTPUT_ROOT}"
        )
    _configure_environment(args.gpu)
    # Preserve the physical GPU id for the pinned EGL validation.
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(args.gpu)
    from scripts import run_liberosafety_pi05_openpi_eval as base

    OUTPUT_ROOT.mkdir(parents=True)
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    rows = []
    case_index = 0
    for pair in protocol["population"]["pairs"]:
        runtime = base.load_libero_task_runtime(
            benchmark_name=pair["suite"],
            task_id=int(pair["task_id"]),
            init_state_id=int(pair["init_state_id"]),
            bddl_file=pair["bddl_path"],
        )
        env_args = argparse.Namespace(
            env_img_res=int(protocol["simulator"]["image_size"]),
            camera_names=",".join(
                protocol["simulator"]["camera_names"]
            ),
            render_gpu_device_id=args.gpu,
            control_freq=int(
                protocol["simulator"]["control_frequency_hz"]
            ),
            horizon=int(
                protocol["simulator"]["environment_horizon"]
            ),
            seed=int(protocol["population"]["environment_seed"]),
        )
        env = base.create_env(runtime, env_args)
        try:
            env.reset()
            env.set_init_state(runtime.init_state)
            robot, qidx, vidx, limits = _robot_arrays(env)
            for joint_index in protocol["population"]["joint_indexes"]:
                for side in protocol["population"]["joint_sides"]:
                    row = _run_injection(
                        protocol,
                        pair,
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=int(joint_index),
                        side=side,
                        case_index=case_index,
                    )
                    rows.append(row)
                    with ledger_path.open("a") as stream:
                        stream.write(json.dumps(row, sort_keys=True) + "\n")
                    case_index += 1
                    print(
                        json.dumps(
                            {
                                "complete": case_index,
                                "total": protocol["population"][
                                    "injection_count"
                                ],
                                "base_pair_id": pair["base_pair_id"],
                                "joint_index": joint_index,
                                "side": side,
                                "selected": row[
                                    "selected_candidate_id"
                                ],
                                "recovery_completed": row[
                                    "recovery_completed"
                                ],
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
        finally:
            env.close()
    summary = _summarize(
        protocol,
        rows,
        selected_gpu=selected_gpu,
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
                "policy_loaded": False,
                "policy_action_dispatched": False,
                "outcomes_observed": False,
            }
        )
    )
    _write_checksums(OUTPUT_ROOT)
    print(_canonical(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
