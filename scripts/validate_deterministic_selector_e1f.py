#!/usr/bin/env python3
"""Validate E1F logic while preserving its frozen latency measurements."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from run_deterministic_selector_qualification_e1f import (  # noqa: E402
    EVIDENCE_PATH,
    FallbackQualificationError,
    PROTOCOL_PATH,
    build_evidence,
    canonical_text,
    file_sha256,
    validate_protocol,
)


def build_report() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    observed = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    recomputed = build_evidence(protocol)
    if len(observed["rows"]) != len(recomputed["rows"]):
        raise FallbackQualificationError("E1F row count changed")
    for observed_row, recomputed_row in zip(
        observed["rows"],
        recomputed["rows"],
        strict=True,
    ):
        recomputed_row["first_latency_ns"] = observed_row[
            "first_latency_ns"
        ]
    recomputed["latency_ns"] = observed["latency_ns"]
    p99_pass = (
        observed["latency_ns"]["p99"]
        <= protocol["gates"]["maximum_p99_latency_ns"]
    )
    recomputed["gate_results"]["p99_latency"] = p99_pass
    recomputed["qualified"] = all(
        recomputed["gate_results"].values()
    )
    recomputed["classification"] = (
        "deterministic_fsm_fallback_gate_pass"
        if recomputed["qualified"]
        else "deterministic_fsm_fallback_gate_fail"
    )
    if canonical_text(observed) != canonical_text(recomputed):
        raise FallbackQualificationError(
            "E1F persisted logic differs from recomputation"
        )
    expected_measurements = (
        protocol["expected_case_count"]
        * protocol["latency_repetitions_per_case"]
    )
    if observed["latency_ns"]["measurement_count"] != expected_measurements:
        raise FallbackQualificationError(
            "E1F latency measurement count is inconsistent"
        )
    return {
        "schema": "proofalign.deterministic-selector-e1f-validation.v1",
        "valid": True,
        "evidence_path": str(EVIDENCE_PATH.relative_to(REPO_ROOT)),
        "evidence_sha256": file_sha256(EVIDENCE_PATH),
        "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "classification": observed["classification"],
        "case_count": observed["case_count"],
        "exact_match_rate": observed["exact_match_rate"],
        "unknown_fail_closed_rate": observed[
            "unknown_fail_closed_rate"
        ],
        "latency_ns": observed["latency_ns"],
        "gate_results": observed["gate_results"],
        "qualified": observed["qualified"],
        "no_outcome_boundary": {
            "training_performed": observed["training_performed"],
            "policy_loaded": observed["policy_loaded"],
            "simulator_created": observed["simulator_created"],
            "actions_executed": observed["actions_executed"],
            "outcomes_read": observed["outcomes_read"],
        },
    }


def main() -> int:
    try:
        print(json.dumps(build_report(), indent=2, ensure_ascii=False))
        return 0
    except (
        FallbackQualificationError,
        KeyError,
        OSError,
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
