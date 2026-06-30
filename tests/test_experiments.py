from __future__ import annotations

from pathlib import Path

from proofalign.baselines import BaselineMode
from proofalign.experiments import run_directory


ROOT = Path(__file__).resolve().parents[1]


def test_experiment_runner_writes_summary(tmp_path):
    summary = run_directory(ROOT / "examples" / "tasks", tmp_path, [BaselineMode.DUAL, BaselineMode.INTENT_ONLY])

    assert "dual" in summary
    assert "intent_only" in summary
    assert (tmp_path / "dual.jsonl").exists()
    assert (tmp_path / "summary.json").exists()
    assert summary["dual"]["episodes"] == 5
