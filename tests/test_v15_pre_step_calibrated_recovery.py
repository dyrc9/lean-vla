from __future__ import annotations

import pytest

from scripts import (
    run_l2_predictive_virtual_brake_v15_pre_step_calibrated_recovery as recovery,
)


def _calibration() -> dict:
    return {
        "interface_available": True,
        "active": True,
        "candidate_count": 7,
        "selected_candidate_id": "arm_friction_1_3x",
        "selected_residual": 0.25,
        "minimum_residual_candidate_count": 1,
        "bind_identity": True,
        "latency_seconds": 0.31,
    }


def test_setup_calibration_does_not_change_action_screen_latency() -> None:
    audit = {"screen_latency_seconds": 0.08}

    recovery._attach_setup_calibration(audit, _calibration())

    assert audit["screen_latency_seconds"] == 0.08
    assert audit["pre_step_shadow_calibration_latency_seconds"] == 0.31
    assert audit["pre_step_shadow_calibration_outside_action_critical_path"] is True
    assert audit["pre_step_shadow_selected_candidate_id"] == "arm_friction_1_3x"


def test_setup_calibration_requires_full_model_bank() -> None:
    calibration = _calibration()
    calibration["candidate_count"] = 6

    with pytest.raises(
        recovery.PreStepCalibratedRecoveryError,
        match="unavailable or incomplete",
    ):
        recovery._attach_setup_calibration(
            {"screen_latency_seconds": 0.08}, calibration
        )
