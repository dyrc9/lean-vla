#!/usr/bin/env python3
"""Audit the official drawer joint source over all 50 frozen init states.

The execution path constructs and resets one SafeLIBERO scenario, applies each
frozen initial state, and reads one joint scalar. ``env.step`` is hard-patched to
raise.  No policy, model, socket, action, or dispatch path is imported.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.aegis_runtime import load_json, sha256_file  # noqa: E402
from proofalign.benchmark.safelibero_foundation import (  # noqa: E402
    build_safelibero_inventory,
)
from proofalign.benchmark.safelibero_open_region import (  # noqa: E402
    OFFICIAL_JOINT_SOURCE_ID,
    OFFICIAL_OPEN_THRESHOLD_M,
    audit_official_open_region_source,
)


SCHEMA = "proofalign.ctda-v2-open-region-coverage-v1"
PROTOCOL_SCHEMA = "proofalign.ctda-v2-open-region-coverage-protocol-v1"
MARKER = "PROOFALIGN_CTDA_V2_OPEN_REGION_COVERAGE="
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_open_region_coverage_protocol.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_open_region_coverage_summary.json"


class OpenRegionCoverageError(RuntimeError):
    pass


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 600,
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
        raise OpenRegionCoverageError(result.stderr.strip() or "nvidia-smi failed")
    for line in result.stdout.splitlines():
        values = [item.strip() for item in line.split(",", 5)]
        if int(values[0]) == index:
            return {
                "index": int(values[0]),
                "uuid": values[1],
                "name": values[2],
                "memory_total_mib": int(values[3]),
                "memory_used_mib": int(values[4]),
                "utilization_percent": int(values[5]),
            }
    raise OpenRegionCoverageError(f"GPU {index} is absent")


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
        raise OpenRegionCoverageError(result.stderr.strip() or "GPU process query failed")
    return sum(
        1
        for line in result.stdout.splitlines()
        if line.strip() and line.split(",", 1)[0].strip() == uuid
    )


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise OpenRegionCoverageError("unsupported OpenRegion coverage protocol schema")
    if protocol.get("authorization") != "simulator_initialization_only_no_step":
        raise OpenRegionCoverageError("OpenRegion protocol does not forbid dispatch")
    if protocol.get("formal_rollout_authorized") is not False:
        raise OpenRegionCoverageError("OpenRegion protocol must explicitly block rollout")

    source_root = Path(protocol["runtime"]["source_root"])
    inventory = build_safelibero_inventory(source_root)
    matches = [
        scenario
        for scenario in inventory["scenarios"]
        if scenario["unit_id"] == protocol["population"]["unit_id"]
    ]
    if len(matches) != 1:
        raise OpenRegionCoverageError("frozen OpenRegion scenario is not unique")
    scenario = matches[0]
    source_identity = audit_official_open_region_source(source_root)
    checks = {
        "source_commit": _run(["git", "rev-parse", "HEAD"], cwd=source_root).stdout.strip()
        == protocol["source"]["commit"],
        "source_tree": _run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=source_root
        ).stdout.strip()
        == protocol["source"]["git_tree"],
        "source_clean": _run(
            ["git", "status", "--porcelain=v1"], cwd=source_root
        ).stdout.strip()
        == "",
        "dataset_digest": inventory["dataset_digest"]
        == protocol["population"]["dataset_digest"],
        "unit_id": scenario["unit_id"] == protocol["population"]["unit_id"],
        "task_name": scenario["task_name"] == protocol["population"]["task_name"],
        "bddl_sha256": scenario["bddl_sha256"]
        == protocol["population"]["bddl_sha256"],
        "init_state_count": scenario["init_state_count"]
        == protocol["population"]["init_state_count"],
        "source_identity_digest": source_identity.source_identity_digest
        == protocol["open_region_binding"]["source_identity_digest"],
        "source_file_sha256": dict(source_identity.file_sha256)
        == protocol["open_region_binding"]["source_file_sha256"],
        "joint_source_id": protocol["open_region_binding"]["joint_source_id"]
        == OFFICIAL_JOINT_SOURCE_ID,
        "open_threshold": protocol["open_region_binding"]["open_when_less_than_m"]
        == OFFICIAL_OPEN_THRESHOLD_M,
        "simulator_python": Path(protocol["runtime"]["simulator_python"]).is_file(),
        "wire_parity_ready": load_json(ROOT / protocol["prerequisite"]["wire_parity_summary"])[
            "status"
        ]
        == "wire_lean_parity_ready_rollout_blocked",
        "wire_parity_summary_sha256": sha256_file(
            ROOT / protocol["prerequisite"]["wire_parity_summary"]
        )
        == protocol["prerequisite"]["wire_parity_summary_sha256"],
        "state_coverage_ready": load_json(
            ROOT / protocol["prerequisite"]["state_coverage_summary"]
        )["status"]
        == "state_coverage_ready_rollout_blocked",
        "state_coverage_summary_sha256": sha256_file(
            ROOT / protocol["prerequisite"]["state_coverage_summary"]
        )
        == protocol["prerequisite"]["state_coverage_summary_sha256"],
    }
    for relative, expected in protocol["implementation_hashes"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected
    if not all(checks.values()):
        raise OpenRegionCoverageError(f"OpenRegion preflight failed: {checks}")
    return {
        "protocol_sha256": sha256_file(protocol_path),
        "checks": checks,
        "scenario": scenario,
        "source_identity_digest": source_identity.source_identity_digest,
    }


def _coverage_subprocess(
    protocol: Mapping[str, Any], scenario: Mapping[str, Any]
) -> dict[str, Any]:
    runtime = protocol["runtime"]
    gpu_index = protocol["gpu"]["physical_index"]
    code = f"""
import hashlib
import json
from pathlib import Path
import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.environments.base import MujocoEnv

STEP_COUNT = 0
original_step = MujocoEnv.step
def forbidden_step(self, action):
    global STEP_COUNT
    STEP_COUNT += 1
    raise RuntimeError('env.step is forbidden by OpenRegion coverage protocol')
MujocoEnv.step = forbidden_step

suite = benchmark.get_benchmark_dict()[{scenario['suite']!r}](safety_level={scenario['safety_level']!r})
task = suite.get_task({scenario['task_index']})
initial_states = suite.get_task_init_states({scenario['task_index']})
bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
env = None
records = []
try:
    env = OffScreenRenderEnv(
        bddl_file_name=bddl,
        camera_heights={protocol['coverage']['camera_resolution']},
        camera_widths={protocol['coverage']['camera_resolution']},
        camera_depths=False,
        render_gpu_device_id={gpu_index},
    )
    env.seed({protocol['coverage']['seed']})
    env.reset()
    site = env.object_sites_dict[{protocol['open_region_binding']['region_id']!r}]
    joint_names = list(site.joints)
    for index, initial_state in enumerate(initial_states):
        env.set_init_state(initial_state)
        source_ok = joint_names == [{protocol['open_region_binding']['joint_source_id']!r}]
        qpos = None
        official_open = None
        strict_open = None
        in_range = False
        if source_ok:
            address = env.sim.model.get_joint_qpos_addr(joint_names[0])
            qpos = float(env.sim.data.qpos[address])
            official_open = bool(env.object_states_dict[{protocol['open_region_binding']['region_id']!r}].is_open())
            strict_open = qpos < {protocol['open_region_binding']['open_when_less_than_m']!r}
            in_range = (
                np.isfinite(qpos)
                and {protocol['open_region_binding']['joint_range_m'][0]!r} <= qpos
                and qpos <= {protocol['open_region_binding']['joint_range_m'][1]!r}
            )
        records.append({{
            'unit_id': {scenario['unit_id']!r} + ':init' + str(index),
            'episode_index': index,
            'joint_names': joint_names,
            'joint_source_exact': source_ok,
            'joint_position_m': qpos,
            'joint_position_finite_in_asset_range': in_range,
            'official_open': official_open,
            'strict_threshold_open': strict_open,
            'predicate_agreement': official_open is not None and official_open == strict_open,
        }})
finally:
    if env is not None:
        env.close()
    MujocoEnv.step = original_step

payload = {{
    'task_name': task.name,
    'bddl_sha256': hashlib.sha256(bddl.read_bytes()).hexdigest(),
    'expected_init_count': len(initial_states),
    'observed_init_count': len(records),
    'joint_source_coverage_count': sum(item['joint_source_exact'] for item in records),
    'finite_range_coverage_count': sum(item['joint_position_finite_in_asset_range'] for item in records),
    'predicate_agreement_count': sum(item['predicate_agreement'] for item in records),
    'env_step_count': STEP_COUNT,
    'simulator_construction_count': 1,
    'reset_count': 1,
    'set_init_state_count': len(records),
    'records': records,
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
        "MPLCONFIGDIR": "/tmp/proofalign-ctda-v2-open-region-matplotlib",
    }
    result = _run(
        [runtime["simulator_python"], "-c", code],
        cwd=source_root,
        env=env,
        timeout_seconds=protocol["coverage"]["timeout_seconds"],
    )
    rows = [
        line[len(MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(MARKER)
    ]
    if result.returncode != 0 or len(rows) != 1:
        raise OpenRegionCoverageError(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-4000:],
                    "stderr_tail": result.stderr[-4000:],
                },
                indent=2,
            )
        )
    return json.loads(rows[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    verified = _verify(protocol, protocol_path)
    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "protocol_ready_not_executed",
                    "protocol_sha256": verified["protocol_sha256"],
                    "unit_id": verified["scenario"]["unit_id"],
                    "init_state_count": verified["scenario"]["init_state_count"],
                    "formal_rollout_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    output = args.output.resolve()
    if output.exists():
        raise OpenRegionCoverageError(f"fresh output required: {output}")
    gpu_before = _gpu_snapshot(protocol["gpu"]["physical_index"])
    if gpu_before["uuid"] != protocol["gpu"]["uuid"]:
        raise OpenRegionCoverageError("OpenRegion GPU UUID mismatch")
    if gpu_before["memory_used_mib"] >= protocol["gpu"]["max_prelaunch_used_memory_mib"]:
        raise OpenRegionCoverageError("OpenRegion GPU memory gate failed")
    processes_before = _gpu_process_count(gpu_before["uuid"])
    if processes_before != 0:
        raise OpenRegionCoverageError("OpenRegion GPU has a prelaunch compute process")

    coverage = _coverage_subprocess(protocol, verified["scenario"])
    gpu_after = _gpu_snapshot(protocol["gpu"]["physical_index"])
    processes_after = _gpu_process_count(gpu_after["uuid"])
    expected = protocol["population"]["init_state_count"]
    checks = {
        "task_name": coverage["task_name"] == protocol["population"]["task_name"],
        "bddl_sha256": coverage["bddl_sha256"] == protocol["population"]["bddl_sha256"],
        "all_init_states_retained": coverage["observed_init_count"] == expected,
        "exact_joint_source_coverage": coverage["joint_source_coverage_count"] == expected,
        "finite_asset_range_coverage": coverage["finite_range_coverage_count"] == expected,
        "official_predicate_agreement": coverage["predicate_agreement_count"] == expected,
        "env_step_count_zero": coverage["env_step_count"] == 0,
        "simulator_construction_count": coverage["simulator_construction_count"] == 1,
        "reset_count": coverage["reset_count"] == 1,
        "set_init_state_count": coverage["set_init_state_count"] == expected,
        "post_gpu_process_count_zero": processes_after == 0,
    }
    if not all(checks.values()):
        raise OpenRegionCoverageError(f"OpenRegion coverage failed: {checks}")
    summary = {
        "schema": SCHEMA,
        "status": "open_region_coverage_ready_rollout_blocked",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": verified["protocol_sha256"],
        "preflight_checks": verified["checks"],
        "checks": checks,
        "source_identity_digest": verified["source_identity_digest"],
        "coverage": coverage,
        "gpu": {
            "before": gpu_before,
            "after": gpu_after,
            "process_count_before": processes_before,
            "process_count_after": processes_after,
        },
        "counters": {
            "env_step_count": 0,
            "model_construction_count": 0,
            "policy_inference_count": 0,
            "socket_bind_count": 0,
            "dispatch_count": 0,
        },
        "formal_rollout_authorized": False,
        "next_gate": "Implement the post-filter/recovery no-dispatch adapter.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
