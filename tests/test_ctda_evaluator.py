from __future__ import annotations

from pathlib import Path

import pytest

from proofalign.ctda_evaluator import (
    CTDAEvaluatorMode,
    LeanKernelEvaluator,
    PythonReferenceEvaluator,
    ShadowEvaluator,
    generate_lean_replay_source,
)
from proofalign.ctda_wire import (
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    make_wire_request,
)


def _semantic() -> dict:
    return {
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "contract_digest": "contract",
        "active_phase": "approach",
        "contract_phase": "approach",
        "enabled_obligation_ids": ["pick:mug"],
        "contract_obligation_ids": ["pick:mug"],
        "contract_target": "mug",
        "obligation_target": "mug",
        "contract_part": "handle",
        "obligation_part": "handle",
        "contract_region": None,
        "obligation_region": None,
        "mission_integrity": True,
        "contract_integrity": True,
        "issued_at_ns": 10,
        "deadline_ns": 100,
        "now_ns": 20,
        "guarantee": {"tag": "atom", "name": "holding:mug", "expected": True},
    }


def _prefix() -> dict:
    return {
        "semantic_request_id": "semantic",
        "semantic_verdict": "proven",
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "contract_digest": "contract",
        "binder_verdict": "proven",
        "state_digest": "state",
        "authorization_state_digest": "state",
        "monitor_digest": "monitor",
        "authorization_monitor_digest": "monitor",
        "episode_nonce": "episode",
        "authorization_nonce": "episode",
        "proposal_index": 0,
        "authorization_proposal_index": 0,
        "monitor_last_proposal_index": -1,
        "proposal_digest": "proposal",
        "authorization_proposal_digest": "proposal",
        "command_digest": "command",
        "authorization_command_digest": "command",
        "time_base_digest": "time",
        "authorization_time_base_digest": "time",
        "now_ns": 20,
        "issued_at_ns": 10,
        "valid_until_ns": 50,
        "duration_ns": 20,
    }


def _observed() -> dict:
    return {
        "prefix_request_id": "prefix",
        "prefix_verdict": "proven",
        "plant_verdict": "proven",
        "authorization_digest": "authorization",
        "receipt_authorization_digest": "authorization",
        "episode_nonce": "episode",
        "receipt_episode_nonce": "episode",
        "authorized_command_digest": "command",
        "dispatched_command_digest": "command",
        "receipt_command_digest": "command",
        "mission_time_base_digest": "time",
        "plant_time_base_digest": "time",
        "dispatch_ns": 30,
        "observed_ns": 40,
        "receipt_digest": "receipt",
        "plant_trace_digest": "plant",
        "event_trace_digest": "events",
    }


def _monitor() -> dict:
    return {
        "observed_request_id": "observed",
        "observed_verdict": "proven",
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "episode_nonce": "episode",
        "monitor_episode_nonce": "episode",
        "contract_digest": "contract",
        "monitor_contract_digest": "contract",
        "active_phase": "approach",
        "monitor_phase": "approach",
        "previous_monitor_digest": "monitor",
        "record_monitor_before_digest": "monitor",
        "previous_last_timestamp_ns": -1,
        "event_timestamps_ns": [40],
        "previous_observed_atoms": [],
        "current_observed_atoms": ["holding:mug"],
        "guarantee": {"tag": "atom", "name": "holding:mug", "expected": True},
        "invariant": {"tag": "atom", "name": "collision", "expected": False},
        "expected_phase": "holding",
        "terminal_phase_event": True,
        "completion_witness": True,
        "post_evidence": True,
        "now_ns": 40,
        "deadline_ns": 100,
        "next_proposal_index": 1,
        "record_proposal_index": 0,
    }


@pytest.fixture(scope="module")
def evaluator(tmp_path_factory) -> LeanKernelEvaluator:
    return LeanKernelEvaluator(
        artifact_root=tmp_path_factory.mktemp("ctda-kernel-artifacts"),
        timeout_seconds=20,
    )


@pytest.mark.parametrize(
    ("stage", "payload_factory", "expected"),
    [
        (WireStage.SEMANTIC, _semantic, WireStaticVerdict.PROVEN),
        (WireStage.PREFIX_PRE, _prefix, WireStaticVerdict.PROVEN),
        (WireStage.OBSERVED_PREFIX, _observed, WireStaticVerdict.PROVEN),
        (WireStage.MONITOR_STEP, _monitor, WireMonitorVerdict.COMPLETE),
    ],
)
def test_lean_kernel_checks_each_wire_stage(
    evaluator, stage, payload_factory, expected
) -> None:
    request = make_wire_request(
        stage, evaluator.checker_version_digest, payload_factory()
    )

    result = evaluator.evaluate(request)

    assert result.verdict is expected
    assert result.artifact.mode is CTDAEvaluatorMode.LEAN_KERNEL
    assert result.artifact.proof_verified is True
    assert result.artifact.parity_match is True
    assert result.artifact.artifact_dir is not None
    artifact_dir = Path(result.artifact.artifact_dir)
    assert (artifact_dir / "request.json").is_file()
    assert (artifact_dir / "Replay.lean").is_file()
    assert (artifact_dir / "result.json").is_file()
    assert (artifact_dir / "stdout.txt").is_file()
    assert (artifact_dir / "stderr.txt").is_file()


@pytest.mark.parametrize(
    ("stage", "payload_factory", "mutation", "expected"),
    [
        (
            WireStage.SEMANTIC,
            _semantic,
            lambda value: value.__setitem__("contract_target", "knife"),
            WireStaticVerdict.REFUTED,
        ),
        (
            WireStage.PREFIX_PRE,
            _prefix,
            lambda value: value.__setitem__("authorization_nonce", "replay"),
            WireStaticVerdict.REFUTED,
        ),
        (
            WireStage.OBSERVED_PREFIX,
            _observed,
            lambda value: value.__setitem__("receipt_command_digest", "tamper"),
            WireStaticVerdict.REFUTED,
        ),
        (
            WireStage.MONITOR_STEP,
            _monitor,
            lambda value: value.__setitem__("previous_last_timestamp_ns", 50),
            WireMonitorVerdict.INCONSISTENT,
        ),
    ],
)
def test_lean_kernel_checks_negative_golden_cases(
    evaluator, stage, payload_factory, mutation, expected
) -> None:
    payload = payload_factory()
    mutation(payload)
    request = make_wire_request(stage, evaluator.checker_version_digest, payload)

    result = evaluator.evaluate(request)

    assert result.verdict is expected
    assert result.artifact.proof_verified is True
    assert result.artifact.parity_match is True


def test_lean_source_uses_character_codes_for_injection_strings(evaluator) -> None:
    payload = _semantic()
    payload["mission_digest"] = '你好"\\\nexample : False := by trivial'
    payload["contract_spec_digest"] = payload["mission_digest"]
    request = make_wire_request(
        WireStage.SEMANTIC, evaluator.checker_version_digest, payload
    )

    source = generate_lean_replay_source(request, WireStaticVerdict.PROVEN)
    result = evaluator.evaluate(request)

    assert 'example : False' not in source
    assert "Char.ofNat" in source
    assert result.verdict is WireStaticVerdict.PROVEN
    assert result.artifact.proof_verified is True


def test_lean_unavailable_and_checker_digest_tamper_fail_closed(tmp_path) -> None:
    unavailable = LeanKernelEvaluator(
        lean_command=str(tmp_path / "missing-lean"), artifact_root=tmp_path / "artifacts"
    )
    request = make_wire_request(
        WireStage.SEMANTIC, unavailable.checker_version_digest, _semantic()
    )
    unavailable_result = unavailable.evaluate(request)
    wrong_digest_request = make_wire_request(
        WireStage.SEMANTIC, "0" * 64, _semantic()
    )
    digest_result = unavailable.evaluate(wrong_digest_request)

    assert unavailable_result.verdict is WireStaticVerdict.INCONSISTENT
    assert unavailable_result.artifact.proof_verified is False
    assert digest_result.verdict is WireStaticVerdict.INCONSISTENT
    assert digest_result.artifact.proof_verified is False


def test_shadow_reports_zero_parity_mismatch_but_never_authorizes(evaluator) -> None:
    python = PythonReferenceEvaluator(evaluator.checker_version_digest)
    shadow = ShadowEvaluator(python, evaluator)
    request = make_wire_request(
        WireStage.PREFIX_PRE, evaluator.checker_version_digest, _prefix()
    )

    result = shadow.evaluate(request)

    assert result.verdict is WireStaticVerdict.PROVEN
    assert result.artifact.mode is CTDAEvaluatorMode.SHADOW
    assert result.artifact.parity_match is True
    assert result.artifact.proof_verified is False
    assert result.proven is False


def test_lean_cache_is_bound_to_mode_schema_checker_and_request(evaluator) -> None:
    request = make_wire_request(
        WireStage.SEMANTIC, evaluator.checker_version_digest, _semantic()
    )
    first = evaluator.evaluate(request)
    second = evaluator.evaluate(request)
    changed = _semantic()
    changed["now_ns"] = 21
    third = evaluator.evaluate(
        make_wire_request(WireStage.SEMANTIC, evaluator.checker_version_digest, changed)
    )

    assert first.artifact.cache_key == second.artifact.cache_key
    assert second.artifact.cache_hit is True
    assert third.artifact.cache_key != first.artifact.cache_key
