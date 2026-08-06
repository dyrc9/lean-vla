#!/usr/bin/env python3
"""Wait for two qualified GPUs, then run support45 clean fresh2 once."""

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
    / "proofalign_four_arm_v4_support45_successor.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_support45_clean_20260727_fresh2"
)
LAUNCHER_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_support45_clean_launcher_20260727"
)
EVENTS_PATH = LAUNCHER_ROOT / "events.jsonl"
STATE_PATH = LAUNCHER_ROOT / "state.json"
EXECUTION_LOG_PATH = LAUNCHER_ROOT / "clean_execution.log"
LOCK_PATH = LAUNCHER_ROOT / "launcher.lock"
PROJECT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
OPENPI_PYTHON = (
    REPO_ROOT / "external" / "openpi" / ".venv" / "bin" / "python"
)
RUNNER_PATH = (
    REPO_ROOT
    / "scripts"
    / "run_proofalign_four_arm_v4_support45_clean.py"
)


class LauncherError(RuntimeError):
    """Raised when the one-shot support45 launcher must stop."""


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
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "recorded_at": utc_now(),
                    "event": event,
                    **fields,
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()


def write_state(status: str, **fields: Any) -> None:
    LAUNCHER_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        canonical_text(
            {
                "schema": (
                    "proofalign.four-arm-v4-support45-clean-launcher-"
                    "state.v1"
                ),
                "updated_at": utc_now(),
                "status": status,
                "support_conditioned": True,
                "exploratory": True,
                "confirmatory_claim_authorized": False,
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
                    f"support45 launcher already runs as PID {prior_pid}"
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
    if (
        not isinstance(value, dict)
        or value.get("confirmatory_claim_authorized") is not False
        or value.get("population", {}).get("base_pair_count") != 45
    ):
        raise LauncherError(
            "support45 protocol does not preserve its claim boundary"
        )
    return value


def qualified_gpu_indices(
    protocol: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> list[int]:
    budget = protocol["resource_budget"]
    required = int(budget["policy_gpu_count"]) + int(
        budget["egl_gpu_count"]
    )
    limit = int(
        budget[
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
        ]
    )
    qualified = sorted(
        (
            row
            for row in inventory
            if row["memory_used_mib"] < limit
        ),
        key=lambda row: (row["memory_used_mib"], row["index"]),
    )
    return [row["index"] for row in qualified[:required]]


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
        mode,
    ]
    if gpu_indices is not None:
        if len(gpu_indices) != 2:
            raise LauncherError(
                "support45 launch requires one policy and one EGL GPU"
            )
        command.extend(
            (
                "--policy-gpu",
                str(gpu_indices[0]),
                "--egl-gpu",
                str(gpu_indices[1]),
            )
        )
    return command


def run_json(
    command: list[str],
    *,
    timeout: float,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LauncherError(
            "support45 command did not return JSON: "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise LauncherError("support45 command returned a non-object")
    payload["process_returncode"] = completed.returncode
    return payload


def launch(
    protocol: dict[str, Any],
    gpu_indices: list[int],
) -> int:
    command = runner_command(
        "--execute",
        gpu_indices=gpu_indices,
        python=OPENPI_PYTHON,
    )
    shell_command = (
        "source scripts/env_vla.sh\n"
        "exec " + " ".join(command)
    )
    timeout_seconds = (
        float(
            protocol["resource_budget"][
                "wall_clock_hours_cap_per_closed_loop_stage"
            ]
        )
        * 3600
    )
    with EXECUTION_LOG_PATH.open("ab") as handle:
        try:
            completed = subprocess.run(
                ("bash", "-lc", shell_command),
                cwd=REPO_ROOT,
                check=False,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise LauncherError(
                "support45 clean run exceeded its wall-clock cap"
            ) from exc
    return completed.returncode


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
        budget = protocol["resource_budget"]
        required = int(budget["policy_gpu_count"]) + int(
            budget["egl_gpu_count"]
        )
        limit = int(
            budget[
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
            report = run_json(
                runner_command(
                    "--preflight",
                    gpu_indices=selected,
                ),
                timeout=600,
            )
            append_event(
                "preflight_complete",
                selected_gpu_indices=selected,
                ready=report.get("ready"),
                blockers=report.get("blockers"),
                error=report.get("error"),
            )
            if report.get("ready") is not True:
                message = json.dumps(report, sort_keys=True)
                gpu_only = (
                    "invalid GPU selection" in message
                    and (
                        "memory" in message
                        or "MiB gate" in message
                    )
                )
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
                    f"non-resource support45 preflight blocker: {report}"
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
                "support45_clean_launching",
                policy_gpu=selected[0],
                egl_gpu=selected[1],
            )
            returncode = launch(protocol, selected)
            if returncode != 0:
                write_state(
                    "terminal_execution_failed",
                    launcher_pid=os.getpid(),
                    selected_gpu_indices=selected,
                    runner_returncode=returncode,
                    execution_log=str(
                        EXECUTION_LOG_PATH.relative_to(REPO_ROOT)
                    ),
                )
                raise LauncherError(
                    "support45 run failed; no retry is allowed"
                )
            validation = run_json(
                runner_command("--validate-results"),
                timeout=3600,
            )
            if (
                validation.get("process_returncode") != 0
                or validation.get("terminal_requested") is not True
                or validation.get("present_episode_count") != 360
                or validation.get("valid_episode_count") != 360
                or validation.get("classification")
                not in {
                    "support45_clean_gate_pass",
                    "support45_clean_gate_nonpass",
                }
            ):
                raise LauncherError(
                    f"support45 result validation failed: {validation}"
                )
            write_state(
                "support45_clean_complete_validated",
                launcher_pid=os.getpid(),
                selected_gpu_indices=selected,
                classification=validation.get("classification"),
                clean_gate_pass=validation.get("clean_gate_pass"),
                validation=validation,
            )
            append_event(
                "support45_clean_complete_validated",
                selected_gpu_indices=selected,
                classification=validation.get("classification"),
                clean_gate_pass=validation.get("clean_gate_pass"),
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
