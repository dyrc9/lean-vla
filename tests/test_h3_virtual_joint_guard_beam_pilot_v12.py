from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from scripts.run_h3_virtual_joint_guard_beam_pilot_v12 import (
    CONTROLLER_MODE_COUNT,
    VIRTUAL_JOINT_GUARD_MARGINS_RAD,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _configure_virtual_joint_guard,
    _scoped_virtual_joint_guard,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.torques = np.zeros(7)

    def run_controller(self) -> np.ndarray:
        self.torques = np.zeros(7)
        return self.torques


class _FakeSim:
    def __init__(self) -> None:
        self.model = SimpleNamespace(
            jnt_qposadr=np.arange(7),
            jnt_range=np.column_stack(
                (np.full(7, -2.0), np.full(7, 2.0))
            ),
        )
        self.data = SimpleNamespace(
            qpos=np.zeros(7),
            qvel=np.zeros(7),
            qfrc_constraint=np.zeros(7),
        )
        self.forward_count = 0

    def forward(self) -> None:
        self.forward_count += 1


class _FakeEnv:
    def __init__(self) -> None:
        self.sim = _FakeSim()


class _FakeRobot:
    def __init__(self) -> None:
        self.controller = _FakeController()


def test_virtual_guard_contract_is_separate_and_exact_action() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert contract["controller_mode_type"] == (
        "virtual_joint_guard_margin"
    )
    assert contract["virtual_joint_guard_margins_rad"] == list(
        VIRTUAL_JOINT_GUARD_MARGINS_RAD
    )
    assert CONTROLLER_MODE_COUNT == 4
    assert min(VIRTUAL_JOINT_GUARD_MARGINS_RAD) > 0.15
    assert contract["guard_range_restore_required"] is True
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_virtual_guard_scope_preserves_state_and_restores_range() -> None:
    env = _FakeEnv()
    robot = _FakeRobot()
    qidx = np.arange(7)
    vidx = np.arange(7)
    env.sim.data.qpos[1] = 1.7
    before_qpos = env.sim.data.qpos.copy()
    before_qvel = env.sim.data.qvel.copy()
    before_range = env.sim.model.jnt_range[1].copy()
    configuration = _configure_virtual_joint_guard(
        env=env,
        qidx=qidx,
        vidx=vidx,
        target_joint_index=1,
        target_joint_side="upper",
        guard_margin_rad=0.2,
    )

    assert configuration["configuration_inside_guard_range"] is True
    assert configuration["configuration_qpos_identity"] is True
    assert configuration["configuration_qvel_identity"] is True
    with _scoped_virtual_joint_guard(
        env,
        robot,
        configuration=configuration,
    ) as audit:
        assert np.array_equal(
            env.sim.model.jnt_range[1], [-2.0, 1.8]
        )
        robot.controller.run_controller()
        env.sim.data.qpos[1] = 1.8
        env.sim.data.qfrc_constraint[1] = -12.0
        robot.controller.run_controller()

    assert np.array_equal(
        env.sim.model.jnt_range[1], before_range
    )
    assert np.array_equal(before_qpos[:1], env.sim.data.qpos[:1])
    assert np.array_equal(before_qvel, env.sim.data.qvel)
    assert env.sim.forward_count == 2
    assert "run_controller" not in robot.controller.__dict__
    assert audit[1]["guard_constraint_near_or_active"] is True
    assert audit[1]["target_dof_constraint_force"] == -12.0
    assert not any(row["torque_bound_violation"] for row in audit)
