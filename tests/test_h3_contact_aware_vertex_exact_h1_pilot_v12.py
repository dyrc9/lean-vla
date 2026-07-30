from __future__ import annotations

import numpy as np

from scripts.run_h3_contact_aware_vertex_exact_h1_pilot_v12 import (
    CONTACT_AWARE_VERTEX_IDS,
    TARGET_JOINT_INDEX,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _contact_aware_actuator_vertex,
    _scoped_contact_aware_actuator_vertex,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.joint_vel = np.zeros(7)
        self.torques = np.zeros(7)

    def run_controller(self) -> np.ndarray:
        self.torques = np.zeros(7)
        return self.torques


class _FakeRobot:
    def __init__(self) -> None:
        self.controller = _FakeController()


def test_contact_aware_vertex_contract_is_frozen_and_exact() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert contract["other_joint_vertex_ids"] == list(
        CONTACT_AWARE_VERTEX_IDS
    )
    assert contract["other_joint_vertex_count"] == 64
    assert contract["target_joint_index"] == TARGET_JOINT_INDEX
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_contact_aware_vertex_mapping_and_scope() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=TARGET_JOINT_INDEX,
        target_joint_side="upper",
        vertex_id=1,
    )
    assert vertex[TARGET_JOINT_INDEX] == -80.0
    assert vertex[0] == 80.0
    assert np.all(vertex[[2, 3, 4, 5, 6]] == -80.0)

    with _scoped_contact_aware_actuator_vertex(
        robot,
        target_joint_index=TARGET_JOINT_INDEX,
        target_joint_side="upper",
        vertex_id=1,
    ) as audit:
        applied = controller.run_controller()
        assert np.array_equal(applied, vertex)
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["torque_bound_violation"] is False
