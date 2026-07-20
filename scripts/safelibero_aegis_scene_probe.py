#!/usr/bin/env python3
"""Construct and serialize one pinned SafeLIBERO scene with zero env.step calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proofalign.benchmark.aegis_runtime import dump_json, load_json, sha256_file  # noqa: E402


SCHEMA = "proofalign.safelibero-aegis-scene-probe-report-v1"
MARKER = "PROOFALIGN_SCENE_JSON="
DEFAULT_PROTOCOL = ROOT / "experiments" / "safelibero_aegis_scene_protocol.json"


class SceneProbeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the model-load gate and optionally construct exactly one "
            "pinned SafeLIBERO scene without calling env.step."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 300,
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


def _digest_arrays(values: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(values):
        array = np.asarray(values[key])
        header = json.dumps(
            {"key": key, "dtype": str(array.dtype), "shape": list(array.shape)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        data = np.ascontiguousarray(array).tobytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _verify_files(protocol: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, record in protocol["pinned_files"].items():
        path = Path(record["path"])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise SceneProbeError(f"missing pinned {name}: {path}")
        observed[name] = sha256_file(path)
        if observed[name] != record["sha256"]:
            raise SceneProbeError(f"digest mismatch for {name}: {path}")
    for relative, expected in protocol["implementation"].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise SceneProbeError(f"implementation mismatch: {path}")
    return observed


def _gpu_snapshot(index: int) -> dict[str, Any]:
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
        raise SceneProbeError(result.stderr.strip() or "nvidia-smi failed")
    for line in result.stdout.splitlines():
        fields = [part.strip() for part in line.split(",", 5)]
        if int(fields[0]) == index:
            return {
                "index": int(fields[0]),
                "uuid": fields[1],
                "name": fields[2],
                "memory_total_mib": int(fields[3]),
                "memory_used_mib": int(fields[4]),
                "utilization_percent": int(fields[5]),
            }
    raise SceneProbeError(f"GPU {index} is absent")


def _selected_gpu_process_count(uuid: str) -> int:
    result = _run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid",
            "--format=csv,noheader,nounits",
        ],
        cwd=ROOT,
        timeout_seconds=30,
    )
    if result.returncode != 0:
        raise SceneProbeError(result.stderr.strip() or "nvidia-smi process query failed")
    return sum(
        1
        for line in result.stdout.splitlines()
        if line.strip() and line.split(",", 1)[0].strip() == uuid
    )


def _scene_subprocess(protocol: Mapping[str, Any]) -> dict[str, Any]:
    runtime = protocol["runtime"]
    scene = protocol["scene"]
    source_root = Path(runtime["source_root"])
    python = Path(runtime["simulator_python"])
    code = f"""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.environments.base import MujocoEnv

step_count = 0
original_step = MujocoEnv.step
def forbidden_step(self, action):
    global step_count
    step_count += 1
    raise RuntimeError('env.step is forbidden by the scene-only protocol')
MujocoEnv.step = forbidden_step

def digest_arrays(values):
    digest = hashlib.sha256()
    for key in sorted(values):
        array = np.asarray(values[key])
        header = json.dumps({{'key': key, 'dtype': str(array.dtype), 'shape': list(array.shape)}}, sort_keys=True, separators=(',', ':')).encode()
        digest.update(len(header).to_bytes(8, 'big'))
        digest.update(header)
        data = np.ascontiguousarray(array).tobytes()
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()

started = time.monotonic()
suite = benchmark.get_benchmark_dict()[{scene['suite']!r}](safety_level={scene['level']!r})
task = suite.get_task({scene['task_index']})
initial_states = suite.get_task_init_states({scene['task_index']})
initial_state = initial_states[{scene['episode_index']}]
bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
env = None
reset_count = 0
set_init_state_count = 0
try:
    env = OffScreenRenderEnv(
        bddl_file_name=bddl,
        camera_heights={scene['resolution']},
        camera_widths={scene['resolution']},
        camera_depths=True,
        render_gpu_device_id={protocol['gpu']['physical_index']},
    )
    env.seed({scene['seed']})
    env.reset()
    reset_count += 1
    observation = env.set_init_state(initial_state)
    set_init_state_count += 1
    joint_names = [str(name) for name in env.sim.model.joint_names]
    obstacle_joints = sorted(name for name in joint_names if 'obstacle' in name)
    camera_shapes = {{
        key: list(np.asarray(value).shape)
        for key, value in observation.items()
        if 'image' in key or 'depth' in key
    }}
    payload = {{
        'suite': {scene['suite']!r},
        'level': {scene['level']!r},
        'task_index': {scene['task_index']},
        'episode_index': {scene['episode_index']},
        'seed': {scene['seed']},
        'task_name': task.name,
        'task_language': task.language,
        'bddl_path': str(bddl),
        'initial_state_digest': hashlib.sha256(np.ascontiguousarray(np.asarray(initial_state)).tobytes()).hexdigest(),
        'initial_state_shape': list(np.asarray(initial_state).shape),
        'observation_digest': digest_arrays(observation),
        'observation_keys': sorted(observation),
        'camera_shapes': camera_shapes,
        'sim_model_counts': {{
            'nbody': int(env.sim.model.nbody),
            'njnt': int(env.sim.model.njnt),
            'ngeom': int(env.sim.model.ngeom),
        }},
        'obstacle_joints': obstacle_joints,
        'simulator_construction_count': 1,
        'reset_count': reset_count,
        'set_init_state_count': set_init_state_count,
        'env_step_count': step_count,
        'load_seconds': time.monotonic() - started,
    }}
finally:
    if env is not None:
        env.close()
    MujocoEnv.step = original_step
print('{MARKER}' + json.dumps(payload, sort_keys=True))
"""
    env = {
        "CUDA_VISIBLE_DEVICES": str(protocol["gpu"]["physical_index"]),
        "MUJOCO_EGL_DEVICE_ID": str(protocol["gpu"]["physical_index"]),
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "LIBERO_CONFIG_PATH": str(ROOT / runtime["libero_config_dir"]),
        "PYTHONPATH": f"{source_root / 'safelibero'}:{ROOT / 'src'}",
        "MPLCONFIGDIR": "/tmp/proofalign-aegis-matplotlib",
    }
    result = _run([str(python), "-c", code], cwd=source_root, env=env)
    lines = [line[len(MARKER) :] for line in result.stdout.splitlines() if line.startswith(MARKER)]
    if result.returncode != 0 or len(lines) != 1:
        raise SceneProbeError(
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
        raise SceneProbeError("scene subprocess did not emit an object")
    return value


def main() -> int:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    if protocol.get("schema") != "proofalign.safelibero-aegis-scene-protocol-v1":
        raise SceneProbeError("unsupported scene protocol schema")
    observed = _verify_files(protocol)
    r2_summary = load_json(ROOT / protocol["r2_model_gate"]["summary"])
    r2_ready = (
        r2_summary.get("model_load_ready") is True
        and r2_summary.get("scene_probe_authorized") is True
        and r2_summary.get("formal_rollout_authorized") is False
    )
    base = {
        "schema": SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256_file(protocol_path),
        "pinned_file_sha256": observed,
        "r2_model_load_ready": r2_ready,
        "executed": args.execute,
        "formal_rollout_authorized": False,
    }
    if not args.execute:
        base["status"] = "scene_probe_ready" if r2_ready else "blocked_by_r2"
        print(json.dumps(base, indent=2, sort_keys=True))
        return 0 if r2_ready else 2
    if not r2_ready:
        raise SceneProbeError("R2 does not authorize scene construction")

    gpu = _gpu_snapshot(protocol["gpu"]["physical_index"])
    expected_gpu = protocol["gpu"]
    if gpu["uuid"] != expected_gpu["uuid"]:
        raise SceneProbeError("EGL GPU identity mismatch")
    if gpu["memory_used_mib"] >= expected_gpu["max_prelaunch_used_memory_mib"]:
        raise SceneProbeError("EGL GPU exceeds prelaunch memory gate")
    process_count = _selected_gpu_process_count(gpu["uuid"])
    if process_count:
        raise SceneProbeError("EGL GPU already has a compute process")

    started_wall = time.time_ns()
    scene = _scene_subprocess(protocol)
    checks = {
        "task_name": scene.get("task_name") == protocol["scene"]["task_name"],
        "env_step_zero": scene.get("env_step_count") == 0,
        "one_simulator": scene.get("simulator_construction_count") == 1,
        "one_reset": scene.get("reset_count") == 1,
        "one_set_init_state": scene.get("set_init_state_count") == 1,
        "observation_present": bool(scene.get("observation_keys")),
        "camera_observations_present": len(scene.get("camera_shapes", {})) >= 6,
        "obstacle_joint_present": bool(scene.get("obstacle_joints")),
    }
    ready = all(checks.values())
    report = {
        **base,
        "executed": True,
        "started_unix_ns": started_wall,
        "gpu_before": gpu,
        "gpu_compute_process_count_before": process_count,
        "scene": scene,
        "checks": checks,
        "counters": {
            "policy_construction_count": 0,
            "policy_inference_call_count": 0,
            "groundingdino_inference_call_count": 0,
            "server_socket_bind_count": 0,
            "simulator_construction_count": scene.get("simulator_construction_count"),
            "env_step_count": scene.get("env_step_count"),
        },
        "scene_ready": ready,
        "formal_rollout_authorized": False,
        "status": "scene_ready_rollout_blocked" if ready else "scene_probe_failed",
    }
    if args.output:
        output = args.output.resolve()
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing report: {output}")
        dump_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
