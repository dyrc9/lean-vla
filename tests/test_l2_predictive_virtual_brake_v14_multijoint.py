from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from scripts import run_l2_predictive_virtual_brake_v14_multijoint as runner
from scripts.run_l2_predictive_virtual_brake_v14_multijoint import (
    MultiJointBrakeConfig,
    MultiJointPredictiveVirtualBrakeEnvironment,
    PredictiveVirtualBrakeV14Error,
    _joint_side_margins,
    _margin_rows,
    _risk_sides,
)


class _FakeEnvironment:
    def __init__(self) -> None:
        self.guard_margins: dict[tuple[int, str], float] = {}
        self.step_count = 0
        self.sim = SimpleNamespace(
            model=SimpleNamespace(
                jnt_qposadr=np.arange(7),
                jnt_range=np.column_stack(
                    (np.full(7, -2.0), np.full(7, 2.0))
                ),
                jnt_solref=np.tile([0.02, 1.0], (7, 1)),
                jnt_solimp=np.tile(
                    [0.9, 0.95, 0.001, 0.5, 2.0],
                    (7, 1),
                ),
            ),
            data=SimpleNamespace(
                qpos=np.array(
                    [-1.83, 0.0, 0.0, 0.0, 0.0, 1.83, 0.0]
                ),
                qvel=np.zeros(7),
                qfrc_constraint=np.zeros(7),
            ),
        )
        self.robots = [
            SimpleNamespace(controller=SimpleNamespace())
        ]

    def step(self, action: Any) -> tuple[dict, float, bool, dict]:
        self.step_count += 1
        values = np.asarray(action, dtype=np.float64)
        self.sim.data.qpos[0] += 0.05 * values[0]
        self.sim.data.qpos[5] += 0.05 * values[1]
        for (joint, side), margin in self.guard_margins.items():
            if side == "lower":
                self.sim.data.qpos[joint] = max(
                    self.sim.data.qpos[joint],
                    -2.0 + margin,
                )
            else:
                self.sim.data.qpos[joint] = min(
                    self.sim.data.qpos[joint],
                    2.0 - margin,
                )
        return {"qpos": self.sim.data.qpos.copy()}, 0.0, False, {}


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def capture(env: Any, _robot: Any, *, source_id: str) -> Any:
        return SimpleNamespace(
            qpos=env.sim.data.qpos.copy(),
            qvel=env.sim.data.qvel.copy(),
            source_id=source_id,
        )

    def restore(env: Any, _robot: Any, snapshot: Any) -> Any:
        env.sim.data.qpos[:] = snapshot.qpos
        env.sim.data.qvel[:] = snapshot.qvel
        return SimpleNamespace(
            trusted_arm_bitwise_identity=True,
            controller_state_identity=True,
            simulator_input_identity=True,
            environment_clock_identity=True,
            qacc_warmstart_identity=True,
        )

    def arrays(env: Any) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray]:
        return (
            env.robots[0],
            np.arange(7),
            np.arange(7),
            env.sim.model.jnt_range.copy(),
        )

    def configure(
        *,
        env: Any,
        qidx: np.ndarray,
        vidx: np.ndarray,
        target_joint_index: int,
        target_joint_side: str,
        guard_margin_rad: float,
        guard_solref: Any,
        guard_solimp: Any,
    ) -> dict[str, Any]:
        del qidx, vidx, guard_solref, guard_solimp
        side_index = 1 if target_joint_side == "upper" else 0
        position = env.sim.data.qpos[target_joint_index]
        current_margin = (
            2.0 - position
            if target_joint_side == "upper"
            else position + 2.0
        )
        guarded_range = [-2.0, 2.0]
        guarded_range[side_index] = (
            2.0 - guard_margin_rad
            if target_joint_side == "upper"
            else -2.0 + guard_margin_rad
        )
        return {
            "model_joint_id": target_joint_index,
            "qpos_address": target_joint_index,
            "dof_address": target_joint_index,
            "target_joint_index": target_joint_index,
            "target_joint_side": target_joint_side,
            "guard_margin_rad": guard_margin_rad,
            "configuration_inside_guard_range": (
                current_margin >= guard_margin_rad
            ),
            "configuration_qpos_identity": True,
            "configuration_qvel_identity": True,
            "original_joint_range": [-2.0, 2.0],
            "guarded_joint_range": guarded_range,
            "original_joint_solref": [0.02, 1.0],
            "original_joint_solimp": [0.9, 0.95, 0.001, 0.5, 2.0],
            "guarded_joint_solref": [0.004, 1.0],
            "guarded_joint_solimp": [0.999, 0.9999, 0.001, 0.5, 2.0],
        }

    @contextmanager
    def scope(
        env: _FakeEnvironment,
        _robot: Any,
        *,
        configurations: list[dict[str, Any]],
    ) -> Any:
        env.guard_margins = {
            (
                int(configuration["target_joint_index"]),
                str(configuration["target_joint_side"]),
            ): float(configuration["guard_margin_rad"])
            for configuration in configurations
        }
        try:
            yield [
                {
                    "torque_bound_violation": False,
                    "guarded_sides": [
                        {
                            "dof_constraint_force": -12.0,
                        }
                        for _configuration in configurations
                    ],
                }
            ]
        finally:
            env.guard_margins = {}

    monkeypatch.setattr(
        runner.core,
        "capture_warmstart_policy_shadow_snapshot",
        capture,
    )
    monkeypatch.setattr(
        runner.core,
        "restore_warmstart_policy_shadow_snapshot",
        restore,
    )
    monkeypatch.setattr(runner.core, "_robot_arrays", arrays)
    monkeypatch.setattr(
        runner.core,
        "_configure_virtual_joint_guard",
        configure,
    )
    monkeypatch.setattr(
        runner,
        "_scoped_multi_joint_guards",
        scope,
    )
    monkeypatch.setattr(
        runner,
        "_scope_restored",
        lambda _env, _robot, _configurations: True,
    )


def test_multijoint_margin_matrix_covers_all_fourteen_sides() -> None:
    limits = np.column_stack(
        (
            np.full(7, -1.0),
            np.full(7, 1.0),
        )
    )
    qpos = np.array([-0.9, 0.0, 0.2, -0.3, 0.4, 0.8, 0.95])

    margins = _joint_side_margins(qpos, limits)
    rows = _margin_rows(margins)

    assert margins.shape == (7, 2)
    assert len(rows) == 7
    assert rows[0] == {
        "joint_index": 0,
        "lower_margin_rad": pytest.approx(0.1),
        "upper_margin_rad": pytest.approx(1.9),
    }
    assert rows[6]["upper_margin_rad"] == pytest.approx(0.05)


def test_multijoint_risk_sides_select_one_worst_side_per_joint() -> None:
    current = np.full((7, 2), 0.5)
    predicted = np.full((7, 2), 0.5)
    current[2, 0] = 0.14
    predicted[5, 1] = 0.08
    # Synthetic narrow-range ambiguity: retain only the worse side.
    current[6] = np.array([0.12, 0.10])

    risks = _risk_sides(
        current,
        predicted,
        trigger_margin_rad=0.15,
    )

    assert [
        (row["joint_index"], row["side"])
        for row in risks
    ] == [(5, "upper"), (6, "upper"), (2, "lower")]
    assert len({row["joint_index"] for row in risks}) == len(risks)


def test_multijoint_configuration_is_frozen_to_all_arm_joints() -> None:
    config = MultiJointBrakeConfig()

    assert config.joint_indices == tuple(range(7))
    assert config.trigger_margin_rad == 0.15
    assert config.safe_margin_floor_rad == 0.15
    assert config.guard_margins_rad == (0.16, 0.18, 0.20, 0.22)

    with pytest.raises(ValueError):
        MultiJointBrakeConfig(joint_indices=(0, 1))


def test_multijoint_margin_validation_fails_closed() -> None:
    with pytest.raises(PredictiveVirtualBrakeV14Error):
        _joint_side_margins(
            np.zeros(6),
            np.zeros((7, 2)),
        )


def test_multijoint_trigger_jointly_guards_two_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime(monkeypatch)
    raw = _FakeEnvironment()
    wrapped = MultiJointPredictiveVirtualBrakeEnvironment(
        raw,
        wait_steps=0,
        enabled=True,
        config=None,
    )

    wrapped.step([-1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    audit = wrapped.observations[0]
    assert audit["triggered"] is True
    assert audit["intervened"] is True
    assert audit["deadlock"] is False
    assert [
        (row["joint_index"], row["side"])
        for row in audit["risk_sides"]
    ] == [(0, "lower"), (5, "upper")]
    assert audit["selected_guard_margin_rad"] == 0.16
    assert audit["actual_minimum_margin_rad"] == pytest.approx(0.16)
    assert audit["candidate_count"] == 4
    assert audit["candidates"][0]["guarded_sides"] == [
        {"joint_index": 0, "side": "lower"},
        {"joint_index": 5, "side": "upper"},
    ]
    assert audit["prediction_execution_margin_error_rad"] == 0.0
    assert audit["maximum_abs_guarded_constraint_force"] == 12.0
    assert audit["exact_action_identity"] is True
