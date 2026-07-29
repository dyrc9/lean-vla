from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from proofalign.escape_recovery_v12 import (
    EscapeRecoveryConfig,
    select_escape_recovery_candidate,
    trusted_joint_state_from_libero,
)
from proofalign.integrity_v4_models import command_digest
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    ShadowJointTrajectory,
    TrustedJointState,
)


COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)


def _state(q0: float = 0.95) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=0,
        qpos=(q0, 0.0),
        qvel=(0.0, 0.0),
        joint_lower=(-1.0, -1.0),
        joint_upper=(1.0, 1.0),
        source_id="escape-fixture",
    )


def _candidate(
    state: TrustedJointState,
    candidate_id: str,
    margins_q0: tuple[float, ...],
    *,
    command: tuple[float, ...] = COMMAND,
    hard: tuple[str, ...] = (),
) -> RecoveryCandidate:
    return RecoveryCandidate(
        candidate_id=candidate_id,
        command=command,
        command_shape=(1, 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(command),
            positions=tuple((value, 0.0) for value in margins_q0),
            predictor_id="escape-fixture-v1",
        ),
        hard_violation_atoms=hard,
    )


def test_escape_selector_allows_monotone_exit_from_trigger_region() -> None:
    state = _state()
    candidate = _candidate(
        state,
        "escape",
        (0.945, 0.92, 0.85, 0.70),
    )

    selection = select_escape_recovery_candidate(state, (candidate,))

    assert selection.selected is candidate
    evaluation = selection.evaluations[0]
    assert evaluation.eligible is True
    assert evaluation.first_safe_step == 2
    assert evaluation.minimum_margin == pytest.approx(0.055)
    assert evaluation.terminal_margin == pytest.approx(0.3)


def test_escape_selector_rejects_transient_limit_crossing() -> None:
    state = _state()
    candidate = _candidate(
        state,
        "crosses",
        (1.01, 0.70),
    )

    selection = select_escape_recovery_candidate(state, (candidate,))

    assert selection.selected is None
    assert "joint_limit_crossed" in selection.evaluations[0].reasons


def test_escape_selector_rejects_excessive_transient_loss() -> None:
    state = _state()
    candidate = _candidate(
        state,
        "dips",
        (0.956, 0.70),
    )

    selection = select_escape_recovery_candidate(
        state,
        (candidate,),
        config=EscapeRecoveryConfig(
            max_transient_margin_loss_rad=0.005
        ),
    )

    assert selection.selected is None
    assert (
        "transient_margin_loss_exceeded"
        in selection.evaluations[0].reasons
    )


def test_escape_selector_rejects_candidate_that_never_becomes_safe() -> None:
    state = _state()
    candidate = _candidate(
        state,
        "too-short",
        (0.94, 0.91),
    )

    selection = select_escape_recovery_candidate(state, (candidate,))

    assert selection.selected is None
    assert "safe_margin_not_reached" in selection.evaluations[0].reasons


def test_escape_selector_prefers_earliest_safe_candidate() -> None:
    state = _state()
    early = _candidate(
        state,
        "early",
        (0.94, 0.80, 0.70),
    )
    later = _candidate(
        state,
        "later",
        (0.94, 0.90, 0.80, 0.60),
        command=(0.2, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
    )

    selection = select_escape_recovery_candidate(
        state, (later, early)
    )

    assert selection.selected is early


def test_trusted_joint_state_extracts_exact_robot_indexes() -> None:
    robot = SimpleNamespace(
        _ref_joint_pos_indexes=np.asarray([1, 3]),
        _ref_joint_vel_indexes=np.asarray([1, 3]),
        _ref_joint_indexes=np.asarray([0, 2]),
    )
    sim = SimpleNamespace(
        data=SimpleNamespace(
            qpos=np.asarray([9.0, 0.2, 8.0, -0.3]),
            qvel=np.asarray([7.0, 0.01, 6.0, -0.02]),
        ),
        model=SimpleNamespace(
            jnt_range=np.asarray(
                [
                    [-1.0, 1.0],
                    [-2.0, 2.0],
                    [-0.5, 0.5],
                ]
            )
        ),
    )
    env = SimpleNamespace(robots=[robot], sim=sim)

    state = trusted_joint_state_from_libero(
        env, state_epoch=4, source_id="case-1"
    )

    assert state.qpos == (0.2, -0.3)
    assert state.qvel == (0.01, -0.02)
    assert state.joint_lower == (-1.0, -0.5)
    assert state.joint_upper == (1.0, 0.5)
    assert state.state_epoch == 4
