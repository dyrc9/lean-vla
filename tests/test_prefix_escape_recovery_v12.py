from __future__ import annotations

import pytest

from proofalign.integrity_v4_models import command_digest
from proofalign.prefix_escape_recovery_v12 import (
    select_prefix_escape_recovery_candidate,
)
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    ShadowJointTrajectory,
    TrustedJointState,
)


def _state() -> TrustedJointState:
    return TrustedJointState(
        state_epoch=1,
        qpos=(0.95,),
        qvel=(0.0,),
        joint_lower=(-1.0,),
        joint_upper=(1.0,),
        source_id="prefix-fixture",
    )


def _candidate(
    state: TrustedJointState,
    positions: tuple[float, ...],
    *,
    hard: tuple[str, ...] = (),
) -> RecoveryCandidate:
    action = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
    command = action * len(positions)
    return RecoveryCandidate(
        candidate_id="primitive",
        command=command,
        command_shape=(len(positions), 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(command),
            positions=tuple((value,) for value in positions),
            predictor_id="prefix-fixture-v1",
        ),
        hard_violation_atoms=hard,
    )


def test_shortest_safe_prefix_removes_late_limit_crossing() -> None:
    state = _state()
    candidate = _candidate(
        state,
        (0.90, 0.80, 0.60, 1.01),
        hard=("joint_limit_crossed",),
    )

    selection = select_prefix_escape_recovery_candidate(
        state, (candidate,)
    )

    assert selection.selected is not None
    assert selection.selected.candidate_id == "primitive@h2"
    assert selection.selected.command_shape == (2, 7)
    assert selection.selected_assessment is not None
    assert selection.selected_assessment.terminal_margin == pytest.approx(
        0.2
    )


def test_prefix_selector_abstains_if_no_prefix_reaches_safe_margin() -> None:
    state = _state()
    candidate = _candidate(state, (0.94, 0.93, 0.92))

    selection = select_prefix_escape_recovery_candidate(
        state, (candidate,)
    )

    assert selection.selected is None
    assert selection.evaluated_prefix_count == 3


def test_non_joint_hard_atom_remains_fail_closed_for_every_prefix() -> None:
    state = _state()
    candidate = _candidate(
        state,
        (0.90, 0.80, 0.60),
        hard=("workspace_violation",),
    )

    selection = select_prefix_escape_recovery_candidate(
        state, (candidate,)
    )

    assert selection.selected is None
    assert all(
        "workspace_violation" in row.reasons
        for row in selection.evaluations
    )
