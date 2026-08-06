from __future__ import annotations

import numpy as np

from scripts.run_h3_coupled_inverse_mass_brake_exact_h1_pilot_v12 import (
    TARGET_JOINT_INDEX,
    TORQUE_VERTEX_BLEND_FRACTIONS,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _scoped_coupled_inverse_mass_brake,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.joint_vel = np.zeros(7)
        self.mass_matrix = np.eye(7)
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


def test_coupled_inverse_mass_contract_is_frozen_and_exact() -> None:
    config = pilot_config()
    contract = config[
        "controller_coupled_inverse_mass_brake_exact_h1_contract"
    ]

    assert contract["torque_vertex_blend_fractions"] == list(
        TORQUE_VERTEX_BLEND_FRACTIONS
    )
    assert contract["target_joint_index"] == TARGET_JOINT_INDEX
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["all_torques_within_actuator_limits"] is True
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_scoped_coupled_brake_uses_inverse_mass_vertex() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    assert "run_controller" not in controller.__dict__

    with _scoped_coupled_inverse_mass_brake(
        robot,
        joint_index=TARGET_JOINT_INDEX,
        joint_side="upper",
        blend_fraction=0.5,
    ) as audit:
        torques = controller.run_controller()
        assert torques[TARGET_JOINT_INDEX] == -15.0
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["mass_solve_max_abs_residual"] == 0.0
    assert audit[0]["torque_bound_violation"] is False
    assert (
        audit[0]["vertex_toward_acceleration_term"]
        < audit[0]["nominal_toward_acceleration_term"]
    )
    assert (
        controller.run_controller()[TARGET_JOINT_INDEX] == 50.0
    )
