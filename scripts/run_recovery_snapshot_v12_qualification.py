#!/usr/bin/env python3
"""Run the frozen v12.3 recovery snapshot-boundary qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.simulator_snapshot_v12 import (  # noqa: E402
    capture_simulator_snapshot,
    restore_simulator_snapshot,
)
from scripts import saber_io  # noqa: E402
from scripts.freeze_recovery_snapshot_v12_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _reset_controller,
    _robot_arrays,
)


ROW_SCHEMA = "proofalign.recovery-snapshot-v12-qualification-row.v1"
SUMMARY_SCHEMA = (
    "proofalign.recovery-snapshot-v12-qualification-summary.v1"
)


class SnapshotQualificationError(RuntimeError):
    """Raised when the v12.3 qualification must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise SnapshotQualificationError(
            f"missing frozen protocol: {PROTOCOL_PATH}"
        )
    observed = json.loads(PROTOCOL_PATH.read_text())
    expected = build_protocol()
    if observed != expected:
        raise SnapshotQualificationError(
            "v12.3 snapshot protocol is stale"
        )
    if observed["schema"] != PROTOCOL_SCHEMA:
        raise SnapshotQualificationError(
            "unexpected v12.3 snapshot protocol schema"
        )
    for group in ("source_bindings", "runtime_bindings"):
        for relative, digest in observed[group].items():
            if _sha256(REPO_ROOT / relative) != digest:
                raise SnapshotQualificationError(
                    f"v12.3 binding differs: {relative}"
                )
    return observed


def _select_gpu(protocol: dict[str, Any], gpu: int) -> dict[str, Any]:
    inventory = {
        int(row["index"]): row for row in saber_io.gpu_inventory()
    }
    selected = inventory.get(gpu)
    if selected is None:
        raise SnapshotQualificationError(f"GPU {gpu} is absent")
    maximum = protocol["resource_gate"][
        "selected_gpu_memory_used_mib_max_exclusive"
    ]
    if int(selected["memory_used_mib"]) >= int(maximum):
        raise SnapshotQualificationError(
            f"GPU {gpu} violates the <{maximum} MiB memory gate"
        )
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < protocol["resource_gate"]["minimum_free_disk_gib"]:
        raise SnapshotQualificationError(
            "free disk is below the v12.3 gate"
        )
    return {**selected, "free_disk_gib": free_gib}


def _run_case(
    protocol: dict[str, Any],
    pair: dict[str, Any],
    case: dict[str, Any],
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
) -> dict[str, Any]:
    harness_snapshot = capture_simulator_snapshot(
        env,
        arm_qpos_indexes=qidx,
        arm_qvel_indexes=vidx,
        source_id=case["case_id"] + ":harness",
    )
    joint_index = int(case["joint_index"])
    side = case["side"]
    margin = float(protocol["probe"]["injected_limit_margin_rad"])
    env.sim.data.qpos[qidx[joint_index]] = (
        limits[joint_index, 0] + margin
        if side == "lower"
        else limits[joint_index, 1] - margin
    )
    env.sim.data.qvel[vidx] = 0.0
    env.sim.forward()
    _reset_controller(robot)
    trigger_snapshot = capture_simulator_snapshot(
        env,
        arm_qpos_indexes=qidx,
        arm_qvel_indexes=vidx,
        source_id=case["case_id"] + ":trigger",
    )
    baseline_trigger = bool(robot.check_q_limits())
    selected_id = case["selected_candidate_id"]
    if selected_id is None:
        action = protocol["probe"]["fallback_probe_action"]
        steps = 1
    else:
        primitive_id = selected_id.split("@h", 1)[0]
        action = protocol["probe"]["candidate_actions"][primitive_id]
        steps = int(case["selected_prefix_steps"])
    for _ in range(steps):
        # This is a snapshot probe only. The wrapper return is deliberately
        # discarded without inspecting task outcomes.
        env.step(np.asarray(action, dtype=np.float64))
    trigger_restore = restore_simulator_snapshot(
        env, robot, trigger_snapshot
    )
    harness_restore = restore_simulator_snapshot(
        env, robot, harness_snapshot
    )
    return {
        "schema": ROW_SCHEMA,
        "case_id": case["case_id"],
        "base_pair_id": pair["base_pair_id"],
        "suite": pair["suite"],
        "task_id": pair["task_id"],
        "init_state_id": pair["init_state_id"],
        "joint_index": joint_index,
        "side": side,
        "selected_candidate_id": selected_id,
        "probe_step_count": steps,
        "valid": True,
        "baseline_model_trigger": baseline_trigger,
        "trigger_snapshot_digest": trigger_snapshot.snapshot_digest,
        "trigger_full_state_bitwise_identity": (
            trigger_restore.full_state_bitwise_identity
        ),
        "trigger_trusted_arm_bitwise_identity": (
            trigger_restore.trusted_arm_bitwise_identity
        ),
        "trigger_full_state_max_abs_error": (
            trigger_restore.full_state_max_abs_error
        ),
        "trigger_full_state_differing_value_count": (
            trigger_restore.full_state_differing_value_count
        ),
        "harness_snapshot_digest": harness_snapshot.snapshot_digest,
        "harness_full_state_bitwise_identity": (
            harness_restore.full_state_bitwise_identity
        ),
        "harness_trusted_arm_bitwise_identity": (
            harness_restore.trusted_arm_bitwise_identity
        ),
        "harness_full_state_max_abs_error": (
            harness_restore.full_state_max_abs_error
        ),
        "harness_full_state_differing_value_count": (
            harness_restore.full_state_differing_value_count
        ),
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise SnapshotQualificationError(
            "snapshot denominator must be positive"
        )
    return numerator / denominator


def _summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    selected_gpu: dict[str, Any],
) -> dict[str, Any]:
    gates = protocol["gates"]
    metrics = {
        "valid_case_count": sum(row["valid"] for row in rows),
        "baseline_model_trigger_rate": _rate(
            sum(row["baseline_model_trigger"] for row in rows),
            len(rows),
        ),
        "trigger_full_state_bitwise_identity_rate": _rate(
            sum(
                row["trigger_full_state_bitwise_identity"]
                for row in rows
            ),
            len(rows),
        ),
        "trigger_trusted_arm_bitwise_identity_rate": _rate(
            sum(
                row["trigger_trusted_arm_bitwise_identity"]
                for row in rows
            ),
            len(rows),
        ),
        "harness_full_state_bitwise_identity_rate": _rate(
            sum(
                row["harness_full_state_bitwise_identity"]
                for row in rows
            ),
            len(rows),
        ),
        "harness_trusted_arm_bitwise_identity_rate": _rate(
            sum(
                row["harness_trusted_arm_bitwise_identity"]
                for row in rows
            ),
            len(rows),
        ),
        "trigger_full_state_max_abs_error": max(
            row["trigger_full_state_max_abs_error"] for row in rows
        ),
        "harness_full_state_max_abs_error": max(
            row["harness_full_state_max_abs_error"] for row in rows
        ),
        "trigger_full_state_differing_value_count": sum(
            row["trigger_full_state_differing_value_count"]
            for row in rows
        ),
        "harness_full_state_differing_value_count": sum(
            row["harness_full_state_differing_value_count"]
            for row in rows
        ),
        "probe_env_step_count": sum(
            row["probe_step_count"] for row in rows
        ),
        "simulator_create_count": protocol["population"]["pair_count"],
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": sum(
            row["runtime_exception_count"] for row in rows
        ),
    }
    conditions = {
        "valid_case_count": metrics["valid_case_count"]
        >= gates["valid_case_count_min"],
        "baseline_model_trigger": metrics[
            "baseline_model_trigger_rate"
        ]
        >= gates["baseline_model_trigger_rate_min"],
        "trigger_full_state_bitwise_identity": metrics[
            "trigger_full_state_bitwise_identity_rate"
        ]
        >= gates["trigger_full_state_bitwise_identity_rate_min"],
        "trigger_trusted_arm_bitwise_identity": metrics[
            "trigger_trusted_arm_bitwise_identity_rate"
        ]
        >= gates["trigger_trusted_arm_bitwise_identity_rate_min"],
        "harness_trusted_arm_bitwise_identity": metrics[
            "harness_trusted_arm_bitwise_identity_rate"
        ]
        >= gates["harness_trusted_arm_bitwise_identity_rate_min"],
        "runtime_exception_count": metrics["runtime_exception_count"]
        <= gates["runtime_exception_count_max"],
        "policy_load_count": metrics["policy_load_count"]
        <= gates["policy_load_count_max"],
        "policy_action_dispatch_count": metrics[
            "policy_action_dispatch_count"
        ]
        <= gates["policy_action_dispatch_count_max"],
        "outcome_read_count": metrics["outcome_read_count"]
        <= gates["outcome_read_count_max"],
    }
    passed = all(conditions.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": (
            "recovery_snapshot_v12_qualification_pass"
            if passed
            else "recovery_snapshot_v12_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "selected_gpu": selected_gpu,
        "predecessor_positive_metrics": protocol[
            "predecessor_evidence"
        ]["positive_metrics_reused_without_reclassification"],
        "execution_boundary": {
            "simulator_create_count": metrics[
                "simulator_create_count"
            ],
            "probe_env_step_count": metrics["probe_env_step_count"],
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "outcome_read_count": 0,
        },
        "claim_boundary": protocol["claim_boundary"],
        "lifecycle": {
            "terminal": True,
            "v12_2_nonpass_unchanged": True,
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
            f"refusing to overwrite snapshot root: {OUTPUT_ROOT}"
        )
    _configure_environment(args.gpu)
    from scripts import run_liberosafety_pi05_openpi_eval as base

    OUTPUT_ROOT.mkdir(parents=True)
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    cases_by_pair: dict[str, list[dict[str, Any]]] = {}
    for case in protocol["population"]["cases"]:
        cases_by_pair.setdefault(case["base_pair_id"], []).append(case)
    rows = []
    complete = 0
    for pair in protocol["population"]["pairs"]:
        runtime = base.load_libero_task_runtime(
            benchmark_name=pair["suite"],
            task_id=int(pair["task_id"]),
            init_state_id=int(pair["init_state_id"]),
            bddl_file=pair["bddl_path"],
        )
        env_args = argparse.Namespace(
            env_img_res=int(protocol["probe"]["image_size"]),
            camera_names=",".join(protocol["probe"]["camera_names"]),
            render_gpu_device_id=args.gpu,
            control_freq=int(
                protocol["probe"]["control_frequency_hz"]
            ),
            horizon=int(protocol["probe"]["environment_horizon"]),
            seed=int(protocol["population"]["environment_seed"]),
        )
        env = base.create_env(runtime, env_args)
        try:
            env.reset()
            env.set_init_state(runtime.init_state)
            robot, qidx, vidx, limits = _robot_arrays(env)
            for case in cases_by_pair[pair["base_pair_id"]]:
                row = _run_case(
                    protocol,
                    pair,
                    case,
                    env,
                    robot,
                    qidx,
                    vidx,
                    limits,
                )
                rows.append(row)
                with ledger_path.open("a") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                complete += 1
                print(
                    json.dumps(
                        {
                            "complete": complete,
                            "total": protocol["population"]["case_count"],
                            "case_id": case["case_id"],
                            "trigger_full": row[
                                "trigger_full_state_bitwise_identity"
                            ],
                            "harness_arm": row[
                                "harness_trusted_arm_bitwise_identity"
                            ],
                            "harness_full": row[
                                "harness_full_state_bitwise_identity"
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
