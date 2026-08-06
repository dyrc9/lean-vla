from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_rolling_prebound_recovery as recovery,
)


def test_runner_binds_pre_step_base_class_immutably() -> None:
    assert recovery.predecessor._INCREMENTAL_BASE_CLASS is not (
        recovery.MultiJointRollingPreboundRecoveryEnvironment
    )


def test_runner_declares_rolling_schema() -> None:
    assert "v15.10" in recovery.BRAKE_AUDIT_SCHEMA
    assert "rolling_prebound" in recovery.RUNNER_VARIANT
