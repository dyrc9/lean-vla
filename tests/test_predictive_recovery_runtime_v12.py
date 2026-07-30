from __future__ import annotations

from dataclasses import replace

from proofalign.integrity_v4_models import command_digest
from proofalign.policy_prefix_shadow_v12 import (
    PolicyPrefixShadowVerdict,
    decide_policy_prefix_shadow,
)
from proofalign.predictive_recovery_runtime_v12 import (
    PredictiveRecoveryRouteVerdict,
    PredictiveRecoveryRuntime,
)
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    ShadowJointTrajectory,
    TrustedJointState,
    select_recovery_candidate,
)
from proofalign.recovery_runtime_v12 import (
    InMemoryRecoveryActionSink,
    RecoveryRuntimeVerdict,
)


PREFIX = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
RECOVERY = (
    -0.1,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    -0.1,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
)


def _state(epoch: int, qpos: float) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=epoch,
        qpos=(qpos,),
        qvel=(0.0,),
        joint_lower=(-1.0,),
        joint_upper=(1.0,),
        source_id=f"integrated-{epoch}-{qpos}",
    )


def _decision(state: TrustedJointState):
    trajectory = ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(PREFIX),
        positions=((state.qpos[0],),),
        predictor_id="integrated-policy-shadow-fixture",
    )
    return decide_policy_prefix_shadow(state, trajectory)[0]


def _selection(state: TrustedJointState):
    candidate = RecoveryCandidate(
        candidate_id="move-inward",
        command=RECOVERY,
        command_shape=(2, 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(RECOVERY),
            positions=((0.7,), (0.4,)),
            predictor_id="integrated-recovery-fixture",
        ),
    )
    return select_recovery_candidate(state, (candidate,))


def test_allow_exact_grants_only_matching_prefix() -> None:
    state = _state(4, 0.0)
    decision = _decision(state)
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)

    route = runtime.route(
        decision,
        state,
        submitted_policy_prefix_digest=command_digest(PREFIX),
        recovery_selection=None,
        now_ns=100,
    )

    assert decision.verdict is PolicyPrefixShadowVerdict.ALLOW_EXACT
    assert (
        route.verdict
        is PredictiveRecoveryRouteVerdict.ALLOW_POLICY_EXACT
    )
    assert route.policy_authorization_digest is not None
    assert sink.applied == []


def test_prefix_or_state_substitution_rejects_without_side_effect() -> None:
    state = _state(4, 0.0)
    decision = _decision(state)
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)

    wrong_prefix = runtime.route(
        decision,
        state,
        submitted_policy_prefix_digest=command_digest(RECOVERY),
        recovery_selection=None,
        now_ns=100,
    )
    wrong_state = runtime.route(
        decision,
        _state(4, 0.1),
        submitted_policy_prefix_digest=command_digest(PREFIX),
        recovery_selection=None,
        now_ns=100,
    )

    assert wrong_prefix.verdict is PredictiveRecoveryRouteVerdict.REJECT
    assert wrong_state.verdict is PredictiveRecoveryRouteVerdict.REJECT
    assert sink.applied == []


def test_recovery_route_revokes_old_and_requires_fresh_state() -> None:
    trigger = _state(4, 0.95)
    decision = _decision(trigger)
    selection = _selection(trigger)
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)

    route = runtime.route(
        decision,
        trigger,
        submitted_policy_prefix_digest=command_digest(PREFIX),
        recovery_selection=selection,
        now_ns=100,
    )
    assert decision.verdict is PolicyPrefixShadowVerdict.RECOVERY_REQUIRED
    assert (
        route.verdict
        is PredictiveRecoveryRouteVerdict.RECOVERY_OPENED
    )
    assert route.recovery_session is not None
    assert route.recovery_authorization is not None
    replay = runtime.boundary.open(
        runtime.gate,
        route.recovery_authorization,
        selection,
        now_ns=101,
    )
    assert replay.verdict is RecoveryRuntimeVerdict.REJECT
    for index in range(route.recovery_session.action_count):
        result = runtime.boundary.dispatch_next(
            route.recovery_session,
            route.recovery_session.action_at(index),
            now_ns=102 + index,
        )
        assert result.verdict is RecoveryRuntimeVerdict.ALLOW
    recovered = _state(5, 0.4)
    assert runtime.coordinator.complete_recovery(
        route.recovery_session, recovered
    )
    assert route.policy_authorization_digest is not None
    assert not runtime.gate.policy_authorization_allowed(
        route.policy_authorization_digest
    )
    fresh = command_digest((0.2,))
    assert runtime.coordinator.fresh_policy_authorization_allowed(
        fresh, current_state=recovered
    )
    assert not runtime.coordinator.fresh_policy_authorization_allowed(
        fresh,
        current_state=replace(recovered, source_id="substituted"),
    )
    assert len(sink.applied) == 2


def test_recovery_selection_must_bind_trigger_state() -> None:
    trigger = _state(4, 0.95)
    decision = _decision(trigger)
    selection = _selection(_state(4, -0.95))
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)

    route = runtime.route(
        decision,
        trigger,
        submitted_policy_prefix_digest=command_digest(PREFIX),
        recovery_selection=selection,
        now_ns=100,
    )

    assert route.verdict is PredictiveRecoveryRouteVerdict.REJECT
    assert sink.applied == []


def test_predicted_future_risk_requires_replan_without_authorization() -> None:
    state = _state(4, 0.0)
    trajectory = ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(PREFIX),
        positions=((0.95,),),
        predictor_id="future-risk-fixture",
    )
    decision = decide_policy_prefix_shadow(state, trajectory)[0]
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)

    route = runtime.route(
        decision,
        state,
        submitted_policy_prefix_digest=command_digest(PREFIX),
        recovery_selection=None,
        now_ns=100,
    )

    assert decision.verdict is PolicyPrefixShadowVerdict.BLOCK_REPLAN
    assert (
        route.verdict
        is PredictiveRecoveryRouteVerdict.REPLAN_REQUIRED
    )
    assert route.policy_authorization_digest is None
    assert sink.applied == []
