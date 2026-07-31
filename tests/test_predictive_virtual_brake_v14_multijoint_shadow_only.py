from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from scripts import run_l2_predictive_virtual_brake_v14_multijoint as predecessor
from scripts import freeze_predictive_virtual_brake_v14_multijoint_shadow_only as freezer
from scripts import freeze_predictive_virtual_brake_v14_multijoint_shadow_only_terminal as terminal
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_shadow_only as runner
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as clean
from scripts import run_predictive_virtual_brake_v14_multijoint_shadow_only as shadow


class _ShadowEnvironment:
    def __init__(self) -> None:
        self.step_count = 0
        self.sim = SimpleNamespace(
            model=SimpleNamespace(
                jnt_range=np.column_stack(
                    (np.full(7, -2.0), np.full(7, 2.0))
                ),
            ),
            data=SimpleNamespace(
                qpos=np.linspace(-0.6, 0.6, 7),
            ),
        )
        self.robots = [SimpleNamespace(controller=SimpleNamespace())]

    def step(self, action: Any) -> tuple[dict, float, bool, dict]:
        self.step_count += 1
        self.sim.data.qpos += (
            0.01 * np.asarray(action, dtype=np.float64)[:7]
        )
        return {}, 0.0, False, {}


def test_shadow_only_restores_then_dispatches_exact_action_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _ShadowEnvironment()
    initial = raw.sim.data.qpos.copy()
    monkeypatch.setattr(
        runner.predecessor.core,
        "_robot_arrays",
        lambda env: (
            env.robots[0],
            np.arange(7),
            np.arange(7),
            env.sim.model.jnt_range.copy(),
        ),
    )
    monkeypatch.setattr(
        runner.predecessor.core,
        "capture_warmstart_policy_shadow_snapshot",
        lambda env, _robot, source_id: {
            "qpos": env.sim.data.qpos.copy(),
            "source_id": source_id,
        },
    )

    def restore(env: Any, _robot: Any, snapshot: dict) -> dict:
        env.sim.data.qpos[:] = snapshot["qpos"]
        return {"identity": True}

    monkeypatch.setattr(
        runner.predecessor.core,
        "restore_warmstart_policy_shadow_snapshot",
        restore,
    )
    monkeypatch.setattr(
        runner.predecessor.core,
        "_restore_identity",
        lambda report: report == {"identity": True},
    )
    wrapped = (
        runner.MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment(
            raw,
            wait_steps=0,
            enabled=True,
            config=None,
        )
    )
    action = np.linspace(0.1, 0.7, 7)

    transition = wrapped.step(action)

    assert transition[2] is False
    assert raw.step_count == 2
    assert np.allclose(raw.sim.data.qpos, initial + 0.01 * action)
    audit = wrapped.observations[0]
    assert audit["schema"] == runner.BRAKE_AUDIT_SCHEMA
    assert audit["shadow_only"] is True
    assert audit["intervention_authority_enabled"] is False
    assert audit["guard_candidate_evaluation_performed"] is False
    assert audit["intervened"] is False
    assert audit["deadlock"] is False
    assert audit["candidate_count"] == 0
    assert audit["shadow_env_step_count"] == 1
    assert audit["exact_action_identity"] is True
    assert len(audit["actual_joint_side_margins"]) == 7


def test_shadow_only_environment_patch_is_scoped() -> None:
    original = predecessor.MultiJointPredictiveVirtualBrakeEnvironment

    with runner._patched_predecessor_environment():
        assert (
            predecessor.MultiJointPredictiveVirtualBrakeEnvironment
            is runner.MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment
        )

    assert (
        predecessor.MultiJointPredictiveVirtualBrakeEnvironment
        is original
    )


def test_shadow_only_runner_declares_no_intervention_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted = []
    monkeypatch.setattr(
        runner.predecessor,
        "run_episode",
        lambda **_kwargs: {
            "metadata": {
                "l2_execution_integrity": True,
                "predictive_virtual_brake_active": True,
            },
            "trace": [],
        },
    )
    monkeypatch.setattr(
        runner.v1,
        "_persist_annotated_episode",
        lambda payload: persisted.append(payload),
    )

    payload = runner.run_episode(args=object())

    metadata = payload["metadata"]
    assert metadata["runner_variant"] == runner.RUNNER_VARIANT
    assert metadata["predictive_virtual_brake_shadow_only"] is True
    assert (
        metadata["predictive_virtual_brake_intervention_authority"]
        is False
    )
    assert (
        metadata["predictive_virtual_brake_guard_candidate_evaluation"]
        is False
    )
    assert metadata["predictive_virtual_brake_simultaneous_guarding"] is False
    assert persisted == [payload]


def test_shadow_only_clean_patch_is_scoped_and_restored() -> None:
    original = (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean.EXPECTED_RUNNER,
        clean.online,
        clean._v14_metrics,
        clean._enrich,
    )

    with shadow._patched_predecessor():
        assert clean.PROTOCOL_SCHEMA == shadow.PROTOCOL_SCHEMA
        assert clean.EVIDENCE_SCHEMA == shadow.EVIDENCE_SCHEMA
        assert clean.AUTHORIZED_STATUS == shadow.AUTHORIZED_STATUS
        assert clean.DEFAULT_PROTOCOL == shadow.DEFAULT_PROTOCOL
        assert clean.EXPECTED_RUNNER == runner.RUNNER_VARIANT
        assert clean.online is runner
        assert clean._v14_metrics is shadow._shadow_metrics
        assert clean._enrich is shadow._shadow_enrich

    assert (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean.EXPECTED_RUNNER,
        clean.online,
        clean._v14_metrics,
        clean._enrich,
    ) == original


def test_shadow_metrics_replaces_only_expected_guarding_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = {
        "schema": runner.BRAKE_AUDIT_SCHEMA,
        "actual_joint_side_margins": predecessor._margin_rows(
            np.full((7, 2), 0.5)
        ),
        "enabled": True,
        "screen_performed": True,
        "shadow_only": True,
        "intervention_authority_enabled": False,
        "guard_candidate_evaluation_performed": False,
        "triggered": False,
        "intervened": False,
        "deadlock": False,
        "exact_action_identity": True,
        "shadow_restore_identity": True,
        "candidate_count": 0,
        "eligible_candidate_count": 0,
        "shadow_env_step_count": 1,
        "selected_predicted_joint_side_margins": None,
        "maximum_abs_guarded_constraint_force": 0.0,
        "torque_bound_violation_count": 0,
    }
    episode = {
        "metadata": {
            "runner_variant": runner.RUNNER_VARIANT,
            "predictive_virtual_brake_active": True,
            "predictive_virtual_brake_simultaneous_guarding": False,
            "predictive_virtual_brake_shadow_monitor_active": True,
            "predictive_virtual_brake_shadow_only": True,
            "predictive_virtual_brake_intervention_authority": False,
            "predictive_virtual_brake_guard_candidate_evaluation": False,
            "shadow_only_same_schedule_causal_control": True,
        },
        "trace": [
            {
                "phase": "policy",
                "predictive_virtual_brake": audit,
            }
        ],
    }
    monkeypatch.setattr(
        shadow,
        "_BASE_V14_METRICS",
        lambda _protocol, _evidence: (
            {
                "v14_metadata_mismatch_count": 1,
                "policy_step_count": 1,
                "l2_policy_step_count": 1,
                "intervention_count": 0,
                "deadlock_count": 0,
            },
            {"v14_metadata_matches": False},
        ),
    )
    monkeypatch.setattr(
        shadow,
        "load_json_object",
        lambda _path: episode,
    )
    protocol = {
        "schedule": [
            {
                "episode_id": "episode-0",
                "arm": "execution_only",
            }
        ]
    }
    evidence = {
        "episodes": [
            {
                "episode_id": "episode-0",
                "path": "episode.json",
            }
        ]
    }

    metrics, gates = shadow._shadow_metrics(protocol, evidence)

    assert metrics["v14_metadata_mismatch_count"] == 0
    assert (
        metrics[
            "shadow_only_inherited_expected_guarding_mismatch_count"
        ]
        == 1
    )
    assert gates["v14_metadata_matches"] is True
    assert gates["shadow_only_l2_contract"] is True
    assert gates["shadow_only_zero_intervention_and_deadlock"] is True


def test_shadow_only_freezer_preserves_exact_full_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git(*args: str) -> str:
        if args[:2] == ("status", "--porcelain=v1"):
            return ""
        if args[0] == "rev-parse" and args[1].endswith("^{tree}"):
            return "tree"
        return ""

    monkeypatch.setattr(freezer, "_git", fake_git)

    protocol = freezer.build_protocol(source_commit="commit")

    full = freezer.load_json_object(freezer.FULL_PROTOCOL_PATH)
    assert protocol["schedule"] == full["schedule"]
    assert protocol["schedule_sha256"] == full["schedule_sha256"]
    assert protocol["workloads"] == full["workloads"]
    assert protocol["episode_constants"] == full["episode_constants"]
    assert protocol["fresh_output_root"].endswith("causal1")
    assert (
        protocol["shadow_only_execution_contract"][
            "intervention_authority_enabled"
        ]
        is False
    )
    assert (
        protocol["v14_gates"][
            "maximum_prediction_execution_side_error_rad"
        ]
        == freezer.PREDICTION_TOLERANCE_RAD
    )
    assert protocol["selection"][
        "full_brake_outcomes_observed_before_freeze"
    ] is True


def test_terminal_paired_bootstrap_reports_signed_mean() -> None:
    report = terminal._paired_bootstrap_mean(
        [-4.0, -2.0, 0.0, 2.0],
        resamples=2_000,
        seed=17,
    )

    assert report["estimate"] == -1.0
    assert report["unit_count"] == 4
    assert report["lower"] <= report["estimate"] <= report["upper"]
