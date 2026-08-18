from __future__ import annotations

import json

import pytest

from scripts import freeze_l1_task_conditioned_v3_development as freeze


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
        "population": "development",
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
