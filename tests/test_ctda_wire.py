from __future__ import annotations

import json

import pytest

from proofalign.ctda import digest_text
from proofalign.ctda_wire import (
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    WireValidationError,
    canonical_wire_bytes,
    decode_wire_request,
    make_wire_request,
    reference_wire_verdict,
)


CHECKER_DIGEST = digest_text("ctda-wire-test-checker")


def _semantic_payload() -> dict:
    return {
        "mission_digest": "mission-你好-\"quote\"-\\-\n-import ProofAlign",
        "contract_spec_digest": "mission-你好-\"quote\"-\\-\n-import ProofAlign",
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
        "guarantee": {
            "tag": "eventually",
            "item": {"tag": "atom", "name": "holding:mug", "expected": True},
            "deadline_ns": 100,
        },
    }


def _prefix_payload() -> dict:
    return {
        "semantic_request_id": "semantic-request",
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


def _observed_payload() -> dict:
    return {
        "prefix_request_id": "prefix-request",
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


def _monitor_payload() -> dict:
    return {
        "observed_request_id": "observed-request",
        "observed_verdict": "proven",
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "episode_nonce": "episode",
        "monitor_episode_nonce": "episode",
        "contract_digest": "contract",
        "monitor_contract_digest": "contract",
        "active_phase": "approach",
        "monitor_phase": "approach",
        "previous_monitor_digest": "monitor-before",
        "record_monitor_before_digest": "monitor-before",
        "previous_last_timestamp_ns": -1,
        "event_timestamps_ns": [40],
        "previous_observed_atoms": [],
        "current_observed_atoms": ["holding:mug"],
        "guarantee": {
            "tag": "eventually",
            "item": {"tag": "atom", "name": "holding:mug", "expected": True},
            "deadline_ns": 100,
        },
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


@pytest.mark.parametrize(
    ("stage", "payload", "verdict"),
    [
        (WireStage.SEMANTIC, _semantic_payload, WireStaticVerdict.PROVEN),
        (WireStage.PREFIX_PRE, _prefix_payload, WireStaticVerdict.PROVEN),
        (WireStage.OBSERVED_PREFIX, _observed_payload, WireStaticVerdict.PROVEN),
        (WireStage.MONITOR_STEP, _monitor_payload, WireMonitorVerdict.COMPLETE),
    ],
)
def test_wire_round_trip_and_reference_verdict(stage, payload, verdict) -> None:
    request = make_wire_request(stage, CHECKER_DIGEST, payload())

    decoded = decode_wire_request(request.canonical_bytes())

    assert decoded == request
    assert reference_wire_verdict(decoded) is verdict


def test_wire_is_canonical_utf8_and_escapes_source_injection_text() -> None:
    request = make_wire_request(WireStage.SEMANTIC, CHECKER_DIGEST, _semantic_payload())
    encoded = request.canonical_bytes()

    assert "你好" in encoded.decode("utf-8")
    assert b'\\"quote\\"' in encoded
    assert b"\\\\" in encoded
    assert b"\\n-import ProofAlign" in encoded
    assert encoded == canonical_wire_bytes(json.loads(encoded))
    assert decode_wire_request(encoded).payload["mission_digest"].endswith(
        "\n-import ProofAlign"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["payload"].__setitem__("unknown", True),
        lambda value: value["payload"].pop("mission_digest"),
        lambda value: value["payload"].__setitem__("now_ns", 1.5),
        lambda value: value["payload"].__setitem__("now_ns", True),
        lambda value: value.__setitem__("stage", "future_stage"),
        lambda value: value.__setitem__("time_unit", "ms"),
    ],
)
def test_wire_rejects_unknown_missing_enum_and_wrong_types(mutation) -> None:
    request = make_wire_request(WireStage.SEMANTIC, CHECKER_DIGEST, _semantic_payload())
    value = request.to_dict()
    mutation(value)

    with pytest.raises(WireValidationError):
        decode_wire_request(canonical_wire_bytes(value))


def test_wire_rejects_nan_infinity_duplicate_keys_and_noncanonical_bytes() -> None:
    request = make_wire_request(WireStage.SEMANTIC, CHECKER_DIGEST, _semantic_payload())
    text = request.canonical_bytes().decode("utf-8")

    with pytest.raises(WireValidationError):
        decode_wire_request(text.replace('"now_ns":20', '"now_ns":NaN'))
    with pytest.raises(WireValidationError):
        decode_wire_request(text.replace('"now_ns":20', '"now_ns":Infinity'))
    with pytest.raises(WireValidationError, match="duplicate"):
        decode_wire_request('{"schema_version":"ctda-wire-v1","schema_version":"x"}')
    with pytest.raises(WireValidationError, match="canonical"):
        decode_wire_request(json.dumps(request.to_dict(), ensure_ascii=True, indent=2).encode())


def test_consumer_recomputes_request_id_after_critical_tamper() -> None:
    request = make_wire_request(WireStage.PREFIX_PRE, CHECKER_DIGEST, _prefix_payload())
    value = request.to_dict()
    value["payload"]["authorization_nonce"] = "cross-episode"

    with pytest.raises(WireValidationError, match="request_id"):
        decode_wire_request(canonical_wire_bytes(value))


def test_set_like_lists_and_formula_children_have_stable_order() -> None:
    payload = _semantic_payload()
    payload["enabled_obligation_ids"] = ["z", "a", "z"]
    payload["contract_obligation_ids"] = ["a", "z"]
    payload["guarantee"] = {
        "tag": "all",
        "items": [
            {"tag": "atom", "name": "z", "expected": True},
            {"tag": "atom", "name": "a", "expected": True},
        ],
    }

    request = make_wire_request(WireStage.SEMANTIC, CHECKER_DIGEST, payload)

    assert request.payload["enabled_obligation_ids"] == ["a", "z"]
    assert [item["name"] for item in request.payload["guarantee"]["items"]] == ["a", "z"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda value: value.__setitem__("contract_spec_digest", "tampered"), WireStaticVerdict.REFUTED),
        (lambda value: value.__setitem__("binder_verdict", "unknown"), WireStaticVerdict.REFUTED),
        (lambda value: value.__setitem__("authorization_nonce", "replay"), WireStaticVerdict.REFUTED),
        (lambda value: value.__setitem__("authorization_command_digest", "other"), WireStaticVerdict.REFUTED),
        (lambda value: value.__setitem__("authorization_time_base_digest", "other"), WireStaticVerdict.REFUTED),
    ],
)
def test_prefix_reference_fails_closed_on_binding_tamper(mutation, expected) -> None:
    payload = _prefix_payload()
    mutation(payload)
    request = make_wire_request(WireStage.PREFIX_PRE, CHECKER_DIGEST, payload)

    assert reference_wire_verdict(request) is expected


def test_monitor_distinguishes_pending_violation_and_timestamp_inconsistency() -> None:
    pending = _monitor_payload()
    pending["current_observed_atoms"] = []
    pending["terminal_phase_event"] = False
    violated = _monitor_payload()
    violated["current_observed_atoms"] = ["collision"]
    rollback = _monitor_payload()
    rollback["previous_last_timestamp_ns"] = 50

    assert reference_wire_verdict(
        make_wire_request(WireStage.MONITOR_STEP, CHECKER_DIGEST, pending)
    ) is WireMonitorVerdict.SAFE_PENDING
    assert reference_wire_verdict(
        make_wire_request(WireStage.MONITOR_STEP, CHECKER_DIGEST, violated)
    ) is WireMonitorVerdict.VIOLATED
    assert reference_wire_verdict(
        make_wire_request(WireStage.MONITOR_STEP, CHECKER_DIGEST, rollback)
    ) is WireMonitorVerdict.INCONSISTENT
