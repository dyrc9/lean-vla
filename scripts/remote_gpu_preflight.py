#!/usr/bin/env python3
"""Fail-closed readiness check for a ProofAlign remote GPU checkout.

The script intentionally uses only the Python standard library so it can run
before either the root or OpenPI virtual environment has been activated.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")
LIBERO_CONFIG_KEYS = (
    "benchmark_root",
    "bddl_files",
    "init_states",
    "datasets",
    "assets",
)


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: float = 120.0,
) -> CommandResult:
    try:
        completed = subprocess.run(
            tuple(str(item) for item in argv),
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(
            tuple(str(item) for item in argv),
            completed.returncode,
            completed.stdout.strip(),
            completed.stderr.strip(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(
            tuple(str(item) for item in argv),
            127,
            "",
            f"{type(exc).__name__}: {exc}",
        )


def parse_gpu_inventory(text: str) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        parts = [part.strip() for part in raw_line.split(",")]
        if len(parts) < 4:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        inventory.append(
            {
                "index": index,
                "name": parts[1],
                "memory_total_mib": parts[2],
                "driver_version": parts[3],
            }
        )
    return inventory


def validate_gpu_selection(
    inventory: list[dict[str, Any]],
    vla_gpu: str | None,
    egl_gpu: str | None,
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    available = {int(item["index"]) for item in inventory}
    selected: dict[str, int] = {}
    for label, value in (("VLA_GPU", vla_gpu), ("EGL_GPU", egl_gpu)):
        if value is None or not str(value).strip():
            blockers.append(f"{label} is not set")
            continue
        try:
            selected[label] = int(value)
        except ValueError:
            blockers.append(f"{label} must be a physical integer GPU id, got {value!r}")
            continue
        if selected[label] not in available:
            blockers.append(
                f"{label}={selected[label]} is absent from nvidia-smi physical GPU inventory"
            )
    if (
        "VLA_GPU" in selected
        and "EGL_GPU" in selected
        and selected["VLA_GPU"] == selected["EGL_GPU"]
    ):
        warnings.append("VLA and MuJoCo EGL share one physical GPU; verify memory headroom")
    return blockers, warnings


def file_digest(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def parse_libero_config_paths(text: str) -> dict[str, str]:
    """Parse the flat path-only subset used by LIBERO's config.yaml."""

    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        key = key.strip()
        if separator and key in LIBERO_CONFIG_KEYS:
            values[key] = value.strip().strip("'\"")
    return values


def validate_libero_config_paths(
    values: dict[str, str], *, config_path: Path, libero_root: Path
) -> list[str]:
    blockers: list[str] = []
    benchmark_root = libero_root / "libero" / "libero"
    expected = {
        "benchmark_root": benchmark_root,
        "bddl_files": benchmark_root / "bddl_files",
        "init_states": benchmark_root / "init_files",
        "datasets": libero_root / "libero" / "datasets",
        "assets": benchmark_root / "assets",
    }
    for key, expected_path in expected.items():
        value = values.get(key)
        if not value:
            blockers.append(f"LIBERO config is missing {key}: {config_path}")
            continue
        configured = Path(value).expanduser()
        if not configured.is_absolute():
            configured = config_path.parent / configured
        if configured.resolve() != expected_path.resolve():
            blockers.append(
                f"LIBERO config {key} points outside the selected LIBERO-Safety "
                f"checkout: {configured.resolve()} != {expected_path.resolve()}"
            )
    return blockers


def git_snapshot(path: Path) -> dict[str, Any]:
    requested_root = path.expanduser().resolve()
    top_level = run_command(("git", "rev-parse", "--show-toplevel"), cwd=requested_root)
    reported_root: Path | None = None
    if top_level.returncode == 0 and top_level.stdout:
        reported_root = Path(top_level.stdout).expanduser().resolve()
    if reported_root != requested_root:
        if reported_root is None:
            error = top_level.stderr or f"no Git top-level found for {requested_root}"
        else:
            error = (
                f"Git top-level {reported_root} does not match requested checkout "
                f"{requested_root}"
            )
        return {
            "path": str(requested_root),
            "top_level": str(reported_root) if reported_root is not None else None,
            "head": None,
            "branch": None,
            "dirty": None,
            "status": [],
            "error": error,
        }
    head = run_command(("git", "rev-parse", "HEAD"), cwd=path)
    branch = run_command(("git", "branch", "--show-current"), cwd=path)
    status = run_command(("git", "status", "--porcelain=v1"), cwd=path)
    return {
        "path": str(requested_root),
        "top_level": str(reported_root),
        "head": head.stdout if head.returncode == 0 else None,
        "branch": branch.stdout if branch.returncode == 0 else None,
        "dirty": bool(status.stdout) if status.returncode == 0 else None,
        "status": status.stdout.splitlines() if status.returncode == 0 else [],
        "error": head.stderr if head.returncode != 0 else None,
    }


def command_path(command: str) -> str | None:
    expanded = str(Path(command).expanduser())
    if "/" in expanded:
        path = Path(expanded)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(command)


def collect_preflight(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).expanduser().resolve()
    openpi_root = Path(args.openpi_root).expanduser().resolve()
    libero_root = Path(args.libero_safety_root).expanduser().resolve()
    checkpoint_dir = Path(args.checkpoint_dir).expanduser().resolve()
    libero_config = Path(args.libero_config).expanduser().resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    required_paths = {
        "workspace": workspace,
        "openpi_root": openpi_root,
        "libero_safety_root": libero_root,
        "checkpoint_dir": checkpoint_dir,
        "libero_config": libero_config,
    }
    for label, path in required_paths.items():
        expected = path.is_file() if label == "libero_config" else path.is_dir()
        if not expected:
            blockers.append(f"required {label} is missing: {path}")

    libero_config_paths: dict[str, str] = {}
    if libero_config.is_file():
        try:
            libero_config_paths = parse_libero_config_paths(
                libero_config.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as exc:
            blockers.append(f"LIBERO config is unreadable: {libero_config}: {exc}")
        else:
            blockers.extend(
                validate_libero_config_paths(
                    libero_config_paths,
                    config_path=libero_config,
                    libero_root=libero_root,
                )
            )

    required_commands = {
        "git": "git",
        "python": sys.executable,
        "uv": args.uv,
        "lake": "lake",
    }
    if not args.skip_gpu:
        required_commands["nvidia_smi"] = "nvidia-smi"
    command_paths = {label: command_path(value) for label, value in required_commands.items()}
    for label, path in command_paths.items():
        if path is None:
            blockers.append(f"required command is unavailable: {label} ({required_commands[label]})")

    repositories: dict[str, dict[str, Any]] = {}
    for label, path in (
        ("proofalign", workspace),
        ("openpi", openpi_root),
        ("libero_safety", libero_root),
    ):
        if path.is_dir():
            snapshot = git_snapshot(path)
            repositories[label] = snapshot
            if snapshot["head"] is None:
                blockers.append(f"{label} is not a readable Git checkout: {path}")
            if snapshot["dirty"] and not args.allow_dirty:
                blockers.append(f"{label} checkout is dirty: {path}")

    gpu_query: CommandResult | None = None
    gpu_inventory: list[dict[str, Any]] = []
    if args.skip_gpu:
        warnings.append("GPU query skipped; this manifest is not sufficient to start an experiment")
    elif command_paths.get("nvidia_smi"):
        gpu_query = run_command(
            (
                command_paths["nvidia_smi"],
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            )
        )
        if gpu_query.returncode != 0:
            blockers.append(f"nvidia-smi query failed: {gpu_query.stderr}")
        else:
            gpu_inventory = parse_gpu_inventory(gpu_query.stdout)
            if not gpu_inventory:
                blockers.append("nvidia-smi returned no parseable physical GPUs")
            gpu_blockers, gpu_warnings = validate_gpu_selection(
                gpu_inventory, args.vla_gpu, args.egl_gpu
            )
            blockers.extend(gpu_blockers)
            warnings.extend(gpu_warnings)

    versions: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    version_commands = {
        "git": ("git", "--version"),
        "uv": (args.uv, "--version"),
        "lake": ("lake", "--version"),
    }
    for label, argv in version_commands.items():
        if command_paths.get(label):
            result = run_command(argv)
            versions[label] = result.stdout if result.returncode == 0 else result.stderr

    verification: dict[str, Any] = {}
    if args.run_verification and not any(
        item.startswith("required command is unavailable") for item in blockers
    ):
        pytest_result = run_command(
            (args.uv, "run", "pytest", "-q"),
            cwd=workspace,
            timeout_seconds=args.verification_timeout_seconds,
        )
        lean_result = run_command(
            ("lake", "build", "ProofAlign"),
            cwd=workspace / "lean",
            timeout_seconds=args.verification_timeout_seconds,
        )
        verification = {
            "pytest": pytest_result.as_dict(),
            "lean": lean_result.as_dict(),
        }
        if pytest_result.returncode != 0:
            blockers.append("remote pytest verification failed")
        if lean_result.returncode != 0:
            blockers.append("remote Lean verification failed")
    elif not args.run_verification:
        warnings.append("CPU/Lean verification not run; pass --run-verification before GPU smoke")

    critical_files = (
        workspace / "pyproject.toml",
        workspace / "uv.lock",
        workspace / "lean" / "lean-toolchain",
        workspace / "lean" / "lake-manifest.json",
        workspace / "scripts" / "run_liberosafety_pi05_openpi_eval.py",
        workspace / "scripts" / "run_libero_online_batch.py",
        workspace / "src" / "proofalign" / "ctda_wire.py",
        workspace / "src" / "proofalign" / "ctda_evaluator.py",
    )
    digests = {str(path): file_digest(path) for path in critical_files}
    for path, digest in digests.items():
        if digest is None:
            blockers.append(f"critical source file is missing: {path}")

    return {
        "schema": "proofalign.remote-gpu-preflight.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ready": not blockers and not args.skip_gpu and args.run_verification,
        "blockers": blockers,
        "warnings": warnings,
        "paths": {label: str(path) for label, path in required_paths.items()},
        "libero_config_paths": libero_config_paths,
        "commands": command_paths,
        "repositories": repositories,
        "versions": versions,
        "gpu": {
            "query": gpu_query.as_dict() if gpu_query else None,
            "inventory": gpu_inventory,
            "vla_gpu": args.vla_gpu,
            "egl_gpu": args.egl_gpu,
        },
        "environment": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "MUJOCO_EGL_DEVICE_ID": os.environ.get("MUJOCO_EGL_DEVICE_ID"),
            "HF_HOME": os.environ.get("HF_HOME"),
            "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR"),
        },
        "critical_file_sha256": digests,
        "verification": verification,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a remote GPU checkout and emit a reproducibility manifest."
    )
    parser.add_argument("--workspace", default=str(REPO_ROOT))
    parser.add_argument("--openpi-root", default=str(REPO_ROOT / "external" / "openpi"))
    parser.add_argument(
        "--libero-safety-root",
        default=str(REPO_ROOT / "external" / "LIBERO-Safety"),
    )
    parser.add_argument("--checkpoint-dir", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument(
        "--libero-config",
        default=str(
            Path(os.environ.get("LIBERO_CONFIG_PATH", str(Path.home() / ".libero")))
            / "config.yaml"
        ),
    )
    parser.add_argument("--uv", default=os.environ.get("PROOFALIGN_UV", "uv"))
    parser.add_argument("--vla-gpu", default=os.environ.get("VLA_GPU"))
    parser.add_argument("--egl-gpu", default=os.environ.get("EGL_GPU"))
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--skip-gpu", action="store_true")
    parser.add_argument("--run-verification", action="store_true")
    parser.add_argument("--verification-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_preflight(args)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "output": str(output)}))
    for blocker in report["blockers"]:
        print(f"BLOCKER: {blocker}", file=sys.stderr)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
