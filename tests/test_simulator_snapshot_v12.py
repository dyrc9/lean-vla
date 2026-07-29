from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.simulator_snapshot_v12 import (
    capture_simulator_snapshot,
    restore_simulator_snapshot,
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
        return np.concatenate(
            ([self.time], self.qpos, self.qvel)
        )


class _Sim:
    def __init__(self) -> None:
        self.data = SimpleNamespace(
            time=1.0,
            qpos=np.asarray([0.2, 0.7]),
            qvel=np.asarray([0.01, 0.02]),
        )
        self.renormalize_non_arm = False
        self.change_arm = False

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
        if self.renormalize_non_arm:
            self.data.qpos[1] += 1e-12
        if self.change_arm:
            self.data.qpos[0] += 1e-6


class _Controller:
    def update(self, *, force: bool) -> None:
        assert force is True

    def reset_goal(self) -> None:
        return None


def test_snapshot_separates_full_state_from_trusted_arm_identity() -> None:
    env = SimpleNamespace(sim=_Sim())
    robot = SimpleNamespace(controller=_Controller())
    snapshot = capture_simulator_snapshot(
        env,
        arm_qpos_indexes=(0,),
        arm_qvel_indexes=(0,),
        source_id="fixture",
    )
    env.sim.data.qpos[:] = 9.0
    env.sim.renormalize_non_arm = True

    assessment = restore_simulator_snapshot(env, robot, snapshot)

    assert assessment.full_state_bitwise_identity is False
    assert assessment.trusted_arm_bitwise_identity is True
    assert assessment.full_state_differing_value_count == 1
    assert assessment.full_state_max_abs_error > 0


def test_snapshot_detects_trusted_arm_restore_failure() -> None:
    env = SimpleNamespace(sim=_Sim())
    robot = SimpleNamespace(controller=_Controller())
    snapshot = capture_simulator_snapshot(
        env,
        arm_qpos_indexes=(0,),
        arm_qvel_indexes=(0,),
        source_id="fixture",
    )
    env.sim.change_arm = True

    assessment = restore_simulator_snapshot(env, robot, snapshot)

    assert assessment.full_state_bitwise_identity is False
    assert assessment.trusted_arm_bitwise_identity is False
