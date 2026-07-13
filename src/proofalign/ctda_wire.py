"""Canonical internal wire protocol for the jointly supported CTDA slice.

This schema is intentionally separate from episode JSON and attack-record files.
It accepts only a small Pick/Place judgment vocabulary and rejects extensions by
default so Python and Lean cannot silently interpret different requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "ctda-wire-v1"
TIME_UNIT = "ns"


class WireValidationError(ValueError):
    pass


class WireStage(str, Enum):
    SEMANTIC = "semantic"
    PREFIX_PRE = "prefix_pre"
    OBSERVED_PREFIX = "observed_prefix"
    MONITOR_STEP = "monitor_step"


class WireStaticVerdict(str, Enum):
    PROVEN = "proven"
    REFUTED = "refuted"
    UNKNOWN = "unknown"
    INCONSISTENT = "inconsistent"


class WireMonitorVerdict(str, Enum):
    SAFE_PENDING = "safe_pending"
    COMPLETE = "complete"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    INCONSISTENT = "inconsistent"


_ENVELOPE_FIELDS = {
    "schema_version",
    "request_id",
    "stage",
    "time_unit",
    "checker_version_digest",
    "payload",
}

_PAYLOAD_FIELDS: dict[WireStage, set[str]] = {
    WireStage.SEMANTIC: {
        "mission_digest",
        "contract_spec_digest",
        "contract_digest",
        "active_phase",
        "contract_phase",
        "enabled_obligation_ids",
        "contract_obligation_ids",
        "contract_target",
        "obligation_target",
        "contract_part",
        "obligation_part",
        "contract_region",
        "obligation_region",
        "mission_integrity",
        "contract_integrity",
        "issued_at_ns",
        "deadline_ns",
        "now_ns",
        "guarantee",
    },
    WireStage.PREFIX_PRE: {
        "semantic_request_id",
        "semantic_verdict",
        "mission_digest",
        "contract_spec_digest",
        "contract_digest",
        "binder_verdict",
        "state_digest",
        "authorization_state_digest",
        "monitor_digest",
        "authorization_monitor_digest",
        "episode_nonce",
        "authorization_nonce",
        "proposal_index",
        "authorization_proposal_index",
        "monitor_last_proposal_index",
        "proposal_digest",
        "authorization_proposal_digest",
        "command_digest",
        "authorization_command_digest",
        "time_base_digest",
        "authorization_time_base_digest",
        "now_ns",
        "issued_at_ns",
        "valid_until_ns",
        "duration_ns",
    },
    WireStage.OBSERVED_PREFIX: {
        "prefix_request_id",
        "prefix_verdict",
        "plant_verdict",
        "authorization_digest",
        "receipt_authorization_digest",
        "episode_nonce",
        "receipt_episode_nonce",
        "authorized_command_digest",
        "dispatched_command_digest",
        "receipt_command_digest",
        "mission_time_base_digest",
        "plant_time_base_digest",
        "dispatch_ns",
        "observed_ns",
        "receipt_digest",
        "plant_trace_digest",
        "event_trace_digest",
    },
    WireStage.MONITOR_STEP: {
        "observed_request_id",
        "observed_verdict",
        "mission_digest",
        "contract_spec_digest",
        "episode_nonce",
        "monitor_episode_nonce",
        "contract_digest",
        "monitor_contract_digest",
        "active_phase",
        "monitor_phase",
        "previous_monitor_digest",
        "record_monitor_before_digest",
        "previous_last_timestamp_ns",
        "event_timestamps_ns",
        "previous_observed_atoms",
        "current_observed_atoms",
        "guarantee",
        "invariant",
        "expected_phase",
        "terminal_phase_event",
        "completion_witness",
        "post_evidence",
        "now_ns",
        "deadline_ns",
        "next_proposal_index",
        "record_proposal_index",
    },
}

_SET_LIST_FIELDS = {
    "enabled_obligation_ids",
    "contract_obligation_ids",
    "previous_observed_atoms",
    "current_observed_atoms",
}

_TEXT_FIELDS = {
    "mission_digest",
    "contract_spec_digest",
    "contract_digest",
    "active_phase",
    "contract_phase",
    "semantic_request_id",
    "state_digest",
    "authorization_state_digest",
    "monitor_digest",
    "authorization_monitor_digest",
    "episode_nonce",
    "authorization_nonce",
    "proposal_digest",
    "authorization_proposal_digest",
    "command_digest",
    "authorization_command_digest",
    "time_base_digest",
    "authorization_time_base_digest",
    "prefix_request_id",
    "authorization_digest",
    "receipt_authorization_digest",
    "receipt_episode_nonce",
    "authorized_command_digest",
    "dispatched_command_digest",
    "receipt_command_digest",
    "mission_time_base_digest",
    "plant_time_base_digest",
    "receipt_digest",
    "plant_trace_digest",
    "event_trace_digest",
    "observed_request_id",
    "monitor_episode_nonce",
    "monitor_contract_digest",
    "monitor_phase",
    "previous_monitor_digest",
    "record_monitor_before_digest",
    "expected_phase",
}

_OPTIONAL_TEXT_FIELDS = {
    "contract_target",
    "obligation_target",
    "contract_part",
    "obligation_part",
    "contract_region",
    "obligation_region",
}

_BOOL_FIELDS = {
    "mission_integrity",
    "contract_integrity",
    "terminal_phase_event",
    "completion_witness",
    "post_evidence",
}

_NS_FIELDS = {
    "issued_at_ns",
    "deadline_ns",
    "now_ns",
    "valid_until_ns",
    "duration_ns",
    "dispatch_ns",
    "observed_ns",
    "previous_last_timestamp_ns",
}

_INDEX_FIELDS = {
    "proposal_index",
    "authorization_proposal_index",
    "monitor_last_proposal_index",
    "next_proposal_index",
    "record_proposal_index",
}


@dataclass(frozen=True)
class CTDAWireRequest:
    schema_version: str
    request_id: str
    stage: WireStage
    time_unit: str
    checker_version_digest: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "stage": self.stage.value,
            "time_unit": self.time_unit,
            "checker_version_digest": self.checker_version_digest,
            "payload": self.payload,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_wire_bytes(self.to_dict())


def make_wire_request(
    stage: WireStage | str,
    checker_version_digest: str,
    payload: Mapping[str, Any],
) -> CTDAWireRequest:
    actual_stage = WireStage(stage)
    normalized = _normalize_payload(actual_stage, dict(payload))
    _validate_checker_digest(checker_version_digest)
    request_id = _request_id(actual_stage, checker_version_digest, normalized)
    return CTDAWireRequest(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        stage=actual_stage,
        time_unit=TIME_UNIT,
        checker_version_digest=checker_version_digest,
        payload=normalized,
    )


def decode_wire_request(raw: bytes | str) -> CTDAWireRequest:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise WireValidationError("wire request is not canonical UTF-8") from exc
    elif isinstance(raw, str):
        text = raw
    else:
        raise WireValidationError("wire request must be UTF-8 bytes or text")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=lambda value: (_raise_nonfinite(value)),
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WireValidationError("wire request is not valid JSON") from exc
    if not isinstance(value, dict):
        raise WireValidationError("wire envelope must be an object")
    _require_exact_fields(value, _ENVELOPE_FIELDS, "wire envelope")
    if value["schema_version"] != SCHEMA_VERSION:
        raise WireValidationError("unsupported wire schema_version")
    if value["time_unit"] != TIME_UNIT:
        raise WireValidationError("wire time_unit must be ns")
    try:
        stage = WireStage(value["stage"])
    except (TypeError, ValueError) as exc:
        raise WireValidationError("wire stage is unknown") from exc
    _validate_checker_digest(value["checker_version_digest"])
    if not isinstance(value["request_id"], str) or not value["request_id"]:
        raise WireValidationError("wire request_id must be non-empty text")
    if not isinstance(value["payload"], dict):
        raise WireValidationError("wire payload must be an object")
    normalized = _normalize_payload(stage, value["payload"])
    expected = _request_id(stage, value["checker_version_digest"], normalized)
    if value["request_id"] != expected:
        raise WireValidationError("wire request_id digest does not match its critical fields")
    request = CTDAWireRequest(
        schema_version=SCHEMA_VERSION,
        request_id=expected,
        stage=stage,
        time_unit=TIME_UNIT,
        checker_version_digest=value["checker_version_digest"],
        payload=normalized,
    )
    if isinstance(raw, bytes) and raw != request.canonical_bytes():
        raise WireValidationError("wire bytes are not in canonical JSON form")
    return request


def canonical_wire_bytes(value: Mapping[str, Any]) -> bytes:
    _reject_unsupported_json(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WireValidationError(f"wire value is not canonical JSON: {exc}") from exc


def temporal_formula(value: Mapping[str, Any]) -> dict[str, Any]:
    formula = dict(value)
    tag = formula.get("tag")
    if tag == "atom":
        _require_exact_fields(formula, {"tag", "name", "expected"}, "atom formula")
        if not isinstance(formula["name"], str) or not formula["name"]:
            raise WireValidationError("formula atom name must be non-empty text")
        if type(formula["expected"]) is not bool:
            raise WireValidationError("formula atom expected must be bool")
        return {"tag": "atom", "name": formula["name"], "expected": formula["expected"]}
    if tag in {"all", "any"}:
        _require_exact_fields(formula, {"tag", "items"}, f"{tag} formula")
        if not isinstance(formula["items"], list) or not formula["items"]:
            raise WireValidationError(f"{tag} formula items must be a non-empty list")
        items = [temporal_formula(item) for item in formula["items"]]
        items.sort(key=lambda item: canonical_wire_bytes(item))
        if len({canonical_wire_bytes(item) for item in items}) != len(items):
            raise WireValidationError(f"{tag} formula items must be unique")
        return {"tag": tag, "items": items}
    if tag == "not":
        _require_exact_fields(formula, {"tag", "item"}, "not formula")
        return {"tag": "not", "item": temporal_formula(formula["item"])}
    if tag == "eventually":
        _require_exact_fields(formula, {"tag", "item", "deadline_ns"}, "eventually formula")
        _require_nonnegative_int("deadline_ns", formula["deadline_ns"])
        return {
            "tag": "eventually",
            "item": temporal_formula(formula["item"]),
            "deadline_ns": formula["deadline_ns"],
        }
    raise WireValidationError("temporal formula tag is unknown")


def evaluate_temporal_formula(
    formula: Mapping[str, Any],
    observed_atoms: Sequence[str],
    *,
    now_ns: int,
) -> bool | None:
    value = temporal_formula(formula)
    atoms = set(observed_atoms)
    tag = value["tag"]
    if tag == "atom":
        if value["expected"]:
            return True if value["name"] in atoms else None
        return value["name"] not in atoms
    if tag in {"all", "any"}:
        results = [evaluate_temporal_formula(item, atoms, now_ns=now_ns) for item in value["items"]]
        if tag == "all":
            if False in results:
                return False
            return True if all(item is True for item in results) else None
        if True in results:
            return True
        return False if all(item is False for item in results) else None
    if tag == "not":
        result = evaluate_temporal_formula(value["item"], atoms, now_ns=now_ns)
        return None if result is None else not result
    result = evaluate_temporal_formula(value["item"], atoms, now_ns=now_ns)
    if result is True:
        return True
    return False if now_ns > value["deadline_ns"] else None


def reference_wire_verdict(
    request: CTDAWireRequest,
) -> WireStaticVerdict | WireMonitorVerdict:
    payload = request.payload
    if request.stage is WireStage.SEMANTIC:
        valid = (
            payload["mission_integrity"]
            and payload["contract_integrity"]
            and payload["mission_digest"] == payload["contract_spec_digest"]
            and payload["active_phase"] == payload["contract_phase"]
            and payload["enabled_obligation_ids"] == payload["contract_obligation_ids"]
            and payload["contract_target"] == payload["obligation_target"]
            and payload["contract_part"] == payload["obligation_part"]
            and payload["contract_region"] == payload["obligation_region"]
            and payload["issued_at_ns"] <= payload["now_ns"] <= payload["deadline_ns"]
        )
        return WireStaticVerdict.PROVEN if valid else WireStaticVerdict.REFUTED
    if request.stage is WireStage.PREFIX_PRE:
        if payload["semantic_verdict"] != WireStaticVerdict.PROVEN.value:
            return WireStaticVerdict.REFUTED
        bindings = (
            payload["mission_digest"] == payload["contract_spec_digest"]
            and payload["binder_verdict"] == WireStaticVerdict.PROVEN.value
            and payload["state_digest"] == payload["authorization_state_digest"]
            and payload["monitor_digest"] == payload["authorization_monitor_digest"]
            and payload["episode_nonce"] == payload["authorization_nonce"]
            and payload["proposal_index"] == payload["authorization_proposal_index"]
            and payload["proposal_index"] > payload["monitor_last_proposal_index"]
            and payload["proposal_digest"] == payload["authorization_proposal_digest"]
            and payload["command_digest"] == payload["authorization_command_digest"]
            and payload["time_base_digest"] == payload["authorization_time_base_digest"]
            and payload["issued_at_ns"] <= payload["now_ns"]
            and payload["now_ns"] + payload["duration_ns"] <= payload["valid_until_ns"]
        )
        return WireStaticVerdict.PROVEN if bindings else WireStaticVerdict.REFUTED
    if request.stage is WireStage.OBSERVED_PREFIX:
        valid = (
            payload["prefix_verdict"] == WireStaticVerdict.PROVEN.value
            and payload["plant_verdict"] == WireStaticVerdict.PROVEN.value
            and payload["authorization_digest"] == payload["receipt_authorization_digest"]
            and payload["episode_nonce"] == payload["receipt_episode_nonce"]
            and payload["authorized_command_digest"] == payload["dispatched_command_digest"]
            and payload["authorized_command_digest"] == payload["receipt_command_digest"]
            and payload["mission_time_base_digest"] == payload["plant_time_base_digest"]
            and payload["dispatch_ns"] <= payload["observed_ns"]
        )
        return WireStaticVerdict.PROVEN if valid else WireStaticVerdict.REFUTED

    bindings = (
        payload["observed_verdict"] == WireStaticVerdict.PROVEN.value
        and payload["mission_digest"] == payload["contract_spec_digest"]
        and payload["episode_nonce"] == payload["monitor_episode_nonce"]
        and payload["contract_digest"] == payload["monitor_contract_digest"]
        and payload["active_phase"] == payload["monitor_phase"]
        and payload["previous_monitor_digest"] == payload["record_monitor_before_digest"]
        and payload["next_proposal_index"] == payload["record_proposal_index"] + 1
    )
    if not bindings:
        return WireMonitorVerdict.INCONSISTENT
    timestamps = payload["event_timestamps_ns"]
    if timestamps and timestamps[0] <= payload["previous_last_timestamp_ns"]:
        return WireMonitorVerdict.INCONSISTENT
    if any(left >= right for left, right in zip(timestamps, timestamps[1:])):
        return WireMonitorVerdict.INCONSISTENT
    atoms = tuple(payload["previous_observed_atoms"] + payload["current_observed_atoms"])
    invariant = evaluate_temporal_formula(payload["invariant"], atoms, now_ns=payload["now_ns"])
    if invariant is False:
        return WireMonitorVerdict.VIOLATED
    if invariant is None:
        return WireMonitorVerdict.UNKNOWN
    guarantee = evaluate_temporal_formula(payload["guarantee"], atoms, now_ns=payload["now_ns"])
    complete = (
        guarantee is True
        and payload["terminal_phase_event"]
        and payload["completion_witness"]
        and payload["post_evidence"]
        and payload["now_ns"] <= payload["deadline_ns"]
    )
    if complete:
        return WireMonitorVerdict.COMPLETE
    if payload["now_ns"] > payload["deadline_ns"] or guarantee is False:
        return WireMonitorVerdict.VIOLATED
    return WireMonitorVerdict.SAFE_PENDING


def _normalize_payload(stage: WireStage, payload: dict[str, Any]) -> dict[str, Any]:
    _require_exact_fields(payload, _PAYLOAD_FIELDS[stage], f"{stage.value} payload")
    normalized = dict(payload)
    for field in _TEXT_FIELDS & payload.keys():
        if not isinstance(payload[field], str) or not payload[field]:
            raise WireValidationError(f"{field} must be non-empty text")
    for field in _OPTIONAL_TEXT_FIELDS & payload.keys():
        if payload[field] is not None and (
            not isinstance(payload[field], str) or not payload[field]
        ):
            raise WireValidationError(f"{field} must be null or non-empty text")
    for field in _BOOL_FIELDS & payload.keys():
        if type(payload[field]) is not bool:
            raise WireValidationError(f"{field} must be bool")
    for field in _NS_FIELDS & payload.keys():
        minimum = -1 if field == "previous_last_timestamp_ns" else 0
        _require_int(field, payload[field], minimum)
    for field in _INDEX_FIELDS & payload.keys():
        minimum = -1 if field == "monitor_last_proposal_index" else 0
        _require_int(field, payload[field], minimum)
    if "event_timestamps_ns" in payload:
        if not isinstance(payload["event_timestamps_ns"], list):
            raise WireValidationError("event_timestamps_ns must be a list")
        for value in payload["event_timestamps_ns"]:
            _require_nonnegative_int("event_timestamps_ns item", value)
    for field in _SET_LIST_FIELDS & payload.keys():
        value = payload[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise WireValidationError(f"{field} must be a text list")
        normalized[field] = sorted(set(value))
    for field in ("guarantee", "invariant"):
        if field in payload:
            if not isinstance(payload[field], dict):
                raise WireValidationError(f"{field} must be a tagged temporal formula")
            normalized[field] = temporal_formula(payload[field])
    for field in (
        "semantic_verdict",
        "binder_verdict",
        "prefix_verdict",
        "plant_verdict",
        "observed_verdict",
    ):
        if field in payload:
            try:
                WireStaticVerdict(payload[field])
            except (TypeError, ValueError) as exc:
                raise WireValidationError(f"{field} has an unknown verdict") from exc
    _reject_unsupported_json(normalized)
    return normalized


def _request_id(stage: WireStage, checker_digest: str, payload: Mapping[str, Any]) -> str:
    critical = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage.value,
        "time_unit": TIME_UNIT,
        "checker_version_digest": checker_digest,
        "payload": payload,
    }
    return sha256(canonical_wire_bytes(critical)).hexdigest()


def _validate_checker_digest(value: Any) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise WireValidationError("checker_version_digest must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise WireValidationError("checker_version_digest must be hexadecimal") from exc


def _require_exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise WireValidationError(f"{label} fields mismatch; missing={missing}, unknown={unknown}")


def _require_nonnegative_int(name: str, value: Any) -> None:
    _require_int(name, value, 0)


def _require_int(name: str, value: Any, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise WireValidationError(f"{name} must be an integer >= {minimum}")


def _reject_duplicate_object_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise WireValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _raise_nonfinite(value: str) -> Any:
    raise WireValidationError(f"non-finite JSON number is forbidden: {value}")


def _reject_unsupported_json(value: Any) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if isinstance(value, float):
        raise WireValidationError("wire floats are forbidden; use integer nanoseconds and typed atoms")
    if isinstance(value, list):
        for item in value:
            _reject_unsupported_json(item)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise WireValidationError("wire object keys must be text")
        for item in value.values():
            _reject_unsupported_json(item)
        return
    raise WireValidationError(f"unsupported wire value type: {type(value).__name__}")


__all__ = [
    "CTDAWireRequest",
    "SCHEMA_VERSION",
    "TIME_UNIT",
    "WireMonitorVerdict",
    "WireStage",
    "WireStaticVerdict",
    "WireValidationError",
    "canonical_wire_bytes",
    "decode_wire_request",
    "evaluate_temporal_formula",
    "make_wire_request",
    "reference_wire_verdict",
    "temporal_formula",
]
