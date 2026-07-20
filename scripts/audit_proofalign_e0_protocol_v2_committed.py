from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import audit_proofalign_e0_protocol_v2 as frozen_audit


REPO_ROOT = frozen_audit.REPO_ROOT
DEFAULT_PROTOCOL = frozen_audit.DEFAULT_PROTOCOL
E0V2FreezeError = frozen_audit.E0V2FreezeError


def _git_head(path: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _is_ancestor(path: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.returncode == 0


def _git_blob_sha256(path: Path, commit: str, relative: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "show", f"{commit}:{relative}"],
        check=False,
        capture_output=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    return sha256(completed.stdout).hexdigest()


def _protocol_freeze_commit(path: Path, protocol_path: Path) -> str | None:
    try:
        relative = protocol_path.resolve().relative_to(path.resolve())
    except ValueError:
        return None
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "log",
            "--diff-filter=A",
            "--format=%H",
            "--",
            str(relative),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    commits = completed.stdout.splitlines() if completed.returncode == 0 else []
    return commits[-1] if commits else None


def audit(protocol_path: Path) -> dict[str, Any]:
    """Audit a frozen E0 v2 snapshot from a committed descendant checkout.

    The original auditor is itself method-pinned and intentionally left unchanged.
    It expected the checkout HEAD to remain at the pre-freeze base commit, which is
    no longer possible after committing the pinned freeze files. This adapter first
    verifies that the pinned base is an ancestor of the current HEAD, then delegates
    every byte/evidence/classification check to the original frozen auditor.
    """

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    method = protocol.get("method_pins") or {}
    base_commit = method.get("base_commit")
    if not isinstance(base_commit, str) or not base_commit:
        raise E0V2FreezeError("E0 v2 method base commit is absent")

    current_head = _git_head(REPO_ROOT)
    if current_head is None:
        raise E0V2FreezeError("current repository HEAD is unavailable")
    if not _is_ancestor(REPO_ROOT, base_commit, current_head):
        raise E0V2FreezeError("E0 v2 method base is not an ancestor of current HEAD")

    freeze_commit = _protocol_freeze_commit(REPO_ROOT, protocol_path)
    if freeze_commit is None or not _is_ancestor(REPO_ROOT, freeze_commit, current_head):
        raise E0V2FreezeError("E0 v2 protocol freeze commit is unavailable")

    method_files = method.get("files") or {}
    if not isinstance(method_files, dict) or not method_files:
        raise E0V2FreezeError("E0 v2 method file pins are empty")

    original_git_commit = frozen_audit._git_commit
    original_require_bound_file = frozen_audit._require_bound_file

    def _committed_snapshot_git_commit(path: Path) -> str | None:
        if path.resolve() == REPO_ROOT.resolve():
            return base_commit
        return original_git_commit(path)

    def _committed_snapshot_require_bound_file(
        path_value: Any, digest_value: Any, label: str
    ) -> Path:
        relative = str(path_value)
        if relative in method_files:
            path = REPO_ROOT / relative
            if not path.is_file():
                raise E0V2FreezeError(f"{label} is missing: {path}")
            if _git_blob_sha256(REPO_ROOT, freeze_commit, relative) != digest_value:
                raise E0V2FreezeError(
                    f"{label} digest differs from the committed E0 v2 snapshot"
                )
            return path
        return original_require_bound_file(path_value, digest_value, label)

    frozen_audit._git_commit = _committed_snapshot_git_commit
    frozen_audit._require_bound_file = _committed_snapshot_require_bound_file
    try:
        report = frozen_audit.audit(protocol_path)
    finally:
        frozen_audit._git_commit = original_git_commit
        frozen_audit._require_bound_file = original_require_bound_file

    report = dict(report)
    report.update(
        {
            "schema": "proofalign.e0.protocol-v2-committed-audit.v1",
            "frozen_audit_schema": "proofalign.e0.protocol-v2-audit.v1",
            "method_base_commit": base_commit,
            "protocol_freeze_commit": freeze_commit,
            "current_head": current_head,
            "method_base_is_ancestor": True,
        }
    )
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify frozen ProofAlign E0 v2 from a committed descendant checkout."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = audit(args.protocol.expanduser().resolve())
    except (
        E0V2FreezeError,
        OSError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
