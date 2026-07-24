"""Minimal domain model for mission-rooted VLA execution integrity.

This module implements the public objects described in ``docs/method.md``.  It
is version-isolated from the evaluated CTDA v1 path and the frozen CTDA v2
six-stage prototype.  Digests here are binding metadata, not authentication or
claims about physical truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Iterable

from proofalign.digests import digest_payload


METHOD_ID = "proofalign-integrity-v1"
CORE_SCHEMA_VERSION = "proofalign.integrity-core-v1"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_digest(name: str, value: str) -> None:
    _require_text(name, value)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _require_nonnegative(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _freeze_text(values: Iterable[str], *, require_nonempty: bool = False) -> tuple[str, ...]:
    frozen = tuple(str(value).strip() for value in values)
    if any(not value for value in frozen):
        raise ValueError("text sequence cannot contain empty values")
    if len(frozen) != len(set(frozen)):
        raise ValueError("text sequence cannot contain duplicates")
    if require_nonempty and not frozen:
        raise ValueError("text sequence must be non-empty")
    return frozen


def freeze_command(command: Iterable[float]) -> tuple[float, ...]:
    frozen = tuple(float(value) for value in command)
    if not frozen or any(not isfinite(value) for value in frozen):
        raise ValueError("command must be a non-empty finite numeric sequence")
    return frozen


def command_digest(command: Iterable[float]) -> str:
    return digest_payload(freeze_command(command))


class MethodArm(str, Enum):
    VLA_ONLY = "vla_only"
    INTENT_ONLY = "intent_only"
    EXECUTION_ONLY = "execution_only"
    DUAL = "dual"

    @property
    def intent_enabled(self) -> bool:
        return self in (MethodArm.INTENT_ONLY, MethodArm.DUAL)

    @property
    def execution_enabled(self) -> bool:
        return self in (MethodArm.EXECUTION_ONLY, MethodArm.DUAL)


class LayerVerdict(str, Enum):
    DISABLED = "disabled"
    PROVEN = "proven"
    REFUTED = "refuted"
    UNKNOWN = "unknown"


class CoreVerdict(str, Enum):
    ALLOW = "allow"
    PENDING = "pending"
    COMPLETE = "complete"
    REJECT = "reject"
    UNKNOWN = "unknown"


class InterventionKind(str, Enum):
    PASS = "pass"
    PROJECT_OR_BRAKE = "project_or_brake"
    REPLAN = "replan"
    HARD_BLOCK = "hard_block"


@dataclass(frozen=True)
class PhaseTemplate:
    phase_before: str
    expected_next_phase: str
    skill: str
    obligation_id: str
    completion_atoms: tuple[str, ...]
    target: str | None = None
    part: str | None = None
    region: str | None = None
    contract_version: str = "1"

    def __post_init__(self) -> None:
        for name in (
            "phase_before",
            "expected_next_phase",
            "skill",
            "obligation_id",
            "contract_version",
        ):
            _require_text(name, getattr(self, name))
        object.__setattr__(
            self,
            "completion_atoms",
            _freeze_text(self.completion_atoms, require_nonempty=True),
        )
        for name in ("target", "part", "region"):
            value = getattr(self, name)
            if value is not None:
                _require_text(name, value)


@dataclass(frozen=True)
class TrustedTaskArtifact:
    """Task input supplied by the declared trusted mission adapter boundary."""

    source_id: str
    source_version: str
    artifact_digest: str
    instruction_digest: str
    phases: tuple[str, ...]
    initial_phase: str
    templates: tuple[PhaseTemplate, ...]
    hard_invariants: tuple[str, ...] = ()
    artifact_schema: str = "proofalign.trusted-task-artifact-v1"

    def __post_init__(self) -> None:
        for name in ("source_id", "source_version", "initial_phase", "artifact_schema"):
            _require_text(name, getattr(self, name))
        _require_digest("artifact_digest", self.artifact_digest)
        _require_digest("instruction_digest", self.instruction_digest)
        phases = _freeze_text(self.phases, require_nonempty=True)
        templates = tuple(self.templates)
        invariants = _freeze_text(self.hard_invariants)
        if self.initial_phase not in phases:
            raise ValueError("initial phase is not declared")
        if not templates:
            raise ValueError("trusted task artifact requires at least one phase template")
        sources = [item.phase_before for item in templates]
        if len(sources) != len(set(sources)):
            raise ValueError("minimal mission adapter requires one template per source phase")
        obligations = [item.obligation_id for item in templates]
        if len(obligations) != len(set(obligations)):
            raise ValueError("phase obligation ids must be unique")
        if any(
            item.phase_before not in phases or item.expected_next_phase not in phases
            for item in templates
        ):
            raise ValueError("phase template references an undeclared phase")
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "templates", templates)
        object.__setattr__(self, "hard_invariants", invariants)


@dataclass(frozen=True)
class MissionRoot:
    source_id: str
    source_version: str
    artifact_digest: str
    instruction_digest: str
    episode_nonce: str
    phases: tuple[str, ...]
    initial_phase: str
    templates: tuple[PhaseTemplate, ...]
    hard_invariants: tuple[str, ...]
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    root_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("mission root uses an unsupported integrity-core version")
        for name in ("source_id", "source_version", "episode_nonce", "initial_phase"):
            _require_text(name, getattr(self, name))
        _require_digest("artifact_digest", self.artifact_digest)
        _require_digest("instruction_digest", self.instruction_digest)
        phases = _freeze_text(self.phases, require_nonempty=True)
        templates = tuple(self.templates)
        invariants = _freeze_text(self.hard_invariants)
        if self.initial_phase not in phases:
            raise ValueError("mission root initial phase is not declared")
        if not templates:
            raise ValueError("mission root requires at least one phase template")
        sources = [item.phase_before for item in templates]
        obligations = [item.obligation_id for item in templates]
        if len(sources) != len(set(sources)) or len(obligations) != len(set(obligations)):
            raise ValueError("mission root templates must have unique source phases and obligations")
        if any(
            item.phase_before not in phases or item.expected_next_phase not in phases
            for item in templates
        ):
            raise ValueError("mission root template references an undeclared phase")
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "templates", templates)
        object.__setattr__(self, "hard_invariants", invariants)
        object.__setattr__(self, "root_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "artifact_digest": self.artifact_digest,
            "instruction_digest": self.instruction_digest,
            "episode_nonce": self.episode_nonce,
            "phases": self.phases,
            "initial_phase": self.initial_phase,
            "templates": self.templates,
            "hard_invariants": self.hard_invariants,
        }

    def template_for_phase(self, phase: str) -> PhaseTemplate | None:
        return next((item for item in self.templates if item.phase_before == phase), None)


@dataclass(frozen=True)
class ActiveContract:
    mission_root_digest: str
    episode_nonce: str
    phase_before: str
    expected_next_phase: str
    skill: str
    obligation_id: str
    completion_atoms: tuple[str, ...]
    target: str | None
    part: str | None
    region: str | None
    contract_version: str
    activated_at_ns: int
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    contract_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("active contract uses an unsupported integrity-core version")
        _require_digest("mission_root_digest", self.mission_root_digest)
        for name in (
            "episode_nonce",
            "phase_before",
            "expected_next_phase",
            "skill",
            "obligation_id",
            "contract_version",
        ):
            _require_text(name, getattr(self, name))
        _require_nonnegative("activated_at_ns", self.activated_at_ns)
        object.__setattr__(
            self,
            "completion_atoms",
            _freeze_text(self.completion_atoms, require_nonempty=True),
        )
        for name in ("target", "part", "region"):
            value = getattr(self, name)
            if value is not None:
                _require_text(name, value)
        object.__setattr__(self, "contract_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "mission_root_digest": self.mission_root_digest,
            "episode_nonce": self.episode_nonce,
            "phase_before": self.phase_before,
            "expected_next_phase": self.expected_next_phase,
            "skill": self.skill,
            "obligation_id": self.obligation_id,
            "completion_atoms": self.completion_atoms,
            "target": self.target,
            "part": self.part,
            "region": self.region,
            "contract_version": self.contract_version,
            "activated_at_ns": self.activated_at_ns,
        }


@dataclass(frozen=True)
class StateSnapshot:
    episode_nonce: str
    state_epoch: int
    observed_at_ns: int
    max_age_ns: int
    state_digest: str | None
    known: bool
    unknown_reason: str | None = None
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("episode_nonce", self.episode_nonce)
        _require_nonnegative("state_epoch", self.state_epoch)
        _require_nonnegative("observed_at_ns", self.observed_at_ns)
        if type(self.max_age_ns) is not int or self.max_age_ns <= 0:
            raise ValueError("max_age_ns must be a positive integer")
        if type(self.known) is not bool:
            raise TypeError("known must be bool")
        if self.known:
            if self.state_digest is None:
                raise ValueError("known state requires a digest")
            _require_digest("state_digest", self.state_digest)
            if self.unknown_reason is not None:
                raise ValueError("known state cannot carry an unknown reason")
        else:
            if self.state_digest is not None:
                raise ValueError("unknown state cannot carry a digest")
            _require_text("unknown_reason", self.unknown_reason or "")
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "episode_nonce": self.episode_nonce,
                    "state_epoch": self.state_epoch,
                    "observed_at_ns": self.observed_at_ns,
                    "max_age_ns": self.max_age_ns,
                    "state_digest": self.state_digest,
                    "known": self.known,
                    "unknown_reason": self.unknown_reason,
                }
            ),
        )

    def freshness_issue(self, now_ns: int) -> str | None:
        if not self.known:
            return f"state is unknown: {self.unknown_reason}"
        if now_ns < self.observed_at_ns:
            return "state observation is from the future"
        if now_ns - self.observed_at_ns > self.max_age_ns:
            return "state observation is stale"
        return None


@dataclass(frozen=True)
class ActionProposal:
    episode_nonce: str
    proposal_index: int
    proposed_at_ns: int
    skill: str
    command: tuple[float, ...]
    target: str | None = None
    part: str | None = None
    region: str | None = None
    proposal_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("episode_nonce", self.episode_nonce)
        _require_text("skill", self.skill)
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("proposed_at_ns", self.proposed_at_ns)
        object.__setattr__(self, "command", freeze_command(self.command))
        for name in ("target", "part", "region"):
            value = getattr(self, name)
            if value is not None:
                _require_text(name, value)
        object.__setattr__(self, "proposal_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "proposed_at_ns": self.proposed_at_ns,
            "skill": self.skill,
            "target": self.target,
            "part": self.part,
            "region": self.region,
            "command": self.command,
        }


@dataclass(frozen=True)
class LayerCheck:
    verdict: LayerVerdict
    issues: tuple[str, ...] = ()
    witness_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(str(item) for item in self.issues))
        if self.verdict is LayerVerdict.PROVEN:
            if self.witness_digest is None:
                raise ValueError("proven layer check requires a witness digest")
            _require_digest("witness_digest", self.witness_digest)
        elif self.witness_digest is not None:
            _require_digest("witness_digest", self.witness_digest)

    @classmethod
    def disabled(cls) -> "LayerCheck":
        return cls(LayerVerdict.DISABLED)


@dataclass(frozen=True)
class InterventionResult:
    kind: InterventionKind
    nominal_command: tuple[float, ...]
    final_command: tuple[float, ...] | None
    reason: str
    witness_digest: str | None = None
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("reason", self.reason)
        nominal = freeze_command(self.nominal_command)
        final = None if self.final_command is None else freeze_command(self.final_command)
        if self.kind is InterventionKind.PASS:
            if final != nominal or self.witness_digest is not None:
                raise ValueError("pass must preserve the nominal command without a filter witness")
        elif self.kind is InterventionKind.PROJECT_OR_BRAKE:
            if final is None or final == nominal or self.witness_digest is None:
                raise ValueError("project_or_brake requires a changed command and witness")
            _require_digest("witness_digest", self.witness_digest)
        elif self.kind in (InterventionKind.REPLAN, InterventionKind.HARD_BLOCK):
            if final is not None or self.witness_digest is not None:
                raise ValueError("non-dispatch intervention cannot carry a final command or witness")
        object.__setattr__(self, "nominal_command", nominal)
        object.__setattr__(self, "final_command", final)
        object.__setattr__(
            self,
            "result_digest",
            digest_payload(
                {
                    "kind": self.kind.value,
                    "nominal_command": nominal,
                    "final_command": final,
                    "reason": self.reason,
                    "witness_digest": self.witness_digest,
                }
            ),
        )


@dataclass(frozen=True)
class MonitorState:
    mission_root_digest: str
    episode_nonce: str
    phase: str
    residual_obligations: tuple[str, ...]
    active_contract_digest: str | None = None
    completed_atoms: tuple[str, ...] = ()
    history_evidence_digests: tuple[str, ...] = ()
    last_proposal_index: int = -1
    revision: int = 0
    state_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("mission_root_digest", self.mission_root_digest)
        _require_text("episode_nonce", self.episode_nonce)
        _require_text("phase", self.phase)
        obligations = _freeze_text(self.residual_obligations)
        completed = _freeze_text(self.completed_atoms)
        history = tuple(self.history_evidence_digests)
        if any(len(value) != 64 for value in history):
            raise ValueError("monitor history must contain digests")
        if self.active_contract_digest is not None:
            _require_digest("active_contract_digest", self.active_contract_digest)
        if type(self.last_proposal_index) is not int or self.last_proposal_index < -1:
            raise ValueError("last_proposal_index must be >= -1")
        _require_nonnegative("revision", self.revision)
        object.__setattr__(self, "residual_obligations", obligations)
        object.__setattr__(self, "completed_atoms", completed)
        object.__setattr__(self, "history_evidence_digests", history)
        object.__setattr__(self, "state_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "mission_root_digest": self.mission_root_digest,
            "episode_nonce": self.episode_nonce,
            "phase": self.phase,
            "residual_obligations": self.residual_obligations,
            "active_contract_digest": self.active_contract_digest,
            "completed_atoms": self.completed_atoms,
            "history_evidence_digests": self.history_evidence_digests,
            "last_proposal_index": self.last_proposal_index,
            "revision": self.revision,
        }

    @classmethod
    def initial(cls, mission: MissionRoot) -> "MonitorState":
        return cls(
            mission_root_digest=mission.root_digest,
            episode_nonce=mission.episode_nonce,
            phase=mission.initial_phase,
            residual_obligations=tuple(item.obligation_id for item in mission.templates),
        )


@dataclass(frozen=True)
class ContractTransaction:
    verdict: CoreVerdict
    before_state_digest: str
    after_state: MonitorState
    contract: ActiveContract | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrefixAuthorization:
    arm: MethodArm
    verdict: CoreVerdict
    mission_root_digest: str
    contract_digest: str
    episode_nonce: str
    state_snapshot_digest: str
    monitor_state_digest: str
    proposal_index: int
    proposal_digest: str
    nominal_command_digest: str
    final_command: tuple[float, ...] | None
    final_command_digest: str | None
    intervention: InterventionResult
    intent_check: LayerCheck
    execution_check: LayerCheck
    issued_at_ns: int
    valid_until_ns: int
    method_id: str = METHOD_ID
    schema_version: str = CORE_SCHEMA_VERSION
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.method_id != METHOD_ID or self.schema_version != CORE_SCHEMA_VERSION:
            raise ValueError("prefix authorization uses an unsupported integrity-core version")
        for name in (
            "mission_root_digest",
            "contract_digest",
            "state_snapshot_digest",
            "monitor_state_digest",
            "proposal_digest",
            "nominal_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        _require_text("episode_nonce", self.episode_nonce)
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("issued_at_ns", self.issued_at_ns)
        if self.valid_until_ns <= self.issued_at_ns:
            raise ValueError("authorization validity window is empty")
        final = None if self.final_command is None else freeze_command(self.final_command)
        if self.nominal_command_digest != command_digest(self.intervention.nominal_command):
            raise ValueError("nominal command digest does not match intervention input")
        if final != self.intervention.final_command:
            raise ValueError("authorization final command does not match intervention output")
        if final is None:
            if self.final_command_digest is not None:
                raise ValueError("non-dispatch authorization cannot carry a command digest")
            if self.verdict is CoreVerdict.ALLOW:
                raise ValueError("allow authorization requires a final command")
        else:
            expected = command_digest(final)
            if self.final_command_digest != expected:
                raise ValueError("final command digest mismatch")
        if self.verdict is CoreVerdict.ALLOW:
            if self.arm.intent_enabled:
                if self.intent_check.verdict is not LayerVerdict.PROVEN:
                    raise ValueError("allow authorization lacks required intent proof")
            elif self.intent_check.verdict is not LayerVerdict.DISABLED:
                raise ValueError("disabled intent layer must have a disabled verdict")
            if self.arm.execution_enabled:
                if self.execution_check.verdict is not LayerVerdict.PROVEN:
                    raise ValueError("allow authorization lacks required execution proof")
            elif self.execution_check.verdict is not LayerVerdict.DISABLED:
                raise ValueError("disabled execution layer must have a disabled verdict")
        object.__setattr__(self, "final_command", final)
        object.__setattr__(self, "authorization_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "schema_version": self.schema_version,
            "arm": self.arm.value,
            "verdict": self.verdict.value,
            "mission_root_digest": self.mission_root_digest,
            "contract_digest": self.contract_digest,
            "episode_nonce": self.episode_nonce,
            "state_snapshot_digest": self.state_snapshot_digest,
            "monitor_state_digest": self.monitor_state_digest,
            "proposal_index": self.proposal_index,
            "proposal_digest": self.proposal_digest,
            "nominal_command_digest": self.nominal_command_digest,
            "final_command": self.final_command,
            "final_command_digest": self.final_command_digest,
            "intervention_digest": self.intervention.result_digest,
            "intent_verdict": self.intent_check.verdict.value,
            "intent_witness": self.intent_check.witness_digest,
            "execution_verdict": self.execution_check.verdict.value,
            "execution_witness": self.execution_check.witness_digest,
            "issued_at_ns": self.issued_at_ns,
            "valid_until_ns": self.valid_until_ns,
        }

    @property
    def dispatchable(self) -> bool:
        return (
            self.verdict is CoreVerdict.ALLOW
            and self.final_command is not None
            and (not self.arm.intent_enabled or self.intent_check.verdict is LayerVerdict.PROVEN)
            and (
                not self.arm.execution_enabled
                or self.execution_check.verdict is LayerVerdict.PROVEN
            )
        )

    def is_fresh(self, now_ns: int) -> bool:
        return self.issued_at_ns <= now_ns <= self.valid_until_ns


@dataclass(frozen=True)
class DispatchReceipt:
    authorization_digest: str
    episode_nonce: str
    proposal_index: int
    authorized_command_digest: str
    applied_command_digest: str
    applied_at_ns: int
    sink_id: str
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "authorization_digest",
            "authorized_command_digest",
            "applied_command_digest",
        ):
            _require_digest(name, getattr(self, name))
        for name in ("episode_nonce", "sink_id"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("applied_at_ns", self.applied_at_ns)
        object.__setattr__(
            self,
            "receipt_digest",
            digest_payload(
                {
                    "authorization_digest": self.authorization_digest,
                    "episode_nonce": self.episode_nonce,
                    "proposal_index": self.proposal_index,
                    "authorized_command_digest": self.authorized_command_digest,
                    "applied_command_digest": self.applied_command_digest,
                    "applied_at_ns": self.applied_at_ns,
                    "sink_id": self.sink_id,
                }
            ),
        )


@dataclass(frozen=True)
class DispatchResult:
    verdict: CoreVerdict
    receipt: DispatchReceipt | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionEvidence:
    authorization_digest: str
    receipt_digest: str
    episode_nonce: str
    proposal_index: int
    observed_at_ns: int
    observed_command_digest: str | None
    observed_atoms: tuple[str, ...]
    known: bool
    violation: bool = False
    unknown_reason: str | None = None
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("authorization_digest", self.authorization_digest)
        _require_digest("receipt_digest", self.receipt_digest)
        _require_text("episode_nonce", self.episode_nonce)
        _require_nonnegative("proposal_index", self.proposal_index)
        _require_nonnegative("observed_at_ns", self.observed_at_ns)
        if type(self.known) is not bool or type(self.violation) is not bool:
            raise TypeError("known and violation must be bool")
        atoms = _freeze_text(self.observed_atoms)
        if self.known:
            if self.observed_command_digest is None:
                raise ValueError("known execution evidence requires an observed command digest")
            _require_digest("observed_command_digest", self.observed_command_digest)
            if self.unknown_reason is not None:
                raise ValueError("known execution evidence cannot carry an unknown reason")
        else:
            if self.observed_command_digest is not None or atoms or self.violation:
                raise ValueError("unknown execution evidence cannot carry observations")
            _require_text("unknown_reason", self.unknown_reason or "")
        object.__setattr__(self, "observed_atoms", atoms)
        object.__setattr__(
            self,
            "evidence_digest",
            digest_payload(
                {
                    "authorization_digest": self.authorization_digest,
                    "receipt_digest": self.receipt_digest,
                    "episode_nonce": self.episode_nonce,
                    "proposal_index": self.proposal_index,
                    "observed_at_ns": self.observed_at_ns,
                    "observed_command_digest": self.observed_command_digest,
                    "observed_atoms": atoms,
                    "known": self.known,
                    "violation": self.violation,
                    "unknown_reason": self.unknown_reason,
                }
            ),
        )


@dataclass(frozen=True)
class MonitorTransition:
    verdict: CoreVerdict
    before_state_digest: str
    after_state: MonitorState
    contract_digest: str
    proposal_index: int
    evidence_digest: str
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectUpdateResult:
    verdict: CoreVerdict
    before_state: MonitorState
    after_state: MonitorState
    issues: tuple[str, ...] = ()


__all__ = [
    "CORE_SCHEMA_VERSION",
    "METHOD_ID",
    "ActionProposal",
    "ActiveContract",
    "ContractTransaction",
    "CoreVerdict",
    "DispatchReceipt",
    "DispatchResult",
    "EffectUpdateResult",
    "ExecutionEvidence",
    "InterventionKind",
    "InterventionResult",
    "LayerCheck",
    "LayerVerdict",
    "MethodArm",
    "MissionRoot",
    "MonitorState",
    "MonitorTransition",
    "PhaseTemplate",
    "PrefixAuthorization",
    "StateSnapshot",
    "TrustedTaskArtifact",
    "command_digest",
    "freeze_command",
]
