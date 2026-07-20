#!/usr/bin/env python3
"""No-step CPU probe of the official OpenRegion strict threshold and both classes."""

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
from proofalign.benchmark.safelibero_foundation import build_safelibero_inventory  # noqa: E402
from proofalign.benchmark.safelibero_open_region import (  # noqa: E402
    OFFICIAL_JOINT_SOURCE_ID,
    OFFICIAL_OPEN_THRESHOLD_M,
    audit_official_open_region_source,
)


SCHEMA = "proofalign.ctda-v2-open-region-threshold-probe-v1"
PROTOCOL_SCHEMA = "proofalign.ctda-v2-open-region-threshold-protocol-v1"
MARKER = "PROOFALIGN_CTDA_V2_OPEN_REGION_THRESHOLD="
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_open_region_threshold_protocol.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_open_region_threshold_summary.json"


class OpenRegionThresholdProbeError(RuntimeError):
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


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise OpenRegionThresholdProbeError("unsupported OpenRegion threshold protocol schema")
    if protocol.get("protocol_id") != "ctda-v2-open-region-threshold-r0-cpu":
        raise OpenRegionThresholdProbeError("unexpected OpenRegion threshold protocol id")
    if (
        protocol.get("authorization") != "simulator_state_injection_only_no_step"
        or protocol.get("formal_rollout_authorized") is not False
        or protocol["runtime"].get("render_backend") != "osmesa"
        or protocol["runtime"].get("render_device_id") != -1
    ):
        raise OpenRegionThresholdProbeError("threshold probe authorization boundary changed")
    source_root = Path(protocol["runtime"]["source_root"])
    inventory = build_safelibero_inventory(source_root)
    scenarios = [
        item
        for item in inventory["scenarios"]
        if item["unit_id"] == protocol["population"]["unit_id"]
    ]
    if len(scenarios) != 1:
        raise OpenRegionThresholdProbeError("frozen drawer scenario is not unique")
    scenario = scenarios[0]
    identity = audit_official_open_region_source(source_root)
    points = protocol["probe"]["joint_positions_m"]
    expected = protocol["probe"]["expected_open"]
    checks = {
        "source_commit": _run(["git", "rev-parse", "HEAD"], cwd=source_root).stdout.strip()
        == protocol["source"]["commit"],
        "source_tree": _run(["git", "rev-parse", "HEAD^{tree}"], cwd=source_root).stdout.strip()
        == protocol["source"]["git_tree"],
        "source_clean": _run(["git", "status", "--porcelain=v1"], cwd=source_root).stdout.strip()
        == "",
        "dataset_digest": inventory["dataset_digest"] == protocol["population"]["dataset_digest"],
        "unit_id": scenario["unit_id"] == protocol["population"]["unit_id"],
        "bddl_sha256": scenario["bddl_sha256"] == protocol["population"]["bddl_sha256"],
        "init_sha256": scenario["init_sha256"] == protocol["population"]["init_sha256"],
        "source_identity_digest": identity.source_identity_digest
        == protocol["open_region_binding"]["source_identity_digest"],
        "joint_source": protocol["open_region_binding"]["joint_source_id"]
        == OFFICIAL_JOINT_SOURCE_ID,
        "threshold": protocol["open_region_binding"]["open_when_less_than_m"]
        == OFFICIAL_OPEN_THRESHOLD_M,
        "probe_shape": len(points) == len(expected) == 5,
        "strict_boundary_present": OFFICIAL_OPEN_THRESHOLD_M in points,
        "both_expected_classes": set(expected) == {False, True},
        "simulator_python": Path(protocol["runtime"]["simulator_python"]).is_file(),
    }
    for relative, expected_hash in protocol["implementation_hashes"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected_hash
    for name, dependency in protocol["prerequisites"].items():
        path = ROOT / dependency["path"]
        checks[f"prerequisite:{name}"] = path.is_file() and sha256_file(path) == dependency["sha256"]
    if not all(checks.values()):
        raise OpenRegionThresholdProbeError(f"threshold probe preflight failed: {checks}")
    return {
        "checks": checks,
        "protocol_sha256": sha256_file(protocol_path),
        "scenario": scenario,
        "source_identity_digest": identity.source_identity_digest,
    }


def _execute(protocol: Mapping[str, Any], scenario: Mapping[str, Any]) -> dict[str, Any]:
    code = f"""
import hashlib
import json
from pathlib import Path
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.environments.base import MujocoEnv

STEP_COUNT = 0
original_step = MujocoEnv.step
def forbidden_step(self, action):
    global STEP_COUNT
    STEP_COUNT += 1
    raise RuntimeError('env.step is forbidden by OpenRegion threshold protocol')
MujocoEnv.step = forbidden_step

suite = benchmark.get_benchmark_dict()[{scenario['suite']!r}](safety_level={scenario['safety_level']!r})
task = suite.get_task({scenario['task_index']})
states = suite.get_task_init_states({scenario['task_index']})
bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
env = None
rows = []
try:
    env = OffScreenRenderEnv(
        bddl_file_name=bddl,
        camera_heights={protocol['probe']['camera_resolution']},
        camera_widths={protocol['probe']['camera_resolution']},
        camera_depths=False,
        render_gpu_device_id=-1,
    )
    env.seed({protocol['probe']['seed']})
    env.reset()
    env.set_init_state(states[0])
    task_env = env.env
    site = task_env.object_sites_dict[{protocol['open_region_binding']['region_id']!r}]
    joints = list(site.joints)
    if joints != [{protocol['open_region_binding']['joint_source_id']!r}]:
        raise RuntimeError('threshold probe joint source mismatch')
    joint = joints[0]
    for index, requested in enumerate({protocol['probe']['joint_positions_m']!r}):
        env.sim.data.set_joint_qpos(joint, requested)
        env.sim.forward()
        address = env.sim.model.get_joint_qpos_addr(joint)
        observed = float(env.sim.data.qpos[address])
        official = bool(task_env.object_states_dict[{protocol['open_region_binding']['region_id']!r}].is_open())
        strict = observed < {protocol['open_region_binding']['open_when_less_than_m']!r}
        rows.append({{
            'probe_index': index,
            'requested_joint_position_m': requested,
            'observed_joint_position_m': observed,
            'official_open': official,
            'strict_threshold_open': strict,
            'predicate_agreement': official == strict,
        }})
finally:
    if env is not None:
        env.close()
    MujocoEnv.step = original_step

print({MARKER!r} + json.dumps({{
    'task_name': task.name,
    'bddl_sha256': hashlib.sha256(bddl.read_bytes()).hexdigest(),
    'joint_names': joints,
    'env_step_count': STEP_COUNT,
    'simulator_construction_count': 1,
    'reset_count': 1,
    'set_init_state_count': 1,
    'state_injection_count': len(rows),
    'records': rows,
}}, sort_keys=True))
"""
    source_root = Path(protocol["runtime"]["source_root"])
    env = {
        "MUJOCO_GL": "osmesa",
        "PYOPENGL_PLATFORM": "osmesa",
        "LIBERO_CONFIG_PATH": str(ROOT / protocol["runtime"]["libero_config_dir"]),
        "PYTHONPATH": str(source_root / "safelibero"),
        "MPLCONFIGDIR": "/tmp/proofalign-ctda-v2-open-region-threshold",
        "MESA_SHADER_CACHE_DIR": "/tmp/proofalign-ctda-v2-mesa-cache",
    }
    result = _run(
        [protocol["runtime"]["simulator_python"], "-c", code],
        cwd=source_root,
        env=env,
        timeout_seconds=protocol["probe"]["timeout_seconds"],
    )
    payloads = [
        line[len(MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(MARKER)
    ]
    if result.returncode != 0 or len(payloads) != 1:
        raise OpenRegionThresholdProbeError(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-4000:],
                    "stderr_tail": result.stderr[-4000:],
                },
                indent=2,
            )
        )
    return json.loads(payloads[0])


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
                    "probe_count": len(protocol["probe"]["joint_positions_m"]),
                    "render_backend": "osmesa",
                    "formal_rollout_authorized": False,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    output = args.output.resolve()
    if output.exists():
        raise OpenRegionThresholdProbeError(f"fresh output required: {output}")
    observed = _execute(protocol, verified["scenario"])
    expected_positions = protocol["probe"]["joint_positions_m"]
    expected_open = protocol["probe"]["expected_open"]
    checks = {
        "task_name": observed["task_name"] == protocol["population"]["task_name"],
        "bddl_sha256": observed["bddl_sha256"] == protocol["population"]["bddl_sha256"],
        "joint_source_exact": observed["joint_names"]
        == [protocol["open_region_binding"]["joint_source_id"]],
        "probe_count": len(observed["records"]) == len(expected_positions),
        "requested_values_exact": [item["requested_joint_position_m"] for item in observed["records"]]
        == expected_positions,
        "observed_values_exact": [item["observed_joint_position_m"] for item in observed["records"]]
        == expected_positions,
        "official_expected_classes": [item["official_open"] for item in observed["records"]]
        == expected_open,
        "predicate_agreement": all(item["predicate_agreement"] for item in observed["records"]),
        "strict_boundary_closed": next(
            item
            for item in observed["records"]
            if item["observed_joint_position_m"] == OFFICIAL_OPEN_THRESHOLD_M
        )["official_open"]
        is False,
        "env_step_count_zero": observed["env_step_count"] == 0,
        "single_simulator_reset_init": (
            observed["simulator_construction_count"] == 1
            and observed["reset_count"] == 1
            and observed["set_init_state_count"] == 1
        ),
        "state_injection_count": observed["state_injection_count"] == len(expected_positions),
    }
    if not all(checks.values()):
        raise OpenRegionThresholdProbeError(f"threshold probe failed: {checks}")
    summary = {
        "schema": SCHEMA,
        "status": "open_region_threshold_ready_rollout_blocked",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": verified["protocol_sha256"],
        "preflight_checks": verified["checks"],
        "checks": checks,
        "source_identity_digest": verified["source_identity_digest"],
        "probe": observed,
        "counters": {
            "env_step_count": 0,
            "model_construction_count": 0,
            "policy_inference_count": 0,
            "socket_bind_count": 0,
            "dispatch_count": 0,
        },
        "formal_rollout_authorized": False,
        "claim_boundary": protocol["claim_boundary"],
        "next_gate": protocol["next_gate"],
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
