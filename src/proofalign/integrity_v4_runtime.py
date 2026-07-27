"""Fresh authorization and one-use prefix dispatch for integrity v4.

One ``(H, D)`` ActionBlock is one logical authorization transaction.  The
authorization is consumed when a dispatch session opens; the session then
checks and applies the H actions in order, producing one receipt per action.
No caller can reopen the authorization after a partial dispatch or sink
failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Protocol

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import (
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    IntegrityV4Error,
    PrefixAuthorization,
    PrefixExecutionEvidence,
    StepDispatchReceipt,
    command_digest,
    execution_evidence_binding_issues,
)


AUTHORIZER_ID = "proofalign-v4-fresh-prefix-authorizer"
AUTHORIZER_VERSION = "1"


class TransactionVerdict(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    UNKNOWN = "unknown"
    PENDING = "pending"


@dataclass(frozen=True)
class FreshPrefixAuthorizer:
    """Issue an exact authorization only from current, final v4 artifacts."""

    authorization_ttl_ns: int = 60_000_000_000
    max_artifact_age_ns: int = 60_000_000_000
    authorizer_id: str = AUTHORIZER_ID
    authorizer_version: str = AUTHORIZER_VERSION

    def __post_init__(self) -> None:
        for name in ("authorization_ttl_ns", "max_artifact_age_ns"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise IntegrityV4Error(f"{name} must be a positive integer")
        if not self.authorizer_id or not self.authorizer_version:
            raise IntegrityV4Error(
                "authorizer identity fields must be non-empty"
            )

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "authorizer_id": self.authorizer_id,
                "authorizer_version": self.authorizer_version,
                "authorization_ttl_ns": self.authorization_ttl_ns,
                "max_artifact_age_ns": self.max_artifact_age_ns,
            }
        )

    def authorize(
        self,
        proposal: ActionProposal,
        assessment: ActionBlockAssessment,
        contract: BlockExecutionContract,
        *,
        current_state_epoch: int,
        current_trusted_observation_digest: str,
        now_ns: int,
    ) -> PrefixAuthorization:
        if type(now_ns) is not int or now_ns < 0:
            raise IntegrityV4Error("authorization time must be non-negative")
        if proposal.proposed_at_ns > now_ns:
            raise IntegrityV4Error("action proposal is from the future")
        if assessment.generated_at_ns > now_ns:
            raise IntegrityV4Error("action assessment is from the future")
        if contract.issued_at_ns > now_ns:
            raise IntegrityV4Error("execution contract is from the future")
        if now_ns - contract.issued_at_ns > self.max_artifact_age_ns:
            raise IntegrityV4Error(
                "final assessment/contract transaction is stale"
            )
        return PrefixAuthorization.for_transaction(
            proposal,
            assessment,
            contract,
            authorizer_id=self.authorizer_id,
            authorizer_version=self.authorizer_version,
            authorizer_config_digest=self.config_digest,
            issued_at_ns=now_ns,
            valid_until_ns=now_ns + self.authorization_ttl_ns,
            current_state_epoch=current_state_epoch,
            current_trusted_observation_digest=(
                current_trusted_observation_digest
            ),
        )


@dataclass(frozen=True)
class AppliedAction:
    """Action reported by the sink after its sole side-effecting call."""

    action: tuple[float, ...]
    applied_at_ns: int
    transition: Any = None

    def __post_init__(self) -> None:
        frozen = tuple(float(value) for value in self.action)
        if not frozen:
            raise IntegrityV4Error("applied action must be non-empty")
        if type(self.applied_at_ns) is not int or self.applied_at_ns < 0:
            raise IntegrityV4Error(
                "applied_at_ns must be a non-negative integer"
            )
        # command_digest performs the finite-number validation.
        command_digest(frozen)
        object.__setattr__(self, "action", frozen)


class ActionSink(Protocol):
    sink_id: str

    def apply(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedAction:
        ...


class InMemoryActionSink:
    """No-simulator sink for transaction and fixed-trace tests."""

    sink_id = "proofalign-v4-in-memory-no-action-sink"

    def __init__(self) -> None:
        self.applied: list[AppliedAction] = []

    def apply(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedAction:
        applied = AppliedAction(action=action, applied_at_ns=now_ns)
        self.applied.append(applied)
        return applied


@dataclass
class PrefixDispatchSession:
    """Mutable capability owned by exactly one dispatch boundary."""

    authorization: PrefixAuthorization
    _owner_token: object = field(repr=False)
    _receipts: list[StepDispatchReceipt] = field(
        default_factory=list, repr=False
    )
    _status: str = field(default="open", repr=False)

    @property
    def receipts(self) -> tuple[StepDispatchReceipt, ...]:
        return tuple(self._receipts)

    @property
    def next_step_index(self) -> int:
        return len(self._receipts)

    @property
    def complete(self) -> bool:
        return len(self._receipts) == self.authorization.action_count

    @property
    def status(self) -> str:
        return self._status

    def next_authorized_action(self) -> tuple[float, ...]:
        if self._status != "open":
            raise IntegrityV4Error("prefix dispatch session is not open")
        return self.authorization.action_at(self.next_step_index)


@dataclass(frozen=True)
class OpenDispatchResult:
    verdict: TransactionVerdict
    session: PrefixDispatchSession | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepDispatchResult:
    verdict: TransactionVerdict
    receipt: StepDispatchReceipt | None
    transition: Any = None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionEvaluation:
    verdict: TransactionVerdict
    issues: tuple[str, ...] = ()


class SingleUsePrefixDispatchBoundary:
    """Consume one authorization once and apply its exact actions in order."""

    def __init__(self, sink: ActionSink) -> None:
        self.sink = sink
        self._owner_token = object()
        self._used_authorizations: set[str] = set()
        self._lock = Lock()

    def open(
        self, authorization: PrefixAuthorization, *, now_ns: int
    ) -> OpenDispatchResult:
        issues = []
        if not authorization.is_fresh(now_ns):
            issues.append("prefix authorization is stale or not yet valid")
        with self._lock:
            if (
                authorization.authorization_digest
                in self._used_authorizations
            ):
                issues.append("prefix authorization has already been consumed")
            if issues:
                return OpenDispatchResult(
                    TransactionVerdict.REJECT, None, tuple(issues)
                )
            # Consumption precedes every side effect.  A later substitution,
            # sink failure, or partial episode cannot make this authorization
            # replayable.
            self._used_authorizations.add(
                authorization.authorization_digest
            )
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
        with self._lock:
            session_issue = self._session_issue(session)
            if session_issue is not None:
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(session_issue,),
                )
            authorization = session.authorization
            if not authorization.is_fresh(now_ns):
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(
                        "prefix authorization expired before action dispatch",
                    ),
                )
            expected = authorization.action_at(session.next_step_index)
            try:
                candidate_digest = command_digest(action)
            except (IntegrityV4Error, TypeError, ValueError) as exc:
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(f"invalid dispatch action: {exc}",),
                )
            expected_digest = command_digest(expected)
            if candidate_digest != expected_digest:
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    None,
                    issues=(
                        "dispatch action differs from the exact authorized "
                        f"action at step {session.next_step_index}",
                    ),
                )
            step_index = session.next_step_index
            try:
                applied = self.sink.apply(expected, now_ns=now_ns)
            except Exception as exc:  # pragma: no cover - external sink path.
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.UNKNOWN,
                    None,
                    issues=(
                        "command sink failed: "
                        f"{type(exc).__name__}: {exc}",
                    ),
                )
            receipt = StepDispatchReceipt(
                authorization_digest=authorization.authorization_digest,
                action_block_digest=authorization.action_block_digest,
                assessment_digest=authorization.assessment_digest,
                execution_contract_digest=(
                    authorization.execution_contract_digest
                ),
                episode_nonce=authorization.episode_nonce,
                proposal_index=authorization.proposal_index,
                step_index=step_index,
                action_count=authorization.action_count,
                authorized_action_digest=expected_digest,
                applied_action=applied.action,
                applied_at_ns=applied.applied_at_ns,
                sink_id=self.sink.sink_id,
            )
            session._receipts.append(receipt)
            if receipt.applied_action_digest != expected_digest:
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    receipt,
                    applied.transition,
                    (
                        "command sink reported an action different from the "
                        "exact authorization",
                    ),
                )
            if not authorization.is_fresh(applied.applied_at_ns):
                session._status = "failed"
                return StepDispatchResult(
                    TransactionVerdict.REJECT,
                    receipt,
                    applied.transition,
                    ("sink applied action outside authorization window",),
                )
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
        contract: BlockExecutionContract,
        evidence: PrefixExecutionEvidence,
    ) -> ExecutionEvaluation:
        with self._lock:
            if session._owner_token is not self._owner_token:
                return ExecutionEvaluation(
                    TransactionVerdict.REJECT,
                    ("dispatch session belongs to another boundary",),
                )
            if session._status == "sealed":
                return ExecutionEvaluation(
                    TransactionVerdict.REJECT,
                    ("dispatch session has already been sealed",),
                )
            binding_issues = execution_evidence_binding_issues(
                session.authorization,
                contract,
                session.receipts,
                evidence,
            )
            session._status = "sealed"
        if binding_issues:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT, binding_issues
            )
        if not evidence.observation_window_complete:
            return ExecutionEvaluation(
                TransactionVerdict.PENDING,
                ("effect observation window remains open",),
            )
        if not evidence.prefix_complete:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                ("authorized prefix was not completely consumed",),
            )
        if evidence.observed_violation_atoms:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT,
                (
                    "observer violations: "
                    + ",".join(evidence.observed_violation_atoms),
                ),
            )
        if not evidence.effects_known:
            return ExecutionEvaluation(
                TransactionVerdict.UNKNOWN,
                (
                    "execution effects are unknown: "
                    f"{evidence.unknown_reason}",
                ),
            )
        observed = set(evidence.observed_effect_atoms)
        missing = set(contract.expected_effect_atoms).difference(observed)
        forbidden = set(contract.forbidden_effect_atoms).intersection(
            observed
        )
        issues = []
        if missing:
            issues.append(
                "expected effects missing: " + ",".join(sorted(missing))
            )
        if forbidden:
            issues.append(
                "forbidden effects observed: "
                + ",".join(sorted(forbidden))
            )
        if issues:
            return ExecutionEvaluation(
                TransactionVerdict.REJECT, tuple(issues)
            )
        return ExecutionEvaluation(TransactionVerdict.ALLOW)

    def _session_issue(
        self, session: PrefixDispatchSession
    ) -> str | None:
        if not isinstance(session, PrefixDispatchSession):
            return "invalid prefix dispatch session"
        if session._owner_token is not self._owner_token:
            return "dispatch session belongs to another boundary"
        if session._status != "open":
            return f"dispatch session is {session._status}"
        if session.next_step_index >= session.authorization.action_count:
            return "authorized prefix has already been consumed"
        return None


__all__ = [
    "AUTHORIZER_ID",
    "AUTHORIZER_VERSION",
    "ActionSink",
    "AppliedAction",
    "ExecutionEvaluation",
    "FreshPrefixAuthorizer",
    "InMemoryActionSink",
    "OpenDispatchResult",
    "PrefixDispatchSession",
    "SingleUsePrefixDispatchBoundary",
    "StepDispatchResult",
    "TransactionVerdict",
]
