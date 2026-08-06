from __future__ import annotations

from typing import Any

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_current_edge_priority_recovery_stress_calibration as freezer,
)
from scripts import (
    run_v15_current_edge_priority_recovery_stress_calibration as runner,
)


def _report(
    *,
    screened: bool,
    deadlock: int = 0,
    recovery: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "trigger_count": int(deadlock > 0 or recovery),
        "intervention_count": int(recovery),
        "deadlock_count": deadlock,
        "reactive_stop_count": 0,
        "below_floor_count": 0,
        "crossing_count": 0,
        "executed_step_count": 5 - deadlock,
        "policy_decision_count": 5,
        "shadow_env_step_count": 2 if screened else 0,
        "observed_state_count": 5 - deadlock,
        "observed_side_value_count": 14 * (5 - deadlock),
        "restore_failure_count": 0,
        "exact_action_mismatch_count": 0,
        "minimum_margin_rad": 0.1501,
        "maximum_abs_constraint_force": 12.0 if screened else 0.0,
        "screen_latency_seconds_values": (
            [0.01, 0.03] if screened else []
        ),
    }
    if recovery:
        report.update(
            {
                "v15_2_schema_mismatch_count": 0,
                "v15_2_priority_mismatch_count": 0,
                "v14_baseline_would_deadlock_count": 1,
                "v14_baseline_would_deadlock_lane": True,
                "recovery_prevented_deadlock_count": 1,
                "recovery_prevented_deadlock_lane": True,
                "current_edge_attempted_count": 1,
                "current_edge_eligible_count": 1,
                "current_edge_selected_count": 1,
                "floor_edge_attempted_count": 1,
                "floor_edge_eligible_count": 1,
                "floor_edge_selected_count": 0,
                "selected_recovery_count": 1,
                "selected_floor_violation_count": 0,
                "selected_actual_minimum_margin_rad": 0.1501,
                "selected_guard_minimum_margin_rad": 0.15009,
                "maximum_prediction_execution_error_rad": 0.00001,
            }
        )
    return report


def test_calibration_environments_retain_pairs_and_change_seed() -> None:
    source = load_json_object(freezer.V14_STRESS_PROTOCOL_PATH)

    rows = freezer._calibration_environments(source)

    assert len(rows) == 12
    assert {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in rows
    } == {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in source["environments"]
    }
    assert {row["environment_seed"] for row in rows} == {2509}


def test_analysis_separates_integrity_from_descriptive_recovery() -> None:
    rows = [
        {
            "environment_id": "env0",
            "joint_index": 3,
            "side": "upper",
            "dose": {"dose": "high"},
            "baselines": {
                "no_guard": _report(screened=False),
                "shadow_only": _report(screened=True),
                "v14_predictive_brake": _report(
                    screened=True,
                    deadlock=1,
                ),
                "v15_2_recovery": _report(
                    screened=True,
                    recovery=True,
                ),
            },
        }
    ]
    contacts = [
        {
            "environment_id": "env0",
            "phases": {
                phase: {
                    "contact_observation_count": 1,
                    "contact_saturation_count": 0,
                    "maximum_ncon": 2,
                    "minimum_nconmax": 5000,
                    "warning_count": 0,
                    "contact_capacity_warning_count": 0,
                }
                for phase in ("prebinding", "active")
            },
        }
    ]
    protocol = {
        "gates": {
            "expected_environment_count": 1,
            "expected_stress_lanes_per_environment": 1,
            "expected_stress_lane_count": 1,
            "expected_baseline_lane_count": 4,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "selected_floor_violation_count_max": 0,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "control_period_seconds": 0.05,
        }
    }

    metrics, gates = runner._analyze(
        protocol,
        rows,
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.0,
        contact_reports=contacts,
    )

    assert all(gates.values())
    assert metrics["recovery"]["paired_deadlock_lane_identity"] is True
    assert metrics["recovery"]["v15_2_residual_deadlock_lane_count"] == 0
    assert metrics["recovery"]["current_edge_selected_count"] == 1
    assert metrics["aggregate"][
        "v15_2_recovery_executed_step_availability"
    ] == 1.0
    assert metrics["latency_deadlines"]["v15_2_recovery"][
        "miss_rate"
    ] == 0.0


def test_frozen_calibration_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
