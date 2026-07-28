from __future__ import annotations

import json

from scripts.run_semantic_effect_observer_qualification_e5 import (
    CHECKSUMS_PATH,
    PROTOCOL_PATH,
    RESULT_PATH,
    build_cases,
    build_protocol,
    canonical_text,
    file_sha256,
    validate_protocol,
    validate_result,
)


def test_e5_protocol_and_result_are_current() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    validate_protocol(protocol)
    validate_result(protocol, result)
    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_protocol())
    assert len(build_cases(protocol)) == 2100
    assert CHECKSUMS_PATH.read_text(encoding="utf-8") == (
        f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
    )


def test_e5_analytic_effect_observer_passes_all_frozen_gates() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    summary = result["summary"]

    assert (
        result["classification"]
        == "analytic_semantic_effect_observer_qualified"
    )
    assert summary["case_count"] == 2100
    assert summary["clean_retention"] == 1.0
    assert summary["attack_false_allow_count"] == 0
    assert summary["ood_abstention_rate"] == 1.0
    assert summary["latency_ns"]["p99"] <= protocol["gates"][
        "maximum_p99_latency_ns"
    ]
    assert summary["qualified"] is True
    assert all(summary["gate_results"].values())
