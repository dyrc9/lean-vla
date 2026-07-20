"""SafeLIBERO CTDA v2 online-evidence wiring without action dispatch.

This module turns already captured, source-bound observations and external
filter results into authenticated CTDA v2 objects.  It deliberately has no
environment, policy, actuator, socket, action, or dispatch method.  The local
exact-allowlist issuer used by tests is simulator TCB only; a deployment must
provide its own authenticated ``CTDAEvidenceIssuer`` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
import re
from typing import Any

from proofalign.ctda import EvidenceAttestation, StaticCheckResult, digest_payload
from proofalign.ctda_runtime import CTDAEvidenceIssuer
from proofalign.ctda_v2 import (
    ActiveContractContextV2,
    ContractLeaseV2,
    CTDAV2ReferenceChecker,
    FilterApplicationV2,
    Intervention,
    PrefixAuthorizationClaimV2,
    PrefixAuthorizationV2,
    PrefixDecisionClaimV2,
    PrefixDecisionV2,
    ProgressBudgetV2,
    ProgressLedgerV2,
    ProgressObservationV2,
    ProgressUpdateResultV2,
    RelevantStateSnapshotV2,
    SafetyEvidenceBundleV2,
    SemanticCertificateV2,
    SnapshotStatus,
)
from proofalign.benchmark.safelibero_open_region import (
    SafeLiberoOpenRegionObservationV2,
    SafeLiberoOpenRegionRuntimeV2,
)


NO_DISPATCH_SCHEMA = "proofalign.safelibero-ctda-v2-no-dispatch-v1"
COMMAND_SCHEMA = "proofalign.safelibero-command-v2"
FILTER_WITNESS_SCHEMA = "proofalign.safelibero-post-filter-witness-v2"
PROGRESS_PACKET_SCHEMA = "proofalign.safelibero-open-region-progress-v2"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class SafeLiberoCommandV2:
    """Canonical seven-dimensional LIBERO delta command."""

    values: tuple[float, ...]
    frame: str = "libero_delta_action"
    schema: str = COMMAND_SCHEMA
    command_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema != COMMAND_SCHEMA or self.frame != "libero_delta_action":
            raise ValueError("unsupported SafeLIBERO command schema or frame")
        if len(self.values) != 7:
            raise ValueError("SafeLIBERO commands must contain exactly seven scalars")
        if any(type(value) not in (int, float) or not isfinite(float(value)) for value in self.values):
            raise ValueError("SafeLIBERO command contains a non-finite or non-numeric scalar")
        normalized = tuple(float(value) for value in self.values)
        object.__setattr__(self, "values", normalized)
        object.__setattr__(self, "command_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {"schema": self.schema, "frame": self.frame, "values": self.values}


@dataclass(frozen=True)
class SafeLiberoPostFilterWitnessV2:
    """Typed output from a filter, before consumer-side CTDA membership."""

    filter_id: str
    filter_version: str
    filter_digest: str
    state_snapshot_digest: str
    safety_bundle_digest: str
    nominal_command_digest: str
    adjusted_command_digest: str
    constraint_ids: tuple[str, ...]
    status: SnapshotStatus
    adjusted_admissible: bool | None
    reason: str
    observed_at_ns: int
    unknown_reason: str | None = None
    schema: str = FILTER_WITNESS_SCHEMA
    witness_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema != FILTER_WITNESS_SCHEMA:
            raise ValueError("unsupported post-filter witness schema")
        for name in ("filter_id", "filter_version", "reason"):
            _require_text(name, getattr(self, name))
        for name in (
            "filter_digest",
            "state_snapshot_digest",
            "safety_bundle_digest",
            "nominal_command_digest",
            "adjusted_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        constraints = tuple(sorted(set(self.constraint_ids)))
        if not constraints or any(not isinstance(item, str) or not item.strip() for item in constraints):
            raise ValueError("post-filter witness requires named constraints")
        if self.observed_at_ns < 0:
            raise ValueError("post-filter witness time must be non-negative")
        if self.status is SnapshotStatus.OBSERVED:
            if type(self.adjusted_admissible) is not bool or self.unknown_reason is not None:
                raise ValueError("observed post-filter witness requires a boolean verdict only")
        elif self.status is SnapshotStatus.UNKNOWN:
            if self.adjusted_admissible is not None or not self.unknown_reason:
                raise ValueError("unknown post-filter witness requires only an unknown reason")
        object.__setattr__(self, "constraint_ids", constraints)
        object.__setattr__(self, "witness_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "filter_id": self.filter_id,
            "filter_version": self.filter_version,
            "filter_digest": self.filter_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "safety_bundle_digest": self.safety_bundle_digest,
            "nominal_command_digest": self.nominal_command_digest,
            "adjusted_command_digest": self.adjusted_command_digest,
            "constraint_ids": self.constraint_ids,
            "status": self.status.value,
            "adjusted_admissible": self.adjusted_admissible,
            "reason": self.reason,
            "observed_at_ns": self.observed_at_ns,
            "unknown_reason": self.unknown_reason,
        }


@dataclass(frozen=True)
class SafeLiberoOpenRegionProgressPacketV2:
    """Source observations, augmented states, and their progress attestation."""

    runtime_digest: str
    before_observation: SafeLiberoOpenRegionObservationV2
    after_observation: SafeLiberoOpenRegionObservationV2
    before_state: RelevantStateSnapshotV2
    after_state: RelevantStateSnapshotV2
    progress: ProgressObservationV2
    schema: str = PROGRESS_PACKET_SCHEMA
    packet_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("runtime_digest", self.runtime_digest)
        if self.schema != PROGRESS_PACKET_SCHEMA:
            raise ValueError("unsupported OpenRegion progress packet schema")
        if (
            self.before_state.status is not SnapshotStatus.OBSERVED
            or self.after_state.status is not SnapshotStatus.OBSERVED
        ):
            raise ValueError("authenticated OpenRegion progress requires observed augmented states")
        claim = self.progress.claim
        if (
            claim.before_snapshot_digest != self.before_state.snapshot_digest
            or claim.after_state.snapshot_digest != self.after_state.snapshot_digest
        ):
            raise ValueError("OpenRegion progress claim is bound to other augmented states")
        object.__setattr__(
            self,
            "packet_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "runtime_digest": self.runtime_digest,
                    "before_observation_digest": self.before_observation.observation_digest,
                    "after_observation_digest": self.after_observation.observation_digest,
                    "before_snapshot_digest": self.before_state.snapshot_digest,
                    "after_snapshot_digest": self.after_state.snapshot_digest,
                    "progress_claim_digest": claim.claim_digest,
                    "progress_attestation_digest": self.progress.progress_attestation.attestation_digest,
                }
            ),
        )


@dataclass(frozen=True)
class SafeLiberoOpenRegionProgressProducerV2:
    """Issue exact-source progress evidence from two captured joint scalars."""

    runtime: SafeLiberoOpenRegionRuntimeV2
    issuer: CTDAEvidenceIssuer
    attestation_valid_for_ns: int
    producer_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.attestation_valid_for_ns <= 0:
            raise ValueError("OpenRegion progress attestation lifetime must be positive")
        object.__setattr__(
            self,
            "producer_digest",
            digest_payload(
                {
                    "schema": PROGRESS_PACKET_SCHEMA,
                    "runtime_digest": self.runtime.runtime_digest,
                    "attestation_valid_for_ns": self.attestation_valid_for_ns,
                }
            ),
        )

    def produce(
        self,
        *,
        certificate_digest: str,
        before_base_state: RelevantStateSnapshotV2,
        after_base_state: RelevantStateSnapshotV2,
        before_joint_position_m: Any,
        after_joint_position_m: Any,
        before_joint_source_id: str,
        after_joint_source_id: str,
        minimum_progress_m: float,
        elapsed_control_epochs: int,
        translation_consumed_m: float,
        motion_consumed: float,
    ) -> SafeLiberoOpenRegionProgressPacketV2:
        if after_base_state.state_epoch <= before_base_state.state_epoch:
            raise ValueError("OpenRegion online progress state epoch must advance")
        if after_base_state.observed_at_ns <= before_base_state.observed_at_ns:
            raise ValueError("OpenRegion online progress observation time must advance")
        before_observation = self.runtime.observe(
            before_joint_position_m,
            joint_source_id=before_joint_source_id,
            episode_nonce=before_base_state.episode_nonce,
            state_epoch=before_base_state.state_epoch,
            observed_at_ns=before_base_state.observed_at_ns,
        )
        after_observation = self.runtime.observe(
            after_joint_position_m,
            joint_source_id=after_joint_source_id,
            episode_nonce=after_base_state.episode_nonce,
            state_epoch=after_base_state.state_epoch,
            observed_at_ns=after_base_state.observed_at_ns,
        )
        if (
            before_observation.status is not SnapshotStatus.OBSERVED
            or after_observation.status is not SnapshotStatus.OBSERVED
        ):
            reasons = tuple(
                item.unknown_reason
                for item in (before_observation, after_observation)
                if item.status is SnapshotStatus.UNKNOWN
            )
            raise ValueError(f"OpenRegion progress source is unknown: {reasons}")
        before_state = self.runtime.augment_snapshot(before_base_state, before_observation)
        after_state = self.runtime.augment_snapshot(after_base_state, after_observation)
        claim = self.runtime.progress_claim(
            before_observation,
            after_observation,
            certificate_digest=certificate_digest,
            before_state=before_state,
            after_state=after_state,
            minimum_progress_m=minimum_progress_m,
            elapsed_control_epochs=elapsed_control_epochs,
            translation_consumed_m=translation_consumed_m,
            motion_consumed=motion_consumed,
        )
        issued_at_ns = after_state.observed_at_ns
        attestation = self.issuer.issue(
            "ctda_v2_progress_observation",
            claim.claim_digest,
            payload={
                "schema": PROGRESS_PACKET_SCHEMA,
                "producer_digest": self.producer_digest,
                "runtime_digest": self.runtime.runtime_digest,
                "binding_digest": self.runtime.binding.binding_digest,
                "before_observation_digest": before_observation.observation_digest,
                "after_observation_digest": after_observation.observation_digest,
                "before_snapshot_digest": before_state.snapshot_digest,
                "after_snapshot_digest": after_state.snapshot_digest,
                "progress_claim": claim.payload(),
            },
            issued_at_ns=issued_at_ns,
            valid_until_ns=issued_at_ns + self.attestation_valid_for_ns,
            assumptions=("simulator-test-tcb-only",),
            producer_id=self.runtime.producer_id,
            producer_version=self.runtime.producer_version,
        )
        progress = ProgressObservationV2(claim, attestation)
        return SafeLiberoOpenRegionProgressPacketV2(
            runtime_digest=self.runtime.runtime_digest,
            before_observation=before_observation,
            after_observation=after_observation,
            before_state=before_state,
            after_state=after_state,
            progress=progress,
        )


@dataclass(frozen=True)
class SafeLiberoNoDispatchTransactionV2:
    """Checked post-filter decision/authorization with no actuator capability."""

    adapter_digest: str
    nominal_command: SafeLiberoCommandV2
    adjusted_command: SafeLiberoCommandV2
    filter_witness: SafeLiberoPostFilterWitnessV2
    decision: PrefixDecisionV2
    decision_check: StaticCheckResult
    authorization: PrefixAuthorizationV2 | None
    authorization_check: StaticCheckResult | None
    schema: str = NO_DISPATCH_SCHEMA
    dispatch_count: int = 0
    formal_rollout_authorized: bool = False
    transaction_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("adapter_digest", self.adapter_digest)
        if self.schema != NO_DISPATCH_SCHEMA:
            raise ValueError("unsupported SafeLIBERO no-dispatch transaction schema")
        if self.dispatch_count != 0 or self.formal_rollout_authorized:
            raise ValueError("no-dispatch transaction cannot authorize or record rollout")
        if (self.authorization is None) != (self.authorization_check is None):
            raise ValueError("authorization and its check must be present together")
        object.__setattr__(
            self,
            "transaction_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "adapter_digest": self.adapter_digest,
                    "nominal_command_digest": self.nominal_command.command_digest,
                    "adjusted_command_digest": self.adjusted_command.command_digest,
                    "filter_witness_digest": self.filter_witness.witness_digest,
                    "decision_digest": self.decision.decision_digest,
                    "decision_verdict": self.decision_check.verdict.value,
                    "authorization_digest": (
                        None if self.authorization is None else self.authorization.authorization_digest
                    ),
                    "authorization_verdict": (
                        None
                        if self.authorization_check is None
                        else self.authorization_check.verdict.value
                    ),
                    "dispatch_count": self.dispatch_count,
                    "formal_rollout_authorized": self.formal_rollout_authorized,
                }
            ),
        )

    @property
    def authorization_ready(self) -> bool:
        return bool(
            self.authorization is not None
            and self.decision_check.proven
            and self.authorization_check is not None
            and self.authorization_check.proven
        )


@dataclass(frozen=True)
class SafeLiberoPostFilterNoDispatchAdapterV2:
    """Bind a typed external filter result to CTDA decision and authorization."""

    checker: CTDAV2ReferenceChecker
    issuer: CTDAEvidenceIssuer
    filter_id: str
    filter_version: str
    filter_digest: str
    max_filter_witness_age_ns: int
    membership_valid_for_ns: int
    authorization_valid_for_ns: int
    adapter_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("filter_id", "filter_version"):
            _require_text(name, getattr(self, name))
        _require_digest("filter_digest", self.filter_digest)
        if (
            self.max_filter_witness_age_ns <= 0
            or self.membership_valid_for_ns <= 0
            or self.authorization_valid_for_ns <= 0
        ):
            raise ValueError("post-filter evidence lifetimes must be positive")
        object.__setattr__(
            self,
            "adapter_digest",
            digest_payload(
                {
                    "schema": NO_DISPATCH_SCHEMA,
                    "checker_id": self.checker.checker_id,
                    "checker_version": self.checker.checker_version,
                    "checker_digest": self.checker.checker_digest,
                    "filter_id": self.filter_id,
                    "filter_version": self.filter_version,
                    "filter_digest": self.filter_digest,
                    "max_filter_witness_age_ns": self.max_filter_witness_age_ns,
                    "membership_valid_for_ns": self.membership_valid_for_ns,
                    "authorization_valid_for_ns": self.authorization_valid_for_ns,
                }
            ),
        )

    def evaluate(
        self,
        *,
        certificate: SemanticCertificateV2,
        lease: ContractLeaseV2,
        context: ActiveContractContextV2,
        safety: SafetyEvidenceBundleV2,
        nominal_command: SafeLiberoCommandV2,
        adjusted_command: SafeLiberoCommandV2,
        filter_witness: SafeLiberoPostFilterWitnessV2,
        proposal_index: int,
        now_ns: int,
    ) -> SafeLiberoNoDispatchTransactionV2:
        witness_valid = (
            filter_witness.filter_id == self.filter_id
            and filter_witness.filter_version == self.filter_version
            and filter_witness.filter_digest == self.filter_digest
            and filter_witness.state_snapshot_digest == lease.claim.activation_state.snapshot_digest
            and filter_witness.safety_bundle_digest == safety.bundle_digest
            and filter_witness.nominal_command_digest == nominal_command.command_digest
            and filter_witness.adjusted_command_digest == adjusted_command.command_digest
            and filter_witness.status is SnapshotStatus.OBSERVED
            and filter_witness.adjusted_admissible is True
            and 0 <= now_ns - filter_witness.observed_at_ns <= self.max_filter_witness_age_ns
        )
        if not witness_valid:
            intervention = Intervention.HARD_BLOCK
            adjusted_digest = None
            application = None
            reason = "post_filter_witness_invalid_or_mismatched"
        elif nominal_command.command_digest == adjusted_command.command_digest:
            intervention = Intervention.PASS
            adjusted_digest = nominal_command.command_digest
            application = None
            reason = "post_filter_nominal_admissible"
        else:
            intervention = Intervention.PROJECT_OR_BRAKE
            adjusted_digest = adjusted_command.command_digest
            application = FilterApplicationV2(
                filter_id=self.filter_id,
                filter_version=self.filter_version,
                filter_digest=self.filter_digest,
                nominal_command_digest=nominal_command.command_digest,
                adjusted_command_digest=adjusted_command.command_digest,
                reason=filter_witness.reason,
                modification_norm=sqrt(
                    sum(
                        (before - after) ** 2
                        for before, after in zip(nominal_command.values, adjusted_command.values)
                    )
                ),
                constraint_witness_digest=filter_witness.witness_digest,
            )
            reason = filter_witness.reason
        claim = PrefixDecisionClaimV2(
            certificate_digest=certificate.certificate_digest,
            lease_digest=lease.lease_digest,
            episode_nonce=context.episode_nonce,
            proposal_index=proposal_index,
            control_epoch=context.control_epoch,
            state_snapshot_digest=lease.claim.activation_state.snapshot_digest,
            safety_bundle_digest=safety.bundle_digest,
            nominal_command_digest=nominal_command.command_digest,
            intervention=intervention,
            adjusted_command_digest=adjusted_digest,
            filter_application=application,
            reason=reason,
        )
        membership: EvidenceAttestation | None = None
        if intervention in (Intervention.PASS, Intervention.PROJECT_OR_BRAKE):
            membership = self.issuer.issue(
                "ctda_v2_command_membership",
                claim.claim_digest,
                payload={
                    "schema": NO_DISPATCH_SCHEMA,
                    "adapter_digest": self.adapter_digest,
                    "decision_claim": claim.payload(),
                    "nominal_command": nominal_command.payload(),
                    "adjusted_command": adjusted_command.payload(),
                    "filter_witness_digest": filter_witness.witness_digest,
                },
                issued_at_ns=now_ns,
                valid_until_ns=now_ns + self.membership_valid_for_ns,
                assumptions=("simulator-test-tcb-only", "no-dispatch"),
                producer_id=self.checker.checker_id,
                producer_version=self.checker.checker_version,
            )
        decision = PrefixDecisionV2(claim, membership)
        decision_check = self.checker.check_decision(
            certificate, lease, context, safety, decision, now_ns=now_ns
        )
        authorization = None
        authorization_check = None
        if decision_check.proven and intervention in (
            Intervention.PASS,
            Intervention.PROJECT_OR_BRAKE,
        ):
            authorization_claim = PrefixAuthorizationClaimV2(
                decision_digest=decision.decision_digest,
                certificate_digest=certificate.certificate_digest,
                lease_digest=lease.lease_digest,
                episode_nonce=context.episode_nonce,
                proposal_index=proposal_index,
                control_epoch=context.control_epoch,
                authorized_command_digest=adjusted_digest or nominal_command.command_digest,
                issued_at_ns=now_ns,
                valid_until_ns=now_ns + self.authorization_valid_for_ns,
            )
            authorization_attestation = self.issuer.issue(
                "ctda_v2_prefix_authorization",
                authorization_claim.claim_digest,
                payload={
                    "schema": NO_DISPATCH_SCHEMA,
                    "adapter_digest": self.adapter_digest,
                    "decision_digest": decision.decision_digest,
                    "authorized_command_digest": authorization_claim.authorized_command_digest,
                    "filter_witness_digest": filter_witness.witness_digest,
                },
                issued_at_ns=now_ns,
                valid_until_ns=now_ns + self.authorization_valid_for_ns,
                assumptions=("simulator-test-tcb-only", "no-dispatch"),
                producer_id=self.checker.checker_id,
                producer_version=self.checker.checker_version,
            )
            authorization = PrefixAuthorizationV2(
                authorization_claim, authorization_attestation
            )
            authorization_check = self.checker.check_authorization(
                certificate,
                lease,
                context,
                safety,
                decision,
                authorization,
                now_ns=now_ns,
            )
        return SafeLiberoNoDispatchTransactionV2(
            adapter_digest=self.adapter_digest,
            nominal_command=nominal_command,
            adjusted_command=adjusted_command,
            filter_witness=filter_witness,
            decision=decision,
            decision_check=decision_check,
            authorization=authorization,
            authorization_check=authorization_check,
        )


@dataclass(frozen=True)
class SafeLiberoRecoveryRecordV2:
    """Progress-ledger recovery transition with no command or dispatch."""

    before_ledger_digest: str
    update: ProgressUpdateResultV2
    resulting_ledger: ProgressLedgerV2
    schema: str = NO_DISPATCH_SCHEMA
    dispatch_count: int = 0
    command_digest: None = None
    formal_rollout_authorized: bool = False
    record_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("before_ledger_digest", self.before_ledger_digest)
        if self.schema != NO_DISPATCH_SCHEMA:
            raise ValueError("unsupported recovery record schema")
        if self.dispatch_count != 0 or self.command_digest is not None or self.formal_rollout_authorized:
            raise ValueError("recovery record cannot contain a command or dispatch")
        object.__setattr__(
            self,
            "record_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "before_ledger_digest": self.before_ledger_digest,
                    "updated_ledger_digest": self.update.ledger.ledger_digest,
                    "resulting_ledger_digest": self.resulting_ledger.ledger_digest,
                    "verdict": self.update.check.verdict.value,
                    "required_intervention": self.update.required_intervention.value,
                    "dispatch_count": self.dispatch_count,
                    "formal_rollout_authorized": self.formal_rollout_authorized,
                }
            ),
        )

    @property
    def terminal(self) -> bool:
        return self.update.required_intervention is Intervention.HARD_BLOCK


@dataclass(frozen=True)
class SafeLiberoRecoveryNoDispatchAdapterV2:
    checker: CTDAV2ReferenceChecker

    def record(
        self,
        ledger: ProgressLedgerV2,
        progress: ProgressObservationV2,
        budget: ProgressBudgetV2,
        *,
        now_ns: int,
    ) -> SafeLiberoRecoveryRecordV2:
        update = self.checker.update_progress(ledger, progress, budget, now_ns=now_ns)
        resulting = update.ledger
        if update.required_intervention is Intervention.REPLAN:
            resulting = resulting.record_replan()
        return SafeLiberoRecoveryRecordV2(
            before_ledger_digest=ledger.ledger_digest,
            update=update,
            resulting_ledger=resulting,
        )
