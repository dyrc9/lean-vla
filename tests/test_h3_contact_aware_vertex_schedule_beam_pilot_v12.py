from __future__ import annotations

import numpy as np

from scripts.run_h3_contact_aware_vertex_schedule_beam_pilot_v12 import (
    CONTROLLER_MODE_COUNT,
    SCHEDULE_SWITCH_SUBSTEP_INDEX,
    SCHEDULE_VERTEX_IDS,
    VERTEX_SCHEDULES,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _contact_aware_actuator_vertex,
    _scoped_contact_aware_actuator_vertex_schedule,
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


def test_schedule_beam_contract_freezes_8_by_8_modes() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert len(SCHEDULE_VERTEX_IDS) == 8
    assert len(VERTEX_SCHEDULES) == CONTROLLER_MODE_COUNT == 64
    assert contract["blend_fractions"] == []
    assert contract["vertex_schedules"] == [
        list(schedule) for schedule in VERTEX_SCHEDULES
    ]
    assert contract["schedule_switch_substep_index"] == (
        SCHEDULE_SWITCH_SUBSTEP_INDEX
    ) == 12
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_schedule_scope_switches_vertices_at_frozen_substep() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    first = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=1,
        target_joint_side="upper",
        vertex_id=25,
    )
    second = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=1,
        target_joint_side="upper",
        vertex_id=9,
    )

    with _scoped_contact_aware_actuator_vertex_schedule(
        robot,
        target_joint_index=1,
        target_joint_side="upper",
        first_vertex_id=25,
        second_vertex_id=9,
        switch_substep_index=12,
    ) as audit:
        applied = [controller.run_controller() for _ in range(13)]
        assert all(
            np.array_equal(value, first)
            for value in applied[:12]
        )
        assert np.array_equal(applied[12], second)

    assert "run_controller" not in controller.__dict__
    assert [row["schedule_phase_index"] for row in audit] == (
        [0] * 12 + [1]
    )
    assert audit[11]["applied_vertex_id"] == 25
    assert audit[12]["applied_vertex_id"] == 9
    assert not any(row["torque_bound_violation"] for row in audit)
