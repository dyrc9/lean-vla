"""Shared filesystem, Git, and GPU helpers for the active SABER experiment line."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProtocolError(RuntimeError):
    """A frozen protocol, source state, or retained artifact is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_ledger(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_command(
    argv: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        tuple(str(item) for item in argv),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def checked_output(argv: Sequence[str | os.PathLike[str]], *, cwd: Path) -> str:
    result = run_command(argv, cwd=cwd)
    if result.returncode != 0:
        raise ProtocolError(
            f"command failed ({' '.join(str(item) for item in argv)}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def committed_file_info(path: Path) -> dict[str, str]:
    relative = path.resolve().relative_to(REPO_ROOT)
    tracked = run_command(
        ("git", "ls-files", "--error-unmatch", str(relative)),
        cwd=REPO_ROOT,
    )
    if tracked.returncode != 0:
        raise ProtocolError(f"required file is not tracked by Git: {relative}")
    diff = run_command(
        ("git", "diff", "--quiet", "HEAD", "--", str(relative)),
        cwd=REPO_ROOT,
    )
    if diff.returncode != 0:
        raise ProtocolError(f"required file differs from committed HEAD: {relative}")
    return {
        "path": str(relative),
        "commit": checked_output(
            ("git", "log", "-1", "--format=%H", "--", str(relative)),
            cwd=REPO_ROOT,
        ),
        "blob": checked_output(
            ("git", "rev-parse", f"HEAD:{relative}"),
            cwd=REPO_ROOT,
        ),
        "sha256": file_digest(path),
    }


def gpu_inventory() -> list[dict[str, Any]]:
    result = run_command(
        (
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.used,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ),
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise ProtocolError(
            f"nvidia-smi failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            raise ProtocolError(f"unexpected nvidia-smi row: {line}")
        rows.append(
            {
                "index": int(parts[0]),
                "uuid": parts[1],
                "name": parts[2],
                "memory_used_mib": int(parts[3]),
                "memory_total_mib": int(parts[4]),
                "driver_version": parts[5],
            }
        )
    return rows
