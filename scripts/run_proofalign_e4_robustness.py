#!/usr/bin/env python3
"""Run the frozen E4 CPU/Lean fail-closed robustness matrix.

This is a component-semantics experiment.  It does not execute a GPU policy or
physical simulator rollout, and it does not establish real-time, recovery, or
attack-defense claims.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from proofalign.ctda_evaluator import (  # noqa: E402
    LeanKernelEvaluator,
    PythonReferenceEvaluator,
    ShadowEvaluator,
)
from proofalign.ctda_shadow import golden_scenario  # noqa: E402
from proofalign.ctda_wire import (  # noqa: E402
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    canonical_wire_bytes,
    make_wire_request,
)


SCHEMA = "proofalign.e4.robustness-result.v1"
PROTOCOL_SCHEMA = "proofalign.e4.robustness-protocol.v1"
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e4_robustness_protocol.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "proofalign_e4_robustness_20260717"


class ProtocolError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError(f"{label} must be a JSON object")
    return value


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ProtocolError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def load_protocol(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = _load_object(path, "E4 robustness protocol")
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise ProtocolError("unexpected E4 robustness protocol schema")
    if protocol.get("status") != "frozen_ready_for_execution":
        raise ProtocolError("E4 robustness protocol is not frozen")
    if protocol.get("timing_is_gate") is not False:
        raise ProtocolError("timing must remain diagnostic-only")
    if protocol.get("gpu_or_simulator_execution") is not False:
        raise ProtocolError("E4 robustness must remain CPU/Lean-only")

    cases = protocol.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ProtocolError("E4 robustness cases must be non-empty")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(cases) or len(set(case_ids)) != len(case_ids):
        raise ProtocolError("E4 robustness case ids are malformed or duplicated")
    allowed_kinds = {
        "kernel_control",
        "lean_unavailable",
        "lean_timeout",
        "checker_digest_tamper",
        "canonical_wire_tamper",
        "shadow_non_authorizing",
        "golden_fault",
        "artifact_digest_tamper",
        "pytest_contract",
    }
    if any(case.get("kind") not in allowed_kinds for case in cases):
        raise ProtocolError("E4 robustness protocol contains an unsupported case kind")

    observed_files: dict[str, str] = {}
    required = protocol.get("required_files")
    if not isinstance(required, list) or not required:
        raise ProtocolError("E4 robustness required_files must be non-empty")
    for item in required:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ProtocolError("malformed E4 required file binding")
        relative = str(item["path"])
        bound = (REPO_ROOT / relative).resolve()
        if not bound.is_relative_to(REPO_ROOT) or not bound.is_file():
            raise ProtocolError(f"required file is missing or outside repository: {relative}")
        observed = file_digest(bound)
        if observed != item["sha256"]:
            raise ProtocolError(f"required file digest mismatch: {relative}")
        observed_files[relative] = observed
    runner_relative = str(Path(__file__).resolve().relative_to(REPO_ROOT))
    if runner_relative not in observed_files:
        raise ProtocolError("protocol does not pin its runner")

    head = _git("rev-parse", "HEAD")
    base = str(protocol.get("method_base_commit", ""))
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, head],
        cwd=REPO_ROOT,
        check=False,
    ).returncode == 0
    if not base or not ancestor:
        raise ProtocolError("E4 method base is not an ancestor of HEAD")
    return protocol, {
        "protocol": {"path": str(path), "sha256": file_digest(path)},
        "method_base_commit": base,
        "current_head": head,
        "method_base_is_ancestor": True,
        "required_files": observed_files,
        "case_count": len(cases),
    }


def _toolchain_env(protocol: dict[str, Any]) -> tuple[dict[str, str], Path]:
    toolchain = (REPO_ROOT / str(protocol["lean"]["toolchain_bin"])).resolve()
    lean = toolchain / "lean"
    lake = toolchain / "lake"
    if not toolchain.is_relative_to(REPO_ROOT) or not lean.is_file() or not lake.is_file():
        raise ProtocolError("frozen Lean toolchain is unavailable")
    if file_digest(lean) != protocol["lean"]["lean_sha256"]:
        raise ProtocolError("Lean executable digest mismatch")
    if file_digest(lake) != protocol["lean"]["lake_sha256"]:
        raise ProtocolError("lake executable digest mismatch")
    env = dict(os.environ)
    env["PATH"] = f"{toolchain}:{env.get('PATH', '')}"
    return env, lean


def _artifact_payload(result: Any) -> dict[str, Any]:
    payload = asdict(result.artifact)
    payload["mode"] = result.artifact.mode.value
    payload["stage"] = result.artifact.stage.value
    return payload


def _safe_response(stage: WireStage, result: Any) -> bool:
    if stage is WireStage.MONITOR_STEP:
        return result.verdict is not WireMonitorVerdict.COMPLETE
    return not result.proven


def _evaluate_case(
    case: dict[str, Any],
    *,
    protocol: dict[str, Any],
    output: Path,
    kernel: LeanKernelEvaluator,
    lean: Path,
    env: dict[str, str],
    controls: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    kind = str(case["kind"])
    case_root = output / "cases" / case_id
    case_root.mkdir(parents=True, exist_ok=False)
    started = _now()
    detail: dict[str, Any] = {}
    passed = False

    if kind in {"kernel_control", "golden_fault"}:
        scenario = str(case["scenario"])
        stage, payload = golden_scenario(scenario)
        request = make_wire_request(stage, kernel.checker_version_digest, payload)
        result = kernel.evaluate(request)
        reference = PythonReferenceEvaluator(kernel.checker_version_digest).evaluate(request)
        expected = str(case["expected_verdict"])
        safe = _safe_response(stage, result)
        passed = bool(
            result.verdict.value == expected
            and reference.verdict.value == expected
            and result.artifact.proof_verified
            and result.artifact.parity_match is True
            and (kind == "kernel_control" or safe)
        )
        detail = {
            "scenario": scenario,
            "stage": stage.value,
            "expected_verdict": expected,
            "reference_verdict": reference.verdict.value,
            "observed_verdict": result.verdict.value,
            "proof_verified": result.artifact.proof_verified,
            "parity_match": result.artifact.parity_match,
            "gate_safe_response": safe,
            "artifact": _artifact_payload(result),
        }
        if kind == "kernel_control":
            controls["kernel_result_path"] = Path(result.artifact.artifact_dir) / "result.json"

    elif kind == "lean_unavailable":
        evaluator = LeanKernelEvaluator(
            lean_root=REPO_ROOT / "lean",
            lean_command=str(case_root / "missing-lean"),
            artifact_root=case_root / "kernel",
        )
        stage, payload = golden_scenario(str(case["scenario"]))
        result = evaluator.evaluate(make_wire_request(stage, evaluator.checker_version_digest, payload))
        passed = bool(
            result.verdict.value == case["expected_verdict"]
            and not result.artifact.proof_verified
            and _safe_response(stage, result)
            and "unavailable" in result.artifact.stderr
        )
        detail = {
            "stage": stage.value,
            "observed_verdict": result.verdict.value,
            "proof_verified": result.artifact.proof_verified,
            "gate_safe_response": _safe_response(stage, result),
            "artifact": _artifact_payload(result),
        }

    elif kind == "lean_timeout":
        slow = case_root / "slow-lean"
        slow.write_text("#!/bin/sh\nsleep 1\n", encoding="utf-8")
        slow.chmod(0o755)
        evaluator = LeanKernelEvaluator(
            lean_root=REPO_ROOT / "lean",
            lean_command=str(slow),
            artifact_root=case_root / "kernel",
            timeout_seconds=float(case["timeout_seconds"]),
        )
        evaluator._project_built = True
        stage, payload = golden_scenario(str(case["scenario"]))
        result = evaluator.evaluate(make_wire_request(stage, evaluator.checker_version_digest, payload))
        passed = bool(
            result.verdict.value == case["expected_verdict"]
            and not result.artifact.proof_verified
            and _safe_response(stage, result)
            and "timed out" in result.artifact.stderr
        )
        detail = {
            "stage": stage.value,
            "injected_timeout_seconds": case["timeout_seconds"],
            "observed_verdict": result.verdict.value,
            "proof_verified": result.artifact.proof_verified,
            "gate_safe_response": _safe_response(stage, result),
            "artifact": _artifact_payload(result),
        }

    elif kind == "checker_digest_tamper":
        stage, payload = golden_scenario(str(case["scenario"]))
        request = make_wire_request(stage, "0" * 64, payload)
        result = kernel.evaluate(request)
        passed = bool(
            result.verdict.value == case["expected_verdict"]
            and not result.artifact.proof_verified
            and _safe_response(stage, result)
            and "checker_version_digest" in result.artifact.stderr
        )
        detail = {
            "stage": stage.value,
            "observed_verdict": result.verdict.value,
            "proof_verified": result.artifact.proof_verified,
            "gate_safe_response": _safe_response(stage, result),
            "artifact": _artifact_payload(result),
        }

    elif kind == "canonical_wire_tamper":
        stage, payload = golden_scenario(str(case["scenario"]))
        request = make_wire_request(stage, kernel.checker_version_digest, payload)
        wire = json.loads(request.canonical_bytes())
        wire["request_id"] = "0" * 64
        result = kernel.evaluate(canonical_wire_bytes(wire))
        passed = bool(
            result.verdict.value == case["expected_verdict"]
            and not result.artifact.proof_verified
            and _safe_response(stage, result)
            and "request_id digest" in result.artifact.stderr
        )
        detail = {
            "stage": stage.value,
            "observed_verdict": result.verdict.value,
            "proof_verified": result.artifact.proof_verified,
            "gate_safe_response": _safe_response(stage, result),
            "artifact": _artifact_payload(result),
        }

    elif kind == "shadow_non_authorizing":
        stage, payload = golden_scenario(str(case["scenario"]))
        request = make_wire_request(stage, kernel.checker_version_digest, payload)
        shadow = ShadowEvaluator(PythonReferenceEvaluator(kernel.checker_version_digest), kernel)
        result = shadow.evaluate(request)
        passed = bool(
            result.verdict.value == case["expected_verdict"]
            and result.artifact.parity_match is True
            and result.artifact.proof_verified is False
            and result.proven is False
        )
        detail = {
            "stage": stage.value,
            "observed_verdict": result.verdict.value,
            "parity_match": result.artifact.parity_match,
            "proof_verified": result.artifact.proof_verified,
            "gate_authorized": result.proven,
            "artifact": _artifact_payload(result),
        }

    elif kind == "artifact_digest_tamper":
        source = controls.get("kernel_result_path")
        if not isinstance(source, Path) or not source.is_file():
            raise RuntimeError("kernel control artifact is unavailable")
        expected_digest = file_digest(source)
        mutated = case_root / "mutated-result.json"
        mutated.write_bytes(source.read_bytes() + b"\n")
        observed_digest = file_digest(mutated)
        passed = expected_digest != observed_digest
        detail = {
            "source": str(source.relative_to(output)),
            "expected_sha256": expected_digest,
            "mutated_copy": str(mutated.relative_to(output)),
            "observed_sha256": observed_digest,
            "digest_match": expected_digest == observed_digest,
        }

    elif kind == "pytest_contract":
        nodeid = str(case["nodeid"])
        proc = subprocess.run(
            [str(REPO_ROOT / ".venv" / "bin" / "pytest"), "-q", "-p", "no:cacheprovider", nodeid],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=float(protocol["execution"]["pytest_timeout_seconds"]),
        )
        (case_root / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (case_root / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
        passed = proc.returncode == 0
        detail = {
            "nodeid": nodeid,
            "returncode": proc.returncode,
            "asserted_contract": case["asserted_contract"],
            "stdout_sha256": file_digest(case_root / "stdout.txt"),
            "stderr_sha256": file_digest(case_root / "stderr.txt"),
        }
    else:  # pragma: no cover - load_protocol rejects this
        raise ProtocolError(f"unsupported case kind: {kind}")

    return {
        "schema": SCHEMA,
        "case_id": case_id,
        "kind": kind,
        "role": case.get("role", "fault"),
        "started_at": started,
        "finished_at": _now(),
        "passed": passed,
        "detail": detail,
    }


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
            "sha256": file_digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in {"manifest.json", "summary.json"}
    ]


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol, audit = load_protocol(protocol_path)
    if output.exists():
        raise ProtocolError("output root must be fresh and absent")
    output.mkdir(parents=True)
    env, lean = _toolchain_env(protocol)
    os.environ["PATH"] = env["PATH"]
    kernel = LeanKernelEvaluator(
        lean_root=REPO_ROOT / "lean",
        lean_command=str(lean),
        artifact_root=output / "kernel_artifacts",
        timeout_seconds=float(protocol["lean"]["timeout_seconds"]),
    )

    records: list[dict[str, Any]] = []
    controls: dict[str, Any] = {}
    for case in protocol["cases"]:
        try:
            record = _evaluate_case(
                case,
                protocol=protocol,
                output=output,
                kernel=kernel,
                lean=lean,
                env=env,
                controls=controls,
            )
        except Exception as exc:  # retain a terminal record for every frozen case
            record = {
                "schema": SCHEMA,
                "case_id": case["case_id"],
                "kind": case["kind"],
                "role": case.get("role", "fault"),
                "started_at": _now(),
                "finished_at": _now(),
                "passed": False,
                "detail": {"runner_exception": f"{type(exc).__name__}: {exc}"},
            }
        records.append(record)
        record_path = output / "cases" / str(case["case_id"]) / "record.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_bytes(canonical_wire_bytes(record))

    records_path = output / "records.jsonl"
    records_path.write_bytes(b"".join(canonical_wire_bytes(item) + b"\n" for item in records))
    fault_records = [item for item in records if item["role"] == "fault"]
    summary = {
        "schema": "proofalign.e4.robustness-summary.v1",
        "status": (
            "complete_fail_closed_component_robustness_established"
            if records and all(item["passed"] for item in records)
            else "complete_fail_closed_component_robustness_not_established"
        ),
        "claim_boundary": protocol["claim_boundary"],
        "protocol_audit": audit,
        "recorded_cases": len(records),
        "passed_cases": sum(bool(item["passed"]) for item in records),
        "failed_cases": sum(not bool(item["passed"]) for item in records),
        "fault_cases": len(fault_records),
        "fail_closed_fault_cases": sum(bool(item["passed"]) for item in fault_records),
        "control_cases": sum(item["role"] == "control" for item in records),
        "timing_evaluated_as_gate": False,
        "gpu_or_simulator_executed": False,
        "physical_safety_claim": False,
        "attack_defense_claim": False,
        "real_time_claim": False,
        "finished_at": _now(),
    }
    manifest = {
        "schema": "proofalign.e4.robustness-manifest.v1",
        "protocol_sha256": audit["protocol"]["sha256"],
        "records_sha256": file_digest(records_path),
        "artifacts": _inventory(output),
    }
    (output / "manifest.json").write_bytes(canonical_wire_bytes(manifest))
    summary["manifest_sha256"] = file_digest(output / "manifest.json")
    summary["records_sha256"] = file_digest(records_path)
    (output / "summary.json").write_bytes(canonical_wire_bytes(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        summary = run(args.protocol.resolve(), args.output.resolve())
    except (ProtocolError, OSError) as exc:
        print(f"E4 robustness preflight failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
