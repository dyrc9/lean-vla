"""Runtime adapters for independent online L1/L2 treatment arms.

The frozen M2/base runner remains byte-identical.  This module supplies:

* a semantic-only dispatch boundary that preserves the checked L1 ActionBlock
  while deliberately disabling L2 exact-dispatch/effect enforcement; and
* an execution-only authorization/session schema that binds a raw policy
  source chunk without pretending that semantic alignment was enabled.

Neither adapter changes the existing v4 digest domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from threading import Lock
from typing import Any, Iterable

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import (
    PrefixAuthorization,
    StepDispatchReceipt,
    command_digest,
)
from proofalign.integrity_v4_runtime import (
    ActionSink,
    ExecutionEvaluation,
    OpenDispatchResult,
    PrefixDispatchSession,
    StepDispatchResult,
    TransactionVerdict,
)


EXECUTION_ONLY_SCHEMA = "proofalign.execution-only-prefix-v1"


class L2OnlineArmError(ValueError):
    """Raised when an independent online-arm record is malformed."""


def _digest(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise L2OnlineArmError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _action(value: Iterable[float]) -> tuple[float, ...]:
    try:
        frozen = tuple(float(component) for component in value)
    except (TypeError, ValueError) as exc:
        raise L2OnlineArmError("action must be numeric") from exc
    if len(frozen) != 7:
        raise L2OnlineArmError("action must be a 7D LIBERO command")
    if any(not isfinite(component) for component in frozen):
        raise L2OnlineArmError("action must be finite")
    return frozen


@dataclass(frozen=True)
class ExecutionOnlyPrefixAuthorization:
    """Exact raw-policy ActionBlock authorization with no L1 claim."""

    episode_nonce: str
    proposal_index: int
    source_policy_chunk_digest: str
    policy_observation_digest: str
    actions: tuple[tuple[float, ...], ...]
    issued_at_ns: int
    valid_until_ns: int
    authorization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.episode_nonce:
            raise L2OnlineArmError("episode_nonce must be non-empty")
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise L2OnlineArmError(
                "proposal_index must be a non-negative integer"
            )
        _digest(
            "source_policy_chunk_digest",
            self.source_policy_chunk_digest,
        )
        _digest(
            "policy_observation_digest",
            self.policy_observation_digest,
        )
        actions = tuple(_action(action) for action in self.actions)
        if not actions:
            raise L2OnlineArmError(
                "execution-only authorization requires a non-empty prefix"
            )
        if type(self.issued_at_ns) is not int or self.issued_at_ns < 0:
            raise L2OnlineArmError(
                "issued_at_ns must be a non-negative integer"
            )
        if (
            type(self.valid_until_ns) is not int
            or self.valid_until_ns <= self.issued_at_ns
        ):
            raise L2OnlineArmError(
                "authorization validity window must be non-empty"
            )
        object.__setattr__(self, "actions", actions)
        object.__setattr__(
            self,
            "authorization_digest",
            digest_payload(self.payload()),
        )

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def action_chunk_digest(self) -> str:
        return digest_payload(
            {
                "schema": f"{EXECUTION_ONLY_SCHEMA}.action-chunk",
                "shape": (len(self.actions), 7),
                "actions": self.actions,
            }
        )

    def action_at(self, index: int) -> tuple[float, ...]:
        if type(index) is not int or not 0 <= index < len(self.actions):
            raise L2OnlineArmError(
                "authorized action index is out of range"
            )
        return self.actions[index]

    def is_fresh(self, now_ns: int) -> bool:
        return (
            type(now_ns) is int
            and self.issued_at_ns <= now_ns <= self.valid_until_ns
        )

    def payload(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ONLY_SCHEMA,
            "authorization_basis": "raw_policy_source_action_chunk",
            "l1_semantic_alignment": False,
            "l2_execution_integrity": True,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "source_policy_chunk_digest": (
                self.source_policy_chunk_digest
            ),
            "policy_observation_digest": (
                self.policy_observation_digest
            ),
            "actions": self.actions,
            "issued_at_ns": self.issued_at_ns,
            "valid_until_ns": self.valid_until_ns,
        }


@dataclass(frozen=True)
class ExecutionOnlyStepReceipt:
    authorization_digest: str
    action_chunk_digest: str
    episode_nonce: str
    proposal_index: int
    step_index: int
    action_count: int
    authorized_action_digest: str
    reported_action: tuple[float, ...]
    applied_at_ns: int
    sink_id: str
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "authorization_digest",
            "action_chunk_digest",
            "authorized_action_digest",
        ):
            _digest(name, getattr(self, name))
        if not self.episode_nonce or not self.sink_id:
            raise L2OnlineArmError(
                "episode_nonce and sink_id must be non-empty"
            )
        if (
            type(self.proposal_index) is not int
            or self.proposal_index < 0
            or type(self.step_index) is not int
            or self.step_index < 0
            or type(self.action_count) is not int
            or self.action_count <= 0
            or self.step_index >= self.action_count
        ):
            raise L2OnlineArmError(
                "receipt indices/count are inconsistent"
            )
        if type(self.applied_at_ns) is not int or self.applied_at_ns < 0:
            raise L2OnlineArmError(
                "applied_at_ns must be a non-negative integer"
            )
        object.__setattr__(
            self,
            "reported_action",
            _action(self.reported_action),
        )
        object.__setattr__(
            self,
            "receipt_digest",
            digest_payload(self.payload()),
        )

    @property
    def reported_action_digest(self) -> str:
        return command_digest(self.reported_action)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": f"{EXECUTION_ONLY_SCHEMA}.receipt",
            "authorization_digest": self.authorization_digest,
            "action_chunk_digest": self.action_chunk_digest,
            "episode_nonce": self.episode_nonce,
            "proposal_index": self.proposal_index,
            "step_index": self.step_index,
            "action_count": self.action_count,
            "authorized_action_digest": (
                self.authorized_action_digest
            ),
            "reported_action": self.reported_action,
            "applied_at_ns": self.applied_at_ns,
            "sink_id": self.sink_id,
        }


@dataclass
class ExecutionOnlyPrefixSession:
    authorization: ExecutionOnlyPrefixAuthorization
    _owner_token: object = field(repr=False)
    _receipts: list[ExecutionOnlyStepReceipt] = field(
        default_factory=list,
        repr=False,
    )
    _status: str = field(default="open", repr=False)

    @property
    def receipts(self) -> tuple[ExecutionOnlyStepReceipt, ...]:
        return tuple(self._receipts)

    @property
    def next_step_index(self) -> int:
        return len(self._receipts)

    @property
    def complete(self) -> bool:
        return (
            len(self._receipts)
            == self.authorization.action_count
        )


@dataclass(frozen=True)
class ExecutionOnlyOpenResult:
    verdict: TransactionVerdict
    session: ExecutionOnlyPrefixSession | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionOnlyStepResult:
    verdict: TransactionVerdict
    receipt: ExecutionOnlyStepReceipt | None
    transition: Any = None
    issues: tuple[str, ...] = ()


class ExecutionOnlyPrefixDispatchBoundary:
    """One-use exact boundary for raw-policy source ActionBlocks."""

    def __init__(self, sink: ActionSink) -> None:
        self.sink = sink
        self._owner_token = object()
        self._used_authorizations: set[str] = set()
        self._lock = Lock()

    def open(
        self,
        authorization: ExecutionOnlyPrefixAuthorization,
        *,
        now_ns: int,
    ) -> ExecutionOnlyOpenResult:
        issues = []
        if not authorization.is_fresh(now_ns):
            issues.append(
                "execution-only authorization is stale or not yet valid"
            )
        with self._lock:
            if (
                authorization.authorization_digest
                in self._used_authorizations
            ):
                issues.append(
                    "execution-only authorization has already been consumed"
                )
            if issues:
                return ExecutionOnlyOpenResult(
                    TransactionVerdict.REJECT,
                    None,
                    tuple(issues),
                )
            self._used_authorizations.add(
                authorization.authorization_digest
            )
        return ExecutionOnlyOpenResult(
            TransactionVerdict.ALLOW,
            ExecutionOnlyPrefixSession(
                authorization=authorization,
                _owner_token=self._owner_token,
            ),
        )

    def dispatch_next(
        self,
        session: ExecutionOnlyPrefixSession,
        action: Iterable[float],
        *,
        now_ns: int,
    ) -> ExecutionOnlyStepResult:
        with self._lock:
            if session._owner_token is not self._owner_token:
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(
                        "execution-only session belongs to another boundary",
                    ),
                )
            if session._status != "open" or session.complete:
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=("execution-only session is not open",),
                )
            if not session.authorization.is_fresh(now_ns):
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=("execution-only authorization expired",),
                )
            expected = session.authorization.action_at(
                session.next_step_index
            )
            try:
                candidate = _action(action)
            except L2OnlineArmError as exc:
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(f"invalid dispatch action: {exc}",),
                )
            expected_digest = command_digest(expected)
            if command_digest(candidate) != expected_digest:
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(
                        "dispatch action differs from the exact raw-policy "
                        f"authorization at step {session.next_step_index}",
                    ),
                )
            step_index = session.next_step_index
            try:
                applied = self.sink.apply(expected, now_ns=now_ns)
            except Exception as exc:  # pragma: no cover - external sink.
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.UNKNOWN,
                    None,
                    issues=(
                        "command sink failed: "
                        f"{type(exc).__name__}: {exc}",
                    ),
                )
            receipt = ExecutionOnlyStepReceipt(
                authorization_digest=(
                    session.authorization.authorization_digest
                ),
                action_chunk_digest=(
                    session.authorization.action_chunk_digest
                ),
                episode_nonce=session.authorization.episode_nonce,
                proposal_index=session.authorization.proposal_index,
                step_index=step_index,
                action_count=session.authorization.action_count,
                authorized_action_digest=expected_digest,
                reported_action=applied.action,
                applied_at_ns=applied.applied_at_ns,
                sink_id=self.sink.sink_id,
            )
            session._receipts.append(receipt)
            if receipt.reported_action_digest != expected_digest:
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    receipt,
                    applied.transition,
                    (
                        "command sink reported an action different from the "
                        "exact raw-policy authorization",
                    ),
                )
            if not session.authorization.is_fresh(
                applied.applied_at_ns
            ):
                session._status = "failed"
                return ExecutionOnlyStepResult(
                    TransactionVerdict.REJECT,
                    receipt,
                    applied.transition,
                    ("command sink applied outside authorization window",),
                )
            if session.complete:
                session._status = "complete"
            return ExecutionOnlyStepResult(
                TransactionVerdict.ALLOW,
                receipt,
                applied.transition,
            )

    def seal(
        self,
        session: ExecutionOnlyPrefixSession,
        *,
        effects_known: bool,
        observed_violation_atoms: Iterable[str] = (),
        unknown_reason: str | None = None,
    ) -> ExecutionEvaluation:
        if session._owner_token is not self._owner_token:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                ("execution-only session belongs to another boundary",),
            )
        if session._status == "failed":
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                ("execution-only dispatch session has failed",),
            )
        if not session.complete:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                ("authorized raw-policy prefix was not completely consumed",),
            )
        violations = tuple(dict.fromkeys(observed_violation_atoms))
        if violations:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                (
                    "observer violations: "
                    + ",".join(violations),
                ),
            )
        if not effects_known:
            return ExecutionEvaluation(
                TransactionVerdict.UNKNOWN,
                (
                    "execution effects are unknown: "
                    + (unknown_reason or "unspecified"),
                ),
            )
        return ExecutionEvaluation(TransactionVerdict.ALLOW)


class L2DisabledPrefixDispatchBoundary:
    """Shape-compatible v4 boundary with all L2 enforcement disabled."""

    def __init__(self, sink: ActionSink) -> None:
        self.sink = sink
        self._owner_token = object()

    def open(
        self,
        authorization: PrefixAuthorization,
        *,
        now_ns: int,
    ) -> OpenDispatchResult:
        del now_ns
        return OpenDispatchResult(
            TransactionVerdict.ALLOW,
            PrefixDispatchSession(
                authorization=authorization,
                _owner_token=self._owner_token,
            ),
        )

    def dispatch_next(
        self,
        session: PrefixDispatchSession,
        action: tuple[float, ...],
        *,
        now_ns: int,
    ) -> StepDispatchResult:
        if session._owner_token is not self._owner_token:
            return StepDispatchResult(
                TransactionVerdict.REJECT,
                None,
                issues=("dispatch session belongs to another boundary",),
            )
        if session.complete:
            return StepDispatchResult(
                TransactionVerdict.REJECT,
                None,
                issues=("dispatch session is already complete",),
            )
        expected = session.authorization.action_at(
            session.next_step_index
        )
        try:
            applied = self.sink.apply(
                tuple(float(value) for value in action),
                now_ns=now_ns,
            )
        except Exception as exc:  # pragma: no cover - external sink.
            return StepDispatchResult(
                TransactionVerdict.UNKNOWN,
                None,
                issues=(
                    "command sink failed: "
                    f"{type(exc).__name__}: {exc}",
                ),
            )
        receipt = StepDispatchReceipt(
            authorization_digest=(
                session.authorization.authorization_digest
            ),
            action_block_digest=(
                session.authorization.action_block_digest
            ),
            assessment_digest=(
                session.authorization.assessment_digest
            ),
            execution_contract_digest=(
                session.authorization.execution_contract_digest
            ),
            episode_nonce=session.authorization.episode_nonce,
            proposal_index=session.authorization.proposal_index,
            step_index=session.next_step_index,
            action_count=session.authorization.action_count,
            authorized_action_digest=command_digest(expected),
            applied_action=applied.action,
            applied_at_ns=applied.applied_at_ns,
            sink_id=self.sink.sink_id,
        )
        session._receipts.append(receipt)
        if session.complete:
            session._status = "complete"
        return StepDispatchResult(
            TransactionVerdict.ALLOW,
            receipt,
            applied.transition,
        )

    def seal(
        self,
        session: PrefixDispatchSession,
        contract: Any,
        evidence: Any,
    ) -> ExecutionEvaluation:
        del session, contract, evidence
        return ExecutionEvaluation(TransactionVerdict.ALLOW)


def execution_only_authorization_audit(
    authorization: ExecutionOnlyPrefixAuthorization,
) -> dict[str, Any]:
    return {
        **authorization.payload(),
        "action_chunk_digest": authorization.action_chunk_digest,
        "authorization_digest": authorization.authorization_digest,
    }


def execution_only_receipt_audit(
    receipt: ExecutionOnlyStepReceipt,
) -> dict[str, Any]:
    return {
        **receipt.payload(),
        "reported_action_digest": receipt.reported_action_digest,
        "receipt_digest": receipt.receipt_digest,
    }


__all__ = [
    "EXECUTION_ONLY_SCHEMA",
    "ExecutionOnlyOpenResult",
    "ExecutionOnlyPrefixAuthorization",
    "ExecutionOnlyPrefixDispatchBoundary",
    "ExecutionOnlyPrefixSession",
    "ExecutionOnlyStepReceipt",
    "ExecutionOnlyStepResult",
    "L2DisabledPrefixDispatchBoundary",
    "L2OnlineArmError",
    "execution_only_authorization_audit",
    "execution_only_receipt_audit",
]
