#!/usr/bin/env python3
"""CPU/OSMesa fallback for the frozen OpenRegion 50-init no-step audit."""

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


SCHEMA = "proofalign.ctda-v2-open-region-coverage-v1"
PROTOCOL_SCHEMA = "proofalign.ctda-v2-open-region-coverage-protocol-v1"
MARKER = "PROOFALIGN_CTDA_V2_OPEN_REGION_CPU_COVERAGE="
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_open_region_coverage_protocol_r1.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_open_region_coverage_summary_r1.json"


class OpenRegionCPUCoverageError(RuntimeError):
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
        raise OpenRegionCPUCoverageError("unsupported OpenRegion protocol schema")
    if protocol.get("protocol_id") != "ctda-v2-open-region-source-coverage-r1-cpu":
        raise OpenRegionCPUCoverageError("CPU runner requires the frozen r1 protocol")
    if (
        protocol.get("authorization") != "simulator_initialization_only_no_step"
        or protocol.get("formal_rollout_authorized") is not False
        or protocol["runtime"].get("render_backend") != "osmesa"
        or protocol["runtime"].get("render_device_id") != -1
    ):
        raise OpenRegionCPUCoverageError("CPU protocol execution boundary is invalid")
    source_root = Path(protocol["runtime"]["source_root"])
    inventory = build_safelibero_inventory(source_root)
    scenarios = [
        item
        for item in inventory["scenarios"]
        if item["unit_id"] == protocol["population"]["unit_id"]
    ]
    if len(scenarios) != 1:
        raise OpenRegionCPUCoverageError("frozen drawer scenario is not unique")
    scenario = scenarios[0]
    identity = audit_official_open_region_source(source_root)
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
        "init_sha256": scenario["init_sha256"]
        == protocol["population"]["init_sha256"],
        "init_state_count": scenario["init_state_count"] == 50,
        "source_identity_digest": identity.source_identity_digest
        == protocol["open_region_binding"]["source_identity_digest"],
        "source_file_sha256": dict(identity.file_sha256)
        == protocol["open_region_binding"]["source_file_sha256"],
        "joint_source": protocol["open_region_binding"]["joint_source_id"]
        == OFFICIAL_JOINT_SOURCE_ID,
        "threshold": protocol["open_region_binding"]["open_when_less_than_m"]
        == OFFICIAL_OPEN_THRESHOLD_M,
        "simulator_python": Path(protocol["runtime"]["simulator_python"]).is_file(),
    }
    for name in ("wire_parity_summary", "state_coverage_summary"):
        relative = protocol["prerequisite"][name]
        checks[f"{name}_sha256"] = sha256_file(ROOT / relative) == protocol[
            "prerequisite"
        ][f"{name}_sha256"]
    for relative, expected in protocol["implementation_hashes"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected
    if not all(checks.values()):
        raise OpenRegionCPUCoverageError(f"CPU OpenRegion preflight failed: {checks}")
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
import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from robosuite.environments.base import MujocoEnv

STEP_COUNT = 0
original_step = MujocoEnv.step
def forbidden_step(self, action):
    global STEP_COUNT
    STEP_COUNT += 1
    raise RuntimeError('env.step is forbidden by OpenRegion CPU coverage protocol')
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
        camera_heights={protocol['coverage']['camera_resolution']},
        camera_widths={protocol['coverage']['camera_resolution']},
        camera_depths=False,
        render_gpu_device_id=-1,
    )
    env.seed({protocol['coverage']['seed']})
    env.reset()
    site = env.object_sites_dict[{protocol['open_region_binding']['region_id']!r}]
    joints = list(site.joints)
    for index, state in enumerate(states):
        env.set_init_state(state)
        exact = joints == [{protocol['open_region_binding']['joint_source_id']!r}]
        qpos = official = strict = None
        finite_range = False
        if exact:
            address = env.sim.model.get_joint_qpos_addr(joints[0])
            qpos = float(env.sim.data.qpos[address])
            official = bool(env.object_states_dict[{protocol['open_region_binding']['region_id']!r}].is_open())
            strict = qpos < {protocol['open_region_binding']['open_when_less_than_m']!r}
            finite_range = bool(
                np.isfinite(qpos)
                and {protocol['open_region_binding']['joint_range_m'][0]!r} <= qpos
                and qpos <= {protocol['open_region_binding']['joint_range_m'][1]!r}
            )
        rows.append({{
            'unit_id': {scenario['unit_id']!r} + ':init' + str(index),
            'episode_index': index,
            'joint_names': joints,
            'joint_source_exact': exact,
            'joint_position_m': qpos,
            'joint_position_finite_in_asset_range': finite_range,
            'official_open': official,
            'strict_threshold_open': strict,
            'predicate_agreement': official is not None and official == strict,
        }})
finally:
    if env is not None:
        env.close()
    MujocoEnv.step = original_step

print({MARKER!r} + json.dumps({{
    'task_name': task.name,
    'bddl_sha256': hashlib.sha256(bddl.read_bytes()).hexdigest(),
    'observed_init_count': len(rows),
    'joint_source_coverage_count': sum(item['joint_source_exact'] for item in rows),
    'finite_range_coverage_count': sum(item['joint_position_finite_in_asset_range'] for item in rows),
    'predicate_agreement_count': sum(item['predicate_agreement'] for item in rows),
    'env_step_count': STEP_COUNT,
    'simulator_construction_count': 1,
    'reset_count': 1,
    'set_init_state_count': len(rows),
    'records': rows,
}}, sort_keys=True))
"""
    source_root = Path(protocol["runtime"]["source_root"])
    env = {
        "MUJOCO_GL": "osmesa",
        "PYOPENGL_PLATFORM": "osmesa",
        "LIBERO_CONFIG_PATH": str(ROOT / protocol["runtime"]["libero_config_dir"]),
        "PYTHONPATH": str(source_root / "safelibero"),
        "MPLCONFIGDIR": "/tmp/proofalign-ctda-v2-open-region-osmesa",
    }
    result = _run(
        [protocol["runtime"]["simulator_python"], "-c", code],
        cwd=source_root,
        env=env,
        timeout_seconds=protocol["coverage"]["timeout_seconds"],
    )
    payloads = [
        line[len(MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(MARKER)
    ]
    if result.returncode != 0 or len(payloads) != 1:
        raise OpenRegionCPUCoverageError(
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
                    "unit_id": verified["scenario"]["unit_id"],
                    "init_state_count": 50,
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
        raise OpenRegionCPUCoverageError(f"fresh output required: {output}")
    coverage = _execute(protocol, verified["scenario"])
    expected = 50
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
    }
    if not all(checks.values()):
        raise OpenRegionCPUCoverageError(f"CPU OpenRegion coverage failed: {checks}")
    summary = {
        "schema": SCHEMA,
        "status": "open_region_coverage_ready_rollout_blocked",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": verified["protocol_sha256"],
        "render_backend": "osmesa",
        "preflight_checks": verified["checks"],
        "checks": checks,
        "source_identity_digest": verified["source_identity_digest"],
        "coverage": coverage,
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
