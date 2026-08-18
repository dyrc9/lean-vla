from __future__ import annotations

import json

import pytest

from scripts import freeze_l1_task_conditioned_v3_development as freeze
from scripts import freeze_l1_task_conditioned_v3_heldout as heldout


def _analysis(message: str) -> dict:
    rows = [
        {
            "terminal_exception": False,
            "terminal_exception_type": None,
            "terminal_exception_message": None,
        }
        for _ in range(240)
    ]
    rows[17] = {
        "terminal_exception": True,
        "terminal_exception_type": "TaskConditionedL1Error",
        "terminal_exception_message": message,
    }
    return {
        "schema": "proofalign.l1-task-conditioned-analysis.v2",
        "population": "development",
        "risk_transition_definition": {
            "channels": [
                "libero_cost_or_collision",
                "robot_contact_count_delta",
                "joint_limit_steps_delta",
                "excessive_force_steps_delta",
            ],
            "same_as_45_35_percent_baseline": True,
        },
        "registered_risk_analysis": {
            "historical_baseline": {
                "unit_count": 120,
                "eligible": 86,
                "transitions": 39,
                "four_channel_rows_verified": 86,
            }
        },
        "episode_rows": rows,
    }


def test_v3_freeze_accepts_only_complete_v2_recovery_coverage_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(
            _analysis('no qualified fresh recovery ActionBlock: {"reject":3}')
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(freeze, "PARENT_ANALYSIS", path)
    monkeypatch.setattr(freeze, "REPO_ROOT", tmp_path)
    diagnostic = freeze._v2_diagnostic()
    assert diagnostic["complete_episode_count"] == 240
    assert diagnostic["terminal_recovery_coverage_failure_count"] == 1
    assert diagnostic["task_success_or_risk_result_used"] is False
    assert diagnostic["registered_four_channel_analysis_verified"] is True


@pytest.mark.parametrize(
    "message",
    [
        "qualified L1 shadow restore identity failed: {}",
        "source policy returned invalid ActionBlock",
    ],
)
def test_v3_freeze_rejects_failures_outside_repair_scope(
    tmp_path, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(_analysis(message)), encoding="utf-8")
    monkeypatch.setattr(freeze, "PARENT_ANALYSIS", path)
    with pytest.raises(
        freeze.FreezeV3Error,
        match="outside the v3 repair scope",
    ):
        freeze._v2_diagnostic()


def test_v3_freeze_does_not_authorize_from_incomplete_analysis(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "analysis.json"
    value = _analysis('no qualified fresh recovery ActionBlock: {"reject":3}')
    value["episode_rows"].pop()
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(freeze, "PARENT_ANALYSIS", path)
    with pytest.raises(freeze.FreezeV3Error, match="incomplete"):
        freeze._v2_diagnostic()


def _heldout_fixture(tmp_path, monkeypatch: pytest.MonkeyPatch):
    episode_path = tmp_path / "episode.json"
    audit = {
        "schema": "proofalign.task-conditioned-l1.v3.candidate-decision",
        "source_policy_chunk_base_array_sha256": "a" * 64,
        "recovery_library_digest": heldout.recovery_library_digest(),
        "selected_kind": "nominal",
        "nominal_command_changed": False,
        "selection_reason": "transition_aligned_exact_shadow_allow",
    }
    episode_path.write_text(
        json.dumps(
            {
                "observation_frame_audits": [
                    {"online_progress_projection_v3": audit}
                ]
            }
        ),
        encoding="utf-8",
    )
    rows = []
    for index in range(240):
        l1 = index >= 120
        rows.append(
            {
                "arm": "semantic_only" if l1 else "vla_only",
                "terminal_exception": False,
                "l1_audit_count": 1 if l1 else 0,
                "l1_shadow_restore_identity_complete": l1,
                "artifact_path": "episode.json",
                "task_success": bool(index % 2),
            }
        )
    analysis_path = tmp_path / "v3-analysis.json"
    analysis_path.write_text(json.dumps(_heldout_analysis(rows)), encoding="utf-8")
    monkeypatch.setattr(heldout, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(heldout, "V3_DEV_ANALYSIS", analysis_path)
    return analysis_path, episode_path, rows, audit


def _heldout_analysis(rows: list[dict]) -> dict:
    return {
        "schema": "proofalign.l1-task-conditioned-analysis.v2",
        "population": "development",
        "risk_transition_definition": {
            "channels": [
                "libero_cost_or_collision",
                "robot_contact_count_delta",
                "joint_limit_steps_delta",
                "excessive_force_steps_delta",
            ],
            "same_as_45_35_percent_baseline": True,
        },
        "registered_risk_analysis": {
            "historical_baseline": {
                "unit_count": 120,
                "eligible": 86,
                "transitions": 39,
                "four_channel_rows_verified": 86,
            }
        },
        "episode_rows": rows,
    }


def test_v3_heldout_authorization_is_outcome_blind_and_identity_bound(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _heldout_fixture(tmp_path, monkeypatch)
    result = heldout._qualification()
    assert result["episode_count"] == 240
    assert result["l1_episode_count"] == 120
    assert result["qualified_restore_complete_episode_count"] == 120
    assert result["registered_four_channel_analysis_verified"] is True
    assert result["outcome_gate_applied"] is False
    assert result["task_success_or_risk_result_used_for_authorization"] is False


def test_v3_heldout_authorization_rejects_terminal_or_unbound_recovery(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path, episode_path, rows, audit = _heldout_fixture(
        tmp_path, monkeypatch
    )
    rows[120]["terminal_exception"] = True
    analysis_path.write_text(json.dumps(_heldout_analysis(rows)), encoding="utf-8")
    with pytest.raises(
        heldout.HeldoutV3FreezeError, match="terminal implementation"
    ):
        heldout._qualification()

    rows[120]["terminal_exception"] = False
    analysis_path.write_text(json.dumps(_heldout_analysis(rows)), encoding="utf-8")
    audit["recovery_library_digest"] = "b" * 64
    episode_path.write_text(
        json.dumps(
            {
                "observation_frame_audits": [
                    {"online_progress_projection_v3": audit}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        heldout.HeldoutV3FreezeError, match="library binding differs"
    ):
        heldout._qualification()
