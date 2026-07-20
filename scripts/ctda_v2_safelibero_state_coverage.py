#!/usr/bin/env python3
"""No-step CTDA v2 observation-key coverage over all frozen SafeLIBERO init states."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.aegis_runtime import load_json, sha256_file  # noqa: E402
from proofalign.benchmark.safelibero_ctda_support import (  # noqa: E402
    SafeLiberoCTDAV2StateAdapter,
    audit_safelibero_support,
    compile_safelibero_mission_template,
    parse_safelibero_goal_manifest,
)
from proofalign.benchmark.safelibero_foundation import build_safelibero_inventory  # noqa: E402


SCHEMA = "proofalign.ctda-v2-safelibero-state-coverage-v1"
MARKER = "PROOFALIGN_CTDA_V2_STATE_COVERAGE="
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_safelibero_state_coverage_protocol.json"


class StateCoverageError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or execute the frozen 32-scenario/1600-init SafeLIBERO state-key "
            "coverage audit. env.step, policy/model inference, and socket binds are forbidden."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 1800,
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
        raise StateCoverageError(result.stderr.strip() or "nvidia-smi failed")
    for line in result.stdout.splitlines():
        fields = [item.strip() for item in line.split(",", 5)]
        if int(fields[0]) == index:
            return {
                "index": int(fields[0]),
                "uuid": fields[1],
                "name": fields[2],
                "memory_total_mib": int(fields[3]),
                "memory_used_mib": int(fields[4]),
                "utilization_percent": int(fields[5]),
            }
    raise StateCoverageError(f"GPU {index} is absent")


def _gpu_process_count(uuid: str) -> int:
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
        raise StateCoverageError(result.stderr.strip() or "nvidia-smi process query failed")
    return sum(
        1
        for line in result.stdout.splitlines()
        if line.strip() and line.split(",", 1)[0].strip() == uuid
    )


def _scenario_records(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inventory = build_safelibero_inventory(source_root)
    records: list[dict[str, Any]] = []
    for scenario in inventory["scenarios"]:
        bddl = source_root / scenario["bddl_path"]
        manifest = parse_safelibero_goal_manifest(
            bddl.read_text(encoding="utf-8"),
            suite=scenario["suite"],
            task_index=scenario["task_index"],
            safety_level=scenario["safety_level"],
            task_name=scenario["task_name"],
            bddl_sha256=scenario["bddl_sha256"],
        )
        template = compile_safelibero_mission_template(manifest)
        adapter = SafeLiberoCTDAV2StateAdapter(
            manifest,
            producer_id="official-safelibero-observation-adapter",
            producer_version="ctda-v2-state-coverage-v1",
            max_sensor_age_ns=100_000_000,
        )
        records.append(
            {
                **scenario,
                "goal_manifest_digest": manifest.manifest_digest,
                "mission_template_digest": template.template_digest,
                "action_set": list(template.action_set),
                "adapter_digest": adapter.adapter_digest,
                "required_keys": list(adapter.required_keys),
                "reference_position_keys": sorted(
                    {f"{atom.reference}_pos" for atom in manifest.goal_atoms}
                ),
            }
        )
    return records, inventory


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    if protocol.get("schema") != "proofalign.ctda-v2-safelibero-state-coverage-protocol-v1":
        raise StateCoverageError("unsupported state coverage protocol schema")
    if protocol.get("authorization") != "simulator_initialization_only_no_step":
        raise StateCoverageError("state coverage protocol does not forbid dispatch")
    source_root = Path(protocol["runtime"]["source_root"])
    records, inventory = _scenario_records(source_root)
    checks = {
        "source_commit": _run(
            ["git", "rev-parse", "HEAD"], cwd=source_root, timeout_seconds=30
        ).stdout.strip()
        == protocol["source"]["commit"],
        "source_tree": _run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=source_root, timeout_seconds=30
        ).stdout.strip()
        == protocol["source"]["git_tree"],
        "source_clean": _run(
            ["git", "status", "--porcelain=v1"], cwd=source_root, timeout_seconds=30
        ).stdout.strip()
        == "",
        "dataset_digest": inventory["dataset_digest"] == protocol["dataset"]["dataset_digest"],
        "scenario_count": len(records) == protocol["dataset"]["scenario_count"],
        "candidate_episode_count": inventory["candidate_episode_count"]
        == protocol["dataset"]["candidate_episode_count"],
        "simulator_python": Path(protocol["runtime"]["simulator_python"]).is_file(),
        "r3_scene_ready": load_json(ROOT / protocol["prerequisite"]["scene_summary"]).get(
            "scene_ready"
        )
        is True,
    }
    for relative, expected in protocol["implementation"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected
    if not all(checks.values()):
        raise StateCoverageError(f"state coverage preflight failed: {checks}")
    return {
        "protocol_sha256": sha256_file(protocol_path),
        "checks": checks,
        "records": records,
        "inventory": inventory,
    }


def _coverage_subprocess(
    protocol: Mapping[str, Any], scenario_records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    runtime = protocol["runtime"]
    gpu_index = protocol["gpu"]["physical_index"]
    records_json = json.dumps(list(scenario_records), sort_keys=True)
    code = f"""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.environments.base import MujocoEnv

SCENARIOS = json.loads({records_json!r})
STEP_COUNT = 0
original_step = MujocoEnv.step
def forbidden_step(self, action):
    global STEP_COUNT
    STEP_COUNT += 1
    raise RuntimeError('env.step is forbidden by CTDA v2 state coverage protocol')
MujocoEnv.step = forbidden_step

def array_digest(value):
    array = np.ascontiguousarray(np.asarray(value))
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode())
    digest.update(json.dumps(list(array.shape)).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()

def selected_digest(observation, keys):
    payload = []
    for key in sorted(keys):
        array = np.asarray(observation[key])
        payload.append({{'key': key, 'dtype': str(array.dtype), 'shape': list(array.shape), 'value': array.tolist()}})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

started = time.monotonic()
units = []
scenario_rows = []
simulator_construction_count = 0
reset_count = 0
set_init_state_count = 0
try:
    for scenario in SCENARIOS:
        suite = benchmark.get_benchmark_dict()[scenario['suite']](safety_level=scenario['safety_level'])
        task = suite.get_task(scenario['task_index'])
        initial_states = suite.get_task_init_states(scenario['task_index'])
        bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
        env = None
        scenario_units = []
        scenario_issue = None
        try:
            env = OffScreenRenderEnv(
                bddl_file_name=bddl,
                camera_heights={protocol['coverage']['camera_resolution']},
                camera_widths={protocol['coverage']['camera_resolution']},
                camera_depths=False,
                render_gpu_device_id={gpu_index},
            )
            simulator_construction_count += 1
            env.seed({protocol['coverage']['seed']})
            env.reset()
            reset_count += 1
            obstacle_names = sorted(set(
                str(name).replace('_joint0', '')
                for name in env.sim.model.joint_names
                if 'obstacle' in str(name)
            ))
            for episode_index in range(len(initial_states)):
                initial_state = initial_states[episode_index]
                observation = env.set_init_state(initial_state)
                set_init_state_count += 1
                observation = dict(observation)
                simulator_site_source_keys = []
                for key in scenario['reference_position_keys']:
                    if key in observation:
                        continue
                    site_name = key[:-4]
                    try:
                        observation[key] = np.asarray(env.sim.data.get_site_xpos(site_name)).copy()
                        simulator_site_source_keys.append(key)
                    except Exception:
                        pass
                missing = [key for key in scenario['required_keys'] if key not in observation]
                malformed = []
                for key in scenario['required_keys']:
                    if key not in observation:
                        continue
                    expected = 4 if key == 'robot0_eef_quat' else 2 if key == 'robot0_gripper_qpos' else 3
                    array = np.asarray(observation[key])
                    if array.size != expected or not np.isfinite(array).all():
                        malformed.append({{'key': key, 'shape': list(array.shape), 'size': int(array.size)}})
                active = []
                for obstacle_name in obstacle_names:
                    key = obstacle_name + '_pos'
                    if key not in observation:
                        continue
                    position = np.asarray(observation[key]).reshape(-1)
                    if len(position) >= 3 and position[2] > 0 and -0.5 < position[0] < 0.5 and -0.5 < position[1] < 0.5:
                        active.append(obstacle_name)
                unit = {{
                    'unit_id': scenario['unit_id'] + ':init' + str(episode_index),
                    'scenario_id': scenario['unit_id'],
                    'episode_index': episode_index,
                    'initial_state_sha256': array_digest(initial_state),
                    'required_state_keys_complete': not missing and not malformed,
                    'missing_keys': missing,
                    'malformed_keys': malformed,
                    'selected_state_sha256': None if missing or malformed else selected_digest(observation, scenario['required_keys']),
                    'simulator_site_source_keys': simulator_site_source_keys,
                    'active_obstacle_count': len(active),
                    'active_obstacle_id': active[0] if len(active) == 1 else None,
                    'collision_producer_source_complete': len(active) == 1,
                }}
                units.append(unit)
                scenario_units.append(unit)
        except Exception as exc:
            scenario_issue = type(exc).__name__ + ': ' + str(exc)
        finally:
            if env is not None:
                env.close()
        manifest_lines = [
            json.dumps(item, sort_keys=True, separators=(',', ':'))
            for item in scenario_units
        ]
        scenario_rows.append({{
            'unit_id': scenario['unit_id'],
            'task_name_matches': task.name == scenario['task_name'],
            'bddl_sha256': hashlib.sha256(bddl.read_bytes()).hexdigest(),
            'bddl_matches': hashlib.sha256(bddl.read_bytes()).hexdigest() == scenario['bddl_sha256'],
            'expected_init_count': scenario['init_state_count'],
            'observed_init_count': len(scenario_units),
            'required_state_key_coverage': sum(item['required_state_keys_complete'] for item in scenario_units),
            'collision_source_coverage': sum(item['collision_producer_source_complete'] for item in scenario_units),
            'unit_manifest_sha256': hashlib.sha256(('\\n'.join(manifest_lines) + '\\n').encode()).hexdigest(),
            'issue': scenario_issue,
        }})
finally:
    MujocoEnv.step = original_step

payload = {{
    'scenario_rows': scenario_rows,
    'units': units,
    'scenario_count': len(scenario_rows),
    'unit_count': len(units),
    'state_key_coverage_count': sum(item['required_state_keys_complete'] for item in units),
    'collision_source_coverage_count': sum(item['collision_producer_source_complete'] for item in units),
    'simulator_construction_count': simulator_construction_count,
    'reset_count': reset_count,
    'set_init_state_count': set_init_state_count,
    'env_step_count': STEP_COUNT,
    'elapsed_seconds': time.monotonic() - started,
}}
print({MARKER!r} + json.dumps(payload, sort_keys=True))
"""
    source_root = Path(runtime["source_root"])
    env = {
        "CUDA_VISIBLE_DEVICES": str(gpu_index),
        "MUJOCO_EGL_DEVICE_ID": str(gpu_index),
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "LIBERO_CONFIG_PATH": str(ROOT / runtime["libero_config_dir"]),
        "PYTHONPATH": str(source_root / "safelibero"),
        "MPLCONFIGDIR": "/tmp/proofalign-ctda-v2-state-coverage-matplotlib",
    }
    result = _run(
        [runtime["simulator_python"], "-c", code],
        cwd=source_root,
        env=env,
        timeout_seconds=protocol["coverage"]["timeout_seconds"],
    )
    lines = [
        line[len(MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(MARKER)
    ]
    if result.returncode != 0 or len(lines) != 1:
        raise StateCoverageError(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-5000:],
                    "stderr_tail": result.stderr[-5000:],
                },
                indent=2,
            )
        )
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise StateCoverageError("state coverage subprocess emitted a non-object")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    verified = _verify(protocol, protocol_path)
    base = {
        "schema": SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": verified["protocol_sha256"],
        "authorization": protocol["authorization"],
        "preflight_checks": verified["checks"],
        "executed": args.execute,
        "formal_rollout_authorized": False,
    }
    if not args.execute:
        base["status"] = "state_coverage_ready"
        print(json.dumps(base, indent=2, sort_keys=True))
        return 0

    gpu = _gpu_snapshot(protocol["gpu"]["physical_index"])
    if gpu["uuid"] != protocol["gpu"]["uuid"]:
        raise StateCoverageError("state coverage GPU UUID mismatch")
    if gpu["memory_used_mib"] >= protocol["gpu"]["max_prelaunch_used_memory_mib"]:
        raise StateCoverageError("state coverage GPU exceeds prelaunch memory gate")
    prelaunch_processes = _gpu_process_count(gpu["uuid"])
    if prelaunch_processes:
        raise StateCoverageError("state coverage GPU already has a compute process")
    coverage = _coverage_subprocess(protocol, verified["records"])
    post_gpu = _gpu_snapshot(protocol["gpu"]["physical_index"])
    post_processes = _gpu_process_count(gpu["uuid"])
    expected = protocol["dataset"]
    checks = {
        "scenario_count": coverage.get("scenario_count") == expected["scenario_count"],
        "unit_count": coverage.get("unit_count") == expected["candidate_episode_count"],
        "state_key_coverage": coverage.get("state_key_coverage_count")
        == expected["candidate_episode_count"],
        "collision_source_coverage": coverage.get("collision_source_coverage_count")
        == expected["candidate_episode_count"],
        "simulator_construction_count": coverage.get("simulator_construction_count")
        == expected["scenario_count"],
        "reset_count": coverage.get("reset_count") == expected["scenario_count"],
        "set_init_state_count": coverage.get("set_init_state_count")
        == expected["candidate_episode_count"],
        "env_step_count_zero": coverage.get("env_step_count") == 0,
        "scenario_rows_complete": all(
            row.get("issue") is None
            and row.get("task_name_matches") is True
            and row.get("bddl_matches") is True
            and row.get("observed_init_count") == row.get("expected_init_count") == 50
            for row in coverage.get("scenario_rows", ())
        ),
        "post_process_count_zero": post_processes == 0,
    }
    ready = all(checks.values())
    report = {
        **base,
        "executed_at_ns": time.time_ns(),
        "gpu": {
            "prelaunch": gpu,
            "prelaunch_compute_process_count": prelaunch_processes,
            "post": post_gpu,
            "post_compute_process_count": post_processes,
        },
        "coverage": coverage,
        "checks": checks,
        "state_coverage_ready": ready,
        "policy_construction_count": 0,
        "policy_inference_count": 0,
        "model_construction_count": 0,
        "socket_bind_count": 0,
        "formal_rollout_authorized": False,
        "status": "state_coverage_ready_rollout_blocked" if ready else "state_coverage_failed",
        "claim_boundary": (
            "Simulator initialization/set-state observation-key and official collision-source "
            "coverage only. No env.step, policy/model inference, task outcome, safety outcome, "
            "CTDA authorization, or rollout readiness is established."
        ),
    }
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite state coverage report: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "status": report["status"],
                "checks": checks,
                "scenario_count": coverage.get("scenario_count"),
                "unit_count": coverage.get("unit_count"),
                "state_key_coverage_count": coverage.get("state_key_coverage_count"),
                "collision_source_coverage_count": coverage.get(
                    "collision_source_coverage_count"
                ),
                "env_step_count": coverage.get("env_step_count"),
                "elapsed_seconds": coverage.get("elapsed_seconds"),
                "formal_rollout_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
