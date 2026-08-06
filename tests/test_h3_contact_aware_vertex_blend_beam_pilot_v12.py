from __future__ import annotations

import numpy as np

from scripts.run_h3_contact_aware_vertex_blend_beam_pilot_v12 import (
    BEAM_WIDTH,
    CONTACT_VERTEX_IDS,
    CONTROLLER_MODE_COUNT,
    MAX_BEAM_HORIZON,
    VERTEX_BLEND_FRACTIONS,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _contact_aware_actuator_vertex,
    _scoped_contact_aware_actuator_vertex_blend,
)


class _FakeController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.joint_vel = np.zeros(7)
        self.torques = np.zeros(7)

    def clip_torques(self, torques: np.ndarray) -> np.ndarray:
        return np.clip(
            torques, self.actuator_min, self.actuator_max
        )

    def run_controller(self) -> np.ndarray:
        self.torques = np.full(7, 20.0)
        return self.torques


class _FakeRobot:
    def __init__(self) -> None:
        self.controller = _FakeController()


def test_blend_beam_contract_freezes_64_smooth_modes() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    receding = config["receding_horizon"]

    assert len(CONTACT_VERTEX_IDS) == 16
    assert VERTEX_BLEND_FRACTIONS == (0.25, 0.5, 0.75, 1.0)
    assert contract["candidate_vertex_ids"] == list(
        CONTACT_VERTEX_IDS
    )
    assert contract["controller_mode_count"] == (
        CONTROLLER_MODE_COUNT
    ) == 64
    assert contract["beam_width"] == BEAM_WIDTH == 64
    assert contract["maximum_beam_horizon"] == (
        MAX_BEAM_HORIZON
    ) == 4
    assert receding[
        "contact_aware_vertex_beam_blend_fractions"
    ] == list(VERTEX_BLEND_FRACTIONS)
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )


def test_blended_vertex_scope_preserves_nominal_to_vertex_rule() -> None:
    robot = _FakeRobot()
    controller = robot.controller
    vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=1,
        target_joint_side="upper",
        vertex_id=1,
    )

    with _scoped_contact_aware_actuator_vertex_blend(
        robot,
        target_joint_index=1,
        target_joint_side="upper",
        vertex_id=1,
        blend_fraction=0.25,
    ) as audit:
        applied = controller.run_controller()
        expected = 20.0 + 0.25 * (vertex - 20.0)
        assert np.array_equal(applied, expected)
        assert "run_controller" in controller.__dict__

    assert "run_controller" not in controller.__dict__
    assert len(audit) == 1
    assert audit[0]["blend_fraction"] == 0.25
    assert audit[0]["torque_bound_violation"] is False
