#!/usr/bin/env python3
"""Wait for two qualified GPUs, then launch the frozen M2 producer once."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "saber_confirmatory_producer_m2_authorized_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "saber_confirmatory_producer_m2_20260727_fresh1"
)
LAUNCHER_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_m2_producer_launcher_20260727"
)
EVENTS_PATH = LAUNCHER_ROOT / "events.jsonl"
STATE_PATH = LAUNCHER_ROOT / "state.json"
EXECUTION_LOG_PATH = LAUNCHER_ROOT / "producer_execution.log"
LOCK_PATH = LAUNCHER_ROOT / "launcher.lock"
PROJECT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
SABER_PYTHON = (
    REPO_ROOT / "external" / "SABER" / ".venv" / "bin" / "python"
)
RUNNER_PATH = (
    REPO_ROOT / "scripts" / "generate_saber_confirmatory_records.py"
)


class LauncherError(RuntimeError):
    """Raised when the one-shot launcher must stop fail-closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def append_event(event: str, **fields: Any) -> None:
    LAUNCHER_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "recorded_at": utc_now(),
        "event": event,
        **fields,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()


def write_state(status: str, **fields: Any) -> None:
    LAUNCHER_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        canonical_text(
            {
                "schema": "proofalign.m2-producer-launcher-state.v1",
                "updated_at": utc_now(),
                "status": status,
                "protocol": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
                "output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
                **fields,
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


def acquire_lock() -> None:
    LAUNCHER_ROOT.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            prior_pid = int(
                LOCK_PATH.read_text(encoding="utf-8").strip()
            )
        except ValueError:
            prior_pid = -1
        if prior_pid > 0:
            try:
                os.kill(prior_pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                raise LauncherError(
                    f"launcher lock belongs to inaccessible PID {prior_pid}"
                ) from exc
            else:
                raise LauncherError(
                    f"M2 producer launcher already runs as PID {prior_pid}"
                )
        LOCK_PATH.unlink()
    descriptor = os.open(
        LOCK_PATH,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o644,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def gpu_inventory() -> list[dict[str, Any]]:
    completed = subprocess.run(
        (
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.used,memory.free,"
            "utilization.gpu",
            "--format=csv,noheader,nounits",
        ),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    rows = []
    for line in completed.stdout.splitlines():
        values = [value.strip() for value in line.split(",", 5)]
        if len(values) != 6:
            raise LauncherError(
                f"unexpected nvidia-smi inventory row: {line}"
            )
        rows.append(
            {
                "index": int(values[0]),
                "uuid": values[1],
                "name": values[2],
                "memory_used_mib": int(values[3]),
                "memory_free_mib": int(values[4]),
                "utilization_percent": int(values[5]),
            }
        )
    return rows


def load_protocol() -> dict[str, Any]:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LauncherError("M2 producer protocol is not a JSON object")
    return value


def qualified_gpu_indices(
    protocol: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> list[int]:
    required = int(protocol["resource_budget"]["attack_gpu_count"])
    limit = int(
        protocol["resource_budget"][
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
        ]
    )
    qualified = sorted(
        row["index"]
        for row in inventory
        if row["memory_used_mib"] < limit
    )
    return qualified[:required]


def runner_command(
    mode: str,
    *,
    gpu_indices: list[int] | None = None,
    python: Path = PROJECT_PYTHON,
) -> list[str]:
    command = [
        str(python),
        str(RUNNER_PATH),
        "--protocol",
        str(PROTOCOL_PATH),
        "--output-root",
        str(OUTPUT_ROOT),
        mode,
    ]
    if gpu_indices is not None:
        command.extend(
            ("--attack-gpus", ",".join(map(str, gpu_indices)))
        )
    return command


def preflight(gpu_indices: list[int]) -> dict[str, Any]:
    completed = subprocess.run(
        runner_command("--preflight", gpu_indices=gpu_indices),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LauncherError(
            "M2 preflight did not return JSON: "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise LauncherError("M2 preflight returned a non-object")
    payload["process_returncode"] = completed.returncode
    return payload


def launch(gpu_indices: list[int]) -> int:
    command = runner_command(
        "--execute",
        gpu_indices=gpu_indices,
        python=SABER_PYTHON,
    )
    shell_command = (
        "source scripts/env_vla.sh\n"
        "exec " + " ".join(command)
    )
    with EXECUTION_LOG_PATH.open("ab") as handle:
        completed = subprocess.run(
            ("bash", "-lc", shell_command),
            cwd=REPO_ROOT,
            check=False,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    return completed.returncode


def validate_results() -> dict[str, Any]:
    completed = subprocess.run(
        runner_command("--validate-results"),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LauncherError(
            "M2 result validator did not return JSON: "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from exc
    if completed.returncode != 0:
        raise LauncherError(
            f"M2 result validation failed: {payload}"
        )
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise LauncherError(
            f"M2 result validation did not pass: {payload}"
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-launch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.poll_seconds <= 0:
            raise LauncherError("--poll-seconds must be positive")
        acquire_lock()
        protocol = load_protocol()
        required = int(
            protocol["resource_budget"]["attack_gpu_count"]
        )
        limit = int(
            protocol["resource_budget"][
                "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
            ]
        )
        append_event(
            "launcher_started",
            pid=os.getpid(),
            required_gpu_count=required,
            memory_limit_mib_exclusive=limit,
            no_launch=args.no_launch,
        )
        while True:
            inventory = gpu_inventory()
            selected = qualified_gpu_indices(protocol, inventory)
            waiting = len(selected) != required
            write_state(
                "waiting_for_gpu" if waiting else "gpu_candidate_found",
                launcher_pid=os.getpid(),
                selected_gpu_indices=selected,
                gpu_inventory=inventory,
                required_gpu_count=required,
                memory_limit_mib_exclusive=limit,
            )
            append_event(
                "gpu_poll",
                selected_gpu_indices=selected,
                qualified=not waiting,
                gpu_memory_used_mib={
                    str(row["index"]): row["memory_used_mib"]
                    for row in inventory
                },
            )
            if waiting:
                if args.once:
                    return 3
                time.sleep(args.poll_seconds)
                continue
            report = preflight(selected)
            append_event(
                "preflight_complete",
                selected_gpu_indices=selected,
                ready=report.get("ready"),
                blockers=report.get("blockers"),
            )
            if report.get("ready") is not True:
                blockers = list(report.get("blockers", ()))
                gpu_only = blockers == [
                    "selected attack GPU violates prelaunch memory gate"
                ]
                if gpu_only:
                    if args.once:
                        return 3
                    time.sleep(args.poll_seconds)
                    continue
                write_state(
                    "terminal_preflight_blocked",
                    launcher_pid=os.getpid(),
                    selected_gpu_indices=selected,
                    preflight=report,
                )
                raise LauncherError(
                    f"non-resource preflight blocker: {blockers}"
                )
            if args.no_launch:
                write_state(
                    "ready_not_launched",
                    launcher_pid=os.getpid(),
                    selected_gpu_indices=selected,
                    preflight=report,
                )
                return 0
            write_state(
                "launching",
                launcher_pid=os.getpid(),
                selected_gpu_indices=selected,
                preflight=report,
            )
            append_event(
                "producer_launching",
                selected_gpu_indices=selected,
            )
            returncode = launch(selected)
            if returncode != 0:
                write_state(
                    "terminal_execution_failed",
                    launcher_pid=os.getpid(),
                    selected_gpu_indices=selected,
                    producer_returncode=returncode,
                    execution_log=str(
                        EXECUTION_LOG_PATH.relative_to(REPO_ROOT)
                    ),
                )
                raise LauncherError(
                    "M2 producer failed; no retry or replacement is allowed"
                )
            validation = validate_results()
            write_state(
                "producer_complete_validated",
                launcher_pid=os.getpid(),
                selected_gpu_indices=selected,
                validation=validation,
            )
            append_event(
                "producer_complete_validated",
                selected_gpu_indices=selected,
                validation=validation,
            )
            return 0
    except (
        json.JSONDecodeError,
        KeyError,
        LauncherError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as exc:
        try:
            append_event(
                "launcher_terminal_error",
                error=f"{type(exc).__name__}: {exc}",
            )
            write_state(
                "terminal_launcher_error",
                launcher_pid=os.getpid(),
                error=f"{type(exc).__name__}: {exc}",
            )
        except OSError:
            pass
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
