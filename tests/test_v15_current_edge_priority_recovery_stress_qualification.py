from __future__ import annotations

from collections import Counter
from typing import Any

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_current_edge_priority_recovery_stress_qualification as freezer,
)
from scripts import (
    run_v15_current_edge_priority_recovery_stress_qualification as runner,
)


def _report(
    *,
    screened: bool,
    deadlock: int = 0,
    crossing: int = 0,
    recovery: bool = False,
    force: float = 100.0,
    latency: float = 0.02,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "trigger_count": int(deadlock > 0 or recovery),
        "intervention_count": int(recovery),
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
        "minimum_margin_rad": -0.01 if crossing else 0.1501,
        "maximum_abs_constraint_force": force,
        "screen_latency_seconds_values": (
            [latency, latency] if screened else []
        ),
        "actual_joint_side_margins": [],
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


def _contacts() -> list[dict[str, Any]]:
    return [
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


def _protocol() -> dict[str, Any]:
    return {
        "gates": {
            "expected_environment_count": 1,
            "expected_stress_lanes_per_environment": 2,
            "expected_stress_lane_count": 2,
            "expected_baseline_lane_count": 8,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "selected_floor_violation_count_max": 0,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "control_period_seconds": 0.05,
            "thresholds_rad": [0.0, 0.15, 0.16, 0.22, 0.30],
            "latency_budget_seconds": 0.10,
            "stress_activation_no_guard_crossing_count_min": 1,
            "v14_predictive_deadlock_lane_count_min": 1,
            "v15_2_crossing_count_max": 0,
            "v15_2_below_floor_count_max": 0,
            "v15_2_residual_deadlock_lane_count_max": 0,
            "v15_2_prevention_identity_required": True,
            "v15_2_selected_floor_violation_count_max": 0,
            "v15_2_minus_v14_availability_min": 0.0,
            "maximum_prediction_execution_error_rad_max": 0.001,
            "v15_2_maximum_abs_constraint_force_max": 10000.0,
            "v15_2_to_v14_maximum_force_ratio_max": 1.25,
            "v15_2_screen_latency_p95_seconds_max": 0.10,
            "v15_2_screen_latency_seconds_max": 0.20,
            "v15_2_100ms_deadline_miss_rate_max": 0.025,
        }
    }


def _rows(*, latency: float = 0.02) -> list[dict[str, Any]]:
    def lane(dose: str) -> dict[str, Any]:
        return {
            "environment_id": "env0",
            "joint_index": 3,
            "side": "upper",
            "dose": {"dose": dose},
            "baselines": {
                "no_guard": _report(
                    screened=False,
                    crossing=1,
                    force=10.0,
                ),
                "shadow_only": _report(
                    screened=True,
                    crossing=1,
                    force=10.0,
                ),
                "v14_predictive_brake": _report(
                    screened=True,
                    deadlock=1,
                    force=100.0,
                ),
                "v15_2_recovery": _report(
                    screened=True,
                    recovery=True,
                    force=110.0,
                    latency=latency,
                ),
            },
        }

    return [lane("medium"), lane("high")]


def test_selection_is_deterministic_and_excludes_all_prior_pairs() -> None:
    clean = load_json_object(freezer.V14_CLEAN_PROTOCOL_PATH)
    v14_qualification = load_json_object(
        freezer.V14_STRESS_QUALIFICATION_PROTOCOL_PATH
    )
    v15_development = load_json_object(
        freezer.V15_2_DEVELOPMENT_PROTOCOL_PATH
    )
    calibration = load_json_object(freezer.CALIBRATION_PROTOCOL_PATH)
    prior = freezer._pairs(clean["workloads"])
    prior.update(freezer._pairs(v14_qualification["environments"]))
    prior.update(freezer._pairs(v15_development["schedule"]))
    prior.update(freezer._pairs(calibration["environments"]))

    first = freezer._select_environments(clean["workloads"], prior)
    second = freezer._select_environments(clean["workloads"], prior)

    assert first == second
    assert len(first) == 18
    assert Counter(row["suite"] for row in first) == {
        suite: 6 for suite in freezer.SUITES
    }
    assert not (freezer._pairs(first) & prior)
    assert {row["environment_seed"] for row in first} == {3509}


def test_analysis_registers_recovery_and_overhead_gates() -> None:
    metrics, gates = runner._analyze(
        _protocol(),
        _rows(),
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.2,
        contact_reports=_contacts(),
    )

    assert all(gates.values())
    assert metrics["recovery"]["paired_deadlock_lane_identity"] is True
    assert metrics["force_comparison"]["v15_2_to_v14_ratio"] == 1.1
    assert metrics["raw_all_side_numeric_identity_diagnostic"][
        "registered_as_gate"
    ] is False


def test_analysis_rejects_registered_latency_failure() -> None:
    _, gates = runner._analyze(
        _protocol(),
        _rows(latency=0.15),
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.0,
        contact_reports=_contacts(),
    )

    assert gates["v15_2_latency_p95"] is False
    assert gates["v15_2_100ms_deadline_miss_rate"] is False


def test_frozen_qualification_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
