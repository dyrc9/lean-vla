#!/usr/bin/env python3
"""Run controller-shadow qualification over frozen executed policy prefixes."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from proofalign.escape_recovery_v12 import (  # noqa: E402
    trusted_joint_state_from_libero,
)
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    PolicyPrefixShadowVerdict,
    capture_policy_shadow_snapshot,
    decide_policy_prefix_shadow,
    restore_policy_shadow_snapshot,
)
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    ShadowJointTrajectory,
    assess_shadow_joint_trajectory,
)
from scripts import saber_io  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as runner  # noqa: E402
from scripts import run_saber_threat_validation_r5 as result_io  # noqa: E402
from scripts.freeze_fixed_policy_prefix_shadow_v12_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)
from scripts.generate_fixed_policy_prefix_v12_corpus import (  # noqa: E402
    CORPUS_PATH,
)
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _reset_controller,
    _robot_arrays,
)
from scripts.run_policy_prefix_shadow_v12_qualification import (  # noqa: E402
    ROW_SCHEMA,
    _aggregate_metrics,
    _minimum_margin,
    _snapshot_payload,
)


SUMMARY_SCHEMA = (
    "proofalign.fixed-policy-prefix-shadow-v12-qualification-summary.v1"
)
PILOT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "engineering_pilot_20260729_fresh2"
)
REQUIRED_INTERPRETER = REPO_ROOT / ".venv/bin/python"


class FixedPolicyPrefixShadowError(RuntimeError):
    """Raised when the fixed-prefix qualification must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise FixedPolicyPrefixShadowError(
            f"expected JSON object: {path}"
        )
    return payload


def _args(
    entry: dict[str, Any],
    config: dict[str, Any],
    *,
    output_root: Path,
    gpu: int,
) -> SimpleNamespace:
    episode = config["episode"]
    return SimpleNamespace(
        checkpoint_dir=Path("/unused/fixed-prefix"),
        output_dir=output_root,
        seed=int(entry["environment_seed"]),
        render_gpu_device_id=gpu,
        camera_names="agentview,robot0_eye_in_hand",
        env_img_res=256,
        resize_size=224,
        control_freq=int(episode["control_frequency_hz"]),
        horizon=int(episode["environment_horizon"]),
    )


def _replay(
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    snapshot: Any,
    prefix: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    restores = [
        _snapshot_payload(
            restore_policy_shadow_snapshot(env, robot, snapshot)
        )
    ]
    positions = []
    for action in prefix:
        env.step(np.asarray(action, dtype=np.float64))
        positions.append(
            np.asarray(env.sim.data.qpos[qidx], dtype=np.float64)
        )
    restores.append(
        _snapshot_payload(
            restore_policy_shadow_snapshot(env, robot, snapshot)
        )
    )
    return np.asarray(positions), restores


def _run_case(
    config: dict[str, Any],
    entry: dict[str, Any],
    *,
    condition: str,
    case_index: int,
    gpu: int,
    output_root: Path,
) -> dict[str, Any]:
    runtime = runner.load_libero_task_runtime(
        benchmark_name=entry["suite"],
        task_id=int(entry["task_id"]),
        init_state_id=int(entry["init_state_id"]),
        bddl_file=entry["bddl_path"],
    )
    args = _args(
        entry, config, output_root=output_root, gpu=gpu
    )
    env = runner.create_env(runtime, args)
    try:
        env.reset()
        obs = (
            env.set_init_state(runtime.init_state)
            if runtime.init_state is not None
            else None
        )
        if obs is None:
            runner.get_observation(env)
        if (
            runner.array_digest(runtime.init_state)
            != entry["source_initial_state_sha256"]
        ):
            raise FixedPolicyPrefixShadowError(
                "runtime initial state differs from source trace"
            )
        for _ in range(int(config["episode"]["stabilization_steps"])):
            env.step(runner.LIBERO_DUMMY_ACTION)
        robot, qidx, vidx, limits = _robot_arrays(env)
        _reset_controller(robot)
        injected_joint = None
        injected_side = None
        if condition == "synthetic_joint_pressure":
            injected_joint = int(entry["synthetic_joint_index"])
            injected_side = str(entry["synthetic_joint_side"])
            margin = float(
                config["episode"]["synthetic_injected_margin_rad"]
            )
            env.sim.data.qpos[qidx[injected_joint]] = (
                limits[injected_joint, 0] + margin
                if injected_side == "lower"
                else limits[injected_joint, 1] - margin
            )
            env.sim.data.qvel[vidx] = 0.0
            env.sim.forward()
            _reset_controller(robot)
        elif condition != "nominal":
            raise FixedPolicyPrefixShadowError(
                f"unexpected condition: {condition}"
            )
        prefix = np.asarray(
            entry["executed_prefix"], dtype=np.float64
        )
        if prefix.shape != (10, 7) or not np.isfinite(prefix).all():
            raise FixedPolicyPrefixShadowError(
                "fixed executed prefix is malformed"
            )
        command = tuple(float(value) for value in prefix.reshape(-1))
        prefix_digest = command_digest(command)
        if prefix_digest != entry["executed_prefix_digest"]:
            raise FixedPolicyPrefixShadowError(
                "fixed executed prefix digest differs"
            )
        trusted = trusted_joint_state_from_libero(
            env,
            state_epoch=case_index,
            source_id=(
                f"v12.4a:{entry['base_pair_id']}:{condition}:"
                f"trace-{entry['source_trace_sha256']}"
            ),
        )
        snapshot = capture_policy_shadow_snapshot(
            env,
            robot,
            source_id=f"v12.4a:{entry['base_pair_id']}:{condition}",
        )
        first, first_restores = _replay(
            env, robot, qidx, snapshot, prefix
        )
        trajectory = ShadowJointTrajectory(
            initial_state_digest=trusted.state_digest,
            action_block_digest=prefix_digest,
            positions=tuple(
                tuple(float(value) for value in row)
                for row in first
            ),
            predictor_id=(
                f"fixed-prefix-controller-shadow-v12.4a:"
                f"{entry['base_pair_id']}:{condition}:first"
            ),
        )
        decision, assessment = decide_policy_prefix_shadow(
            trusted,
            trajectory,
            trigger_margin_rad=float(
                config["episode"]["trigger_margin_rad"]
            ),
        )
        second, second_restores = _replay(
            env, robot, qidx, snapshot, prefix
        )
        reference = ShadowJointTrajectory(
            initial_state_digest=trusted.state_digest,
            action_block_digest=prefix_digest,
            positions=tuple(
                tuple(float(value) for value in row)
                for row in second
            ),
            predictor_id=(
                f"fixed-prefix-controller-shadow-v12.4a:"
                f"{entry['base_pair_id']}:{condition}:reference"
            ),
        )
        reference_assessment = assess_shadow_joint_trajectory(
            trusted,
            reference,
            trigger_margin_rad=float(
                config["episode"]["trigger_margin_rad"]
            ),
        )
        final_restore = _snapshot_payload(
            restore_policy_shadow_snapshot(env, robot, snapshot)
        )
        maximum_error = float(np.max(np.abs(first - second)))
        restores = (
            first_restores + second_restores + [final_restore]
        )
        exact_allow_identity = (
            decision.verdict
            is not PolicyPrefixShadowVerdict.ALLOW_EXACT
            or decision.authorized_action_block_digest == prefix_digest
        )
        blocked_authorized = (
            decision.verdict
            is not PolicyPrefixShadowVerdict.ALLOW_EXACT
            and decision.authorized_action_block_digest is not None
        )
        return {
            "schema": ROW_SCHEMA,
            "case_id": f"{entry['base_pair_id']}:{condition}",
            **{
                key: entry[key]
                for key in (
                    "base_pair_id",
                    "suite",
                    "task_id",
                    "init_state_id",
                    "bddl_path",
                    "trusted_instruction",
                    "source_trace_path",
                    "source_trace_sha256",
                )
            },
            "condition": condition,
            "synthetic_joint_index": injected_joint,
            "synthetic_joint_side": injected_side,
            "valid": True,
            "policy_seed": entry["policy_seed"],
            "source_policy_chunk_sha256": entry[
                "source_policy_chunk_sha256"
            ],
            "source_policy_chunk_shape": entry[
                "source_policy_chunk_shape"
            ],
            "source_prefix_digest": prefix_digest,
            "source_prefix_shape": list(prefix.shape),
            "finite_source_prefix": True,
            "initial_state_digest": trusted.state_digest,
            "initial_minimum_margin_rad": trusted.minimum_margin,
            "current_state_triggered": (
                trusted.minimum_margin
                <= float(config["episode"]["trigger_margin_rad"])
            ),
            "decision": {
                "verdict": decision.verdict.value,
                "risk_predicted": decision.risk_predicted,
                "authorized_action_block_digest": (
                    decision.authorized_action_block_digest
                ),
                "decision_digest": decision.decision_digest,
            },
            "shadow_assessment": {
                "known": assessment.known,
                "risk_predicted": assessment.risk_predicted,
                "minimum_margin_rad": assessment.minimum_margin,
                "terminal_margin_rad": assessment.terminal_margin,
                "first_risk_step": assessment.first_risk_step,
                "assessment_digest": assessment.assessment_digest,
            },
            "reference_assessment": {
                "known": reference_assessment.known,
                "risk_predicted": reference_assessment.risk_predicted,
                "minimum_margin_rad": (
                    reference_assessment.minimum_margin
                ),
                "terminal_margin_rad": (
                    reference_assessment.terminal_margin
                ),
                "first_risk_step": (
                    reference_assessment.first_risk_step
                ),
                "assessment_digest": (
                    reference_assessment.assessment_digest
                ),
            },
            "shadow_reference_risk_agreement": (
                assessment.risk_predicted
                == reference_assessment.risk_predicted
            ),
            "repeat_trajectory_max_abs_qpos_error_rad": maximum_error,
            "repeat_trajectory_within_tolerance": (
                maximum_error
                <= float(
                    config["episode"]["trajectory_tolerance_rad"]
                )
            ),
            "first_replay_minimum_margin_rad": min(
                _minimum_margin(row, limits) for row in first
            ),
            "second_replay_minimum_margin_rad": min(
                _minimum_margin(row, limits) for row in second
            ),
            "restore_assessments": restores,
            "exact_allow_identity": exact_allow_identity,
            "blocked_prefix_authorized": blocked_authorized,
            "stabilization_env_step_count": int(
                config["episode"]["stabilization_steps"]
            ),
            "policy_shadow_env_step_count": 20,
            "policy_load_count": 0,
            "policy_inference_count": 0,
            "live_policy_dispatch_count": 0,
            "outcome_read_count": 0,
        }
    finally:
        env.close()


def build_summary(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    pilot: bool,
) -> dict[str, Any]:
    metrics = _aggregate_metrics(rows)
    if pilot:
        return {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "fixed_policy_prefix_shadow_v12_engineering_pilot_complete"
            ),
            "qualification_pass": None,
            "valid_case_count": metrics["valid_case_count"],
            "metrics": metrics,
            "execution_boundary": {
                key: metrics[key]
                for key in (
                    "policy_load_count",
                    "policy_inference_count",
                    "policy_shadow_env_step_count",
                    "live_policy_dispatch_count",
                    "outcome_read_count",
                )
            },
            "claim_boundary": config["claim_boundary"],
        }
    gates = config["gates"]
    comparisons = (
        ("valid_case_count", ">=", "valid_case_count_min"),
        (
            "finite_source_prefix_rate",
            ">=",
            "finite_source_prefix_rate_min",
        ),
        ("nominal_allow_rate", ">=", "nominal_allow_rate_min"),
        (
            "worst_suite_nominal_allow_rate",
            ">=",
            "worst_suite_nominal_allow_rate_min",
        ),
        (
            "synthetic_current_trigger_rate",
            ">=",
            "synthetic_current_trigger_rate_min",
        ),
        (
            "synthetic_recovery_required_rate",
            ">=",
            "synthetic_recovery_required_rate_min",
        ),
        (
            "shadow_reference_risk_agreement_rate",
            ">=",
            "shadow_reference_risk_agreement_rate_min",
        ),
        (
            "repeat_trajectory_within_tolerance_rate",
            ">=",
            "repeat_trajectory_within_tolerance_rate_min",
        ),
        (
            "trusted_arm_restore_identity_rate",
            ">=",
            "trusted_arm_restore_identity_rate_min",
        ),
        (
            "controller_restore_identity_rate",
            ">=",
            "controller_restore_identity_rate_min",
        ),
        (
            "simulator_input_restore_identity_rate",
            ">=",
            "simulator_input_restore_identity_rate_min",
        ),
        (
            "environment_clock_restore_identity_rate",
            ">=",
            "environment_clock_restore_identity_rate_min",
        ),
        (
            "exact_allow_identity_rate",
            ">=",
            "exact_allow_identity_rate_min",
        ),
        (
            "blocked_prefix_authorization_count",
            "<=",
            "blocked_prefix_authorization_count_max",
        ),
        (
            "policy_load_count",
            "<=",
            "policy_load_count_max",
        ),
        (
            "policy_inference_count",
            "<=",
            "policy_inference_count_max",
        ),
        (
            "live_policy_dispatch_count",
            "<=",
            "live_policy_dispatch_count_max",
        ),
        (
            "outcome_read_count",
            "<=",
            "outcome_read_count_max",
        ),
        (
            "runtime_exception_count",
            "<=",
            "runtime_exception_count_max",
        ),
    )
    conditions = {
        metric: (
            metrics[metric] >= gates[gate]
            if operator == ">="
            else metrics[metric] <= gates[gate]
        )
        for metric, operator, gate in comparisons
    }
    passed = all(conditions.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": config["protocol_id"],
        "classification": (
            "fixed_policy_prefix_shadow_v12_qualification_pass"
            if passed
            else "fixed_policy_prefix_shadow_v12_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "failed_gates": [
            name for name, value in conditions.items() if not value
        ],
        "outcomes_observed": False,
        "fresh_policy_qualification_complete": False,
        "clean_rollout_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }


def _preflight(
    config: dict[str, Any],
    *,
    output_root: Path,
    gpu: int | None,
    formal: bool,
) -> dict[str, Any]:
    blockers = []
    if Path(sys.executable).resolve() != REQUIRED_INTERPRETER.resolve():
        blockers.append(f"required interpreter is {REQUIRED_INTERPRETER}")
    if output_root.exists():
        blockers.append(f"fresh output root exists: {output_root}")
    completed = subprocess.run(
        (
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    status = completed.stdout.strip()
    if formal and status:
        blockers.append("formal fixed-prefix run requires clean worktree")
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < config["resource_gate"]["minimum_free_disk_gib"]:
        blockers.append("free disk is below the fixed-prefix gate")
    selected = None
    if gpu is None:
        blockers.append("simulator GPU has not been selected")
    else:
        inventory = {
            int(row["index"]): row
            for row in saber_io.gpu_inventory()
        }
        selected = inventory.get(gpu)
        if selected is None:
            blockers.append(f"simulator GPU {gpu} is absent")
        elif int(selected["memory_used_mib"]) >= int(
            config["resource_gate"][
                "simulator_gpu_memory_used_mib_max_exclusive"
            ]
        ):
            blockers.append("simulator GPU is above the memory gate")
    return {
        "schema": (
            "proofalign.fixed-policy-prefix-shadow-v12-preflight.v1"
        ),
        "ready": not blockers,
        "formal": formal,
        "output_root_absent": not output_root.exists(),
        "worktree_status": status.splitlines(),
        "selected_gpu": selected,
        "free_disk_gib": free_gib,
        "blockers": blockers,
    }


def _run(
    config: dict[str, Any],
    *,
    output_root: Path,
    gpu: int,
    formal: bool,
    protocol_path: Path | None,
) -> dict[str, Any]:
    preflight = _preflight(
        config,
        output_root=output_root,
        gpu=gpu,
        formal=formal,
    )
    if not preflight["ready"]:
        raise FixedPolicyPrefixShadowError(
            f"fixed-prefix preflight failed: {preflight['blockers']}"
        )
    output_root.mkdir(parents=True)
    runtime_config = result_io.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    _configure_environment(gpu)
    manifest_path = output_root / "run_manifest.json"
    ledger_path = output_root / "qualification_ledger.jsonl"
    manifest = {
        "schema": "proofalign.fixed-policy-prefix-shadow-v12-run.v1",
        "status": "running",
        "created_at": saber_io.utc_now(),
        "formal": formal,
        "protocol_id": config["protocol_id"],
        "protocol_sha256": (
            _sha256(protocol_path)
            if protocol_path is not None
            else None
        ),
        "gpu": gpu,
        "preflight": preflight,
        "runtime_config": runtime_config,
        "policy_loaded": False,
        "outcomes_observed": False,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        for entry_index, entry in enumerate(
            config["population"]["prefixes"]
        ):
            for condition in (
                "nominal",
                "synthetic_joint_pressure",
            ):
                row = _run_case(
                    config,
                    entry,
                    condition=condition,
                    case_index=entry_index * 2
                    + int(condition == "synthetic_joint_pressure"),
                    gpu=gpu,
                    output_root=output_root,
                )
                saber_io.append_ledger(ledger_path, row)
        rows = [
            json.loads(line)
            for line in ledger_path.read_text().splitlines()
            if line.strip()
        ]
        summary = build_summary(config, rows, pilot=not formal)
        saber_io.atomic_json(output_root / "summary.json", summary)
        manifest["status"] = "complete"
        manifest["classification"] = summary["classification"]
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        result_io.write_checksums(output_root)
        return summary
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        result_io.write_checksums(output_root)
        raise


def _with_injections(
    prefixes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assignments = [
        (joint, side)
        for joint in range(7)
        for side in ("lower", "upper")
    ] + [(1, "upper")]
    if len(prefixes) == 3:
        assignments = [(0, "lower"), (3, "upper"), (6, "lower")]
    if len(prefixes) != len(assignments):
        raise FixedPolicyPrefixShadowError(
            "fixed-prefix injection assignment differs"
        )
    return [
        {
            **entry,
            "synthetic_joint_index": joint,
            "synthetic_joint_side": side,
        }
        for entry, (joint, side) in zip(
            prefixes, assignments, strict=True
        )
    ]


def _pilot_config() -> dict[str, Any]:
    corpus = _load(CORPUS_PATH)
    return {
        "schema": "proofalign.fixed-policy-prefix-shadow-v12-pilot.v1",
        "protocol_id": "fixed-prefix-engineering-pilot",
        "population": {
            "prefixes": _with_injections(corpus["pilot_prefixes"]),
        },
        "episode": {
            "control_frequency_hz": 20,
            "environment_horizon": 100000,
            "stabilization_steps": 10,
            "trigger_margin_rad": 0.1,
            "synthetic_injected_margin_rad": 0.05,
            "trajectory_tolerance_rad": 0.02,
        },
        "resource_gate": {
            "simulator_gpu_memory_used_mib_max_exclusive": 30000,
            "minimum_free_disk_gib": 10,
        },
        "claim_boundary": (
            "This three-prefix, six-case engineering pilot uses exact "
            "executed commands extracted without outcomes from frozen "
            "outcome-known traces. It selects the formal controller-shadow "
            "protocol and is not qualification or fresh-policy evidence."
        ),
    }


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise FixedPolicyPrefixShadowError(
            f"missing formal protocol: {PROTOCOL_PATH}"
        )
    observed = _load(PROTOCOL_PATH)
    expected = build_protocol()
    if observed != expected or observed["schema"] != PROTOCOL_SCHEMA:
        raise FixedPolicyPrefixShadowError(
            "fixed-prefix formal protocol is stale"
        )
    return observed


def _validate(
    config: dict[str, Any],
    *,
    output_root: Path,
    pilot: bool,
) -> dict[str, Any]:
    result_io.read_checksums(output_root)
    manifest = _load(output_root / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise FixedPolicyPrefixShadowError(
            "fixed-prefix manifest is not complete"
        )
    rows = [
        json.loads(line)
        for line in (
            output_root / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    retained = _load(output_root / "summary.json")
    recomputed = build_summary(config, rows, pilot=pilot)
    if retained != recomputed:
        raise FixedPolicyPrefixShadowError(
            "fixed-prefix summary differs from recomputation"
        )
    return recomputed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    if args.pilot:
        if args.gpu is None:
            parser.error("--pilot requires --gpu")
        if args.preflight or args.execute or args.validate_results:
            parser.error("--pilot cannot be combined with formal modes")
        payload = _run(
            _pilot_config(),
            output_root=PILOT_ROOT,
            gpu=args.gpu,
            formal=False,
            protocol_path=None,
        )
    else:
        if sum(
            (args.preflight, args.execute, args.validate_results)
        ) != 1:
            parser.error(
                "choose one formal mode: --preflight, --execute, "
                "or --validate-results"
            )
        config = _verify_protocol()
        if args.preflight:
            payload = _preflight(
                config,
                output_root=OUTPUT_ROOT,
                gpu=args.gpu,
                formal=True,
            )
        elif args.execute:
            if args.gpu is None:
                parser.error("--execute requires --gpu")
            payload = _run(
                config,
                output_root=OUTPUT_ROOT,
                gpu=args.gpu,
                formal=True,
                protocol_path=PROTOCOL_PATH,
            )
        else:
            payload = _validate(
                config, output_root=OUTPUT_ROOT, pilot=False
            )
    print(_canonical(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
