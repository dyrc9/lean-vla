from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ctda_v2_safelibero_state_coverage",
    ROOT / "scripts" / "ctda_v2_safelibero_state_coverage.py",
)
assert SPEC is not None and SPEC.loader is not None
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


def test_gpu_snapshot_parser_retains_physical_identity(monkeypatch) -> None:
    output = "5, GPU-state, NVIDIA RTX 6000 Ada Generation, 49140, 3, 0\n"
    monkeypatch.setattr(
        coverage,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )

    snapshot = coverage._gpu_snapshot(5)

    assert snapshot["uuid"] == "GPU-state"
    assert snapshot["memory_used_mib"] == 3


def test_exact_population_records_use_goal_reference_not_fixture_base() -> None:
    records, inventory = coverage._scenario_records(ROOT / "external" / "vlsa-aegis")

    assert len(records) == 32
    assert inventory["candidate_episode_count"] == 1600
    drawer = next(
        item
        for item in records
        if item["unit_id"] == "safelibero_goal:task3:levelI"
    )
    assert "wooden_cabinet_1_top_region_pos" in drawer["required_keys"]
    assert "wooden_cabinet_1_pos" not in drawer["required_keys"]
    assert drawer["reference_position_keys"] == ["wooden_cabinet_1_top_region_pos"]


def test_r0_negative_and_r1_complete_state_coverage_are_both_retained() -> None:
    r0 = json.loads(
        (ROOT / "experiments" / "ctda_v2_safelibero_state_coverage_summary.json").read_text()
    )
    r1 = json.loads(
        (ROOT / "experiments" / "ctda_v2_safelibero_state_coverage_summary_r1.json").read_text()
    )

    assert r0["status"] == "state_coverage_failed"
    assert r0["coverage"]["state_key_coverage_count"] == 1250
    assert r0["coverage"]["collision_source_coverage_count"] == 1600
    assert r0["coverage"]["env_step_count"] == 0
    assert r1["status"] == "state_coverage_ready_rollout_blocked"
    assert r1["coverage"]["unit_count"] == 1600
    assert r1["coverage"]["state_key_coverage_count"] == 1600
    assert r1["coverage"]["collision_source_coverage_count"] == 1600
    assert r1["coverage"]["env_step_count"] == 0
    assert r1["policy_inference_count"] == 0
    assert r1["formal_rollout_authorized"] is False

