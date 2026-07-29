from __future__ import annotations

import pytest

from proofalign.integrity_v4_models import command_digest
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
    RecoveryCandidate,
    RecoveryMode,
    RecoveryTransactionGate,
    ShadowJointTrajectory,
    SparseL1Verdict,
    TrustedJointState,
    assess_shadow_joint_trajectory,
    select_recovery_candidate,
    sparse_l1_decision,
)
from proofalign.semantic_local_checker import LocalActionAssessment


COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
COMMAND_SHAPE = (1, 7)


def _assessment(
    *,
    known: bool = True,
    compatible: bool = True,
    violations: tuple[str, ...] = (),
    preconditions: tuple[str, ...] = (),
    progress: float | None = 0.003,
    unknown_reason: str | None = None,
) -> LocalActionAssessment:
    return LocalActionAssessment(
        known=known,
        semantic_compatible=compatible,
        motion_atoms=(),
        precondition_atoms=preconditions,
        predicted_effect_atoms=(),
        violation_atoms=violations,
        progress_margin=progress,
        target="cup",
        part=None,
        region="plate",
        unknown_reason=unknown_reason,
    )


def _state(
    qpos: tuple[float, float] = (0.95, 0.0),
    *,
    epoch: int = 0,
) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=epoch,
        qpos=qpos,
        qvel=(0.0, 0.0),
        joint_lower=(-1.0, -1.0),
        joint_upper=(1.0, 1.0),
        source_id="qualification-fixture",
    )


def _trajectory(
    state: TrustedJointState,
    positions: tuple[tuple[float, float], ...],
    *,
    command: tuple[float, ...] = COMMAND,
) -> ShadowJointTrajectory:
    return ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(command),
        positions=positions,
        predictor_id="analytic-qualification-v1",
    )


def _candidate(
    state: TrustedJointState,
    *,
    candidate_id: str,
    positions: tuple[tuple[float, float], ...],
    command: tuple[float, ...] = COMMAND,
    hard: tuple[str, ...] = (),
) -> RecoveryCandidate:
    return RecoveryCandidate(
        candidate_id=candidate_id,
        command=command,
        command_shape=COMMAND_SHAPE,
        trajectory=_trajectory(state, positions, command=command),
        hard_violation_atoms=hard,
    )


def test_sparse_l1_clean_block_is_exact_passthrough() -> None:
    decision = sparse_l1_decision(
        _assessment(),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.PASSTHROUGH
    assert decision.exact_passthrough is True
    assert decision.l1_authorization_allowed is True
    assert (
        decision.returned_action_block_digest
        == decision.source_action_block_digest
    )


def test_sparse_l1_progress_is_advisory_without_rewrite() -> None:
    decision = sparse_l1_decision(
        _assessment(progress=0.001),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.PASSTHROUGH
    assert decision.advisory_atoms == (
        "progress_below_historical_2mm",
    )
    assert decision.replan_after_block is True
    assert decision.exact_passthrough is True


@pytest.mark.parametrize(
    "atom",
    (
        "wrong_target",
        "release_outside_valid_place_region",
        "translation_velocity_limit",
        "unexpected_contact_neighborhood:knife",
    ),
)
def test_sparse_l1_recognized_hard_atoms_reject(atom: str) -> None:
    decision = sparse_l1_decision(
        _assessment(compatible=False, violations=(atom,)),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.HARD_REJECT
    assert decision.exact_passthrough is False
    assert decision.returned_action_block_digest is None
    assert decision.l1_authorization_allowed is False


def test_sparse_l1_missing_geometry_is_audited_advisory_bypass() -> None:
    decision = sparse_l1_decision(
        _assessment(
            known=False,
            compatible=False,
            progress=None,
            unknown_reason="missing_destination_geometry",
        ),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.ADVISORY_REPLAN
    assert decision.exact_passthrough is True
    assert decision.l1_authorization_allowed is False
    assert decision.replan_after_block is True


def test_sparse_l1_stale_state_remains_fail_closed() -> None:
    decision = sparse_l1_decision(
        _assessment(
            known=False,
            compatible=False,
            progress=None,
            unknown_reason="stale_observation_state_epoch",
        ),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.UNKNOWN
    assert decision.exact_passthrough is False
    assert decision.returned_action_block_digest is None


def test_unrecognized_violation_remains_fail_closed() -> None:
    decision = sparse_l1_decision(
        _assessment(violations=("new_unqualified_atom",)),
        source_command=COMMAND,
        command_shape=COMMAND_SHAPE,
    )

    assert decision.verdict is SparseL1Verdict.HARD_REJECT
    assert decision.hard_atoms == (
        "unrecognized_violation:new_unqualified_atom",
    )


def test_shadow_assessment_detects_safe_and_risky_trajectories() -> None:
    state = _state()
    safe = assess_shadow_joint_trajectory(
        state,
        _trajectory(state, ((0.8, 0.0), (0.7, 0.0))),
    )
    risky = assess_shadow_joint_trajectory(
        state,
        _trajectory(state, ((0.92, 0.0), (0.99, 0.0))),
    )

    assert safe.known is True
    assert safe.risk_predicted is False
    assert safe.minimum_margin == pytest.approx(0.2)
    assert risky.known is True
    assert risky.risk_predicted is True
    assert risky.first_risk_step == 0


def test_shadow_state_substitution_is_unknown_fail_closed() -> None:
    state = _state()
    other = _state(epoch=1)
    result = assess_shadow_joint_trajectory(
        state,
        _trajectory(other, ((0.8, 0.0),)),
    )

    assert result.known is False
    assert result.risk_predicted is True
    assert result.issues == (
        "shadow_initial_state_binding_mismatch",
    )


def test_recovery_selection_maximizes_margin_and_rejects_hard_atoms() -> None:
    state = _state()
    weaker = _candidate(
        state,
        candidate_id="weaker",
        positions=((0.85, 0.0),),
    )
    stronger = _candidate(
        state,
        candidate_id="stronger",
        positions=((0.7, 0.0),),
        command=(0.2, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
    )
    unsafe = _candidate(
        state,
        candidate_id="unsafe",
        positions=((0.6, 0.0),),
        command=(0.3, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        hard=("workspace_exit",),
    )

    selection = select_recovery_candidate(
        state, (weaker, stronger, unsafe)
    )

    assert selection.selected is stronger
    assert selection.selected_assessment is not None
    assert selection.selected_assessment.terminal_margin == pytest.approx(
        0.3
    )
    assert selection.rejected == (
        ("unsafe", ("workspace_exit",)),
    )


def test_recovery_selection_abstains_when_no_candidate_is_safe() -> None:
    state = _state()
    selection = select_recovery_candidate(
        state,
        (
            _candidate(
                state,
                candidate_id="still-risky",
                positions=((0.96, 0.0),),
            ),
        ),
    )

    assert selection.selected is None
    assert selection.selected_assessment is None
    assert selection.rejected[0][0] == "still-risky"


def test_recovery_candidate_requires_exact_trajectory_command_binding() -> None:
    state = _state()
    with pytest.raises(
        RecoverableAlignmentV12Error,
        match="not bound to command",
    ):
        RecoveryCandidate(
            candidate_id="substituted",
            command=COMMAND,
            command_shape=COMMAND_SHAPE,
            trajectory=_trajectory(
                state,
                ((0.7, 0.0),),
                command=(
                    0.2,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    -1.0,
                ),
            ),
        )


def test_recovery_transaction_revokes_old_policy_and_requires_fresh_new() -> None:
    state = _state()
    candidate = _candidate(
        state,
        candidate_id="recover",
        positions=((0.7, 0.0),),
    )
    selection = select_recovery_candidate(state, (candidate,))
    gate = RecoveryTransactionGate(safe_margin_rad=0.15)
    old_policy = "a" * 64
    new_policy = "b" * 64

    authorization = gate.authorize_recovery(
        triggering_policy_authorization_digest=old_policy,
        trigger_state=state,
        selection=selection,
        now_ns=100,
    )

    assert gate.mode is RecoveryMode.RECOVERY_AUTHORIZED
    assert gate.policy_authorization_allowed(old_policy) is False
    assert gate.policy_authorization_allowed(new_policy) is False

    receipt = gate.consume_recovery(
        authorization,
        command=candidate.command,
        now_ns=101,
    )
    assert len(receipt) == 64
    assert gate.mode is RecoveryMode.AWAITING_RECOVERY_OBSERVATION

    assert gate.complete_recovery(_state((0.7, 0.0), epoch=1)) is True
    assert gate.mode is RecoveryMode.POLICY
    assert gate.policy_authorization_allowed(old_policy) is False
    assert gate.policy_authorization_allowed(new_policy) is True


def test_recovery_transaction_rejects_command_substitution_and_replay() -> None:
    state = _state()
    candidate = _candidate(
        state,
        candidate_id="recover",
        positions=((0.7, 0.0),),
    )
    selection = select_recovery_candidate(state, (candidate,))
    gate = RecoveryTransactionGate()
    authorization = gate.authorize_recovery(
        triggering_policy_authorization_digest="a" * 64,
        trigger_state=state,
        selection=selection,
        now_ns=100,
    )

    with pytest.raises(
        RecoverableAlignmentV12Error,
        match="differs from authorization",
    ):
        gate.consume_recovery(
            authorization,
            command=(0.0,) * 7,
            now_ns=101,
        )

    gate.consume_recovery(
        authorization,
        command=candidate.command,
        now_ns=102,
    )
    with pytest.raises(
        RecoverableAlignmentV12Error,
        match="not authorized",
    ):
        gate.consume_recovery(
            authorization,
            command=candidate.command,
            now_ns=103,
        )


def test_recovery_does_not_complete_below_safe_margin() -> None:
    state = _state()
    candidate = _candidate(
        state,
        candidate_id="recover",
        positions=((0.7, 0.0),),
    )
    selection = select_recovery_candidate(state, (candidate,))
    gate = RecoveryTransactionGate(safe_margin_rad=0.15)
    authorization = gate.authorize_recovery(
        triggering_policy_authorization_digest="a" * 64,
        trigger_state=state,
        selection=selection,
        now_ns=100,
    )
    gate.consume_recovery(
        authorization,
        command=candidate.command,
        now_ns=101,
    )

    assert gate.complete_recovery(_state((0.9, 0.0), epoch=1)) is False
    assert gate.mode is RecoveryMode.AWAITING_RECOVERY_OBSERVATION
