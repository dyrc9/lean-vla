"""Runtime integration helpers for CTDA.

The implementation provides a deliberately small conditional kinematic
assurance adapter for LIBERO-style delta-action chunks.  Its guarantee is only
as strong as the configured action scaling, observed clearance, and explicitly
trusted fallback assumptions; those assumptions are bound into the generated witness
digests instead of being hidden behind a Boolean certificate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite, sqrt
import time
from typing import Any, Protocol, Sequence

from proofalign.ctda import (
    AbstractionLink,
    ActionProposalBinding,
    CTDAChecker,
    CTDASupervisor,
    ContractExecution,
    DigestAllowlistEvidenceVerifier,
    EvidenceAttestation,
    EvidenceVerifier,
    ExecutionReceipt,
    MonitorCheckResult,
    MonitorVerdict,
    PlantSample,
    PlantTrace,
    PrefixAuthorization,
    PrefixCandidate,
    PrefixExecutionRecord,
    ReachableTube,
    SemanticSkillContract,
    StaticCheckResult,
    SymbolicEvent,
    SymbolicEventTrace,
    TraceAbstractionEvidence,
    advance_monitor_state,
    bind_mission_authority,
    contract_from_legacy_action,
    digest_legacy_action,
    digest_legacy_state,
    digest_payload,
    digest_text,
    filter_envelope_subject_digest,
    guard_subject_digest,
    mission_from_legacy,
    proposal_contract_subject_digest,
)


class CTDAEvidenceIssuer(Protocol):
    """Explicit trust boundary used to issue typed CTDA evidence.

    Production implementations should back ``verifier`` with signatures or
    proof checking. Runtime code never treats a digest or producer id alone as
    authentication.
    """

    @property
    def verifier(self) -> EvidenceVerifier:
        ...

    @property
    def producer_id(self) -> str:
        ...

    @property
    def producer_version(self) -> str:
        ...

    def issue(
        self,
        evidence_type: str,
        subject_digest: str,
        *,
        payload: Any,
        issued_at_ns: int,
        valid_until_ns: int,
        assumptions: Sequence[str] = (),
        producer_id: str | None = None,
        producer_version: str | None = None,
    ) -> EvidenceAttestation:
        ...


@dataclass
class ExactAllowlistEvidenceIssuer:
    """SIMULATOR/TEST TCB ONLY: locally issue and exactly allowlist evidence.

    Possession of this object is authority to attest arbitrary claims. It is
    useful for deterministic simulator integration tests, not a production
    authenticity mechanism.
    """

    producer_id: str = "proofalign-local-simulator-test-tcb"
    producer_version: str = "1"
    _verifier: DigestAllowlistEvidenceVerifier = field(
        default_factory=DigestAllowlistEvidenceVerifier,
        init=False,
        repr=False,
    )

    @property
    def verifier(self) -> EvidenceVerifier:
        return self._verifier

    def issue(
        self,
        evidence_type: str,
        subject_digest: str,
        *,
        payload: Any,
        issued_at_ns: int,
        valid_until_ns: int,
        assumptions: Sequence[str] = (),
        producer_id: str | None = None,
        producer_version: str | None = None,
    ) -> EvidenceAttestation:
        actual_producer = producer_id or self.producer_id
        actual_version = producer_version or self.producer_version
        payload_digest = digest_payload(payload)
        attestation = EvidenceAttestation(
            evidence_type=evidence_type,
            subject_digest=subject_digest,
            producer_id=actual_producer,
            producer_version=actual_version,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            payload_digest=payload_digest,
            proof_digest=digest_payload(
                {
                    "tcb": "local-exact-allowlist-simulator-test-only",
                    "evidence_type": evidence_type,
                    "subject_digest": subject_digest,
                    "producer_id": actual_producer,
                    "producer_version": actual_version,
                    "payload_digest": payload_digest,
                    "issued_at_ns": issued_at_ns,
                    "valid_until_ns": valid_until_ns,
                    "assumptions": tuple(assumptions),
                }
            ),
            assumptions=tuple(assumptions),
        )
        self._verifier.trust(attestation)
        return attestation


LocalEvidenceIssuer = ExactAllowlistEvidenceIssuer


@dataclass(frozen=True)
class ConditionalKinematicConfig:
    control_period_ns: int = 20_000_000
    contract_budget_ns: int = 2_000_000_000
    authorization_slack_ns: int = 20_000_000
    max_command_abs: float = 1.0
    translation_scale_m: float = 0.05
    dynamics_model_id: str = "libero-delta-kinematic-v1"
    filter_policy_id: str = "identity-filter-v1"
    fallback_id: str = "hold"
    fallback_witness_digest: str = ""
    fallback_verified: bool = False
    fallback_action: tuple[float, ...] = ()
    evidence_validity_ns: int = 3_600_000_000_000
    semantic_evidence: tuple[str, ...] = ("semantic_requirement",)
    physical_evidence: tuple[str, ...] = ("physical_requirement",)
    runtime_evidence: tuple[str, ...] = ("runtime_requirement",)
    post_evidence: tuple[str, ...] = ("post_requirement",)

    def __post_init__(self) -> None:
        if self.control_period_ns <= 0 or self.contract_budget_ns <= 0:
            raise ValueError("runtime periods and budgets must be positive")
        if self.authorization_slack_ns < 0:
            raise ValueError("authorization slack must be non-negative")
        if self.evidence_validity_ns <= 0:
            raise ValueError("evidence validity must be positive")
        if not isfinite(self.max_command_abs) or self.max_command_abs <= 0:
            raise ValueError("max_command_abs must be finite and positive")
        if not isfinite(self.translation_scale_m) or self.translation_scale_m < 0:
            raise ValueError("translation_scale_m must be finite and non-negative")
        if self.fallback_verified and not self.fallback_witness_digest:
            raise ValueError("an enabled fallback requires a witness digest")
        object.__setattr__(self, "fallback_action", tuple(self.fallback_action))
        if self.fallback_verified and not self.fallback_action:
            raise ValueError("an enabled fallback requires an executable fallback_action")
        if any(
            type(value) not in (int, float) or not isfinite(float(value))
            for value in self.fallback_action
        ):
            raise ValueError("fallback_action must contain only finite numbers")
        if any(abs(float(value)) > self.max_command_abs for value in self.fallback_action):
            raise ValueError("fallback_action exceeds the configured command envelope")
        if self.fallback_verified and any(
            float(value) != 0.0 for value in self.fallback_action[:-1]
        ):
            raise ValueError(
                "enabled hold fallback may only command the bounded gripper channel"
            )


@dataclass(frozen=True)
class PreparedPrefix:
    candidate: PrefixCandidate
    authorized_actions: tuple[Any, ...]
    symbolic_action: Any
    before_state: Any
    state_digest: str
    start_ns: int


@dataclass(frozen=True)
class PrepareResult:
    check: StaticCheckResult
    prepared: PreparedPrefix | None = None


@dataclass(frozen=True)
class FallbackPostconditionEvaluation:
    """Typed, fail-closed evaluation of the observed fallback post-state."""

    observation_complete: bool
    mission_invariants_hold: bool
    distance_thresholds_hold: bool
    no_collision: bool | None
    no_cost: bool | None
    human_clearance_m: float | None
    obstacle_clearance_m: float | None
    required_margin_m: float
    checked_invariants: tuple[str, ...]
    issues: tuple[str, ...] = ()
    evaluation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "observation_complete",
            "mission_invariants_hold",
            "distance_thresholds_hold",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if self.no_collision is not None and type(self.no_collision) is not bool:
            raise TypeError("no_collision must be bool or None")
        if self.no_cost is not None and type(self.no_cost) is not bool:
            raise TypeError("no_cost must be bool or None")
        for name in ("human_clearance_m", "obstacle_clearance_m"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} must be a finite non-negative value or None")
        if not isfinite(self.required_margin_m) or self.required_margin_m < 0:
            raise ValueError("required fallback margin must be finite and non-negative")
        object.__setattr__(self, "checked_invariants", tuple(self.checked_invariants))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(
            self,
            "evaluation_digest",
            digest_payload(
                {
                    "observation_complete": self.observation_complete,
                    "mission_invariants_hold": self.mission_invariants_hold,
                    "distance_thresholds_hold": self.distance_thresholds_hold,
                    "no_collision": self.no_collision,
                    "no_cost": self.no_cost,
                    "human_clearance_m": self.human_clearance_m,
                    "obstacle_clearance_m": self.obstacle_clearance_m,
                    "required_margin_m": self.required_margin_m,
                    "checked_invariants": self.checked_invariants,
                    "issues": self.issues,
                }
            ),
        )

    @property
    def proven(self) -> bool:
        return (
            self.observation_complete
            and self.mission_invariants_hold
            and self.distance_thresholds_hold
            and self.no_collision is True
            and self.no_cost is True
            and not self.issues
        )


def _fallback_actuation_subject_digest(
    episode_nonce: str,
    fallback_id: str,
    command_digest: str,
    dispatched_at_ns: int,
) -> str:
    return digest_payload(
        {
            "episode_nonce": episode_nonce,
            "fallback_id": fallback_id,
            "requested_command_digest": command_digest,
            "dispatched_at_ns": dispatched_at_ns,
        }
    )


@dataclass(frozen=True)
class FallbackSwitchReceipt:
    episode_nonce: str
    fallback_id: str
    trigger: str
    state_before_digest: str
    state_after_digest: str
    requested_command_digest: str
    command_application: str
    applied_command_digest: str | None
    actuator_attestation: EvidenceAttestation | None
    postcondition: FallbackPostconditionEvaluation
    triggered_at_ns: int
    requested_at_ns: int
    dispatched_at_ns: int
    observed_at_ns: int
    switch_latency_bound_ns: int
    active_contract_digest: str | None = None
    pending_authorization_digest: str | None = None
    active_execution_digest: str | None = None
    monitor_state_digest: str | None = None
    attestation: EvidenceAttestation | None = None
    claim_digest: str = field(init=False)
    receipt_digest: str = field(init=False)
    succeeded: bool = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "episode_nonce",
            "fallback_id",
            "trigger",
            "state_before_digest",
            "state_after_digest",
            "requested_command_digest",
            "command_application",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not (
            0
            <= self.triggered_at_ns
            <= self.requested_at_ns
            <= self.dispatched_at_ns
            <= self.observed_at_ns
        ):
            raise ValueError("fallback switch timestamps are not monotonic")
        if self.switch_latency_bound_ns < 0:
            raise ValueError("fallback switch latency bound must be non-negative")
        if not isinstance(self.postcondition, FallbackPostconditionEvaluation):
            raise TypeError("fallback postcondition must be a typed evaluation")
        if self.command_application not in {"requested_only", "typed_simulator_applied"}:
            raise ValueError("unsupported fallback command application status")
        applied = self.command_application == "typed_simulator_applied"
        if applied != (self.applied_command_digest is not None):
            raise ValueError("applied-command digest does not match its application status")
        if applied and self.applied_command_digest != self.requested_command_digest:
            raise ValueError("applied fallback command differs from the requested command")
        actuation_structurally_bound = bool(
            applied
            and self.actuator_attestation is not None
            and self.actuator_attestation.verify_integrity()
            and self.actuator_attestation.evidence_type == "fallback_actuator_applied"
            and self.dispatched_at_ns
            <= self.actuator_attestation.issued_at_ns
            <= self.observed_at_ns
            and self.actuator_attestation.valid_until_ns >= self.observed_at_ns
            and "simulator_env_step_applies_requested_command"
            in self.actuator_attestation.assumptions
            and self.actuator_attestation.subject_digest
            == _fallback_actuation_subject_digest(
                self.episode_nonce,
                self.fallback_id,
                self.requested_command_digest,
                self.dispatched_at_ns,
            )
        )
        within_latency = (
            self.observed_at_ns - self.triggered_at_ns <= self.switch_latency_bound_ns
        )
        object.__setattr__(
            self,
            "succeeded",
            bool(actuation_structurally_bound and within_latency and self.postcondition.proven),
        )
        claim = {
            "episode_nonce": self.episode_nonce,
            "fallback_id": self.fallback_id,
            "trigger": self.trigger,
            "state_before_digest": self.state_before_digest,
            "state_after_digest": self.state_after_digest,
            "requested_command_digest": self.requested_command_digest,
            "command_application": self.command_application,
            "applied_command_digest": self.applied_command_digest,
            "actuator_attestation": self.actuator_attestation,
            "postcondition": self.postcondition,
            "triggered_at_ns": self.triggered_at_ns,
            "requested_at_ns": self.requested_at_ns,
            "dispatched_at_ns": self.dispatched_at_ns,
            "observed_at_ns": self.observed_at_ns,
            "switch_latency_bound_ns": self.switch_latency_bound_ns,
            "active_contract_digest": self.active_contract_digest,
            "pending_authorization_digest": self.pending_authorization_digest,
            "active_execution_digest": self.active_execution_digest,
            "monitor_state_digest": self.monitor_state_digest,
            "succeeded": self.succeeded,
        }
        object.__setattr__(self, "claim_digest", digest_payload(claim))
        object.__setattr__(
            self,
            "receipt_digest",
            digest_payload({**claim, "attestation": self.attestation}),
        )

    def verify_integrity(self) -> bool:
        claim = {
            "episode_nonce": self.episode_nonce,
            "fallback_id": self.fallback_id,
            "trigger": self.trigger,
            "state_before_digest": self.state_before_digest,
            "state_after_digest": self.state_after_digest,
            "requested_command_digest": self.requested_command_digest,
            "command_application": self.command_application,
            "applied_command_digest": self.applied_command_digest,
            "actuator_attestation": self.actuator_attestation,
            "postcondition": self.postcondition,
            "triggered_at_ns": self.triggered_at_ns,
            "requested_at_ns": self.requested_at_ns,
            "dispatched_at_ns": self.dispatched_at_ns,
            "observed_at_ns": self.observed_at_ns,
            "switch_latency_bound_ns": self.switch_latency_bound_ns,
            "active_contract_digest": self.active_contract_digest,
            "pending_authorization_digest": self.pending_authorization_digest,
            "active_execution_digest": self.active_execution_digest,
            "monitor_state_digest": self.monitor_state_digest,
            "succeeded": self.succeeded,
        }
        actuation_structurally_bound = bool(
            self.command_application == "typed_simulator_applied"
            and self.applied_command_digest == self.requested_command_digest
            and self.actuator_attestation is not None
            and self.actuator_attestation.verify_integrity()
            and self.actuator_attestation.evidence_type == "fallback_actuator_applied"
            and self.dispatched_at_ns
            <= self.actuator_attestation.issued_at_ns
            <= self.observed_at_ns
            and self.actuator_attestation.valid_until_ns >= self.observed_at_ns
            and "simulator_env_step_applies_requested_command"
            in self.actuator_attestation.assumptions
            and self.actuator_attestation.subject_digest
            == _fallback_actuation_subject_digest(
                self.episode_nonce,
                self.fallback_id,
                self.requested_command_digest,
                self.dispatched_at_ns,
            )
        )
        expected_succeeded = bool(
            actuation_structurally_bound
            and self.observed_at_ns - self.triggered_at_ns
            <= self.switch_latency_bound_ns
            and self.postcondition.proven
        )
        return (
            self.succeeded is expected_succeeded
            and self.claim_digest == digest_payload(claim)
            and self.receipt_digest == digest_payload({**claim, "attestation": self.attestation})
            and self.postcondition.evaluation_digest
            == digest_payload(
                {
                    "observation_complete": self.postcondition.observation_complete,
                    "mission_invariants_hold": self.postcondition.mission_invariants_hold,
                    "distance_thresholds_hold": self.postcondition.distance_thresholds_hold,
                    "no_collision": self.postcondition.no_collision,
                    "no_cost": self.postcondition.no_cost,
                    "human_clearance_m": self.postcondition.human_clearance_m,
                    "obstacle_clearance_m": self.postcondition.obstacle_clearance_m,
                    "required_margin_m": self.postcondition.required_margin_m,
                    "checked_invariants": self.postcondition.checked_invariants,
                    "issues": self.postcondition.issues,
                }
            )
            and (
                (self.attestation is None and not self.succeeded)
                or (
                    self.attestation.verify_integrity()
                    and self.attestation.evidence_type == "fallback_switch"
                    and self.attestation.subject_digest == self.claim_digest
                )
            )
        )


@dataclass
class CTDARuntimeSession:
    """Stateful bridge between legacy wrapper objects and the CTDA supervisor."""

    supervisor: CTDASupervisor
    config: ConditionalKinematicConfig = field(default_factory=ConditionalKinematicConfig)
    evidence_issuer: CTDAEvidenceIssuer | None = None
    proposal_index: int = 0
    active_execution: ContractExecution | None = None
    last_fallback_receipt: FallbackSwitchReceipt | None = None

    @classmethod
    def from_legacy(
        cls,
        intent: Any,
        state: Any,
        safety_spec: Any,
        authority: Any,
        time_base: Any,
        *,
        spec_id: str,
        config: ConditionalKinematicConfig | None = None,
        evidence_issuer: CTDAEvidenceIssuer | None = None,
        now_ns: int | None = None,
        episode_nonce: str | None = None,
    ) -> "CTDARuntimeSession":
        if evidence_issuer is None:
            raise ValueError("CTDA fails closed without an explicit typed evidence issuer")
        runtime_config = config or ConditionalKinematicConfig()
        now = time.monotonic_ns() if now_ns is None else now_ns
        nonce = episode_nonce or digest_payload(
            {
                "spec_id": spec_id,
                "created_at_ns": now,
                "state_digest": digest_legacy_state(state),
                "authority_id": authority.authority_id,
            }
        )
        unsigned_mission = mission_from_legacy(
            intent,
            state,
            safety_spec,
            authority,
            time_base,
            spec_id=spec_id,
            episode_nonce=nonce,
        )
        authority_attestation = evidence_issuer.issue(
            "authority",
            unsigned_mission.mission_claim_digest,
            payload=unsigned_mission.unsigned_payload(),
            issued_at_ns=now,
            valid_until_ns=now + runtime_config.evidence_validity_ns,
            producer_id=authority.authority_id,
            producer_version=authority.version,
        )
        mission = bind_mission_authority(unsigned_mission, authority_attestation)
        checker = CTDAChecker(
            trusted_authorities=(mission.authority.authority_id,),
            evidence_verifier=evidence_issuer.verifier,
        )
        return cls(
            CTDASupervisor(mission, checker, now_ns=now),
            runtime_config,
            evidence_issuer,
        )

    def reset(self) -> None:
        self.supervisor.checker.clear_authorization_ledger()
        self.supervisor.active_phase = self.supervisor.mission.initial_phase
        self.supervisor.active_contract = None
        self.supervisor.monitor_state = None
        self.supervisor.active_semantic_witness_digest = None
        self.supervisor.active_semantic_attestations = ()
        self.supervisor.pending_authorization_digest = None
        self.supervisor.terminal_verdict = None
        self.proposal_index = 0
        self.active_execution = None
        self.last_fallback_receipt = None

    def fallback_command(self) -> tuple[float, ...]:
        if not self.config.fallback_verified or not self.config.fallback_action:
            raise RuntimeError("no trusted executable fallback is configured")
        return tuple(float(value) for value in self.config.fallback_action)

    def attest_fallback_actuation(
        self,
        command: Sequence[float],
        *,
        dispatched_at_ns: int,
        applied_at_ns: int | None = None,
    ) -> EvidenceAttestation:
        """Attest simulator-adapter evidence that the requested command was applied.

        Calling this method is an explicit simulator TCB boundary. Merely asking
        an actuator to apply a command is not evidence that it was applied.
        """

        normalized = tuple(float(value) for value in command)
        if normalized != self.fallback_command():
            raise ValueError(
                "applied fallback command differs from the configured controller action"
            )
        command_digest = digest_payload(normalized)
        issued_at = time.monotonic_ns() if applied_at_ns is None else applied_at_ns
        if issued_at < dispatched_at_ns:
            raise ValueError("fallback actuation evidence predates command dispatch")
        attestation = self._issue(
            "fallback_actuator_applied",
            _fallback_actuation_subject_digest(
                self.supervisor.mission.episode_nonce,
                self.config.fallback_id,
                command_digest,
                dispatched_at_ns,
            ),
            payload={
                "fallback_id": self.config.fallback_id,
                "requested_command_digest": command_digest,
                "applied_command_digest": command_digest,
                "dispatched_at_ns": dispatched_at_ns,
                "applied_at_ns": issued_at,
                "trust_boundary": "simulator-env-step-adapter",
            },
            issued_at_ns=issued_at,
            assumptions=("simulator_env_step_applies_requested_command",),
        )
        if self.evidence_issuer is None or not self.evidence_issuer.verifier.verify(
            attestation
        ):
            raise RuntimeError("fallback actuator attestation failed verification")
        return attestation

    def record_fallback_switch(
        self,
        *,
        trigger: str,
        state_before: Any,
        state_after: Any | None,
        command: Sequence[float],
        triggered_at_ns: int,
        requested_at_ns: int,
        dispatched_at_ns: int,
        observed_at_ns: int,
        safety_spec: Any,
        environment_info: Any | None = None,
        observation_error: str | None = None,
        actuator_attestation: EvidenceAttestation | None = None,
    ) -> FallbackSwitchReceipt:
        normalized = tuple(float(value) for value in command)
        if normalized != self.fallback_command():
            raise ValueError("dispatched fallback command differs from the configured controller action")
        command_digest = digest_payload(normalized)
        verified_actuation = bool(
            actuator_attestation is not None
            and actuator_attestation.verify_integrity()
            and actuator_attestation.evidence_type == "fallback_actuator_applied"
            and dispatched_at_ns
            <= actuator_attestation.issued_at_ns
            <= observed_at_ns
            and actuator_attestation.valid_until_ns >= observed_at_ns
            and "simulator_env_step_applies_requested_command"
            in actuator_attestation.assumptions
            and actuator_attestation.subject_digest
            == _fallback_actuation_subject_digest(
                self.supervisor.mission.episode_nonce,
                self.config.fallback_id,
                command_digest,
                dispatched_at_ns,
            )
            and self.evidence_issuer is not None
            and self.evidence_issuer.verifier.verify(actuator_attestation)
        )
        postcondition = _evaluate_fallback_postcondition(
            self.supervisor.mission,
            state_after,
            safety_spec,
            environment_info=environment_info,
            observation_error=observation_error,
        )
        active_contract_digest = (
            self.supervisor.active_contract.contract_digest
            if self.supervisor.active_contract is not None
            else None
        )
        monitor_state_digest = (
            self.supervisor.monitor_state.monitor_state_digest
            if self.supervisor.monitor_state is not None
            else None
        )
        active_execution_digest = (
            self.active_execution.execution_digest
            if self.active_execution is not None
            else None
        )
        state_after_digest = (
            digest_legacy_state(state_after)
            if state_after is not None
            else digest_payload(
                {
                    "unknown_fallback_post_state": True,
                    "observation_error": observation_error or "post-state unavailable",
                    "observed_at_ns": observed_at_ns,
                }
            )
        )
        receipt = FallbackSwitchReceipt(
            episode_nonce=self.supervisor.mission.episode_nonce,
            fallback_id=self.config.fallback_id,
            trigger=trigger,
            state_before_digest=digest_legacy_state(state_before),
            state_after_digest=state_after_digest,
            requested_command_digest=command_digest,
            command_application=(
                "typed_simulator_applied" if verified_actuation else "requested_only"
            ),
            applied_command_digest=command_digest if verified_actuation else None,
            actuator_attestation=actuator_attestation if verified_actuation else None,
            postcondition=postcondition,
            triggered_at_ns=triggered_at_ns,
            requested_at_ns=requested_at_ns,
            dispatched_at_ns=dispatched_at_ns,
            observed_at_ns=observed_at_ns,
            switch_latency_bound_ns=self.supervisor.mission.time_base.switch_latency_ns,
            active_contract_digest=active_contract_digest,
            pending_authorization_digest=self.supervisor.pending_authorization_digest,
            active_execution_digest=active_execution_digest,
            monitor_state_digest=monitor_state_digest,
        )
        try:
            receipt = replace(
                receipt,
                attestation=self._issue(
                    "fallback_switch",
                    receipt.claim_digest,
                    payload={
                        "claim_digest": receipt.claim_digest,
                        "fallback_witness_digest": self.config.fallback_witness_digest,
                        "postcondition_digest": postcondition.evaluation_digest,
                    },
                    issued_at_ns=observed_at_ns,
                ),
            )
            if (
                receipt.attestation is None
                or not receipt.verify_integrity()
                or self.evidence_issuer is None
                or not self.evidence_issuer.verifier.verify(receipt.attestation)
            ):
                raise RuntimeError(
                    "fallback switch receipt attestation failed verification"
                )
        except Exception as exc:
            failed_postcondition = replace(
                postcondition,
                issues=postcondition.issues
                + (f"fallback receipt attestation unavailable: {exc}",),
            )
            receipt = replace(
                receipt,
                command_application="requested_only",
                applied_command_digest=None,
                actuator_attestation=None,
                postcondition=failed_postcondition,
                attestation=None,
            )
        finally:
            # A fallback attempt terminates the old execution authority. Clear
            # every live handle before publishing the receipt, then latch the
            # supervisor so that no stale prefix can resume after the switch.
            self.supervisor.pending_authorization_digest = None
            self.supervisor.active_contract = None
            self.supervisor.monitor_state = None
            self.supervisor.active_semantic_witness_digest = None
            self.supervisor.active_semantic_attestations = ()
            self.supervisor.terminal_verdict = (
                MonitorVerdict.VIOLATED
                if receipt.succeeded
                else MonitorVerdict.INCONSISTENT
            )
            self.active_execution = None
            self.last_fallback_receipt = receipt
        return receipt

    def _issue(
        self,
        evidence_type: str,
        subject_digest: str,
        *,
        payload: Any,
        issued_at_ns: int,
        assumptions: Sequence[str] = (),
        producer_id: str | None = None,
        producer_version: str | None = None,
    ) -> EvidenceAttestation:
        if self.evidence_issuer is None:
            raise RuntimeError("CTDA typed evidence issuer is not configured")
        return self.evidence_issuer.issue(
            evidence_type,
            subject_digest,
            payload=payload,
            issued_at_ns=issued_at_ns,
            valid_until_ns=issued_at_ns + self.config.evidence_validity_ns,
            assumptions=assumptions,
            producer_id=producer_id,
            producer_version=producer_version,
        )

    def _issue_requirements(
        self,
        evidence_types: Sequence[str],
        subject_digest: str,
        *,
        payload: Any,
        issued_at_ns: int,
        assumptions: Sequence[str] = (),
    ) -> tuple[EvidenceAttestation, ...]:
        return tuple(
            self._issue(
                evidence_type,
                subject_digest,
                payload={"requirement": evidence_type, "claim": payload},
                issued_at_ns=issued_at_ns,
                assumptions=assumptions,
            )
            for evidence_type in _unique_strings(evidence_types)
        )

    def prepare_prefix(
        self,
        symbolic_action: Any,
        current_state: Any,
        raw_actions: Sequence[Any],
        safety_spec: Any,
        *,
        now_ns: int | None = None,
    ) -> PrepareResult:
        now = time.monotonic_ns() if now_ns is None else now_ns
        if self.evidence_issuer is None:
            return PrepareResult(
                StaticCheckResult.refuted(
                    "CTDA fails closed without an explicit typed evidence issuer"
                )
            )
        if not raw_actions:
            return PrepareResult(StaticCheckResult.refuted("policy proposal contains no raw actions"))
        try:
            commands = tuple(_normalise_command(action) for action in raw_actions)
        except (TypeError, ValueError) as exc:
            return PrepareResult(StaticCheckResult.refuted(f"invalid raw action proposal: {exc}"))

        if self.supervisor.active_contract is None:
            try:
                contract = contract_from_legacy_action(
                    self.supervisor.mission,
                    symbolic_action,
                    contract_id=digest_payload(
                        {
                            "spec": self.supervisor.mission.spec_digest,
                            "phase": self.supervisor.active_phase,
                            "action": digest_legacy_action(symbolic_action),
                            "created": now,
                        }
                    ),
                    current_phase=self.supervisor.active_phase,
                    issued_at_ns=now,
                    deadline_ns=now + self.config.contract_budget_ns,
                    fallback_id=self.config.fallback_id,
                )
                contract = replace(
                    contract,
                    semantic_pre_requirements=_unique_strings(
                        contract.semantic_pre_requirements + self.config.semantic_evidence
                    ),
                    physical_pre_requirements=_unique_strings(
                        contract.physical_pre_requirements + self.config.physical_evidence
                    ),
                    runtime_requirements=_unique_strings(
                        contract.runtime_requirements + self.config.runtime_evidence
                    ),
                    post_requirements=_unique_strings(
                        contract.post_requirements + self.config.post_evidence
                    ),
                )
                semantic_types = _unique_strings(
                    self.supervisor.mission.required_evidence
                    + contract.semantic_pre_requirements
                )
                semantic_attestations = self._issue_requirements(
                    semantic_types,
                    contract.contract_digest,
                    payload={
                        "spec_digest": self.supervisor.mission.spec_digest,
                        "contract_digest": contract.contract_digest,
                        "phase": self.supervisor.active_phase,
                        "state_digest": digest_legacy_state(current_state),
                    },
                    issued_at_ns=now,
                )
            except (TypeError, ValueError) as exc:
                return PrepareResult(StaticCheckResult.refuted(f"cannot activate semantic contract: {exc}"))
            except Exception as exc:
                return PrepareResult(
                    StaticCheckResult.inconsistent(f"cannot issue semantic evidence: {exc}")
                )
            activated = self.supervisor.activate_contract(
                contract,
                semantic_attestations,
                now_ns=now,
            )
            if not activated.proven:
                return PrepareResult(activated)

        contract = self.supervisor.active_contract
        monitor = self.supervisor.monitor_state
        if contract is None or monitor is None:
            return PrepareResult(StaticCheckResult.inconsistent("supervisor lost its active contract state"))

        try:
            proposal_admissible = _action_matches_contract(symbolic_action, contract)
            state_digest = digest_legacy_state(current_state)
            proposal_digest = digest_payload(commands)
            authorised_digest = digest_payload(commands)
            duration_ns = len(commands) * self.config.control_period_ns
            model_digest = digest_text(self.config.dynamics_model_id)
            assumptions = _kinematic_assumptions(self.config, safety_spec)
            prefix_safe = _prefix_clearance_safe(
                current_state, commands, safety_spec, self.config
            )
            proposal = ActionProposalBinding(
                contract_id=contract.contract_id,
                contract_digest=contract.contract_digest,
                proposal_index=self.proposal_index,
                proposal_digest=proposal_digest,
                proposed_horizon_ns=duration_ns,
                issued_at_ns=now,
            )
            tube_witness = digest_payload(
                {
                    "model": model_digest,
                    "commands": authorised_digest,
                    "state": state_digest,
                    "assumptions": assumptions,
                    "prefix_safe": prefix_safe,
                    "fallback_witness": self.config.fallback_witness_digest,
                    "fallback_action_digest": (
                        digest_payload(self.fallback_command())
                        if self.config.fallback_verified
                        else None
                    ),
                }
            )
            tube = ReachableTube(
                authorized_command_digest=authorised_digest,
                dynamics_model_digest=model_digest,
                duration_ns=duration_ns,
                fallback_id=self.config.fallback_id,
                all_prefixes_safe=prefix_safe,
                all_cut_states_recoverable=self.config.fallback_verified,
                witness_digest=tube_witness,
                assumptions=assumptions,
            )
            tube = replace(
                tube,
                attestation=self._issue(
                    "reachable_tube",
                    tube.claim_digest,
                    payload={"claim_digest": tube.claim_digest, "state_digest": state_digest},
                    issued_at_ns=now,
                    assumptions=assumptions,
                ),
            )
            validity_ns = duration_ns + self.config.authorization_slack_ns
            valid_until_ns = min(now + validity_ns, contract.deadline_ns)
            if valid_until_ns <= now:
                return PrepareResult(
                    StaticCheckResult.refuted("semantic contract cannot cover another prefix")
                )
            semantic_witness = self.supervisor.active_semantic_witness_digest
            if not semantic_witness:
                return PrepareResult(
                    StaticCheckResult.inconsistent("active semantic witness is missing")
                )
            authorization = PrefixAuthorization(
                contract_id=contract.contract_id,
                contract_digest=contract.contract_digest,
                spec_digest=self.supervisor.mission.spec_digest,
                episode_nonce=self.supervisor.mission.episode_nonce,
                state_digest=state_digest,
                monitor_state_digest=monitor.monitor_state_digest,
                proposal_index=self.proposal_index,
                proposal_digest=proposal_digest,
                authorized_command_digest=authorised_digest,
                filter_policy_digest=digest_text(self.config.filter_policy_id),
                dynamics_model_digest=model_digest,
                time_base_digest=self.supervisor.mission.time_base.time_base_digest,
                tube_digest=tube.tube_digest,
                max_authorized_duration_ns=duration_ns,
                fallback_id=self.config.fallback_id,
                issued_at_ns=now,
                valid_until_ns=valid_until_ns,
                semantic_witness_digest=semantic_witness,
            )
            proposal_witness = digest_payload(
                {
                    "contract_digest": contract.contract_digest,
                    "legacy_action_digest": digest_legacy_action(symbolic_action),
                    "proposal_binding_digest": proposal.binding_digest,
                    "proposal_admissible": proposal_admissible,
                }
            )
            proposal_attestation = self._issue(
                "proposal_contract",
                proposal_contract_subject_digest(
                    contract,
                    proposal,
                    proposal_admissible,
                    proposal_witness,
                ),
                payload={
                    "contract_digest": contract.contract_digest,
                    "proposal_digest": proposal.binding_digest,
                    "legacy_action_digest": digest_legacy_action(symbolic_action),
                    "admissible": proposal_admissible,
                },
                issued_at_ns=now,
            )
            filter_witness = digest_payload(
                {
                    "filter_policy_digest": authorization.filter_policy_digest,
                    "proposal_digest": proposal_digest,
                    "authorized_command_digest": authorised_digest,
                    "preserves_contract": True,
                }
            )
            filter_attestation = self._issue(
                "filter_envelope",
                filter_envelope_subject_digest(
                    contract,
                    proposal,
                    authorization,
                    True,
                    filter_witness,
                ),
                payload={
                    "filter_policy_digest": authorization.filter_policy_digest,
                    "proposal_digest": proposal_digest,
                    "authorized_command_digest": authorised_digest,
                    "preserves_contract": True,
                },
                issued_at_ns=now,
            )
            physical_attestations = self._issue_requirements(
                contract.physical_pre_requirements,
                authorization.authorization_digest,
                payload={
                    "authorization_digest": authorization.authorization_digest,
                    "tube_digest": tube.tube_digest,
                },
                issued_at_ns=now,
                assumptions=assumptions,
            )
            guard_attestations = self._issue_requirements(
                tuple(f"guard:{guard}" for guard in contract.guards),
                guard_subject_digest(
                    contract,
                    state_digest,
                    monitor.monitor_state_digest,
                ),
                payload={
                    "contract_digest": contract.contract_digest,
                    "state_digest": state_digest,
                    "monitor_state_digest": monitor.monitor_state_digest,
                },
                issued_at_ns=now,
            )
            candidate = PrefixCandidate(
                proposal=proposal,
                authorization=authorization,
                tube=tube,
                proposal_contract_witness_digest=proposal_witness,
                filter_envelope_witness_digest=filter_witness,
                proposal_admissible=proposal_admissible,
                filter_preserves_contract=True,
                semantic_attestations=self.supervisor.active_semantic_attestations,
                guard_attestations=guard_attestations,
                proposal_contract_attestation=proposal_attestation,
                filter_envelope_attestation=filter_attestation,
                pre_attestations=physical_attestations,
            )
        except Exception as exc:
            return PrepareResult(
                StaticCheckResult.inconsistent(f"cannot construct typed prefix evidence: {exc}")
            )
        check = self.supervisor.authorize_prefix(
            state_digest,
            candidate,
            (),
            now_ns=now,
        )
        if not check.proven:
            return PrepareResult(check)

        if self.active_execution is None:
            self.active_execution = ContractExecution(
                contract_id=contract.contract_id,
                spec_digest=self.supervisor.mission.spec_digest,
                episode_nonce=self.supervisor.mission.episode_nonce,
                initial_state_digest=state_digest,
                initial_monitor_state_digest=monitor.monitor_state_digest,
            )
        before_state = current_state.clone() if hasattr(current_state, "clone") else current_state
        prepared = PreparedPrefix(
            candidate,
            commands,
            symbolic_action,
            before_state,
            state_digest,
            now,
        )
        self.proposal_index += 1
        return PrepareResult(check, prepared)

    def observe_prefix(
        self,
        prepared: PreparedPrefix,
        states_after: Sequence[Any],
        executed_actions: Sequence[Any],
        safety_spec: Any,
        *,
        dispatch_ns: int | None = None,
        observation_times_ns: Sequence[int] | None = None,
        now_ns: int | None = None,
    ) -> tuple[MonitorCheckResult, PrefixExecutionRecord]:
        if self.evidence_issuer is None:
            raise RuntimeError("CTDA fails closed without an explicit typed evidence issuer")
        contract = self.supervisor.active_contract
        monitor = self.supervisor.monitor_state
        if contract is None or monitor is None:
            raise RuntimeError("no CTDA contract is active for the execution receipt")
        if not states_after or len(states_after) != len(executed_actions):
            raise ValueError("states_after and executed_actions must be non-empty and aligned")
        if dispatch_ns is None or observation_times_ns is None:
            raise ValueError("real dispatch_ns and observation_times_ns are required")
        observation_times = tuple(int(value) for value in observation_times_ns)
        if len(observation_times) != len(states_after):
            raise ValueError("observation timestamps must align with observed states")
        if any(value < dispatch_ns for value in observation_times):
            raise ValueError("an observation timestamp predates command dispatch")
        if any(left >= right for left, right in zip(observation_times, observation_times[1:])):
            raise ValueError("observation timestamps must be strictly increasing")
        commands = tuple(_normalise_command(action) for action in executed_actions)
        executed_digest = digest_payload(commands)
        samples: list[PlantSample] = []
        for index, (state, timestamp) in enumerate(zip(states_after, observation_times)):
            previous_state = prepared.before_state if index == 0 else states_after[index - 1]
            samples.append(
                PlantSample(
                    timestamp_ns=timestamp,
                    state_digest=digest_legacy_state(state),
                    command_digest=executed_digest,
                    hard_invariants_hold=_state_invariants_hold(state, safety_spec),
                    within_reachable_tube=_observed_tube_membership(
                        prepared.before_state,
                        state,
                        commands[: index + 1],
                        safety_spec,
                        self.config,
                    ),
                    model_assumptions_hold=_model_assumptions_hold(
                        previous_state,
                        state,
                        commands[index],
                        self.config,
                    ),
                )
            )
        evidence_time = observation_times[-1]
        observer_digest = digest_payload(
            {
                "producer": "legacy-world-state-observer",
                "states": [sample.state_digest for sample in samples],
                "timestamps": observation_times,
            }
        )
        plant_trace = PlantTrace(
            time_base_digest=self.supervisor.mission.time_base.time_base_digest,
            samples=tuple(samples),
            observer_evidence_digest=observer_digest,
        )
        plant_trace = replace(
            plant_trace,
            attestation=self._issue(
                "plant_trace",
                plant_trace.claim_digest,
                payload={
                    "claim_digest": plant_trace.claim_digest,
                    "observer_evidence_digest": observer_digest,
                },
                issued_at_ns=evidence_time,
                assumptions=prepared.candidate.tube.assumptions,
            ),
        )
        events_with_samples = _derive_events(
            contract, prepared.before_state, states_after, samples
        )
        events = tuple(item[0] for item in events_with_samples)
        links = tuple(
            AbstractionLink(
                event_index=index,
                plant_sample_index=sample_index,
                atom=event.atom,
                derivation_digest=digest_payload(
                    {
                        "producer": "legacy-event-abstraction-v1",
                        "event": event,
                        "sample": samples[sample_index].state_digest,
                    }
                ),
            )
            for index, (event, sample_index) in enumerate(events_with_samples)
        )
        abstraction = TraceAbstractionEvidence(
            plant_trace_digest=plant_trace.plant_trace_digest,
            time_base_digest=self.supervisor.mission.time_base.time_base_digest,
            events_digest=digest_payload(events),
            links=links,
            producer_id="legacy-event-abstraction",
            producer_version="1",
            witness_digest=digest_payload(links),
        )
        abstraction = replace(
            abstraction,
            attestation=self._issue(
                "trace_abstraction",
                abstraction.claim_digest,
                payload={
                    "claim_digest": abstraction.claim_digest,
                    "plant_trace_digest": plant_trace.plant_trace_digest,
                },
                issued_at_ns=evidence_time,
                producer_id=abstraction.producer_id,
                producer_version=abstraction.producer_version,
            ),
        )
        event_trace = SymbolicEventTrace(
            time_base_digest=self.supervisor.mission.time_base.time_base_digest,
            plant_trace_digest=plant_trace.plant_trace_digest,
            abstraction_evidence_digest=abstraction.abstraction_evidence_digest,
            events=events,
        )
        next_monitor = advance_monitor_state(
            contract, monitor, event_trace, prepared.candidate.proposal.proposal_index
        )
        receipt = ExecutionReceipt(
            authorization_digest=prepared.candidate.authorization.authorization_digest,
            authorized_command_digest=prepared.candidate.authorization.authorized_command_digest,
            executed_command_digest=executed_digest,
            actuator_evidence_digest=digest_payload(
                {
                    "authorized": prepared.candidate.authorization.authorized_command_digest,
                    "executed": executed_digest,
                }
            ),
            executed_at_ns=dispatch_ns,
            within_authorized_error=(
                commands == prepared.authorized_actions[: len(commands)]
                and len(commands) <= len(prepared.authorized_actions)
            ),
        )
        receipt = replace(
            receipt,
            attestation=self._issue(
                "actuator_receipt",
                receipt.claim_digest,
                payload={
                    "claim_digest": receipt.claim_digest,
                    "dispatch_ns": dispatch_ns,
                    "observation_times_ns": observation_times,
                },
                issued_at_ns=evidence_time,
            ),
        )
        runtime_attestations = self._issue_requirements(
            contract.runtime_requirements,
            plant_trace.plant_trace_digest,
            payload={
                "plant_trace_digest": plant_trace.plant_trace_digest,
                "authorization_digest": prepared.candidate.authorization.authorization_digest,
            },
            issued_at_ns=evidence_time,
            assumptions=prepared.candidate.tube.assumptions,
        )
        post_attestations = self._issue_requirements(
            contract.post_requirements,
            event_trace.symbolic_event_trace_digest,
            payload={
                "symbolic_event_trace_digest": event_trace.symbolic_event_trace_digest,
                "contract_digest": contract.contract_digest,
            },
            issued_at_ns=evidence_time,
        )
        record = PrefixExecutionRecord(
            candidate=prepared.candidate,
            receipt=receipt,
            plant_trace=plant_trace,
            event_trace=event_trace,
            abstraction_evidence=abstraction,
            monitor_before_digest=monitor.monitor_state_digest,
            monitor_after_digest=next_monitor.monitor_state_digest,
            runtime_attestations=runtime_attestations,
        )
        evaluation_time = max(
            evidence_time,
            evidence_time if now_ns is None else now_ns,
        )
        result = self.supervisor.observe_prefix(
            record,
            post_attestations,
            now_ns=evaluation_time,
        )
        if self.active_execution is None:
            raise RuntimeError("CTDA execution chain was not initialised")
        self.active_execution = self.active_execution.append(record)
        if result.complete:
            self.active_execution = None
        return result, record


def _unique_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def _normalise_command(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return _normalise_command(value.tolist())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if not isfinite(number):
            raise ValueError("command contains a non-finite value")
        return number
    if isinstance(value, (list, tuple)):
        return tuple(_normalise_command(item) for item in value)
    raise TypeError(f"unsupported command value {type(value).__name__}")


def _flatten_command(value: Any) -> list[float]:
    if isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        result: list[float] = []
        for item in value:
            result.extend(_flatten_command(item))
        return result
    return []


def _commands_within_model(commands: Sequence[Any], config: ConditionalKinematicConfig) -> bool:
    numbers = [number for command in commands for number in _flatten_command(command)]
    return bool(numbers) and all(isfinite(number) and abs(number) <= config.max_command_abs for number in numbers)


def _translation_bound(commands: Sequence[Any], config: ConditionalKinematicConfig) -> float:
    bound = 0.0
    for command in commands:
        numbers = _flatten_command(command)
        xyz = (numbers + [0.0, 0.0, 0.0])[:3]
        bound += sqrt(sum(value * value for value in xyz)) * config.translation_scale_m
    return bound


def _has_unknown_observation(state: Any) -> bool:
    notes = getattr(state, "notes", ()) or ()
    return any(
        str(note).startswith("ctda_unknown_observation:")
        or str(note).startswith("missing trusted CTDA observation:")
        for note in notes
    )


def _environment_no_cost(environment_info: Any | None) -> bool | None:
    if not isinstance(environment_info, dict) or "cost" not in environment_info:
        return None
    cost = environment_info.get("cost")
    if isinstance(cost, dict):
        return not any(bool(value) for value in cost.values())
    if cost in (None, 0, 0.0, False):
        return True
    if isinstance(cost, (bool, int, float)):
        return False
    return None


def _evaluate_fallback_postcondition(
    mission: Any,
    state_after: Any | None,
    safety_spec: Any,
    *,
    environment_info: Any | None,
    observation_error: str | None,
) -> FallbackPostconditionEvaluation:
    """Evaluate fallback success from observations, never from a caller verdict."""

    issues: list[str] = []
    try:
        configured_margin = float(getattr(safety_spec, "safety_margin", 0.0))
    except (TypeError, ValueError):
        configured_margin = 0.0
        issues.append("fallback safety margin is not numeric")
    if not isfinite(configured_margin) or configured_margin < 0:
        configured_margin = 0.0
        issues.append("fallback safety margin is not finite and non-negative")

    invariant_thresholds: list[float] = []
    checked_invariants = tuple(str(value) for value in mission.hard_invariants)
    for invariant in checked_invariants:
        if invariant.startswith("human_clearance>=") or invariant.startswith(
            "obstacle_clearance>="
        ):
            try:
                threshold = float(invariant.split(">=", 1)[1])
            except (TypeError, ValueError):
                issues.append(f"unsupported fallback invariant: {invariant}")
                continue
            if not isfinite(threshold) or threshold < 0:
                issues.append(f"invalid fallback invariant threshold: {invariant}")
                continue
            invariant_thresholds.append(threshold)
        elif invariant != "no_collision":
            issues.append(f"unsupported fallback invariant: {invariant}")
    required_margin = max((configured_margin, *invariant_thresholds))

    human: float | None = None
    obstacle: float | None = None
    no_collision: bool | None = None
    if state_after is None:
        issues.append("fallback post-state is unavailable")
    else:
        if _has_unknown_observation(state_after):
            issues.append("fallback post-state contains unknown safety observations")
        collision = getattr(state_after, "collision", None)
        no_collision = not collision if type(collision) is bool else None
        if no_collision is None:
            issues.append("fallback collision observation is unavailable")
        elif not no_collision:
            issues.append("fallback post-state reports a collision")
        for attribute, label in (
            ("min_distance_to_human_hand", "human"),
            ("min_distance_to_obstacle", "obstacle"),
        ):
            try:
                value = float(getattr(state_after, attribute))
            except (AttributeError, TypeError, ValueError):
                value = float("nan")
            if not isfinite(value) or value < 0:
                issues.append(f"fallback {label} clearance observation is unavailable")
            elif label == "human":
                human = value
            else:
                obstacle = value

    no_cost = _environment_no_cost(environment_info)
    if no_cost is None:
        issues.append("fallback cost observation is unavailable")
    elif not no_cost:
        issues.append("fallback action incurred an environment cost")
    if observation_error:
        issues.append(f"fallback observation failed: {observation_error}")

    distance_thresholds_hold = bool(
        human is not None
        and obstacle is not None
        and human >= required_margin
        and obstacle >= required_margin
    )
    if human is not None and human < required_margin:
        issues.append("fallback human clearance is below the required margin")
    if obstacle is not None and obstacle < required_margin:
        issues.append("fallback obstacle clearance is below the required margin")

    mission_invariants_hold = True
    for invariant in checked_invariants:
        if invariant == "no_collision":
            holds = no_collision is True
        elif invariant.startswith("human_clearance>="):
            try:
                threshold = float(invariant.split(">=", 1)[1])
                holds = human is not None and isfinite(threshold) and human >= threshold
            except (TypeError, ValueError):
                holds = False
        elif invariant.startswith("obstacle_clearance>="):
            try:
                threshold = float(invariant.split(">=", 1)[1])
                holds = obstacle is not None and isfinite(threshold) and obstacle >= threshold
            except (TypeError, ValueError):
                holds = False
        else:
            holds = False
        if not holds:
            mission_invariants_hold = False
            issues.append(f"fallback mission invariant not established: {invariant}")

    issues = list(dict.fromkeys(issues))
    observation_complete = bool(
        state_after is not None
        and not observation_error
        and not _has_unknown_observation(state_after)
        and no_collision is not None
        and no_cost is not None
        and human is not None
        and obstacle is not None
    )
    return FallbackPostconditionEvaluation(
        observation_complete=observation_complete,
        mission_invariants_hold=mission_invariants_hold,
        distance_thresholds_hold=distance_thresholds_hold,
        no_collision=no_collision,
        no_cost=no_cost,
        human_clearance_m=human,
        obstacle_clearance_m=obstacle,
        required_margin_m=required_margin,
        checked_invariants=checked_invariants,
        issues=tuple(issues),
    )


def _state_invariants_hold(state: Any, safety_spec: Any) -> bool | None:
    if _has_unknown_observation(state):
        return None
    margin = float(getattr(safety_spec, "safety_margin", 0.0))
    try:
        human = float(getattr(state, "min_distance_to_human_hand"))
        obstacle = float(getattr(state, "min_distance_to_obstacle"))
        collision = getattr(state, "collision")
    except (AttributeError, TypeError, ValueError):
        return None
    if not isinstance(collision, bool) or not isfinite(human) or not isfinite(obstacle):
        return None
    return (
        not collision
        and human >= margin
        and obstacle >= margin
    )


def _prefix_clearance_safe(
    state: Any,
    commands: Sequence[Any],
    safety_spec: Any,
    config: ConditionalKinematicConfig,
) -> bool | None:
    if not _commands_within_model(commands, config):
        return False
    invariants = _state_invariants_hold(state, safety_spec)
    if invariants is None:
        return None
    if not invariants:
        return False
    margin = float(getattr(safety_spec, "safety_margin", 0.0))
    required = margin + _translation_bound(commands, config)
    human = float(getattr(state, "min_distance_to_human_hand", float("nan")))
    obstacle = float(getattr(state, "min_distance_to_obstacle", float("nan")))
    return human >= required and obstacle >= required


def _pose_distance(before: Any, after: Any) -> float | None:
    before_pose = getattr(before, "robot_pose", None)
    after_pose = getattr(after, "robot_pose", None)
    if before_pose is None or after_pose is None or not hasattr(before_pose, "distance_to"):
        return None
    try:
        distance = float(before_pose.distance_to(after_pose))
    except (TypeError, ValueError):
        return None
    return distance if isfinite(distance) else None


def _observed_tube_membership(
    initial_state: Any,
    observed_state: Any,
    cumulative_commands: Sequence[Any],
    safety_spec: Any,
    config: ConditionalKinematicConfig,
) -> bool | None:
    if _has_unknown_observation(initial_state) or _has_unknown_observation(observed_state):
        return None
    if not _commands_within_model(cumulative_commands, config):
        return False
    initial_safe = _prefix_clearance_safe(
        initial_state, cumulative_commands, safety_spec, config
    )
    observed_safe = _state_invariants_hold(observed_state, safety_spec)
    displacement = _pose_distance(initial_state, observed_state)
    if initial_safe is None or observed_safe is None or displacement is None:
        return None
    return bool(
        initial_safe
        and observed_safe
        and displacement <= _translation_bound(cumulative_commands, config) + 1e-9
    )


def _model_assumptions_hold(
    previous_state: Any,
    observed_state: Any,
    command: Any,
    config: ConditionalKinematicConfig,
) -> bool | None:
    if _has_unknown_observation(previous_state) or _has_unknown_observation(observed_state):
        return None
    if not _commands_within_model((command,), config):
        return False
    displacement = _pose_distance(previous_state, observed_state)
    if displacement is None:
        return None
    return displacement <= _translation_bound((command,), config) + 1e-9


def _kinematic_assumptions(
    config: ConditionalKinematicConfig,
    safety_spec: Any,
) -> tuple[str, ...]:
    return (
        f"delta_translation_scale_m={config.translation_scale_m}",
        f"command_abs_bound={config.max_command_abs}",
        f"clearance_margin_m={float(getattr(safety_spec, 'safety_margin', 0.0))}",
        "world_state_clearance_observation_sound",
        "kinematic_delta_bound_covers_plant_motion",
    )


def _action_matches_contract(action: Any, contract: SemanticSkillContract) -> bool:
    kind = getattr(getattr(action, "kind", None), "value", getattr(action, "kind", None))
    if str(kind) != contract.skill:
        return False
    if contract.target is not None and getattr(action, "object_id", None) != contract.target:
        return False
    if contract.part is not None and getattr(action, "part", None) != contract.part:
        return False
    if contract.region is not None and getattr(action, "region", None) != contract.region:
        return False
    return True


def _derive_events(
    contract: SemanticSkillContract,
    before_state: Any,
    states: Sequence[Any],
    samples: Sequence[PlantSample],
) -> list[tuple[SymbolicEvent, int]]:
    events: list[tuple[SymbolicEvent, int]] = []
    for index, (state, sample) in enumerate(zip(states, samples)):
        timestamp = sample.timestamp_ns
        if bool(getattr(state, "collision", False)):
            events.append((SymbolicEvent(timestamp, "collision", True), index))
        if contract.target is not None and getattr(state, "gripper_holding", None) == contract.target:
            events.append(
                (SymbolicEvent(timestamp, f"holding:{contract.target}", True, contract.target), index)
            )
        if contract.target is not None and contract.region is not None:
            objects = getattr(state, "objects", {})
            regions = getattr(state, "regions", {})
            obj = objects.get(contract.target) if hasattr(objects, "get") else None
            region = regions.get(contract.region) if hasattr(regions, "get") else None
            in_region = bool(obj and region and region.contains(obj.pose))
            if in_region:
                events.append(
                    (
                        SymbolicEvent(
                            timestamp,
                            f"in_region:{contract.target}:{contract.region}",
                            True,
                            contract.target,
                            contract.region,
                        ),
                        index,
                    )
                )
            if in_region and getattr(state, "gripper_holding", None) is None:
                events.append(
                    (SymbolicEvent(timestamp, f"released:{contract.target}", True, contract.target), index)
                )
        if contract.skill == "MoveTo" and contract.guarantees:
            if _observed_progress(before_state, state, contract):
                for guarantee in contract.guarantees:
                    if guarantee.startswith("progress:"):
                        events.append((SymbolicEvent(timestamp, guarantee, True), index))
        guarantees_seen = {event.atom for event, _ in events}
        if set(contract.guarantees).issubset(guarantees_seen):
            events.append(
                (SymbolicEvent(timestamp, f"phase:{contract.expected_next_phase}", True), index)
            )
            break
    return events


def _observed_progress(before: Any, after: Any, contract: SemanticSkillContract) -> bool:
    if contract.target is not None and contract.region is not None:
        before_objects = getattr(before, "objects", {})
        after_objects = getattr(after, "objects", {})
        regions = getattr(after, "regions", {})
        before_obj = before_objects.get(contract.target) if hasattr(before_objects, "get") else None
        after_obj = after_objects.get(contract.target) if hasattr(after_objects, "get") else None
        region = regions.get(contract.region) if hasattr(regions, "get") else None
        if before_obj and after_obj and region:
            return after_obj.pose.distance_to(region.center) < before_obj.pose.distance_to(region.center)
    before_pose = getattr(before, "robot_pose", None)
    after_pose = getattr(after, "robot_pose", None)
    if before_pose is not None and after_pose is not None and hasattr(before_pose, "distance_to"):
        return before_pose.distance_to(after_pose) > 1e-6
    return False


__all__ = [
    "ConditionalKinematicConfig",
    "CTDAEvidenceIssuer",
    "CTDARuntimeSession",
    "ExactAllowlistEvidenceIssuer",
    "FallbackSwitchReceipt",
    "LocalEvidenceIssuer",
    "PreparedPrefix",
    "PrepareResult",
]
