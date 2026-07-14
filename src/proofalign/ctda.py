"""Core runtime objects for Contract-Carrying Temporal Dual Alignment (CTDA).

The module deliberately contains no simulator or Lean integration.  It defines the
immutable boundary objects exchanged by those components and a fail-closed Python
reference checker for the staged protocol::

    mission -> semantic contract -> proposal -> authorization -> receipt
            -> plant trace -> symbolic trace

The Python checker is not a replacement for the planned Lean reflection theorems.
It is useful as an executable schema, an integration guard, and an oracle for unit
tests while the Lean definitions are brought up to parity.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
import re
import time
from typing import Any, Iterable, Mapping, Protocol, Sequence


def _canonical(value: Any) -> Any:
    """Return a JSON-compatible, deterministic representation of ``value``."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _canonical(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("CTDA digest mappings require string keys")
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=_canonical_sort_key)
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("non-finite floats are not valid CTDA digest payloads")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported digest payload type: {type(value).__name__}")


def _canonical_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_payload(value: Any) -> str:
    """Compute the canonical SHA-256 digest used by CTDA bindings."""

    encoded = json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def canonical_json(value: Any) -> str:
    """Serialize supported CTDA/legacy model values in their digest representation."""

    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def digest_text(value: str) -> str:
    """Convenience helper for callers that need a digest for an opaque artifact."""

    return sha256(value.encode("utf-8")).hexdigest()


def _init_payload(value: Any) -> dict[str, Any]:
    """Payload of constructor fields, excluding computed ``init=False`` digests."""

    return {item.name: getattr(value, item.name) for item in fields(value) if item.init}


def _computed_digest(value: Any) -> str:
    return digest_payload(_init_payload(value))


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_optional_bool(name: str, value: bool | None) -> None:
    if value is not None and type(value) is not bool:
        raise TypeError(f"{name} must be bool or None")


def _require_bool(name: str, value: bool) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def _freeze_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _freeze_evidence(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(_freeze_strings(values))))


@dataclass(frozen=True)
class EvidenceAttestation:
    """Typed, bounded evidence whose authenticity is checked by ``EvidenceVerifier``.

    ``proof_digest`` is intentionally opaque to this module.  A production verifier
    can interpret it as a signature, proof object, MAC, or handle into a proof store.
    Hash integrity alone never makes an attestation trusted.
    """

    evidence_type: str
    subject_digest: str
    producer_id: str
    producer_version: str
    issued_at_ns: int
    valid_until_ns: int
    payload_digest: str
    proof_digest: str
    assumptions: tuple[str, ...] = ()
    attestation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "evidence_type",
            "subject_digest",
            "producer_id",
            "producer_version",
            "payload_digest",
            "proof_digest",
        ):
            _require_text(name, getattr(self, name))
        if self.issued_at_ns < 0 or self.valid_until_ns < self.issued_at_ns:
            raise ValueError("evidence validity window is invalid")
        object.__setattr__(self, "assumptions", _freeze_evidence(self.assumptions))
        object.__setattr__(self, "attestation_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.attestation_digest == _computed_digest(self)

    def is_fresh(self, now_ns: int) -> bool:
        return self.issued_at_ns <= now_ns <= self.valid_until_ns


class EvidenceVerifier(Protocol):
    """Authenticates an evidence attestation after structural checks."""

    def verify(self, attestation: EvidenceAttestation) -> bool:
        ...


class DigestAllowlistEvidenceVerifier:
    """Exact-attestation verifier useful for tests and trusted local adapters.

    Production deployments should generally provide a signature/proof verifier.
    Merely claiming an allowlisted producer id is deliberately insufficient.
    """

    def __init__(self, trusted_attestation_digests: Iterable[str] = ()) -> None:
        self._trusted = set(trusted_attestation_digests)

    def trust(self, *attestations: EvidenceAttestation) -> None:
        self._trusted.update(item.attestation_digest for item in attestations)

    def verify(self, attestation: EvidenceAttestation) -> bool:
        return (
            attestation.verify_integrity()
            and attestation.attestation_digest in self._trusted
        )


class StaticVerdict(str, Enum):
    PROVEN = "proven"
    REFUTED = "refuted"
    UNKNOWN = "unknown"
    INCONSISTENT = "inconsistent"


class TruthValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class MonitorVerdict(str, Enum):
    COMPLETE = "complete"
    VIOLATED = "violated"
    SAFE_PENDING = "safe_pending"
    UNKNOWN = "unknown"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class StaticCheckResult:
    verdict: StaticVerdict
    witness_ref: str | None = None
    issues: tuple[str, ...] = ()

    @property
    def proven(self) -> bool:
        return self.verdict is StaticVerdict.PROVEN

    @classmethod
    def success(cls, witness_ref: str) -> "StaticCheckResult":
        return cls(StaticVerdict.PROVEN, witness_ref=witness_ref)

    @classmethod
    def refuted(cls, *issues: str) -> "StaticCheckResult":
        return cls(StaticVerdict.REFUTED, issues=tuple(issues))

    @classmethod
    def unknown(cls, *issues: str) -> "StaticCheckResult":
        return cls(StaticVerdict.UNKNOWN, issues=tuple(issues))

    @classmethod
    def inconsistent(cls, *issues: str) -> "StaticCheckResult":
        return cls(StaticVerdict.INCONSISTENT, issues=tuple(issues))


@dataclass(frozen=True)
class MonitorCheckResult:
    verdict: MonitorVerdict
    monitor_state: "ContractMonitorState"
    witness_ref: str | None = None
    issues: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.verdict is MonitorVerdict.COMPLETE

    @property
    def may_continue(self) -> bool:
        return self.verdict is MonitorVerdict.SAFE_PENDING


@dataclass(frozen=True)
class AuthorityEnvelope:
    """Attestation metadata; signature verification occurs outside this module."""

    authority_id: str
    source: str
    version: str
    attestation_digest: str
    authenticated: bool = False
    attestation: EvidenceAttestation | None = None
    envelope_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("authority_id", "source", "version", "attestation_digest"):
            _require_text(name, getattr(self, name))
        _require_bool("authenticated", self.authenticated)
        object.__setattr__(self, "envelope_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.envelope_digest == _computed_digest(self) and (
            self.attestation is None or self.attestation.verify_integrity()
        )


@dataclass(frozen=True)
class TimeBase:
    clock_id: str
    control_period_ns: int
    max_jitter_ns: int
    monitor_latency_ns: int
    switch_latency_ns: int
    time_base_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("clock_id", self.clock_id)
        if self.control_period_ns <= 0:
            raise ValueError("control_period_ns must be positive")
        for name in ("max_jitter_ns", "monitor_latency_ns", "switch_latency_ns"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        object.__setattr__(self, "time_base_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.time_base_digest == _computed_digest(self)


@dataclass(frozen=True)
class TaskTransition:
    source_phase: str
    skill: str
    destination_phase: str

    def __post_init__(self) -> None:
        _require_text("source_phase", self.source_phase)
        _require_text("skill", self.skill)
        _require_text("destination_phase", self.destination_phase)


@dataclass(frozen=True)
class PhaseObligation:
    """Typed residual-goal obligation advanced by one automaton transition."""

    obligation_id: str
    source_phase: str
    skill: str
    destination_phase: str
    guarantees: tuple[str, ...]
    target: str | None = None
    part: str | None = None
    region: str | None = None
    completes_goal: bool = False

    def __post_init__(self) -> None:
        for name in ("obligation_id", "source_phase", "skill", "destination_phase"):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "guarantees", _freeze_evidence(self.guarantees))
        _require_bool("completes_goal", self.completes_goal)
        if not self.guarantees:
            raise ValueError("phase obligation must declare at least one guarantee")


@dataclass(frozen=True)
class MissionSpec:
    """Authenticated and deeply frozen task/safety root for one episode."""

    spec_id: str
    authority: AuthorityEnvelope
    instruction_digest: str
    goal: str
    phases: tuple[str, ...]
    transitions: tuple[TaskTransition, ...]
    initial_phase: str
    time_base: TimeBase
    episode_nonce: str
    hard_invariants: tuple[str, ...] = ()
    object_ids: tuple[str, ...] = ()
    region_ids: tuple[str, ...] = ()
    safe_parts: tuple[tuple[str, str], ...] = ()
    forbidden_objects: tuple[str, ...] = ()
    forbidden_parts: tuple[str, ...] = ()
    default_must_preserve: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    goal_atoms: tuple[str, ...] = ()
    goal_phases: tuple[str, ...] = ()
    phase_obligations: tuple[PhaseObligation, ...] = ()
    mission_claim_digest: str = field(init=False)
    spec_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "spec_id",
            "instruction_digest",
            "goal",
            "initial_phase",
            "episode_nonce",
        ):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "phases", _freeze_strings(self.phases))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        for name in (
            "hard_invariants",
            "object_ids",
            "region_ids",
            "forbidden_objects",
            "forbidden_parts",
            "default_must_preserve",
        ):
            object.__setattr__(self, name, _freeze_strings(getattr(self, name)))
        object.__setattr__(
            self,
            "safe_parts",
            tuple((str(object_id), str(part)) for object_id, part in self.safe_parts),
        )
        object.__setattr__(self, "required_evidence", _freeze_evidence(self.required_evidence))
        object.__setattr__(self, "goal_atoms", _freeze_evidence(self.goal_atoms))
        object.__setattr__(self, "goal_phases", _freeze_evidence(self.goal_phases))
        object.__setattr__(self, "phase_obligations", tuple(self.phase_obligations))
        if not self.phases or len(set(self.phases)) != len(self.phases):
            raise ValueError("phases must be a non-empty unique sequence")
        if self.initial_phase not in self.phases:
            raise ValueError("initial_phase is not declared in phases")
        if not set(self.goal_phases).issubset(self.phases):
            raise ValueError("goal phase is not declared in phases")
        for transition in self.transitions:
            if transition.source_phase not in self.phases or transition.destination_phase not in self.phases:
                raise ValueError("task transition references an undeclared phase")
        obligation_ids = [item.obligation_id for item in self.phase_obligations]
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("phase obligation ids must be unique")
        for obligation in self.phase_obligations:
            transition = TaskTransition(
                obligation.source_phase,
                obligation.skill,
                obligation.destination_phase,
            )
            if transition not in self.transitions:
                raise ValueError("phase obligation references an undeclared transition")
        goal_obligations = [item for item in self.phase_obligations if item.completes_goal]
        if self.goal_atoms and goal_obligations:
            for obligation in goal_obligations:
                if not set(self.goal_atoms).issubset(obligation.guarantees):
                    raise ValueError("goal-completing obligation does not imply mission goal atoms")
        object.__setattr__(
            self,
            "mission_claim_digest",
            digest_payload(self.unsigned_payload()),
        )
        object.__setattr__(self, "spec_digest", _computed_digest(self))

    def unsigned_payload(self) -> dict[str, Any]:
        """Canonical authority-signed payload, excluding signatures and final digests."""

        return {
            "spec_id": self.spec_id,
            "authority": {
                "authority_id": self.authority.authority_id,
                "source": self.authority.source,
                "version": self.authority.version,
            },
            "instruction_digest": self.instruction_digest,
            "goal": self.goal,
            "phases": self.phases,
            "transitions": self.transitions,
            "initial_phase": self.initial_phase,
            "time_base": self.time_base,
            "episode_nonce": self.episode_nonce,
            "hard_invariants": self.hard_invariants,
            "object_ids": self.object_ids,
            "region_ids": self.region_ids,
            "safe_parts": self.safe_parts,
            "forbidden_objects": self.forbidden_objects,
            "forbidden_parts": self.forbidden_parts,
            "default_must_preserve": self.default_must_preserve,
            "required_evidence": self.required_evidence,
            "goal_atoms": self.goal_atoms,
            "goal_phases": self.goal_phases,
            "phase_obligations": self.phase_obligations,
        }

    def verify_integrity(self) -> bool:
        return (
            self.spec_digest == _computed_digest(self)
            and self.mission_claim_digest == digest_payload(self.unsigned_payload())
            and self.authority.verify_integrity()
            and self.time_base.verify_integrity()
        )

    @property
    def frozen(self) -> bool:
        return True


def mission_unsigned_payload(mission: MissionSpec) -> dict[str, Any]:
    """Return the deterministic payload an authority must attest."""

    return mission.unsigned_payload()


def bind_mission_authority(
    mission: MissionSpec,
    attestation: EvidenceAttestation,
) -> MissionSpec:
    """Second stage of mission construction, without a signature/digest cycle."""

    if attestation.evidence_type != "authority":
        raise ValueError("mission authority attestation has the wrong evidence type")
    if attestation.subject_digest != mission.mission_claim_digest:
        raise ValueError("mission authority attestation is bound to another mission claim")
    if attestation.producer_id != mission.authority.authority_id:
        raise ValueError("mission authority attestation has the wrong producer")
    if attestation.producer_version != mission.authority.version:
        raise ValueError("mission authority attestation has the wrong producer version")
    bound = replace(
        mission,
        authority=replace(
            mission.authority,
            attestation_digest=attestation.attestation_digest,
            authenticated=True,
            attestation=attestation,
        ),
    )
    if bound.mission_claim_digest != mission.mission_claim_digest:
        raise AssertionError("binding authority changed the unsigned mission claim")
    return bound


@dataclass(frozen=True)
class SemanticSkillContract:
    """A semantic contract that persists across one or more policy proposals."""

    contract_id: str
    spec_id: str
    spec_digest: str
    phase_before: str
    expected_next_phase: str
    skill: str
    issued_at_ns: int
    deadline_ns: int
    target: str | None = None
    part: str | None = None
    region: str | None = None
    guards: tuple[str, ...] = ()
    guarantees: tuple[str, ...] = ()
    may_modify: tuple[str, ...] = ()
    must_preserve: tuple[str, ...] = ()
    fallback_id: str = "hold"
    semantic_pre_requirements: tuple[str, ...] = ()
    physical_pre_requirements: tuple[str, ...] = ()
    runtime_requirements: tuple[str, ...] = ()
    post_requirements: tuple[str, ...] = ()
    advances_obligations: tuple[str, ...] = ()
    contract_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "spec_id",
            "spec_digest",
            "phase_before",
            "expected_next_phase",
            "skill",
            "fallback_id",
        ):
            _require_text(name, getattr(self, name))
        if self.issued_at_ns < 0 or self.deadline_ns <= self.issued_at_ns:
            raise ValueError("contract deadline must be after its issue time")
        for name in ("guards", "guarantees", "may_modify", "must_preserve"):
            object.__setattr__(self, name, _freeze_strings(getattr(self, name)))
        for name in (
            "semantic_pre_requirements",
            "physical_pre_requirements",
            "runtime_requirements",
            "post_requirements",
            "advances_obligations",
        ):
            object.__setattr__(self, name, _freeze_evidence(getattr(self, name)))
        object.__setattr__(self, "contract_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.contract_digest == _computed_digest(self)


@dataclass(frozen=True)
class ActionProposalBinding:
    contract_id: str
    contract_digest: str
    proposal_index: int
    proposal_digest: str
    proposed_horizon_ns: int
    issued_at_ns: int = 0
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("contract_id", "contract_digest", "proposal_digest"):
            _require_text(name, getattr(self, name))
        if self.proposal_index < 0:
            raise ValueError("proposal_index must be non-negative")
        if self.proposed_horizon_ns <= 0 or self.issued_at_ns < 0:
            raise ValueError("proposal horizon must be positive and issue time non-negative")
        object.__setattr__(self, "binding_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.binding_digest == _computed_digest(self)


@dataclass(frozen=True)
class PrefixAuthorization:
    contract_id: str
    contract_digest: str
    spec_digest: str
    episode_nonce: str
    state_digest: str
    monitor_state_digest: str
    proposal_index: int
    proposal_digest: str
    authorized_command_digest: str
    filter_policy_digest: str
    dynamics_model_digest: str
    time_base_digest: str
    tube_digest: str
    max_authorized_duration_ns: int
    fallback_id: str
    issued_at_ns: int
    valid_until_ns: int
    semantic_witness_digest: str = ""
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "contract_digest",
            "spec_digest",
            "episode_nonce",
            "state_digest",
            "monitor_state_digest",
            "proposal_digest",
            "authorized_command_digest",
            "filter_policy_digest",
            "dynamics_model_digest",
            "time_base_digest",
            "tube_digest",
            "fallback_id",
        ):
            _require_text(name, getattr(self, name))
        if self.proposal_index < 0 or self.max_authorized_duration_ns <= 0:
            raise ValueError("invalid authorization proposal index or duration")
        if self.issued_at_ns < 0 or self.valid_until_ns <= self.issued_at_ns:
            raise ValueError("authorization validity window is empty")
        object.__setattr__(self, "authorization_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.authorization_digest == _computed_digest(self)

    def is_fresh(self, now_ns: int) -> bool:
        return self.issued_at_ns <= now_ns <= self.valid_until_ns


@dataclass(frozen=True)
class ReachableTube:
    authorized_command_digest: str
    dynamics_model_digest: str
    duration_ns: int
    fallback_id: str
    all_prefixes_safe: bool | None
    all_cut_states_recoverable: bool | None
    witness_digest: str
    assumptions: tuple[str, ...] = ()
    attestation: EvidenceAttestation | None = None
    claim_digest: str = field(init=False)
    tube_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "authorized_command_digest",
            "dynamics_model_digest",
            "fallback_id",
            "witness_digest",
        ):
            _require_text(name, getattr(self, name))
        if self.duration_ns <= 0:
            raise ValueError("tube duration must be positive")
        _require_optional_bool("all_prefixes_safe", self.all_prefixes_safe)
        _require_optional_bool(
            "all_cut_states_recoverable", self.all_cut_states_recoverable
        )
        object.__setattr__(self, "assumptions", _freeze_strings(self.assumptions))
        object.__setattr__(
            self,
            "claim_digest",
            digest_payload(
                {
                    "authorized_command_digest": self.authorized_command_digest,
                    "dynamics_model_digest": self.dynamics_model_digest,
                    "duration_ns": self.duration_ns,
                    "fallback_id": self.fallback_id,
                    "all_prefixes_safe": self.all_prefixes_safe,
                    "all_cut_states_recoverable": self.all_cut_states_recoverable,
                    "witness_digest": self.witness_digest,
                    "assumptions": self.assumptions,
                }
            ),
        )
        object.__setattr__(self, "tube_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.tube_digest == _computed_digest(self) and (
            self.attestation is None or self.attestation.verify_integrity()
        )


@dataclass(frozen=True)
class PrefixCandidate:
    proposal: ActionProposalBinding
    authorization: PrefixAuthorization
    tube: ReachableTube
    proposal_contract_witness_digest: str
    filter_envelope_witness_digest: str
    proposal_admissible: bool | None
    filter_preserves_contract: bool | None
    pre_evidence: tuple[str, ...] = ()
    semantic_attestations: tuple[EvidenceAttestation, ...] = ()
    guard_attestations: tuple[EvidenceAttestation, ...] = ()
    proposal_contract_attestation: EvidenceAttestation | None = None
    filter_envelope_attestation: EvidenceAttestation | None = None
    pre_attestations: tuple[EvidenceAttestation, ...] = ()
    candidate_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("proposal_contract_witness_digest", self.proposal_contract_witness_digest)
        _require_text("filter_envelope_witness_digest", self.filter_envelope_witness_digest)
        _require_optional_bool("proposal_admissible", self.proposal_admissible)
        _require_optional_bool("filter_preserves_contract", self.filter_preserves_contract)
        object.__setattr__(self, "pre_evidence", _freeze_evidence(self.pre_evidence))
        object.__setattr__(self, "semantic_attestations", tuple(self.semantic_attestations))
        object.__setattr__(self, "guard_attestations", tuple(self.guard_attestations))
        object.__setattr__(self, "pre_attestations", tuple(self.pre_attestations))
        object.__setattr__(self, "candidate_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return (
            self.candidate_digest == _computed_digest(self)
            and self.proposal.verify_integrity()
            and self.authorization.verify_integrity()
            and self.tube.verify_integrity()
            and all(item.verify_integrity() for item in self.semantic_attestations)
            and all(item.verify_integrity() for item in self.guard_attestations)
            and all(item.verify_integrity() for item in self.pre_attestations)
            and (
                self.proposal_contract_attestation is None
                or self.proposal_contract_attestation.verify_integrity()
            )
            and (
                self.filter_envelope_attestation is None
                or self.filter_envelope_attestation.verify_integrity()
            )
        )


@dataclass(frozen=True)
class ExecutionReceipt:
    authorization_digest: str
    authorized_command_digest: str
    executed_command_digest: str
    actuator_evidence_digest: str
    executed_at_ns: int
    within_authorized_error: bool | None
    attestation: EvidenceAttestation | None = None
    claim_digest: str = field(init=False)
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "authorization_digest",
            "authorized_command_digest",
            "executed_command_digest",
            "actuator_evidence_digest",
        ):
            _require_text(name, getattr(self, name))
        if self.executed_at_ns < 0:
            raise ValueError("receipt execution time must be non-negative")
        _require_optional_bool("within_authorized_error", self.within_authorized_error)
        object.__setattr__(
            self,
            "claim_digest",
            digest_payload(
                {
                    "authorization_digest": self.authorization_digest,
                    "authorized_command_digest": self.authorized_command_digest,
                    "executed_command_digest": self.executed_command_digest,
                    "actuator_evidence_digest": self.actuator_evidence_digest,
                    "executed_at_ns": self.executed_at_ns,
                    "within_authorized_error": self.within_authorized_error,
                }
            ),
        )
        object.__setattr__(self, "receipt_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.receipt_digest == _computed_digest(self) and (
            self.attestation is None or self.attestation.verify_integrity()
        )


@dataclass(frozen=True)
class KinematicSampleDiagnostics:
    cumulative_observed_displacement_m: float | None
    cumulative_translation_bound_m: float
    model_error_allowance_m: float
    cumulative_displacement_limit_m: float
    cumulative_displacement_margin_m: float | None
    step_observed_displacement_m: float | None
    step_translation_bound_m: float
    step_displacement_limit_m: float
    step_displacement_margin_m: float | None

    def __post_init__(self) -> None:
        for name in (
            "cumulative_observed_displacement_m",
            "cumulative_translation_bound_m",
            "model_error_allowance_m",
            "cumulative_displacement_limit_m",
            "cumulative_displacement_margin_m",
            "step_observed_displacement_m",
            "step_translation_bound_m",
            "step_displacement_limit_m",
            "step_displacement_margin_m",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be finite or None")
        for name in (
            "cumulative_translation_bound_m",
            "model_error_allowance_m",
            "cumulative_displacement_limit_m",
            "step_translation_bound_m",
            "step_displacement_limit_m",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class PlantSample:
    timestamp_ns: int
    state_digest: str
    command_digest: str
    hard_invariants_hold: bool | None
    within_reachable_tube: bool | None
    model_assumptions_hold: bool | None
    kinematic_diagnostics: KinematicSampleDiagnostics | None = None

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("plant timestamp must be non-negative")
        _require_text("state_digest", self.state_digest)
        _require_text("command_digest", self.command_digest)
        _require_optional_bool("hard_invariants_hold", self.hard_invariants_hold)
        _require_optional_bool("within_reachable_tube", self.within_reachable_tube)
        _require_optional_bool("model_assumptions_hold", self.model_assumptions_hold)


@dataclass(frozen=True)
class PlantTrace:
    time_base_digest: str
    samples: tuple[PlantSample, ...]
    observer_evidence_digest: str
    attestation: EvidenceAttestation | None = None
    claim_digest: str = field(init=False)
    plant_trace_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("time_base_digest", self.time_base_digest)
        _require_text("observer_evidence_digest", self.observer_evidence_digest)
        object.__setattr__(self, "samples", tuple(self.samples))
        object.__setattr__(
            self,
            "claim_digest",
            digest_payload(
                {
                    "time_base_digest": self.time_base_digest,
                    "samples": self.samples,
                    "observer_evidence_digest": self.observer_evidence_digest,
                }
            ),
        )
        object.__setattr__(self, "plant_trace_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.plant_trace_digest == _computed_digest(self) and (
            self.attestation is None or self.attestation.verify_integrity()
        )

    @property
    def duration_ns(self) -> int:
        if len(self.samples) < 2:
            return 0
        return self.samples[-1].timestamp_ns - self.samples[0].timestamp_ns

    @property
    def final_state_digest(self) -> str | None:
        return self.samples[-1].state_digest if self.samples else None


@dataclass(frozen=True)
class SymbolicEvent:
    timestamp_ns: int
    atom: str
    value: "TruthValue | bool" = True
    object_id: str | None = None
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("event timestamp must be non-negative")
        _require_text("atom", self.atom)
        if isinstance(self.value, bool):
            object.__setattr__(
                self,
                "value",
                TruthValue.TRUE if self.value else TruthValue.FALSE,
            )
        elif not isinstance(self.value, TruthValue):
            raise TypeError("symbolic event value must be TruthValue or bool")


@dataclass(frozen=True)
class AbstractionLink:
    event_index: int
    plant_sample_index: int
    atom: str
    derivation_digest: str

    def __post_init__(self) -> None:
        if self.event_index < 0 or self.plant_sample_index < 0:
            raise ValueError("trace abstraction indices must be non-negative")
        _require_text("atom", self.atom)
        _require_text("derivation_digest", self.derivation_digest)


@dataclass(frozen=True)
class TraceAbstractionEvidence:
    plant_trace_digest: str
    time_base_digest: str
    events_digest: str
    links: tuple[AbstractionLink, ...]
    producer_id: str
    producer_version: str
    witness_digest: str
    attestation: EvidenceAttestation | None = None
    claim_digest: str = field(init=False)
    abstraction_evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "plant_trace_digest",
            "time_base_digest",
            "events_digest",
            "producer_id",
            "producer_version",
            "witness_digest",
        ):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "links", tuple(self.links))
        object.__setattr__(
            self,
            "claim_digest",
            digest_payload(
                {
                    "plant_trace_digest": self.plant_trace_digest,
                    "time_base_digest": self.time_base_digest,
                    "events_digest": self.events_digest,
                    "links": self.links,
                    "producer_id": self.producer_id,
                    "producer_version": self.producer_version,
                    "witness_digest": self.witness_digest,
                }
            ),
        )
        object.__setattr__(self, "abstraction_evidence_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.abstraction_evidence_digest == _computed_digest(self) and (
            self.attestation is None or self.attestation.verify_integrity()
        )


@dataclass(frozen=True)
class SymbolicEventTrace:
    time_base_digest: str
    plant_trace_digest: str
    abstraction_evidence_digest: str
    events: tuple[SymbolicEvent, ...]
    symbolic_event_trace_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("time_base_digest", "plant_trace_digest", "abstraction_evidence_digest"):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "symbolic_event_trace_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return self.symbolic_event_trace_digest == _computed_digest(self)


@dataclass(frozen=True)
class PrefixExecutionRecord:
    candidate: PrefixCandidate
    receipt: ExecutionReceipt
    plant_trace: PlantTrace
    event_trace: SymbolicEventTrace
    abstraction_evidence: TraceAbstractionEvidence
    monitor_before_digest: str
    monitor_after_digest: str
    runtime_evidence: tuple[str, ...] = ()
    runtime_attestations: tuple[EvidenceAttestation, ...] = ()
    record_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("monitor_before_digest", self.monitor_before_digest)
        _require_text("monitor_after_digest", self.monitor_after_digest)
        object.__setattr__(self, "runtime_evidence", _freeze_evidence(self.runtime_evidence))
        object.__setattr__(self, "runtime_attestations", tuple(self.runtime_attestations))
        object.__setattr__(self, "record_digest", _computed_digest(self))

    def verify_integrity(self) -> bool:
        return (
            self.record_digest == _computed_digest(self)
            and self.candidate.verify_integrity()
            and self.receipt.verify_integrity()
            and self.plant_trace.verify_integrity()
            and self.event_trace.verify_integrity()
            and self.abstraction_evidence.verify_integrity()
            and all(item.verify_integrity() for item in self.runtime_attestations)
        )


@dataclass(frozen=True)
class ContractExecution:
    contract_id: str
    spec_digest: str
    episode_nonce: str
    initial_state_digest: str
    initial_monitor_state_digest: str
    prefixes: tuple[PrefixExecutionRecord, ...] = ()
    execution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "spec_digest",
            "episode_nonce",
            "initial_state_digest",
            "initial_monitor_state_digest",
        ):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "prefixes", tuple(self.prefixes))
        object.__setattr__(self, "execution_digest", _computed_digest(self))

    def append(self, record: PrefixExecutionRecord) -> "ContractExecution":
        if record.candidate.proposal.contract_id != self.contract_id:
            raise ValueError("record belongs to another contract")
        return replace(self, prefixes=self.prefixes + (record,))

    def verify_integrity(self) -> bool:
        return self.execution_digest == _computed_digest(self) and all(
            record.verify_integrity() for record in self.prefixes
        )


@dataclass(frozen=True)
class ContractMonitorState:
    contract_id: str
    spec_digest: str
    phase: str
    episode_nonce: str
    completed_guarantees: tuple[str, ...] = ()
    observed_atoms: tuple[str, ...] = ()
    accepted_events: tuple[SymbolicEvent, ...] = ()
    last_proposal_index: int = -1
    last_event_timestamp_ns: int = -1
    monitor_state_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("contract_id", "spec_digest", "phase", "episode_nonce"):
            _require_text(name, getattr(self, name))
        object.__setattr__(self, "completed_guarantees", _freeze_evidence(self.completed_guarantees))
        object.__setattr__(self, "observed_atoms", _freeze_evidence(self.observed_atoms))
        object.__setattr__(self, "accepted_events", tuple(self.accepted_events))
        if self.last_proposal_index < -1 or self.last_event_timestamp_ns < -1:
            raise ValueError("invalid monitor sequence counters")
        object.__setattr__(self, "monitor_state_digest", _computed_digest(self))

    @classmethod
    def initial(cls, mission: MissionSpec, contract: SemanticSkillContract) -> "ContractMonitorState":
        return cls(
            contract.contract_id,
            mission.spec_digest,
            contract.phase_before,
            mission.episode_nonce,
        )

    def verify_integrity(self) -> bool:
        return self.monitor_state_digest == _computed_digest(self)

    def history_is_well_formed(self) -> bool:
        return (
            all(
                left.timestamp_ns <= right.timestamp_ns
                for left, right in zip(self.accepted_events, self.accepted_events[1:])
            )
            and (
                (
                    not self.accepted_events
                    and self.last_event_timestamp_ns == -1
                )
                or (
                    bool(self.accepted_events)
                    and self.accepted_events[-1].timestamp_ns
                    == self.last_event_timestamp_ns
                )
            )
        )


def advance_monitor_state(
    contract: SemanticSkillContract,
    state: ContractMonitorState,
    event_trace: SymbolicEventTrace,
    proposal_index: int,
) -> ContractMonitorState:
    """Pure persistent-monitor transition used by runtime and tests."""

    atoms = set(state.observed_atoms)
    completed = set(state.completed_guarantees)
    accepted_events = list(state.accepted_events)
    phase = state.phase
    last_timestamp = state.last_event_timestamp_ns
    for event in event_trace.events:
        if event.value is TruthValue.TRUE:
            atoms.add(event.atom)
            if event.atom in contract.guarantees:
                completed.add(event.atom)
            if event.atom == f"phase:{contract.expected_next_phase}":
                phase = contract.expected_next_phase
        elif event.value is TruthValue.FALSE:
            atoms.discard(event.atom)
            completed.discard(event.atom)
            if (
                event.atom == f"phase:{contract.expected_next_phase}"
                and phase == contract.expected_next_phase
            ):
                phase = contract.phase_before
        last_timestamp = max(last_timestamp, event.timestamp_ns)
        accepted_events.append(event)
    return ContractMonitorState(
        contract_id=state.contract_id,
        spec_digest=state.spec_digest,
        phase=phase,
        episode_nonce=state.episode_nonce,
        completed_guarantees=tuple(completed),
        observed_atoms=tuple(atoms),
        accepted_events=tuple(accepted_events),
        last_proposal_index=proposal_index,
        last_event_timestamp_ns=last_timestamp,
    )


def semantic_witness_digest(
    mission: MissionSpec,
    current_phase: str,
    contract: SemanticSkillContract,
    attestations: Iterable[EvidenceAttestation],
) -> str:
    """Deterministic witness reference bound into every prefix authorization."""

    return digest_payload(
        {
            "spec_digest": mission.spec_digest,
            "current_phase": current_phase,
            "contract_digest": contract.contract_digest,
            "advances_obligations": contract.advances_obligations,
            "attestations": sorted(item.attestation_digest for item in attestations),
        }
    )


def proposal_contract_subject_digest(
    contract: SemanticSkillContract,
    proposal: ActionProposalBinding,
    proposal_admissible: bool | None,
    witness_digest: str,
) -> str:
    _require_optional_bool("proposal_admissible", proposal_admissible)
    _require_text("witness_digest", witness_digest)
    return digest_payload(
        {
            "contract_digest": contract.contract_digest,
            "proposal_binding_digest": proposal.binding_digest,
            "proposal_admissible": proposal_admissible,
            "witness_digest": witness_digest,
        }
    )


def filter_envelope_subject_digest(
    contract: SemanticSkillContract,
    proposal: ActionProposalBinding,
    authorization: PrefixAuthorization,
    filter_preserves_contract: bool | None,
    witness_digest: str,
) -> str:
    _require_optional_bool("filter_preserves_contract", filter_preserves_contract)
    _require_text("witness_digest", witness_digest)
    return digest_payload(
        {
            "contract_digest": contract.contract_digest,
            "proposal_binding_digest": proposal.binding_digest,
            "authorization_digest": authorization.authorization_digest,
            "filter_policy_digest": authorization.filter_policy_digest,
            "authorized_command_digest": authorization.authorized_command_digest,
            "filter_preserves_contract": filter_preserves_contract,
            "witness_digest": witness_digest,
        }
    )


def guard_subject_digest(
    contract: SemanticSkillContract,
    state_digest: str,
    monitor_state_digest: str,
) -> str:
    _require_text("state_digest", state_digest)
    _require_text("monitor_state_digest", monitor_state_digest)
    return digest_payload(
        {
            "contract_digest": contract.contract_digest,
            "state_digest": state_digest,
            "monitor_state_digest": monitor_state_digest,
        }
    )


class CTDAChecker:
    """Fail-closed executable checker for the CTDA staged protocol."""

    def __init__(
        self,
        trusted_authorities: Iterable[str] | None = None,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> None:
        # ``None`` no longer means trust everyone.  An empty set is fail-closed.
        self.trusted_authorities = frozenset(trusted_authorities or ())
        self.evidence_verifier = evidence_verifier
        self._authorization_ledger: dict[str, tuple[int, str]] = {}

    def clear_authorization_ledger(self) -> None:
        self._authorization_ledger.clear()

    def _attestation_issue(
        self,
        attestation: EvidenceAttestation | None,
        *,
        evidence_type: str,
        subject_digest: str,
        now_ns: int,
        required_assumptions: Iterable[str] = (),
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
        if not set(required_assumptions).issubset(attestation.assumptions):
            return f"{evidence_type} attestation omits required assumptions"
        if self.evidence_verifier is None or not self.evidence_verifier.verify(attestation):
            return f"{evidence_type} attestation is not authenticated by the configured verifier"
        return None

    def _verified_evidence_kinds(
        self,
        attestations: Iterable[EvidenceAttestation],
        *,
        subject_digest: str,
        now_ns: int,
    ) -> tuple[set[str], list[str]]:
        kinds: set[str] = set()
        issues: list[str] = []
        for item in attestations:
            if not isinstance(item, EvidenceAttestation):
                issues.append("untyped evidence cannot satisfy a CTDA requirement")
                continue
            issue = self._attestation_issue(
                item,
                evidence_type=item.evidence_type,
                subject_digest=subject_digest,
                now_ns=now_ns,
            )
            if issue is None:
                kinds.add(item.evidence_type)
            else:
                issues.append(issue)
        return kinds, issues

    def check_mission_spec(
        self,
        mission: MissionSpec,
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        if not mission.verify_integrity():
            return StaticCheckResult.inconsistent("mission or nested digest integrity failure")
        if mission.authority.authority_id not in self.trusted_authorities:
            return StaticCheckResult.refuted("mission authority is outside the trusted authority set")
        if not mission.goal_atoms or not mission.goal_phases or not mission.phase_obligations:
            return StaticCheckResult.refuted("mission has no typed goal/phase obligations")
        if not any(item.completes_goal for item in mission.phase_obligations):
            return StaticCheckResult.refuted("mission has no goal-completing obligation")
        now = time.monotonic_ns() if now_ns is None else now_ns
        issue = self._attestation_issue(
            mission.authority.attestation,
            evidence_type="authority",
            subject_digest=mission.mission_claim_digest,
            now_ns=now,
            producer_id=mission.authority.authority_id,
            producer_version=mission.authority.version,
        )
        if issue is not None:
            return StaticCheckResult.refuted(issue)
        return StaticCheckResult.success(mission.spec_digest)

    def check_semantic_refinement(
        self,
        mission: MissionSpec,
        current_phase: str,
        contract: SemanticSkillContract,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        now = time.monotonic_ns() if now_ns is None else now_ns
        evidence_items = tuple(evidence)
        mission_result = self.check_mission_spec(mission, now)
        if not mission_result.proven:
            return mission_result
        if not contract.verify_integrity():
            return StaticCheckResult.inconsistent("contract digest integrity failure")

        refutations: list[str] = []
        if contract.spec_id != mission.spec_id or contract.spec_digest != mission.spec_digest:
            refutations.append("contract is not bound to the frozen mission")
        if current_phase != contract.phase_before:
            refutations.append("contract phase does not match the active task phase")
        transition = TaskTransition(contract.phase_before, contract.skill, contract.expected_next_phase)
        if transition not in mission.transitions:
            refutations.append("skill is not an allowed task-automaton transition")
        if not contract.guarantees:
            refutations.append("contract trace language is empty: no guarantee is declared")
        obligations = {
            item.obligation_id: item for item in mission.phase_obligations
        }
        advanced = set(contract.advances_obligations)
        enabled = {
            item.obligation_id: item
            for item in mission.phase_obligations
            if item.source_phase == contract.phase_before
            and item.skill == contract.skill
            and item.destination_phase == contract.expected_next_phase
        }
        if not advanced:
            refutations.append("contract advances no residual mission obligation")
        if not advanced.issubset(enabled):
            refutations.append("contract advances an obligation outside its task transition")
        if enabled and not set(enabled).issubset(advanced):
            refutations.append("contract omits an enabled phase obligation")
        for obligation_id in advanced & set(obligations):
            obligation = obligations[obligation_id]
            if not set(obligation.guarantees).issubset(contract.guarantees):
                refutations.append(
                    f"contract guarantees do not imply obligation {obligation_id}"
                )
            if obligation.target is not None and contract.target != obligation.target:
                refutations.append(f"contract target differs from obligation {obligation_id}")
            if obligation.part is not None and contract.part != obligation.part:
                refutations.append(f"contract part differs from obligation {obligation_id}")
            if obligation.region is not None and contract.region != obligation.region:
                refutations.append(f"contract region differs from obligation {obligation_id}")
        if contract.expected_next_phase in mission.goal_phases:
            advanced_items = [obligations[item] for item in advanced if item in obligations]
            if not advanced_items or not all(item.completes_goal for item in advanced_items):
                refutations.append("transition enters a goal phase without discharging the mission goal")
        if set(contract.may_modify) & set(contract.must_preserve):
            refutations.append("an object is both may-modify and must-preserve")
        if contract.target is not None and contract.target not in contract.may_modify:
            refutations.append("contract target is not declared may-modify")
        if mission.object_ids and not set(contract.may_modify).issubset(mission.object_ids):
            refutations.append("contract may-modify set leaves the frozen object registry")
        if not set(mission.default_must_preserve).issubset(set(contract.must_preserve)):
            refutations.append("contract omits a mission-level must-preserve object")
        if contract.target is not None and mission.object_ids and contract.target not in mission.object_ids:
            refutations.append("contract target is not in the frozen object registry")
        if contract.region is not None and mission.region_ids and contract.region not in mission.region_ids:
            refutations.append("contract region is not in the frozen region registry")
        if contract.target in mission.forbidden_objects:
            refutations.append("contract targets a forbidden object")
        if contract.part in mission.forbidden_parts:
            refutations.append("contract targets a forbidden part")
        if contract.skill == "Pick" and contract.part is None:
            refutations.append("Pick contract must name a safe grasp part")
        if contract.part is not None and mission.safe_parts:
            if (contract.target or "", contract.part) not in mission.safe_parts:
                refutations.append("contract part has no safe-affordance binding")
        if now < contract.issued_at_ns:
            refutations.append("contract is not yet active")
        if now > contract.deadline_ns:
            refutations.append("contract deadline has expired")
        if refutations:
            return StaticCheckResult.refuted(*refutations)

        required = (
            mission.required_evidence
            + contract.semantic_pre_requirements
        )
        verified, evidence_issues = self._verified_evidence_kinds(
            evidence_items,
            subject_digest=contract.contract_digest,
            now_ns=now,
        )
        if evidence_issues:
            return StaticCheckResult.refuted(*evidence_issues)
        missing = _missing_evidence(required, verified)
        if missing:
            return StaticCheckResult.unknown(*(f"missing semantic evidence: {item}" for item in missing))
        return StaticCheckResult.success(
            semantic_witness_digest(mission, current_phase, contract, evidence_items)
        )

    def check_prefix_pre(
        self,
        mission: MissionSpec,
        contract: SemanticSkillContract,
        state_digest: str,
        monitor_state: ContractMonitorState,
        candidate: PrefixCandidate,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
        *,
        commit: bool = True,
    ) -> StaticCheckResult:
        """Check and optionally consume an execution authorization."""

        now = time.monotonic_ns() if now_ns is None else now_ns
        evidence_items = tuple(evidence)
        if not candidate.verify_integrity() or not monitor_state.verify_integrity():
            return StaticCheckResult.inconsistent("candidate or monitor digest integrity failure")
        if not monitor_state.history_is_well_formed():
            return StaticCheckResult.inconsistent("persistent monitor history is not time ordered")
        mission_result = self.check_mission_spec(mission, now)
        if not mission_result.proven:
            return mission_result
        if not contract.verify_integrity():
            return StaticCheckResult.inconsistent("contract digest integrity failure")

        proposal = candidate.proposal
        authorization = candidate.authorization
        tube = candidate.tube
        refutations: list[str] = []
        semantic = self.check_semantic_refinement(
            mission,
            contract.phase_before,
            contract,
            candidate.semantic_attestations,
            authorization.issued_at_ns,
        )
        if semantic.verdict is StaticVerdict.INCONSISTENT:
            return semantic
        if semantic.verdict is StaticVerdict.REFUTED:
            refutations.extend(semantic.issues)
        elif semantic.verdict is StaticVerdict.UNKNOWN:
            return semantic
        elif authorization.semantic_witness_digest != semantic.witness_ref:
            refutations.append("authorization is not bound to the semantic refinement witness")
        if proposal.contract_id != contract.contract_id or proposal.contract_digest != contract.contract_digest:
            refutations.append("proposal is not bound to the active semantic contract")
        if authorization.contract_id != contract.contract_id or authorization.contract_digest != contract.contract_digest:
            refutations.append("authorization is not bound to the active semantic contract")
        if authorization.spec_digest != mission.spec_digest:
            refutations.append("authorization spec digest does not match the frozen mission")
        if authorization.episode_nonce != mission.episode_nonce:
            refutations.append("authorization episode nonce does not match the mission")
        if authorization.state_digest != state_digest:
            refutations.append("authorization was issued for a different state")
        if authorization.monitor_state_digest != monitor_state.monitor_state_digest:
            refutations.append("authorization was issued for a different monitor state")
        if monitor_state.contract_id != contract.contract_id or monitor_state.spec_digest != mission.spec_digest:
            refutations.append("monitor state is not bound to this contract and mission")
        if monitor_state.episode_nonce != mission.episode_nonce:
            refutations.append("monitor state belongs to another episode")
        if monitor_state.phase != contract.phase_before:
            refutations.append("monitor is no longer in the contract source phase")
        if proposal.proposal_index != authorization.proposal_index:
            refutations.append("proposal index does not match authorization")
        if proposal.proposal_digest != authorization.proposal_digest:
            refutations.append("proposal digest does not match authorization")
        if proposal.issued_at_ns > authorization.issued_at_ns:
            refutations.append("authorization predates its proposal")
        if authorization.issued_at_ns < contract.issued_at_ns:
            refutations.append("authorization predates its semantic contract")
        if authorization.time_base_digest != mission.time_base.time_base_digest:
            refutations.append("authorization uses a different time base")
        if authorization.tube_digest != tube.tube_digest:
            refutations.append("authorization is not bound to the supplied reachable tube")
        if authorization.authorized_command_digest != tube.authorized_command_digest:
            refutations.append("tube is not bound to the authorized command")
        if authorization.dynamics_model_digest != tube.dynamics_model_digest:
            refutations.append("tube uses a different dynamics model")
        if authorization.fallback_id != tube.fallback_id or authorization.fallback_id != contract.fallback_id:
            refutations.append("fallback binding differs across contract, authorization, and tube")
        if authorization.max_authorized_duration_ns > proposal.proposed_horizon_ns:
            refutations.append("authorization exceeds the policy proposal horizon")
        if authorization.max_authorized_duration_ns > tube.duration_ns:
            refutations.append("reachable tube does not cover the authorized duration")
        if authorization.valid_until_ns - authorization.issued_at_ns < authorization.max_authorized_duration_ns:
            refutations.append("validity window cannot cover the authorized duration")
        if now + authorization.max_authorized_duration_ns > min(
            authorization.valid_until_ns,
            contract.deadline_ns,
        ):
            refutations.append("remaining authorization window cannot cover the prefix duration")
        if now > contract.deadline_ns:
            refutations.append("active semantic contract deadline has expired")
        if authorization.valid_until_ns > contract.deadline_ns:
            refutations.append("authorization outlives the active semantic contract")
        if not authorization.is_fresh(now):
            refutations.append("authorization is stale or not yet valid")
        if commit:
            previous = self._authorization_ledger.get(contract.contract_id)
            if previous is not None:
                previous_index, previous_digest = previous
                if authorization.authorization_digest == previous_digest:
                    refutations.append("authorization replay detected")
                elif proposal.proposal_index <= previous_index:
                    refutations.append("proposal index is not strictly monotonic")
        if monitor_state.last_proposal_index >= proposal.proposal_index:
            refutations.append("proposal index does not advance the persistent monitor")
        if tube.all_prefixes_safe is False:
            refutations.append("reachable tube contains an unsafe prefix")
        if tube.all_cut_states_recoverable is False:
            refutations.append("an allowed cut state is outside the recoverable set")
        if candidate.proposal_admissible is False:
            refutations.append("proposal is outside the semantic contract envelope")
        if candidate.filter_preserves_contract is False:
            refutations.append("safety filter does not preserve the semantic contract envelope")
        attestation_checks = (
            (
                candidate.proposal_contract_attestation,
                "proposal_contract",
                proposal_contract_subject_digest(
                    contract,
                    proposal,
                    candidate.proposal_admissible,
                    candidate.proposal_contract_witness_digest,
                ),
                (),
            ),
            (
                candidate.filter_envelope_attestation,
                "filter_envelope",
                filter_envelope_subject_digest(
                    contract,
                    proposal,
                    authorization,
                    candidate.filter_preserves_contract,
                    candidate.filter_envelope_witness_digest,
                ),
                (),
            ),
            (
                tube.attestation,
                "reachable_tube",
                tube.claim_digest,
                tube.assumptions,
            ),
        )
        for attestation, evidence_type, subject, assumptions in attestation_checks:
            issue = self._attestation_issue(
                attestation,
                evidence_type=evidence_type,
                subject_digest=subject,
                now_ns=now,
                required_assumptions=assumptions,
            )
            if issue is not None:
                refutations.append(issue)
        guard_verified, guard_issues = self._verified_evidence_kinds(
            candidate.guard_attestations,
            subject_digest=guard_subject_digest(
                contract,
                state_digest,
                monitor_state.monitor_state_digest,
            ),
            now_ns=now,
        )
        refutations.extend(guard_issues)
        if refutations:
            return StaticCheckResult.refuted(*refutations)

        unknown: list[str] = []
        if tube.all_prefixes_safe is None:
            unknown.append("reachable-tube prefix safety witness is missing")
        if tube.all_cut_states_recoverable is None:
            unknown.append("terminal recoverability witness is missing")
        if candidate.proposal_admissible is None:
            unknown.append("proposal-to-contract admissibility witness is missing")
        if candidate.filter_preserves_contract is None:
            unknown.append("filter-envelope preservation witness is missing")
        missing_guards = _missing_evidence(
            tuple(f"guard:{guard}" for guard in contract.guards),
            guard_verified,
        )
        unknown.extend(f"missing dynamic guard evidence: {item}" for item in missing_guards)
        verified, evidence_issues = self._verified_evidence_kinds(
            tuple(candidate.pre_attestations) + evidence_items,
            subject_digest=authorization.authorization_digest,
            now_ns=now,
        )
        if evidence_issues:
            return StaticCheckResult.refuted(*evidence_issues)
        missing = _missing_evidence(contract.physical_pre_requirements, verified)
        unknown.extend(f"missing physical pre-evidence: {item}" for item in missing)
        if unknown:
            return StaticCheckResult.unknown(*unknown)

        if commit:
            self._authorization_ledger[contract.contract_id] = (
                proposal.proposal_index,
                authorization.authorization_digest,
            )
        return StaticCheckResult.success(authorization.authorization_digest)

    def check_trace_abstraction(
        self,
        plant_trace: PlantTrace,
        event_trace: SymbolicEventTrace,
        evidence: TraceAbstractionEvidence,
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        if not plant_trace.verify_integrity() or not event_trace.verify_integrity() or not evidence.verify_integrity():
            return StaticCheckResult.inconsistent("trace or abstraction digest integrity failure")
        refutations: list[str] = []
        if event_trace.plant_trace_digest != plant_trace.plant_trace_digest:
            refutations.append("symbolic trace is bound to another plant trace")
        if evidence.plant_trace_digest != plant_trace.plant_trace_digest:
            refutations.append("abstraction evidence is bound to another plant trace")
        if evidence.events_digest != digest_payload(event_trace.events):
            refutations.append("abstraction evidence is bound to different symbolic events")
        if event_trace.abstraction_evidence_digest != evidence.abstraction_evidence_digest:
            refutations.append("symbolic trace is bound to different abstraction evidence")
        if not (
            plant_trace.time_base_digest
            == event_trace.time_base_digest
            == evidence.time_base_digest
        ):
            refutations.append("plant, symbolic, and abstraction time bases differ")
        plant_times = [sample.timestamp_ns for sample in plant_trace.samples]
        event_times = [event.timestamp_ns for event in event_trace.events]
        if not _strictly_increasing(plant_times):
            refutations.append("plant sample timestamps are not strictly increasing")
        if not _nondecreasing(event_times):
            refutations.append("symbolic event timestamps are not monotonic")

        linked_events: set[int] = set()
        for link in evidence.links:
            if link.event_index >= len(event_trace.events) or link.plant_sample_index >= len(plant_trace.samples):
                refutations.append("abstraction link index is outside its trace")
                continue
            if link.event_index in linked_events:
                refutations.append("symbolic event has multiple abstraction links")
                continue
            linked_events.add(link.event_index)
            event = event_trace.events[link.event_index]
            sample = plant_trace.samples[link.plant_sample_index]
            if link.atom != event.atom:
                refutations.append("abstraction link atom differs from symbolic event")
            if event.timestamp_ns != sample.timestamp_ns:
                refutations.append("symbolic event timestamp is not sourced from its plant sample")
        if linked_events != set(range(len(event_trace.events))):
            refutations.append("not every symbolic event has exactly one provenance link")
        now = time.monotonic_ns() if now_ns is None else now_ns
        issue = self._attestation_issue(
            evidence.attestation,
            evidence_type="trace_abstraction",
            subject_digest=evidence.claim_digest,
            now_ns=now,
            producer_id=evidence.producer_id,
            producer_version=evidence.producer_version,
        )
        if issue is not None:
            refutations.append(issue)
        if refutations:
            return StaticCheckResult.refuted(*refutations)
        return StaticCheckResult.success(evidence.abstraction_evidence_digest)

    def check_observed_prefix(
        self,
        mission: MissionSpec,
        contract: SemanticSkillContract,
        record: PrefixExecutionRecord,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        if not record.verify_integrity():
            return StaticCheckResult.inconsistent("prefix execution record digest integrity failure")
        candidate = record.candidate
        authorization = candidate.authorization
        receipt = record.receipt
        trace = record.plant_trace
        evaluation_time = (
            trace.samples[-1].timestamp_ns
            if trace.samples
            else receipt.executed_at_ns
        )
        if now_ns is not None:
            evaluation_time = max(evaluation_time, now_ns)
        mission_result = self.check_mission_spec(mission, evaluation_time)
        if not mission_result.proven:
            return mission_result
        if not contract.verify_integrity():
            return StaticCheckResult.inconsistent("contract digest integrity failure")
        refutations: list[str] = []
        if (
            candidate.proposal.contract_id != contract.contract_id
            or candidate.proposal.contract_digest != contract.contract_digest
        ):
            refutations.append("executed prefix belongs to another contract")
        if (
            authorization.contract_id != contract.contract_id
            or authorization.contract_digest != contract.contract_digest
        ):
            refutations.append("executed authorization belongs to another contract")
        if authorization.spec_digest != mission.spec_digest:
            refutations.append("executed prefix belongs to another mission")
        if authorization.episode_nonce != mission.episode_nonce:
            refutations.append("executed prefix belongs to another episode")
        if candidate.proposal.proposal_index != authorization.proposal_index:
            refutations.append("executed proposal index differs from its authorization")
        if candidate.proposal.proposal_digest != authorization.proposal_digest:
            refutations.append("executed proposal digest differs from its authorization")
        if authorization.tube_digest != candidate.tube.tube_digest:
            refutations.append("executed authorization is bound to another reachable tube")
        if authorization.authorized_command_digest != candidate.tube.authorized_command_digest:
            refutations.append("executed tube is bound to another command")
        if receipt.authorization_digest != authorization.authorization_digest:
            refutations.append("execution receipt is not bound to the authorization")
        if receipt.authorized_command_digest != authorization.authorized_command_digest:
            refutations.append("receipt names a different authorized command")
        if receipt.executed_at_ns < authorization.issued_at_ns or receipt.executed_at_ns > authorization.valid_until_ns:
            refutations.append("command was dispatched outside the authorization window")
        if record.monitor_before_digest != authorization.monitor_state_digest:
            refutations.append("record starts from a different monitor state")
        if not trace.samples:
            refutations.append("plant trace is empty")
        else:
            if trace.samples[0].command_digest != receipt.executed_command_digest:
                refutations.append("plant trace is not bound to the executed command")
            if trace.samples[0].timestamp_ns < receipt.executed_at_ns:
                refutations.append("plant trace predates the execution receipt")
            if trace.duration_ns > authorization.max_authorized_duration_ns:
                refutations.append("observed plant trace exceeds the authorized duration")
            final_timestamp = trace.samples[-1].timestamp_ns
            if final_timestamp > receipt.executed_at_ns + authorization.max_authorized_duration_ns:
                refutations.append("plant trace ends beyond dispatch plus authorized duration")
            if final_timestamp > authorization.valid_until_ns:
                refutations.append("plant trace continues after authorization expiry")
            if final_timestamp > contract.deadline_ns:
                refutations.append("plant trace continues after the contract deadline")
        if trace.time_base_digest != mission.time_base.time_base_digest:
            refutations.append("plant trace uses a different time base")
        for sample in trace.samples:
            if sample.command_digest != receipt.executed_command_digest:
                refutations.append("plant trace contains a command outside the receipt")
                break
            if sample.hard_invariants_hold is False:
                refutations.append("a hard invariant was violated on an observed prefix")
            if sample.within_reachable_tube is False:
                refutations.append("observed plant state left the certified tube")
            if sample.model_assumptions_hold is False:
                refutations.append("a recorded dynamics/model assumption was violated")
        abstraction = self.check_trace_abstraction(
            record.plant_trace,
            record.event_trace,
            record.abstraction_evidence,
            evaluation_time,
        )
        if abstraction.verdict is StaticVerdict.INCONSISTENT:
            return abstraction
        if abstraction.verdict is StaticVerdict.REFUTED:
            refutations.extend(abstraction.issues)
        if receipt.within_authorized_error is False:
            refutations.append("actuation receipt exceeds the authorized error bound")
        receipt_issue = self._attestation_issue(
            receipt.attestation,
            evidence_type="actuator_receipt",
            subject_digest=receipt.claim_digest,
            now_ns=evaluation_time,
        )
        if receipt_issue is not None:
            refutations.append(receipt_issue)
        plant_issue = self._attestation_issue(
            trace.attestation,
            evidence_type="plant_trace",
            subject_digest=trace.claim_digest,
            now_ns=evaluation_time,
            required_assumptions=candidate.tube.assumptions,
        )
        if plant_issue is not None:
            refutations.append(plant_issue)
        if refutations:
            return StaticCheckResult.refuted(*refutations)

        unknown: list[str] = []
        if receipt.within_authorized_error is None:
            unknown.append("actuation error-bound evidence is missing")
        for sample in trace.samples:
            if sample.hard_invariants_hold is None:
                unknown.append("hard-invariant observation is missing")
            if sample.within_reachable_tube is None:
                unknown.append("tube-membership observation is missing")
            if sample.model_assumptions_hold is None:
                unknown.append("model-assumption observation is missing")
        verified, evidence_issues = self._verified_evidence_kinds(
            tuple(record.runtime_attestations) + tuple(evidence),
            subject_digest=trace.plant_trace_digest,
            now_ns=evaluation_time,
        )
        if evidence_issues:
            return StaticCheckResult.refuted(*evidence_issues)
        missing = _missing_evidence(contract.runtime_requirements, verified)
        unknown.extend(f"missing runtime evidence: {item}" for item in missing)
        if unknown:
            return StaticCheckResult.unknown(*tuple(dict.fromkeys(unknown)))
        return StaticCheckResult.success(record.record_digest)

    def check_execution_chain(
        self,
        execution: ContractExecution,
        contract: SemanticSkillContract,
    ) -> StaticCheckResult:
        if not execution.verify_integrity():
            return StaticCheckResult.inconsistent("contract execution digest integrity failure")
        refutations: list[str] = []
        if execution.contract_id != contract.contract_id or execution.spec_digest != contract.spec_digest:
            refutations.append("contract execution has the wrong contract or mission binding")
        previous_index = -1
        previous_state = execution.initial_state_digest
        previous_monitor = execution.initial_monitor_state_digest
        previous_issue_time = -1
        for record in execution.prefixes:
            proposal = record.candidate.proposal
            authorization = record.candidate.authorization
            if proposal.proposal_index <= previous_index:
                refutations.append("execution proposal indices are not strictly monotonic")
            if authorization.state_digest != previous_state:
                refutations.append("adjacent prefix state digests are discontinuous")
            if authorization.monitor_state_digest != previous_monitor:
                refutations.append("adjacent prefix monitor digests are discontinuous")
            if record.monitor_before_digest != previous_monitor:
                refutations.append("prefix monitor-before digest breaks the monitor chain")
            if authorization.issued_at_ns < previous_issue_time:
                refutations.append("authorization issue times move backwards")
            if record.plant_trace.final_state_digest is None:
                refutations.append("prefix has no terminal plant state")
            else:
                previous_state = record.plant_trace.final_state_digest
            previous_monitor = record.monitor_after_digest
            previous_index = proposal.proposal_index
            previous_issue_time = authorization.issued_at_ns
        if refutations:
            return StaticCheckResult.refuted(*refutations)
        return StaticCheckResult.success(execution.execution_digest)

    def monitor_step(
        self,
        mission: MissionSpec,
        contract: SemanticSkillContract,
        state: ContractMonitorState,
        record: PrefixExecutionRecord,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> MonitorCheckResult:
        evidence_items = tuple(evidence)
        pre = self.check_prefix_pre(
            mission,
            contract,
            record.candidate.authorization.state_digest,
            state,
            record.candidate,
            (),
            record.receipt.executed_at_ns,
            commit=False,
        )
        if pre.verdict is StaticVerdict.INCONSISTENT:
            return MonitorCheckResult(MonitorVerdict.INCONSISTENT, state, issues=pre.issues)
        if pre.verdict is StaticVerdict.REFUTED:
            return MonitorCheckResult(MonitorVerdict.VIOLATED, state, issues=pre.issues)
        if pre.verdict is StaticVerdict.UNKNOWN:
            return MonitorCheckResult(MonitorVerdict.UNKNOWN, state, issues=pre.issues)
        observed = self.check_observed_prefix(mission, contract, record, (), now_ns)
        if observed.verdict is StaticVerdict.INCONSISTENT:
            return MonitorCheckResult(MonitorVerdict.INCONSISTENT, state, issues=observed.issues)
        if observed.verdict is StaticVerdict.REFUTED:
            return MonitorCheckResult(MonitorVerdict.VIOLATED, state, issues=observed.issues)
        if observed.verdict is StaticVerdict.UNKNOWN:
            return MonitorCheckResult(MonitorVerdict.UNKNOWN, state, issues=observed.issues)
        if record.monitor_before_digest != state.monitor_state_digest:
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                state,
                issues=("runtime record does not continue the supplied monitor state",),
            )
        if state.last_proposal_index >= record.candidate.proposal.proposal_index:
            return MonitorCheckResult(
                MonitorVerdict.VIOLATED,
                state,
                issues=("runtime proposal index does not advance the monitor",),
            )
        if (
            state.last_event_timestamp_ns >= 0
            and record.event_trace.events
            and record.event_trace.events[0].timestamp_ns <= state.last_event_timestamp_ns
        ):
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                state,
                issues=("runtime event trace does not strictly extend monitor history",),
            )
        new_state = advance_monitor_state(
            contract, state, record.event_trace, record.candidate.proposal.proposal_index
        )
        if record.monitor_after_digest != new_state.monitor_state_digest:
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                state,
                issues=("recorded monitor-after digest does not match the monitor transition",),
            )
        violations = _event_violations(mission, record.event_trace)
        if violations:
            return MonitorCheckResult(MonitorVerdict.VIOLATED, new_state, issues=tuple(violations))
        now = time.monotonic_ns() if now_ns is None else now_ns
        if record.plant_trace.samples:
            now = max(now, record.plant_trace.samples[-1].timestamp_ns)
        if now > contract.deadline_ns:
            return MonitorCheckResult(
                MonitorVerdict.VIOLATED,
                new_state,
                issues=("contract deadline expired before completion was accepted",),
            )
        guarantees_complete = set(contract.guarantees).issubset(new_state.completed_guarantees)
        phase_complete = new_state.phase == contract.expected_next_phase
        if guarantees_complete and phase_complete:
            verified, evidence_issues = self._verified_evidence_kinds(
                evidence_items,
                subject_digest=record.event_trace.symbolic_event_trace_digest,
                now_ns=now,
            )
            if evidence_issues:
                return MonitorCheckResult(
                    MonitorVerdict.UNKNOWN,
                    new_state,
                    issues=tuple(evidence_issues),
                )
            missing = _missing_evidence(contract.post_requirements, verified)
            if missing:
                return MonitorCheckResult(
                    MonitorVerdict.UNKNOWN,
                    new_state,
                    issues=tuple(f"missing post evidence: {item}" for item in missing),
                )
            witness = digest_payload(
                {
                    "contract": contract.contract_digest,
                    "monitor": new_state.monitor_state_digest,
                    "record": record.record_digest,
                    "post_attestations": sorted(
                        item.attestation_digest for item in evidence_items
                    ),
                    "evaluation_time_ns": now,
                }
            )
            return MonitorCheckResult(MonitorVerdict.COMPLETE, new_state, witness_ref=witness)
        return MonitorCheckResult(MonitorVerdict.SAFE_PENDING, new_state)

    def check_contract_execution(
        self,
        mission: MissionSpec,
        contract: SemanticSkillContract,
        execution: ContractExecution,
        initial_monitor_state: ContractMonitorState,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> MonitorCheckResult:
        chain = self.check_execution_chain(execution, contract)
        if chain.verdict is StaticVerdict.INCONSISTENT:
            return MonitorCheckResult(MonitorVerdict.INCONSISTENT, initial_monitor_state, issues=chain.issues)
        if chain.verdict is StaticVerdict.REFUTED:
            return MonitorCheckResult(MonitorVerdict.VIOLATED, initial_monitor_state, issues=chain.issues)
        if execution.initial_monitor_state_digest != initial_monitor_state.monitor_state_digest:
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                initial_monitor_state,
                issues=("execution initial monitor digest does not match supplied state",),
            )
        if execution.episode_nonce != mission.episode_nonce:
            return MonitorCheckResult(
                MonitorVerdict.VIOLATED,
                initial_monitor_state,
                issues=("contract execution belongs to another episode",),
            )
        if not execution.prefixes:
            now = time.monotonic_ns() if now_ns is None else now_ns
            verdict = MonitorVerdict.VIOLATED if now > contract.deadline_ns else MonitorVerdict.SAFE_PENDING
            issue = ("contract deadline expired before any prefix",) if verdict is MonitorVerdict.VIOLATED else ()
            return MonitorCheckResult(verdict, initial_monitor_state, issues=issue)
        evidence_items = tuple(evidence)
        result = MonitorCheckResult(MonitorVerdict.SAFE_PENDING, initial_monitor_state)
        state = initial_monitor_state
        current_state_digest = execution.initial_state_digest
        for index, record in enumerate(execution.prefixes):
            pre = self.check_prefix_pre(
                mission,
                contract,
                current_state_digest,
                state,
                record.candidate,
                (),
                record.receipt.executed_at_ns,
                commit=False,
            )
            if pre.verdict is StaticVerdict.INCONSISTENT:
                return MonitorCheckResult(MonitorVerdict.INCONSISTENT, state, issues=pre.issues)
            if pre.verdict is StaticVerdict.REFUTED:
                return MonitorCheckResult(MonitorVerdict.VIOLATED, state, issues=pre.issues)
            if pre.verdict is StaticVerdict.UNKNOWN:
                return MonitorCheckResult(MonitorVerdict.UNKNOWN, state, issues=pre.issues)
            result = self.monitor_step(
                mission,
                contract,
                state,
                record,
                evidence_items,
                now_ns,
            )
            if result.verdict is MonitorVerdict.COMPLETE and index != len(execution.prefixes) - 1:
                return MonitorCheckResult(
                    MonitorVerdict.VIOLATED,
                    result.monitor_state,
                    issues=("execution contains prefixes after contract completion",),
                )
            if result.verdict is not MonitorVerdict.SAFE_PENDING:
                return result
            state = result.monitor_state
            if record.plant_trace.final_state_digest is not None:
                current_state_digest = record.plant_trace.final_state_digest
        return result


class CTDASupervisor:
    """Small stateful facade suitable for a wrapper's dispatch/observe loop.

    The supervisor owns the active phase and persistent monitor state.  It does
    not dispatch commands itself; a caller must only dispatch after
    :meth:`authorize_prefix` returns ``proven``.
    """

    def __init__(
        self,
        mission: MissionSpec,
        checker: CTDAChecker | None = None,
        now_ns: int | None = None,
    ) -> None:
        self.mission = mission
        self.checker = checker or CTDAChecker()
        mission_result = self.checker.check_mission_spec(mission, now_ns)
        if not mission_result.proven:
            raise ValueError("invalid mission root: " + "; ".join(mission_result.issues))
        self.active_phase = mission.initial_phase
        self.active_contract: SemanticSkillContract | None = None
        self.monitor_state: ContractMonitorState | None = None
        self.active_semantic_witness_digest: str | None = None
        self.active_semantic_attestations: tuple[EvidenceAttestation, ...] = ()
        self.pending_authorization_digest: str | None = None
        self.terminal_verdict: MonitorVerdict | None = None

    def activate_contract(
        self,
        contract: SemanticSkillContract,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        if self.terminal_verdict is not None:
            return StaticCheckResult.refuted("supervisor is latched and requires verified fallback/reset")
        if self.active_contract is not None:
            return StaticCheckResult.refuted("a semantic contract is already active")
        evidence_items = tuple(evidence)
        result = self.checker.check_semantic_refinement(
            self.mission, self.active_phase, contract, evidence_items, now_ns
        )
        if result.proven:
            self.active_contract = contract
            self.monitor_state = ContractMonitorState.initial(self.mission, contract)
            self.active_semantic_witness_digest = result.witness_ref
            self.active_semantic_attestations = evidence_items
        return result

    def authorize_prefix(
        self,
        current_state: Any,
        candidate: PrefixCandidate,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> StaticCheckResult:
        if self.terminal_verdict is not None:
            return StaticCheckResult.refuted("supervisor is latched after a non-continuable verdict")
        if self.pending_authorization_digest is not None:
            return StaticCheckResult.refuted("another prefix authorization is still in flight")
        if self.active_contract is None or self.monitor_state is None:
            return StaticCheckResult.refuted("no semantic contract is active")
        if (
            self.active_semantic_witness_digest is None
            or candidate.authorization.semantic_witness_digest
            != self.active_semantic_witness_digest
        ):
            return StaticCheckResult.refuted(
                "candidate does not bind the supervisor's active semantic witness"
            )
        candidate_semantic = {
            item.attestation_digest for item in candidate.semantic_attestations
        }
        active_semantic = {
            item.attestation_digest for item in self.active_semantic_attestations
        }
        if candidate_semantic != active_semantic:
            return StaticCheckResult.refuted(
                "candidate semantic evidence differs from contract activation evidence"
            )
        state_digest = current_state if isinstance(current_state, str) else digest_legacy_state(current_state)
        result = self.checker.check_prefix_pre(
            self.mission,
            self.active_contract,
            state_digest,
            self.monitor_state,
            candidate,
            evidence,
            now_ns,
        )
        if result.proven:
            self.pending_authorization_digest = candidate.authorization.authorization_digest
        return result

    def observe_prefix(
        self,
        record: PrefixExecutionRecord,
        evidence: Iterable[EvidenceAttestation] = (),
        now_ns: int | None = None,
    ) -> MonitorCheckResult:
        if self.active_contract is None or self.monitor_state is None:
            raise RuntimeError("no semantic contract is active")
        if self.terminal_verdict is not None:
            return MonitorCheckResult(
                self.terminal_verdict,
                self.monitor_state,
                issues=("supervisor is latched after a non-continuable verdict",),
            )
        if self.pending_authorization_digest is None:
            self.terminal_verdict = MonitorVerdict.INCONSISTENT
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                self.monitor_state,
                issues=("execution record has no in-flight authorization",),
            )
        if record.candidate.authorization.authorization_digest != self.pending_authorization_digest:
            self.terminal_verdict = MonitorVerdict.INCONSISTENT
            return MonitorCheckResult(
                MonitorVerdict.INCONSISTENT,
                self.monitor_state,
                issues=("execution record does not match the in-flight authorization",),
            )
        self.pending_authorization_digest = None
        result = self.checker.monitor_step(
            self.mission,
            self.active_contract,
            self.monitor_state,
            record,
            evidence,
            now_ns,
        )
        self.monitor_state = result.monitor_state
        if result.verdict is MonitorVerdict.COMPLETE:
            self.active_phase = result.monitor_state.phase
            self.active_contract = None
            self.monitor_state = None
            self.active_semantic_witness_digest = None
            self.active_semantic_attestations = ()
        elif result.verdict is not MonitorVerdict.SAFE_PENDING:
            self.terminal_verdict = result.verdict
        return result


def digest_legacy_state(state: Any) -> str:
    """Digest an existing ``WorldState`` (or another ``to_dict`` state object)."""

    payload = state.to_dict() if hasattr(state, "to_dict") else state
    return digest_payload(payload)


def digest_legacy_action(action: Any) -> str:
    """Digest an existing :class:`proofalign.models.Action` deterministically."""

    return digest_payload(action)


def mission_from_legacy(
    intent: Any,
    state: Any,
    safety_spec: Any,
    authority: AuthorityEnvelope,
    time_base: TimeBase,
    *,
    spec_id: str,
    episode_nonce: str,
) -> MissionSpec:
    """Compile the frozen Pick/Place task-template slice used by paper CTDA.

    ``intent`` must already have been produced from the benchmark-owned trusted
    instruction.  Policy-facing prompts and policy symbolic metadata must never be
    passed to this compiler.  The function is deliberately *not* a general natural
    language or BDDL compiler: unsupported verbs, ambiguous grasp parts, and missing
    registry entries fail closed.
    """

    verb = str(getattr(intent, "verb", "")).lower()
    target = getattr(intent, "target_object", None)
    objects = getattr(state, "objects", {})
    regions = getattr(state, "regions", {})
    target = _resolve_frozen_object_id(target, objects)
    if target is None:
        raise ValueError("trusted Pick/Place template target is absent from the frozen registry")

    requested_part = getattr(intent, "target_part", None)
    target_parts = getattr(objects[target], "parts", {})
    safe_target_parts = tuple(
        sorted(
            str(part_name)
            for part_name, part in target_parts.items()
            if getattr(part, "safe_to_grasp", False)
            and not getattr(part, "dangerous", False)
        )
    )
    if requested_part is None:
        if len(safe_target_parts) != 1:
            raise ValueError("trusted Pick/Place template has an ambiguous safe grasp part")
        requested_part = safe_target_parts[0]
    elif requested_part not in safe_target_parts:
        raise ValueError("trusted Pick/Place template names a non-safe grasp part")

    region = _resolve_frozen_region_id(
        getattr(intent, "target_region", None),
        regions,
        str(getattr(intent, "raw_instruction", "")),
    )
    if verb == "pick":
        phases = ("approach", "holding")
        transitions = (TaskTransition("approach", "Pick", "holding"),)
        initial_phase = "holding" if getattr(state, "gripper_holding", None) == target else "approach"
    elif verb == "place":
        if region is None or region not in regions:
            raise ValueError("trusted Place template region is absent from the frozen registry")
        phases = ("approach", "holding", "released")
        transitions = (
            TaskTransition("approach", "Pick", "holding"),
            TaskTransition("holding", "Place", "released"),
        )
        initial_phase = "holding" if getattr(state, "gripper_holding", None) == target else "approach"
    else:
        raise ValueError(f"unsupported trusted task template verb: {verb or '<missing>'}")

    safe_parts: list[tuple[str, str]] = []
    for object_id, obj in objects.items():
        for part_name, part in getattr(obj, "parts", {}).items():
            if getattr(part, "safe_to_grasp", False) and not getattr(part, "dangerous", False):
                safe_parts.append((str(object_id), str(part_name)))

    forbidden_objects = set(getattr(safety_spec, "forbidden_objects", ()))
    forbidden_objects.update(getattr(intent, "prohibited_objects", ()))
    forbidden_parts = set(getattr(safety_spec, "forbidden_parts", ()))
    forbidden_parts.update(getattr(intent, "prohibited_parts", ()))
    must_preserve = set(getattr(safety_spec, "protected_objects", ()))
    must_preserve.discard(target)
    hard_invariants: list[str] = []
    if getattr(safety_spec, "require_no_collision", True):
        hard_invariants.append("no_collision")
    margin = getattr(safety_spec, "safety_margin", None)
    protected_keys = {_registry_symbol_key(item) for item in must_preserve}
    if margin is not None and any("humanhand" in item for item in protected_keys):
        hard_invariants.append(f"human_clearance>={margin}")
    if margin is not None and any("obstacle" in item for item in protected_keys):
        hard_invariants.append(f"obstacle_clearance>={margin}")
    required_evidence = ("legacy_certificate",) if getattr(safety_spec, "require_certificates", False) else ()
    goal_payload = {
        "verb": verb,
        "target_object": target,
        "target_part": requested_part,
        "target_region": region,
    }
    if verb == "pick":
        goal_atoms = (f"holding:{target}",)
        goal_phases = ("holding",)
    elif verb == "place":
        goal_atoms = (f"released:{target}", f"in_region:{target}:{region}")
        goal_phases = ("released",)

    phase_obligations: list[PhaseObligation] = []
    for index, transition in enumerate(transitions):
        guarantees = _legacy_transition_guarantees(
            transition.skill,
            target,
            region,
            getattr(intent, "avoid_object", None),
        )
        phase_obligations.append(
            PhaseObligation(
                obligation_id=(
                    f"legacy:{index}:{transition.source_phase}:"
                    f"{transition.skill}:{transition.destination_phase}"
                ),
                source_phase=transition.source_phase,
                skill=transition.skill,
                destination_phase=transition.destination_phase,
                guarantees=guarantees,
                target=(target if transition.skill in {"Pick", "Place", "MoveTo"} else None),
                part=(requested_part if transition.skill == "Pick" else None),
                region=(region if transition.skill == "Place" else None),
                completes_goal=set(goal_atoms).issubset(guarantees),
            )
        )
    unsigned_authority = replace(
        authority,
        attestation_digest="unsigned",
        authenticated=False,
        attestation=None,
    )
    return MissionSpec(
        spec_id=spec_id,
        authority=unsigned_authority,
        instruction_digest=digest_text(str(getattr(intent, "raw_instruction", ""))),
        goal=canonical_json(goal_payload),
        phases=phases,
        transitions=transitions,
        initial_phase=initial_phase,
        time_base=time_base,
        episode_nonce=episode_nonce,
        hard_invariants=tuple(hard_invariants),
        object_ids=tuple(sorted(str(item) for item in objects)),
        region_ids=tuple(sorted(str(item) for item in regions)),
        safe_parts=tuple(sorted(safe_parts)),
        forbidden_objects=tuple(sorted(str(item) for item in forbidden_objects)),
        forbidden_parts=tuple(sorted(str(item) for item in forbidden_parts)),
        default_must_preserve=tuple(sorted(str(item) for item in must_preserve)),
        required_evidence=required_evidence,
        goal_atoms=goal_atoms,
        goal_phases=goal_phases,
        phase_obligations=tuple(phase_obligations),
    )


def _registry_symbol_key(value: Any) -> str:
    text = re.sub(r"__?\d+$", "", str(value).lower())
    return re.sub(r"[^a-z0-9]", "", text)


def _resolve_frozen_object_id(target: Any, objects: Mapping[str, Any]) -> str | None:
    if target is None:
        return None
    target_text = str(target)
    if target_text in objects:
        return target_text
    key = _registry_symbol_key(target_text)
    matches = {
        str(object_id)
        for object_id, obj in objects.items()
        if key
        and key
        in {
            _registry_symbol_key(object_id),
            _registry_symbol_key(getattr(obj, "kind", "")),
        }
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _resolve_frozen_region_id(
    region: Any,
    regions: Mapping[str, Any],
    trusted_instruction: str,
) -> str | None:
    if region is None:
        return None
    region_text = str(region)
    if region_text in regions:
        return region_text
    key = _registry_symbol_key(region_text)
    candidates = {
        str(region_id)
        for region_id in regions
        if key and key in _registry_symbol_key(region_id)
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    instruction_words = set(re.findall(r"[a-z0-9]+", trusted_instruction.lower()))
    directional = instruction_words & {"left", "right", "front", "back", "behind"}
    if directional:
        narrowed = {
            region_id
            for region_id in candidates
            if directional <= set(re.findall(r"[a-z0-9]+", region_id.lower().replace("_", " ")))
        }
        if len(narrowed) == 1:
            return next(iter(narrowed))
    return None


def contract_from_legacy_action(
    mission: MissionSpec,
    action: Any,
    *,
    contract_id: str,
    current_phase: str,
    issued_at_ns: int,
    deadline_ns: int,
    fallback_id: str = "hold",
) -> SemanticSkillContract:
    """Legacy compatibility adapter; paper CTDA uses ``contract_from_mission_phase``."""

    kind = getattr(action, "kind", None)
    skill = str(getattr(kind, "value", kind))
    matching = [
        transition
        for transition in mission.transitions
        if transition.source_phase == current_phase and transition.skill == skill
    ]
    if not matching:
        raise ValueError(f"{skill} is not enabled in mission phase {current_phase}")
    expected_phase = matching[0].destination_phase
    target = getattr(action, "object_id", None)
    region = getattr(action, "region", None)
    obligations = tuple(
        item
        for item in mission.phase_obligations
        if item.source_phase == current_phase
        and item.skill == skill
        and item.destination_phase == expected_phase
    )
    if not obligations:
        raise ValueError("enabled transition has no typed residual-goal obligation")
    guarantees = tuple(
        sorted({atom for obligation in obligations for atom in obligation.guarantees})
    )
    return SemanticSkillContract(
        contract_id=contract_id,
        spec_id=mission.spec_id,
        spec_digest=mission.spec_digest,
        phase_before=current_phase,
        expected_next_phase=expected_phase,
        skill=skill,
        issued_at_ns=issued_at_ns,
        deadline_ns=deadline_ns,
        target=target,
        part=getattr(action, "part", None),
        region=region,
        guarantees=guarantees,
        may_modify=(target,) if target is not None else (),
        must_preserve=mission.default_must_preserve,
        fallback_id=fallback_id,
        advances_obligations=tuple(item.obligation_id for item in obligations),
    )


def contract_from_mission_phase(
    mission: MissionSpec,
    *,
    current_phase: str,
    issued_at_ns: int,
    deadline_ns: int,
    fallback_id: str = "hold",
) -> SemanticSkillContract:
    """Provide the unique active contract from frozen residual obligations.

    No policy prompt, symbolic proposal, producer-supplied contract id, or expected
    effect is an input.  Approach and transport remain raw prefixes inside the
    persistent Pick/Place macro-contract.
    """

    obligations = tuple(
        item for item in mission.phase_obligations if item.source_phase == current_phase
    )
    if not obligations:
        raise ValueError(f"mission phase {current_phase} has no residual obligation")
    transitions = {
        (item.skill, item.destination_phase) for item in obligations
    }
    if len(transitions) != 1:
        raise ValueError(f"mission phase {current_phase} has ambiguous residual obligations")
    skill, destination_phase = next(iter(transitions))
    targets = {item.target for item in obligations}
    parts = {item.part for item in obligations}
    regions = {item.region for item in obligations}
    if len(targets) != 1 or len(parts) != 1 or len(regions) != 1:
        raise ValueError(f"mission phase {current_phase} has ambiguous contract bindings")
    target = next(iter(targets))
    part = next(iter(parts))
    region = next(iter(regions))
    obligation_ids = tuple(sorted(item.obligation_id for item in obligations))
    contract_id = digest_payload(
        {
            "provider": "mission-rooted-pick-place-v1",
            "spec_digest": mission.spec_digest,
            "episode_nonce": mission.episode_nonce,
            "phase": current_phase,
            "obligations": obligation_ids,
        }
    )
    guarantees = tuple(
        sorted({atom for obligation in obligations for atom in obligation.guarantees})
    )
    return SemanticSkillContract(
        contract_id=contract_id,
        spec_id=mission.spec_id,
        spec_digest=mission.spec_digest,
        phase_before=current_phase,
        expected_next_phase=destination_phase,
        skill=skill,
        issued_at_ns=issued_at_ns,
        deadline_ns=deadline_ns,
        target=target,
        part=part,
        region=region,
        guarantees=guarantees,
        may_modify=(target,) if target is not None else (),
        must_preserve=mission.default_must_preserve,
        fallback_id=fallback_id,
        advances_obligations=obligation_ids,
    )


def _legacy_transition_guarantees(
    skill: str,
    target: str | None,
    region: str | None,
    avoid_object: str | None,
) -> tuple[str, ...]:
    if skill == "Pick":
        return (f"holding:{target}",)
    if skill == "Place":
        return (f"released:{target}", f"in_region:{target}:{region}")
    if skill == "MoveTo":
        return (f"progress:{target}:{region}",)
    if skill == "Avoid":
        return (f"avoided:{avoid_object}",)
    if skill == "Stop":
        return ("stopped",)
    return ("rejected",)


def _missing_evidence(required: Iterable[str], provided: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(required) - set(provided)))


def _strictly_increasing(values: Sequence[int]) -> bool:
    return all(left < right for left, right in zip(values, values[1:]))


def _nondecreasing(values: Sequence[int]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))


def _event_violations(mission: MissionSpec, trace: SymbolicEventTrace) -> list[str]:
    violations: list[str] = []
    unconditional_bad_atoms = {"collision", "bad_contact", "assumption_violation"}
    for event in trace.events:
        if event.atom.startswith("violation:") and event.value is TruthValue.TRUE:
            violations.append(f"symbolic violation event observed: {event.atom}")
        if event.atom in unconditional_bad_atoms and event.value is TruthValue.TRUE:
            violations.append(f"unsafe symbolic event observed: {event.atom}")
        if event.atom in mission.hard_invariants and event.value is TruthValue.FALSE:
            violations.append(f"hard invariant evaluated false: {event.atom}")
    return violations


__all__ = [
    "AbstractionLink",
    "ActionProposalBinding",
    "AuthorityEnvelope",
    "CTDAChecker",
    "CTDASupervisor",
    "ContractExecution",
    "ContractMonitorState",
    "DigestAllowlistEvidenceVerifier",
    "EvidenceAttestation",
    "EvidenceVerifier",
    "ExecutionReceipt",
    "KinematicSampleDiagnostics",
    "MissionSpec",
    "MonitorCheckResult",
    "MonitorVerdict",
    "PlantSample",
    "PlantTrace",
    "PhaseObligation",
    "PrefixAuthorization",
    "PrefixCandidate",
    "PrefixExecutionRecord",
    "ReachableTube",
    "SemanticSkillContract",
    "StaticCheckResult",
    "StaticVerdict",
    "SymbolicEvent",
    "SymbolicEventTrace",
    "TaskTransition",
    "TimeBase",
    "TraceAbstractionEvidence",
    "TruthValue",
    "advance_monitor_state",
    "bind_mission_authority",
    "canonical_json",
    "contract_from_legacy_action",
    "contract_from_mission_phase",
    "digest_legacy_action",
    "digest_legacy_state",
    "digest_payload",
    "digest_text",
    "filter_envelope_subject_digest",
    "guard_subject_digest",
    "mission_unsigned_payload",
    "mission_from_legacy",
    "proposal_contract_subject_digest",
    "semantic_witness_digest",
]
