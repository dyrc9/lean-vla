#!/usr/bin/env python3
"""Audit authenticated AEGIS geometry-to-CBF derivation without dispatch."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
AEGIS_ROOT = ROOT / "external" / "vlsa-aegis"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.aegis_runtime import load_json, sha256_file  # noqa: E402


SCHEMA = "proofalign.ctda-v2-aegis-cbf-geometry-audit-v1"
PROTOCOL_SCHEMA = "proofalign.ctda-v2-aegis-cbf-geometry-protocol-v1"
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_aegis_cbf_geometry_protocol.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_aegis_cbf_geometry_summary.json"


class AegisCBFGeometryAuditError(RuntimeError):
    pass


def _ast_boundary(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    definitions: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.add(node.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    forbidden_imports = sorted(imports & {"libero", "mujoco", "robosuite", "socket", "subprocess"})
    forbidden_definitions = sorted(definitions & {"action", "dispatch", "step"})
    forbidden_calls = sorted(calls & {"bind", "connect", "dispatch", "send", "step"})
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "forbidden_imports": forbidden_imports,
        "forbidden_definitions": forbidden_definitions,
        "forbidden_calls": forbidden_calls,
        "ready": not forbidden_imports and not forbidden_definitions and not forbidden_calls,
    }


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(AEGIS_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AegisCBFGeometryAuditError(result.stderr.strip() or "AEGIS git query failed")
    return result.stdout.strip()


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise AegisCBFGeometryAuditError("unsupported AEGIS CBF geometry protocol schema")
    if protocol.get("protocol_id") != "ctda-v2-aegis-cbf-geometry-r0":
        raise AegisCBFGeometryAuditError("unexpected AEGIS CBF geometry protocol id")
    if (
        protocol.get("authorization") != "signed_geometry_fixture_only_no_dispatch"
        or protocol.get("formal_rollout_authorized") is not False
    ):
        raise AegisCBFGeometryAuditError("AEGIS geometry authorization boundary changed")
    checks: dict[str, bool] = {}
    for relative, expected in protocol["implementation_hashes"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected
    for relative, expected in protocol["source"]["file_sha256"].items():
        path = AEGIS_ROOT / relative
        checks[f"source:{relative}"] = path.is_file() and sha256_file(path) == expected
    for name, dependency in protocol["prerequisites"].items():
        path = ROOT / dependency["path"]
        checks[f"prerequisite:{name}"] = path.is_file() and sha256_file(path) == dependency["sha256"]
    checks["source_commit"] = _git_value("rev-parse", "HEAD") == protocol["source"]["commit"]
    checks["source_tree"] = _git_value("rev-parse", "HEAD^{tree}") == protocol["source"]["tree"]
    checks["source_worktree_clean"] = _git_value("status", "--porcelain") == ""
    boundaries = [_ast_boundary(ROOT / relative) for relative in protocol["ast_boundary_files"]]
    checks["ast_no_simulator_socket_step_dispatch"] = all(item["ready"] for item in boundaries)
    if not all(checks.values()):
        raise AegisCBFGeometryAuditError(f"AEGIS geometry preflight failed: {checks}")
    return {
        "checks": checks,
        "boundaries": boundaries,
        "protocol_sha256": sha256_file(protocol_path),
    }


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join((str(SRC), str(ROOT)))
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _execute(protocol: Mapping[str, Any]) -> dict[str, Any]:
    tests = _run(
        [sys.executable, "-m", "pytest", "-q", protocol["test_path"]],
        protocol["timeout_seconds"],
    )
    match = re.search(r"(?P<count>\d+) passed", tests.stdout)
    passed = 0 if match is None else int(match.group("count"))
    if tests.returncode != 0 or passed != protocol["acceptance"]["test_count"]:
        raise AegisCBFGeometryAuditError(
            json.dumps(
                {
                    "stage": "pytest",
                    "returncode": tests.returncode,
                    "passed": passed,
                    "stdout": tests.stdout[-4000:],
                    "stderr": tests.stderr[-4000:],
                },
                indent=2,
            )
        )
    parity = _run(
        [sys.executable, protocol["parity_script"]],
        protocol["timeout_seconds"],
    )
    if parity.returncode != 0:
        raise AegisCBFGeometryAuditError(
            json.dumps(
                {
                    "stage": "geometry_parity",
                    "returncode": parity.returncode,
                    "stdout": parity.stdout[-4000:],
                    "stderr": parity.stderr[-4000:],
                },
                indent=2,
            )
        )
    parity_record = json.loads(parity.stdout)
    if (
        parity_record.get("status") != "parity_passed"
        or parity_record.get("case_count") != protocol["acceptance"]["parity_case_count"]
        or any(
            value > protocol["acceptance"]["parity_tolerance"]
            for value in parity_record["maximum_absolute_errors"].values()
        )
    ):
        raise AegisCBFGeometryAuditError(f"AEGIS geometry parity failed: {parity_record}")
    return {
        "test_count": passed,
        "test_stdout_sha256": sha256(tests.stdout.encode()).hexdigest(),
        "test_stderr_sha256": sha256(tests.stderr.encode()).hexdigest(),
        "geometry_parity": parity_record,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    verified = _verify(protocol, protocol_path)
    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "protocol_ready_not_executed",
                    "protocol_sha256": verified["protocol_sha256"],
                    "test_count": protocol["acceptance"]["test_count"],
                    "parity_case_count": protocol["acceptance"]["parity_case_count"],
                    "formal_rollout_authorized": False,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    output = args.output.resolve()
    if output.exists():
        raise AegisCBFGeometryAuditError(f"fresh output required: {output}")
    execution = _execute(protocol)
    summary = {
        "schema": SCHEMA,
        "status": "geometry_coefficients_ready_raw_perception_blocked",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": verified["protocol_sha256"],
        "checks": verified["checks"],
        "ast_boundaries": verified["boundaries"],
        "execution": execution,
        "coverage": protocol["coverage"],
        "counters": {
            "persistent_private_key_count": 0,
            "simulator_construction_count": 0,
            "env_step_count": 0,
            "model_construction_count": 0,
            "policy_inference_count": 0,
            "socket_bind_count": 0,
            "dispatch_count": 0,
        },
        "formal_rollout_authorized": False,
        "claim_boundary": protocol["claim_boundary"],
        "next_gate": protocol["next_gate"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
