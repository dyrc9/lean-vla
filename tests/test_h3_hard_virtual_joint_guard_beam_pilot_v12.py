from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from scripts.run_h3_hard_virtual_joint_guard_beam_pilot_v12 import (
    GUARD_SOLIMP,
    GUARD_SOLREF,
    pilot_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (
    _configure_virtual_joint_guard,
    _scoped_virtual_joint_guard,
)


class _Controller:
    def __init__(self) -> None:
        self.actuator_min = np.full(7, -80.0)
        self.actuator_max = np.full(7, 80.0)

    def clip_torques(self, torques: np.ndarray) -> np.ndarray:
        return np.clip(
            torques, self.actuator_min, self.actuator_max
        )

    def run_controller(self) -> np.ndarray:
        return np.zeros(7)


def test_hard_guard_contract_changes_only_constraint_profile() -> None:
    config = pilot_config()
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]

    assert contract["virtual_joint_guard_solref"] == list(
        GUARD_SOLREF
    )
    assert contract["virtual_joint_guard_solimp"] == list(
        GUARD_SOLIMP
    )
    assert contract["virtual_joint_guard_margins_rad"] == [
        0.16,
        0.18,
        0.2,
        0.22,
    ]
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False


def test_hard_guard_scope_restores_range_and_solver_profile() -> None:
    original_solref = np.tile([0.02, 1.0], (7, 1))
    original_solimp = np.tile(
        [0.9, 0.95, 0.001, 0.5, 2.0], (7, 1)
    )
    model = SimpleNamespace(
        jnt_qposadr=np.arange(7),
        jnt_range=np.column_stack(
            (np.full(7, -2.0), np.full(7, 2.0))
        ),
        jnt_solref=original_solref.copy(),
        jnt_solimp=original_solimp.copy(),
    )
    data = SimpleNamespace(
        qpos=np.zeros(7),
        qvel=np.zeros(7),
        qfrc_constraint=np.zeros(7),
    )
    env = SimpleNamespace(
        sim=SimpleNamespace(
            model=model,
            data=data,
            forward=lambda: None,
        )
    )
    robot = SimpleNamespace(controller=_Controller())
    configuration = _configure_virtual_joint_guard(
        env=env,
        qidx=np.arange(7),
        vidx=np.arange(7),
        target_joint_index=1,
        target_joint_side="upper",
        guard_margin_rad=0.2,
        guard_solref=GUARD_SOLREF,
        guard_solimp=GUARD_SOLIMP,
    )

    with _scoped_virtual_joint_guard(
        env,
        robot,
        configuration=configuration,
    ):
        assert np.array_equal(
            model.jnt_solref[1], GUARD_SOLREF
        )
        assert np.array_equal(
            model.jnt_solimp[1], GUARD_SOLIMP
        )

    assert np.array_equal(
        model.jnt_range[1], [-2.0, 2.0]
    )
    assert np.array_equal(
        model.jnt_solref[1], original_solref[1]
    )
    assert np.array_equal(
        model.jnt_solimp[1], original_solimp[1]
    )
