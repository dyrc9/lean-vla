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
    KinematicSampleDiagnostics,
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
    StaticVerdict,
    SymbolicEvent,
    SymbolicEventTrace,
    TraceAbstractionEvidence,
    advance_monitor_state,
    bind_mission_authority,
    contract_from_mission_phase,
    digest_legacy_state,
    digest_payload,
    digest_text,
    filter_envelope_subject_digest,
    guard_subject_digest,
    mission_from_legacy,
    proposal_contract_subject_digest,
)
from proofalign.ctda_evaluator import (
    CTDAEvaluationArtifact,
    CTDAEvaluationResult,
    CTDAEvaluator,
    CTDAEvaluatorMode,
)
from proofalign.ctda_wire import (
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    make_wire_request,
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
class RawProposalBinderConfig:
    """Versioned, finite-domain interpretation of LIBERO delta commands."""

    version: str = "mission-raw-binder-pick-place-v1"
    gripper_close_threshold: float = -0.2
    gripper_open_threshold: float = 0.2
    close_direction: int = -1
    grasp_neighborhood_m: float = 0.25
    translation_scale_m: float = 0.05
    direction_epsilon: float = 1e-9
    stutter_translation_bound_m: float = 0.0
    stutter_motion_command_bound: float = 0.0
    stutter_no_progress_limit: int = 0
    config_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("raw binder version must be non-empty")
        for name in (
            "gripper_close_threshold",
            "gripper_open_threshold",
            "grasp_neighborhood_m",
            "translation_scale_m",
            "direction_epsilon",
            "stutter_translation_bound_m",
            "stutter_motion_command_bound",
        ):
            if not isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} must be finite")
        if self.close_direction not in (-1, 1):
            raise ValueError("raw binder close_direction must be -1 or 1")
        if self.close_direction < 0 and self.gripper_close_threshold >= self.gripper_open_threshold:
            raise ValueError("raw binder gripper thresholds overlap")
        if self.close_direction > 0 and self.gripper_close_threshold <= self.gripper_open_threshold:
            raise ValueError("raw binder gripper thresholds overlap")
        if (
            self.grasp_neighborhood_m <= 0
            or self.translation_scale_m <= 0
            or self.direction_epsilon < 0
            or self.stutter_translation_bound_m < 0
            or self.stutter_motion_command_bound < 0
        ):
            raise ValueError("raw binder geometry thresholds are invalid")
        if (
            type(self.stutter_no_progress_limit) is not int
            or self.stutter_no_progress_limit < 0
        ):
            raise ValueError(
                "raw binder stutter no-progress limit must be a non-negative integer"
            )
        stutter_values = (
            self.stutter_translation_bound_m,
            self.stutter_motion_command_bound,
            self.stutter_no_progress_limit,
        )
        if any(stutter_values) and not all(stutter_values):
            raise ValueError(
                "raw binder cumulative stutter bounds and no-progress limit must be enabled together"
            )
        object.__setattr__(
            self,
            "config_digest",
            digest_payload(
                {
                    "version": self.version,
                    "gripper_close_threshold": self.gripper_close_threshold,
                    "gripper_open_threshold": self.gripper_open_threshold,
                    "close_direction": self.close_direction,
                    "grasp_neighborhood_m": self.grasp_neighborhood_m,
                    "translation_scale_m": self.translation_scale_m,
                    "direction_epsilon": self.direction_epsilon,
                    "stutter_translation_bound_m": self.stutter_translation_bound_m,
                    "stutter_motion_command_bound": self.stutter_motion_command_bound,
                    "stutter_no_progress_limit": self.stutter_no_progress_limit,
                }
            ),
        )

    @property
    def bounded_stutter_enabled(self) -> bool:
        return bool(
            self.stutter_translation_bound_m
            and self.stutter_motion_command_bound
            and self.stutter_no_progress_limit
        )


@dataclass(frozen=True)
class RawProposalBinderResult:
    """Consumer-computed raw-command binding; producer metadata is absent."""

    verdict: StaticVerdict
    mission_digest: str
    contract_digest: str
    state_digest: str
    command_digest: str
    config_digest: str
    issues: tuple[str, ...] = ()
    bounded_stutter: bool = False
    stutter_translation_m: float = 0.0
    stutter_motion_command_norm: float = 0.0
    witness_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(str(item) for item in self.issues))
        if type(self.bounded_stutter) is not bool:
            raise TypeError("bounded_stutter must be bool")
        if self.bounded_stutter and self.verdict is not StaticVerdict.PROVEN:
            raise ValueError("only a proven raw proposal can be a bounded stutter")
        for name in ("stutter_translation_m", "stutter_motion_command_norm"):
            value = getattr(self, name)
            if not isfinite(float(value)) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not self.bounded_stutter and (
            self.stutter_translation_m != 0.0
            or self.stutter_motion_command_norm != 0.0
        ):
            raise ValueError("non-stutter binder result cannot consume stutter budget")
        object.__setattr__(
            self,
            "witness_digest",
            digest_payload(
                {
                    "verdict": self.verdict.value,
                    "mission_digest": self.mission_digest,
                    "contract_digest": self.contract_digest,
                    "state_digest": self.state_digest,
                    "command_digest": self.command_digest,
                    "config_digest": self.config_digest,
                    "issues": self.issues,
                    "bounded_stutter": self.bounded_stutter,
                    "stutter_translation_m": self.stutter_translation_m,
                    "stutter_motion_command_norm": self.stutter_motion_command_norm,
                }
            ),
        )

    @property
    def proven(self) -> bool:
        return self.verdict is StaticVerdict.PROVEN


@dataclass(frozen=True)
class ConditionalKinematicConfig:
    control_period_ns: int = 20_000_000
    contract_budget_ns: int = 2_000_000_000
    authorization_slack_ns: int = 20_000_000
    max_command_abs: float = 1.0
    translation_scale_m: float = 0.05
    model_error_m: float = 0.0
    dynamics_model_id: str = "libero-delta-kinematic-v1"
    filter_policy_id: str = "identity-filter-v1"
    timing_policy_id: str = "strict-real-time-v1"
    fallback_id: str = "hold"
    fallback_witness_digest: str = ""
    fallback_verified: bool = False
    fallback_action: tuple[float, ...] = ()
    evidence_validity_ns: int = 3_600_000_000_000
    semantic_evidence: tuple[str, ...] = ("semantic_requirement",)
    physical_evidence: tuple[str, ...] = ("physical_requirement",)
    runtime_evidence: tuple[str, ...] = ("runtime_requirement",)
    post_evidence: tuple[str, ...] = ("post_requirement",)
    raw_binder: RawProposalBinderConfig = field(default_factory=RawProposalBinderConfig)

    def __post_init__(self) -> None:
        if self.control_period_ns <= 0 or self.contract_budget_ns <= 0:
            raise ValueError("runtime periods and budgets must be positive")
        if self.authorization_slack_ns < 0:
            raise ValueError("authorization slack must be non-negative")
        if self.timing_policy_id not in {
            "strict-real-time-v1",
            "slow-interlock-diagnostic-v1",
        }:
            raise ValueError("unsupported CTDA timing policy")
        if self.evidence_validity_ns <= 0:
            raise ValueError("evidence validity must be positive")
        if not isfinite(self.max_command_abs) or self.max_command_abs <= 0:
            raise ValueError("max_command_abs must be finite and positive")
        if not isfinite(self.translation_scale_m) or self.translation_scale_m < 0:
            raise ValueError("translation_scale_m must be finite and non-negative")
        if not isfinite(self.model_error_m) or self.model_error_m < 0:
            raise ValueError("model_error_m must be finite and non-negative")
        if self.raw_binder.bounded_stutter_enabled:
            if self.raw_binder.translation_scale_m != self.translation_scale_m:
                raise ValueError(
                    "bounded stutter and dynamics model must share translation scale"
                )
            command_path_translation_bound_m = (
                self.translation_scale_m
                * self.raw_binder.stutter_motion_command_bound
            )
            if (
                self.raw_binder.stutter_translation_bound_m
                > command_path_translation_bound_m + 1e-15
            ):
                raise ValueError(
                    "bounded stutter translation cannot exceed its "
                    "command-path-derived kinematic bound"
                )
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

    @property
    def realtime_timing_enforced(self) -> bool:
        return self.timing_policy_id == "strict-real-time-v1"


@dataclass(frozen=True)
class PreparedPrefix:
    candidate: PrefixCandidate
    authorized_actions: tuple[Any, ...]
    symbolic_action: Any
    before_state: Any
    state_digest: str
    start_ns: int
    bounded_stutter: bool = False
    bounded_stutter_count_before: int = 0
    bounded_stutter_translation_before_m: float = 0.0
    bounded_stutter_translation_after_m: float = 0.0
    bounded_stutter_motion_before: float = 0.0
    bounded_stutter_motion_after: float = 0.0


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
    required_observations: tuple[str, ...]
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
        object.__setattr__(self, "required_observations", tuple(self.required_observations))
        supported_observations = {
            "collision",
            "cost",
            "min_distance_to_human_hand",
            "min_distance_to_obstacle",
        }
        if (
            len(set(self.required_observations)) != len(self.required_observations)
            or not set(self.required_observations).issubset(supported_observations)
        ):
            raise ValueError("fallback required observations must be unique and supported")
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
                    "required_observations": self.required_observations,
                    "issues": self.issues,
                }
            ),
        )

    @property
    def proven(self) -> bool:
        required = set(self.required_observations)
        return (
            self.observation_complete
            and self.mission_invariants_hold
            and self.distance_thresholds_hold
            and ("collision" not in required or self.no_collision is True)
            and ("cost" not in required or self.no_cost is True)
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
    timing_policy_id: str
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
            "timing_policy_id",
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
        if self.timing_policy_id not in {
            "strict-real-time-v1",
            "slow-interlock-diagnostic-v1",
        }:
            raise ValueError("unsupported fallback timing policy")
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
            "timing_policy_id": self.timing_policy_id,
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
            "timing_policy_id": self.timing_policy_id,
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
                    "required_observations": self.postcondition.required_observations,
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

    @property
    def switch_latency_ns(self) -> int:
        return self.observed_at_ns - self.triggered_at_ns

    @property
    def within_switch_latency_bound(self) -> bool:
        return self.switch_latency_ns <= self.switch_latency_bound_ns

    @property
    def actuation_and_postcondition_established(self) -> bool:
        """Whether the requested fallback was applied and its safe set observed.

        This intentionally excludes the switch-latency SLA.  The original
        ``succeeded`` field remains the strict conjunction including latency.
        """

        return bool(
            self.command_application == "typed_simulator_applied"
            and self.applied_command_digest == self.requested_command_digest
            and self.actuator_attestation is not None
            and self.actuator_attestation.verify_integrity()
            and self.actuator_attestation.evidence_type
            == "fallback_actuator_applied"
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
            and self.postcondition.proven
        )


@dataclass
class CTDARuntimeSession:
    """Stateful bridge between legacy wrapper objects and the CTDA supervisor."""

    supervisor: CTDASupervisor
    config: ConditionalKinematicConfig = field(default_factory=ConditionalKinematicConfig)
    evidence_issuer: CTDAEvidenceIssuer | None = None
    evaluator: CTDAEvaluator | None = None
    proposal_index: int = 0
    bounded_stutter_count: int = 0
    bounded_stutter_translation_consumed_m: float = 0.0
    bounded_stutter_motion_consumed: float = 0.0
    bounded_stutter_deadline_ns: int | None = None
    active_execution: ContractExecution | None = None
    last_fallback_receipt: FallbackSwitchReceipt | None = None
    evaluation_artifacts: list[CTDAEvaluationArtifact] = field(default_factory=list)
    stage_request_ids: dict[WireStage, str] = field(default_factory=dict)

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
        evaluator: CTDAEvaluator | None = None,
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
            evaluator,
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
        # A reset/replan within the same mission nonce must not mint a fresh
        # micro-action allowance.  Only successful non-stutter contract
        # completion moves to a new contract budget below.
        self.active_execution = None
        self.last_fallback_receipt = None
        self.evaluation_artifacts.clear()
        self.stage_request_ids.clear()

    @property
    def evaluator_mode(self) -> str:
        return (
            self.evaluator.mode.value
            if self.evaluator is not None
            else CTDAEvaluatorMode.PYTHON_REFERENCE.value
        )

    @property
    def kernel_proof_verified(self) -> bool:
        return bool(
            self.evaluator is not None
            and self.evaluator.mode is CTDAEvaluatorMode.LEAN_KERNEL
            and self.evaluation_artifacts
            and all(item.proof_verified for item in self.evaluation_artifacts)
        )

    def fallback_command(self) -> tuple[float, ...]:
        if not self.config.fallback_verified or not self.config.fallback_action:
            raise RuntimeError("no trusted executable fallback is configured")
        return tuple(float(value) for value in self.config.fallback_action)

    def fallback_established_for_timing_policy(
        self, receipt: FallbackSwitchReceipt
    ) -> bool:
        """Apply the configured timing policy without weakening fallback safety."""

        if not receipt.verify_integrity():
            return False
        if receipt.timing_policy_id != self.config.timing_policy_id:
            return False
        if self.config.realtime_timing_enforced:
            return receipt.succeeded
        return bool(
            receipt.actuation_and_postcondition_established
            and receipt.attestation is not None
            and self.evidence_issuer is not None
            and self.evidence_issuer.verifier.verify(receipt.attestation)
        )

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
            timing_policy_id=self.config.timing_policy_id,
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

    def _evaluate_stage(
        self,
        stage: WireStage,
        payload: dict[str, Any],
    ) -> CTDAEvaluationResult | None:
        if self.evaluator is None:
            return None
        try:
            request = make_wire_request(
                stage,
                self.evaluator.checker_version_digest,
                payload,
            )
            result = self.evaluator.evaluate(request)
        except Exception as exc:
            raise RuntimeError(f"{stage.value} evaluator failed closed: {exc}") from exc
        self.evaluation_artifacts.append(result.artifact)
        self.stage_request_ids[stage] = request.request_id
        return result

    def _static_evaluation_check(
        self,
        result: CTDAEvaluationResult | None,
        stage: WireStage,
    ) -> StaticCheckResult:
        if result is None:
            return StaticCheckResult.success(f"python-reference:{stage.value}")
        if self.evaluator is not None and self.evaluator.mode is CTDAEvaluatorMode.SHADOW:
            return StaticCheckResult.inconsistent(
                "ctda-shadow is diagnostic and cannot authorize dispatch"
            )
        if result.verdict is WireStaticVerdict.PROVEN:
            if (
                self.evaluator is not None
                and self.evaluator.mode is CTDAEvaluatorMode.LEAN_KERNEL
                and not result.artifact.proof_verified
            ):
                return StaticCheckResult.inconsistent(
                    f"{stage.value} was not checked by the Lean kernel"
                )
            return StaticCheckResult.success(result.artifact.request_id)
        if result.verdict is WireStaticVerdict.UNKNOWN:
            return StaticCheckResult.unknown(
                f"{stage.value} evaluator returned unknown"
            )
        if result.verdict is WireStaticVerdict.REFUTED:
            return StaticCheckResult.refuted(
                f"{stage.value} evaluator refuted the wire request"
            )
        return StaticCheckResult.inconsistent(
            f"{stage.value} evaluator failed: {result.artifact.stderr or result.verdict.value}"
        )

    def _monitor_evaluation_check(
        self,
        result: CTDAEvaluationResult | None,
        reference: MonitorCheckResult,
        monitor_state: Any,
    ) -> MonitorCheckResult | None:
        if result is None:
            return None
        if self.evaluator is not None and self.evaluator.mode is CTDAEvaluatorMode.SHADOW:
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                monitor_state,
                issues=("ctda-shadow is diagnostic and cannot advance the online monitor",),
            )
        if (
            self.evaluator is not None
            and self.evaluator.mode is CTDAEvaluatorMode.LEAN_KERNEL
            and not result.artifact.proof_verified
        ):
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                monitor_state,
                issues=("monitor_step was not checked by the Lean kernel",),
            )
        if result.verdict.value != reference.verdict.value:
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                monitor_state,
                issues=(
                    "Python/Lean monitor parity mismatch; phase advance failed closed",
                ),
            )
        return None

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
                deadline_ns = now + self.config.contract_budget_ns
                if self.bounded_stutter_deadline_ns is not None:
                    deadline_ns = min(deadline_ns, self.bounded_stutter_deadline_ns)
                if deadline_ns <= now:
                    return PrepareResult(
                        StaticCheckResult.refuted(
                            "original bounded-stutter contract deadline is exhausted"
                        )
                    )
                contract = contract_from_mission_phase(
                    self.supervisor.mission,
                    current_phase=self.supervisor.active_phase,
                    issued_at_ns=now,
                    deadline_ns=deadline_ns,
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
                semantic_evaluation = self._evaluate_stage(
                    WireStage.SEMANTIC,
                    _semantic_wire_payload(
                        self.supervisor.mission,
                        self.supervisor.active_phase,
                        contract,
                        now,
                    ),
                )
            except (TypeError, ValueError) as exc:
                return PrepareResult(StaticCheckResult.refuted(f"cannot activate semantic contract: {exc}"))
            except Exception as exc:
                return PrepareResult(
                    StaticCheckResult.inconsistent(f"cannot issue semantic evidence: {exc}")
                )
            semantic_gate = self._static_evaluation_check(
                semantic_evaluation,
                WireStage.SEMANTIC,
            )
            if not semantic_gate.proven:
                return PrepareResult(semantic_gate)
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
            state_digest = digest_legacy_state(current_state)
            proposal_digest = digest_payload(commands)
            authorised_digest = digest_payload(commands)
            binder_result = bind_raw_proposal(
                self.supervisor.mission,
                contract,
                current_state,
                commands,
                self.config.raw_binder,
            )
            if not binder_result.proven:
                if binder_result.verdict is StaticVerdict.UNKNOWN:
                    return PrepareResult(StaticCheckResult.unknown(*binder_result.issues))
                if binder_result.verdict is StaticVerdict.INCONSISTENT:
                    return PrepareResult(StaticCheckResult.inconsistent(*binder_result.issues))
                return PrepareResult(StaticCheckResult.refuted(*binder_result.issues))
            stutter_translation_after_m = (
                self.bounded_stutter_translation_consumed_m
                + binder_result.stutter_translation_m
            )
            stutter_motion_after = (
                self.bounded_stutter_motion_consumed
                + binder_result.stutter_motion_command_norm
            )
            if binder_result.bounded_stutter:
                if (
                    self.bounded_stutter_count
                    >= self.config.raw_binder.stutter_no_progress_limit
                ):
                    return PrepareResult(
                        StaticCheckResult.refuted(
                            "raw binder persistent bounded-stutter no-progress limit is exhausted"
                        )
                    )
                if (
                    stutter_translation_after_m
                    > self.config.raw_binder.stutter_translation_bound_m
                ):
                    return PrepareResult(
                        StaticCheckResult.refuted(
                            "raw binder cumulative bounded-stutter predicted-translation budget is exceeded"
                        )
                    )
                if (
                    stutter_motion_after
                    > self.config.raw_binder.stutter_motion_command_bound
                ):
                    return PrepareResult(
                        StaticCheckResult.refuted(
                            "raw binder cumulative bounded-stutter six-dimensional command-path budget is exceeded"
                        )
                    )
            proposal_admissible = True
            duration_ns = len(commands) * self.config.control_period_ns
            model_digest = digest_text(self.config.dynamics_model_id)
            assumptions = _kinematic_assumptions(self.config, safety_spec)
            if binder_result.bounded_stutter:
                assumptions += (
                    "bounded_stutter_pick_approach_only",
                    "bounded_stutter_non_closing_gripper",
                    "bounded_stutter_cumulative_translation_m<="
                    f"{self.config.raw_binder.stutter_translation_bound_m}",
                    "bounded_stutter_cumulative_motion_command_path_norm<="
                    f"{self.config.raw_binder.stutter_motion_command_bound}",
                    "bounded_stutter_persistent_no_progress_limit="
                    f"{self.config.raw_binder.stutter_no_progress_limit}",
                    "bounded_stutter_budget_consumed_at_authorization",
                    "bounded_stutter_zero_phase_advance",
                )
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
                    "bounded_stutter": binder_result.bounded_stutter,
                    "bounded_stutter_count_before": self.bounded_stutter_count,
                    "bounded_stutter_no_progress_limit": (
                        self.config.raw_binder.stutter_no_progress_limit
                    ),
                    "bounded_stutter_translation_m": binder_result.stutter_translation_m,
                    "bounded_stutter_translation_consumed_before_m": (
                        self.bounded_stutter_translation_consumed_m
                    ),
                    "bounded_stutter_translation_consumed_after_m": (
                        stutter_translation_after_m
                    ),
                    "bounded_stutter_translation_budget_m": (
                        self.config.raw_binder.stutter_translation_bound_m
                    ),
                    "bounded_stutter_motion_command_norm": (
                        binder_result.stutter_motion_command_norm
                    ),
                    "bounded_stutter_motion_consumed_before": (
                        self.bounded_stutter_motion_consumed
                    ),
                    "bounded_stutter_motion_consumed_after": stutter_motion_after,
                    "bounded_stutter_motion_budget": (
                        self.config.raw_binder.stutter_motion_command_bound
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
                    "proposal_binding_digest": proposal.binding_digest,
                    "raw_binder_witness_digest": binder_result.witness_digest,
                    "raw_binder_config_digest": binder_result.config_digest,
                    "bounded_stutter": binder_result.bounded_stutter,
                    "bounded_stutter_count_before": self.bounded_stutter_count,
                    "bounded_stutter_no_progress_limit": (
                        self.config.raw_binder.stutter_no_progress_limit
                    ),
                    "bounded_stutter_translation_m": binder_result.stutter_translation_m,
                    "bounded_stutter_translation_consumed_before_m": (
                        self.bounded_stutter_translation_consumed_m
                    ),
                    "bounded_stutter_translation_consumed_after_m": (
                        stutter_translation_after_m
                    ),
                    "bounded_stutter_translation_budget_m": (
                        self.config.raw_binder.stutter_translation_bound_m
                    ),
                    "bounded_stutter_motion_command_norm": (
                        binder_result.stutter_motion_command_norm
                    ),
                    "bounded_stutter_motion_consumed_before": (
                        self.bounded_stutter_motion_consumed
                    ),
                    "bounded_stutter_motion_consumed_after": stutter_motion_after,
                    "bounded_stutter_motion_budget": (
                        self.config.raw_binder.stutter_motion_command_bound
                    ),
                    "proposal_admissible": True,
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
                    "raw_binder_witness_digest": binder_result.witness_digest,
                    "raw_binder_config_digest": binder_result.config_digest,
                    "bounded_stutter": binder_result.bounded_stutter,
                    "bounded_stutter_count_before": self.bounded_stutter_count,
                    "bounded_stutter_no_progress_limit": (
                        self.config.raw_binder.stutter_no_progress_limit
                    ),
                    "bounded_stutter_translation_consumed_after_m": (
                        stutter_translation_after_m
                    ),
                    "bounded_stutter_motion_consumed_after": stutter_motion_after,
                    "admissible": True,
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
                bounded_stutter=binder_result.bounded_stutter,
                bounded_stutter_index=(
                    self.bounded_stutter_count
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_no_progress_limit=(
                    self.config.raw_binder.stutter_no_progress_limit
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_translation_m=(
                    binder_result.stutter_translation_m
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_translation_consumed_before_m=(
                    self.bounded_stutter_translation_consumed_m
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_translation_budget_m=(
                    self.config.raw_binder.stutter_translation_bound_m
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_motion_command_norm=(
                    binder_result.stutter_motion_command_norm
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_motion_consumed_before=(
                    self.bounded_stutter_motion_consumed
                    if binder_result.bounded_stutter
                    else None
                ),
                bounded_stutter_motion_budget=(
                    self.config.raw_binder.stutter_motion_command_bound
                    if binder_result.bounded_stutter
                    else None
                ),
                semantic_attestations=self.supervisor.active_semantic_attestations,
                guard_attestations=guard_attestations,
                proposal_contract_attestation=proposal_attestation,
                filter_envelope_attestation=filter_attestation,
                pre_attestations=physical_attestations,
            )
            prefix_evaluation = self._evaluate_stage(
                WireStage.PREFIX_PRE,
                _prefix_wire_payload(
                    self.supervisor.mission,
                    contract,
                    monitor,
                    candidate,
                    binder_result,
                    now,
                    self.stage_request_ids.get(
                        WireStage.SEMANTIC,
                        f"python-reference:{WireStage.SEMANTIC.value}",
                    ),
                ),
            )
        except Exception as exc:
            return PrepareResult(
                StaticCheckResult.inconsistent(f"cannot construct typed prefix evidence: {exc}")
            )
        prefix_gate = self._static_evaluation_check(
            prefix_evaluation,
            WireStage.PREFIX_PRE,
        )
        if not prefix_gate.proven:
            return PrepareResult(prefix_gate)
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
            binder_result.bounded_stutter,
            self.bounded_stutter_count,
            self.bounded_stutter_translation_consumed_m,
            stutter_translation_after_m,
            self.bounded_stutter_motion_consumed,
            stutter_motion_after,
        )
        self.proposal_index += 1
        if binder_result.bounded_stutter:
            if self.bounded_stutter_deadline_ns is None:
                self.bounded_stutter_deadline_ns = contract.deadline_ns
            self.bounded_stutter_count += 1
            self.bounded_stutter_translation_consumed_m = stutter_translation_after_m
            self.bounded_stutter_motion_consumed = stutter_motion_after
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
        if prepared.bounded_stutter and (
            self.bounded_stutter_translation_consumed_m
            != prepared.bounded_stutter_translation_after_m
            or self.bounded_stutter_motion_consumed
            != prepared.bounded_stutter_motion_after
            or self.bounded_stutter_deadline_ns != contract.deadline_ns
        ):
            raise RuntimeError(
                "bounded stutter cumulative authorization budget state changed before observation"
            )
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
            cumulative_commands = commands[: index + 1]
            cumulative_displacement = _pose_distance(prepared.before_state, state)
            cumulative_translation_bound = _translation_bound(
                cumulative_commands, self.config
            )
            cumulative_limit = cumulative_translation_bound + self.config.model_error_m
            step_displacement = _pose_distance(previous_state, state)
            step_translation_bound = _translation_bound(
                (commands[index],), self.config
            )
            step_limit = step_translation_bound + self.config.model_error_m
            samples.append(
                PlantSample(
                    timestamp_ns=timestamp,
                    state_digest=digest_legacy_state(state),
                    command_digest=executed_digest,
                    hard_invariants_hold=_state_invariants_hold(state, safety_spec),
                    within_reachable_tube=_observed_tube_membership(
                        prepared.before_state,
                        state,
                        cumulative_commands,
                        safety_spec,
                        self.config,
                    ),
                    model_assumptions_hold=_model_assumptions_hold(
                        previous_state,
                        state,
                        commands[index],
                        self.config,
                    ),
                    kinematic_diagnostics=KinematicSampleDiagnostics(
                        cumulative_observed_displacement_m=cumulative_displacement,
                        cumulative_translation_bound_m=cumulative_translation_bound,
                        model_error_allowance_m=self.config.model_error_m,
                        cumulative_displacement_limit_m=cumulative_limit,
                        cumulative_displacement_margin_m=(
                            None
                            if cumulative_displacement is None
                            else cumulative_limit - cumulative_displacement
                        ),
                        step_observed_displacement_m=step_displacement,
                        step_translation_bound_m=step_translation_bound,
                        step_displacement_limit_m=step_limit,
                        step_displacement_margin_m=(
                            None
                            if step_displacement is None
                            else step_limit - step_displacement
                        ),
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
            contract,
            prepared.before_state,
            states_after,
            samples,
            prior_observed_atoms=monitor.observed_atoms,
        )
        events = tuple(item[0] for item in events_with_samples)
        if prepared.bounded_stutter:
            progress_atoms = set(contract.guarantees) | {
                f"phase:{contract.expected_next_phase}"
            }
            observed_progress = tuple(
                event.atom for event in events if event.atom in progress_atoms
            )
            if observed_progress:
                raise RuntimeError(
                    "bounded stutter produced contract progress; fail closed without phase advance: "
                    + ",".join(observed_progress)
                )
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
        observed_reference = self.supervisor.checker.check_observed_prefix(
            self.supervisor.mission,
            contract,
            record,
            (),
            evaluation_time,
            enforce_dispatch_observation_sla=(
                self.config.realtime_timing_enforced
            ),
        )
        try:
            observed_evaluation = self._evaluate_stage(
                WireStage.OBSERVED_PREFIX,
                _observed_wire_payload(
                    self.supervisor.mission,
                    record,
                    observed_reference,
                    self.stage_request_ids.get(
                        WireStage.PREFIX_PRE,
                        f"python-reference:{WireStage.PREFIX_PRE.value}",
                    ),
                    observation_times[-1],
                ),
            )
        except Exception as exc:
            return (
                MonitorCheckResult(
                    MonitorVerdict.INCONSISTENT,
                    monitor,
                    issues=(f"observed_prefix evaluator failed closed: {exc}",),
                ),
                record,
            )
        observed_gate = self._static_evaluation_check(
            observed_evaluation,
            WireStage.OBSERVED_PREFIX,
        )
        if self.evaluator is not None and not observed_gate.proven:
            failed_check = (
                observed_reference
                if not observed_reference.proven
                else observed_gate
            )
            return _monitor_result_from_static(failed_check, monitor), record

        monitor_reference = self.supervisor.checker.monitor_step(
            self.supervisor.mission,
            contract,
            monitor,
            record,
            post_attestations,
            evaluation_time,
            enforce_dispatch_observation_sla=(
                self.config.realtime_timing_enforced
            ),
        )
        try:
            monitor_evaluation = self._evaluate_stage(
                WireStage.MONITOR_STEP,
                _monitor_wire_payload(
                    self.supervisor.mission,
                    contract,
                    monitor,
                    record,
                    post_attestations,
                    evaluation_time,
                    self.stage_request_ids.get(
                        WireStage.OBSERVED_PREFIX,
                        f"python-reference:{WireStage.OBSERVED_PREFIX.value}",
                    ),
                ),
            )
        except Exception as exc:
            return (
                MonitorCheckResult(
                    MonitorVerdict.INCONSISTENT,
                    monitor,
                    issues=(f"monitor_step evaluator failed closed: {exc}",),
                ),
                record,
            )
        monitor_gate = self._monitor_evaluation_check(
            monitor_evaluation,
            monitor_reference,
            monitor,
        )
        if monitor_gate is not None:
            return monitor_gate, record
        result = self.supervisor.observe_prefix(
            record,
            post_attestations,
            now_ns=evaluation_time,
            enforce_dispatch_observation_sla=(
                self.config.realtime_timing_enforced
            ),
        )
        if self.active_execution is None:
            raise RuntimeError("CTDA execution chain was not initialised")
        self.active_execution = self.active_execution.append(record)
        if prepared.bounded_stutter and result.verdict is MonitorVerdict.SAFE_PENDING:
            if self.supervisor.active_phase != contract.phase_before:
                raise RuntimeError("bounded stutter advanced the semantic phase")
        if result.complete:
            self.active_execution = None
            self.bounded_stutter_count = 0
            self.bounded_stutter_translation_consumed_m = 0.0
            self.bounded_stutter_motion_consumed = 0.0
            self.bounded_stutter_deadline_ns = None
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


def bind_raw_proposal(
    mission: Any,
    contract: SemanticSkillContract,
    state: Any,
    commands: Sequence[Any],
    config: RawProposalBinderConfig,
) -> RawProposalBinderResult:
    """Conservatively bind a raw Pick/Place prefix to the active mission contract.

    This consumer-side function intentionally has no policy metadata argument.  A
    producer cannot upgrade its verdict by supplying ``admissible``, a contract id,
    an expected effect, or a symbolic action.
    """

    state_digest = digest_legacy_state(state)
    command_digest = digest_payload(commands)

    def result(
        verdict: StaticVerdict,
        *issues: str,
        bounded_stutter: bool = False,
        stutter_translation_m: float = 0.0,
        stutter_motion_command_norm: float = 0.0,
    ) -> RawProposalBinderResult:
        return RawProposalBinderResult(
            verdict=verdict,
            mission_digest=mission.spec_digest,
            contract_digest=contract.contract_digest,
            state_digest=state_digest,
            command_digest=command_digest,
            config_digest=config.config_digest,
            issues=tuple(issues),
            bounded_stutter=bounded_stutter,
            stutter_translation_m=stutter_translation_m,
            stutter_motion_command_norm=stutter_motion_command_norm,
        )

    if not mission.verify_integrity() or not contract.verify_integrity():
        return result(StaticVerdict.INCONSISTENT, "raw binder received a tampered mission or contract")
    if contract.spec_digest != mission.spec_digest or contract.spec_id != mission.spec_id:
        return result(StaticVerdict.REFUTED, "raw binder contract is not rooted in the frozen mission")
    if _has_unknown_observation(state):
        return result(
            StaticVerdict.UNKNOWN,
            "raw binder trusted observation is incomplete; prefix safety witness is missing",
        )
    if contract.skill not in {"Pick", "Place"}:
        return result(StaticVerdict.UNKNOWN, "raw binder does not support this mission primitive")
    if contract.target is None or contract.target not in mission.object_ids:
        return result(StaticVerdict.REFUTED, "raw binder contract target is outside the frozen registry")
    objects = getattr(state, "objects", None)
    if not hasattr(objects, "get"):
        return result(StaticVerdict.UNKNOWN, "raw binder object observation is unavailable")
    target_object = objects.get(contract.target)
    if target_object is None:
        return result(StaticVerdict.UNKNOWN, "raw binder target observation is unavailable")
    robot_xyz = _binder_pose_xyz(getattr(state, "robot_pose", None))
    target_xyz = _binder_pose_xyz(getattr(target_object, "pose", None))
    if robot_xyz is None or target_xyz is None:
        return result(StaticVerdict.UNKNOWN, "raw binder target or robot pose is unavailable")
    if not commands:
        return result(StaticVerdict.REFUTED, "raw binder received an empty proposal")
    flattened = tuple(tuple(_flatten_command(command)) for command in commands)
    if any(len(command) < 4 for command in flattened):
        return result(StaticVerdict.UNKNOWN, "raw binder command lacks translation or gripper channels")
    if any(not all(isfinite(value) for value in command) for command in flattened):
        return result(StaticVerdict.REFUTED, "raw binder command contains a non-finite value")

    translation = tuple(sum(command[index] for command in flattened) for index in range(3))
    translation_norm = sqrt(sum(value * value for value in translation))
    predicted_translation_m = (
        sum(
            sqrt(sum(value * value for value in command[:3]))
            for command in flattened
        )
        * config.translation_scale_m
    )
    cumulative_motion_command_norm = (
        sum(sqrt(sum(value * value for value in command[:6])) for command in flattened)
        if all(len(command) >= 7 for command in flattened)
        else float("inf")
    )
    if config.close_direction < 0:
        close_requested = any(
            command[-1] <= config.gripper_close_threshold for command in flattened
        )
        open_requested = any(
            command[-1] >= config.gripper_open_threshold for command in flattened
        )
    else:
        close_requested = any(
            command[-1] >= config.gripper_close_threshold for command in flattened
        )
        open_requested = any(
            command[-1] <= config.gripper_open_threshold for command in flattened
        )
    if close_requested and open_requested:
        return result(StaticVerdict.REFUTED, "raw binder proposal has conflicting gripper commands")

    held = getattr(state, "gripper_holding", None)
    if held not in (None, contract.target):
        return result(StaticVerdict.REFUTED, "raw binder observed the wrong held object")

    if contract.skill == "Pick":
        if held == contract.target:
            return result(StaticVerdict.REFUTED, "raw binder Pick contract target is already held")
        if contract.part is None or (contract.target, contract.part) not in mission.safe_parts:
            return result(StaticVerdict.REFUTED, "raw binder Pick contract has no unique safe grasp part")
        target_delta = tuple(target - robot for target, robot in zip(target_xyz, robot_xyz))
        target_distance = sqrt(sum(value * value for value in target_delta))
        if close_requested and target_distance > config.grasp_neighborhood_m:
            return result(StaticVerdict.REFUTED, "raw binder closes outside the target neighborhood")
        bounded_stutter = bool(
            config.bounded_stutter_enabled
            and not close_requested
            and predicted_translation_m <= config.stutter_translation_bound_m
            and cumulative_motion_command_norm
            <= config.stutter_motion_command_bound
        )
        if bounded_stutter:
            return result(
                StaticVerdict.PROVEN,
                bounded_stutter=True,
                stutter_translation_m=predicted_translation_m,
                stutter_motion_command_norm=cumulative_motion_command_norm,
            )
        if translation_norm > config.direction_epsilon:
            direction_dot = sum(
                command * target for command, target in zip(translation, target_delta)
            )
            if direction_dot <= config.direction_epsilon:
                return result(StaticVerdict.REFUTED, "raw binder Pick prefix moves away from the mission target")
        elif not close_requested:
            return result(StaticVerdict.UNKNOWN, "raw binder Pick prefix establishes neither approach nor grasp")
        return result(StaticVerdict.PROVEN)

    if held != contract.target:
        return result(StaticVerdict.REFUTED, "raw binder Place prefix is not carrying the mission target")
    if contract.region is None or contract.region not in mission.region_ids:
        return result(StaticVerdict.REFUTED, "raw binder Place region is outside the frozen registry")
    regions = getattr(state, "regions", None)
    region = regions.get(contract.region) if hasattr(regions, "get") else None
    region_xyz = _binder_pose_xyz(getattr(region, "center", None)) if region is not None else None
    if region is None or region_xyz is None:
        return result(StaticVerdict.UNKNOWN, "raw binder Place region observation is unavailable")
    region_delta = tuple(region_value - object_value for region_value, object_value in zip(region_xyz, target_xyz))
    if translation_norm > config.direction_epsilon:
        direction_dot = sum(
            command * target for command, target in zip(translation, region_delta)
        )
        if direction_dot <= config.direction_epsilon:
            return result(StaticVerdict.REFUTED, "raw binder Place prefix moves away from the mission region")
    if open_requested:
        predicted = tuple(
            value + delta * config.translation_scale_m
            for value, delta in zip(target_xyz, translation)
        )
        radius = getattr(region, "radius", None)
        if type(radius) not in (int, float) or not isfinite(float(radius)) or float(radius) < 0:
            return result(StaticVerdict.UNKNOWN, "raw binder Place region radius is unavailable")
        predicted_distance = sqrt(
            sum((value - center) ** 2 for value, center in zip(predicted, region_xyz))
        )
        if predicted_distance > float(radius):
            return result(StaticVerdict.REFUTED, "raw binder releases outside the mission region")
    return result(StaticVerdict.PROVEN)


def _binder_pose_xyz(value: Any) -> tuple[float, float, float] | None:
    try:
        result = (float(value.x), float(value.y), float(value.z))
    except (AttributeError, TypeError, ValueError):
        return None
    return result if all(isfinite(item) for item in result) else None


def _guarantee_formula(
    guarantees: Sequence[str],
    deadline_ns: int,
) -> dict[str, Any]:
    atoms = [
        {"tag": "atom", "name": str(atom), "expected": True}
        for atom in sorted(set(guarantees))
    ]
    if not atoms:
        raise ValueError("wire contract guarantee is empty")
    item: dict[str, Any] = atoms[0] if len(atoms) == 1 else {"tag": "all", "items": atoms}
    return {"tag": "eventually", "item": item, "deadline_ns": deadline_ns}


def _semantic_wire_payload(
    mission: Any,
    active_phase: str,
    contract: SemanticSkillContract,
    now_ns: int,
) -> dict[str, Any]:
    obligations = tuple(
        item for item in mission.phase_obligations if item.source_phase == active_phase
    )
    binding_set = {
        (item.target, item.part, item.region) for item in obligations
    }
    obligation_target: str | None = None
    obligation_part: str | None = None
    obligation_region: str | None = None
    if len(binding_set) == 1:
        obligation_target, obligation_part, obligation_region = next(iter(binding_set))
    return {
        "mission_digest": mission.spec_digest,
        "contract_spec_digest": contract.spec_digest,
        "contract_digest": contract.contract_digest,
        "active_phase": active_phase,
        "contract_phase": contract.phase_before,
        "enabled_obligation_ids": [item.obligation_id for item in obligations],
        "contract_obligation_ids": list(contract.advances_obligations),
        "contract_target": contract.target,
        "obligation_target": obligation_target,
        "contract_part": contract.part,
        "obligation_part": obligation_part,
        "contract_region": contract.region,
        "obligation_region": obligation_region,
        "mission_integrity": mission.verify_integrity(),
        "contract_integrity": contract.verify_integrity(),
        "issued_at_ns": contract.issued_at_ns,
        "deadline_ns": contract.deadline_ns,
        "now_ns": now_ns,
        "guarantee": _guarantee_formula(contract.guarantees, contract.deadline_ns),
    }


def _prefix_wire_payload(
    mission: Any,
    contract: SemanticSkillContract,
    monitor: Any,
    candidate: PrefixCandidate,
    binder: RawProposalBinderResult,
    now_ns: int,
    semantic_request_id: str,
) -> dict[str, Any]:
    proposal = candidate.proposal
    authorization = candidate.authorization
    return {
        "semantic_request_id": semantic_request_id,
        "semantic_verdict": WireStaticVerdict.PROVEN.value,
        "mission_digest": mission.spec_digest,
        "contract_spec_digest": contract.spec_digest,
        "contract_digest": contract.contract_digest,
        "binder_verdict": binder.verdict.value,
        "state_digest": binder.state_digest,
        "authorization_state_digest": authorization.state_digest,
        "monitor_digest": monitor.monitor_state_digest,
        "authorization_monitor_digest": authorization.monitor_state_digest,
        "episode_nonce": mission.episode_nonce,
        "authorization_nonce": authorization.episode_nonce,
        "proposal_index": proposal.proposal_index,
        "authorization_proposal_index": authorization.proposal_index,
        "monitor_last_proposal_index": monitor.last_proposal_index,
        "proposal_digest": proposal.proposal_digest,
        "authorization_proposal_digest": authorization.proposal_digest,
        "command_digest": binder.command_digest,
        "authorization_command_digest": authorization.authorized_command_digest,
        "time_base_digest": mission.time_base.time_base_digest,
        "authorization_time_base_digest": authorization.time_base_digest,
        "now_ns": now_ns,
        "issued_at_ns": authorization.issued_at_ns,
        "valid_until_ns": authorization.valid_until_ns,
        "duration_ns": authorization.max_authorized_duration_ns,
    }


def _observed_wire_payload(
    mission: Any,
    record: PrefixExecutionRecord,
    plant_check: StaticCheckResult,
    prefix_request_id: str,
    observed_ns: int,
) -> dict[str, Any]:
    authorization = record.candidate.authorization
    receipt = record.receipt
    return {
        "prefix_request_id": prefix_request_id,
        "prefix_verdict": WireStaticVerdict.PROVEN.value,
        "plant_verdict": plant_check.verdict.value,
        "authorization_digest": authorization.authorization_digest,
        "receipt_authorization_digest": receipt.authorization_digest,
        "episode_nonce": mission.episode_nonce,
        "receipt_episode_nonce": authorization.episode_nonce,
        "authorized_command_digest": authorization.authorized_command_digest,
        "dispatched_command_digest": receipt.executed_command_digest,
        "receipt_command_digest": receipt.executed_command_digest,
        "mission_time_base_digest": mission.time_base.time_base_digest,
        "plant_time_base_digest": record.plant_trace.time_base_digest,
        "dispatch_ns": receipt.executed_at_ns,
        "observed_ns": observed_ns,
        "receipt_digest": receipt.receipt_digest,
        "plant_trace_digest": record.plant_trace.plant_trace_digest,
        "event_trace_digest": record.event_trace.symbolic_event_trace_digest,
    }


def _monitor_wire_payload(
    mission: Any,
    contract: SemanticSkillContract,
    monitor: Any,
    record: PrefixExecutionRecord,
    post_attestations: Sequence[EvidenceAttestation],
    now_ns: int,
    observed_request_id: str,
) -> dict[str, Any]:
    current_atoms = tuple(event.atom for event in record.event_trace.events)
    accumulated_atoms = set(monitor.observed_atoms) | set(current_atoms)
    terminal_atom = f"phase:{contract.expected_next_phase}"
    terminal_seen = terminal_atom in current_atoms
    completion_witness = bool(
        terminal_seen and set(contract.guarantees).issubset(accumulated_atoms)
    )
    post_types = {item.evidence_type for item in post_attestations}
    post_evidence = set(contract.post_requirements).issubset(post_types)
    return {
        "observed_request_id": observed_request_id,
        "observed_verdict": WireStaticVerdict.PROVEN.value,
        "mission_digest": mission.spec_digest,
        "contract_spec_digest": contract.spec_digest,
        "episode_nonce": mission.episode_nonce,
        "monitor_episode_nonce": monitor.episode_nonce,
        "contract_digest": contract.contract_digest,
        "monitor_contract_digest": (
            contract.contract_digest
            if monitor.contract_id == contract.contract_id
            else monitor.contract_id
        ),
        "active_phase": contract.phase_before,
        "monitor_phase": monitor.phase,
        "previous_monitor_digest": monitor.monitor_state_digest,
        "record_monitor_before_digest": record.monitor_before_digest,
        "previous_last_timestamp_ns": monitor.last_event_timestamp_ns,
        "event_timestamps_ns": sorted(
            {event.timestamp_ns for event in record.event_trace.events}
        ),
        "previous_observed_atoms": list(monitor.observed_atoms),
        "current_observed_atoms": list(current_atoms),
        "guarantee": _guarantee_formula(contract.guarantees, contract.deadline_ns),
        "invariant": {
            "tag": "atom",
            "name": "collision",
            "expected": False,
        },
        "expected_phase": contract.expected_next_phase,
        "terminal_phase_event": terminal_seen,
        "completion_witness": completion_witness,
        "post_evidence": post_evidence,
        "now_ns": now_ns,
        "deadline_ns": contract.deadline_ns,
        "next_proposal_index": record.candidate.proposal.proposal_index + 1,
        "record_proposal_index": record.candidate.proposal.proposal_index,
    }


def _monitor_result_from_static(
    result: StaticCheckResult,
    monitor_state: Any,
) -> MonitorCheckResult:
    if result.verdict is StaticVerdict.UNKNOWN:
        verdict = MonitorVerdict.UNKNOWN
    elif result.verdict is StaticVerdict.INCONSISTENT:
        verdict = MonitorVerdict.INCONSISTENT
    else:
        verdict = MonitorVerdict.VIOLATED
    return MonitorCheckResult(verdict, monitor_state, issues=result.issues)


def _has_unknown_observation(state: Any) -> bool:
    return bool(_unknown_observations(state))


def _unknown_observations(state: Any) -> frozenset[str]:
    notes = getattr(state, "notes", ()) or ()
    prefixes = (
        "ctda_unknown_observation:",
        "missing trusted CTDA observation:",
    )
    return frozenset(
        text.removeprefix(prefix).strip()
        for note in notes
        for text in (str(note),)
        for prefix in prefixes
        if text.startswith(prefix) and text.removeprefix(prefix).strip()
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
    required_observations: set[str] = set()
    if getattr(safety_spec, "require_no_collision", True):
        required_observations.update(("collision", "cost"))
    for invariant in checked_invariants:
        if invariant == "no_collision":
            required_observations.update(("collision", "cost"))
        elif invariant.startswith("human_clearance>=") or invariant.startswith(
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
            required_observations.add(
                "min_distance_to_human_hand"
                if invariant.startswith("human_clearance>=")
                else "min_distance_to_obstacle"
            )
        else:
            issues.append(f"unsupported fallback invariant: {invariant}")
    required_margin = max((configured_margin, *invariant_thresholds))
    ordered_required_observations = tuple(
        name
        for name in (
            "collision",
            "cost",
            "min_distance_to_human_hand",
            "min_distance_to_obstacle",
        )
        if name in required_observations
    )

    human: float | None = None
    obstacle: float | None = None
    no_collision: bool | None = None
    unknown_observations: frozenset[str] = frozenset()
    if state_after is None:
        issues.append("fallback post-state is unavailable")
    else:
        unknown_observations = _unknown_observations(state_after)
        unknown_required = unknown_observations & required_observations
        if unknown_required:
            issues.append(
                "fallback post-state contains unknown required safety observations: "
                + ", ".join(sorted(unknown_required))
            )
        if "collision" in required_observations and "collision" not in unknown_observations:
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
            if attribute not in required_observations or attribute in unknown_observations:
                continue
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

    no_cost: bool | None = None
    if "cost" in required_observations and "cost" not in unknown_observations:
        no_cost = _environment_no_cost(environment_info)
        if no_cost is None:
            issues.append("fallback cost observation is unavailable")
        elif not no_cost:
            issues.append("fallback action incurred an environment cost")
    if observation_error:
        issues.append(f"fallback observation failed: {observation_error}")

    distance_thresholds_hold = bool(
        (
            "min_distance_to_human_hand" not in required_observations
            or (human is not None and human >= required_margin)
        )
        and (
            "min_distance_to_obstacle" not in required_observations
            or (obstacle is not None and obstacle >= required_margin)
        )
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
    observation_availability = {
        "collision": no_collision is not None,
        "cost": no_cost is not None,
        "min_distance_to_human_hand": human is not None,
        "min_distance_to_obstacle": obstacle is not None,
    }
    observation_complete = bool(
        state_after is not None
        and not observation_error
        and not (unknown_observations & required_observations)
        and all(
            observation_availability[name]
            for name in ordered_required_observations
        )
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
        required_observations=ordered_required_observations,
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
    required = margin + _translation_bound(commands, config) + config.model_error_m
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
        and displacement
        <= _translation_bound(cumulative_commands, config) + config.model_error_m + 1e-9
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
    return displacement <= _translation_bound((command,), config) + config.model_error_m + 1e-9


def _kinematic_assumptions(
    config: ConditionalKinematicConfig,
    safety_spec: Any,
) -> tuple[str, ...]:
    return (
        f"delta_translation_scale_m={config.translation_scale_m}",
        f"model_error_m={config.model_error_m}",
        f"command_abs_bound={config.max_command_abs}",
        f"clearance_margin_m={float(getattr(safety_spec, 'safety_margin', 0.0))}",
        f"timing_policy_id={config.timing_policy_id}",
        "dispatch_to_observation_sla_enforced="
        f"{str(config.realtime_timing_enforced).lower()}",
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
    *,
    prior_observed_atoms: Sequence[str] = (),
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
        guarantees_seen = set(prior_observed_atoms) | {event.atom for event, _ in events}
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
    "RawProposalBinderConfig",
    "RawProposalBinderResult",
    "bind_raw_proposal",
]
