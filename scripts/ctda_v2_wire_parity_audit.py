#!/usr/bin/env python3
"""Run the frozen CTDA v2 Python/Lean golden parity audit.

This command has no simulator, model, policy, socket, or dispatch dependency.
Without ``--execute`` it verifies the protocol and prints the frozen plan only.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proofalign.ctda import digest_payload  # noqa: E402
from proofalign.ctda_v2_evaluator import (  # noqa: E402
    CTDAV2LeanKernelEvaluator,
    CTDAV2PythonReferenceEvaluator,
)
from proofalign.ctda_v2_golden import build_v2_golden_corpus  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "experiments" / "ctda_v2_wire_parity_protocol.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "ctda_v2_wire_parity_summary.json"
DEFAULT_ARTIFACT_ROOT = ROOT / "experiments" / "ctda_v2_wire_parity_artifacts"


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def load_and_verify_protocol(path: Path) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("schema") != "proofalign.ctda-v2-wire-parity-protocol-v1":
        raise RuntimeError("unsupported CTDA v2 wire parity protocol schema")
    if protocol.get("formal_rollout_authorized") is not False:
        raise RuntimeError("wire parity protocol must explicitly block formal rollout")
    if protocol.get("execution_mode") != "offline_no_dispatch":
        raise RuntimeError("wire parity protocol execution mode must be offline_no_dispatch")
    for relative, expected in protocol.get("implementation_hashes", {}).items():
        actual = _sha256_file(ROOT / relative)
        if actual != expected:
            raise RuntimeError(
                f"implementation freeze mismatch for {relative}: expected {expected}, got {actual}"
            )
    return protocol


def build_summary(
    *,
    protocol_path: Path,
    protocol: dict[str, Any],
    artifact_root: Path,
) -> dict[str, Any]:
    evaluator = CTDAV2LeanKernelEvaluator(
        artifact_root=artifact_root,
        timeout_seconds=float(protocol["lean_timeout_seconds"]),
    )
    if not evaluator.available:
        raise RuntimeError("Lean/lake is unavailable; parity audit failed closed")
    python = CTDAV2PythonReferenceEvaluator(evaluator.checker_version_digest)
    corpus = build_v2_golden_corpus(evaluator.checker_version_digest)
    rows = []
    for case in corpus:
        python_result = python.evaluate(case.request)
        lean_result = evaluator.evaluate(case.request)
        row = {
            "case_id": case.case_id,
            "stage": case.request.stage.value,
            "expected_verdict": case.expected.value,
            "python_verdict": python_result.verdict.value,
            "lean_verdict": lean_result.verdict.value,
            "proof_verified": lean_result.artifact.proof_verified,
            "parity_match": lean_result.artifact.parity_match,
            "request_id": case.request.request_id,
            "payload_digest": case.request.payload_digest,
            "canonical_request_sha256": sha256(case.request.canonical_bytes()).hexdigest(),
            "generated_lean_source_sha256": sha256(
                lean_result.artifact.generated_lean_source.encode("utf-8")
            ).hexdigest(),
            "cache_key": lean_result.artifact.cache_key,
            "artifact_dir": str(
                Path(lean_result.artifact.artifact_dir or "").relative_to(ROOT)
            ),
        }
        rows.append(row)

    stage_counts = Counter(row["stage"] for row in rows)
    verdict_counts = Counter(row["expected_verdict"] for row in rows)
    checks = {
        "implementation_freeze": True,
        "golden_case_count": len(rows) == protocol["golden_corpus"]["case_count"],
        "stage_distribution": dict(sorted(stage_counts.items()))
        == protocol["golden_corpus"]["stage_counts"],
        "verdict_distribution": dict(sorted(verdict_counts.items()))
        == protocol["golden_corpus"]["verdict_counts"],
        "python_matches_expected": all(
            row["python_verdict"] == row["expected_verdict"] for row in rows
        ),
        "lean_matches_expected": all(
            row["lean_verdict"] == row["expected_verdict"] for row in rows
        ),
        "all_lean_proofs_verified": all(row["proof_verified"] for row in rows),
        "all_python_lean_parity": all(row["parity_match"] is True for row in rows),
        "all_six_stages_covered": len(stage_counts) == 6,
    }
    if not all(checks.values()):
        raise RuntimeError(f"CTDA v2 wire parity audit failed: {checks}")
    return {
        "schema": "proofalign.ctda-v2-wire-parity-summary-v1",
        "status": "wire_lean_parity_ready_rollout_blocked",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_path": str(protocol_path.relative_to(ROOT)),
        "protocol_sha256": _sha256_file(protocol_path),
        "checker_version_digest": evaluator.checker_version_digest,
        "checker_source_digest": evaluator.checker_source_digest,
        "checker_build_digest": evaluator.checker_build_digest,
        "checks": checks,
        "counters": {
            "case_count": len(rows),
            "stage_count": len(stage_counts),
            "python_lean_parity_count": sum(row["parity_match"] is True for row in rows),
            "env_step_count": 0,
            "model_construction_count": 0,
            "policy_inference_count": 0,
            "socket_bind_count": 0,
            "dispatch_count": 0,
        },
        "stage_counts": dict(sorted(stage_counts.items())),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "artifact_root": str(artifact_root.relative_to(ROOT)),
        "rows_digest": digest_payload(rows),
        "rows": rows,
        "formal_rollout_authorized": False,
        "next_gate": (
            "Implement and audit OpenRegion runtime/progress support before post-filter "
            "no-dispatch integration."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    protocol_path = args.protocol.resolve()
    protocol = load_and_verify_protocol(protocol_path)
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "protocol_ready_not_executed",
                    "protocol_sha256": _sha256_file(protocol_path),
                    "case_count": protocol["golden_corpus"]["case_count"],
                    "formal_rollout_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    output = args.output.resolve()
    artifact_root = args.artifact_root.resolve()
    if output.exists():
        raise RuntimeError(f"fresh output required; already exists: {output}")
    if artifact_root.exists():
        raise RuntimeError(f"fresh artifact root required; already exists: {artifact_root}")
    if ROOT not in output.parents or ROOT not in artifact_root.parents:
        raise RuntimeError("output and artifact root must remain inside the repository")

    summary = build_summary(
        protocol_path=protocol_path,
        protocol=protocol,
        artifact_root=artifact_root,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_bytes(summary) + b"\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
