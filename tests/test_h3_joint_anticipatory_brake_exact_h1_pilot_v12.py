from __future__ import annotations

import numpy as np

from scripts.run_h3_joint_anticipatory_brake_exact_h1_pilot_v12 import (
    ACTUATOR_BOUND_FRACTIONS,
    TARGET_JOINT_INDEX,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _scoped_joint_limit_anticipatory_brake,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.joint_pos = np.zeros(7)
        self.joint_vel = np.zeros(7)
        self.torques = np.zeros(7)

    def clip_torques(self, torques: np.ndarray) -> np.ndarray:
        return np.clip(
            torques, self.actuator_min, self.actuator_max
        )

    def run_controller(self) -> np.ndarray:
        self.torques = np.zeros(7)
        self.torques[TARGET_JOINT_INDEX] = 50.0
        return self.torques


class _FakeRobot:
    def __init__(self) -> None:
        self.controller = _FakeController()


def test_anticipatory_brake_contract_is_frozen_and_exact() -> None:
    config = pilot_config()
    contract = config[
        "controller_joint_anticipatory_brake_exact_h1_contract"
    ]

    assert contract["actuator_bound_fractions"] == list(
        ACTUATOR_BOUND_FRACTIONS
    )
    assert contract["target_joint_index"] == TARGET_JOINT_INDEX
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["terminal_non_toward_velocity_required"] is True
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_scoped_anticipatory_brake_starts_immediately_and_restores() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    assert "run_controller" not in controller.__dict__

    with _scoped_joint_limit_anticipatory_brake(
        robot,
        joint_index=TARGET_JOINT_INDEX,
        joint_side="upper",
        actuator_bound_fraction=0.5,
    ) as audit:
        torques = controller.run_controller()
        assert torques[TARGET_JOINT_INDEX] == -40.0
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["requested_brake_torque"] == -40.0
    assert audit[0]["target_joint_torque_clipped"] is False
    assert (
        controller.run_controller()[TARGET_JOINT_INDEX] == 50.0
    )
