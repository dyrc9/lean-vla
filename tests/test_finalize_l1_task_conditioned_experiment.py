from __future__ import annotations

import pytest

from scripts.finalize_l1_task_conditioned_experiment import (
    FinalizeError,
    _assert_analysis,
    _markdown_tables,
    _table_rows,
)


ARMS = ("vla_only", "semantic_only", "execution_only", "dual")


def _arm_summary() -> dict:
    return {
        "episode_count": 120,
        "terminal_exception_count": 0,
        "task_success_count": 60,
        "task_success_rate": 0.5,
        "l1_intervention_count": 3,
        "l1_intervention_rate_per_policy_call": 0.1,
        "typed_risk_signal_complete_count": 120,
        "risk_channel_sums": {
            "robot_contact_count": 4,
            "joint_limit_violation_steps": 5,
            "excessive_force_steps": 6,
        },
        "l1_shadow_latency_seconds": 1.25,
        "episode_wall_time_seconds": 12.5,
    }


def _analysis() -> dict:
    return {
        "risk_transition_definition": {
            "same_as_45_35_percent_baseline": True,
        },
        "episode_rows": [{} for _ in range(960)],
        "paired_rows": [{} for _ in range(480)],
        "condition_arm_summary": {
            condition: {arm: _arm_summary() for arm in ARMS}
            for condition in ("clean", "attacked")
        },
        "paired_risk_summary": {
            arm: {
                "pair_count": 120,
                "any_risk_transition_count": 24,
                "any_risk_transition_rate": 0.2,
                "safe_task_success_count": 48,
                "safe_task_success_rate": 0.4,
                "channel_transition_counts": {
                    "robot_contact_count": 8,
                    "joint_limit_violation_steps": 9,
                    "excessive_force_steps": 10,
                },
            }
            for arm in ARMS
        },
    }


def test_finalizer_requires_complete_registered_heldout_analysis() -> None:
    analysis = _analysis()
    _assert_analysis(analysis)
    analysis["risk_transition_definition"]["same_as_45_35_percent_baseline"] = False
    with pytest.raises(FinalizeError):
        _assert_analysis(analysis)


def test_generated_tables_are_derived_from_analysis() -> None:
    condition_rows, risk_rows = _table_rows(_analysis())
    assert len(condition_rows) == 8
    assert len(risk_rows) == 4
    markdown = _markdown_tables(condition_rows, risk_rows)
    assert "60/120 (50.00%)" in markdown
    assert "24/120 (20.00%)" in markdown
    assert "48/120 (40.00%)" in markdown
    assert "attacked minus clean is greater than zero" in markdown
