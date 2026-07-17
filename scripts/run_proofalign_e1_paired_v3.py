#!/usr/bin/env python3
"""Run the frozen E1-v3 clean paired pilot after pre-dispatch repairs.

V3 retains the immutable v1/v2 failures, updates only the policy-output audit
and invalid-pair analysis gate, and adds a real OpenPI policy-output probe that
never calls ``env.step`` before a fresh result directory may be created.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts import run_proofalign_e1_paired as v1
from scripts import run_proofalign_e1_paired_v2 as v2


DEFAULT_PROTOCOL = (
    REPO_ROOT / "experiments" / "proofalign_e1_clean_pilot_protocol_v3.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "results" / "proofalign_e1_clean_pilot_v3_20260717"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_artifact(item: dict[str, Any], *, label: str) -> None:
    path = v1.repo_path(str(item.get("path", "")))
    if not path.is_file() or _digest(path) != item.get("sha256"):
        raise v1.ProtocolError(f"E1-v3 {label} mismatch: {path}")


def load_effective_protocol(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    amendment = v1.load_object(path, "E1-v3 protocol")
    if amendment.get("schema") != "proofalign.e1.clean-paired-pilot-amendment.v3":
        raise v1.ProtocolError("unexpected E1-v3 amendment schema")
    if amendment.get("status") != "frozen_ready_for_preflight":
        raise v1.ProtocolError("E1-v3 amendment is not frozen_ready_for_preflight")

    base_ref = amendment.get("base_protocol", {})
    base_path = v1.repo_path(str(base_ref.get("path", "")))
    if not base_path.is_file() or _digest(base_path) != base_ref.get("sha256"):
        raise v1.ProtocolError("E1-v3 base protocol digest mismatch")
    for run in amendment.get("prior_failed_runs", []):
        for item in run.get("artifacts", []):
            _verify_artifact(item, label=f"prior {run.get('version')} evidence")

    effective = deepcopy(v1.load_object(base_path, "E1-v1 base protocol"))
    replacements = {
        str(item["path"]): str(item["sha256"])
        for item in amendment.get("required_file_replacements", [])
    }
    base_paths = {str(item["path"]) for item in effective["required_files"]}
    if not replacements or not set(replacements).issubset(base_paths):
        raise v1.ProtocolError("E1-v3 required-file replacements are malformed")
    for item in effective["required_files"]:
        relative = str(item["path"])
        if relative in replacements:
            item["sha256"] = replacements[relative]
    effective["required_files"].extend(amendment["additional_required_files"])
    effective["claim_boundary"] = amendment["claim_boundary"]
    effective["runtime"].update(amendment["runtime_correction"])
    effective["analysis"].update(amendment["analysis_correction"])
    effective["artifact_policy"]["default_output_root"] = str(
        amendment["artifact_policy"]["default_output_root"]
    )
    effective["protocol_amendment"] = {
        "path": str(path),
        "sha256": _digest(path),
        "schema": amendment["schema"],
        "prior_failed_run_versions": [
            str(item.get("version")) for item in amendment["prior_failed_runs"]
        ],
    }
    return amendment, effective


def _probe_environment(protocol: dict[str, Any], selected_gpu: int) -> dict[str, str]:
    env = os.environ.copy()
    overlay = v1.repo_path(protocol["runtime"]["libero_import_overlay"])
    lean_bin = v1.repo_path(protocol["runtime"]["lean_bin_directory"])
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                (str(overlay), str(REPO_ROOT / "src"), str(REPO_ROOT))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLCONFIGDIR": "/tmp/proofalign-e1-v3-mpl",
            "CUDA_VISIBLE_DEVICES": str(selected_gpu),
            "MUJOCO_EGL_DEVICE_ID": str(selected_gpu),
            "MUJOCO_GL": "egl",
            "PYOPENGL_PLATFORM": "egl",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
            "LIBERO_SAFETY_ROOT": str(REPO_ROOT / "external" / "LIBERO-Safety"),
            "PATH": str(lean_bin) + os.pathsep + env.get("PATH", ""),
        }
    )
    return env


def policy_output_probe_child(
    protocol: dict[str, Any], *, selected_gpu: int
) -> dict[str, Any]:
    """Load one frozen unit and audit one real policy output without dispatch."""

    os.environ.update(_probe_environment(protocol, selected_gpu))
    import_roots = [
        str(v1.repo_path(protocol["runtime"]["libero_import_overlay"])),
        str(REPO_ROOT / "src"),
        str(REPO_ROOT),
    ]
    sys.path[:0] = [item for item in import_roots if item not in sys.path]

    from proofalign.benchmark.libero_online_runner import (
        build_policy,
        create_initialized_env,
        load_libero_task_runtime,
    )
    from proofalign.benchmark.libero_e1_policy_audit import (
        install_e1_policy_audit,
    )
    from proofalign.benchmark.libero_online_wrapper import _policy_action_audit

    install_e1_policy_audit()
    spec = v1.expected_specs(protocol)[0]
    with tempfile.TemporaryDirectory(
        prefix="proofalign-e1-v3-policy-probe-", dir="/tmp"
    ) as temporary:
        probe_root = Path(temporary)
        runtime_config = v1.ensure_libero_runtime_config(probe_root)
        os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
        args = v2.corrected_make_episode_args(
            protocol,
            spec,
            probe_root / "unused_episode.json",
            probe_root / "unused_ctda_artifacts",
        )
        runtime = load_libero_task_runtime(
            benchmark_name=args.benchmark,
            task_id=args.task_id,
            init_state_id=args.init_state_id,
            bddl_file=args.bddl_file,
        )
        environment = create_initialized_env(runtime, args)
        try:
            observation = getattr(
                environment, "_proofalign_initialized_observation", None
            )
            if observation is None:
                raise v1.ProtocolError(
                    "E1-v3 policy probe lacks set_init_state observation"
                )
            policy = build_policy(args)
            reset_episode = getattr(policy, "reset_episode", None)
            if callable(reset_episode):
                reset_episode()
            raw_output = policy(runtime.instruction, observation, [])
            call_id, action_chunk, metadata = _policy_action_audit(
                raw_output, default_call_id="e1-v3-probe:000000"
            )
            if not action_chunk:
                raise v1.ProtocolError("E1-v3 policy probe returned no audited actions")
            # ``allow_nan=False`` independently checks the retained JSON boundary.
            json.dumps(metadata, sort_keys=True, allow_nan=False)
            return {
                "episode_id": spec.episode_id,
                "policy_call_id": call_id,
                "audited_action_count": len(action_chunk),
                "metadata_sha256": v1.canonical_digest(metadata),
                "env_step_called": False,
            }
        finally:
            try:
                if hasattr(environment, "close"):
                    environment.close()
            finally:
                snapshot = getattr(
                    environment, "_proofalign_bddl_snapshot_dir", None
                )
                if snapshot:
                    shutil.rmtree(str(snapshot), ignore_errors=True)


def _policy_output_probe(
    protocol_path: Path, protocol: dict[str, Any], selected_gpu: int
) -> dict[str, Any]:
    interpreter = REPO_ROOT / protocol["runtime"]["python_interpreter"]
    completed = subprocess.run(
        (
            str(interpreter),
            str(Path(__file__).resolve()),
            "--protocol",
            str(protocol_path),
            "--gpu",
            str(selected_gpu),
            "--policy-audit-probe-child",
        ),
        cwd=REPO_ROOT,
        env=_probe_environment(protocol, selected_gpu),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise v1.ProtocolError(
            "E1-v3 policy-output audit probe failed: " + completed.stderr.strip()
        )
    try:
        result = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise v1.ProtocolError(
            "E1-v3 policy-output audit probe returned malformed output"
        ) from exc
    if result.get("env_step_called") is not False:
        raise v1.ProtocolError("E1-v3 policy-output probe dispatch boundary changed")
    return result


def corrected_preflight(
    protocol: dict[str, Any], protocol_path: Path, *, selected_gpu: int | None
) -> dict[str, Any]:
    report = v2.corrected_preflight(
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
            raise v1.ProtocolError("E1-v3 has no GPU for policy-output probe")
        report["gpu"]["policy_output_audit_probe"] = _policy_output_probe(
            protocol_path, protocol, probe_gpu
        )
    except v1.ProtocolError as exc:
        report["ready"] = False
        report["issues"].append(str(exc))
    return report


def install_corrections() -> None:
    from proofalign.benchmark.libero_e1_policy_audit import install_e1_policy_audit

    install_e1_policy_audit()
    v1.make_episode_args = v2.corrected_make_episode_args
    v1.preflight = corrected_preflight


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gpu", type=int)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--validate-results", action="store_true")
    modes.add_argument(
        "--policy-audit-probe-child", action="store_true", help=argparse.SUPPRESS
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.resolve()
    _amendment, protocol = load_effective_protocol(protocol_path)
    install_corrections()
    if args.policy_audit_probe_child:
        if args.gpu is None:
            raise v1.ProtocolError("E1-v3 probe child requires --gpu")
        print(
            json.dumps(
                policy_output_probe_child(protocol, selected_gpu=args.gpu),
                sort_keys=True,
            )
        )
        return 0
    if args.execute:
        if args.gpu is None:
            raise v1.ProtocolError("E1-v3 --execute requires --gpu")
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
        summary = v1.validate_retained_results(
            protocol, args.output_root.resolve()
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    report = corrected_preflight(
        protocol, protocol_path, selected_gpu=args.gpu
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
