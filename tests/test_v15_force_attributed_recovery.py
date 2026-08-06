from __future__ import annotations

import numpy as np
import pytest

from scripts import (
    run_l2_predictive_virtual_brake_v15_force_attributed_recovery as recovery,
)


def _audit(*, reported_force: float = 80.0) -> dict[str, object]:
    return {
        "enabled": True,
        "risk_sides": [
            {"joint_index": 1, "side": "upper"},
            {"joint_index": 3, "side": "lower"},
        ],
        "maximum_abs_guarded_constraint_force": reported_force,
        "floor_or_current_edge_recovery_selected": True,
        "intervened": True,
        "candidates": [],
    }


def _scope(*, joint1: float, joint3: float) -> list[list[dict[str, object]]]:
    return [
        [
            {
                "guarded_sides": [
                    {"joint_index": 1, "dof_constraint_force": joint1},
                    {"joint_index": 3, "dof_constraint_force": joint3},
                ]
            }
        ]
    ]


def test_force_attribution_separates_existing_and_added_force() -> None:
    audit = _audit(reported_force=80.0)
    pre = np.asarray([0.0, -100.0, 3.0, 40.0, 0.0, 0.0, 0.0])
    post = np.asarray([0.0, -25.0, 3.0, 50.0, 0.0, 0.0, 0.0])

    recovery._enrich_force_attribution(
        audit,
        pre_step_joint_constraint_force=pre,
        post_step_joint_constraint_force=post,
        scoped_force_audits=_scope(joint1=-80.0, joint3=70.0),
    )

    assert audit["schema"] == recovery.BRAKE_AUDIT_SCHEMA
    assert audit["force_attribution_risk_joint_indices"] == [1, 3]
    assert audit["pre_step_maximum_abs_risk_constraint_force"] == 100.0
    assert (
        audit[
            "guard_scope_reported_maximum_abs_risk_constraint_force"
        ]
        == 80.0
    )
    assert audit["post_step_maximum_abs_risk_constraint_force"] == 50.0
    assert audit["guard_scope_max_envelope_increment_over_pre_step"] == 0.0
    assert audit[
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ] == 30.0
    assert audit[
        "post_step_maximum_positive_joint_increment_over_pre_step"
    ] == 10.0
    assert audit["post_step_max_envelope_reduction_from_pre_step"] == 50.0
    assert audit["guard_scope_legacy_force_recomputed_identity"] is True
    assert audit["force_attribution_changes_mechanism"] is False


def test_force_attribution_records_positive_increment() -> None:
    audit = _audit(reported_force=125.0)
    pre = np.zeros(7)
    pre[1] = 100.0
    post = np.zeros(7)
    post[1] = 110.0

    recovery._enrich_force_attribution(
        audit,
        pre_step_joint_constraint_force=pre,
        post_step_joint_constraint_force=post,
        scoped_force_audits=_scope(joint1=125.0, joint3=0.0),
    )

    assert audit["guard_scope_max_envelope_increment_over_pre_step"] == 25.0
    assert audit[
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ] == 25.0
    assert audit[
        "post_step_maximum_positive_joint_increment_over_pre_step"
    ] == 10.0
    assert audit["post_step_max_envelope_reduction_from_pre_step"] == -10.0


def test_force_attribution_rejects_nonfinite_vectors() -> None:
    audit = _audit()
    invalid = np.zeros(7)
    invalid[2] = np.nan

    with pytest.raises(recovery.ForceAttributionError):
        recovery._enrich_force_attribution(
            audit,
            pre_step_joint_constraint_force=invalid,
            post_step_joint_constraint_force=np.zeros(7),
            scoped_force_audits=[],
        )
