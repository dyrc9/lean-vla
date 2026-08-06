from __future__ import annotations

from scripts import (
    run_v15_bounded_state_triggered_model_mismatch_qualification as qualification,
)


def test_qualification_declares_v15_11_identity() -> None:
    assert "v15.11" in qualification.PROTOCOL_SCHEMA
    assert "v15_11" in qualification.AUTHORIZED_STATUS
    assert "v15_11" in qualification.V15_BASELINE


def test_name_replacement_is_reversible() -> None:
    value = {"v15_8_gate": qualification.predecessor.V15_BASELINE}
    replaced = qualification._replace_names(value)
    assert "v15_11_gate" in replaced
    assert replaced["v15_11_gate"] == qualification.V15_BASELINE
    assert qualification._replace_names(replaced, reverse=True) == value


def test_bounded_gate_contract() -> None:
    protocol = {
        "gates": {
            "expected_v15_11_policy_step_count": 10,
            "expected_v15_11_calibration_evaluation_count": 12,
            "minimum_v15_11_dynamic_motion_generator_step_count": 1,
            "minimum_extended_recovery_evaluated_count": 0,
            "minimum_extended_recovery_selected_count": 0,
            "minimum_force_rejected_base_eligible_candidate_count": 0,
        }
    }
    metrics = {
        "audit_count": 10,
        "inactive_count": 0,
        "state_trigger_margin_mismatch_count": 0,
        "unguarded_shadow_rollout_count": 0,
        "rollout_budget_violation_count": 0,
        "guarded_candidate_rollout_max": 2,
        "calibration_evaluation_count": 12,
        "calibration_bind_count": 12,
        "dynamic_motion_generator_step_count": 1,
        "extended_recovery_evaluated_count": 0,
        "extended_recovery_selected_count": 0,
        "force_rejected_candidate_count": 0,
    }
    assert all(qualification._bounded_gates(protocol, metrics).values())
