"""Typed zero-policy recovery dispatch runtime for v12.2.

The frozen v12 contract gate consumes one complete recovery command before
any side effect.  This module refines that capability into an ordered,
single-owner dispatch session with one receipt per 7D action.  It also binds
recovery completion to a strictly newer trusted-state epoch before a fresh
policy authorization may be considered.

No policy implementation or simulator is imported here.  The in-memory sink
exists only for fixed-trace qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Protocol

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import command_digest
from proofalign.recoverable_alignment_v12 import (
    RecoveryAuthorization,
    RecoveryCandidate,
    RecoveryMode,
    RecoveryTransactionGate,
    RecoverableAlignmentV12Error,
    TrustedJointState,
)


RECOVERY_RUNTIME_SCHEMA = "proofalign.recovery-runtime.v12.2"


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


class RecoveryRuntimeVerdict(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    UNKNOWN = "unknown"


class RecoverySelectionLike(Protocol):
    selected: RecoveryCandidate | None
    selection_digest: str


@dataclass(frozen=True)
class AppliedRecoveryAction:
    action: tuple[float, ...]
    applied_at_ns: int

    def __post_init__(self) -> None:
        frozen = tuple(float(value) for value in self.action)
        if len(frozen) != 7:
            raise RecoverableAlignmentV12Error(
                "applied recovery action must be 7D"
            )
        if type(self.applied_at_ns) is not int or self.applied_at_ns < 0:
            raise RecoverableAlignmentV12Error(
                "applied_at_ns must be non-negative"
            )
        command_digest(frozen)
        object.__setattr__(self, "action", frozen)


class RecoveryActionSink(Protocol):
    sink_id: str

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        ...


class InMemoryRecoveryActionSink:
    """No-simulator sink used only by the frozen fixed-trace gate."""

    sink_id = "proofalign-v12.2-in-memory-recovery-sink"

    def __init__(self) -> None:
        self.applied: list[AppliedRecoveryAction] = []

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        applied = AppliedRecoveryAction(
            action=action,
            applied_at_ns=now_ns,
        )
        self.applied.append(applied)
        return applied


@dataclass(frozen=True)
class RecoveryStepReceipt:
    recovery_authorization_digest: str
    selection_digest: str
    trigger_state_digest: str
    recovery_command_digest: str
    revoked_policy_authorization_digest: str
    step_index: int
    action_count: int
    authorized_action_digest: str
    applied_action: tuple[float, ...]
    applied_at_ns: int
    sink_id: str
    schema: str = RECOVERY_RUNTIME_SCHEMA + ".step-receipt"
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "recovery_authorization_digest",
            "selection_digest",
            "trigger_state_digest",
            "recovery_command_digest",
            "revoked_policy_authorization_digest",
            "authorized_action_digest",
        ):
            _require_digest(name, getattr(self, name))
        if (
            type(self.step_index) is not int
            or type(self.action_count) is not int
            or self.step_index < 0
            or self.action_count <= 0
            or self.step_index >= self.action_count
        ):
            raise RecoverableAlignmentV12Error(
                "recovery receipt step index/count is invalid"
            )
        action = tuple(float(value) for value in self.applied_action)
        if len(action) != 7:
            raise RecoverableAlignmentV12Error(
                "recovery receipt action must be 7D"
            )
        if command_digest(action) != self.authorized_action_digest:
            raise RecoverableAlignmentV12Error(
                "recovery sink action differs from authorized step"
            )
        if type(self.applied_at_ns) is not int or self.applied_at_ns < 0:
            raise RecoverableAlignmentV12Error(
                "recovery receipt time must be non-negative"
            )
        if not isinstance(self.sink_id, str) or not self.sink_id:
            raise RecoverableAlignmentV12Error(
                "recovery sink id must be non-empty"
            )
        object.__setattr__(self, "applied_action", action)
        object.__setattr__(
            self,
            "receipt_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "recovery_authorization_digest": (
                        self.recovery_authorization_digest
                    ),
                    "selection_digest": self.selection_digest,
                    "trigger_state_digest": self.trigger_state_digest,
                    "recovery_command_digest": (
                        self.recovery_command_digest
                    ),
                    "revoked_policy_authorization_digest": (
                        self.revoked_policy_authorization_digest
                    ),
                    "step_index": self.step_index,
                    "action_count": self.action_count,
                    "authorized_action_digest": (
                        self.authorized_action_digest
                    ),
                    "applied_action": action,
                    "applied_at_ns": self.applied_at_ns,
                    "sink_id": self.sink_id,
                }
            ),
        )


@dataclass
class RecoveryDispatchSession:
    authorization: RecoveryAuthorization
    candidate: RecoveryCandidate
    aggregate_consume_receipt_digest: str
    _owner_token: object = field(repr=False)
    _receipts: list[RecoveryStepReceipt] = field(
        default_factory=list, repr=False
    )
    _status: str = field(default="open", repr=False)

    @property
    def receipts(self) -> tuple[RecoveryStepReceipt, ...]:
        return tuple(self._receipts)

    @property
    def next_step_index(self) -> int:
        return len(self._receipts)

    @property
    def action_count(self) -> int:
        return self.candidate.command_shape[0]

    @property
    def complete(self) -> bool:
        return self.next_step_index == self.action_count

    @property
    def status(self) -> str:
        return self._status

    def action_at(self, step_index: int) -> tuple[float, ...]:
        if (
            type(step_index) is not int
            or step_index < 0
            or step_index >= self.action_count
        ):
            raise RecoverableAlignmentV12Error(
                "recovery action index is out of range"
            )
        width = self.candidate.command_shape[1]
        start = step_index * width
        return self.candidate.command[start : start + width]


@dataclass(frozen=True)
class RecoveryOpenResult:
    verdict: RecoveryRuntimeVerdict
    session: RecoveryDispatchSession | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryStepResult:
    verdict: RecoveryRuntimeVerdict
    receipt: RecoveryStepReceipt | None
    issues: tuple[str, ...] = ()


class SingleUseRecoveryDispatchBoundary:
    """Open one recovery capability and dispatch its exact actions in order."""

    def __init__(self, sink: RecoveryActionSink) -> None:
        self.sink = sink
        self._owner_token = object()
        self._used_authorizations: set[str] = set()
        self._lock = Lock()

    def open(
        self,
        gate: RecoveryTransactionGate,
        authorization: RecoveryAuthorization,
        selection: RecoverySelectionLike,
        *,
        now_ns: int,
    ) -> RecoveryOpenResult:
        candidate = selection.selected
        issues = []
        if candidate is None:
            issues.append("recovery selection is empty")
        elif candidate.command_shape[1:] != (7,):
            issues.append("recovery command must have shape (H, 7)")
        if authorization.selection_digest != selection.selection_digest:
            issues.append("recovery selection differs from authorization")
        if (
            candidate is not None
            and authorization.recovery_command_digest
            != candidate.command_digest
        ):
            issues.append("recovery command differs from authorization")
        with self._lock:
            if (
                authorization.authorization_digest
                in self._used_authorizations
            ):
                issues.append(
                    "recovery authorization has already been consumed"
                )
            if issues:
                return RecoveryOpenResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    tuple(issues),
                )
            # Burn the runtime capability before the aggregate gate consume or
            # any sink side effect. A failed/partial path cannot be replayed.
            self._used_authorizations.add(
                authorization.authorization_digest
            )
            try:
                aggregate_receipt = gate.consume_recovery(
                    authorization,
                    command=candidate.command,
                    now_ns=now_ns,
                )
            except (
                RecoverableAlignmentV12Error,
                TypeError,
                ValueError,
            ) as exc:
                return RecoveryOpenResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    (f"aggregate recovery consume failed: {exc}",),
                )
        return RecoveryOpenResult(
            RecoveryRuntimeVerdict.ALLOW,
            RecoveryDispatchSession(
                authorization=authorization,
                candidate=candidate,
                aggregate_consume_receipt_digest=aggregate_receipt,
                _owner_token=self._owner_token,
            ),
        )

    def dispatch_next(
        self,
        session: RecoveryDispatchSession,
        action: tuple[float, ...],
        *,
        now_ns: int,
    ) -> RecoveryStepResult:
        with self._lock:
            issue = self._session_issue(session)
            if issue is not None:
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    (issue,),
                )
            authorization = session.authorization
            if (
                type(now_ns) is not int
                or now_ns < authorization.issued_at_ns
                or now_ns > authorization.valid_until_ns
            ):
                session._status = "failed"
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    ("recovery authorization expired before dispatch",),
                )
            expected = session.action_at(session.next_step_index)
            try:
                supplied_digest = command_digest(action)
            except (TypeError, ValueError) as exc:
                session._status = "failed"
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    (f"invalid recovery action: {exc}",),
                )
            expected_digest = command_digest(expected)
            if supplied_digest != expected_digest:
                session._status = "failed"
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    (
                        "recovery action differs from exact authorized "
                        f"step {session.next_step_index}",
                    ),
                )
            try:
                applied = self.sink.apply_recovery(
                    expected,
                    now_ns=now_ns,
                )
            except Exception as exc:  # pragma: no cover - external sink path.
                session._status = "failed"
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.UNKNOWN,
                    None,
                    (
                        "recovery sink failed: "
                        f"{type(exc).__name__}: {exc}",
                    ),
                )
            if command_digest(applied.action) != expected_digest:
                session._status = "failed"
                return RecoveryStepResult(
                    RecoveryRuntimeVerdict.REJECT,
                    None,
                    ("recovery sink applied a substituted action",),
                )
            receipt = RecoveryStepReceipt(
                recovery_authorization_digest=(
                    authorization.authorization_digest
                ),
                selection_digest=authorization.selection_digest,
                trigger_state_digest=authorization.trigger_state_digest,
                recovery_command_digest=(
                    authorization.recovery_command_digest
                ),
                revoked_policy_authorization_digest=(
                    authorization.revoked_policy_authorization_digest
                ),
                step_index=session.next_step_index,
                action_count=session.action_count,
                authorized_action_digest=expected_digest,
                applied_action=applied.action,
                applied_at_ns=applied.applied_at_ns,
                sink_id=self.sink.sink_id,
            )
            session._receipts.append(receipt)
            if session.complete:
                session._status = "complete"
            return RecoveryStepResult(
                RecoveryRuntimeVerdict.ALLOW,
                receipt,
            )

    def _session_issue(
        self, session: RecoveryDispatchSession
    ) -> str | None:
        if not isinstance(session, RecoveryDispatchSession):
            return "invalid recovery dispatch session"
        if session._owner_token is not self._owner_token:
            return "recovery dispatch session belongs to another boundary"
        if session._status != "open":
            return f"recovery dispatch session is {session._status}"
        if session.next_step_index >= session.action_count:
            return "recovery command has already been consumed"
        return None


class RecoveryRuntimeCoordinator:
    """Bind trigger, recovery dispatch, observation, and fresh-policy epoch."""

    def __init__(
        self,
        *,
        gate: RecoveryTransactionGate,
        boundary: SingleUseRecoveryDispatchBoundary,
    ) -> None:
        self.gate = gate
        self.boundary = boundary
        self._trigger_epoch: int | None = None
        self._triggering_policy_digest: str | None = None
        self._recovered_state: TrustedJointState | None = None

    def trigger_and_open(
        self,
        *,
        triggering_policy_authorization_digest: str,
        trigger_state: TrustedJointState,
        selection: RecoverySelectionLike,
        now_ns: int,
        ttl_ns: int = 5_000_000_000,
    ) -> tuple[RecoveryAuthorization, RecoveryOpenResult]:
        authorization = self.gate.authorize_recovery(
            triggering_policy_authorization_digest=(
                triggering_policy_authorization_digest
            ),
            trigger_state=trigger_state,
            selection=selection,
            now_ns=now_ns,
            ttl_ns=ttl_ns,
        )
        self._trigger_epoch = trigger_state.state_epoch
        self._triggering_policy_digest = (
            triggering_policy_authorization_digest
        )
        opened = self.boundary.open(
            self.gate,
            authorization,
            selection,
            now_ns=now_ns,
        )
        return authorization, opened

    def complete_recovery(
        self,
        session: RecoveryDispatchSession,
        post_state: TrustedJointState,
    ) -> bool:
        if session.status != "complete":
            raise RecoverableAlignmentV12Error(
                "recovery command is not completely dispatched"
            )
        if self._trigger_epoch is None:
            raise RecoverableAlignmentV12Error(
                "recovery trigger epoch is unavailable"
            )
        if post_state.state_epoch <= self._trigger_epoch:
            raise RecoverableAlignmentV12Error(
                "recovery observation must use a fresh state epoch"
            )
        completed = self.gate.complete_recovery(post_state)
        if completed:
            self._recovered_state = post_state
        return completed

    def fresh_policy_authorization_allowed(
        self,
        authorization_digest: str,
        *,
        current_state: TrustedJointState,
    ) -> bool:
        _require_digest("authorization_digest", authorization_digest)
        if (
            self._recovered_state is None
            or self._triggering_policy_digest is None
            or self.gate.mode is not RecoveryMode.POLICY
        ):
            return False
        return (
            authorization_digest != self._triggering_policy_digest
            and current_state.state_digest
            == self._recovered_state.state_digest
            and current_state.state_epoch
            >= self._recovered_state.state_epoch
            and self.gate.policy_authorization_allowed(
                authorization_digest
            )
        )


__all__ = [
    "RECOVERY_RUNTIME_SCHEMA",
    "AppliedRecoveryAction",
    "InMemoryRecoveryActionSink",
    "RecoveryActionSink",
    "RecoveryDispatchSession",
    "RecoveryOpenResult",
    "RecoveryRuntimeCoordinator",
    "RecoveryRuntimeVerdict",
    "RecoveryStepReceipt",
    "RecoveryStepResult",
    "SingleUseRecoveryDispatchBoundary",
]
