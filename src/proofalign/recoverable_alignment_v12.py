"""Outcome-informed v12 sparse-L1 and recoverable-L2 primitives.

This module does not create a simulator, dispatch an action, or read a task
outcome.  It defines the pure decision and transaction boundaries that must be
qualified before an online successor can be authorized.

The v12 changes are deliberately versioned rather than patched into v11:

* L1 hard-rejects only recognized intent or physical violations.  Soft
  progress/effect evidence is advisory and an accepted source ActionBlock is
  never rewritten.
* L2 binds a trusted joint state to a read-only shadow trajectory assessment.
* A typed recovery transaction revokes the triggering policy authorization.
  Only an exactly bound recovery command can be consumed while recovery mode
  is active, and the old policy authorization remains permanently revoked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, prod
from typing import Iterable, Sequence

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import command_digest
from proofalign.risk_selective_semantic import is_physical_risk_atom
from proofalign.semantic_local_checker import LocalActionAssessment


V12_METHOD_ID = "proofalign-recoverable-alignment-v12"
SPARSE_L1_SCHEMA = "proofalign.sparse-l1-decision.v12"
TRUSTED_JOINT_STATE_SCHEMA = "proofalign.trusted-joint-state.v12"
SHADOW_ASSESSMENT_SCHEMA = "proofalign.shadow-joint-assessment.v12"
RECOVERY_TRANSACTION_SCHEMA = "proofalign.recovery-transaction.v12"

INTENT_HARD_VIOLATION_ATOMS = (
    "close_outside_target_neighborhood",
    "move_without_held_target",
    "release_during_move",
    "place_without_held_target",
    "release_outside_valid_place_region",
    "release_without_held_target",
    "release_command_missing",
    "wrong_target",
    "wrong_destination",
    "illegal_task_graph_phase",
)
ADVISORY_UNKNOWN_REASONS = (
    "trusted_articulation_state_unavailable",
    "missing_target_geometry",
    "missing_destination_geometry",
    "finish_has_no_executable_prefix",
)
FAIL_CLOSED_UNKNOWN_PREFIXES = (
    "stale_observation_state_epoch",
    "malformed_checker_input:",
)
ADVISORY_ATOM_PREFIXES = (
    "advisory_semantic_atom:",
    "advisory_semantic_unknown:",
)


class RecoverableAlignmentV12Error(ValueError):
    """Raised when a v12 record is malformed or a binding is substituted."""


def _require_digest(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecoverableAlignmentV12Error(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite_tuple(
    values: Iterable[float],
    *,
    name: str,
    length: int | None = None,
) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise RecoverableAlignmentV12Error(
            f"{name} must be numeric"
        ) from exc
    if (
        not frozen
        or any(not isfinite(value) for value in frozen)
        or (length is not None and len(frozen) != length)
    ):
        raise RecoverableAlignmentV12Error(
            f"{name} must be non-empty and finite"
        )
    return frozen


def _command_shape(
    shape: Sequence[int], *, value_count: int
) -> tuple[int, ...]:
    frozen = tuple(shape)
    if (
        not frozen
        or any(
            type(dimension) is not int or dimension <= 0
            for dimension in frozen
        )
        or prod(frozen) != value_count
    ):
        raise RecoverableAlignmentV12Error(
            "command_shape does not match the command"
        )
    return frozen


class SparseL1Verdict(str, Enum):
    PASSTHROUGH = "passthrough"
    HARD_REJECT = "hard_reject"
    ADVISORY_REPLAN = "advisory_replan"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SparseL1Decision:
    """Versioned L1 partition over one exact source ActionBlock."""

    verdict: SparseL1Verdict
    source_action_block_digest: str
    returned_action_block_digest: str | None
    hard_atoms: tuple[str, ...]
    advisory_atoms: tuple[str, ...]
    unknown_reason: str | None
    exact_passthrough: bool
    l1_authorization_allowed: bool
    replan_after_block: bool
    schema: str = SPARSE_L1_SCHEMA
    method_id: str = V12_METHOD_ID
    decision_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema != SPARSE_L1_SCHEMA or self.method_id != V12_METHOD_ID:
            raise RecoverableAlignmentV12Error(
                "unsupported sparse-L1 decision version"
            )
        _require_digest(
            "source_action_block_digest",
            self.source_action_block_digest,
        )
        if self.returned_action_block_digest is not None:
            _require_digest(
                "returned_action_block_digest",
                self.returned_action_block_digest,
            )
        if self.exact_passthrough:
            if (
                self.returned_action_block_digest
                != self.source_action_block_digest
            ):
                raise RecoverableAlignmentV12Error(
                    "exact passthrough must preserve ActionBlock identity"
                )
        elif self.returned_action_block_digest is not None:
            raise RecoverableAlignmentV12Error(
                "a rejected or unknown block cannot be returned"
            )
        if self.l1_authorization_allowed and not self.exact_passthrough:
            raise RecoverableAlignmentV12Error(
                "L1 authorization requires exact passthrough"
            )
        if self.hard_atoms and self.verdict is not SparseL1Verdict.HARD_REJECT:
            raise RecoverableAlignmentV12Error(
                "hard atoms require a hard-reject verdict"
            )
        object.__setattr__(
            self,
            "decision_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "method_id": self.method_id,
                    "verdict": self.verdict.value,
                    "source_action_block_digest": (
                        self.source_action_block_digest
                    ),
                    "returned_action_block_digest": (
                        self.returned_action_block_digest
                    ),
                    "hard_atoms": self.hard_atoms,
                    "advisory_atoms": self.advisory_atoms,
                    "unknown_reason": self.unknown_reason,
                    "exact_passthrough": self.exact_passthrough,
                    "l1_authorization_allowed": (
                        self.l1_authorization_allowed
                    ),
                    "replan_after_block": self.replan_after_block,
                }
            ),
        )


def sparse_l1_decision(
    assessment: LocalActionAssessment,
    *,
    source_command: Iterable[float],
    command_shape: Sequence[int],
) -> SparseL1Decision:
    """Partition a frozen local assessment without changing source bytes."""

    command = _finite_tuple(source_command, name="source_command")
    _command_shape(command_shape, value_count=len(command))
    source_digest = command_digest(command)

    if not assessment.known:
        reason = assessment.unknown_reason or "unspecified_unknown"
        fail_closed = reason.startswith(FAIL_CLOSED_UNKNOWN_PREFIXES)
        advisory = reason in ADVISORY_UNKNOWN_REASONS
        return SparseL1Decision(
            verdict=(
                SparseL1Verdict.UNKNOWN
                if fail_closed or not advisory
                else SparseL1Verdict.ADVISORY_REPLAN
            ),
            source_action_block_digest=source_digest,
            returned_action_block_digest=(
                source_digest if advisory and not fail_closed else None
            ),
            hard_atoms=(),
            advisory_atoms=(
                (f"advisory_unknown:{reason}",)
                if advisory and not fail_closed
                else ()
            ),
            unknown_reason=reason,
            exact_passthrough=advisory and not fail_closed,
            # An advisory bypass may preserve utility but carries no positive
            # L1 authorization claim.
            l1_authorization_allowed=False,
            replan_after_block=advisory and not fail_closed,
        )

    hard = []
    advisory = []
    for atom in assessment.violation_atoms:
        if is_physical_risk_atom(atom) or atom in INTENT_HARD_VIOLATION_ATOMS:
            hard.append(atom)
        else:
            # Unrecognized violation atoms remain fail closed.
            hard.append(f"unrecognized_violation:{atom}")
    for atom in assessment.precondition_atoms:
        if atom.startswith(ADVISORY_ATOM_PREFIXES):
            advisory.append(atom)
    if not assessment.semantic_compatible and not hard:
        advisory.append("semantic_compatibility_not_established")
    if assessment.progress_margin is not None and assessment.progress_margin < 0.002:
        advisory.append("progress_below_historical_2mm")

    hard_atoms = tuple(dict.fromkeys(hard))
    advisory_atoms = tuple(dict.fromkeys(advisory))
    if hard_atoms:
        return SparseL1Decision(
            verdict=SparseL1Verdict.HARD_REJECT,
            source_action_block_digest=source_digest,
            returned_action_block_digest=None,
            hard_atoms=hard_atoms,
            advisory_atoms=advisory_atoms,
            unknown_reason=None,
            exact_passthrough=False,
            l1_authorization_allowed=False,
            replan_after_block=False,
        )
    return SparseL1Decision(
        verdict=SparseL1Verdict.PASSTHROUGH,
        source_action_block_digest=source_digest,
        returned_action_block_digest=source_digest,
        hard_atoms=(),
        advisory_atoms=advisory_atoms,
        unknown_reason=None,
        exact_passthrough=True,
        l1_authorization_allowed=True,
        replan_after_block=bool(advisory_atoms),
    )


@dataclass(frozen=True)
class TrustedJointState:
    """Content-addressed trusted simulator execution state."""

    state_epoch: int
    qpos: tuple[float, ...]
    qvel: tuple[float, ...]
    joint_lower: tuple[float, ...]
    joint_upper: tuple[float, ...]
    source_id: str
    schema: str = TRUSTED_JOINT_STATE_SCHEMA
    state_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.state_epoch) is not int or self.state_epoch < 0:
            raise RecoverableAlignmentV12Error(
                "state_epoch must be a non-negative integer"
            )
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise RecoverableAlignmentV12Error(
                "source_id must be non-empty"
            )
        qpos = _finite_tuple(self.qpos, name="qpos")
        qvel = _finite_tuple(self.qvel, name="qvel", length=len(qpos))
        lower = _finite_tuple(
            self.joint_lower, name="joint_lower", length=len(qpos)
        )
        upper = _finite_tuple(
            self.joint_upper, name="joint_upper", length=len(qpos)
        )
        if any(
            low >= high
            for low, high in zip(lower, upper, strict=True)
        ):
            raise RecoverableAlignmentV12Error(
                "joint limits must be strictly ordered"
            )
        object.__setattr__(self, "qpos", qpos)
        object.__setattr__(self, "qvel", qvel)
        object.__setattr__(self, "joint_lower", lower)
        object.__setattr__(self, "joint_upper", upper)
        object.__setattr__(
            self,
            "state_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "state_epoch": self.state_epoch,
                    "qpos": qpos,
                    "qvel": qvel,
                    "joint_lower": lower,
                    "joint_upper": upper,
                    "source_id": self.source_id,
                }
            ),
        )

    @property
    def minimum_margin(self) -> float:
        return min(
            min(value - low, high - value)
            for value, low, high in zip(
                self.qpos,
                self.joint_lower,
                self.joint_upper,
                strict=True,
            )
        )


@dataclass(frozen=True)
class ShadowJointTrajectory:
    """Read-only predicted joint positions bound to state and action bytes."""

    initial_state_digest: str
    action_block_digest: str
    positions: tuple[tuple[float, ...], ...]
    predictor_id: str
    trajectory_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(
            "initial_state_digest", self.initial_state_digest
        )
        _require_digest("action_block_digest", self.action_block_digest)
        if (
            not isinstance(self.predictor_id, str)
            or not self.predictor_id.strip()
        ):
            raise RecoverableAlignmentV12Error(
                "predictor_id must be non-empty"
            )
        positions = tuple(
            _finite_tuple(row, name="predicted_qpos")
            for row in self.positions
        )
        if not positions:
            raise RecoverableAlignmentV12Error(
                "shadow trajectory must contain at least one step"
            )
        width = len(positions[0])
        if any(len(row) != width for row in positions):
            raise RecoverableAlignmentV12Error(
                "shadow trajectory joint width must be constant"
            )
        object.__setattr__(self, "positions", positions)
        object.__setattr__(
            self,
            "trajectory_digest",
            digest_payload(
                {
                    "schema": SHADOW_ASSESSMENT_SCHEMA + ".trajectory",
                    "initial_state_digest": self.initial_state_digest,
                    "action_block_digest": self.action_block_digest,
                    "positions": positions,
                    "predictor_id": self.predictor_id,
                }
            ),
        )


@dataclass(frozen=True)
class ShadowJointAssessment:
    known: bool
    risk_predicted: bool
    minimum_margin: float | None
    terminal_margin: float | None
    first_risk_step: int | None
    issues: tuple[str, ...]
    initial_state_digest: str
    action_block_digest: str
    trajectory_digest: str
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "initial_state_digest",
            "action_block_digest",
            "trajectory_digest",
        ):
            _require_digest(name, getattr(self, name))
        if not self.known and not self.issues:
            raise RecoverableAlignmentV12Error(
                "unknown shadow assessment requires an issue"
            )
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": SHADOW_ASSESSMENT_SCHEMA,
                    "known": self.known,
                    "risk_predicted": self.risk_predicted,
                    "minimum_margin": self.minimum_margin,
                    "terminal_margin": self.terminal_margin,
                    "first_risk_step": self.first_risk_step,
                    "issues": self.issues,
                    "initial_state_digest": self.initial_state_digest,
                    "action_block_digest": self.action_block_digest,
                    "trajectory_digest": self.trajectory_digest,
                }
            ),
        )


def assess_shadow_joint_trajectory(
    state: TrustedJointState,
    trajectory: ShadowJointTrajectory,
    *,
    trigger_margin_rad: float = 0.1,
) -> ShadowJointAssessment:
    """Assess a bound shadow trajectory against frozen joint margins."""

    if not isfinite(trigger_margin_rad) or trigger_margin_rad <= 0:
        raise RecoverableAlignmentV12Error(
            "trigger_margin_rad must be positive and finite"
        )
    issues = []
    if trajectory.initial_state_digest != state.state_digest:
        issues.append("shadow_initial_state_binding_mismatch")
    if any(len(row) != len(state.qpos) for row in trajectory.positions):
        issues.append("shadow_joint_width_mismatch")
    if issues:
        return ShadowJointAssessment(
            known=False,
            risk_predicted=True,
            minimum_margin=None,
            terminal_margin=None,
            first_risk_step=None,
            issues=tuple(issues),
            initial_state_digest=state.state_digest,
            action_block_digest=trajectory.action_block_digest,
            trajectory_digest=trajectory.trajectory_digest,
        )

    margins = tuple(
        min(
            min(value - low, high - value)
            for value, low, high in zip(
                row,
                state.joint_lower,
                state.joint_upper,
                strict=True,
            )
        )
        for row in trajectory.positions
    )
    first_risk = next(
        (
            index
            for index, margin in enumerate(margins)
            if margin <= trigger_margin_rad
        ),
        None,
    )
    return ShadowJointAssessment(
        known=True,
        risk_predicted=first_risk is not None,
        minimum_margin=min(margins),
        terminal_margin=margins[-1],
        first_risk_step=first_risk,
        issues=(),
        initial_state_digest=state.state_digest,
        action_block_digest=trajectory.action_block_digest,
        trajectory_digest=trajectory.trajectory_digest,
    )


@dataclass(frozen=True)
class RecoveryCandidate:
    candidate_id: str
    command: tuple[float, ...]
    command_shape: tuple[int, ...]
    trajectory: ShadowJointTrajectory
    hard_violation_atoms: tuple[str, ...] = ()
    command_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise RecoverableAlignmentV12Error(
                "candidate_id must be non-empty"
            )
        command = _finite_tuple(self.command, name="recovery_command")
        shape = _command_shape(
            self.command_shape, value_count=len(command)
        )
        digest = command_digest(command)
        if self.trajectory.action_block_digest != digest:
            raise RecoverableAlignmentV12Error(
                "recovery trajectory is not bound to command bytes"
            )
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "command_shape", shape)
        object.__setattr__(self, "command_digest", digest)


@dataclass(frozen=True)
class RecoverySelection:
    selected: RecoveryCandidate | None
    selected_assessment: ShadowJointAssessment | None
    rejected: tuple[tuple[str, tuple[str, ...]], ...]
    baseline_margin: float
    required_margin_gain: float
    selection_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_digest",
            digest_payload(
                {
                    "schema": RECOVERY_TRANSACTION_SCHEMA + ".selection",
                    "selected_candidate_id": (
                        self.selected.candidate_id
                        if self.selected is not None
                        else None
                    ),
                    "selected_assessment_digest": (
                        self.selected_assessment.assessment_digest
                        if self.selected_assessment is not None
                        else None
                    ),
                    "rejected": self.rejected,
                    "baseline_margin": self.baseline_margin,
                    "required_margin_gain": self.required_margin_gain,
                }
            ),
        )


def select_recovery_candidate(
    state: TrustedJointState,
    candidates: Sequence[RecoveryCandidate],
    *,
    trigger_margin_rad: float = 0.1,
    required_margin_gain_rad: float = 0.02,
) -> RecoverySelection:
    """Select the safest deterministic recovery candidate or abstain."""

    if (
        not isfinite(required_margin_gain_rad)
        or required_margin_gain_rad <= 0
    ):
        raise RecoverableAlignmentV12Error(
            "required_margin_gain_rad must be positive and finite"
        )
    eligible: list[
        tuple[float, float, str, RecoveryCandidate, ShadowJointAssessment]
    ] = []
    rejected = []
    for candidate in candidates:
        assessment = assess_shadow_joint_trajectory(
            state,
            candidate.trajectory,
            trigger_margin_rad=trigger_margin_rad,
        )
        reasons = []
        if not assessment.known:
            reasons.extend(assessment.issues)
        if candidate.hard_violation_atoms:
            reasons.extend(candidate.hard_violation_atoms)
        if assessment.risk_predicted:
            reasons.append("recovery_trajectory_remains_in_trigger_region")
        if (
            assessment.terminal_margin is None
            or assessment.terminal_margin
            < state.minimum_margin + required_margin_gain_rad
        ):
            reasons.append("insufficient_joint_margin_gain")
        if reasons:
            rejected.append(
                (candidate.candidate_id, tuple(dict.fromkeys(reasons)))
            )
            continue
        eligible.append(
            (
                float(assessment.terminal_margin),
                float(assessment.minimum_margin),
                candidate.candidate_id,
                candidate,
                assessment,
            )
        )
    if not eligible:
        return RecoverySelection(
            selected=None,
            selected_assessment=None,
            rejected=tuple(rejected),
            baseline_margin=state.minimum_margin,
            required_margin_gain=required_margin_gain_rad,
        )
    # Maximize terminal then worst-trajectory margin; candidate id is the
    # stable final tie break.
    eligible.sort(key=lambda row: (-row[0], -row[1], row[2]))
    selected = eligible[0]
    return RecoverySelection(
        selected=selected[3],
        selected_assessment=selected[4],
        rejected=tuple(rejected),
        baseline_margin=state.minimum_margin,
        required_margin_gain=required_margin_gain_rad,
    )


class RecoveryMode(str, Enum):
    POLICY = "policy"
    RECOVERY_AUTHORIZED = "recovery_authorized"
    AWAITING_RECOVERY_OBSERVATION = "awaiting_recovery_observation"


@dataclass(frozen=True)
class RecoveryAuthorization:
    trigger_state_digest: str
    revoked_policy_authorization_digest: str
    recovery_command_digest: str
    selection_digest: str
    issued_at_ns: int
    valid_until_ns: int
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "trigger_state_digest",
            "revoked_policy_authorization_digest",
            "recovery_command_digest",
            "selection_digest",
        ):
            _require_digest(name, getattr(self, name))
        if (
            type(self.issued_at_ns) is not int
            or type(self.valid_until_ns) is not int
            or self.issued_at_ns < 0
            or self.valid_until_ns <= self.issued_at_ns
        ):
            raise RecoverableAlignmentV12Error(
                "recovery authorization interval is invalid"
            )
        object.__setattr__(
            self,
            "authorization_digest",
            digest_payload(
                {
                    "schema": RECOVERY_TRANSACTION_SCHEMA + ".authorization",
                    "trigger_state_digest": self.trigger_state_digest,
                    "revoked_policy_authorization_digest": (
                        self.revoked_policy_authorization_digest
                    ),
                    "recovery_command_digest": (
                        self.recovery_command_digest
                    ),
                    "selection_digest": self.selection_digest,
                    "issued_at_ns": self.issued_at_ns,
                    "valid_until_ns": self.valid_until_ns,
                }
            ),
        )


class RecoveryTransactionGate:
    """One-shot typed recovery gate with permanent old-policy revocation."""

    def __init__(self, *, safe_margin_rad: float = 0.15) -> None:
        if not isfinite(safe_margin_rad) or safe_margin_rad <= 0:
            raise RecoverableAlignmentV12Error(
                "safe_margin_rad must be positive and finite"
            )
        self.safe_margin_rad = float(safe_margin_rad)
        self.mode = RecoveryMode.POLICY
        self._revoked_policy_authorizations: set[str] = set()
        self._used_recovery_authorizations: set[str] = set()
        self._trigger_state_digest: str | None = None
        self._revoked_policy_digest: str | None = None
        self._active_recovery: RecoveryAuthorization | None = None

    def policy_authorization_allowed(self, authorization_digest: str) -> bool:
        _require_digest("authorization_digest", authorization_digest)
        return (
            self.mode is RecoveryMode.POLICY
            and authorization_digest
            not in self._revoked_policy_authorizations
        )

    def authorize_recovery(
        self,
        *,
        triggering_policy_authorization_digest: str,
        trigger_state: TrustedJointState,
        selection: RecoverySelection,
        now_ns: int,
        ttl_ns: int = 5_000_000_000,
    ) -> RecoveryAuthorization:
        _require_digest(
            "triggering_policy_authorization_digest",
            triggering_policy_authorization_digest,
        )
        if self.mode is not RecoveryMode.POLICY:
            raise RecoverableAlignmentV12Error(
                "recovery transaction is already active"
            )
        if selection.selected is None:
            raise RecoverableAlignmentV12Error(
                "cannot authorize an empty recovery selection"
            )
        if type(now_ns) is not int or now_ns < 0:
            raise RecoverableAlignmentV12Error(
                "now_ns must be a non-negative integer"
            )
        if type(ttl_ns) is not int or ttl_ns <= 0:
            raise RecoverableAlignmentV12Error(
                "ttl_ns must be a positive integer"
            )
        self._revoked_policy_authorizations.add(
            triggering_policy_authorization_digest
        )
        authorization = RecoveryAuthorization(
            trigger_state_digest=trigger_state.state_digest,
            revoked_policy_authorization_digest=(
                triggering_policy_authorization_digest
            ),
            recovery_command_digest=selection.selected.command_digest,
            selection_digest=selection.selection_digest,
            issued_at_ns=now_ns,
            valid_until_ns=now_ns + ttl_ns,
        )
        self._trigger_state_digest = trigger_state.state_digest
        self._revoked_policy_digest = (
            triggering_policy_authorization_digest
        )
        self._active_recovery = authorization
        self.mode = RecoveryMode.RECOVERY_AUTHORIZED
        return authorization

    def consume_recovery(
        self,
        authorization: RecoveryAuthorization,
        *,
        command: Iterable[float],
        now_ns: int,
    ) -> str:
        if self.mode is not RecoveryMode.RECOVERY_AUTHORIZED:
            raise RecoverableAlignmentV12Error(
                "recovery mode is not authorized"
            )
        if (
            self._active_recovery is None
            or authorization.authorization_digest
            != self._active_recovery.authorization_digest
        ):
            raise RecoverableAlignmentV12Error(
                "recovery authorization substitution"
            )
        if authorization.authorization_digest in (
            self._used_recovery_authorizations
        ):
            raise RecoverableAlignmentV12Error(
                "recovery authorization has already been consumed"
            )
        if (
            type(now_ns) is not int
            or now_ns < authorization.issued_at_ns
            or now_ns > authorization.valid_until_ns
        ):
            raise RecoverableAlignmentV12Error(
                "recovery authorization is stale or not yet valid"
            )
        candidate_digest = command_digest(
            _finite_tuple(command, name="recovery_command")
        )
        if candidate_digest != authorization.recovery_command_digest:
            raise RecoverableAlignmentV12Error(
                "recovery command differs from authorization"
            )
        self._used_recovery_authorizations.add(
            authorization.authorization_digest
        )
        self.mode = RecoveryMode.AWAITING_RECOVERY_OBSERVATION
        return digest_payload(
            {
                "schema": RECOVERY_TRANSACTION_SCHEMA + ".receipt",
                "authorization_digest": authorization.authorization_digest,
                "recovery_command_digest": candidate_digest,
                "consumed_at_ns": now_ns,
            }
        )

    def complete_recovery(
        self, post_state: TrustedJointState
    ) -> bool:
        if self.mode is not RecoveryMode.AWAITING_RECOVERY_OBSERVATION:
            raise RecoverableAlignmentV12Error(
                "no consumed recovery awaits observation"
            )
        if post_state.minimum_margin < self.safe_margin_rad:
            return False
        self.mode = RecoveryMode.POLICY
        self._trigger_state_digest = None
        self._revoked_policy_digest = None
        self._active_recovery = None
        return True


__all__ = [
    "ADVISORY_UNKNOWN_REASONS",
    "INTENT_HARD_VIOLATION_ATOMS",
    "RECOVERY_TRANSACTION_SCHEMA",
    "SHADOW_ASSESSMENT_SCHEMA",
    "SPARSE_L1_SCHEMA",
    "TRUSTED_JOINT_STATE_SCHEMA",
    "V12_METHOD_ID",
    "RecoverableAlignmentV12Error",
    "RecoveryAuthorization",
    "RecoveryCandidate",
    "RecoveryMode",
    "RecoverySelection",
    "RecoveryTransactionGate",
    "ShadowJointAssessment",
    "ShadowJointTrajectory",
    "SparseL1Decision",
    "SparseL1Verdict",
    "TrustedJointState",
    "assess_shadow_joint_trajectory",
    "select_recovery_candidate",
    "sparse_l1_decision",
]
