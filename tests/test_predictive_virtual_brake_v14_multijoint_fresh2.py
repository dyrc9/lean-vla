from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_predictive_virtual_brake_v14_multijoint_clean_fresh2 as freezer
from scripts import freeze_predictive_virtual_brake_v14_multijoint_development1_failure as failure
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as development1
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_fresh2 as runner
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as clean
from scripts import run_predictive_virtual_brake_v14_multijoint_clean_fresh2 as fresh2


class _DisabledEnvironment:
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
            0.001 * np.asarray(action, dtype=np.float64)[:7]
        )
        return {}, 0.0, False, {}


def test_fresh2_disabled_arm_records_all_sides_without_single_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _DisabledEnvironment()
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
    wrapped = (
        runner.MultiJointPredictiveVirtualBrakeFresh2Environment(
            raw,
            wait_steps=0,
            enabled=False,
            config=None,
        )
    )

    transition = wrapped.step(np.zeros(7))

    assert transition[2] is False
    assert raw.step_count == 1
    assert len(wrapped.observations) == 1
    audit = wrapped.observations[0]
    assert audit["enabled"] is False
    assert audit["screen_performed"] is False
    assert audit["multi_joint_audit"] is True
    assert audit["joint_side_scope_count"] == 14
    assert len(audit["actual_joint_side_margins"]) == 7
    assert audit["current_joint_side_margins"] is None
    assert audit["unguarded_predicted_joint_side_margins"] is None
    assert audit["shadow_env_step_count"] == 0
    assert audit["exact_action_identity"] is True


def test_fresh2_environment_patch_is_scoped_and_restored() -> None:
    original = development1.MultiJointPredictiveVirtualBrakeEnvironment

    with runner._patched_predecessor_environment():
        assert (
            development1.MultiJointPredictiveVirtualBrakeEnvironment
            is runner.MultiJointPredictiveVirtualBrakeFresh2Environment
        )

    assert (
        development1.MultiJointPredictiveVirtualBrakeEnvironment
        is original
    )


def test_fresh2_runner_changes_only_successor_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted = []

    def fake_run_episode(**_kwargs: Any) -> dict[str, Any]:
        assert (
            development1.MultiJointPredictiveVirtualBrakeEnvironment
            is runner.MultiJointPredictiveVirtualBrakeFresh2Environment
        )
        return {"metadata": {"existing": True}, "trace": []}

    monkeypatch.setattr(
        runner.predecessor,
        "run_episode",
        fake_run_episode,
    )
    monkeypatch.setattr(
        runner.v1,
        "_persist_annotated_episode",
        lambda payload: persisted.append(payload),
    )

    payload = runner.run_episode(args=object())

    assert payload["metadata"]["runner_variant"] == runner.RUNNER_VARIANT
    assert payload["metadata"][
        "fresh2_disabled_arm_single_target_dependency_removed"
    ] is True
    assert payload["metadata"][
        "fresh2_scientific_parameters_changed"
    ] is False
    assert persisted == [payload]


def test_fresh2_clean_wrapper_patch_is_scoped_and_restored() -> None:
    original = (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean.EXPECTED_RUNNER,
        clean.online,
    )

    with fresh2._patched_predecessor():
        assert clean.PROTOCOL_SCHEMA == fresh2.PROTOCOL_SCHEMA
        assert clean.EVIDENCE_SCHEMA == fresh2.EVIDENCE_SCHEMA
        assert clean.AUTHORIZED_STATUS == fresh2.AUTHORIZED_STATUS
        assert clean.DEFAULT_PROTOCOL == fresh2.DEFAULT_PROTOCOL
        assert clean.EXPECTED_RUNNER == runner.RUNNER_VARIANT
        assert clean.online is runner

    assert (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean.EXPECTED_RUNNER,
        clean.online,
    ) == original


def test_development1_failure_report_binds_two_completed_outcomes() -> None:
    report = failure.build_report()

    assert report["classification"] == failure.CLASSIFICATION
    assert report["terminal_state"]["completed_episode_count"] == 2
    assert report["terminal_state"]["failed_sequence_index"] == 2
    assert report["terminal_state"]["failed_arm"] == "vla_only"
    assert len(report["observed_outcomes"]) == 2
    assert report["scientific_status"]["coverage_estimable"] is False
    assert report["scientific_status"][
        "fresh_successor_must_repeat_all_180_episodes"
    ] is True


def test_fresh2_freezer_preserves_development1_design(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    development1_protocol = load_json_object(
        freezer.DEVELOPMENT1_PROTOCOL_PATH
    )
    failure_report = failure.build_report()

    def fake_load(path: Path) -> dict[str, Any]:
        if path == freezer.DEVELOPMENT1_PROTOCOL_PATH:
            return development1_protocol
        if path == freezer.DEVELOPMENT1_FAILURE_PATH:
            return failure_report
        raise AssertionError(path)

    monkeypatch.setattr(freezer, "load_json_object", fake_load)
    monkeypatch.setattr(
        freezer,
        "_git",
        lambda *args: (
            "tree"
            if args[0] == "rev-parse"
            and args[1].endswith("^{tree}")
            else "commit"
            if args[0] == "rev-parse"
            else ""
        ),
    )
    monkeypatch.setattr(
        freezer,
        "_binding",
        lambda path, classification=None: {
            "path": str(path),
            "sha256": "bound",
            **(
                {"classification": classification}
                if classification is not None
                else {}
            ),
        },
    )
    monkeypatch.setattr(freezer, "SOURCE_PATHS", ("source.py",))
    monkeypatch.setattr(
        freezer,
        "file_sha256",
        lambda _path: "source-sha",
    )

    protocol = freezer.build_protocol(source_commit="commit")

    for field in ("schedule", "workloads", "design", "analysis", "v14_gates"):
        assert protocol[field] == development1_protocol[field]
    assert protocol["fresh_output_root"].endswith("development2")
    assert protocol["retry_disclosure"]["workloads_changed"] is False
    assert protocol["retry_disclosure"]["seeds_changed"] is False
    assert protocol["retry_disclosure"]["guard_changed"] is False
    assert protocol["retry_disclosure"]["thresholds_changed"] is False
    assert protocol["retry_disclosure"][
        "development1_artifacts_reused"
    ] is False


def test_fresh2_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert freezer.OUTPUT_PATH.read_text(
        encoding="utf-8"
    ) == freezer.canonical_text(rebuilt)
