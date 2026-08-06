from __future__ import annotations

from copy import deepcopy

import numpy as np

from scripts import freeze_v15_recovery_component_ablation_qualification as freezer
from scripts import run_v15_recovery_component_ablation_qualification as runner


def _margin_steps(value: float = 0.2, *, count: int = 2) -> list[list[dict]]:
    matrix = np.full((7, 2), value, dtype=np.float64)
    rows = runner.base.calibration.v14.pilot._margin_rows(matrix)
    return [deepcopy(rows) for _ in range(count)]


def _identity_report(value: float = 0.2) -> dict:
    report = {
        field: 0
        for field in (
            "executed_step_count",
            "policy_decision_count",
            "trigger_count",
            "intervention_count",
            "deadlock_count",
            "reactive_stop_count",
            "shadow_env_step_count",
            "restore_failure_count",
            "exact_action_mismatch_count",
            "below_floor_count",
            "crossing_count",
            "observed_state_count",
            "observed_side_value_count",
            "current_edge_selected_count",
            "floor_edge_selected_count",
            "selected_recovery_count",
            "selected_floor_violation_count",
        )
    }
    report["actual_joint_side_margins"] = _margin_steps(value)
    return report


def test_component_ablation_matrix_is_incremental_and_same_lane() -> None:
    assert runner.BASELINES == (
        "no_guard",
        "reactive_stop",
        "shadow_only",
        "v14_predictive_brake",
        "v15_floor_edge_recovery",
        "v15_1_current_edge_recovery",
        "v15_2_current_edge_priority_recovery",
        "v15_3_force_attributed_recovery",
    )
    assert runner.RECOVERY_BASELINES == runner.BASELINES[-4:]


def test_selected_population_excludes_every_predecessor_pair() -> None:
    workloads, prior = freezer._predecessors()

    selected = freezer._select_environments(workloads, prior)

    assert len(selected) == 18
    assert not (freezer._pairs(selected) & prior)
    assert all(row["environment_seed"] == 7509 for row in selected)
    assert all(
        len({row["task_id"] for row in selected if row["suite"] == suite}) == 6
        for suite in freezer.SUITES
    )


def test_freeze_sources_bind_runner_and_test() -> None:
    assert "scripts/run_v15_recovery_component_ablation_qualification.py" in (
        freezer.SOURCE_PATHS
    )
    assert "tests/test_v15_recovery_component_ablation_qualification.py" in (
        freezer.SOURCE_PATHS
    )


def test_generic_recovery_report_preserves_component_audit(monkeypatch) -> None:
    pilot = runner.base.calibration.v14.pilot
    monkeypatch.setattr(pilot, "HORIZON_STEPS", 2)
    monkeypatch.setattr(pilot, "HOLD_ACTION", np.zeros(7))
    monkeypatch.setattr(
        pilot,
        "full_clean_margin_matrix",
        lambda value: np.asarray(value, dtype=np.float64),
    )
    monkeypatch.setattr(pilot, "_margin_rows", lambda value: value.tolist())
    monkeypatch.setattr(
        pilot,
        "_exposure",
        lambda values: {
            "below_floor_count": 0,
            "crossing_count": 0,
            "observed_state_count": len(values),
            "observed_side_value_count": len(values) * 14,
            "minimum_margin_rad": 0.16,
        },
    )

    class FakeWrapper:
        def __init__(self, env, *, wait_steps, enabled, config) -> None:
            assert env == "env"
            assert wait_steps == 0
            assert enabled is True
            assert config is None
            self.observations = []

        def step(self, action) -> None:
            index = len(self.observations)
            self.observations.append(
                {
                    "schema": "expected",
                    "deadlock": False,
                    "deadlock_reason": None,
                    "triggered": True,
                    "intervened": True,
                    "shadow_env_step_count": 3,
                    "shadow_restore_identity": True,
                    "exact_action_identity": True,
                    "screen_latency_seconds": 0.01 + index * 0.001,
                    "maximum_abs_guarded_constraint_force": 10.0 + index,
                    "actual_joint_side_margins": np.full((7, 2), 0.16),
                    "actual_minimum_margin_rad": 0.16,
                    "prediction_execution_margin_error_rad": 1e-5,
                    "v14_baseline_would_deadlock": True,
                    "floor_guard_recovery_attempted": True,
                    "floor_guard_recovery_selected": index == 0,
                    "floor_guard_recovery_prevented_deadlock": index == 0,
                    "current_edge_recovery_attempted": index == 1,
                    "current_edge_recovery_selected": index == 1,
                    "floor_or_current_edge_recovery_prevented_deadlock": (index == 1),
                }
            )

    report = runner._recovery_result(
        "env", wrapper_class=FakeWrapper, expected_schema="expected"
    )

    assert report["component_schema_mismatch_count"] == 0
    assert report["selected_recovery_count"] == 2
    assert report["recovery_prevented_deadlock_count"] == 2
    assert report["floor_edge_selected_count"] == 1
    assert report["current_edge_selected_count"] == 1
    assert report["selected_floor_violation_count"] == 0
    assert report["maximum_prediction_execution_error_rad"] == 1e-5


def test_force_attribution_execution_identity_is_paired_by_lane() -> None:
    prior = _identity_report()
    attributed = deepcopy(prior)
    rows = [
        {
            "baselines": {
                runner.PRIORITY_BASELINE: prior,
                runner.V15_3_BASELINE: attributed,
            }
        }
    ]

    identity = runner._v15_2_v15_3_identity(rows)

    assert identity == {
        "lane_count": 1,
        "scalar_mismatch_count": 0,
        "trace_shape_mismatch_lane_count": 0,
        "maximum_actual_margin_trace_error_rad": 0.0,
        "force_attribution_changes_mechanism": False,
    }

    attributed["selected_recovery_count"] = 1
    attributed["actual_joint_side_margins"] = _margin_steps(0.19)
    changed = runner._v15_2_v15_3_identity(rows)
    assert changed["scalar_mismatch_count"] == 1
    assert np.isclose(changed["maximum_actual_margin_trace_error_rad"], 0.01)


def test_component_metrics_keep_deadlocks_and_recovery_counts_visible() -> None:
    report = {
        "component_schema_mismatch_count": 0,
        "v14_baseline_would_deadlock_count": 2,
        "recovery_prevented_deadlock_count": 2,
        "current_edge_attempted_count": 2,
        "current_edge_selected_count": 2,
        "floor_edge_attempted_count": 2,
        "floor_edge_selected_count": 0,
        "selected_recovery_count": 2,
        "selected_floor_violation_count": 0,
        "deadlock_count": 0,
        "crossing_count": 0,
        "below_floor_count": 0,
        "maximum_prediction_execution_error_rad": 2e-5,
    }
    rows = [{"baselines": {runner.PRIORITY_BASELINE: report}}]

    metrics = runner._component_metrics(rows, runner.PRIORITY_BASELINE)

    assert metrics["lane_count"] == 1
    assert metrics["deadlock_lane_count"] == 0
    assert metrics["current_edge_selected_count"] == 2
    assert metrics["recovery_prevented_deadlock_count"] == 2
    assert metrics["maximum_prediction_execution_error_rad"] == 2e-5
