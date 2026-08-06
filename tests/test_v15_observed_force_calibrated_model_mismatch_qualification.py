from __future__ import annotations

from scripts import (
    run_v15_observed_force_calibrated_model_mismatch_qualification as qualification,
)


def test_calibration_gates_require_full_coverage_and_noninterference() -> None:
    protocol = {
        "gates": {
            "expected_v15_8_policy_step_count": 12,
            "calibration_nonminimum_bind_count_max": 0,
            "calibration_selected_residual_exceeds_nominal_count_max": 0,
        }
    }
    metrics = {
        "evaluation_count": 12,
        "bind_count": 12,
        "nonminimum_bind_count": 0,
        "selected_residual_exceeds_nominal_count": 0,
        "actual_parameter_read_by_selector_count": 0,
        "task_outcome_read_count": 0,
    }

    assert all(qualification._calibration_gates(protocol, metrics).values())


def test_calibration_gate_rejects_nonminimum_binding() -> None:
    protocol = {
        "gates": {
            "expected_v15_8_policy_step_count": 1,
            "calibration_nonminimum_bind_count_max": 0,
            "calibration_selected_residual_exceeds_nominal_count_max": 0,
        }
    }
    metrics = {
        "evaluation_count": 1,
        "bind_count": 1,
        "nonminimum_bind_count": 1,
        "selected_residual_exceeds_nominal_count": 0,
        "actual_parameter_read_by_selector_count": 0,
        "task_outcome_read_count": 0,
    }

    gates = qualification._calibration_gates(protocol, metrics)
    assert gates["v15_8_calibration_minimum_residual_identity"] is False


def test_persisted_name_mapping_round_trips() -> None:
    payload = {
        "v15_7_incremental_adaptive_force_recovery": {
            "v15_7_metric": "v15_7 value"
        }
    }

    persisted = qualification._replace_names(payload)

    assert qualification._replace_names(persisted, reverse=True) == payload
