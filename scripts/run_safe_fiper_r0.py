#!/usr/bin/env python3
"""Auditable launcher for the frozen upstream SAFE and FIPER R0 pipelines."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UV = Path("/home/ldx/.conda/envs/proofalign-libero/bin/uv")
DEFAULT_SAFE_ENV = Path("/data0/ldx/uv-envs/safe-r0")
DEFAULT_SAFE_OPENPI_ENV = Path("/data0/ldx/uv-envs/safe-r0-openpi")
DEFAULT_SAFE_CLIENT_ENV = Path("/data0/ldx/uv-envs/safe-r0-libero-client")
DEFAULT_FIPER_ENV = Path("/data0/ldx/uv-envs/fiper-r0")
DEFAULT_OPENPI_DATA_HOME = Path("/data0/ldx/safe-fiper-r0/openpi")
DEFAULT_SAFE_ROOT = REPO_ROOT / "external" / "SAFE"
DEFAULT_SAFE_OPENPI_ROOT = REPO_ROOT / "external" / "SAFE-openpi"
DEFAULT_FIPER_ROOT = REPO_ROOT / "external" / "fiper"


class LaunchError(RuntimeError):
    """Raised when a frozen run cannot start or finish safely."""


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]

    def rendered(self) -> str:
        env = " ".join(f"{key}={shlex.quote(value)}" for key, value in sorted(self.env.items()))
        command = shlex.join(self.argv)
        return f"cd {shlex.quote(self.cwd)} && {env} {command}".strip()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LaunchError(f"expected a JSON object: {path}")
    return payload


def validate_fiper_restart_authorization(args: argparse.Namespace) -> None:
    path = args.restart_authorization
    if path is None:
        raise LaunchError("fresh FIPER execution requires --restart-authorization")
    authorization = load_json(path)
    checks = (
        (
            authorization.get("schema")
            == "proofalign.fiper-r0-restart-authorization.v1",
            "restart authorization schema changed",
        ),
        (
            authorization.get("protocol_status")
            == "preregistered_execution_authorized_after_commit",
            "restart authorization is not executable",
        ),
        (authorization.get("scope", {}).get("target") == "fiper", "restart target changed"),
        (
            authorization.get("parent_protocol", {}).get("sha256")
            == file_sha256(args.fiper_protocol),
            "frozen FIPER protocol digest changed",
        ),
        (
            authorization.get("source", {}).get("commit")
            == command_output(("git", "rev-parse", "HEAD"), cwd=args.fiper_root).get("stdout"),
            "frozen FIPER source commit changed",
        ),
        (
            authorization.get("environment", {}).get("path")
            == str(args.fiper_env.resolve()),
            "FIPER environment path changed",
        ),
        (
            authorization.get("environment", {}).get("reuse_existing_environment") is True,
            "restart must reuse the existing FIPER environment",
        ),
        (
            authorization.get("environment", {}).get("create_environment") is False,
            "restart cannot create an environment",
        ),
        (
            authorization.get("environment", {}).get("install_dependencies") is False,
            "restart cannot install dependencies",
        ),
        (
            authorization.get("execution", {}).get("run_dir") == str(args.run_dir.resolve()),
            "fresh result directory changed",
        ),
        (
            authorization.get("execution", {}).get("policy_gpu") == args.policy_gpu,
            "selected FIPER GPU changed",
        ),
        (
            authorization.get("result_directory_policy", {}).get("mode") == "fresh",
            "FIPER restart must use a fresh result directory",
        ),
        (
            authorization.get("result_directory_policy", {}).get("resume_prior_attempt") is False,
            "FIPER restart cannot resume a prior attempt",
        ),
        (
            authorization.get("result_directory_policy", {}).get("merge_partial_outputs") is False,
            "FIPER restart cannot merge partial outputs",
        ),
    )
    for condition, message in checks:
        if not condition:
            raise LaunchError(message)


def shared_env() -> dict[str, str]:
    return {
        "HF_HOME": "/data0/ldx/huggingface",
        "HUGGINGFACE_HUB_CACHE": "/data0/ldx/huggingface/hub",
        "TRANSFORMERS_CACHE": "/data0/ldx/huggingface/transformers",
        "HF_ENDPOINT": "https://hf-mirror.com",
        "UV_CACHE_DIR": "/data0/ldx/uv-cache",
        "UV_PYTHON_INSTALL_DIR": "/data0/ldx/uv-python",
        "PIP_CACHE_DIR": "/data0/ldx/pip-cache",
        "MPLCONFIGDIR": "/tmp/proofalign-safe-fiper-mpl",
        "XDG_CACHE_HOME": "/tmp/proofalign-safe-fiper-cache",
        "WANDB_MODE": "offline",
    }


def safe_rollout_plan(args: argparse.Namespace) -> list[CommandSpec]:
    protocol = load_json(args.safe_protocol)
    rollout = protocol["rollout_generation"]
    save_name = args.safe_save_name
    runtime_root = args.run_dir.resolve()
    server_env = shared_env() | {
        "OPENPI_DATA_HOME": str(args.openpi_data_home.resolve()),
        "UV_PROJECT_ENVIRONMENT": str(args.safe_openpi_env.resolve()),
        "CUDA_VISIBLE_DEVICES": str(args.policy_gpu),
    }
    client_env = shared_env() | {
        "CUDA_VISIBLE_DEVICES": str(args.egl_gpu),
        "MUJOCO_EGL_DEVICE_ID": str(args.egl_gpu),
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "NUMBA_CACHE_DIR": "/tmp/proofalign-safe-numba",
        "LIBERO_CONFIG_PATH": str(args.libero_config_dir.resolve()),
        "PYTHONPATH": os.pathsep.join(
            (
                str((args.safe_openpi_root / "third_party" / "libero").resolve()),
                str((args.safe_openpi_root / "packages" / "openpi-client" / "src").resolve()),
            )
        ),
    }
    server = CommandSpec(
        name="safe-rollout-server",
        argv=(
            str(args.uv),
            "--project",
            str(args.safe_openpi_root.resolve()),
            "run",
            "python",
            str((args.safe_openpi_root / "scripts" / "serve_policy.py").resolve()),
            "--env",
            "LIBERO",
            "--record",
            "--save_name",
            save_name,
            "--port",
            str(args.port),
            "policy:checkpoint",
            "--policy.config",
            rollout["policy_config"],
            "--policy.dir",
            str(args.safe_checkpoint.resolve()),
        ),
        cwd=str(runtime_root),
        env=server_env,
    )
    client = CommandSpec(
        name="safe-rollout-client",
        argv=(
            str(args.safe_client_env.resolve() / "bin" / "python"),
            str((args.safe_openpi_root / "examples" / "libero" / "main.py").resolve()),
            "--args.host",
            "127.0.0.1",
            "--args.port",
            str(args.port),
            "--args.task_suite_name",
            rollout["suite"],
            "--args.start_task_id",
            str(rollout["task_ids"][0]),
            "--args.end_task_id",
            str(rollout["task_ids"][-1]),
            "--args.num_trials_per_task",
            str(rollout["num_trials_per_task"]),
            "--args.replan_steps",
            str(rollout["replan_steps"]),
            "--args.num_steps_wait",
            str(rollout["num_steps_wait"]),
            "--args.seed",
            str(rollout["env_seed"]),
            "--args.save_name",
            save_name,
        ),
        cwd=str(runtime_root),
        env=client_env,
    )
    return [server, client]


def safe_detector_plan(args: argparse.Namespace) -> list[CommandSpec]:
    rollout_parent = args.safe_rollout_root.resolve().parent
    env = shared_env() | {
        "PATH": f"{args.safe_env.resolve() / 'bin'}:{os.environ.get('PATH', '')}",
        "SAFE_OPENPI_ROLLOUT_ROOT": f"{rollout_parent}{os.sep}",
    }
    return [
        CommandSpec(
            name="safe-detector-full-matrix",
            argv=("bash", "scripts/batch_training/submit_pi0diff_libero.bash"),
            cwd=str(args.safe_root.resolve()),
            env=env,
        )
    ]


def fiper_plan(args: argparse.Namespace) -> list[CommandSpec]:
    env = shared_env() | {
        "PATH": f"{args.fiper_env.resolve() / 'bin'}:{os.environ.get('PATH', '')}",
        "CUDA_VISIBLE_DEVICES": str(args.policy_gpu),
        "PROOFALIGN_FIPER_ROOT": str(args.fiper_root.resolve()),
    }
    return [
        CommandSpec(
            name="fiper-official-full-pipeline",
            argv=(
                str(args.fiper_env.resolve() / "bin" / "python"),
                str((REPO_ROOT / "scripts" / "run_fiper_compat.py").resolve()),
                f"hydra.run.dir={args.run_dir.resolve() / 'hydra'}",
            ),
            cwd=str(args.fiper_root.resolve()),
            env=env,
        )
    ]


def command_output(argv: Iterable[str], *, cwd: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(tuple(argv), cwd=cwd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": list(argv), "returncode": 127, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "argv": list(argv),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def manifest(args: argparse.Namespace, specs: list[CommandSpec]) -> dict[str, Any]:
    protocols = [args.fiper_protocol] if args.target == "fiper" else [args.safe_protocol]
    if args.restart_authorization is not None:
        protocols.append(args.restart_authorization)
    return {
        "schema": "proofalign.safe-fiper-r0-run-manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "workspace": str(REPO_ROOT),
        "protocols": [
            {
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "payload": load_json(path),
            }
            for path in protocols
        ],
        "commands": [asdict(spec) | {"rendered": spec.rendered()} for spec in specs],
        "versions": {
            "uv": command_output((str(args.uv), "--version"), cwd=REPO_ROOT),
            "proofalign": command_output(("git", "rev-parse", "HEAD"), cwd=REPO_ROOT),
            "proofalign_status": command_output(
                ("git", "status", "--porcelain=v1"), cwd=REPO_ROOT
            ),
            "safe": command_output(("git", "rev-parse", "HEAD"), cwd=args.safe_root),
            "safe_status": command_output(
                ("git", "status", "--porcelain=v1"), cwd=args.safe_root
            ),
            "safe_openpi": command_output(("git", "rev-parse", "HEAD"), cwd=args.safe_openpi_root),
            "safe_openpi_status": command_output(
                ("git", "status", "--porcelain=v1"), cwd=args.safe_openpi_root
            ),
            "fiper": command_output(("git", "rev-parse", "HEAD"), cwd=args.fiper_root),
            "fiper_status": command_output(
                ("git", "status", "--porcelain=v1"), cwd=args.fiper_root
            ),
            "gpu": command_output(
                (
                    "nvidia-smi",
                    "--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu",
                    "--format=csv,noheader",
                ),
                cwd=REPO_ROOT,
            ),
            "gpu_compute_apps": command_output(
                (
                    "nvidia-smi",
                    "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
                    "--format=csv,noheader",
                ),
                cwd=REPO_ROOT,
            ),
        },
        "status": "dry_run" if args.dry_run else "started",
    }


def validate_execution_manifest(args: argparse.Namespace, run_manifest: dict[str, Any]) -> None:
    versions = run_manifest["versions"]
    required_commands = (
        "uv",
        "proofalign",
        "proofalign_status",
        "safe",
        "safe_status",
        "safe_openpi",
        "safe_openpi_status",
        "fiper",
        "fiper_status",
        "gpu",
        "gpu_compute_apps",
    )
    for name in required_commands:
        if versions[name].get("returncode") != 0:
            raise LaunchError(f"manifest provenance command failed: {name}")
    for name in ("proofalign_status", "safe_status", "safe_openpi_status", "fiper_status"):
        if versions[name].get("stdout"):
            raise LaunchError(f"execute requires a clean checkout: {name}")
    if args.target != "fiper":
        return
    authorization = load_json(args.restart_authorization)
    selected_uuid = authorization["execution"]["gpu_uuid"]
    selected_index = str(args.policy_gpu)
    inventory = [
        [field.strip() for field in line.split(",")]
        for line in versions["gpu"].get("stdout", "").splitlines()
        if line.strip()
    ]
    if not any(
        len(fields) >= 2 and fields[0] == selected_index and fields[1] == selected_uuid
        for fields in inventory
    ):
        raise LaunchError("selected FIPER GPU index/UUID no longer matches authorization")
    compute_uuids = {
        line.split(",", 1)[0].strip()
        for line in versions["gpu_compute_apps"].get("stdout", "").splitlines()
        if line.strip()
    }
    if selected_uuid in compute_uuids:
        raise LaunchError("selected FIPER GPU gained a compute process before execute")


def wait_for_port(host: str, port: int, process: subprocess.Popen[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LaunchError(f"policy server exited before readiness with code {process.returncode}")
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise LaunchError(f"policy server did not listen on {host}:{port} within {timeout:.0f}s")


def process_env(spec: CommandSpec) -> dict[str, str]:
    return os.environ.copy() | spec.env


def execute_safe_rollout(args: argparse.Namespace, specs: list[CommandSpec]) -> None:
    server_spec, client_spec = specs
    server_log_path = args.run_dir / "safe_server.log"
    client_log_path = args.run_dir / "safe_client.log"
    with server_log_path.open("w", encoding="utf-8") as server_log:
        server = subprocess.Popen(
            server_spec.argv,
            cwd=server_spec.cwd,
            env=process_env(server_spec),
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            wait_for_port("127.0.0.1", args.port, server, args.server_timeout)
            with client_log_path.open("w", encoding="utf-8") as client_log:
                result = subprocess.run(
                    client_spec.argv,
                    cwd=client_spec.cwd,
                    env=process_env(client_spec),
                    stdout=client_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
            if result.returncode != 0:
                raise LaunchError(f"SAFE rollout client exited with code {result.returncode}")
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGINT)
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGTERM)
                    server.wait(timeout=30)


def execute_sequential(args: argparse.Namespace, specs: list[CommandSpec]) -> None:
    for index, spec in enumerate(specs):
        log_path = args.run_dir / f"{index:02d}_{spec.name}.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(
                spec.argv,
                cwd=spec.cwd,
                env=process_env(spec),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if result.returncode != 0:
            raise LaunchError(f"{spec.name} exited with code {result.returncode}; see {log_path}")


def prepare_fiper_runtime_data(args: argparse.Namespace) -> tuple[Path, Path]:
    """Expose immutable rollouts through a fresh, run-owned FIPER data tree."""

    protocol = load_json(args.fiper_protocol)
    source_root = Path(protocol["dataset"]["extracted_data_root"]).resolve()
    runtime_root = args.run_dir.resolve() / "runtime_data"
    data_link = args.fiper_root.resolve() / "data"
    if data_link.exists() or data_link.is_symlink():
        raise LaunchError(f"refusing to replace existing FIPER data path: {data_link}")
    runtime_root.mkdir(parents=True, exist_ok=False)
    for task in protocol["dataset"]["tasks_in_order"]:
        rollout_source = source_root / task / "rollouts"
        if not rollout_source.is_dir():
            raise LaunchError(f"official FIPER rollout directory is missing: {rollout_source}")
        task_root = runtime_root / task
        task_root.mkdir()
        (task_root / "rollouts").symlink_to(rollout_source, target_is_directory=True)
    data_link.symlink_to(runtime_root, target_is_directory=True)
    return data_link, runtime_root


def remove_fiper_data_link(data_link: Path, runtime_root: Path) -> None:
    if not data_link.is_symlink():
        return
    if data_link.resolve() != runtime_root.resolve():
        raise LaunchError(f"FIPER data link changed during execution: {data_link}")
    data_link.unlink()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("safe-rollout", "safe-detector", "fiper"), required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--uv", type=Path, default=DEFAULT_UV)
    parser.add_argument("--safe-protocol", type=Path, default=REPO_ROOT / "experiments" / "safe_r0_protocol.json")
    parser.add_argument("--fiper-protocol", type=Path, default=REPO_ROOT / "experiments" / "fiper_r0_protocol.json")
    parser.add_argument("--restart-authorization", type=Path)
    parser.add_argument("--safe-root", type=Path, default=DEFAULT_SAFE_ROOT)
    parser.add_argument("--safe-openpi-root", type=Path, default=DEFAULT_SAFE_OPENPI_ROOT)
    parser.add_argument("--fiper-root", type=Path, default=DEFAULT_FIPER_ROOT)
    parser.add_argument("--safe-env", type=Path, default=DEFAULT_SAFE_ENV)
    parser.add_argument("--safe-openpi-env", type=Path, default=DEFAULT_SAFE_OPENPI_ENV)
    parser.add_argument("--safe-client-env", type=Path, default=DEFAULT_SAFE_CLIENT_ENV)
    parser.add_argument("--fiper-env", type=Path, default=DEFAULT_FIPER_ENV)
    parser.add_argument("--openpi-data-home", type=Path, default=DEFAULT_OPENPI_DATA_HOME)
    parser.add_argument("--safe-checkpoint", type=Path, default=DEFAULT_OPENPI_DATA_HOME / "openpi-assets" / "checkpoints" / "pi0_libero")
    parser.add_argument("--safe-rollout-root", type=Path, default=Path("/data0/ldx/safe-fiper-r0/safe/rollouts/pi0-libero_10"))
    parser.add_argument("--safe-save-name", default="pi0-libero_10")
    parser.add_argument(
        "--libero-config-dir",
        type=Path,
        default=REPO_ROOT / "experiments" / "safe_fiper_r0_env" / "libero_config",
    )
    parser.add_argument("--policy-gpu", type=int, default=-1)
    parser.add_argument("--egl-gpu", type=int, default=-1)
    parser.add_argument("--port", type=int, default=18020)
    parser.add_argument("--server-timeout", type=float, default=900.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.target in {"safe-rollout", "fiper"} and args.policy_gpu < 0:
        raise LaunchError("--policy-gpu must be selected from a fresh nvidia-smi inventory")
    if args.target == "safe-rollout" and (args.egl_gpu < 0 or args.egl_gpu == args.policy_gpu):
        raise LaunchError("SAFE rollout requires distinct explicit --policy-gpu and --egl-gpu values")
    if args.target == "fiper" and (args.execute or args.restart_authorization is not None):
        validate_fiper_restart_authorization(args)
    if args.target == "safe-rollout":
        specs = safe_rollout_plan(args)
    elif args.target == "safe-detector":
        specs = safe_detector_plan(args)
    else:
        specs = fiper_plan(args)
    run_manifest = manifest(args, specs)
    print(json.dumps(run_manifest, indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    validate_execution_manifest(args, run_manifest)
    if args.run_dir.exists():
        raise LaunchError(f"refusing to reuse result directory: {args.run_dir}")
    args.run_dir.mkdir(parents=True, exist_ok=False)
    write_json(args.run_dir / "run_manifest.json", run_manifest)
    fiper_runtime: tuple[Path, Path] | None = None
    try:
        if args.target == "safe-rollout":
            execute_safe_rollout(args, specs)
        elif args.target == "fiper":
            fiper_runtime = prepare_fiper_runtime_data(args)
            execute_sequential(args, specs)
        else:
            execute_sequential(args, specs)
    except KeyboardInterrupt:
        run_manifest["status"] = "interrupted"
        run_manifest["error"] = "KeyboardInterrupt"
        write_json(args.run_dir / "run_manifest.json", run_manifest)
        return 130
    except (LaunchError, OSError) as exc:
        run_manifest["status"] = "failed"
        run_manifest["error"] = f"{type(exc).__name__}: {exc}"
        write_json(args.run_dir / "run_manifest.json", run_manifest)
        print(run_manifest["error"], file=sys.stderr)
        return 2
    finally:
        if fiper_runtime is not None:
            remove_fiper_data_link(*fiper_runtime)
    run_manifest["status"] = "completed"
    write_json(args.run_dir / "run_manifest.json", run_manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
