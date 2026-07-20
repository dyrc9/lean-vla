"""Canonical CTDA v2 wire protocol for no-dispatch kernel replay.

This module is deliberately independent from :mod:`proofalign.ctda_wire`.
There is no v1 compatibility decoder and no default filling: the envelope and
the payload for every stage must contain exactly the frozen v2 fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping

from proofalign.ctda import digest_payload
from proofalign.ctda_v2 import CORE_SCHEMA_VERSION, METHOD_ID, WIRE_SCHEMA_VERSION


class V2WireValidationError(ValueError):
    pass


class V2WireStage(str, Enum):
    SEMANTIC_CERTIFICATE = "semantic_certificate"
    STATE_REBIND = "state_rebind"
    PREFIX_DECISION = "prefix_decision"
    PREFIX_AUTHORIZATION = "prefix_authorization"
    DISPATCH_RECEIPT = "dispatch_receipt"
    PROGRESS_UPDATE = "progress_update"


class V2WireVerdict(str, Enum):
    PROVEN = "proven"
    REFUTED = "refuted"
    REPLAN = "replan"
    HARD_BLOCK = "hard_block"
    INCONSISTENT = "inconsistent"


_ENVELOPE_FIELDS = {
    "schema_version",
    "method_id",
    "request_id",
    "stage",
    "checker_version_digest",
    "payload",
    "payload_digest",
}

_COMMON_PAYLOAD_FIELDS = {"method_id", "schema_version"}

_PAYLOAD_FIELDS: dict[V2WireStage, set[str]] = {
    V2WireStage.SEMANTIC_CERTIFICATE: _COMMON_PAYLOAD_FIELDS
    | {
        "claim_digest",
        "certificate_digest",
        "mission_root_digest",
        "episode_nonce",
        "phase",
        "residual_obligations",
        "contract_version",
        "proof_state_episode_nonce",
        "proof_state_known",
        "proof_state_observed_at_ns",
        "proof_started_at_ns",
        "proof_completed_at_ns",
        "proof_attestation_issued_at_ns",
        "proof_attestation_subject_digest",
        "proof_producer_id",
        "expected_proof_producer_id",
        "proof_producer_version",
        "expected_proof_producer_version",
        "proof_authenticated",
        "fast_checker_digest",
        "expected_fast_checker_digest",
    },
    V2WireStage.STATE_REBIND: _COMMON_PAYLOAD_FIELDS
    | {
        "certificate_verdict",
        "certificate_digest",
        "lease_digest",
        "lease_claim_digest",
        "lease_certificate_digest",
        "certificate_checker_digest",
        "lease_checker_digest",
        "certificate_mission_root_digest",
        "context_mission_root_digest",
        "certificate_episode_nonce",
        "activation_episode_nonce",
        "context_episode_nonce",
        "certificate_phase",
        "context_phase",
        "certificate_residual_obligations",
        "context_residual_obligations",
        "certificate_contract_version",
        "context_contract_version",
        "proof_completed_at_ns",
        "activation_state_known",
        "activation_observed_at_ns",
        "activation_max_sensor_age_ns",
        "activated_at_ns",
        "now_ns",
        "activated_control_epoch",
        "valid_through_control_epoch",
        "context_control_epoch",
        "rebind_attestation_subject_digest",
        "rebind_authenticated",
    },
    V2WireStage.PREFIX_DECISION: _COMMON_PAYLOAD_FIELDS
    | {
        "lease_verdict",
        "certificate_digest",
        "decision_certificate_digest",
        "lease_digest",
        "decision_lease_digest",
        "context_episode_nonce",
        "decision_episode_nonce",
        "context_control_epoch",
        "decision_control_epoch",
        "activation_snapshot_digest",
        "decision_state_snapshot_digest",
        "safety_bundle_digest",
        "decision_safety_bundle_digest",
        "required_safety_channels_complete",
        "safety_unknown",
        "safety_violated",
        "decision_claim_digest",
        "nominal_command_digest",
        "intervention",
        "adjusted_command_digest",
        "filter_application_digest",
        "filter_nominal_command_digest",
        "filter_adjusted_command_digest",
        "membership_attestation_subject_digest",
        "membership_authenticated",
    },
    V2WireStage.PREFIX_AUTHORIZATION: _COMMON_PAYLOAD_FIELDS
    | {
        "decision_verdict",
        "intervention",
        "decision_digest",
        "authorization_decision_digest",
        "certificate_digest",
        "authorization_certificate_digest",
        "lease_digest",
        "authorization_lease_digest",
        "context_episode_nonce",
        "authorization_episode_nonce",
        "decision_proposal_index",
        "authorization_proposal_index",
        "context_control_epoch",
        "authorization_control_epoch",
        "decision_adjusted_command_digest",
        "authorized_command_digest",
        "issued_at_ns",
        "valid_until_ns",
        "now_ns",
        "authorization_claim_digest",
        "authorization_attestation_subject_digest",
        "authorization_authenticated",
        "authorization_unused",
    },
    V2WireStage.DISPATCH_RECEIPT: _COMMON_PAYLOAD_FIELDS
    | {
        "authorization_verdict",
        "authorization_digest",
        "receipt_authorization_digest",
        "authorization_episode_nonce",
        "receipt_episode_nonce",
        "authorization_proposal_index",
        "receipt_proposal_index",
        "authorization_control_epoch",
        "receipt_control_epoch",
        "decision_nominal_command_digest",
        "receipt_nominal_command_digest",
        "authorized_command_digest",
        "executed_command_digest",
        "issued_at_ns",
        "valid_until_ns",
        "dispatched_at_ns",
        "receipt_actuator_subject_digest",
        "expected_actuator_subject_digest",
        "actuator_authenticated",
        "authorization_unused",
    },
    V2WireStage.PROGRESS_UPDATE: _COMMON_PAYLOAD_FIELDS
    | {
        "certificate_digest",
        "ledger_certificate_digest",
        "before_snapshot_digest",
        "ledger_last_snapshot_digest",
        "after_episode_nonce",
        "ledger_episode_nonce",
        "last_state_epoch",
        "after_state_epoch",
        "after_state_known",
        "after_observed_at_ns",
        "after_max_sensor_age_ns",
        "now_ns",
        "progress_claim_digest",
        "progress_attestation_subject_digest",
        "progress_authenticated",
        "distance_before_um",
        "distance_after_um",
        "minimum_progress_um",
        "elapsed_control_epochs",
        "consecutive_nonprogress_control_epochs",
        "max_nonprogress_control_epochs",
        "cumulative_translation_um",
        "translation_consumed_um",
        "translation_budget_um",
        "cumulative_motion_units",
        "motion_consumed_units",
        "motion_budget_units",
    },
}

_DIGEST_FIELDS: dict[V2WireStage, set[str]] = {
    V2WireStage.SEMANTIC_CERTIFICATE: {
        "claim_digest",
        "certificate_digest",
        "mission_root_digest",
        "proof_attestation_subject_digest",
        "fast_checker_digest",
        "expected_fast_checker_digest",
    },
    V2WireStage.STATE_REBIND: {
        "certificate_digest",
        "lease_digest",
        "lease_claim_digest",
        "lease_certificate_digest",
        "certificate_checker_digest",
        "lease_checker_digest",
        "certificate_mission_root_digest",
        "context_mission_root_digest",
        "rebind_attestation_subject_digest",
    },
    V2WireStage.PREFIX_DECISION: {
        "certificate_digest",
        "decision_certificate_digest",
        "lease_digest",
        "decision_lease_digest",
        "activation_snapshot_digest",
        "decision_state_snapshot_digest",
        "safety_bundle_digest",
        "decision_safety_bundle_digest",
        "decision_claim_digest",
        "nominal_command_digest",
    },
    V2WireStage.PREFIX_AUTHORIZATION: {
        "decision_digest",
        "authorization_decision_digest",
        "certificate_digest",
        "authorization_certificate_digest",
        "lease_digest",
        "authorization_lease_digest",
        "authorized_command_digest",
        "authorization_claim_digest",
        "authorization_attestation_subject_digest",
    },
    V2WireStage.DISPATCH_RECEIPT: {
        "authorization_digest",
        "receipt_authorization_digest",
        "decision_nominal_command_digest",
        "receipt_nominal_command_digest",
        "authorized_command_digest",
        "executed_command_digest",
        "receipt_actuator_subject_digest",
        "expected_actuator_subject_digest",
    },
    V2WireStage.PROGRESS_UPDATE: {
        "certificate_digest",
        "ledger_certificate_digest",
        "before_snapshot_digest",
        "ledger_last_snapshot_digest",
        "progress_claim_digest",
        "progress_attestation_subject_digest",
    },
}

_OPTIONAL_DIGEST_FIELDS = {
    "adjusted_command_digest",
    "filter_application_digest",
    "filter_nominal_command_digest",
    "filter_adjusted_command_digest",
    "membership_attestation_subject_digest",
    "decision_adjusted_command_digest",
}

_BOOL_FIELDS = {
    "proof_state_known",
    "proof_authenticated",
    "activation_state_known",
    "rebind_authenticated",
    "required_safety_channels_complete",
    "safety_unknown",
    "safety_violated",
    "membership_authenticated",
    "authorization_authenticated",
    "authorization_unused",
    "actuator_authenticated",
    "after_state_known",
    "progress_authenticated",
}

_NAT_FIELDS = {
    "proof_state_observed_at_ns",
    "proof_started_at_ns",
    "proof_completed_at_ns",
    "proof_attestation_issued_at_ns",
    "activation_observed_at_ns",
    "activation_max_sensor_age_ns",
    "activated_at_ns",
    "now_ns",
    "activated_control_epoch",
    "valid_through_control_epoch",
    "context_control_epoch",
    "decision_control_epoch",
    "decision_proposal_index",
    "authorization_proposal_index",
    "authorization_control_epoch",
    "issued_at_ns",
    "valid_until_ns",
    "receipt_proposal_index",
    "receipt_control_epoch",
    "dispatched_at_ns",
    "last_state_epoch",
    "after_state_epoch",
    "after_observed_at_ns",
    "after_max_sensor_age_ns",
    "minimum_progress_um",
    "elapsed_control_epochs",
    "consecutive_nonprogress_control_epochs",
    "max_nonprogress_control_epochs",
    "cumulative_translation_um",
    "translation_consumed_um",
    "translation_budget_um",
    "cumulative_motion_units",
    "motion_consumed_units",
    "motion_budget_units",
}


@dataclass(frozen=True)
class V2WireEnvelope:
    request_id: str
    stage: V2WireStage
    checker_version_digest: str
    payload: Mapping[str, Any]
    schema_version: str = WIRE_SCHEMA_VERSION
    method_id: str = METHOD_ID

    def __post_init__(self) -> None:
        if self.schema_version != WIRE_SCHEMA_VERSION:
            raise V2WireValidationError("unsupported v2 wire schema_version")
        if self.method_id != METHOD_ID:
            raise V2WireValidationError("unsupported v2 method_id")
        _require_digest("checker_version_digest", self.checker_version_digest)
        normalized = _normalize_payload(self.stage, self.payload)
        object.__setattr__(self, "payload", normalized)
        expected_request_id = _request_id(
            self.stage, self.checker_version_digest, digest_payload(normalized)
        )
        if self.request_id != expected_request_id:
            raise V2WireValidationError("v2 wire request_id does not match canonical payload")

    @property
    def payload_digest(self) -> str:
        return digest_payload(dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "request_id": self.request_id,
            "stage": self.stage.value,
            "checker_version_digest": self.checker_version_digest,
            "payload": dict(self.payload),
            "payload_digest": self.payload_digest,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_v2_wire_bytes(self.to_dict())


def make_v2_wire_envelope(
    stage: V2WireStage | str,
    checker_version_digest: str,
    payload: Mapping[str, Any],
) -> V2WireEnvelope:
    actual_stage = V2WireStage(stage)
    normalized = _normalize_payload(actual_stage, payload)
    _require_digest("checker_version_digest", checker_version_digest)
    payload_digest = digest_payload(normalized)
    return V2WireEnvelope(
        request_id=_request_id(actual_stage, checker_version_digest, payload_digest),
        stage=actual_stage,
        checker_version_digest=checker_version_digest,
        payload=normalized,
    )


def decode_v2_wire_envelope(
    value: str | bytes | Mapping[str, Any],
) -> V2WireEnvelope:
    raw: bytes | None = None
    if isinstance(value, bytes):
        raw = value
        try:
            value = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise V2WireValidationError("v2 wire request is not canonical UTF-8") from exc
    if isinstance(value, str):
        if raw is None:
            raw = value.encode("utf-8")
        try:
            parsed = json.loads(
                value,
                object_pairs_hook=_reject_duplicate_object_keys,
                parse_constant=_raise_nonfinite,
            )
        except json.JSONDecodeError as exc:
            raise V2WireValidationError(f"invalid JSON: {exc}") from exc
    else:
        parsed = value
    if not isinstance(parsed, Mapping):
        raise V2WireValidationError("v2 wire request must be an object")
    _require_exact_fields(parsed, _ENVELOPE_FIELDS, "v2 wire envelope")
    try:
        stage = V2WireStage(parsed["stage"])
    except (TypeError, ValueError) as exc:
        raise V2WireValidationError("unsupported v2 wire stage") from exc
    envelope = V2WireEnvelope(
        schema_version=parsed["schema_version"],
        method_id=parsed["method_id"],
        request_id=parsed["request_id"],
        stage=stage,
        checker_version_digest=parsed["checker_version_digest"],
        payload=parsed["payload"],
    )
    if parsed["payload_digest"] != envelope.payload_digest:
        raise V2WireValidationError("v2 wire payload digest mismatch")
    if raw is not None and raw != envelope.canonical_bytes():
        raise V2WireValidationError("v2 wire request is not canonical JSON")
    return envelope


def reference_v2_wire_verdict(request: V2WireEnvelope) -> V2WireVerdict:
    payload = request.payload
    stage = request.stage
    if stage is V2WireStage.SEMANTIC_CERTIFICATE:
        valid = (
            payload["proof_state_known"]
            and payload["proof_state_episode_nonce"] == payload["episode_nonce"]
            and payload["proof_state_observed_at_ns"] <= payload["proof_started_at_ns"]
            and payload["proof_started_at_ns"] <= payload["proof_completed_at_ns"]
            and payload["proof_attestation_issued_at_ns"] == payload["proof_completed_at_ns"]
            and payload["proof_attestation_subject_digest"] == payload["claim_digest"]
            and payload["proof_producer_id"] == payload["expected_proof_producer_id"]
            and payload["proof_producer_version"] == payload["expected_proof_producer_version"]
            and payload["proof_authenticated"]
            and payload["fast_checker_digest"] == payload["expected_fast_checker_digest"]
        )
        return V2WireVerdict.PROVEN if valid else V2WireVerdict.REFUTED
    if stage is V2WireStage.STATE_REBIND:
        valid = (
            payload["certificate_verdict"] == V2WireVerdict.PROVEN.value
            and payload["certificate_digest"] == payload["lease_certificate_digest"]
            and payload["certificate_checker_digest"] == payload["lease_checker_digest"]
            and payload["certificate_mission_root_digest"] == payload["context_mission_root_digest"]
            and payload["certificate_episode_nonce"] == payload["activation_episode_nonce"]
            and payload["certificate_episode_nonce"] == payload["context_episode_nonce"]
            and payload["certificate_phase"] == payload["context_phase"]
            and payload["certificate_residual_obligations"]
            == payload["context_residual_obligations"]
            and payload["certificate_contract_version"] == payload["context_contract_version"]
            and payload["activation_state_known"]
            and payload["activation_max_sensor_age_ns"] > 0
            and payload["proof_completed_at_ns"] <= payload["activation_observed_at_ns"]
            and payload["activation_observed_at_ns"] <= payload["activated_at_ns"]
            and payload["activated_at_ns"] <= payload["now_ns"]
            and payload["now_ns"]
            <= payload["activation_observed_at_ns"] + payload["activation_max_sensor_age_ns"]
            and payload["activated_control_epoch"] <= payload["context_control_epoch"]
            and payload["context_control_epoch"] <= payload["valid_through_control_epoch"]
            and payload["rebind_attestation_subject_digest"] == payload["lease_claim_digest"]
            and payload["rebind_authenticated"]
        )
        return V2WireVerdict.PROVEN if valid else V2WireVerdict.REFUTED
    if stage is V2WireStage.PREFIX_DECISION:
        return _reference_decision_verdict(payload)
    if stage is V2WireStage.PREFIX_AUTHORIZATION:
        dispatch_capable = payload["intervention"] in {"pass", "project_or_brake"}
        valid = (
            payload["decision_verdict"] == V2WireVerdict.PROVEN.value
            and dispatch_capable
            and payload["decision_digest"] == payload["authorization_decision_digest"]
            and payload["certificate_digest"] == payload["authorization_certificate_digest"]
            and payload["lease_digest"] == payload["authorization_lease_digest"]
            and payload["context_episode_nonce"] == payload["authorization_episode_nonce"]
            and payload["decision_proposal_index"] == payload["authorization_proposal_index"]
            and payload["context_control_epoch"] == payload["authorization_control_epoch"]
            and payload["decision_adjusted_command_digest"]
            == payload["authorized_command_digest"]
            and payload["decision_adjusted_command_digest"] is not None
            and payload["issued_at_ns"] <= payload["now_ns"] <= payload["valid_until_ns"]
            and payload["authorization_attestation_subject_digest"]
            == payload["authorization_claim_digest"]
            and payload["authorization_authenticated"]
            and payload["authorization_unused"]
        )
        return V2WireVerdict.PROVEN if valid else V2WireVerdict.REFUTED
    if stage is V2WireStage.DISPATCH_RECEIPT:
        valid = (
            payload["authorization_verdict"] == V2WireVerdict.PROVEN.value
            and payload["authorization_unused"]
            and payload["authorization_digest"] == payload["receipt_authorization_digest"]
            and payload["authorization_episode_nonce"] == payload["receipt_episode_nonce"]
            and payload["authorization_proposal_index"] == payload["receipt_proposal_index"]
            and payload["authorization_control_epoch"] == payload["receipt_control_epoch"]
            and payload["decision_nominal_command_digest"]
            == payload["receipt_nominal_command_digest"]
            and payload["authorized_command_digest"] == payload["executed_command_digest"]
            and payload["issued_at_ns"] <= payload["dispatched_at_ns"] <= payload["valid_until_ns"]
            and payload["receipt_actuator_subject_digest"]
            == payload["expected_actuator_subject_digest"]
            and payload["actuator_authenticated"]
        )
        return V2WireVerdict.PROVEN if valid else V2WireVerdict.REFUTED
    return _reference_progress_verdict(payload)


def _reference_decision_verdict(payload: Mapping[str, Any]) -> V2WireVerdict:
    common = (
        payload["lease_verdict"] == V2WireVerdict.PROVEN.value
        and payload["certificate_digest"] == payload["decision_certificate_digest"]
        and payload["lease_digest"] == payload["decision_lease_digest"]
        and payload["context_episode_nonce"] == payload["decision_episode_nonce"]
        and payload["context_control_epoch"] == payload["decision_control_epoch"]
        and payload["activation_snapshot_digest"] == payload["decision_state_snapshot_digest"]
        and payload["safety_bundle_digest"] == payload["decision_safety_bundle_digest"]
        and payload["required_safety_channels_complete"]
    )
    intervention = payload["intervention"]
    if intervention == "pass":
        binding = (
            payload["adjusted_command_digest"] == payload["nominal_command_digest"]
            and payload["filter_application_digest"] is None
            and payload["filter_nominal_command_digest"] is None
            and payload["filter_adjusted_command_digest"] is None
            and payload["membership_attestation_subject_digest"]
            == payload["decision_claim_digest"]
            and payload["membership_authenticated"]
        )
    elif intervention == "project_or_brake":
        binding = (
            payload["adjusted_command_digest"] is not None
            and payload["adjusted_command_digest"] != payload["nominal_command_digest"]
            and payload["filter_application_digest"] is not None
            and payload["filter_nominal_command_digest"] == payload["nominal_command_digest"]
            and payload["filter_adjusted_command_digest"] == payload["adjusted_command_digest"]
            and payload["membership_attestation_subject_digest"]
            == payload["decision_claim_digest"]
            and payload["membership_authenticated"]
        )
    else:
        binding = (
            payload["adjusted_command_digest"] is None
            and payload["filter_application_digest"] is None
            and payload["filter_nominal_command_digest"] is None
            and payload["filter_adjusted_command_digest"] is None
            and payload["membership_attestation_subject_digest"] is None
            and not payload["membership_authenticated"]
        )
    safety = (
        (not payload["safety_unknown"] or intervention in {"replan", "hard_block"})
        and (not payload["safety_violated"] or intervention == "hard_block")
    )
    return V2WireVerdict.PROVEN if common and binding and safety else V2WireVerdict.REFUTED


def _reference_progress_verdict(payload: Mapping[str, Any]) -> V2WireVerdict:
    binding = (
        payload["certificate_digest"] == payload["ledger_certificate_digest"]
        and payload["before_snapshot_digest"] == payload["ledger_last_snapshot_digest"]
        and payload["after_episode_nonce"] == payload["ledger_episode_nonce"]
        and payload["after_state_epoch"] > payload["last_state_epoch"]
        and payload["after_state_known"]
        and payload["after_observed_at_ns"] <= payload["now_ns"]
        and payload["now_ns"]
        <= payload["after_observed_at_ns"] + payload["after_max_sensor_age_ns"]
        and payload["progress_attestation_subject_digest"] == payload["progress_claim_digest"]
        and payload["progress_authenticated"]
        and payload["minimum_progress_um"] > 0
        and payload["elapsed_control_epochs"] > 0
    )
    before = payload["distance_before_um"]
    after = payload["distance_after_um"]
    if not binding or (before is None) != (after is None):
        return V2WireVerdict.HARD_BLOCK
    translation = payload["cumulative_translation_um"] + payload["translation_consumed_um"]
    motion = payload["cumulative_motion_units"] + payload["motion_consumed_units"]
    if before is not None and before >= after + payload["minimum_progress_um"]:
        nonprogress = 0
        verdict = V2WireVerdict.PROVEN
    elif before is not None:
        nonprogress = (
            payload["consecutive_nonprogress_control_epochs"]
            + payload["elapsed_control_epochs"]
        )
        verdict = V2WireVerdict.REPLAN
    else:
        nonprogress = payload["consecutive_nonprogress_control_epochs"]
        verdict = V2WireVerdict.REPLAN
    if (
        translation > payload["translation_budget_um"]
        or motion > payload["motion_budget_units"]
        or nonprogress > payload["max_nonprogress_control_epochs"]
    ):
        return V2WireVerdict.HARD_BLOCK
    return verdict


def canonical_v2_wire_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise V2WireValidationError("v2 wire value is not canonical JSON") from exc


def _normalize_payload(stage: V2WireStage, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise V2WireValidationError("payload must be an object")
    normalized = dict(payload)
    _require_exact_fields(normalized, _PAYLOAD_FIELDS[stage], f"{stage.value} payload")
    if normalized["method_id"] != METHOD_ID:
        raise V2WireValidationError("payload method_id is missing or not ctda-v2")
    if normalized["schema_version"] != CORE_SCHEMA_VERSION:
        raise V2WireValidationError("payload schema_version is not proofalign.ctda-core-v2")
    for name in _DIGEST_FIELDS[stage]:
        _require_digest(name, normalized[name])
    for name in _OPTIONAL_DIGEST_FIELDS & set(normalized):
        if normalized[name] is not None:
            _require_digest(name, normalized[name])
    for name in _BOOL_FIELDS & set(normalized):
        if type(normalized[name]) is not bool:
            raise V2WireValidationError(f"{name} must be Boolean")
    for name in _NAT_FIELDS & set(normalized):
        _require_nat(name, normalized[name])
    for name in {"distance_before_um", "distance_after_um"} & set(normalized):
        if normalized[name] is not None:
            _require_nat(name, normalized[name])
    for name in _text_fields(stage):
        _require_text(name, normalized[name])
    for name in _residual_fields(stage):
        values = normalized[name]
        if not isinstance(values, list) or not values or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise V2WireValidationError(f"{name} must be a non-empty string list")
        normalized[name] = sorted(set(values))
    for name in _verdict_fields(stage):
        if normalized[name] != V2WireVerdict.PROVEN.value:
            if normalized[name] not in {item.value for item in V2WireVerdict}:
                raise V2WireValidationError(f"{name} has an unsupported verdict")
    if "intervention" in normalized and normalized["intervention"] not in {
        "pass",
        "project_or_brake",
        "replan",
        "hard_block",
    }:
        raise V2WireValidationError("unsupported v2 intervention")
    return normalized


def _text_fields(stage: V2WireStage) -> set[str]:
    fields = {
        V2WireStage.SEMANTIC_CERTIFICATE: {
            "episode_nonce",
            "phase",
            "contract_version",
            "proof_state_episode_nonce",
            "proof_producer_id",
            "expected_proof_producer_id",
            "proof_producer_version",
            "expected_proof_producer_version",
        },
        V2WireStage.STATE_REBIND: {
            "certificate_episode_nonce",
            "activation_episode_nonce",
            "context_episode_nonce",
            "certificate_phase",
            "context_phase",
            "certificate_contract_version",
            "context_contract_version",
        },
        V2WireStage.PREFIX_DECISION: {"context_episode_nonce", "decision_episode_nonce"},
        V2WireStage.PREFIX_AUTHORIZATION: {
            "context_episode_nonce",
            "authorization_episode_nonce",
        },
        V2WireStage.DISPATCH_RECEIPT: {
            "authorization_episode_nonce",
            "receipt_episode_nonce",
        },
        V2WireStage.PROGRESS_UPDATE: {"after_episode_nonce", "ledger_episode_nonce"},
    }
    return fields[stage]


def _residual_fields(stage: V2WireStage) -> set[str]:
    if stage is V2WireStage.SEMANTIC_CERTIFICATE:
        return {"residual_obligations"}
    if stage is V2WireStage.STATE_REBIND:
        return {"certificate_residual_obligations", "context_residual_obligations"}
    return set()


def _verdict_fields(stage: V2WireStage) -> set[str]:
    return {
        V2WireStage.STATE_REBIND: {"certificate_verdict"},
        V2WireStage.PREFIX_DECISION: {"lease_verdict"},
        V2WireStage.PREFIX_AUTHORIZATION: {"decision_verdict"},
        V2WireStage.DISPATCH_RECEIPT: {"authorization_verdict"},
    }.get(stage, set())


def _request_id(stage: V2WireStage, checker_version_digest: str, payload_digest: str) -> str:
    return sha256(
        canonical_v2_wire_bytes(
            {
                "schema_version": WIRE_SCHEMA_VERSION,
                "method_id": METHOD_ID,
                "stage": stage.value,
                "checker_version_digest": checker_version_digest,
                "payload_digest": payload_digest,
            }
        )
    ).hexdigest()


def _require_exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    fields = set(value)
    if fields != expected:
        missing = sorted(expected - fields)
        extra = sorted(fields - expected)
        raise V2WireValidationError(f"{label} fields mismatch: missing={missing}, extra={extra}")


def _require_text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise V2WireValidationError(f"{name} must be a non-empty string")


def _require_digest(name: str, value: Any) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise V2WireValidationError(f"{name} must be a lowercase SHA-256 digest")


def _require_nat(name: str, value: Any) -> None:
    if type(value) is not int or value < 0:
        raise V2WireValidationError(f"{name} must be a non-negative integer")


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise V2WireValidationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _raise_nonfinite(value: str) -> None:
    raise V2WireValidationError(f"non-finite JSON number is forbidden: {value}")


__all__ = [
    "V2WireEnvelope",
    "V2WireStage",
    "V2WireValidationError",
    "V2WireVerdict",
    "canonical_v2_wire_bytes",
    "decode_v2_wire_envelope",
    "make_v2_wire_envelope",
    "reference_v2_wire_verdict",
]
