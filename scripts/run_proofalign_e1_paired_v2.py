#!/usr/bin/env python3
"""E1-v2 launcher correcting the frozen v1 physical-EGL startup binding.

V1 is retained byte-for-byte with its 24 pre-environment startup failures.
This launcher composes the compact v2 amendment with the pinned v1 protocol,
adds an actual robosuite import probe under the selected GPU environment, and
uses the physical GPU id for MuJoCo EGL while JAX uses logical visible device 0.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_proofalign_e1_paired as v1


DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e1_clean_pilot_protocol_v2.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "proofalign_e1_clean_pilot_v2_20260716"
_ORIGINAL_MAKE_EPISODE_ARGS = v1.make_episode_args
_ORIGINAL_PREFLIGHT = v1.preflight


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_effective_protocol(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    amendment = v1.load_object(path, "E1-v2 protocol")
    if amendment.get("schema") != "proofalign.e1.clean-paired-pilot-amendment.v2":
        raise v1.ProtocolError("unexpected E1-v2 amendment schema")
    if amendment.get("status") != "frozen_ready_for_preflight":
        raise v1.ProtocolError("E1-v2 amendment is not frozen_ready_for_preflight")
    base_ref = amendment.get("base_protocol", {})
    base_path = v1.repo_path(str(base_ref.get("path", "")))
    if _digest(base_path) != base_ref.get("sha256"):
        raise v1.ProtocolError("E1-v2 base protocol digest mismatch")
    for item in amendment.get("prior_failed_run", {}).get("artifacts", []):
        artifact = v1.repo_path(str(item["path"]))
        if not artifact.is_file() or _digest(artifact) != item["sha256"]:
            raise v1.ProtocolError(f"E1-v2 prior failure evidence mismatch: {artifact}")
    effective = deepcopy(v1.load_object(base_path, "E1-v1 base protocol"))
    effective["required_files"].extend(amendment["additional_required_files"])
    effective["claim_boundary"] = amendment["claim_boundary"]
    effective["runtime"].update(amendment["runtime_correction"])
    effective["artifact_policy"]["default_output_root"] = str(
        amendment["artifact_policy"]["default_output_root"]
    )
    effective["protocol_amendment"] = {
        "path": str(path),
        "sha256": _digest(path),
        "schema": amendment["schema"],
        "prior_failed_run_status": amendment["prior_failed_run"]["status"],
    }
    return amendment, effective


def _physical_gpu() -> int:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    first = visible.split(",", 1)[0]
    if not first.isdigit():
        raise v1.ProtocolError("E1-v2 requires one numeric CUDA_VISIBLE_DEVICES id")
    return int(first)


def corrected_make_episode_args(
    protocol: dict[str, Any],
    spec: v1.EpisodeSpec,
    output: Path,
    artifact_dir: Path,
) -> Any:
    physical_gpu = _physical_gpu()
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(physical_gpu)
    os.environ["MUJOCO_GL"] = "egl"
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    args = _ORIGINAL_MAKE_EPISODE_ARGS(protocol, spec, output, artifact_dir)
    args.render_gpu_device_id = physical_gpu
    return args


def _runtime_import_probe(protocol: dict[str, Any], selected_gpu: int) -> dict[str, Any]:
    interpreter = REPO_ROOT / protocol["runtime"]["python_interpreter"]
    overlay = v1.repo_path(protocol["runtime"]["libero_import_overlay"])
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                (str(overlay), str(REPO_ROOT / "src"), str(REPO_ROOT))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLCONFIGDIR": "/tmp/proofalign-e1-v2-mpl",
            "CUDA_VISIBLE_DEVICES": str(selected_gpu),
            "MUJOCO_EGL_DEVICE_ID": str(selected_gpu),
            "MUJOCO_GL": "egl",
            "PYOPENGL_PLATFORM": "egl",
        }
    )
    code = (
        "import json; import robosuite.utils.binding_utils as binding; "
        "import libero.libero as core; "
        "from libero.libero.benchmark import get_benchmark; "
        "b=get_benchmark('affordance')(); "
        "print(json.dumps({'core':core.__file__,'tasks':b.n_tasks,"
        "'cuda':binding.CUDA_VISIBLE_DEVICES,'egl':binding.MUJOCO_EGL_DEVICE_ID}))"
    )
    completed = subprocess.run(
        (str(interpreter), "-c", code),
        cwd=REPO_ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise v1.ProtocolError(
            "E1-v2 robosuite GPU import probe failed: " + completed.stderr.strip()
        )
    try:
        result = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise v1.ProtocolError("E1-v2 GPU import probe returned malformed output") from exc
    expected = str(selected_gpu)
    if result.get("tasks") != 15 or result.get("cuda") != expected or result.get("egl") != expected:
        raise v1.ProtocolError(f"E1-v2 GPU import binding mismatch: {result}")
    return result


def corrected_preflight(
    protocol: dict[str, Any], protocol_path: Path, *, selected_gpu: int | None
) -> dict[str, Any]:
    report = _ORIGINAL_PREFLIGHT(
        protocol, protocol_path, selected_gpu=selected_gpu
    )
    if report.get("ready") is not True:
        return report
    probe_gpu = selected_gpu
    if probe_gpu is None:
        eligible = report.get("gpu", {}).get("eligible_physical_ids", [])
        probe_gpu = int(eligible[0]) if eligible else None
    try:
        if probe_gpu is None:
            raise v1.ProtocolError("E1-v2 has no GPU for its runtime import probe")
        report["gpu"]["runtime_import_probe"] = _runtime_import_probe(
            protocol, probe_gpu
        )
        report["gpu"]["jax_visible_device_inside_process"] = 0
        report["gpu"]["mujoco_egl_physical_device"] = probe_gpu
    except v1.ProtocolError as exc:
        report["ready"] = False
        report["issues"].append(str(exc))
    return report


def install_corrections() -> None:
    v1.make_episode_args = corrected_make_episode_args
    v1.preflight = corrected_preflight


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gpu", type=int)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--validate-results", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.resolve()
    _amendment, protocol = load_effective_protocol(protocol_path)
    install_corrections()
    if args.execute:
        if args.gpu is None:
            raise v1.ProtocolError("E1-v2 --execute requires --gpu")
        summary = v1.execute(
            protocol,
            protocol_path,
            args.output_root,
            selected_gpu=args.gpu,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.validate_results:
        v1.assert_protocol_consistency(protocol, protocol_path)
        summary = v1.validate_retained_results(protocol, args.output_root.resolve())
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    report = corrected_preflight(
        protocol, protocol_path, selected_gpu=args.gpu
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
