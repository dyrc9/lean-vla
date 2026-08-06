from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from scripts.run_h3_virtual_joint_guard_beam_replayfix_v12 import (
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _configure_virtual_joint_guard,
    _scoped_virtual_joint_guard,
)


class _ClippedDownstreamController:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)
        self.torques = np.zeros(7)

    def clip_torques(self, torques: np.ndarray) -> np.ndarray:
        return np.clip(
            torques, self.actuator_min, self.actuator_max
        )

    def run_controller(self) -> np.ndarray:
        self.torques = np.full(7, 100.0)
        return self.torques


def test_replayfix_contract_changes_only_torque_audit() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    replayfix = contract["torque_audit_replayfix"]

    assert replayfix["bound_gate_target"] == (
        "downstream_clipped_torque"
    )
    assert replayfix["return_raw_to_original_robot_path"] is True
    assert replayfix["effect_parameters_changed"] is False
    assert contract["virtual_joint_guard_margins_rad"] == [
        0.16,
        0.18,
        0.2,
        0.22,
    ]


def test_replayfix_records_raw_and_clipped_without_dispatch_change() -> None:
    model = SimpleNamespace(
        jnt_qposadr=np.arange(7),
        jnt_range=np.column_stack(
            (np.full(7, -2.0), np.full(7, 2.0))
        ),
        jnt_solref=np.tile([0.02, 1.0], (7, 1)),
        jnt_solimp=np.tile(
            [0.9, 0.95, 0.001, 0.5, 2.0], (7, 1)
        ),
    )
    data = SimpleNamespace(
        qpos=np.zeros(7),
        qvel=np.zeros(7),
        qfrc_constraint=np.zeros(7),
    )
    sim = SimpleNamespace(
        model=model,
        data=data,
        forward=lambda: None,
    )
    env = SimpleNamespace(sim=sim)
    robot = SimpleNamespace(
        controller=_ClippedDownstreamController()
    )
    configuration = _configure_virtual_joint_guard(
        env=env,
        qidx=np.arange(7),
        vidx=np.arange(7),
        target_joint_index=1,
        target_joint_side="upper",
        guard_margin_rad=0.2,
    )

    with _scoped_virtual_joint_guard(
        env,
        robot,
        configuration=configuration,
    ) as audit:
        returned = robot.controller.run_controller()

    assert np.array_equal(returned, np.full(7, 100.0))
    assert audit[0]["raw_controller_torque"] == [100.0] * 7
    assert audit[0]["downstream_clipped_controller_torque"] == (
        [80.0] * 7
    )
    assert audit[0]["downstream_clipping_required"] is True
    assert audit[0]["torque_bound_violation"] is False
