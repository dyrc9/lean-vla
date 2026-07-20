#!/usr/bin/env python3
"""R2 CPU/OSMesa OpenRegion audit with the LIBERO wrapper path fixed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import ctda_v2_open_region_coverage_cpu as base


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_open_region_coverage_protocol_r2.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_open_region_coverage_summary_r2.json"
BASE_VERIFY = base._verify


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    """Reuse the frozen R1 checks while requiring the explicit R2 revision."""

    if protocol.get("protocol_id") != "ctda-v2-open-region-source-coverage-r2-cpu":
        raise base.OpenRegionCPUCoverageError("CPU R2 runner requires the frozen r2 protocol")
    normalized = dict(protocol)
    normalized["protocol_id"] = "ctda-v2-open-region-source-coverage-r1-cpu"
    return BASE_VERIFY(normalized, protocol_path)


def _execute(protocol: Mapping[str, Any], scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Read the source-bound joint from the wrapped LIBERO task environment."""

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
    task_env = env.env
    site = task_env.object_sites_dict[{protocol['open_region_binding']['region_id']!r}]
    joints = list(site.joints)
    for index, state in enumerate(states):
        env.set_init_state(state)
        exact = joints == [{protocol['open_region_binding']['joint_source_id']!r}]
        qpos = official = strict = None
        finite_range = False
        if exact:
            address = env.sim.model.get_joint_qpos_addr(joints[0])
            qpos = float(env.sim.data.qpos[address])
            official = bool(task_env.object_states_dict[{protocol['open_region_binding']['region_id']!r}].is_open())
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

print({base.MARKER!r} + json.dumps({{
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
        "MESA_SHADER_CACHE_DIR": "/tmp/proofalign-ctda-v2-mesa-cache",
    }
    result = base._run(
        [protocol["runtime"]["simulator_python"], "-c", code],
        cwd=source_root,
        env=env,
        timeout_seconds=protocol["coverage"]["timeout_seconds"],
    )
    payloads = [
        line[len(base.MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(base.MARKER)
    ]
    if result.returncode != 0 or len(payloads) != 1:
        raise base.OpenRegionCPUCoverageError(
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


if __name__ == "__main__":
    base.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base._verify = _verify
    base._execute = _execute
    raise SystemExit(base.main())
