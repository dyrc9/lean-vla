from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.integrity_v4_models import command_digest
from proofalign.policy_prefix_shadow_v12 import (
    PolicyPrefixShadowVerdict,
    capture_policy_shadow_snapshot,
    decide_policy_prefix_shadow,
    restore_policy_shadow_snapshot,
)
from proofalign.recoverable_alignment_v12 import (
    ShadowJointTrajectory,
    TrustedJointState,
)


def _state(qpos: tuple[float, ...]) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=1,
        qpos=qpos,
        qvel=tuple(0.0 for _ in qpos),
        joint_lower=tuple(-1.0 for _ in qpos),
        joint_upper=tuple(1.0 for _ in qpos),
        source_id="fixture",
    )


def _trajectory(
    state: TrustedJointState,
    positions: tuple[tuple[float, ...], ...],
) -> ShadowJointTrajectory:
    command = tuple(0.0 for _ in range(len(positions) * 7))
    return ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(command),
        positions=positions,
        predictor_id="fixture-shadow",
    )


def test_policy_prefix_decision_allows_exact_safe_prefix() -> None:
    state = _state((0.0, 0.0))
    trajectory = _trajectory(
        state, ((0.1, 0.0), (0.2, 0.0))
    )

    decision, assessment = decide_policy_prefix_shadow(
        state, trajectory
    )

    assert assessment.risk_predicted is False
    assert decision.verdict is PolicyPrefixShadowVerdict.ALLOW_EXACT
    assert (
        decision.authorized_action_block_digest
        == trajectory.action_block_digest
    )


def test_policy_prefix_decision_separates_replan_from_recovery() -> None:
    safe = _state((0.0, 0.0))
    entering = _trajectory(
        safe, ((0.5, 0.0), (0.95, 0.0))
    )
    replan, _ = decide_policy_prefix_shadow(safe, entering)

    triggered = _state((0.95, 0.0))
    remaining = _trajectory(
        triggered, ((0.7, 0.0), (0.6, 0.0))
    )
    recovery, _ = decide_policy_prefix_shadow(
        triggered, remaining
    )

    assert replan.verdict is PolicyPrefixShadowVerdict.BLOCK_REPLAN
    assert replan.authorized_action_block_digest is None
    assert (
        recovery.verdict
        is PolicyPrefixShadowVerdict.RECOVERY_REQUIRED
    )


def test_policy_prefix_binding_mismatch_fails_closed() -> None:
    state = _state((0.0, 0.0))
    other = _state((0.1, 0.0))
    substituted = _trajectory(
        other, ((0.2, 0.0), (0.3, 0.0))
    )

    decision, assessment = decide_policy_prefix_shadow(
        state, substituted
    )

    assert assessment.known is False
    assert decision.verdict is PolicyPrefixShadowVerdict.UNKNOWN
    assert decision.authorized_action_block_digest is None


class _State:
    def __init__(
        self,
        time: float,
        qpos: np.ndarray,
        qvel: np.ndarray,
    ) -> None:
        self.time = time
        self.qpos = np.array(qpos)
        self.qvel = np.array(qvel)

    def flatten(self) -> np.ndarray:
        return np.concatenate(
            ([self.time], self.qpos, self.qvel)
        )


class _Sim:
    def __init__(self) -> None:
        self.data = SimpleNamespace(
            time=1.0,
            qpos=np.asarray([0.2, 0.7]),
            qvel=np.asarray([0.01, 0.02]),
            ctrl=np.asarray([0.1, 0.2]),
            qfrc_applied=np.asarray([0.0, 0.0]),
            xfrc_applied=np.zeros((1, 6)),
            mocap_pos=np.zeros((1, 3)),
            mocap_quat=np.asarray([[1.0, 0.0, 0.0, 0.0]]),
        )

    def get_state(self) -> _State:
        return _State(
            self.data.time,
            self.data.qpos,
            self.data.qvel,
        )

    def set_state(self, state: _State) -> None:
        self.data.time = state.time
        self.data.qpos[:] = state.qpos
        self.data.qvel[:] = state.qvel

    def forward(self) -> None:
        return None


class _Controller:
    interpolator_pos = None
    interpolator_ori = None

    def __init__(self) -> None:
        self.action_scale = np.ones(6)
        self.action_input_transform = np.zeros(6)
        self.action_output_transform = np.zeros(6)
        self.ee_pos = np.asarray([0.1, 0.2, 0.3])
        self.ee_ori_mat = np.eye(3)
        self.ee_pos_vel = np.zeros(3)
        self.ee_ori_vel = np.zeros(3)
        self.joint_pos = np.asarray([0.2])
        self.joint_vel = np.asarray([0.01])
        self.J_pos = np.ones((3, 1))
        self.J_ori = np.ones((3, 1))
        self.J_full = np.ones((6, 1))
        self.mass_matrix = np.ones((1, 1))
        self.torques = None
        self.initial_joint = np.asarray([0.2])
        self.initial_ee_pos = np.asarray([0.1, 0.2, 0.3])
        self.initial_ee_ori_mat = np.eye(3)
        self.goal_pos = np.asarray([0.1, 0.2, 0.3])
        self.goal_ori = np.eye(3)
        self.relative_ori = np.zeros(3)
        self.ori_ref = None
        self.kp = np.ones(6) * 150.0
        self.kd = np.ones(6) * 10.0
        self.new_update = False


def test_controller_aware_snapshot_restores_all_bound_state() -> None:
    raw = SimpleNamespace(timestep=3, cur_time=0.15, done=False)
    env = SimpleNamespace(sim=_Sim(), env=raw)
    robot = SimpleNamespace(
        controller=_Controller(),
        _ref_joint_pos_indexes=(0,),
        _ref_joint_vel_indexes=(0,),
    )
    snapshot = capture_policy_shadow_snapshot(
        env, robot, source_id="fixture"
    )
    env.sim.data.qpos[:] = 9.0
    env.sim.data.ctrl[:] = 8.0
    robot.controller.goal_pos[:] = 7.0
    robot.controller.new_update = True
    raw.timestep = 99
    raw.cur_time = 9.9
    raw.done = True

    assessment = restore_policy_shadow_snapshot(
        env, robot, snapshot
    )

    assert assessment.full_simulator_state_bitwise_identity is True
    assert assessment.trusted_arm_bitwise_identity is True
    assert assessment.controller_state_identity is True
    assert assessment.simulator_input_identity is True
    assert assessment.environment_clock_identity is True
    assert np.array_equal(
        robot.controller.goal_pos, np.asarray([0.1, 0.2, 0.3])
    )
    assert raw.timestep == 3
