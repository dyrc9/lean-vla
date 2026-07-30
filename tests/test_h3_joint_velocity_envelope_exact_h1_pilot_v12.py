from __future__ import annotations

import numpy as np

from scripts.run_h3_joint_velocity_envelope_exact_h1_pilot_v12 import (
    TARGET_JOINT_INDEX,
    VELOCITY_ENVELOPE_SLOPES_PER_S,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _scoped_joint_limit_velocity_envelope,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -10.0)
        self.actuator_max = np.full(7, 10.0)
        self.joint_pos = np.zeros(7)
        self.joint_pos[TARGET_JOINT_INDEX] = 1.8
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


def test_velocity_envelope_contract_is_frozen_and_exact() -> None:
    config = pilot_config()
    contract = config[
        "controller_joint_velocity_envelope_exact_h1_contract"
    ]

    assert contract["slopes_per_s"] == list(
        VELOCITY_ENVELOPE_SLOPES_PER_S
    )
    assert contract["target_joint_index"] == TARGET_JOINT_INDEX
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["terminal_velocity_envelope_required"] is True
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_scoped_velocity_envelope_brakes_and_removes_wrapper() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    assert "run_controller" not in controller.__dict__

    with _scoped_joint_limit_velocity_envelope(
        robot,
        joint_index=TARGET_JOINT_INDEX,
        joint_side="upper",
        joint_limit=2.0,
        margin_floor=0.15,
        slope=1.0,
    ) as audit:
        torques = controller.run_controller()
        assert torques[TARGET_JOINT_INDEX] == -10.0
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["envelope_activated"] is True
    assert np.isclose(
        audit[0]["allowed_toward_limit_velocity_rad_s"],
        0.05,
    )
    assert (
        controller.run_controller()[TARGET_JOINT_INDEX] == 2.0
    )
