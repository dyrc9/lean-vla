from __future__ import annotations

import json

import pytest

from scripts import freeze_l1_task_conditioned_v4_development as freeze
from scripts import freeze_l1_task_conditioned_v4_heldout as heldout


def _registered(rows: list[dict]) -> dict:
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


def _v3_analysis(message: str) -> dict:
    rows = [
        {
            "terminal_exception": False,
            "terminal_exception_type": None,
            "terminal_exception_message": None,
        }
        for _ in range(240)
    ]
    rows[23] = {
        "terminal_exception": True,
        "terminal_exception_type": "TaskConditionedL1Error",
        "terminal_exception_message": message,
    }
    return _registered(rows)


def test_v4_development_freeze_uses_only_v3_no_allow_closure_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(
            _v3_analysis(
                'no qualified bounded-retreat ActionBlock: {"reject":55}'
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(freeze, "PARENT_ANALYSIS", path)
    monkeypatch.setattr(freeze, "REPO_ROOT", tmp_path)
    result = freeze._v3_diagnostic()
    assert result["complete_episode_count"] == 240
    assert result["terminal_no_allow_closure_failure_count"] == 1
    assert result["task_success_or_risk_result_used"] is False
    assert result["registered_four_channel_analysis_verified"] is True


def test_v4_development_freeze_rejects_failure_outside_scope(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(_v3_analysis("qualified L1 shadow restore identity failed")),
        encoding="utf-8",
    )
    monkeypatch.setattr(freeze, "PARENT_ANALYSIS", path)
    with pytest.raises(freeze.FreezeV4Error, match="outside the v4 repair scope"):
        freeze._v3_diagnostic()


def _heldout_fixture(
    tmp_path, monkeypatch: pytest.MonkeyPatch, *, abort: bool = False
):
    episode_path = tmp_path / "episode.json"
    audit = {
        "schema": "proofalign.task-conditioned-l1.v4.candidate-decision",
        "source_policy_chunk_base_array_sha256": "a" * 64,
        "recovery_library_digest": heldout.recovery_library_digest(),
        "no_dispatch_protocol_digest": heldout.no_dispatch_protocol_digest(),
        "selected_kind": (
            "qualified_no_dispatch_abort" if abort else "nominal"
        ),
        "nominal_command_changed": abort,
        "qualified_no_dispatch_abort": abort,
        "dispatch_intent": "none" if abort else "exact_action_block",
        "selected_action_block_sha256": None if abort else "b" * 64,
        "sentinel_is_authorizable": False,
        "selection_reason": (
            "no_exact_shadow_allow_qualified_no_dispatch"
            if abort
            else "transition_aligned_exact_shadow_allow"
        ),
    }
    frame = {
        "online_progress_projection_v3": audit,
        "semantic_decision": {"accepted": not abort},
    }
    episode_path.write_text(
        json.dumps(
            {
                "decision": (
                    "l1_qualified_no_dispatch_abort" if abort else "max_steps"
                ),
                "metadata": {
                    "l1_qualified_no_dispatch_abort_count": 1 if abort else 0
                },
                "observation_frame_audits": [frame],
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
            }
        )
    analysis_path = tmp_path / "v4-analysis.json"
    analysis_path.write_text(json.dumps(_registered(rows)), encoding="utf-8")
    monkeypatch.setattr(heldout, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(heldout, "V4_DEV_ANALYSIS", analysis_path)
    return analysis_path, episode_path, rows, frame, audit


def test_v4_heldout_qualification_is_outcome_blind_and_no_dispatch_bound(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _heldout_fixture(tmp_path, monkeypatch, abort=True)
    result = heldout._qualification()
    assert result["episode_count"] == 240
    assert result["terminal_implementation_exception_count"] == 0
    assert result["l1_episode_count"] == 120
    assert result["qualified_restore_complete_episode_count"] == 120
    assert result["qualified_no_dispatch_abort_dispatch_count"] == 0
    assert result["outcome_gate_applied"] is False
    assert result["task_success_or_risk_result_used_for_authorization"] is False


def test_v4_heldout_requires_no_dispatch_path_coverage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _heldout_fixture(tmp_path, monkeypatch, abort=False)
    with pytest.raises(
        heldout.HeldoutV4FreezeError, match="did not exercise"
    ):
        heldout._qualification()


def test_v4_heldout_rejects_abort_with_a_dispatch_transaction(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _analysis, episode_path, _rows, frame, _audit = _heldout_fixture(
        tmp_path, monkeypatch, abort=True
    )
    frame["semantic_transaction"] = {"dispatch_status": "open"}
    episode_path.write_text(
        json.dumps(
            {
                "decision": "l1_qualified_no_dispatch_abort",
                "metadata": {"l1_qualified_no_dispatch_abort_count": 1},
                "observation_frame_audits": [frame],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        heldout.HeldoutV4FreezeError, match="not proven no-dispatch"
    ):
        heldout._qualification()
