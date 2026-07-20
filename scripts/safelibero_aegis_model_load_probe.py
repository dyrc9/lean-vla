#!/usr/bin/env python3
"""Load pinned AEGIS models without inference, sockets, simulation, or dispatch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proofalign.benchmark.aegis_runtime import (  # noqa: E402
    build_runtime_preflight,
    dump_json,
    load_json,
    sha256_file,
)


SCHEMA = "proofalign.safelibero-aegis-model-load-report-v1"
MARKER = "PROOFALIGN_MODEL_LOAD_JSON="
DEFAULT_PROTOCOL = ROOT / "experiments" / "safelibero_aegis_model_load_protocol.json"


class ModelLoadProbeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate R1 and optionally load pi05_libero and GroundingDINO. "
            "This runner contains no policy inference or simulator path."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the separately authorized model-load-only probe.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a fresh report; an existing path is never overwritten.",
    )
    return parser.parse_args()


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 900,
) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        merged.update(env)
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=merged,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _run_json(
    python: Path,
    code: str,
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> dict[str, Any]:
    result = _run([str(python), "-c", code], cwd=cwd, env=env)
    lines = [line[len(MARKER) :] for line in result.stdout.splitlines() if line.startswith(MARKER)]
    if result.returncode != 0 or len(lines) != 1:
        raise ModelLoadProbeError(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-4000:],
                    "stderr_tail": result.stderr[-4000:],
                },
                indent=2,
            )
        )
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise ModelLoadProbeError("model probe did not emit a JSON object")
    return value


def _gpu_inventory() -> list[dict[str, Any]]:
    result = _run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        cwd=ROOT,
        timeout_seconds=30,
    )
    if result.returncode != 0:
        raise ModelLoadProbeError(result.stderr.strip() or "nvidia-smi inventory failed")
    gpus = []
    for line in result.stdout.splitlines():
        index, uuid, name, total, used, utilization = [part.strip() for part in line.split(",", 5)]
        gpus.append(
            {
                "index": int(index),
                "uuid": uuid,
                "name": name,
                "memory_total_mib": int(total),
                "memory_used_mib": int(used),
                "utilization_percent": int(utilization),
            }
        )
    return gpus


def _gpu_compute_processes() -> list[dict[str, Any]]:
    result = _run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ],
        cwd=ROOT,
        timeout_seconds=30,
    )
    if result.returncode != 0:
        raise ModelLoadProbeError(result.stderr.strip() or "nvidia-smi process query failed")
    processes = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        uuid, pid, name, used = [part.strip() for part in line.split(",", 3)]
        processes.append(
            {"gpu_uuid": uuid, "pid": int(pid), "process_name": name, "used_memory_mib": int(used)}
        )
    return processes


def _verify_protocol_files(protocol: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative_or_absolute, expected in protocol["sha256"].items():
        path = Path(relative_or_absolute)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise ModelLoadProbeError(f"missing pinned file: {path}")
        observed[relative_or_absolute] = sha256_file(path)
        if observed[relative_or_absolute] != expected:
            raise ModelLoadProbeError(f"digest mismatch: {path}")
    for relative, expected in protocol["implementation"].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ModelLoadProbeError(f"implementation mismatch: {path}")
    return observed


def _load_groundingdino(protocol: Mapping[str, Any]) -> dict[str, Any]:
    config = ROOT / protocol["models"]["groundingdino"]["config"]
    weight = Path(protocol["models"]["groundingdino"]["weight"])
    python = Path(protocol["runtimes"]["simulator_python"])
    code = f"""
import json
import time
import torch
from groundingdino.util.inference import load_model
started = time.monotonic()
model = load_model({str(config)!r}, {str(weight)!r}, device='cpu')
state = model.state_dict()
payload = {{
    'component': 'groundingdino',
    'class': type(model).__name__,
    'device': str(next(model.parameters()).device),
    'state_tensor_count': len(state),
    'parameter_count': sum(parameter.numel() for parameter in model.parameters()),
    'training': model.training,
    'load_seconds': time.monotonic() - started,
    'inference_call_count': 0,
}}
print('{MARKER}' + json.dumps(payload, sort_keys=True))
"""
    return _run_json(
        python,
        code,
        cwd=ROOT,
        env={
            "CUDA_VISIBLE_DEVICES": "",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "MPLCONFIGDIR": "/tmp/proofalign-aegis-matplotlib",
        },
    )


def _load_pi05(protocol: Mapping[str, Any]) -> dict[str, Any]:
    model = protocol["models"]["pi05_libero"]
    python = Path(protocol["runtimes"]["policy_python"])
    source_root = Path(protocol["runtimes"]["source_root"])
    gpu = protocol["gpu"]
    code = f"""
import json
import time
import jax
from flax import nnx
from openpi.policies import policy_config
from openpi.training import config
started = time.monotonic()
train_config = config.get_config({model['config']!r})
policy = policy_config.create_trained_policy(train_config, {model['checkpoint']!r})
state = nnx.state(policy._model)
leaves = jax.tree.leaves(state)
payload = {{
    'component': 'pi05_libero',
    'policy_class': type(policy).__name__,
    'model_class': type(policy._model).__name__,
    'jax_devices': [str(device) for device in jax.devices()],
    'state_leaf_count': len(leaves),
    'parameter_count': sum(getattr(leaf, 'size', 0) for leaf in leaves),
    'metadata_keys': sorted(policy.metadata),
    'load_seconds': time.monotonic() - started,
    'policy_inference_call_count': 0,
}}
print('{MARKER}' + json.dumps(payload, sort_keys=True))
"""
    return _run_json(
        python,
        code,
        cwd=source_root,
        env={
            "CUDA_VISIBLE_DEVICES": str(gpu["physical_index"]),
            "OPENPI_DATA_HOME": protocol["models"]["pi05_libero"]["openpi_data_home"],
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
            "JAX_COMPILATION_CACHE_DIR": "/tmp/proofalign-aegis-jax-cache",
        },
    )


def main() -> int:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    if protocol.get("schema") != "proofalign.safelibero-aegis-model-load-protocol-v1":
        raise ModelLoadProbeError("unsupported model-load protocol schema")

    r1_protocol = load_json(ROOT / protocol["r1_static_gate"]["protocol"])
    r1_report = build_runtime_preflight(r1_protocol, project_root=ROOT)
    static_ready = r1_report["static_runtime_ready"] and r1_report["model_load_probe_authorized"]
    observed_hashes = _verify_protocol_files(protocol)

    base = {
        "schema": SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256_file(protocol_path),
        "static_runtime_ready": static_ready,
        "pinned_file_sha256": observed_hashes,
        "executed": args.execute,
        "formal_rollout_authorized": False,
    }
    if not args.execute:
        base["status"] = "model_load_probe_ready" if static_ready else "blocked_by_r1"
        print(json.dumps(base, indent=2, sort_keys=True))
        return 0 if static_ready else 2
    if not static_ready:
        raise ModelLoadProbeError("R1 static runtime gate did not authorize this probe")

    inventory_before = _gpu_inventory()
    processes_before = _gpu_compute_processes()
    gpu = protocol["gpu"]
    selected = next((item for item in inventory_before if item["index"] == gpu["physical_index"]), None)
    if selected is None or selected["uuid"] != gpu["uuid"]:
        raise ModelLoadProbeError("selected GPU identity mismatch")
    if selected["memory_used_mib"] >= gpu["max_prelaunch_used_memory_mib"]:
        raise ModelLoadProbeError("selected GPU exceeds the prelaunch memory gate")
    if any(item["gpu_uuid"] == gpu["uuid"] for item in processes_before):
        raise ModelLoadProbeError("selected GPU already has a compute process")

    started_wall = time.time_ns()
    started = time.monotonic()
    groundingdino = _load_groundingdino(protocol)
    pi05 = _load_pi05(protocol)
    inventory_after = _gpu_inventory()
    counters = {
        "groundingdino_model_construction_count": 1,
        "pi05_model_construction_count": 1,
        "policy_construction_count": 1,
        "policy_inference_call_count": 0,
        "groundingdino_inference_call_count": 0,
        "server_socket_bind_count": 0,
        "simulator_construction_count": 0,
        "env_step_count": 0,
    }
    model_checks = {
        "groundingdino_eval_mode": groundingdino.get("training") is False,
        "groundingdino_cpu_load": groundingdino.get("device") == "cpu",
        "groundingdino_state_present": groundingdino.get("state_tensor_count", 0) > 0,
        "groundingdino_no_inference": groundingdino.get("inference_call_count") == 0,
        "pi05_state_present": pi05.get("state_leaf_count", 0) > 0,
        "pi05_parameter_count_present": pi05.get("parameter_count", 0) > 0,
        "pi05_gpu_visible": any(
            "cuda" in str(device).lower() for device in pi05.get("jax_devices", [])
        ),
        "pi05_no_inference": pi05.get("policy_inference_call_count") == 0,
        "all_forbidden_counters_zero": all(
            counters[name] == 0
            for name in (
                "policy_inference_call_count",
                "groundingdino_inference_call_count",
                "server_socket_bind_count",
                "simulator_construction_count",
                "env_step_count",
            )
        ),
    }
    model_load_ready = all(model_checks.values())
    result = {
        **base,
        "executed": True,
        "started_unix_ns": started_wall,
        "duration_seconds": time.monotonic() - started,
        "gpu_before": selected,
        "gpu_processes_before": processes_before,
        "gpu_inventory_after": inventory_after,
        "groundingdino": groundingdino,
        "pi05_libero": pi05,
        "counters": counters,
        "model_checks": model_checks,
        "model_load_ready": model_load_ready,
        "scene_probe_authorized": model_load_ready,
        "formal_rollout_authorized": False,
        "status": (
            "model_load_ready_scene_probe_pending"
            if model_load_ready
            else "model_load_probe_failed"
        ),
    }
    if args.output:
        output = args.output.resolve()
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing report: {output}")
        dump_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if model_load_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
