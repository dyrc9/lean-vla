#!/usr/bin/env python3
"""Audit frozen Ed25519 CTDA evidence authentication without simulator or dispatch."""

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
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.aegis_runtime import load_json, sha256_file  # noqa: E402


SCHEMA = "proofalign.ctda-v2-crypto-evidence-audit-v1"
PROTOCOL_SCHEMA = "proofalign.ctda-v2-crypto-evidence-protocol-v1"
DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_crypto_evidence_protocol.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_crypto_evidence_summary.json"


class CryptoEvidenceAuditError(RuntimeError):
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


def _verify(protocol: Mapping[str, Any], protocol_path: Path) -> dict[str, Any]:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise CryptoEvidenceAuditError("unsupported crypto-evidence protocol schema")
    if protocol.get("protocol_id") != "ctda-v2-crypto-evidence-r0":
        raise CryptoEvidenceAuditError("unexpected crypto-evidence protocol id")
    if (
        protocol.get("authorization") != "ephemeral_key_unit_only_no_dispatch"
        or protocol.get("formal_rollout_authorized") is not False
    ):
        raise CryptoEvidenceAuditError("crypto-evidence authorization boundary changed")
    checks: dict[str, bool] = {}
    for relative, expected in protocol["implementation_hashes"].items():
        path = ROOT / relative
        checks[f"implementation:{relative}"] = path.is_file() and sha256_file(path) == expected
    for name, dependency in protocol["prerequisites"].items():
        path = ROOT / dependency["path"]
        checks[f"prerequisite:{name}"] = path.is_file() and sha256_file(path) == dependency["sha256"]
    boundaries = [_ast_boundary(ROOT / relative) for relative in protocol["ast_boundary_files"]]
    checks["ast_no_simulator_socket_step_dispatch"] = all(item["ready"] for item in boundaries)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lockfile = (ROOT / "uv.lock").read_text(encoding="utf-8")
    checks["cryptography_direct_dependency"] = '"cryptography>=46,<50"' in pyproject
    checks["cryptography_locked"] = (
        'name = "cryptography"' in lockfile
        and '{ name = "cryptography", specifier = ">=46,<50" }' in lockfile
    )
    if not all(checks.values()):
        raise CryptoEvidenceAuditError(f"crypto-evidence preflight failed: {checks}")
    return {
        "checks": checks,
        "boundaries": boundaries,
        "protocol_sha256": sha256_file(protocol_path),
    }


def _execute(protocol: Mapping[str, Any]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join((str(SRC), str(ROOT)))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", protocol["test_path"]],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=protocol["timeout_seconds"],
    )
    match = re.search(r"(?P<count>\d+) passed", result.stdout)
    passed = 0 if match is None else int(match.group("count"))
    if result.returncode != 0 or passed != protocol["acceptance"]["test_count"]:
        raise CryptoEvidenceAuditError(
            json.dumps(
                {
                    "returncode": result.returncode,
                    "passed": passed,
                    "stdout": result.stdout[-4000:],
                    "stderr": result.stderr[-4000:],
                },
                indent=2,
            )
        )
    return {
        "test_count": passed,
        "stdout_sha256": sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": sha256(result.stderr.encode()).hexdigest(),
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
                    "formal_rollout_authorized": False,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    output = args.output.resolve()
    if output.exists():
        raise CryptoEvidenceAuditError(f"fresh output required: {output}")
    execution = _execute(protocol)
    summary = {
        "schema": SCHEMA,
        "status": "crypto_evidence_ready_deployment_blocked",
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
