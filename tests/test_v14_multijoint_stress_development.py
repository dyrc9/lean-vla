from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v14_multijoint_stress_development as freezer
from scripts import run_v14_multijoint_stress_development as runner


def test_environment_selection_is_deterministic_and_excludes_pilot() -> None:
    workloads = load_json_object(freezer.V14_PROTOCOL_PATH)["workloads"]

    first = freezer._select_environments(workloads)
    second = freezer._select_environments(workloads)

    assert first == second
    assert len(first) == 12
    assert len({row["environment_id"] for row in first}) == 12
    assert Counter(row["suite"] for row in first) == {
        suite: 4 for suite in freezer.SUITES
    }
    assert not any(
        row["suite"]
        == runner.pilot.PILOT_IDENTITY["benchmark_name"]
        and row["task_id"]
        == runner.pilot.PILOT_IDENTITY["task_id"]
        and row["init_state_id"]
        == runner.pilot.PILOT_IDENTITY["init_state_id"]
        for row in first
    )


def _baseline_report(
    *,
    screened: bool,
    crossing: int = 0,
    intervention: int = 0,
    deadlock: int = 0,
) -> dict[str, Any]:
    latencies = [0.01, 0.03] if screened else []
    return {
        "trigger_count": int(intervention > 0 or deadlock > 0),
        "intervention_count": intervention,
        "deadlock_count": deadlock,
        "reactive_stop_count": 0,
        "below_floor_count": crossing,
        "crossing_count": crossing,
        "executed_step_count": 5 - deadlock,
        "policy_decision_count": 5,
        "shadow_env_step_count": 2 if screened else 0,
        "observed_state_count": 5 - deadlock,
        "observed_side_value_count": 14 * (5 - deadlock),
        "restore_failure_count": 0,
        "exact_action_mismatch_count": 0,
        "minimum_margin_rad": -0.01 if crossing else 0.2,
        "maximum_abs_constraint_force": 12.0 if screened else 3.0,
        "screen_latency_seconds_values": latencies,
    }


def test_analysis_derives_rates_latency_and_integrity_gates() -> None:
    baselines = {
        "no_guard": _baseline_report(screened=False, crossing=1),
        "reactive_stop": _baseline_report(screened=False),
        "shadow_only": _baseline_report(screened=True, crossing=1),
        "predictive_brake": _baseline_report(
            screened=True,
            intervention=1,
            deadlock=1,
        ),
    }
    rows = [
        {
            "environment_id": "env0",
            "joint_index": 3,
            "side": "upper",
            "dose": {"dose": "high"},
            "baselines": baselines,
        }
    ]
    protocol = {
        "gates": {
            "expected_environment_count": 1,
            "expected_stress_lanes_per_environment": 1,
            "expected_stress_lane_count": 1,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
        }
    }

    metrics, gates = runner._analyze(
        protocol,
        rows,
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.0,
    )

    assert all(gates.values())
    assert metrics["no_guard_crossing_side_rate"] == 1 / 70
    assert metrics["predictive_brake_intervention_lane_rate"] == 1.0
    assert metrics["predictive_brake_deadlock_lane_rate"] == 1.0
    assert metrics["predictive_brake_executed_step_availability"] == 0.8
    assert metrics["predictive_brake_screen_latency_sample_count"] == 2
    assert metrics["predictive_brake_screen_latency_seconds_mean"] == 0.02
    assert metrics[
        "predictive_brake_screen_latency_seconds_p95"
    ] == pytest.approx(0.029)
    assert metrics["predictive_brake_maximum_abs_constraint_force"] == 12.0
    assert metrics["by_dose"]["high"]["no_guard_crossing_count"] == 1


def test_analysis_rejects_retained_outcome_fields() -> None:
    baselines = {
        baseline: _baseline_report(
            screened=baseline in {"shadow_only", "predictive_brake"}
        )
        for baseline in runner.pilot.BASELINES
    }
    baselines["no_guard"]["reward"] = 1.0
    rows = [
        {
            "environment_id": "env0",
            "joint_index": 0,
            "side": "lower",
            "dose": {"dose": "low"},
            "baselines": baselines,
        }
    ]
    protocol = {
        "gates": {
            "expected_environment_count": 1,
            "expected_stress_lanes_per_environment": 1,
            "expected_stress_lane_count": 1,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
        }
    }

    _, gates = runner._analyze(
        protocol,
        rows,
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.0,
    )

    assert gates["zero_policy_or_outcome_fields"] is False


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return

    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
