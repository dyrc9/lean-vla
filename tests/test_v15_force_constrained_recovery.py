from __future__ import annotations

import numpy as np

from scripts import (
    run_l2_predictive_virtual_brake_v15_force_constrained_recovery as recovery,
)


def test_force_constrained_config_preserves_candidates_and_softens_profile() -> None:
    edge = 0.158
    config = recovery.ForceConstrainedRecoveryConfig(edge)

    assert config.guard_margins_rad == (
        *recovery.BRAKE_MARGINS_RAD,
        edge,
        recovery.RECOVERY_GUARD_MARGIN_RAD,
    )
    assert config.guard_solref == (0.006, 1.0)
    assert config.guard_solimp == recovery.GUARD_SOLIMP


def test_standard_and_recovery_force_envelopes_are_distinct() -> None:
    metrics = {
        "scope_positive_joint_increment": 2000.0,
        "post_step_absolute_risk_force": 3000.0,
        "post_step_positive_joint_increment": 2000.0,
    }

    assert recovery._force_feasible(metrics, recovery_candidate=False) is True
    assert recovery._force_feasible(metrics, recovery_candidate=True) is False


def test_risk_force_metrics_use_per_joint_positive_increments() -> None:
    pre = np.zeros(7)
    pre[1] = 100.0
    post = np.zeros(7)
    post[1] = 500.0
    torque_audit = [
        {
            "guarded_sides": [
                {"joint_index": 1, "dof_constraint_force": 900.0}
            ]
        },
        {
            "guarded_sides": [
                {"joint_index": 1, "dof_constraint_force": 800.0}
            ]
        },
    ]

    metrics = recovery._risk_force_metrics(
        pre=pre,
        post=post,
        torque_audit=torque_audit,
        risk_indices=(1,),
    )

    assert metrics == {
        "scope_absolute_risk_force": 900.0,
        "scope_positive_joint_increment": 800.0,
        "post_step_absolute_risk_force": 500.0,
        "post_step_positive_joint_increment": 400.0,
    }
