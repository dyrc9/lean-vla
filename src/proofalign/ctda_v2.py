"""CTDA v2 no-dispatch core and fail-closed reference checker.

CTDA v1 remains the frozen evaluated method.  This module deliberately uses new
method and schema identifiers and does not deserialize or mutate v1 artifacts.

The v2 lifetime split is explicit:

* a Lean-authenticated semantic certificate is produced from a frozen mission,
  phase, residual-obligation set, and proof-state snapshot;
* after proof completion the plant is observed again and a pinned fast checker
  authenticates a short state rebind lease;
* certificate lifetime is measured in plant/control epochs, while each rebind,
  command authorization, and receipt retains a wall-clock freshness bound.

This is an executable schema/reference checker, not a claim that the v2 Lean
authority, physical filter, or closed-loop experiment is already complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Iterable

from proofalign.ctda import (
    EvidenceAttestation,
    EvidenceVerifier,
    StaticCheckResult,
    digest_payload,
)


METHOD_ID = "ctda-v2"
CORE_SCHEMA_VERSION = "proofalign.ctda-core-v2"
WIRE_SCHEMA_VERSION = "ctda-wire-v2"
TIME_UNIT = "ns"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _require_nonnegative_finite(name: str, value: float) -> None:
    if type(value) not in (int, float) or not isfinite(float(value)) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")


def _result(issues: Iterable[str] = ()) -> StaticCheckResult:
    retained = tuple(issues)
    return StaticCheckResult.success(METHOD_ID) if not retained else StaticCheckResult.refuted(*retained)


def _attestation_issue(
    verifier: EvidenceVerifier | None,
    attestation: EvidenceAttestation | None,
    *,
    evidence_type: str,
    subject_digest: str,
    now_ns: int,
    producer_id: str | None = None,
    producer_version: str | None = None,
) -> str | None:
    if attestation is None:
        return f"missing typed {evidence_type} attestation"
    if not isinstance(attestation, EvidenceAttestation) or not attestation.verify_integrity():
        return f"invalid {evidence_type} attestation integrity"
    if attestation.evidence_type != evidence_type:
        return f"attestation type {attestation.evidence_type!r} is not {evidence_type!r}"
    if attestation.subject_digest != subject_digest:
        return f"{evidence_type} attestation is bound to another subject"
    if not attestation.is_fresh(now_ns):
        return f"{evidence_type} attestation is stale or not yet valid"
    if producer_id is not None and attestation.producer_id != producer_id:
        return f"{evidence_type} attestation has an unexpected producer"
    if producer_version is not None and attestation.producer_version != producer_version:
        return f"{evidence_type} attestation has an unexpected producer version"
    if verifier is None or not verifier.verify(attestation):
        return f"{evidence_type} attestation is not authenticated by the configured verifier"
    return None


class SnapshotStatus(str, Enum):
    OBSERVED = "observed"
    UNKNOWN = "unknown"


class Intervention(str, Enum):
    PASS = "pass"
    PROJECT_OR_BRAKE = "project_or_brake"
    REPLAN = "replan"
    HARD_BLOCK = "hard_block"


@dataclass(frozen=True)
class RelevantStateSnapshotV2:
    """Relevant state with explicit observer provenance and freshness."""

    episode_nonce: str
    state_epoch: int
    observed_at_ns: int
    producer_id: str
    producer_version: str
    provenance_digest: str
    max_sensor_age_ns: int
    status: SnapshotStatus
    state_digest: str | None = None
    unknown_reason: str | None = None
    schema_version: str = CORE_SCHEMA_VERSION
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("episode_nonce", "producer_id", "producer_version", "schema_version"):
            _require_text(name, getattr(self, name))
        _require_digest("provenance_digest", self.provenance_digest)
        if self.state_epoch < 0 or self.observed_at_ns < 0 or self.max_sensor_age_ns <= 0:
            raise ValueError("snapshot epoch/time must be non-negative and sensor age positive")
        if self.status is SnapshotStatus.OBSERVED:
            if self.state_digest is None:
                raise ValueError("observed snapshot requires a state digest")
            _require_digest("state_digest", self.state_digest)
            if self.unknown_reason is not None:
                raise ValueError("observed snapshot cannot carry an unknown reason")
        elif self.status is SnapshotStatus.UNKNOWN:
            if self.state_digest is not None:
                raise ValueError("unknown snapshot cannot carry a state digest")
            _require_text("unknown_reason", self.unknown_reason or "")
        else:  # pragma: no cover
            raise ValueError("unsupported snapshot status")
        object.__setattr__(self, "snapshot_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_nonce": self.episode_nonce,
            "state_epoch": self.state_epoch,
            "observed_at_ns": self.observed_at_ns,
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "provenance_digest": self.provenance_digest,
            "max_sensor_age_ns": self.max_sensor_age_ns,
            "status": self.status.value,
            "state_digest": self.state_digest,
            "unknown_reason": self.unknown_reason,
        }

    def freshness_issue(self, now_ns: int) -> str | None:
        if self.status is SnapshotStatus.UNKNOWN:
            return f"relevant state is unknown: {self.unknown_reason}"
        if now_ns < self.observed_at_ns:
            return "relevant state observation is from the future"
        if now_ns - self.observed_at_ns > self.max_sensor_age_ns:
            return "relevant state observation exceeds max sensor age"
        return None


@dataclass(frozen=True)
class ActiveContractContextV2:
    mission_root_digest: str
    episode_nonce: str
    phase: str
    residual_obligations: tuple[str, ...]
    contract_version: str
    control_epoch: int

    def __post_init__(self) -> None:
        _require_digest("mission_root_digest", self.mission_root_digest)
        for name in ("episode_nonce", "phase", "contract_version"):
            _require_text(name, getattr(self, name))
        if self.control_epoch < 0:
            raise ValueError("control_epoch must be non-negative")
        frozen = tuple(sorted(set(self.residual_obligations)))
        if not frozen or any(not item.strip() for item in frozen):
            raise ValueError("residual_obligations must be non-empty strings")
        object.__setattr__(self, "residual_obligations", frozen)


@dataclass(frozen=True)
class SemanticCertificateClaimV2:
    mission_root_digest: str
    episode_nonce: str
    phase: str
    residual_obligations: tuple[str, ...]
    contract_version: str
    proof_state: RelevantStateSnapshotV2
    action_set_digest: str
    checker_id: str
    checker_version: str
    checker_digest: str
    lean_proof_artifact_digest: str
    proof_started_at_ns: int
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    claim_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("certificate claim uses an unsupported CTDA version")
        _require_digest("mission_root_digest", self.mission_root_digest)
        for name in (
            "episode_nonce",
            "phase",
            "contract_version",
            "checker_id",
            "checker_version",
        ):
            _require_text(name, getattr(self, name))
        for name in ("action_set_digest", "checker_digest", "lean_proof_artifact_digest"):
            _require_digest(name, getattr(self, name))
        if self.proof_started_at_ns < self.proof_state.observed_at_ns:
            raise ValueError("proof cannot start before its state observation")
        frozen = tuple(sorted(set(self.residual_obligations)))
        if not frozen or any(not item.strip() for item in frozen):
            raise ValueError("certificate requires residual obligations")
        object.__setattr__(self, "residual_obligations", frozen)
        object.__setattr__(self, "claim_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "mission_root_digest": self.mission_root_digest,
            "episode_nonce": self.episode_nonce,
            "phase": self.phase,
            "residual_obligations": self.residual_obligations,
            "contract_version": self.contract_version,
            "proof_state_digest": self.proof_state.snapshot_digest,
            "action_set_digest": self.action_set_digest,
            "checker_id": self.checker_id,
            "checker_version": self.checker_version,
            "checker_digest": self.checker_digest,
            "lean_proof_artifact_digest": self.lean_proof_artifact_digest,
            "proof_started_at_ns": self.proof_started_at_ns,
        }


@dataclass(frozen=True)
class SemanticCertificateV2:
    claim: SemanticCertificateClaimV2
    proof_completed_at_ns: int
    proof_attestation: EvidenceAttestation
    certificate_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.proof_completed_at_ns < self.claim.proof_started_at_ns:
            raise ValueError("proof completion predates proof start")
        object.__setattr__(
            self,
            "certificate_digest",
            digest_payload(
                {
                    "claim_digest": self.claim.claim_digest,
                    "proof_completed_at_ns": self.proof_completed_at_ns,
                    "proof_attestation_digest": self.proof_attestation.attestation_digest,
                }
            ),
        )


@dataclass(frozen=True)
class ContractLeaseClaimV2:
    certificate_digest: str
    activation_state: RelevantStateSnapshotV2
    checker_digest: str
    activated_at_ns: int
    activated_control_epoch: int
    valid_through_control_epoch: int
    previous_lease_digest: str | None = None
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    claim_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("lease claim uses an unsupported CTDA version")
        _require_digest("certificate_digest", self.certificate_digest)
        _require_digest("checker_digest", self.checker_digest)
        if self.previous_lease_digest is not None:
            _require_digest("previous_lease_digest", self.previous_lease_digest)
        if self.activated_at_ns < self.activation_state.observed_at_ns:
            raise ValueError("lease activation predates its state observation")
        if self.activated_control_epoch < 0:
            raise ValueError("activated_control_epoch must be non-negative")
        if self.valid_through_control_epoch < self.activated_control_epoch:
            raise ValueError("lease control-epoch window is empty")
        object.__setattr__(self, "claim_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "certificate_digest": self.certificate_digest,
            "activation_state_digest": self.activation_state.snapshot_digest,
            "checker_digest": self.checker_digest,
            "activated_at_ns": self.activated_at_ns,
            "activated_control_epoch": self.activated_control_epoch,
            "valid_through_control_epoch": self.valid_through_control_epoch,
            "previous_lease_digest": self.previous_lease_digest,
        }


@dataclass(frozen=True)
class ContractLeaseV2:
    claim: ContractLeaseClaimV2
    rebind_attestation: EvidenceAttestation
    lease_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lease_digest",
            digest_payload(
                {
                    "claim_digest": self.claim.claim_digest,
                    "rebind_attestation_digest": self.rebind_attestation.attestation_digest,
                }
            ),
        )


@dataclass(frozen=True)
class SafetyChannelEvidenceV2:
    channel: str
    status: SnapshotStatus
    producer_id: str
    producer_version: str
    unit: str
    source_ids: tuple[str, ...]
    observed_at_ns: int
    state_epoch: int
    state_digest: str
    violation: bool | None = None
    value: Any = None
    unknown_reason: str | None = None
    schema_version: str = CORE_SCHEMA_VERSION
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("channel", "producer_id", "producer_version", "unit", "schema_version"):
            _require_text(name, getattr(self, name))
        _require_digest("state_digest", self.state_digest)
        if self.observed_at_ns < 0 or self.state_epoch < 0:
            raise ValueError("safety evidence time and epoch must be non-negative")
        sources = tuple(sorted(set(self.source_ids)))
        if self.status is SnapshotStatus.OBSERVED:
            if not sources:
                raise ValueError("observed safety evidence requires source ids")
            if type(self.violation) is not bool:
                raise TypeError("observed safety evidence requires a Boolean violation")
            if self.unknown_reason is not None:
                raise ValueError("observed safety evidence cannot carry an unknown reason")
            digest_payload(self.value)
        elif self.status is SnapshotStatus.UNKNOWN:
            if self.violation is not None or self.value is not None:
                raise ValueError("unknown safety evidence cannot carry a value or violation")
            _require_text("unknown_reason", self.unknown_reason or "")
        object.__setattr__(self, "source_ids", sources)
        object.__setattr__(self, "evidence_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "channel": self.channel,
            "status": self.status.value,
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "unit": self.unit,
            "source_ids": self.source_ids,
            "observed_at_ns": self.observed_at_ns,
            "state_epoch": self.state_epoch,
            "state_digest": self.state_digest,
            "violation": self.violation,
            "value": self.value,
            "unknown_reason": self.unknown_reason,
        }


@dataclass(frozen=True)
class SafetyEvidenceBundleV2:
    episode_nonce: str
    state_epoch: int
    state_digest: str
    required_channels: tuple[str, ...]
    observations: tuple[SafetyChannelEvidenceV2, ...]
    bundle_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("episode_nonce", self.episode_nonce)
        _require_digest("state_digest", self.state_digest)
        if self.state_epoch < 0:
            raise ValueError("state_epoch must be non-negative")
        required = tuple(sorted(set(self.required_channels)))
        if not required:
            raise ValueError("at least one required safety channel must be frozen")
        observed_channels = tuple(item.channel for item in self.observations)
        if len(set(observed_channels)) != len(observed_channels):
            raise ValueError("safety bundle contains duplicate channels")
        if not set(required).issubset(observed_channels):
            raise ValueError("safety bundle omits a required channel")
        if any(
            item.state_epoch != self.state_epoch or item.state_digest != self.state_digest
            for item in self.observations
        ):
            raise ValueError("safety evidence is bound to another state")
        object.__setattr__(self, "required_channels", required)
        object.__setattr__(self, "observations", tuple(sorted(self.observations, key=lambda x: x.channel)))
        object.__setattr__(
            self,
            "bundle_digest",
            digest_payload(
                {
                    "episode_nonce": self.episode_nonce,
                    "state_epoch": self.state_epoch,
                    "state_digest": self.state_digest,
                    "required_channels": required,
                    "observation_digests": tuple(
                        item.evidence_digest for item in sorted(self.observations, key=lambda x: x.channel)
                    ),
                }
            ),
        )

    @property
    def unknown_channels(self) -> tuple[str, ...]:
        return tuple(item.channel for item in self.observations if item.status is SnapshotStatus.UNKNOWN)

    @property
    def violated_channels(self) -> tuple[str, ...]:
        return tuple(item.channel for item in self.observations if item.violation is True)


@dataclass(frozen=True)
class FilterApplicationV2:
    filter_id: str
    filter_version: str
    filter_digest: str
    nominal_command_digest: str
    adjusted_command_digest: str
    reason: str
    modification_norm: float
    constraint_witness_digest: str
    application_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("filter_id", "filter_version", "reason"):
            _require_text(name, getattr(self, name))
        for name in (
            "filter_digest",
            "nominal_command_digest",
            "adjusted_command_digest",
            "constraint_witness_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_nonnegative_finite("modification_norm", self.modification_norm)
        if self.adjusted_command_digest == self.nominal_command_digest:
            raise ValueError("project_or_brake must materially distinguish the adjusted command")
        object.__setattr__(self, "application_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "filter_version": self.filter_version,
            "filter_digest": self.filter_digest,
            "nominal_command_digest": self.nominal_command_digest,
            "adjusted_command_digest": self.adjusted_command_digest,
            "reason": self.reason,
            "modification_norm": self.modification_norm,
            "constraint_witness_digest": self.constraint_witness_digest,
        }


@dataclass(frozen=True)
class PrefixDecisionClaimV2:
    certificate_digest: str
    lease_digest: str
    episode_nonce: str
    proposal_index: int
    control_epoch: int
    state_snapshot_digest: str
    safety_bundle_digest: str
    nominal_command_digest: str
    intervention: Intervention
    adjusted_command_digest: str | None = None
    filter_application: FilterApplicationV2 | None = None
    reason: str = "nominal_admissible"
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    claim_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("prefix decision uses an unsupported CTDA version")
        for name in (
            "certificate_digest",
            "lease_digest",
            "state_snapshot_digest",
            "safety_bundle_digest",
            "nominal_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("episode_nonce", self.episode_nonce)
        _require_text("reason", self.reason)
        if self.proposal_index < 0 or self.control_epoch < 0:
            raise ValueError("proposal_index and control_epoch must be non-negative")
        if self.intervention is Intervention.PASS:
            if self.adjusted_command_digest != self.nominal_command_digest:
                raise ValueError("pass must preserve the nominal command digest exactly")
            if self.filter_application is not None:
                raise ValueError("pass cannot carry a filter application")
        elif self.intervention is Intervention.PROJECT_OR_BRAKE:
            if self.adjusted_command_digest is None or self.filter_application is None:
                raise ValueError("project_or_brake requires adjusted command and filter evidence")
            _require_digest("adjusted_command_digest", self.adjusted_command_digest)
            if (
                self.filter_application.nominal_command_digest != self.nominal_command_digest
                or self.filter_application.adjusted_command_digest != self.adjusted_command_digest
            ):
                raise ValueError("filter application command binding mismatch")
        elif self.intervention in (Intervention.REPLAN, Intervention.HARD_BLOCK):
            if self.adjusted_command_digest is not None or self.filter_application is not None:
                raise ValueError("non-dispatch decisions cannot carry an adjusted command")
        object.__setattr__(self, "claim_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "certificate_digest": self.certificate_digest,
            "lease_digest": self.lease_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "control_epoch": self.control_epoch,
            "state_snapshot_digest": self.state_snapshot_digest,
            "safety_bundle_digest": self.safety_bundle_digest,
            "nominal_command_digest": self.nominal_command_digest,
            "intervention": self.intervention.value,
            "adjusted_command_digest": self.adjusted_command_digest,
            "filter_application_digest": (
                None if self.filter_application is None else self.filter_application.application_digest
            ),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PrefixDecisionV2:
    claim: PrefixDecisionClaimV2
    membership_attestation: EvidenceAttestation | None = None
    decision_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.claim.intervention in (Intervention.PASS, Intervention.PROJECT_OR_BRAKE):
            if self.membership_attestation is None:
                raise ValueError("dispatch-capable decision requires post-filter membership evidence")
        elif self.membership_attestation is not None:
            raise ValueError("non-dispatch decision cannot carry command membership evidence")
        object.__setattr__(
            self,
            "decision_digest",
            digest_payload(
                {
                    "claim_digest": self.claim.claim_digest,
                    "membership_attestation_digest": (
                        None
                        if self.membership_attestation is None
                        else self.membership_attestation.attestation_digest
                    ),
                }
            ),
        )


@dataclass(frozen=True)
class PrefixAuthorizationClaimV2:
    decision_digest: str
    certificate_digest: str
    lease_digest: str
    episode_nonce: str
    proposal_index: int
    control_epoch: int
    authorized_command_digest: str
    issued_at_ns: int
    valid_until_ns: int
    claim_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "decision_digest",
            "certificate_digest",
            "lease_digest",
            "authorized_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("episode_nonce", self.episode_nonce)
        if self.proposal_index < 0 or self.control_epoch < 0:
            raise ValueError("authorization indices must be non-negative")
        if self.issued_at_ns < 0 or self.valid_until_ns <= self.issued_at_ns:
            raise ValueError("authorization wall-clock window is empty")
        object.__setattr__(self, "claim_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "decision_digest": self.decision_digest,
            "certificate_digest": self.certificate_digest,
            "lease_digest": self.lease_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "control_epoch": self.control_epoch,
            "authorized_command_digest": self.authorized_command_digest,
            "issued_at_ns": self.issued_at_ns,
            "valid_until_ns": self.valid_until_ns,
        }


@dataclass(frozen=True)
class PrefixAuthorizationV2:
    claim: PrefixAuthorizationClaimV2
    authorization_attestation: EvidenceAttestation
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authorization_digest",
            digest_payload(
                {
                    "claim_digest": self.claim.claim_digest,
                    "authorization_attestation_digest": self.authorization_attestation.attestation_digest,
                }
            ),
        )


@dataclass(frozen=True)
class DispatchReceiptV2:
    authorization_digest: str
    episode_nonce: str
    proposal_index: int
    control_epoch: int
    nominal_command_digest: str
    executed_command_digest: str
    dispatched_at_ns: int
    actuator_attestation: EvidenceAttestation
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "authorization_digest",
            "nominal_command_digest",
            "executed_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("episode_nonce", self.episode_nonce)
        if self.proposal_index < 0 or self.control_epoch < 0 or self.dispatched_at_ns < 0:
            raise ValueError("receipt indices/time must be non-negative")
        object.__setattr__(
            self,
            "receipt_digest",
            digest_payload(
                {
                    "authorization_digest": self.authorization_digest,
                    "episode_nonce": self.episode_nonce,
                    "proposal_index": self.proposal_index,
                    "control_epoch": self.control_epoch,
                    "nominal_command_digest": self.nominal_command_digest,
                    "executed_command_digest": self.executed_command_digest,
                    "dispatched_at_ns": self.dispatched_at_ns,
                    "actuator_attestation_digest": self.actuator_attestation.attestation_digest,
                }
            ),
        )

    @property
    def actuator_subject_digest(self) -> str:
        return digest_payload(
            {
                "authorization_digest": self.authorization_digest,
                "episode_nonce": self.episode_nonce,
                "proposal_index": self.proposal_index,
                "control_epoch": self.control_epoch,
                "executed_command_digest": self.executed_command_digest,
                "dispatched_at_ns": self.dispatched_at_ns,
            }
        )


@dataclass(frozen=True)
class ProgressBudgetV2:
    max_nonprogress_control_epochs: int
    cumulative_translation_budget_m: float
    cumulative_motion_budget: float
    budget_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.max_nonprogress_control_epochs <= 0:
            raise ValueError("max_nonprogress_control_epochs must be positive")
        _require_nonnegative_finite(
            "cumulative_translation_budget_m", self.cumulative_translation_budget_m
        )
        _require_nonnegative_finite("cumulative_motion_budget", self.cumulative_motion_budget)
        if self.cumulative_translation_budget_m == 0 or self.cumulative_motion_budget == 0:
            raise ValueError("progress cumulative budgets must be positive")
        object.__setattr__(
            self,
            "budget_digest",
            digest_payload(
                {
                    "max_nonprogress_control_epochs": self.max_nonprogress_control_epochs,
                    "cumulative_translation_budget_m": self.cumulative_translation_budget_m,
                    "cumulative_motion_budget": self.cumulative_motion_budget,
                }
            ),
        )


@dataclass(frozen=True)
class ProgressObservationClaimV2:
    certificate_digest: str
    before_snapshot_digest: str
    after_state: RelevantStateSnapshotV2
    distance_before_m: float | None
    distance_after_m: float | None
    minimum_progress_m: float
    elapsed_control_epochs: int
    translation_consumed_m: float
    motion_consumed: float
    claim_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("certificate_digest", self.certificate_digest)
        _require_digest("before_snapshot_digest", self.before_snapshot_digest)
        _require_nonnegative_finite("minimum_progress_m", self.minimum_progress_m)
        _require_nonnegative_finite("translation_consumed_m", self.translation_consumed_m)
        _require_nonnegative_finite("motion_consumed", self.motion_consumed)
        if self.minimum_progress_m <= 0 or self.elapsed_control_epochs <= 0:
            raise ValueError("progress threshold and elapsed control epochs must be positive")
        if (self.distance_before_m is None) != (self.distance_after_m is None):
            raise ValueError("progress distances must both be observed or both unknown")
        if self.distance_before_m is not None:
            _require_nonnegative_finite("distance_before_m", self.distance_before_m)
            _require_nonnegative_finite("distance_after_m", self.distance_after_m or 0.0)
        object.__setattr__(self, "claim_digest", digest_payload(self.payload()))

    @property
    def progress_known(self) -> bool:
        return self.distance_before_m is not None and self.distance_after_m is not None

    @property
    def made_progress(self) -> bool:
        return bool(
            self.progress_known
            and float(self.distance_before_m) - float(self.distance_after_m)
            >= self.minimum_progress_m
        )

    def payload(self) -> dict[str, Any]:
        return {
            "certificate_digest": self.certificate_digest,
            "before_snapshot_digest": self.before_snapshot_digest,
            "after_snapshot_digest": self.after_state.snapshot_digest,
            "distance_before_m": self.distance_before_m,
            "distance_after_m": self.distance_after_m,
            "minimum_progress_m": self.minimum_progress_m,
            "elapsed_control_epochs": self.elapsed_control_epochs,
            "translation_consumed_m": self.translation_consumed_m,
            "motion_consumed": self.motion_consumed,
        }


@dataclass(frozen=True)
class ProgressObservationV2:
    claim: ProgressObservationClaimV2
    progress_attestation: EvidenceAttestation


@dataclass(frozen=True)
class ProgressLedgerV2:
    certificate_digest: str
    episode_nonce: str
    last_state: RelevantStateSnapshotV2
    revision: int = 0
    progress_epoch: int = 0
    consecutive_nonprogress_control_epochs: int = 0
    cumulative_translation_m: float = 0.0
    cumulative_motion: float = 0.0
    replan_count: int = 0
    ledger_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("certificate_digest", self.certificate_digest)
        _require_text("episode_nonce", self.episode_nonce)
        if any(
            value < 0
            for value in (
                self.revision,
                self.progress_epoch,
                self.consecutive_nonprogress_control_epochs,
                self.replan_count,
            )
        ):
            raise ValueError("progress ledger counters must be non-negative")
        _require_nonnegative_finite("cumulative_translation_m", self.cumulative_translation_m)
        _require_nonnegative_finite("cumulative_motion", self.cumulative_motion)
        object.__setattr__(
            self,
            "ledger_digest",
            digest_payload(
                {
                    "certificate_digest": self.certificate_digest,
                    "episode_nonce": self.episode_nonce,
                    "last_state_digest": self.last_state.snapshot_digest,
                    "revision": self.revision,
                    "progress_epoch": self.progress_epoch,
                    "consecutive_nonprogress_control_epochs": self.consecutive_nonprogress_control_epochs,
                    "cumulative_translation_m": self.cumulative_translation_m,
                    "cumulative_motion": self.cumulative_motion,
                    "replan_count": self.replan_count,
                }
            ),
        )

    def record_replan(self) -> "ProgressLedgerV2":
        """Record a replan without refunding motion or manufacturing progress."""

        return ProgressLedgerV2(
            certificate_digest=self.certificate_digest,
            episode_nonce=self.episode_nonce,
            last_state=self.last_state,
            revision=self.revision + 1,
            progress_epoch=self.progress_epoch,
            consecutive_nonprogress_control_epochs=self.consecutive_nonprogress_control_epochs,
            cumulative_translation_m=self.cumulative_translation_m,
            cumulative_motion=self.cumulative_motion,
            replan_count=self.replan_count + 1,
        )


@dataclass(frozen=True)
class ProgressUpdateResultV2:
    check: StaticCheckResult
    ledger: ProgressLedgerV2
    required_intervention: Intervention


class CTDAV2ReferenceChecker:
    """Fail-closed consumer-side checker for the no-dispatch v2 core."""

    def __init__(
        self,
        *,
        evidence_verifier: EvidenceVerifier | None,
        checker_id: str,
        checker_version: str,
        checker_digest: str,
        lean_producer_id: str,
        lean_producer_version: str,
    ) -> None:
        for name in ("checker_id", "checker_version", "lean_producer_id", "lean_producer_version"):
            _require_text(name, getattr(self, name, None) or locals()[name])
        _require_digest("checker_digest", checker_digest)
        self.evidence_verifier = evidence_verifier
        self.checker_id = checker_id
        self.checker_version = checker_version
        self.checker_digest = checker_digest
        self.lean_producer_id = lean_producer_id
        self.lean_producer_version = lean_producer_version
        self._consumed_authorizations: set[str] = set()

    def check_certificate(self, certificate: SemanticCertificateV2, *, now_ns: int) -> StaticCheckResult:
        claim = certificate.claim
        issues: list[str] = []
        if claim.checker_id != self.checker_id or claim.checker_version != self.checker_version:
            issues.append("certificate fast-checker identity mismatch")
        if claim.checker_digest != self.checker_digest:
            issues.append("certificate fast-checker digest mismatch")
        if claim.proof_state.status is SnapshotStatus.UNKNOWN:
            issues.append("certificate proof state is unknown")
        if certificate.proof_attestation.issued_at_ns != certificate.proof_completed_at_ns:
            issues.append("Lean proof attestation time does not equal proof completion time")
        issue = _attestation_issue(
            self.evidence_verifier,
            certificate.proof_attestation,
            evidence_type="ctda_v2_semantic_certificate",
            subject_digest=claim.claim_digest,
            now_ns=now_ns,
            producer_id=self.lean_producer_id,
            producer_version=self.lean_producer_version,
        )
        if issue is not None:
            issues.append(issue)
        return _result(issues)

    def check_lease(
        self,
        certificate: SemanticCertificateV2,
        lease: ContractLeaseV2,
        context: ActiveContractContextV2,
        *,
        now_ns: int,
    ) -> StaticCheckResult:
        certificate_check = self.check_certificate(certificate, now_ns=now_ns)
        if not certificate_check.proven:
            return certificate_check
        claim = certificate.claim
        lease_claim = lease.claim
        state = lease_claim.activation_state
        issues: list[str] = []
        if claim.mission_root_digest != context.mission_root_digest:
            issues.append("active mission root differs from certificate")
        if claim.episode_nonce != context.episode_nonce or state.episode_nonce != context.episode_nonce:
            issues.append("cross-episode certificate or state rebind")
        if claim.phase != context.phase:
            issues.append("active phase differs from certificate")
        if claim.residual_obligations != context.residual_obligations:
            issues.append("residual obligations changed after certificate proof")
        if claim.contract_version != context.contract_version:
            issues.append("contract version changed after certificate proof")
        if lease_claim.certificate_digest != certificate.certificate_digest:
            issues.append("lease is bound to another semantic certificate")
        if lease_claim.checker_digest != self.checker_digest:
            issues.append("lease rebind checker digest mismatch")
        if state.observed_at_ns < certificate.proof_completed_at_ns:
            issues.append("lease did not re-observe state after proof completion")
        freshness_issue = state.freshness_issue(now_ns)
        if freshness_issue is not None:
            issues.append(freshness_issue)
        if now_ns < lease_claim.activated_at_ns:
            issues.append("lease is not yet active")
        if not (
            lease_claim.activated_control_epoch
            <= context.control_epoch
            <= lease_claim.valid_through_control_epoch
        ):
            issues.append("contract lease is outside its plant/control epoch window")
        issue = _attestation_issue(
            self.evidence_verifier,
            lease.rebind_attestation,
            evidence_type="ctda_v2_state_rebind",
            subject_digest=lease_claim.claim_digest,
            now_ns=now_ns,
            producer_id=self.checker_id,
            producer_version=self.checker_version,
        )
        if issue is not None:
            issues.append(issue)
        return _result(issues)

    def check_decision(
        self,
        certificate: SemanticCertificateV2,
        lease: ContractLeaseV2,
        context: ActiveContractContextV2,
        safety: SafetyEvidenceBundleV2,
        decision: PrefixDecisionV2,
        *,
        now_ns: int,
    ) -> StaticCheckResult:
        lease_check = self.check_lease(certificate, lease, context, now_ns=now_ns)
        if not lease_check.proven:
            return lease_check
        claim = decision.claim
        issues: list[str] = []
        if claim.certificate_digest != certificate.certificate_digest:
            issues.append("prefix decision is bound to another certificate")
        if claim.lease_digest != lease.lease_digest:
            issues.append("prefix decision is bound to another state lease")
        if claim.episode_nonce != context.episode_nonce or safety.episode_nonce != context.episode_nonce:
            issues.append("cross-episode prefix decision")
        if claim.control_epoch != context.control_epoch:
            issues.append("prefix decision control epoch mismatch")
        state = lease.claim.activation_state
        if claim.state_snapshot_digest != state.snapshot_digest:
            issues.append("prefix decision uses a stale relevant-state snapshot")
        if safety.state_epoch != state.state_epoch or safety.state_digest != state.state_digest:
            issues.append("safety evidence is bound to another relevant state")
        if claim.safety_bundle_digest != safety.bundle_digest:
            issues.append("prefix decision safety bundle digest mismatch")
        if safety.unknown_channels and claim.intervention not in (
            Intervention.REPLAN,
            Intervention.HARD_BLOCK,
        ):
            issues.append("unknown safety provenance cannot authorize dispatch")
        if safety.violated_channels and claim.intervention is not Intervention.HARD_BLOCK:
            issues.append("observed safety violation requires hard_block")
        if claim.intervention in (Intervention.PASS, Intervention.PROJECT_OR_BRAKE):
            issue = _attestation_issue(
                self.evidence_verifier,
                decision.membership_attestation,
                evidence_type="ctda_v2_command_membership",
                subject_digest=claim.claim_digest,
                now_ns=now_ns,
                producer_id=self.checker_id,
                producer_version=self.checker_version,
            )
            if issue is not None:
                issues.append(issue)
        return _result(issues)

    def check_authorization(
        self,
        certificate: SemanticCertificateV2,
        lease: ContractLeaseV2,
        context: ActiveContractContextV2,
        safety: SafetyEvidenceBundleV2,
        decision: PrefixDecisionV2,
        authorization: PrefixAuthorizationV2,
        *,
        now_ns: int,
    ) -> StaticCheckResult:
        decision_check = self.check_decision(
            certificate, lease, context, safety, decision, now_ns=now_ns
        )
        if not decision_check.proven:
            return decision_check
        if decision.claim.intervention not in (Intervention.PASS, Intervention.PROJECT_OR_BRAKE):
            return StaticCheckResult.refuted("non-dispatch decision cannot receive authorization")
        claim = authorization.claim
        expected_command = decision.claim.adjusted_command_digest
        issues: list[str] = []
        if claim.decision_digest != decision.decision_digest:
            issues.append("authorization is bound to another intervention decision")
        if claim.certificate_digest != certificate.certificate_digest or claim.lease_digest != lease.lease_digest:
            issues.append("authorization certificate or lease binding mismatch")
        if claim.episode_nonce != context.episode_nonce:
            issues.append("cross-episode authorization")
        if claim.proposal_index != decision.claim.proposal_index:
            issues.append("authorization proposal index mismatch")
        if claim.control_epoch != context.control_epoch:
            issues.append("authorization control epoch mismatch")
        if claim.authorized_command_digest != expected_command:
            issues.append("authorization is not bound to the post-filter command")
        if not (claim.issued_at_ns <= now_ns <= claim.valid_until_ns):
            issues.append("authorization wall-clock window is stale or not yet valid")
        issue = _attestation_issue(
            self.evidence_verifier,
            authorization.authorization_attestation,
            evidence_type="ctda_v2_prefix_authorization",
            subject_digest=claim.claim_digest,
            now_ns=now_ns,
            producer_id=self.checker_id,
            producer_version=self.checker_version,
        )
        if issue is not None:
            issues.append(issue)
        return _result(issues)

    def check_and_consume_receipt(
        self,
        authorization: PrefixAuthorizationV2,
        decision: PrefixDecisionV2,
        receipt: DispatchReceiptV2,
    ) -> StaticCheckResult:
        claim = authorization.claim
        issues: list[str] = []
        if authorization.authorization_digest in self._consumed_authorizations:
            issues.append("authorization replay: a receipt already consumed this authorization")
        if receipt.authorization_digest != authorization.authorization_digest:
            issues.append("receipt is bound to another authorization")
        if receipt.episode_nonce != claim.episode_nonce:
            issues.append("cross-episode execution receipt")
        if receipt.proposal_index != claim.proposal_index or receipt.control_epoch != claim.control_epoch:
            issues.append("receipt proposal or control epoch mismatch")
        if receipt.nominal_command_digest != decision.claim.nominal_command_digest:
            issues.append("receipt lost the nominal command binding")
        if receipt.executed_command_digest != claim.authorized_command_digest:
            issues.append("receipt executed command differs from post-filter authorization")
        if not (claim.issued_at_ns <= receipt.dispatched_at_ns <= claim.valid_until_ns):
            issues.append("dispatch occurred outside the authorization wall-clock window")
        issue = _attestation_issue(
            self.evidence_verifier,
            receipt.actuator_attestation,
            evidence_type="ctda_v2_actuator_receipt",
            subject_digest=receipt.actuator_subject_digest,
            now_ns=receipt.dispatched_at_ns,
        )
        if issue is not None:
            issues.append(issue)
        result = _result(issues)
        if result.proven:
            self._consumed_authorizations.add(authorization.authorization_digest)
        return result

    def update_progress(
        self,
        ledger: ProgressLedgerV2,
        observation: ProgressObservationV2,
        budget: ProgressBudgetV2,
        *,
        now_ns: int,
    ) -> ProgressUpdateResultV2:
        claim = observation.claim
        issues: list[str] = []
        if claim.certificate_digest != ledger.certificate_digest:
            issues.append("progress observation is bound to another certificate")
        if claim.before_snapshot_digest != ledger.last_state.snapshot_digest:
            issues.append("progress observation does not extend the persistent ledger")
        if claim.after_state.episode_nonce != ledger.episode_nonce:
            issues.append("cross-episode progress observation")
        if claim.after_state.state_epoch <= ledger.last_state.state_epoch:
            issues.append("progress state epoch did not advance")
        freshness_issue = claim.after_state.freshness_issue(now_ns)
        if freshness_issue is not None:
            issues.append(freshness_issue)
        issue = _attestation_issue(
            self.evidence_verifier,
            observation.progress_attestation,
            evidence_type="ctda_v2_progress_observation",
            subject_digest=claim.claim_digest,
            now_ns=now_ns,
        )
        if issue is not None:
            issues.append(issue)
        if issues:
            return ProgressUpdateResultV2(
                StaticCheckResult.refuted(*issues), ledger, Intervention.HARD_BLOCK
            )

        translation = ledger.cumulative_translation_m + claim.translation_consumed_m
        motion = ledger.cumulative_motion + claim.motion_consumed
        if claim.progress_known and claim.made_progress:
            progress_epoch = ledger.progress_epoch + 1
            nonprogress_epochs = 0
            intervention = Intervention.PASS
        elif claim.progress_known:
            progress_epoch = ledger.progress_epoch
            nonprogress_epochs = (
                ledger.consecutive_nonprogress_control_epochs + claim.elapsed_control_epochs
            )
            intervention = Intervention.REPLAN
        else:
            progress_epoch = ledger.progress_epoch
            nonprogress_epochs = ledger.consecutive_nonprogress_control_epochs
            intervention = Intervention.REPLAN

        updated = ProgressLedgerV2(
            certificate_digest=ledger.certificate_digest,
            episode_nonce=ledger.episode_nonce,
            last_state=claim.after_state,
            revision=ledger.revision + 1,
            progress_epoch=progress_epoch,
            consecutive_nonprogress_control_epochs=nonprogress_epochs,
            cumulative_translation_m=translation,
            cumulative_motion=motion,
            replan_count=ledger.replan_count,
        )
        exhausted: list[str] = []
        if translation > budget.cumulative_translation_budget_m:
            exhausted.append("persistent cumulative translation budget is exhausted")
        if motion > budget.cumulative_motion_budget:
            exhausted.append("persistent cumulative motion budget is exhausted")
        if nonprogress_epochs > budget.max_nonprogress_control_epochs:
            exhausted.append("authenticated non-progress control-epoch window is exhausted")
        if exhausted:
            return ProgressUpdateResultV2(
                StaticCheckResult.refuted(*exhausted), updated, Intervention.HARD_BLOCK
            )
        if not claim.progress_known:
            return ProgressUpdateResultV2(
                StaticCheckResult.refuted("progress provenance is unknown"),
                updated,
                Intervention.REPLAN,
            )
        return ProgressUpdateResultV2(StaticCheckResult.success(METHOD_ID), updated, intervention)

