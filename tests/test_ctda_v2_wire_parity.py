from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofalign.ctda import digest_text
from proofalign.ctda_v2_evaluator import (
    CTDAV2EvaluatorMode,
    CTDAV2LeanKernelEvaluator,
    CTDAV2PythonReferenceEvaluator,
    CTDAV2ShadowEvaluator,
    generate_v2_lean_replay_source,
)
from proofalign.ctda_v2_golden import (
    build_v2_golden_corpus,
    semantic_certificate_payload,
)
from proofalign.ctda_v2_wire import (
    V2WireStage,
    V2WireValidationError,
    V2WireVerdict,
    canonical_v2_wire_bytes,
    decode_v2_wire_envelope,
    make_v2_wire_envelope,
    reference_v2_wire_verdict,
)


@pytest.fixture(scope="module")
def evaluator(tmp_path_factory) -> CTDAV2LeanKernelEvaluator:
    return CTDAV2LeanKernelEvaluator(
        artifact_root=tmp_path_factory.mktemp("ctda-v2-kernel-artifacts"),
        timeout_seconds=20,
    )


def test_v2_wire_round_trip_covers_all_six_stages(evaluator) -> None:
    corpus = build_v2_golden_corpus(evaluator.checker_version_digest)
    positive = {}
    for case in corpus:
        positive.setdefault(case.request.stage, case)

    assert set(positive) == set(V2WireStage)
    for stage, case in positive.items():
        decoded = decode_v2_wire_envelope(case.request.canonical_bytes())
        assert decoded == case.request, stage
        assert decoded.request_id == case.request.request_id
        assert reference_v2_wire_verdict(decoded) is case.expected


def test_v2_wire_rejects_v1_default_fill_extra_tamper_and_request_id(evaluator) -> None:
    request = build_v2_golden_corpus(evaluator.checker_version_digest)[0].request

    v1 = request.to_dict()
    v1["schema_version"] = "ctda-wire-v1"
    with pytest.raises(V2WireValidationError, match="unsupported"):
        decode_v2_wire_envelope(v1)

    missing = request.to_dict()
    del missing["method_id"]
    with pytest.raises(V2WireValidationError, match="fields mismatch"):
        decode_v2_wire_envelope(missing)

    extra = request.to_dict()
    extra["payload"]["legacy_default"] = True
    with pytest.raises(V2WireValidationError, match="fields mismatch"):
        decode_v2_wire_envelope(extra)

    tampered = request.to_dict()
    tampered["payload"]["phase"] = "holding"
    tampered["payload_digest"] = request.payload_digest
    with pytest.raises(V2WireValidationError, match="request_id|digest mismatch"):
        decode_v2_wire_envelope(tampered)

    wrong_id = request.to_dict()
    wrong_id["request_id"] = "0" * 64
    with pytest.raises(V2WireValidationError, match="request_id"):
        decode_v2_wire_envelope(wrong_id)


def test_v2_wire_rejects_duplicate_nonfinite_and_noncanonical_json(evaluator) -> None:
    request = build_v2_golden_corpus(evaluator.checker_version_digest)[0].request
    text = request.canonical_bytes().decode("utf-8")

    with pytest.raises(V2WireValidationError, match="duplicate"):
        decode_v2_wire_envelope(
            '{"schema_version":"ctda-wire-v2","schema_version":"ctda-wire-v2"}'
        )
    with pytest.raises(V2WireValidationError, match="non-finite"):
        decode_v2_wire_envelope(text.replace('"proof_started_at_ns":20', '"proof_started_at_ns":NaN'))
    with pytest.raises(V2WireValidationError, match="canonical"):
        decode_v2_wire_envelope(
            json.dumps(request.to_dict(), ensure_ascii=True, indent=2).encode("utf-8")
        )


def test_python_reference_matches_frozen_golden_corpus(evaluator) -> None:
    python = CTDAV2PythonReferenceEvaluator(evaluator.checker_version_digest)
    corpus = build_v2_golden_corpus(evaluator.checker_version_digest)

    for case in corpus:
        result = python.evaluate(case.request)
        assert result.verdict is case.expected, case.case_id
        assert result.artifact.mode is CTDAV2EvaluatorMode.PYTHON_REFERENCE
        assert result.artifact.proof_verified is False


def test_lean_kernel_matches_all_21_golden_cases(evaluator) -> None:
    corpus = build_v2_golden_corpus(evaluator.checker_version_digest)

    for case in corpus:
        result = evaluator.evaluate(case.request)
        assert result.verdict is case.expected, case.case_id
        assert result.artifact.proof_verified is True, case.case_id
        assert result.artifact.parity_match is True, case.case_id
        artifact_dir = Path(result.artifact.artifact_dir or "")
        assert (artifact_dir / "request.json").is_file(), case.case_id
        assert (artifact_dir / "Replay.lean").is_file(), case.case_id
        assert (artifact_dir / "result.json").is_file(), case.case_id


def test_golden_corpus_exercises_all_verdicts_except_kernel_inconsistent(evaluator) -> None:
    verdicts = {
        case.expected for case in build_v2_golden_corpus(evaluator.checker_version_digest)
    }
    assert verdicts == {
        V2WireVerdict.PROVEN,
        V2WireVerdict.REFUTED,
        V2WireVerdict.REPLAN,
        V2WireVerdict.HARD_BLOCK,
    }


def test_v2_lean_source_uses_character_codes_for_injection_text(evaluator) -> None:
    payload = semantic_certificate_payload()
    payload["episode_nonce"] = '你好"\\\nexample : False := by trivial'
    payload["proof_state_episode_nonce"] = payload["episode_nonce"]
    request = make_v2_wire_envelope(
        V2WireStage.SEMANTIC_CERTIFICATE,
        evaluator.checker_version_digest,
        payload,
    )
    source = generate_v2_lean_replay_source(request, V2WireVerdict.PROVEN)
    result = evaluator.evaluate(request)

    assert "example : False" not in source
    assert "Char.ofNat" in source
    assert result.verdict is V2WireVerdict.PROVEN
    assert result.artifact.proof_verified is True


def test_v2_lean_unavailable_and_checker_digest_tamper_fail_closed(
    evaluator, tmp_path
) -> None:
    unavailable = CTDAV2LeanKernelEvaluator(
        lean_command=str(tmp_path / "missing-lean"),
        artifact_root=tmp_path / "unavailable-artifacts",
    )
    request = make_v2_wire_envelope(
        V2WireStage.SEMANTIC_CERTIFICATE,
        unavailable.checker_version_digest,
        semantic_certificate_payload(),
    )
    unavailable_result = unavailable.evaluate(request)

    wrong_checker_request = make_v2_wire_envelope(
        V2WireStage.SEMANTIC_CERTIFICATE,
        digest_text("another-v2-kernel"),
        semantic_certificate_payload(),
    )
    mismatch_result = evaluator.evaluate(wrong_checker_request)

    assert unavailable_result.verdict is V2WireVerdict.INCONSISTENT
    assert unavailable_result.artifact.proof_verified is False
    assert mismatch_result.verdict is V2WireVerdict.INCONSISTENT
    assert mismatch_result.artifact.proof_verified is False


def test_v2_shadow_reports_parity_but_never_authorizes(evaluator) -> None:
    python = CTDAV2PythonReferenceEvaluator(evaluator.checker_version_digest)
    shadow = CTDAV2ShadowEvaluator(python, evaluator)
    request = build_v2_golden_corpus(evaluator.checker_version_digest)[0].request

    result = shadow.evaluate(request)

    assert result.verdict is V2WireVerdict.PROVEN
    assert result.artifact.mode is CTDAV2EvaluatorMode.SHADOW
    assert result.artifact.parity_match is True
    assert result.artifact.proof_verified is False
    assert result.proven is False


def test_v2_lean_cache_binds_schema_checker_stage_and_payload(evaluator) -> None:
    request = build_v2_golden_corpus(evaluator.checker_version_digest)[0].request
    first = evaluator.evaluate(request)
    second = evaluator.evaluate(request)
    changed_payload = semantic_certificate_payload()
    changed_payload["proof_completed_at_ns"] = 101
    changed_payload["proof_attestation_issued_at_ns"] = 101
    changed = make_v2_wire_envelope(
        V2WireStage.SEMANTIC_CERTIFICATE,
        evaluator.checker_version_digest,
        changed_payload,
    )
    third = evaluator.evaluate(changed)

    assert first.artifact.cache_key == second.artifact.cache_key
    assert second.artifact.cache_hit is True
    assert third.artifact.cache_key != first.artifact.cache_key


def test_canonical_helper_refuses_non_json_values() -> None:
    with pytest.raises(V2WireValidationError):
        canonical_v2_wire_bytes({"bad": object()})
