from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.policy_shadow_gripper_state_v15 import (
    capture_gripper_state_policy_shadow_snapshot,
    restore_gripper_state_policy_shadow_snapshot,
)
from proofalign.policy_shadow_dynamic_state_v15 import (
    capture_dynamic_state_policy_shadow_snapshot,
    restore_dynamic_state_policy_shadow_snapshot,
)


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
        return np.concatenate(([self.time], self.qpos, self.qvel))


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
        return _State(self.data.time, self.data.qpos, self.data.qvel)

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


class _Gripper:
    def __init__(self) -> None:
        self.current_action = np.asarray([0.2, -0.2])


class LinearMotionGenerator:
    def __init__(self) -> None:
        self.pos = np.asarray([0.1, 0.2, 0.3])
        self.quat = np.asarray([1.0, 0.0, 0.0, 0.0])
        self.forward = True
        self.step_count = 4


def _fixture() -> tuple[SimpleNamespace, SimpleNamespace]:
    sim = _Sim()
    sim.data.qacc_warmstart = np.asarray([0.3, -0.4])
    raw = SimpleNamespace(
        timestep=3,
        cur_time=0.15,
        done=False,
        mocap_motion_generators={"human": LinearMotionGenerator()},
    )
    env = SimpleNamespace(sim=sim, env=raw)
    robot = SimpleNamespace(
        controller=_Controller(),
        gripper=_Gripper(),
        _ref_joint_pos_indexes=(0,),
        _ref_joint_vel_indexes=(0,),
    )
    return env, robot


def test_gripper_state_snapshot_restores_accumulator() -> None:
    env, robot = _fixture()
    snapshot = capture_gripper_state_policy_shadow_snapshot(
        env, robot, source_id="fixture"
    )
    robot.gripper.current_action = np.asarray([-1.0, 1.0])
    env.sim.data.qpos[:] = 8.0

    assessment = restore_gripper_state_policy_shadow_snapshot(
        env, robot, snapshot
    )

    assert assessment.gripper_class_identity is True
    assert assessment.gripper_current_action_identity is True
    assert assessment.gripper_state_identity is True
    assert assessment.trusted_arm_bitwise_identity is True
    assert np.array_equal(
        robot.gripper.current_action, np.asarray([0.2, -0.2])
    )


def test_gripper_state_snapshot_copies_restored_array() -> None:
    env, robot = _fixture()
    snapshot = capture_gripper_state_policy_shadow_snapshot(
        env, robot, source_id="fixture"
    )
    restore_gripper_state_policy_shadow_snapshot(env, robot, snapshot)

    robot.gripper.current_action[0] = 9.0

    assert snapshot.gripper_current_action == (0.2, -0.2)


def test_dynamic_state_snapshot_rewinds_motion_generator() -> None:
    env, robot = _fixture()
    generator = env.env.mocap_motion_generators["human"]
    snapshot = capture_dynamic_state_policy_shadow_snapshot(
        env, robot, source_id="fixture"
    )
    generator.pos[:] = 9.0
    generator.forward = False
    generator.step_count = 99

    assessment = restore_dynamic_state_policy_shadow_snapshot(
        env, robot, snapshot
    )

    assert assessment.dynamic_motion_registry_identity is True
    assert assessment.dynamic_motion_state_identity is True
    assert assessment.dynamic_motion_generator_count == 1
    assert assessment.runtime_side_state_identity is True
    assert np.array_equal(generator.pos, np.asarray([0.1, 0.2, 0.3]))
    assert generator.forward is True
    assert generator.step_count == 4
