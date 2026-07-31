from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from scripts import run_l2_predictive_virtual_brake_v13 as core
from scripts import run_l2_predictive_virtual_brake_v13_shadow_only as runner
from scripts import freeze_predictive_virtual_brake_v13_shadow_only as freezer
from scripts import run_predictive_virtual_brake_v13_shadow_only as study


class _FakeEnvironment:
    def __init__(self, *, target_position: float) -> None:
        self.step_count = 0
        self.sim = SimpleNamespace(
            model=SimpleNamespace(
                jnt_qposadr=np.arange(7),
                jnt_range=np.column_stack(
                    (np.full(7, -2.0), np.full(7, 2.0))
                ),
            ),
            data=SimpleNamespace(
                qpos=np.asarray(
                    [
                        0.0,
                        target_position,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ]
                ),
                qvel=np.zeros(7),
            ),
        )
        self.robots = [
            SimpleNamespace(controller=SimpleNamespace())
        ]

    def step(
        self,
        action: Any,
    ) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        self.step_count += 1
        self.sim.data.qpos[1] += 0.05 * float(
            np.asarray(action).reshape(-1)[0]
        )
        return {
            "qpos": self.sim.data.qpos.copy()
        }, 0.0, False, {}


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

    monkeypatch.setattr(
        core,
        "capture_warmstart_policy_shadow_snapshot",
        capture,
    )
    monkeypatch.setattr(
        core,
        "restore_warmstart_policy_shadow_snapshot",
        restore,
    )
    monkeypatch.setattr(
        core,
        "_robot_arrays",
        lambda env: (
            env.robots[0],
            np.arange(7),
            np.arange(7),
            env.sim.model.jnt_range.copy(),
        ),
    )


def _action(value: float) -> list[float]:
    return [value, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_shadow_only_replays_and_dispatches_without_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shadow_runtime(monkeypatch)
    env = _FakeEnvironment(target_position=1.86)
    wrapped = runner.ShadowOnlyPredictiveEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=runner.PredictiveVirtualBrakeConfig(),
    )

    transition = wrapped.step(_action(1.0))

    audit = wrapped.observations[0]
    assert transition[2] is False
    assert audit["shadow_only_ablation"] is True
    assert audit["counterfactual_brake_triggered"] is True
    assert audit["triggered"] is False
    assert audit["intervened"] is False
    assert audit["deadlock"] is False
    assert audit["candidate_count"] == 0
    assert audit["shadow_env_step_count"] == 1
    assert audit["shadow_restore_identity"] is True
    assert audit["exact_action_identity"] is True
    assert env.step_count == 2


def test_shadow_environment_patch_is_scoped() -> None:
    original = core.PredictiveVirtualBrakeEnvironment

    with runner._patched_environment():
        assert core.PredictiveVirtualBrakeEnvironment is (
            runner.ShadowOnlyPredictiveEnvironment
        )

    assert core.PredictiveVirtualBrakeEnvironment is original


def test_shadow_metrics_make_outcomes_descriptive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        study,
        "_BASE_V13_METRICS",
        lambda _protocol, _evidence: (
            {
                "trigger_count": 0,
                "intervention_count": 0,
            },
            {
                **{
                    name: False
                    for name in study.OUTCOME_GATE_NAMES
                },
                "integrity": True,
            },
        ),
    )

    metrics, gates = study._shadow_metrics({}, {})

    assert gates == {
        "integrity": True,
        "shadow_only_no_active_trigger": True,
        "shadow_only_no_guard_intervention": True,
    }
    assert metrics["descriptive_outcome_gate_results"] == {
        name: False for name in study.OUTCOME_GATE_NAMES
    }


def test_shadow_clean_patch_is_scoped() -> None:
    original: tuple[Any, ...] = (
        study.clean.PROTOCOL_SCHEMA,
        study.clean.EVIDENCE_SCHEMA,
        study.clean.EXPECTED_RUNNER,
        study.clean.AUTHORIZED_STATUS,
        study.clean.DEFAULT_PROTOCOL,
        study.clean.online,
        study.clean._v13_metrics,
        study.clean._enrich,
    )

    with study._patched_clean():
        assert study.clean.PROTOCOL_SCHEMA == study.PROTOCOL_SCHEMA
        assert study.clean.EXPECTED_RUNNER == runner.RUNNER_VARIANT
        assert study.clean.online is runner
        assert study.clean._v13_metrics is study._shadow_metrics
        assert study.clean._enrich is study._shadow_enrich

    assert (
        study.clean.PROTOCOL_SCHEMA,
        study.clean.EVIDENCE_SCHEMA,
        study.clean.EXPECTED_RUNNER,
        study.clean.AUTHORIZED_STATUS,
        study.clean.DEFAULT_PROTOCOL,
        study.clean.online,
        study.clean._v13_metrics,
        study.clean._enrich,
    ) == original


def test_shadow_protocol_uses_clean_runner_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_git = freezer._git

    def clean_status_git(*args: str) -> str:
        if args[:2] == ("status", "--porcelain=v1"):
            return ""
        return original_git(*args)

    monkeypatch.setattr(freezer, "_git", clean_status_git)
    protocol = freezer.build_protocol()

    assert protocol["execution_authorization"] == {
        "clean_exploratory_pilot": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }
    assert protocol["design"]["guard_intervention_enabled"] is False
