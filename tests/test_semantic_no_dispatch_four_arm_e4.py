from __future__ import annotations

import json

import pytest

from scripts.run_semantic_no_dispatch_four_arm_e4 import (
    PROTOCOL_PATH,
    RESULT_PATH,
    E4GateError,
    build_protocol,
    build_result,
    canonical_text,
    validate_protocol,
    validate_result,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_e4_protocol_and_result_are_canonical() -> None:
    protocol = _protocol()
    observed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_protocol())
    assert RESULT_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_result(protocol))
    validate_result(protocol, observed)


def test_e4_passes_without_authorizing_outcome_execution() -> None:
    result = build_result(_protocol())

    assert result["classification"] == "e4_no_dispatch_gate_pass"
    assert result["e4_complete"] is True
    assert result["failed_gates"] == []
    assert all(result["gate_results"].values())
    assert result["four_arm"]["proposal_count"] == 8
    assert result["four_arm"]["row_count"] == 32
    assert result["trace_independence"]["case_id_overlap"] == []
    assert result["outcome_rollout_ready"] is False
    assert result["outcome_rollout_authorized"] is False
    assert result["no_outcome_boundary"]["e4_dispatch_attempt_count"] == 0


def test_e4_protocol_rejects_execution_authorization() -> None:
    protocol = _protocol()
    protocol["execution_authorization"]["action_dispatch_authorized"] = True

    with pytest.raises(
        E4GateError,
        match="authorizes external execution",
    ):
        validate_protocol(protocol)
