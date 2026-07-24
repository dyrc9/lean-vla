#!/usr/bin/env python3
"""Run the resource-isolated successor to the terminal R3 action-envelope attempt.

This launcher keeps the frozen R3 measurement semantics but fixes the runtime
device boundary: CUDA exposes policy then EGL GPUs, while JAX is explicitly
restricted to local device zero before its backend is initialized.  It also
checks PID-level compute and graphics contexts before starting the all-pair
zero-step binding probe and rejects new external compute users during it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts import run_saber_integrity_action_envelope_r2 as r3  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts.generate_saber_threat_records_r2 import ProtocolError, load_json  # noqa: E402
from proofalign.benchmark.attack_records import apply_attack_record, get_attack_record  # noqa: E402
from proofalign.benchmark.libero_runtime import load_libero_task_runtime  # noqa: E402


DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "saber_integrity_action_envelope_r4_protocol.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "saber_integrity_action_envelope_r4_20260723_fresh1"
PROGRESS_SCHEMA = "proofalign.saber-integrity-action-envelope-binding-progress.v1"


def _required_resource_isolation() -> dict[str, Any]:
    return {
        "cuda_visible_devices_order": "policy_then_egl_physical_indices",
        "jax_cuda_visible_devices_config": "0",
        "jax_device_count": 1,
        "egl_device_mapping": "EGL_NV_device_cuda_query_by_physical_index",
        "robosuite_cuda_visible_devices_assertion_shim": "append_egl_ordinal_then_verify_pid_contexts",
        "post_policy_load_compute_context": "current_pid_on_policy_gpu_only",
        "post_env_create_graphics_context": "current_pid_on_egl_gpu_only",
        "external_compute_during_binding_probe": "terminal_fail_closed",
        "binding_progress_is_non_resumable": True,
    }


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol = r3.load_protocol(path)
    if protocol.get("resource_isolation") != _required_resource_isolation():
        raise ProtocolError("resource-isolated successor contract changed")
    execution = r3._require_dict(protocol.get("execution_gate"), "execution_gate")
    if execution.get("no_compute_process_at_launch") is not True:
        raise ProtocolError("launch compute-process gate changed")
    if execution.get("stable_resource_window_seconds") != 0:
        raise ProtocolError("launch must use the user-authorized immediate resource gate")
    if execution.get("runtime_pid_context_observation_required") is not True:
        raise ProtocolError("runtime PID-context gate changed")
    return protocol


def _run_nvidia_smi(arguments: list[str]) -> str:
    completed = subprocess.run(
        ["nvidia-smi", *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return completed.stdout


def _gpu_uuid_to_index() -> dict[str, int]:
    rows: dict[str, int] = {}
    output = _run_nvidia_smi(
        ["--query-gpu=index,uuid", "--format=csv,noheader,nounits"]
    )
    for line in output.splitlines():
        if not line.strip():
            continue
        index, uuid = (part.strip() for part in line.split(",", maxsplit=1))
        rows[uuid] = int(index)
    return rows


def _compute_contexts() -> list[dict[str, Any]]:
    uuid_to_index = _gpu_uuid_to_index()
    output = _run_nvidia_smi(
        [
            "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ]
    )
    contexts: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        uuid, pid, process_name, used_memory = (
            part.strip() for part in line.split(",", maxsplit=3)
        )
        contexts.append(
            {
                "gpu_index": uuid_to_index[uuid],
                "gpu_uuid": uuid,
                "pid": int(pid),
                "process_name": process_name,
                "used_memory_mib": int(used_memory),
            }
        )
    return contexts


def _pmon_contexts(pid: int) -> list[dict[str, Any]]:
    output = _run_nvidia_smi(["pmon", "-c", "1"])
    contexts: list[dict[str, Any]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        columns = stripped.split()
        if len(columns) < 3 or columns[1] == "-":
            continue
        try:
            context_pid = int(columns[1])
        except ValueError:
            continue
        if context_pid == pid:
            contexts.append(
                {
                    "gpu_index": int(columns[0]),
                    "pid": context_pid,
                    "context_type": columns[2],
                    "process_name": columns[-1],
                }
            )
    return contexts


def _selected_inventory(policy_gpu: int, egl_gpu: int) -> dict[str, dict[str, Any]]:
    inventory = {int(row["index"]): row for row in p0b.gpu_inventory()}
    if policy_gpu not in inventory or egl_gpu not in inventory:
        raise ProtocolError("selected physical GPU is absent")
    return {"policy": inventory[policy_gpu], "egl": inventory[egl_gpu]}


def _assert_launch_resources(
    protocol: dict[str, Any], policy_gpu: int, egl_gpu: int
) -> dict[str, Any]:
    selected = _selected_inventory(policy_gpu, egl_gpu)
    limit = int(protocol["execution_gate"]["selected_gpu_memory_used_mib_max_exclusive"])
    if any(int(row["memory_used_mib"]) >= limit for row in selected.values()):
        raise ProtocolError(f"selected GPU violates the <{limit} MiB launch gate")
    selected_indices = {policy_gpu, egl_gpu}
    contexts = [
        row for row in _compute_contexts() if int(row["gpu_index"]) in selected_indices
    ]
    if contexts:
        raise ProtocolError(f"selected GPU has a compute process at launch: {contexts}")
    return {
        "checked_at": p0b.utc_now(),
        "selected_gpu": selected,
        "compute_contexts": contexts,
    }


def _observe_stable_launch_resources(
    protocol: dict[str, Any], policy_gpu: int, egl_gpu: int
) -> dict[str, Any]:
    required_seconds = int(protocol["execution_gate"]["stable_resource_window_seconds"])
    interval_seconds = 30
    started_at = p0b.utc_now()
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    while True:
        sample = _assert_launch_resources(protocol, policy_gpu, egl_gpu)
        elapsed = time.monotonic() - started
        samples.append(sample)
        print(
            json.dumps(
                {
                    "event": "launch_resource_stability_sample",
                    "elapsed_seconds": round(elapsed, 3),
                    "required_seconds": required_seconds,
                    "sample": sample,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if elapsed >= required_seconds:
            break
        time.sleep(min(interval_seconds, required_seconds - elapsed))
    return {
        "started_at": started_at,
        "completed_at": p0b.utc_now(),
        "required_stable_seconds": required_seconds,
        "sample_interval_seconds": interval_seconds,
        "sample_count": len(samples),
        "samples": samples,
    }


def _egl_cuda_device_mapping() -> list[dict[str, int]]:
    from mujoco.egl import egl_ext as egl

    visible_text = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    visible_physical = [
        int(value.strip()) for value in visible_text.split(",") if value.strip()
    ]
    query_type = ctypes.CFUNCTYPE(
        egl.EGLBoolean,
        egl.EGLDeviceEXT,
        egl.EGLint,
        ctypes.POINTER(ctypes.c_ssize_t),
    )
    address = egl.eglGetProcAddress("eglQueryDeviceAttribEXT")
    if not address:
        raise ProtocolError("eglQueryDeviceAttribEXT is unavailable")
    query = query_type(address)
    mapping: list[dict[str, int]] = []
    for egl_index, device in enumerate(egl.eglQueryDevicesEXT()):
        cuda_index = ctypes.c_ssize_t(-1)
        if query(device, 0x323A, ctypes.byref(cuda_index)):  # EGL_CUDA_DEVICE_NV
            local_index = int(cuda_index.value)
            physical_index = (
                visible_physical[local_index]
                if 0 <= local_index < len(visible_physical)
                else local_index
            )
            mapping.append(
                {
                    "egl_device_ordinal": egl_index,
                    "cuda_visible_index": local_index,
                    "cuda_physical_index": physical_index,
                }
            )
    if not mapping:
        raise ProtocolError("EGL_NV_device_cuda returned no CUDA-backed EGL devices")
    return mapping


def _configure_environment(policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    p0b.configure_environment(
        policy_gpu, egl_gpu, "saber-integrity-envelope-r4-resource-isolated"
    )
    mapping = _egl_cuda_device_mapping()
    ordinals = [
        int(row["egl_device_ordinal"])
        for row in mapping
        if int(row["cuda_physical_index"]) == egl_gpu
    ]
    if len(ordinals) != 1:
        raise ProtocolError(
            f"physical EGL GPU {egl_gpu} does not have one exact EGL ordinal: {mapping}"
        )
    egl_ordinal = ordinals[0]
    # Vendored robosuite compares the EGL ordinal against the textual physical
    # CUDA list.  Append the ordinal solely to satisfy that import-time check;
    # the PID-level gate below remains authoritative for actual compute and
    # graphics contexts.
    visible = [policy_gpu, egl_gpu]
    if egl_ordinal not in visible:
        visible.append(egl_ordinal)
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(value) for value in visible)
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(egl_ordinal)
    # JAX 0.5.3 exposes both CUDA_VISIBLE_DEVICES entries unless this config is
    # updated programmatically before backend initialization.  The environment
    # variable alone was experimentally shown to be insufficient.
    import jax

    jax.config.update("jax_cuda_visible_devices", "0")
    return {
        "mapping_source": "EGL_NV_device_cuda",
        "mapping": mapping,
        "requested_egl_physical_index": egl_gpu,
        "selected_egl_device_ordinal": egl_ordinal,
        "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
        "jax_cuda_visible_devices": "0",
    }


def _assert_no_external_compute(policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    current_pid = os.getpid()
    selected_indices = {policy_gpu, egl_gpu}
    contexts = [
        row
        for row in _compute_contexts()
        if int(row["gpu_index"]) in selected_indices and int(row["pid"]) != current_pid
    ]
    if contexts:
        raise ProtocolError(
            f"external compute process appeared on a selected GPU: {contexts}"
        )
    return {"checked_at": p0b.utc_now(), "external_compute_contexts": contexts}


def _runtime_role_probe(
    *,
    baseline: dict[str, Any],
    records: list[dict[str, Any]],
    args: Any,
    policy: Any,
    jax: Any,
    image_tools: Any,
    runner: Any,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    devices = [str(device) for device in jax.devices()]
    if devices != ["cuda:0"]:
        raise ProtocolError(f"JAX device isolation failed: {devices}")
    current_pid = os.getpid()
    compute_before_env = [
        row for row in _compute_contexts() if int(row["pid"]) == current_pid
    ]
    if {int(row["gpu_index"]) for row in compute_before_env} != {policy_gpu}:
        raise ProtocolError(
            f"policy PID compute context is not isolated to GPU {policy_gpu}: "
            f"{compute_before_env}"
        )

    first = p0b.episode_specs(baseline)[0]
    record_index = p0b.build_record_index(records)
    runtime = load_libero_task_runtime(
        benchmark_name=first.suite,
        task_id=first.task_id,
        init_state_id=first.init_state_id,
        bddl_file=None,
    )
    if first.condition == "attacked":
        record = get_attack_record(
            record_index,
            suite=first.suite,
            task_id=first.task_id,
            init_state_id=first.init_state_id,
        )
        if record is None:
            raise ProtocolError("first runtime-role probe attack record is absent")
        runtime = apply_attack_record(runtime, record)
    env = runner.create_env(runtime, args)
    try:
        env.reset()
        obs = env.set_init_state(runtime.init_state) if runtime.init_state is not None else None
        if obs is None:
            obs = runner.get_observation(env)
        runner.prepare_openpi_element(obs, runtime.instruction, image_tools, args.resize_size)
        pmon = _pmon_contexts(current_pid)
        graphics_gpus = {
            int(row["gpu_index"])
            for row in pmon
            if "G" in str(row["context_type"]).upper()
        }
        if graphics_gpus != {egl_gpu}:
            raise ProtocolError(
                f"EGL graphics context is not isolated to GPU {egl_gpu}: {pmon}"
            )
        compute_after_env = [
            row for row in _compute_contexts() if int(row["pid"]) == current_pid
        ]
        if {int(row["gpu_index"]) for row in compute_after_env} != {policy_gpu}:
            raise ProtocolError(
                f"environment creation changed policy compute isolation: "
                f"{compute_after_env}"
            )
        return {
            "checked_at": p0b.utc_now(),
            "pid": current_pid,
            "jax_devices": devices,
            "compute_contexts_before_env": compute_before_env,
            "pmon_contexts_with_env_open": pmon,
            "compute_contexts_with_env_open": compute_after_env,
            "policy_gpu_verified": policy_gpu,
            "egl_gpu_verified": egl_gpu,
            "env_step_calls": 0,
        }
    finally:
        env.close()


def _probe_bindings_with_progress(
    *,
    baseline: dict[str, Any],
    records: list[dict[str, Any]],
    args: Any,
    policy: Any,
    jax: Any,
    image_tools: Any,
    runner: Any,
    output_root: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, dict[str, Any]]:
    record_index = p0b.build_record_index(records)
    specs = p0b.episode_specs(baseline)
    bindings: dict[str, dict[str, Any]] = {}
    progress_path = output_root / "binding_probe_progress.json"
    for sequence_index, spec in enumerate(specs):
        resource_check = _assert_no_external_compute(policy_gpu, egl_gpu)
        runtime = load_libero_task_runtime(
            benchmark_name=spec.suite,
            task_id=spec.task_id,
            init_state_id=spec.init_state_id,
            bddl_file=None,
        )
        if spec.condition == "attacked":
            record = get_attack_record(
                record_index,
                suite=spec.suite,
                task_id=spec.task_id,
                init_state_id=spec.init_state_id,
            )
            if record is None:
                raise ProtocolError(f"binding probe attack record is absent: {spec.episode_id}")
            runtime = apply_attack_record(runtime, record)
        env = runner.create_env(runtime, args)
        try:
            env.reset()
            obs = env.set_init_state(runtime.init_state) if runtime.init_state is not None else None
            if obs is None:
                obs = runner.get_observation(env)
            element, _, audit = runner.prepare_openpi_element(
                obs, runtime.instruction, image_tools, args.resize_size
            )
            runner.set_policy_seed(
                policy, jax, int(baseline["episode_config"]["policy_seed"])
            )
            actions = policy.infer(element)["actions"]
            binding = {
                "episode_id": spec.episode_id,
                "instruction": runtime.instruction,
                "initial_state_sha256": runner.array_digest(runtime.init_state),
                "first_clean_frame_sha256": audit["clean_frame_sha256"],
                "first_policy_action_chunk_sha256": runner.array_digest(actions),
                "first_policy_action_chunk_shape": list(actions.shape),
                "env_step_calls": 0,
            }
            json.dumps(binding, sort_keys=True)
            bindings[spec.episode_id] = binding
        finally:
            env.close()
        p0b.atomic_json(
            progress_path,
            {
                "schema": PROGRESS_SCHEMA,
                "updated_at": p0b.utc_now(),
                "complete": sequence_index + 1 == len(specs),
                "completed_binding_count": sequence_index + 1,
                "required_binding_count": len(specs),
                "last_episode_id": spec.episode_id,
                "bindings_sha256": p0b.canonical_digest(bindings),
                "resume_allowed": False,
                "last_resource_check": resource_check,
            },
        )
    for pair in baseline["frozen_pairs"]:
        clean = bindings[f"clean_{pair['pair_id']}"]
        attacked = bindings[f"attacked_{pair['pair_id']}"]
        if clean["initial_state_sha256"] != attacked["initial_state_sha256"]:
            raise ProtocolError(f"preflight initial-state binding differs: {pair['pair_id']}")
        if clean["first_clean_frame_sha256"] != attacked["first_clean_frame_sha256"]:
            raise ProtocolError(f"preflight first-frame binding differs: {pair['pair_id']}")
    return bindings


def _execute(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
    policy_gpu: int,
    egl_gpu: int,
    launch_observation: dict[str, Any],
) -> dict[str, Any]:
    preflight = r3.static_preflight(
        protocol, protocol_path, output_root, policy_gpu, egl_gpu
    )
    baseline, baseline_summary, baseline_ledger = r3._validate_baseline(protocol)
    output_root.mkdir(parents=True)
    runtime_config = p0b.ensure_libero_runtime_config(output_root)
    manifest_path = output_root / str(protocol["artifact_policy"]["manifest"])
    ledger_path = r3._ledger_path(protocol, output_root)
    manifest = {
        "schema": "proofalign.saber-integrity-action-envelope-resource-isolated-run.v1",
        "status": "running_runtime_role_probe",
        "protocol_sha256": p0b.file_digest(protocol_path),
        "started_at": p0b.utc_now(),
        "preflight": preflight,
        "launch_resource_observation": launch_observation,
        "libero_runtime_config": runtime_config,
    }
    p0b.atomic_json(manifest_path, manifest)
    try:
        device_mapping = _configure_environment(policy_gpu, egl_gpu)
        manifest["preflight"]["egl_cuda_device_mapping"] = device_mapping
        p0b.atomic_json(manifest_path, manifest)
        os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
        args = r3._episode_args(
            baseline,
            output_root,
            int(device_mapping["selected_egl_device_ordinal"]),
        )
        policy, jax, image_tools, runner = p0b.load_policy(baseline, args)
        records = r3._validated_attack_records(protocol, baseline)
        manifest["preflight"]["runtime_device_observation"] = _runtime_role_probe(
            baseline=baseline,
            records=records,
            args=args,
            policy=policy,
            jax=jax,
            image_tools=image_tools,
            runner=runner,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
        manifest["status"] = "running_zero_step_binding_probe"
        p0b.atomic_json(manifest_path, manifest)
        bindings = _probe_bindings_with_progress(
            baseline=baseline,
            records=records,
            args=args,
            policy=policy,
            jax=jax,
            image_tools=image_tools,
            runner=runner,
            output_root=output_root,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
        manifest["preflight"]["real_policy_probe"] = {
            "bindings": bindings,
            "env_step_calls": 0,
        }
        manifest["status"] = "running_attacked_defended"
        p0b.atomic_json(manifest_path, manifest)
        extractor = p0b.make_constraint_extractor()
        record_index = p0b.build_record_index(records)
        pairs = {str(pair["pair_id"]): pair for pair in baseline["frozen_pairs"]}
        for spec in r3.episode_specs(protocol):
            _assert_no_external_compute(policy_gpu, egl_gpu)
            pair = pairs[spec.pair_id]
            attack_record = get_attack_record(
                record_index,
                suite=spec.suite,
                task_id=spec.task_id,
                init_state_id=spec.init_state_id,
            )
            if attack_record is None:
                raise ProtocolError(f"frozen attack record is missing for {spec.pair_id}")
            payload = r3._run_episode(
                baseline=baseline,
                spec=spec,
                pair=pair,
                attack_record=attack_record,
                binding=bindings[f"attacked_{spec.pair_id}"],
                output_root=output_root,
                policy=policy,
                jax=jax,
                image_tools=image_tools,
                runner=runner,
                egl_gpu=int(device_mapping["selected_egl_device_ordinal"]),
                extractor=extractor,
                protocol=protocol,
            )
            artifact = (
                output_root
                / spec.episode_id
                / "episodes"
                / f"{spec.suite}_task{spec.task_id}_init{spec.init_state_id}.json"
            )
            issues, details = r3._validate_payload(
                baseline,
                spec,
                payload,
                attack_record,
                bindings[f"attacked_{spec.pair_id}"],
            )
            row = {
                "schema": r3.LEDGER_SCHEMA,
                "episode_id": spec.episode_id,
                "pair_id": spec.pair_id,
                "condition": "attacked_defended",
                "sequence_index": spec.sequence_index,
                "suite": spec.suite,
                "task_id": spec.task_id,
                "init_state_id": spec.init_state_id,
                "valid": not issues,
                "validation_issues": issues,
                "episode_json_sha256": (
                    p0b.file_digest(artifact) if artifact.is_file() else None
                ),
                "orchestrator_sha256": p0b.file_digest(Path(__file__).resolve()),
                "base_victim_runner_sha256": p0b.file_digest(r3.BASE_RUNNER),
                **details,
            }
            r3._append_ledger(ledger_path, row)
            if issues:
                raise ProtocolError(
                    f"attacked+defended episode failed closed: {spec.episode_id}: {issues}"
                )
        summary = r3._summary(
            protocol, baseline_summary, baseline_ledger, r3._read_ledger(ledger_path)
        )
        p0b.atomic_json(
            output_root / str(protocol["artifact_policy"]["summary"]), summary
        )
        manifest.update(
            {
                "status": "complete",
                "completed_at": p0b.utc_now(),
                "classification": summary["classification"],
            }
        )
        p0b.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        return summary
    except BaseException as exc:
        summary = r3._summary(
            protocol, baseline_summary, baseline_ledger, r3._read_ledger(ledger_path)
        )
        p0b.atomic_json(
            output_root / str(protocol["artifact_policy"]["summary"]), summary
        )
        manifest.update(
            {
                "status": "failed",
                "failed_at": p0b.utc_now(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        p0b.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--policy-gpu", type=int, required=True)
    parser.add_argument("--egl-gpu", type=int, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.resolve()
    output_root = args.output_root.resolve()
    protocol = load_protocol(protocol_path)
    if args.dry_run:
        print(
            json.dumps(
                [
                    spec.__dict__ | {"episode_id": spec.episode_id}
                    for spec in r3.episode_specs(protocol)
                ],
                indent=2,
            )
        )
        return 0
    launch_observation = _observe_stable_launch_resources(
        protocol, args.policy_gpu, args.egl_gpu
    )
    summary = _execute(
        protocol,
        protocol_path,
        output_root,
        args.policy_gpu,
        args.egl_gpu,
        launch_observation,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, TypeError, ValueError, ProtocolError) as exc:
        print(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2),
            file=sys.stderr,
        )
        raise SystemExit(2)
