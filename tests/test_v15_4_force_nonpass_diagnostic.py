from __future__ import annotations

import numpy as np

from scripts import diagnose_v15_4_force_nonpass as diagnostic


def _candidate(margin: float, force: float, *, eligible: bool) -> dict:
    return {
        "guard_margin_rad": margin,
        "predicted_minimum_margin_rad": 0.151,
        "maximum_abs_constraint_force": force,
        "configuration_inside_guard_ranges": True,
        "eligible": eligible,
    }


def _observation() -> dict:
    return {
        "runner_step_id": 0,
        "triggered": True,
        "intervened": True,
        "deadlock": False,
        "floor_or_current_edge_recovery_selected": False,
        "selected_guard_margin_rad": 0.155,
        "current_target_margin_rad": 0.16,
        "unguarded_predicted_minimum_margin_rad": 0.14,
        "selected_predicted_minimum_margin_rad": 0.151,
        "actual_minimum_margin_rad": 0.151,
        "prediction_execution_margin_error_rad": 0.0,
        "pre_step_maximum_abs_risk_constraint_force": 100.0,
        "guard_scope_maximum_positive_joint_increment_over_pre_step": 1700.0,
        "guard_scope_reported_maximum_abs_risk_constraint_force": 1800.0,
        "post_step_maximum_abs_risk_constraint_force": 900.0,
        "post_step_maximum_positive_joint_increment_over_pre_step": 800.0,
        "risk_sides": [{"joint_index": 1, "side": "upper"}],
        "pre_step_joint_constraint_force": [],
        "post_step_joint_constraint_force": [],
        "candidates": [
            _candidate(0.155, 1800.0, eligible=True),
            _candidate(0.150001, 900.0, eligible=True),
        ],
    }


def test_step_summary_exposes_lower_force_eligible_candidate() -> None:
    row = diagnostic._step_summary(_observation())

    assert row["selected_candidate_force"] == 1800.0
    assert row["minimum_eligible_candidate_force"] == 900.0
    assert row["lower_force_eligible_candidate_exists"] is True
    assert row["candidates"][0]["selected"] is True
    assert row["candidates"][1]["selected"] is False


def test_exactly_one_fails_closed() -> None:
    try:
        diagnostic._exactly_one(
            [{"id": 1}, {"id": 1}], field="id", value=1
        )
    except diagnostic.V154ForceNonpassDiagnosticError:
        pass
    else:
        raise AssertionError("duplicate disclosed rows must fail closed")


def test_candidate_post_force_capture_is_attached_in_scope_order() -> None:
    observation = _observation()
    observation["pre_step_joint_constraint_force"] = [
        {"joint_index": index, "dof_constraint_force": 100.0}
        for index in range(7)
    ]
    observation["post_step_joint_constraint_force"] = [
        {
            "joint_index": index,
            "dof_constraint_force": 300.0 if index == 1 else 0.0,
        }
        for index in range(7)
    ]
    first = np.zeros(7)
    first[1] = 1800.0
    second = np.zeros(7)
    second[1] = 900.0
    actual = np.zeros(7)
    actual[1] = 300.0

    diagnostic._attach_candidate_post_forces(
        observation, [first, second, actual]
    )

    assert observation["candidates"][0][
        "predicted_post_step_maximum_positive_joint_increment"
    ] == 1700.0
    assert observation["candidates"][1][
        "predicted_post_step_maximum_abs_risk_constraint_force"
    ] == 900.0


def test_diagnostic_recovery_ladder_stays_between_current_and_floor() -> None:
    edge = 0.159
    config = diagnostic.DiagnosticRecoveryLadderConfig(edge)
    margins = config.guard_margins_rad
    ladder = margins[
        len(diagnostic.recovery.BRAKE_MARGINS_RAD) + 1 : -1
    ]

    assert margins[:4] == diagnostic.recovery.BRAKE_MARGINS_RAD
    assert margins[4] == edge
    assert margins[-1] == diagnostic.recovery.RECOVERY_GUARD_MARGIN_RAD
    assert len(ladder) == len(diagnostic.RECOVERY_LADDER_FRACTIONS)
    assert all(
        diagnostic.recovery.RECOVERY_GUARD_MARGIN_RAD < value < edge
        for value in ladder
    )


def test_diagnostic_solver_profile_is_bound_in_config_context() -> None:
    priority = diagnostic.recovery.predecessor.predecessor
    original = priority.CurrentEdgePriorityRecoveryConfig

    with diagnostic._patched_diagnostic_recovery_ladder((0.02, 1.0)):
        config = priority.CurrentEdgePriorityRecoveryConfig(0.159)
        assert isinstance(config, diagnostic.DiagnosticRecoveryLadderConfig)
        assert config.guard_solref == (0.02, 1.0)

    assert priority.CurrentEdgePriorityRecoveryConfig is original
