from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from scripts import run_l2_predictive_virtual_brake_v13 as runner


class _FakeEnvironment:
    def __init__(self, *, target_position: float) -> None:
        self.guard_margin: float | None = None
        self.step_count = 0
        self.sim = SimpleNamespace(
            model=SimpleNamespace(
                jnt_qposadr=np.arange(7),
                jnt_range=np.column_stack(
                    (np.full(7, -2.0), np.full(7, 2.0))
                ),
                jnt_solref=np.tile([0.02, 1.0], (7, 1)),
                jnt_solimp=np.tile(
                    [0.9, 0.95, 0.001, 0.5, 2.0], (7, 1)
                ),
            ),
            data=SimpleNamespace(
                qpos=np.asarray(
                    [0.0, target_position, 0.0, 0.0, 0.0, 0.0, 0.0]
                ),
                qvel=np.zeros(7),
                qfrc_constraint=np.zeros(7),
            ),
        )
        self.robots = [
            SimpleNamespace(controller=SimpleNamespace())
        ]

    def step(self, action: Any) -> tuple[dict[str, Any], float, bool, dict]:
        self.step_count += 1
        self.sim.data.qpos[1] += 0.05 * float(
            np.asarray(action).reshape(-1)[0]
        )
        if self.guard_margin is not None:
            self.sim.data.qpos[1] = min(
                self.sim.data.qpos[1],
                2.0 - self.guard_margin,
            )
        return self.get_observation(), 0.0, False, {}

    def get_observation(self) -> dict[str, Any]:
        return {"qpos": self.sim.data.qpos.copy()}


def _patch_shadow_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        current_margin = (
            2.0 - env.sim.data.qpos[target_joint_index]
            if target_joint_side == "upper"
            else env.sim.data.qpos[target_joint_index] + 2.0
        )
        return {
            "model_joint_id": target_joint_index,
            "target_joint_index": target_joint_index,
            "target_joint_side": target_joint_side,
            "guard_margin_rad": guard_margin_rad,
            "configuration_inside_guard_range": (
                current_margin >= guard_margin_rad
            ),
            "configuration_qpos_identity": True,
            "configuration_qvel_identity": True,
            "original_joint_range": [-2.0, 2.0],
            "original_joint_solref": [0.02, 1.0],
            "original_joint_solimp": [0.9, 0.95, 0.001, 0.5, 2.0],
        }

    @contextmanager
    def scope(
        env: Any,
        _robot: Any,
        *,
        configuration: dict[str, Any],
    ) -> Any:
        env.guard_margin = float(configuration["guard_margin_rad"])
        try:
            yield [
                {
                    "target_dof_constraint_force": -12.0,
                    "torque_bound_violation": False,
                }
            ]
        finally:
            env.guard_margin = None

    monkeypatch.setattr(
        runner,
        "capture_warmstart_policy_shadow_snapshot",
        capture,
    )
    monkeypatch.setattr(
        runner,
        "restore_warmstart_policy_shadow_snapshot",
        restore,
    )
    monkeypatch.setattr(runner, "_robot_arrays", arrays)
    monkeypatch.setattr(
        runner, "_configure_virtual_joint_guard", configure
    )
    monkeypatch.setattr(
        runner, "_scoped_virtual_joint_guard", scope
    )
    monkeypatch.setattr(
        runner,
        "_scope_restored",
        lambda _env, _robot, _configuration: True,
    )


def _action(value: float) -> list[float]:
    return [value, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_config_freezes_hard_guard_profile() -> None:
    config = runner.PredictiveVirtualBrakeConfig()
    assert config.guard_margins_rad == (0.16, 0.18, 0.20, 0.22)
    assert config.guard_solref == (0.004, 1.0)
    assert config.guard_solimp == (
        0.999,
        0.9999,
        0.001,
        0.5,
        2.0,
    )
    assert config.target_joint_index == 1
    assert config.target_joint_side == "upper"


def test_trigger_selects_weakest_safe_exact_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shadow_runtime(monkeypatch)
    env = _FakeEnvironment(target_position=1.83)
    wrapped = runner.PredictiveVirtualBrakeEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=runner.PredictiveVirtualBrakeConfig(),
    )

    wrapped.step(_action(1.0))

    audit = wrapped.observations[0]
    assert audit["triggered"] is True
    assert audit["intervened"] is True
    assert audit["deadlock"] is False
    assert audit["selected_guard_margin_rad"] == 0.16
    assert audit["actual_target_margin_rad"] == pytest.approx(0.16)
    assert audit["exact_action_identity"] is True
    assert audit["prediction_execution_margin_error_rad"] == 0.0
    assert audit["shadow_restore_identity"] is True
    assert audit["candidate_restore_identity"] is True
    assert audit["guard_scope_restored"] is True
    assert audit["maximum_abs_target_constraint_force"] == 12.0


def test_nontrigger_replays_then_dispatches_nominal_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shadow_runtime(monkeypatch)
    env = _FakeEnvironment(target_position=1.4)
    wrapped = runner.PredictiveVirtualBrakeEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=runner.PredictiveVirtualBrakeConfig(),
    )

    wrapped.step(_action(1.0))

    audit = wrapped.observations[0]
    assert audit["triggered"] is False
    assert audit["intervened"] is False
    assert audit["deadlock"] is False
    assert audit["shadow_env_step_count"] == 1
    assert env.step_count == 2
    assert env.sim.data.qpos[1] == pytest.approx(1.45)


def test_no_candidate_returns_fail_closed_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shadow_runtime(monkeypatch)
    env = _FakeEnvironment(target_position=1.86)
    wrapped = runner.PredictiveVirtualBrakeEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=runner.PredictiveVirtualBrakeConfig(),
    )

    transition = wrapped.step(_action(1.0))

    audit = wrapped.observations[0]
    assert transition[2] is True
    assert transition[3][runner.DEADLOCK_INFO_KEY] == (
        "no_safe_guard_candidate"
    )
    assert audit["deadlock"] is True
    assert audit["intervened"] is False
    assert audit["executed_action_digest"] is None
    assert env.sim.data.qpos[1] == pytest.approx(1.86)


def test_runner_replaces_legacy_l2_but_restores_arm_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shadow_runtime(monkeypatch)
    raw_env = _FakeEnvironment(target_position=1.4)
    monkeypatch.setattr(
        runner.base,
        "create_env",
        lambda *_args, **_kwargs: raw_env,
    )
    seen: dict[str, Any] = {}

    def fake_v10_run_episode(**kwargs: Any) -> dict[str, Any]:
        seen["l2"] = kwargs["args"].l2_execution_integrity
        env = runner.base.create_env()
        env.step(_action(0.0))
        env.step(_action(1.0))
        return {
            "metadata": {},
            "decision": "max_steps",
            "success_by_done": False,
            "trace": [
                {"step_id": 0, "phase": "wait"},
                {"step_id": 1, "phase": "policy"},
            ],
        }

    monkeypatch.setattr(
        runner.v10, "run_episode", fake_v10_run_episode
    )
    args = SimpleNamespace(
        semantic_runtime=False,
        l1_semantic_alignment="off",
        l2_execution_integrity="on",
        num_steps_wait=1,
    )

    payload = runner.run_episode(args=args)

    assert seen["l2"] == "off"
    assert args.l2_execution_integrity == "on"
    assert payload["metadata"]["four_arm_label"] == "execution_only"
    assert payload["metadata"]["predictive_virtual_brake_active"] is True
    assert (
        payload["trace"][1]["predictive_virtual_brake"]["enabled"]
        is True
    )
