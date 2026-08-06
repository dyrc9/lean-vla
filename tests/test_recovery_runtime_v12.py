from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import command_digest
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    RecoveryTransactionGate,
    RecoverableAlignmentV12Error,
    ShadowJointTrajectory,
    TrustedJointState,
    select_recovery_candidate,
)
from proofalign.recovery_runtime_v12 import (
    AppliedRecoveryAction,
    InMemoryRecoveryActionSink,
    RecoveryRuntimeCoordinator,
    RecoveryRuntimeVerdict,
    SingleUseRecoveryDispatchBoundary,
)


COMMAND = (
    0.1,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    0.2,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
)


def _state(epoch: int, qpos: float = 0.95) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=epoch,
        qpos=(qpos,),
        qvel=(0.0,),
        joint_lower=(-1.0,),
        joint_upper=(1.0,),
        source_id=f"runtime-state-{epoch}-{qpos}",
    )


def _selection(state: TrustedJointState):
    candidate = RecoveryCandidate(
        candidate_id="escape",
        command=COMMAND,
        command_shape=(2, 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(COMMAND),
            positions=((0.7,), (0.4,)),
            predictor_id="runtime-fixture-v1",
        ),
    )
    return select_recovery_candidate(state, (candidate,))


def _opened():
    trigger = _state(4)
    selection = _selection(trigger)
    sink = InMemoryRecoveryActionSink()
    gate = RecoveryTransactionGate(safe_margin_rad=0.15)
    boundary = SingleUseRecoveryDispatchBoundary(sink)
    coordinator = RecoveryRuntimeCoordinator(
        gate=gate,
        boundary=boundary,
    )
    old_policy = digest_payload({"authorization": "old"})
    authorization, opened = coordinator.trigger_and_open(
        triggering_policy_authorization_digest=old_policy,
        trigger_state=trigger,
        selection=selection,
        now_ns=100,
    )
    assert opened.verdict is RecoveryRuntimeVerdict.ALLOW
    assert opened.session is not None
    return (
        trigger,
        selection,
        sink,
        gate,
        boundary,
        coordinator,
        old_policy,
        authorization,
        opened.session,
    )


def test_happy_path_binds_receipts_and_requires_fresh_policy() -> None:
    (
        _,
        _,
        sink,
        gate,
        boundary,
        coordinator,
        old_policy,
        authorization,
        session,
    ) = _opened()

    for index in range(session.action_count):
        result = boundary.dispatch_next(
            session,
            session.action_at(index),
            now_ns=101 + index,
        )
        assert result.verdict is RecoveryRuntimeVerdict.ALLOW
        assert result.receipt is not None
        assert result.receipt.step_index == index
        assert (
            result.receipt.recovery_authorization_digest
            == authorization.authorization_digest
        )
    assert session.complete is True
    assert len(sink.applied) == 2
    recovered = _state(5, qpos=0.4)
    assert coordinator.complete_recovery(session, recovered) is True
    assert gate.policy_authorization_allowed(old_policy) is False
    assert coordinator.fresh_policy_authorization_allowed(
        old_policy,
        current_state=recovered,
    ) is False
    fresh_policy = digest_payload({"authorization": "fresh"})
    assert coordinator.fresh_policy_authorization_allowed(
        fresh_policy,
        current_state=recovered,
    ) is True
    substituted_state = replace(recovered, source_id="substituted")
    assert coordinator.fresh_policy_authorization_allowed(
        fresh_policy,
        current_state=substituted_state,
    ) is False


def test_recovery_authorization_cannot_be_reopened() -> None:
    (
        _,
        selection,
        _,
        gate,
        boundary,
        _,
        _,
        authorization,
        _,
    ) = _opened()

    replay = boundary.open(
        gate,
        authorization,
        selection,
        now_ns=101,
    )

    assert replay.verdict is RecoveryRuntimeVerdict.REJECT
    assert replay.session is None
    assert "already been consumed" in replay.issues[0]


def test_command_substitution_burns_session_before_sink() -> None:
    (
        _,
        _,
        sink,
        _,
        boundary,
        _,
        _,
        _,
        session,
    ) = _opened()

    substituted = (0.9,) + session.action_at(0)[1:]
    rejected = boundary.dispatch_next(
        session,
        substituted,
        now_ns=101,
    )
    replay = boundary.dispatch_next(
        session,
        session.action_at(0),
        now_ns=102,
    )

    assert rejected.verdict is RecoveryRuntimeVerdict.REJECT
    assert replay.verdict is RecoveryRuntimeVerdict.REJECT
    assert sink.applied == []


def test_cross_boundary_session_is_rejected() -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        session,
    ) = _opened()
    other = SingleUseRecoveryDispatchBoundary(
        InMemoryRecoveryActionSink()
    )

    rejected = other.dispatch_next(
        session,
        session.action_at(0),
        now_ns=101,
    )

    assert rejected.verdict is RecoveryRuntimeVerdict.REJECT
    assert "another boundary" in rejected.issues[0]


class SubstitutingSink:
    sink_id = "substituting-recovery-sink"

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        return AppliedRecoveryAction(
            action=(action[0] + 0.5,) + action[1:],
            applied_at_ns=now_ns,
        )


def test_sink_substitution_fails_closed() -> None:
    trigger = _state(4)
    selection = _selection(trigger)
    gate = RecoveryTransactionGate()
    boundary = SingleUseRecoveryDispatchBoundary(SubstitutingSink())
    coordinator = RecoveryRuntimeCoordinator(
        gate=gate,
        boundary=boundary,
    )
    _, opened = coordinator.trigger_and_open(
        triggering_policy_authorization_digest=digest_payload(
            {"authorization": "old"}
        ),
        trigger_state=trigger,
        selection=selection,
        now_ns=100,
    )
    assert opened.session is not None

    result = boundary.dispatch_next(
        opened.session,
        opened.session.action_at(0),
        now_ns=101,
    )

    assert result.verdict is RecoveryRuntimeVerdict.REJECT
    assert "substituted" in result.issues[0]


def test_incomplete_and_stale_epoch_cannot_complete_recovery() -> None:
    (
        trigger,
        _,
        _,
        _,
        boundary,
        coordinator,
        _,
        _,
        session,
    ) = _opened()

    with pytest.raises(
        RecoverableAlignmentV12Error,
        match="not completely dispatched",
    ):
        coordinator.complete_recovery(session, _state(5, qpos=0.4))
    for index in range(session.action_count):
        boundary.dispatch_next(
            session,
            session.action_at(index),
            now_ns=101 + index,
        )
    with pytest.raises(
        RecoverableAlignmentV12Error,
        match="fresh state epoch",
    ):
        coordinator.complete_recovery(
            session,
            replace(trigger, qpos=(0.4,)),
        )


def test_unsafe_post_state_keeps_policy_blocked() -> None:
    (
        _,
        _,
        _,
        gate,
        boundary,
        coordinator,
        _,
        _,
        session,
    ) = _opened()
    for index in range(session.action_count):
        boundary.dispatch_next(
            session,
            session.action_at(index),
            now_ns=101 + index,
        )
    unsafe = _state(5, qpos=0.9)

    assert coordinator.complete_recovery(session, unsafe) is False
    fresh = digest_payload({"authorization": "fresh"})
    assert coordinator.fresh_policy_authorization_allowed(
        fresh,
        current_state=unsafe,
    ) is False
    assert gate.mode.value == "awaiting_recovery_observation"
