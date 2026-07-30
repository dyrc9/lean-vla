from __future__ import annotations

import numpy as np

from scripts.run_h3_joint_damping_exact_h1_pilot_v12 import (
    JOINT_DAMPING_GAINS,
    TARGET_JOINT_INDEX,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _scoped_joint_velocity_damping,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -10.0)
        self.actuator_max = np.full(7, 10.0)
        self.joint_vel = np.zeros(7)
        self.joint_vel[TARGET_JOINT_INDEX] = 0.5
        self.torques = np.zeros(7)

    def clip_torques(self, torques: np.ndarray) -> np.ndarray:
        return np.clip(
            torques, self.actuator_min, self.actuator_max
        )

    def run_controller(self) -> np.ndarray:
        self.torques = np.zeros(7)
        self.torques[TARGET_JOINT_INDEX] = 2.0
        return self.torques


class _FakeRobot:
    def __init__(self) -> None:
        self.controller = _FakeController()


def test_joint_damping_contract_is_frozen_and_exact() -> None:
    config = pilot_config()
    contract = config[
        "controller_joint_damping_exact_h1_contract"
    ]

    assert contract["gains"] == list(JOINT_DAMPING_GAINS)
    assert contract["target_joint_index"] == TARGET_JOINT_INDEX
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert contract["torque_clipped_to_actuator_limits"] is True
    assert (
        contract["wrapper_removed_immediately_after_action"] is True
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_scoped_joint_damping_applies_and_removes_wrapper() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    assert "run_controller" not in controller.__dict__

    with _scoped_joint_velocity_damping(
        robot,
        joint_index=TARGET_JOINT_INDEX,
        gain=5.0,
    ) as audit:
        torques = controller.run_controller()
        assert torques[TARGET_JOINT_INDEX] == -0.5
        assert controller.torques[TARGET_JOINT_INDEX] == -0.5
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["requested_damping_torque"] == -2.5
    assert audit[0]["torque_clipped"] is False
    assert (
        controller.run_controller()[TARGET_JOINT_INDEX] == 2.0
    )
