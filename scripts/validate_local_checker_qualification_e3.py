#!/usr/bin/env python3
"""Validate frozen E3 logic while preserving measured latency values.

The frozen runner records ``violation_atoms`` tuples as JSON arrays.  Its own
post-load equality check therefore rejects otherwise identical recomputed
rows.  This validator compares canonical JSON values, without changing the
frozen runner, protocol, or qualification result.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from run_local_checker_qualification_e3 import (  # noqa: E402
    CHECKSUMS_PATH,
    PROTOCOL_PATH,
    RESULT_PATH,
    CheckerQualificationError,
    build_cases,
    canonical_text,
    evaluate_cases,
    file_sha256,
    summarize,
    validate_protocol,
)


def build_report() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    observed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if (
        observed.get("schema")
        != "proofalign.local-checker-qualification-result-e3.v1"
    ):
        raise CheckerQualificationError("unsupported E3 result schema")
    if any(
        observed.get(name) is not False
        for name in (
            "training_performed",
            "policy_loaded",
            "simulator_created",
            "actions_executed",
            "outcomes_read",
        )
    ):
        raise CheckerQualificationError(
            "E3 crossed the no-outcome/no-dispatch boundary"
        )

    recomputed_rows, _ = evaluate_cases(build_cases(protocol))
    if len(recomputed_rows) != len(observed["rows"]):
        raise CheckerQualificationError("E3 row count changed")
    for expected, actual in zip(
        recomputed_rows,
        observed["rows"],
        strict=True,
    ):
        expected["latency_ns"] = actual["latency_ns"]
    if canonical_text(recomputed_rows) != canonical_text(observed["rows"]):
        raise CheckerQualificationError(
            "E3 persisted logic differs from JSON-normalized recomputation"
        )

    latency = observed["summary"]["latency_ns"]
    expected_summary = summarize(protocol, observed["rows"], latency)
    if canonical_text(expected_summary) != canonical_text(observed["summary"]):
        raise CheckerQualificationError("E3 summary is inconsistent")
    expected_classification = (
        "analytic_local_checker_qualified"
        if expected_summary["qualified"]
        else "analytic_local_checker_disqualified"
    )
    if observed["classification"] != expected_classification:
        raise CheckerQualificationError(
            "E3 classification is inconsistent"
        )
    expected_checksums = (
        f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
    )
    if CHECKSUMS_PATH.read_text(encoding="utf-8") != expected_checksums:
        raise CheckerQualificationError(
            "E3 result checksum manifest is stale"
        )

    return {
        "schema": "proofalign.local-checker-e3-validation.v1",
        "valid": True,
        "result_path": str(RESULT_PATH.relative_to(REPO_ROOT)),
        "result_sha256": file_sha256(RESULT_PATH),
        "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "serialization_normalization": {
            "field": "rows[*].violation_atoms",
            "persisted_type": "json_array",
            "frozen_runtime_type": "tuple",
            "values_changed": False,
        },
        "classification": observed["classification"],
        "summary": observed["summary"],
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
        CheckerQualificationError,
        KeyError,
        OSError,
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
