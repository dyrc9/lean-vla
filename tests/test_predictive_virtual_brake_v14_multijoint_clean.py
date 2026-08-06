from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_predictive_virtual_brake_v14_multijoint_clean as freezer
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as online
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as clean


def _margins(value: float = 0.5) -> list[dict[str, Any]]:
    return [
        {
            "joint_index": joint_index,
            "lower_margin_rad": value + 0.01 * joint_index,
            "upper_margin_rad": value + 0.02 * joint_index,
        }
        for joint_index in range(7)
    ]


def _audit(*, enabled: bool) -> dict[str, Any]:
    actual = _margins()
    return {
        "schema": online.BRAKE_AUDIT_SCHEMA,
        "enabled": enabled,
        "screen_performed": enabled,
        "multi_joint_audit": True,
        "joint_side_scope_count": 14,
        "triggered": False,
        "intervened": False,
        "deadlock": False,
        "actual_joint_side_margins": actual,
        "actual_worst_margin_rad": 0.5,
        "risk_sides": [],
        "current_joint_side_margins": (
            _margins() if enabled else None
        ),
        "unguarded_predicted_joint_side_margins": (
            _margins() if enabled else None
        ),
        "selected_predicted_joint_side_margins": None,
        "candidates": [],
    }


def _metadata(*, enabled: bool) -> dict[str, Any]:
    return {
        "runner_variant": online.RUNNER_VARIANT,
        "predictive_virtual_brake_target_joint_index": None,
        "predictive_virtual_brake_target_joint_side": None,
        "predictive_virtual_brake_target_scope": (
            "all_7_arm_joints_both_sides" if enabled else None
        ),
        "predictive_virtual_brake_joint_indices": (
            list(range(7)) if enabled else None
        ),
        "predictive_virtual_brake_joint_sides": (
            ["lower", "upper"] if enabled else None
        ),
        "predictive_virtual_brake_joint_side_scope_count": (
            14 if enabled else None
        ),
        "predictive_virtual_brake_multijoint": enabled,
        "predictive_virtual_brake_simultaneous_guarding": enabled,
        "predictive_virtual_brake_action_substitution": False,
    }


def test_v14_metrics_require_fourteen_side_coverage_and_calibration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    episodes = []
    schedule = []
    for index, (arm, enabled) in enumerate(
        (("vla_only", False), ("execution_only", True))
    ):
        episode_id = f"episode-{index}"
        relative = Path(f"{episode_id}.json")
        (tmp_path / relative).write_text(
            json.dumps(
                {
                    "metadata": _metadata(enabled=enabled),
                    "trace": [
                        {
                            "phase": "policy",
                            "predictive_virtual_brake": _audit(
                                enabled=enabled
                            ),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        schedule.append(
            {
                "episode_id": episode_id,
                "arm": arm,
            }
        )
        episodes.append(
            {
                "episode_id": episode_id,
                "path": relative.as_posix(),
            }
        )
    monkeypatch.setattr(clean, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        clean,
        "_BASE_V13_METRICS",
        lambda _protocol, _evidence: (
            {
                "policy_step_count": 2,
                "l2_policy_step_count": 1,
            },
            {"base_integrity": True},
        ),
    )

    metrics, gates = clean._v14_metrics(
        {
            "schedule": schedule,
            "v14_gates": {
                "maximum_prediction_execution_side_error_rad": 1e-9,
            },
        },
        {"episodes": episodes},
    )

    assert all(gates.values())
    assert metrics["v14_policy_audit_count"] == 2
    assert metrics["actual_side_value_count"] == 28
    assert metrics["unguarded_predicted_side_value_count"] == 14
    assert (
        metrics["v14_prediction_execution_compared_side_count"]
        == 14
    )
    assert (
        metrics["v14_maximum_prediction_execution_side_error_rad"]
        == 0.0
    )


def test_v14_margin_rows_fail_closed_on_missing_joint() -> None:
    with pytest.raises(clean.PredictiveVirtualBrakeV14CleanError):
        clean._margin_matrix(_margins()[:-1], field="test")


def test_v14_development_completion_excludes_outcome_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome_names = {
        "v9_execution_only_task_success_noninferiority": False,
        "v9_dual_task_success_noninferiority": True,
        "v9_execution_only_official_unsafe_nonincrease": True,
        "v9_dual_official_unsafe_nonincrease": True,
    }
    monkeypatch.setattr(
        clean,
        "_BASE_V13_ENRICH",
        lambda _protocol, evidence: {
            **evidence,
            "gate_results": {
                "episode_count": True,
                "v9_v14_metadata_matches": True,
                **outcome_names,
            },
        },
    )

    enriched = clean._enrich(
        {
            "complete_classification": "complete",
            "incomplete_classification": "nonpass",
        },
        {},
    )

    assert enriched["classification"] == "complete"
    assert enriched["pilot_complete"] is True
    assert enriched["development_data_complete"] is True
    assert enriched["descriptive_clean_utility_gate_passed"] is False
    assert enriched["attacked_stage_authorized"] is False
    assert enriched["confirmatory_claim_authorized"] is False


def test_v14_clean_patch_is_scoped_and_restored() -> None:
    original = (
        clean.predecessor.PROTOCOL_SCHEMA,
        clean.predecessor.EVIDENCE_SCHEMA,
        clean.predecessor.EXPECTED_RUNNER,
        clean.predecessor.AUTHORIZED_STATUS,
        clean.predecessor.DEFAULT_PROTOCOL,
        clean.predecessor.online,
        clean.predecessor._v13_metrics,
        clean.predecessor._enrich,
    )

    with clean._patched_predecessor():
        assert clean.predecessor.PROTOCOL_SCHEMA == clean.PROTOCOL_SCHEMA
        assert clean.predecessor.EVIDENCE_SCHEMA == clean.EVIDENCE_SCHEMA
        assert clean.predecessor.EXPECTED_RUNNER == online.RUNNER_VARIANT
        assert clean.predecessor.AUTHORIZED_STATUS == (
            clean.AUTHORIZED_STATUS
        )
        assert clean.predecessor.online is online
        assert clean.predecessor._v13_metrics is clean._v14_metrics
        assert clean.predecessor._enrich is clean._enrich

    assert (
        clean.predecessor.PROTOCOL_SCHEMA,
        clean.predecessor.EVIDENCE_SCHEMA,
        clean.predecessor.EXPECTED_RUNNER,
        clean.predecessor.AUTHORIZED_STATUS,
        clean.predecessor.DEFAULT_PROTOCOL,
        clean.predecessor.online,
        clean.predecessor._v13_metrics,
        clean.predecessor._enrich,
    ) == original


def test_v14_freezer_reuses_exact_v13_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = load_json_object(freezer.PARENT_PROTOCOL_PATH)
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
        "SOURCE_PATHS",
        ("source.py",),
    )
    monkeypatch.setattr(
        freezer,
        "file_sha256",
        lambda _path: "bound-sha",
    )

    protocol = freezer.build_protocol(source_commit="commit")

    assert protocol["schedule"] == parent["schedule"]
    assert protocol["workloads"] == parent["workloads"]
    assert protocol["stage"] == parent["stage"]
    assert protocol["design"]["joint_side_scope_count"] == 14
    assert protocol["selection"]["development_only"] is True
    assert protocol["outcomes_observed_for_selection"] is True
    assert protocol["execution_authorization"]["attacked_rollout"] is False
    assert protocol["execution_authorization"]["confirmatory_claim"] is False


def test_v14_frozen_protocol_is_current_when_present() -> None:
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
