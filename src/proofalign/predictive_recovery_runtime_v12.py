"""Compose policy-prefix shadow decisions with typed recovery runtime.

This module is the no-policy, no-simulator transaction boundary between the
v12.4 predictive screen and the v12.2 recovery runtime.  It grants an exact
policy authorization only for an ``allow_exact`` decision.  A
``recovery_required`` decision instead revokes the would-be policy
authorization and opens one single-use recovery session.

The module does not infer a policy, simulate a trajectory, dispatch a policy
action, or inspect a task outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from proofalign.digests import digest_payload
from proofalign.policy_prefix_shadow_v12 import (
    PolicyPrefixShadowDecision,
    PolicyPrefixShadowVerdict,
)
from proofalign.recoverable_alignment_v12 import (
    RecoverySelection,
    RecoveryTransactionGate,
    TrustedJointState,
)
from proofalign.recovery_runtime_v12 import (
    RecoveryActionSink,
    RecoveryAuthorization,
    RecoveryDispatchSession,
    RecoveryRuntimeCoordinator,
    RecoveryRuntimeVerdict,
    SingleUseRecoveryDispatchBoundary,
)


PREDICTIVE_RECOVERY_RUNTIME_SCHEMA = (
    "proofalign.predictive-recovery-runtime.v12.5"
)


class PredictiveRecoveryRouteVerdict(str, Enum):
    ALLOW_POLICY_EXACT = "allow_policy_exact"
    RECOVERY_OPENED = "recovery_opened"
    REPLAN_REQUIRED = "replan_required"
    REJECT = "reject"


@dataclass(frozen=True)
class PredictiveRecoveryRoute:
    verdict: PredictiveRecoveryRouteVerdict
    policy_shadow_decision_digest: str
    initial_state_digest: str
    submitted_policy_prefix_digest: str
    policy_authorization_digest: str | None
    recovery_authorization_digest: str | None
    issues: tuple[str, ...]
    recovery_authorization: RecoveryAuthorization | None = field(
        default=None, repr=False, compare=False
    )
    recovery_session: RecoveryDispatchSession | None = field(
        default=None, repr=False, compare=False
    )
    schema: str = PREDICTIVE_RECOVERY_RUNTIME_SCHEMA + ".route"
    route_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.verdict is PredictiveRecoveryRouteVerdict.ALLOW_POLICY_EXACT:
            if (
                self.policy_authorization_digest is None
                or self.recovery_authorization_digest is not None
                or self.recovery_session is not None
                or self.issues
            ):
                raise ValueError("allow-policy route is malformed")
        elif self.verdict is PredictiveRecoveryRouteVerdict.RECOVERY_OPENED:
            if (
                self.policy_authorization_digest is None
                or self.recovery_authorization_digest is None
                or self.recovery_authorization is None
                or self.recovery_session is None
                or self.issues
            ):
                raise ValueError("recovery route is malformed")
        elif (
            self.policy_authorization_digest is not None
            or self.recovery_authorization_digest is not None
            or self.recovery_session is not None
        ):
            raise ValueError("non-authorizing route carries authorization")
        object.__setattr__(
            self,
            "route_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "verdict": self.verdict.value,
                    "policy_shadow_decision_digest": (
                        self.policy_shadow_decision_digest
                    ),
                    "initial_state_digest": self.initial_state_digest,
                    "submitted_policy_prefix_digest": (
                        self.submitted_policy_prefix_digest
                    ),
                    "policy_authorization_digest": (
                        self.policy_authorization_digest
                    ),
                    "recovery_authorization_digest": (
                        self.recovery_authorization_digest
                    ),
                    "issues": self.issues,
                }
            ),
        )


class PredictiveRecoveryRuntime:
    """Route one bound policy decision into policy or recovery mode."""

    def __init__(
        self,
        sink: RecoveryActionSink,
        *,
        safe_margin_rad: float = 0.15,
    ) -> None:
        self.gate = RecoveryTransactionGate(
            safe_margin_rad=safe_margin_rad
        )
        self.boundary = SingleUseRecoveryDispatchBoundary(sink)
        self.coordinator = RecoveryRuntimeCoordinator(
            gate=self.gate,
            boundary=self.boundary,
        )

    @staticmethod
    def _policy_authorization_digest(
        decision: PolicyPrefixShadowDecision,
        state: TrustedJointState,
        submitted_policy_prefix_digest: str,
    ) -> str:
        return digest_payload(
            {
                "schema": PREDICTIVE_RECOVERY_RUNTIME_SCHEMA
                + ".policy-authorization",
                "policy_shadow_decision_digest": (
                    decision.decision_digest
                ),
                "initial_state_digest": state.state_digest,
                "policy_prefix_digest": submitted_policy_prefix_digest,
            }
        )

    @staticmethod
    def _non_authorizing_route(
        decision: PolicyPrefixShadowDecision,
        state: TrustedJointState,
        submitted_policy_prefix_digest: str,
        verdict: PredictiveRecoveryRouteVerdict,
        *issues: str,
    ) -> PredictiveRecoveryRoute:
        return PredictiveRecoveryRoute(
            verdict=verdict,
            policy_shadow_decision_digest=decision.decision_digest,
            initial_state_digest=state.state_digest,
            submitted_policy_prefix_digest=(
                submitted_policy_prefix_digest
            ),
            policy_authorization_digest=None,
            recovery_authorization_digest=None,
            issues=tuple(issues),
        )

    def route(
        self,
        decision: PolicyPrefixShadowDecision,
        state: TrustedJointState,
        *,
        submitted_policy_prefix_digest: str,
        recovery_selection: RecoverySelection | None,
        now_ns: int,
    ) -> PredictiveRecoveryRoute:
        if decision.initial_state_digest != state.state_digest:
            return self._non_authorizing_route(
                decision,
                state,
                submitted_policy_prefix_digest,
                PredictiveRecoveryRouteVerdict.REJECT,
                "policy shadow state binding differs",
            )
        if (
            decision.action_block_digest
            != submitted_policy_prefix_digest
        ):
            return self._non_authorizing_route(
                decision,
                state,
                submitted_policy_prefix_digest,
                PredictiveRecoveryRouteVerdict.REJECT,
                "submitted policy prefix differs from shadow decision",
            )
        policy_authorization = self._policy_authorization_digest(
            decision, state, submitted_policy_prefix_digest
        )
        if (
            decision.verdict
            is PolicyPrefixShadowVerdict.ALLOW_EXACT
        ):
            if (
                recovery_selection is not None
                or decision.authorized_action_block_digest
                != submitted_policy_prefix_digest
                or not self.gate.policy_authorization_allowed(
                    policy_authorization
                )
            ):
                return self._non_authorizing_route(
                    decision,
                    state,
                    submitted_policy_prefix_digest,
                    PredictiveRecoveryRouteVerdict.REJECT,
                    "allow-exact route violates policy binding",
                )
            return PredictiveRecoveryRoute(
                verdict=(
                    PredictiveRecoveryRouteVerdict.ALLOW_POLICY_EXACT
                ),
                policy_shadow_decision_digest=decision.decision_digest,
                initial_state_digest=state.state_digest,
                submitted_policy_prefix_digest=(
                    submitted_policy_prefix_digest
                ),
                policy_authorization_digest=policy_authorization,
                recovery_authorization_digest=None,
                issues=(),
            )
        if (
            decision.verdict
            is PolicyPrefixShadowVerdict.RECOVERY_REQUIRED
        ):
            selected = (
                recovery_selection.selected
                if recovery_selection is not None
                else None
            )
            if (
                selected is None
                or selected.trajectory.initial_state_digest
                != state.state_digest
                or decision.authorized_action_block_digest is not None
            ):
                return self._non_authorizing_route(
                    decision,
                    state,
                    submitted_policy_prefix_digest,
                    PredictiveRecoveryRouteVerdict.REJECT,
                    "recovery route lacks a state-bound selection",
                )
            authorization, opened = (
                self.coordinator.trigger_and_open(
                    triggering_policy_authorization_digest=(
                        policy_authorization
                    ),
                    trigger_state=state,
                    selection=recovery_selection,
                    now_ns=now_ns,
                )
            )
            if (
                opened.verdict is not RecoveryRuntimeVerdict.ALLOW
                or opened.session is None
            ):
                return self._non_authorizing_route(
                    decision,
                    state,
                    submitted_policy_prefix_digest,
                    PredictiveRecoveryRouteVerdict.REJECT,
                    *opened.issues,
                )
            return PredictiveRecoveryRoute(
                verdict=PredictiveRecoveryRouteVerdict.RECOVERY_OPENED,
                policy_shadow_decision_digest=decision.decision_digest,
                initial_state_digest=state.state_digest,
                submitted_policy_prefix_digest=(
                    submitted_policy_prefix_digest
                ),
                policy_authorization_digest=policy_authorization,
                recovery_authorization_digest=(
                    authorization.authorization_digest
                ),
                issues=(),
                recovery_authorization=authorization,
                recovery_session=opened.session,
            )
        return self._non_authorizing_route(
            decision,
            state,
            submitted_policy_prefix_digest,
            PredictiveRecoveryRouteVerdict.REPLAN_REQUIRED,
            "policy shadow did not authorize exact dispatch or recovery",
        )


__all__ = [
    "PREDICTIVE_RECOVERY_RUNTIME_SCHEMA",
    "PredictiveRecoveryRoute",
    "PredictiveRecoveryRouteVerdict",
    "PredictiveRecoveryRuntime",
]
