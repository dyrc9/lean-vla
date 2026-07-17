from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e0_protocol_v2.json"


class E0V2FreezeError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_commit(path: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _require_bound_file(path_value: Any, digest_value: Any, label: str) -> Path:
    path = REPO_ROOT / str(path_value)
    if not path.is_file():
        raise E0V2FreezeError(f"{label} is missing: {path}")
    if _sha256(path) != digest_value:
        raise E0V2FreezeError(f"{label} digest differs from the E0 v2 freeze")
    return path


def audit(protocol_path: Path) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("schema") != "proofalign.e0.protocol.v2":
        raise E0V2FreezeError("unsupported E0 v2 protocol schema")
    if protocol.get("status") != "frozen_non_real_time_supported_slice":
        raise E0V2FreezeError("E0 v2 protocol is not frozen")
    if protocol.get("outcome_blind_freeze") is not True:
        raise E0V2FreezeError("E0 v2 outcome-blind freeze flag is absent")

    method = protocol.get("method_pins") or {}
    if _git_commit(REPO_ROOT) != method.get("base_commit"):
        raise E0V2FreezeError("repository base commit differs from E0 v2")
    method_files = method.get("files") or {}
    if not isinstance(method_files, dict) or not method_files:
        raise E0V2FreezeError("E0 v2 method file pins are empty")
    for relative, digest in method_files.items():
        _require_bound_file(relative, digest, f"method file {relative}")

    evidence = protocol.get("evidence") or {}
    required_evidence = (
        "compiler_observer_candidate_summary",
        "init_validity_summary",
        "slow_interlock_protocol",
        "slow_interlock_audit_summary",
        "prior_strict_gate_decision",
    )
    for name in required_evidence:
        item = evidence.get(name) or {}
        _require_bound_file(item.get("path"), item.get("sha256"), name)

    benchmark = protocol.get("benchmark") or {}
    benchmark_root = REPO_ROOT / "external" / "LIBERO-Safety"
    if _git_commit(benchmark_root) != benchmark.get("commit"):
        raise E0V2FreezeError("LIBERO-Safety commit differs from E0 v2")
    task_map = benchmark_root / "libero" / "libero" / "benchmark" / "vla_safety_task_map.py"
    if _sha256(task_map) != benchmark.get("task_map_sha256"):
        raise E0V2FreezeError("LIBERO-Safety task map differs from E0 v2")

    suites = tuple(str(item) for item in benchmark.get("suites", ()))
    task_ids = tuple(int(item) for item in benchmark.get("task_ids", ()))
    if len(suites) != 5 or task_ids != tuple(range(15)):
        raise E0V2FreezeError("E0 v2 task universe is not five suites x 15 tasks")

    classification = protocol.get("classification") or {}
    supported = classification.get("supported") or {}
    ambiguous = classification.get("ambiguous") or {}
    unsupported = classification.get("unsupported") or {}
    rows: list[tuple[str, int, str]] = []
    for label, groups in (
        ("supported", supported),
        ("ambiguous", ambiguous),
        ("unsupported", unsupported),
    ):
        for suite, ids in groups.items():
            rows.extend((str(suite), int(task_id), label) for task_id in ids)
    identities = [(suite, task_id) for suite, task_id, _ in rows]
    expected = [(suite, task_id) for suite in suites for task_id in task_ids]
    if len(identities) != len(set(identities)) or sorted(identities) != sorted(expected):
        raise E0V2FreezeError("E0 v2 classification is not an exact task partition")
    counts = classification.get("counts") or {}
    observed_counts = {
        "total": len(rows),
        "supported": sum(label == "supported" for _, _, label in rows),
        "ambiguous": sum(label == "ambiguous" for _, _, label in rows),
        "unsupported": sum(label == "unsupported" for _, _, label in rows),
    }
    if counts != observed_counts:
        raise E0V2FreezeError("E0 v2 classification counts are inconsistent")

    supported_ids = tuple(int(item) for item in supported.get("affordance", ()))
    if supported_ids != (0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13):
        raise E0V2FreezeError("E0 v2 supported task set changed")
    if set(supported) != {"affordance"} or ambiguous:
        raise E0V2FreezeError("E0 v2 supported/ambiguous suites changed")

    fallback = protocol.get("fallback") or {}
    registry_path = _require_bound_file(
        fallback.get("registry"),
        fallback.get("registry_sha256"),
        "fallback registry",
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    artifacts = registry.get("artifacts") or []
    by_task = {int(item["task_id"]): item for item in artifacts}
    for task_id in supported_ids:
        entry = by_task.get(task_id)
        if entry is None:
            raise E0V2FreezeError(f"supported task {task_id} has no fallback artifact")
        _require_bound_file(entry.get("path"), entry.get("sha256"), f"fallback task {task_id}")
    if fallback.get("timing_gate_enforced") is not False:
        raise E0V2FreezeError("E0 v2 unexpectedly enforces timing")
    if fallback.get("timing_metrics_stage") != "E4":
        raise E0V2FreezeError("E0 v2 timing metrics are not assigned to E4")

    e1 = protocol.get("e1") or {}
    pilot = e1.get("pilot_units") or []
    pilot_ids = tuple(int(item["task_id"]) for item in pilot)
    if pilot_ids != supported_ids or e1.get("status") != "authorized_not_started":
        raise E0V2FreezeError("E1 pilot is not the exact supported task set")
    for item in pilot:
        if item != {
            "suite": "affordance",
            "task_id": item["task_id"],
            "init_state_id": 0,
            "env_seed": 7,
            "policy_seed": 0,
        }:
            raise E0V2FreezeError("E1 pilot unit configuration changed")

    return {
        "schema": "proofalign.e0.protocol-v2-audit.v1",
        "ready": True,
        "protocol": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "method_files_verified": len(method_files),
        "evidence_files_verified": len(required_evidence),
        "fallback_artifacts_verified": len(supported_ids),
        "counts": observed_counts,
        "supported_units": [
            {"suite": "affordance", "task_id": task_id, "init_state_id": 0}
            for task_id in supported_ids
        ],
        "e1_status": e1["status"],
        "timing_gate_enforced": False,
        "timing_metrics_stage": "E4",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the frozen ProofAlign E0 v2 protocol.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = audit(args.protocol.expanduser().resolve())
    except (E0V2FreezeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
