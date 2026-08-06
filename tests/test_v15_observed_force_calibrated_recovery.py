from __future__ import annotations

import pytest

from scripts import (
    run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery as recovery,
)


class _Calibrator:
    schema = recovery.CALIBRATION_INTERFACE

    def __init__(self, residuals: dict[str, float]) -> None:
        self.residuals = residuals
        self.bound = None

    def evaluate(self, model_bank):
        return [
            {
                "candidate_id": row["candidate_id"],
                "maximum_abs_force_residual": self.residuals[
                    row["candidate_id"]
                ],
            }
            for row in reversed(model_bank)
        ]

    def bind(self, candidate_id):
        self.bound = candidate_id
        return {
            "candidate_id": candidate_id,
            "bind_identity": True,
            "task_outcome_read": False,
            "actual_parameter_read_by_selector": False,
        }


class _Environment:
    pass


def test_calibration_selects_minimum_residual_in_registered_bank() -> None:
    residuals = {
        row["candidate_id"]: float(index + 1)
        for index, row in enumerate(recovery.MODEL_BANK)
    }
    residuals["arm_friction_1_3x"] = 0.0
    env = _Environment()
    env.proofalign_shadow_model_calibrator = _Calibrator(residuals)

    result = recovery._calibrate_shadow_model(env)

    assert result["active"] is True
    assert result["candidate_count"] == 7
    assert result["selected_candidate_id"] == "arm_friction_1_3x"
    assert result["selected_residual"] == 0.0
    assert env.proofalign_shadow_model_calibrator.bound == "arm_friction_1_3x"


def test_calibration_tie_uses_registered_order() -> None:
    residuals = {row["candidate_id"]: 0.0 for row in recovery.MODEL_BANK}
    env = _Environment()
    env.proofalign_shadow_model_calibrator = _Calibrator(residuals)

    result = recovery._calibrate_shadow_model(env)

    assert result["selected_candidate_id"] == "nominal"
    assert result["minimum_residual_candidate_count"] == len(recovery.MODEL_BANK)


def test_calibration_rejects_incomplete_model_bank_evaluation() -> None:
    env = _Environment()
    residuals = {row["candidate_id"]: 1.0 for row in recovery.MODEL_BANK}

    class _IncompleteCalibrator(_Calibrator):
        def evaluate(self, model_bank):
            return super().evaluate(model_bank)[:-1]

    env.proofalign_shadow_model_calibrator = _IncompleteCalibrator(residuals)

    with pytest.raises(
        recovery.ObservedForceCalibratedRecoveryError,
        match="model-bank coverage differs",
    ):
        recovery._calibrate_shadow_model(env)


def test_calibration_is_optional_for_same_model_runtime() -> None:
    result = recovery._calibrate_shadow_model(_Environment())

    assert result["interface_available"] is False
    assert result["active"] is False
    assert result["bind_identity"] is True
