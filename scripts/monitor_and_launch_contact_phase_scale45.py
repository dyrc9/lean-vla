#!/usr/bin/env python3
"""Wait for two free GPUs, then launch the frozen v8 scale45 run once."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_four_arm_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_contact_phase_pick_up_scale45_four_arm_"
    "20260729_fresh1"
)
LAUNCHER_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_contact_phase_pick_up_scale45_four_arm_"
    "launcher_20260729"
)
STATE_PATH = LAUNCHER_ROOT / "state.json"
EVENTS_PATH = LAUNCHER_ROOT / "events.jsonl"
EXECUTION_LOG_PATH = LAUNCHER_ROOT / "execution.log"
LOCK_PATH = LAUNCHER_ROOT / "launcher.lock"
PROJECT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
OPENPI_PYTHON = (
    REPO_ROOT / "external" / "openpi" / ".venv" / "bin" / "python"
)
RUNNER_PATH = (
    REPO_ROOT / "scripts" / "run_contact_phase_pick_up_clean_pilot.py"
)


class Scale45LauncherError(RuntimeError):
    """Raised when the scale45 launcher must fail closed."""


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


def load_protocol() -> dict[str, Any]:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Scale45LauncherError("scale45 protocol is not an object")
    if (
        value.get("protocol_id")
        != "proofalign-contact-phase-pick-up-scale45-four-arm-20260729"
        or value.get("design", {}).get("episode_count") != 180
        or value.get("execution_authorization", {}).get(
            "attacked_rollout"
        )
        is not False
    ):
        raise Scale45LauncherError(
            "scale45 protocol identity or authorization differs"
        )
    return value


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
            raise Scale45LauncherError(
                f"unexpected nvidia-smi row: {line}"
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


def qualified_gpu_indices(
    protocol: Mapping[str, Any],
    inventory: list[Mapping[str, Any]],
) -> list[int]:
    limit = int(
        protocol["resource_gate"][
            "selected_gpu_memory_used_mib_max_exclusive"
        ]
    )
    qualified = sorted(
        (
            row
            for row in inventory
            if int(row["memory_used_mib"]) < limit
        ),
        key=lambda row: (
            int(row["memory_used_mib"]),
            int(row["index"]),
        ),
    )
    return [int(row["index"]) for row in qualified[:2]]


def runner_command(
    mode: str,
    gpu_indices: list[int],
    *,
    python: Path,
) -> list[str]:
    if len(gpu_indices) != 2 or gpu_indices[0] == gpu_indices[1]:
        raise Scale45LauncherError(
            "scale45 launch requires two distinct GPUs"
        )
    return [
        str(python),
        str(RUNNER_PATH),
        mode,
        "--protocol",
        str(PROTOCOL_PATH),
        "--policy-gpu",
        str(gpu_indices[0]),
        "--egl-gpu",
        str(gpu_indices[1]),
    ]


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
                "schema": (
                    "proofalign.contact-phase-scale45-launcher-state.v1"
                ),
                "updated_at": utc_now(),
                "status": status,
                "protocol": PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "output_root": OUTPUT_ROOT.relative_to(
                    REPO_ROOT
                ).as_posix(),
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
                raise Scale45LauncherError(
                    f"launcher lock belongs to PID {prior_pid}"
                ) from exc
            else:
                raise Scale45LauncherError(
                    f"scale45 launcher already runs as PID {prior_pid}"
                )
        LOCK_PATH.unlink()
    descriptor = os.open(
        LOCK_PATH,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o644,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def preflight(gpu_indices: list[int]) -> dict[str, Any]:
    completed = subprocess.run(
        runner_command(
            "--preflight",
            gpu_indices,
            python=PROJECT_PYTHON,
        ),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Scale45LauncherError(
            "scale45 preflight did not return JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise Scale45LauncherError(
            "scale45 preflight returned a non-object"
        )
    payload["process_returncode"] = completed.returncode
    return payload


def launch(gpu_indices: list[int]) -> int:
    command = runner_command(
        "--execute",
        gpu_indices,
        python=OPENPI_PYTHON,
    )
    write_state(
        "running",
        selected_gpu_indices=gpu_indices,
        command=command,
        execution_log=EXECUTION_LOG_PATH.relative_to(
            REPO_ROOT
        ).as_posix(),
    )
    append_event(
        "launch",
        selected_gpu_indices=gpu_indices,
        command=command,
    )
    with EXECUTION_LOG_PATH.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return completed.returncode


def monitor(poll_seconds: float) -> int:
    protocol = load_protocol()
    if OUTPUT_ROOT.exists():
        raise Scale45LauncherError(
            f"scale45 output root already exists: {OUTPUT_ROOT}"
        )
    acquire_lock()
    try:
        append_event("monitor_started", poll_seconds=poll_seconds)
        last_inventory: list[dict[str, Any]] = []
        while True:
            last_inventory = gpu_inventory()
            selected = qualified_gpu_indices(
                protocol, last_inventory
            )
            if len(selected) < 2:
                write_state(
                    "waiting_for_two_free_gpus",
                    qualified_gpu_indices=selected,
                    gpu_inventory=last_inventory,
                )
                time.sleep(poll_seconds)
                continue
            report = preflight(selected)
            if not report.get("ready"):
                append_event(
                    "preflight_not_ready",
                    selected_gpu_indices=selected,
                    blockers=report.get("blockers", []),
                )
                write_state(
                    "waiting_after_preflight",
                    selected_gpu_indices=selected,
                    blockers=report.get("blockers", []),
                    gpu_inventory=last_inventory,
                )
                if OUTPUT_ROOT.exists():
                    raise Scale45LauncherError(
                        "preflight created the fresh output root"
                    )
                time.sleep(poll_seconds)
                continue
            append_event(
                "preflight_ready",
                selected_gpu_indices=selected,
            )
            returncode = launch(selected)
            if returncode != 0:
                write_state(
                    "execution_failed",
                    selected_gpu_indices=selected,
                    returncode=returncode,
                )
                append_event(
                    "execution_failed",
                    selected_gpu_indices=selected,
                    returncode=returncode,
                )
                return returncode
            write_state(
                "execution_complete",
                selected_gpu_indices=selected,
                returncode=0,
            )
            append_event(
                "execution_complete",
                selected_gpu_indices=selected,
            )
            return 0
    finally:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.poll_seconds < 5:
        parser.error("--poll-seconds must be at least 5")
    try:
        return monitor(args.poll_seconds)
    except (
        OSError,
        KeyError,
        RuntimeError,
        Scale45LauncherError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
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
