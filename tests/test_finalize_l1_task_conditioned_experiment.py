from __future__ import annotations

import pytest

from scripts.finalize_l1_task_conditioned_experiment import (
    FinalizeError,
    _assert_analysis,
    _markdown_tables,
    _selective_rows,
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
        "l1_restore_complete_episode_count": 120,
        "typed_risk_signal_complete_count": 120,
        "risk_channel_sums": {
            "robot_contact_count": 4,
            "joint_limit_violation_steps": 5,
            "excessive_force_steps": 6,
        },
        "l1_shadow_latency_seconds": 1.25,
        "episode_wall_time_seconds": 12.5,
        "recovery_selected_kinds": {"reverse_then_hold": 2},
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
        "registered_risk_analysis": {
            "same_as_45_35_percent_baseline": True,
            "channels": [
                "libero_cost_or_collision",
                "robot_contact_count_delta",
                "joint_limit_steps_delta",
                "excessive_force_steps_delta",
            ],
            "by_arm": {
                arm: {
                    "arm_specific_clean_eligible_count": 100,
                    "clean_eligible_base_pair_count": 55,
                    "transition_count": 20,
                    "transition_rate": 0.2,
                    "cluster_bootstrap_interval_95": {
                        "lower": 0.1,
                        "upper": 0.3,
                    },
                    "invalid_attacked_conservative_transition_count": 1,
                    "channel_transition_counts": {
                        "libero_cost_or_collision": 2,
                        "robot_contact_count_delta": 8,
                        "joint_limit_steps_delta": 9,
                        "excessive_force_steps_delta": 10,
                    },
                }
                for arm in ARMS
            },
        },
        "selective_decision_summary": {
            arm: {
                "baseline_arm": baseline,
                "l1_episode_count": 240,
                "first_action_intervention_count": 20,
                "identity_bound_first_action_intervention_count": 10,
                "safe_action_false_reject_count": 2,
                "safe_action_false_reject_rate": 0.2,
                "identity_bound_first_action_allow_count": 30,
                "unsafe_first_action_allow_count": 3,
                "unsafe_first_action_allow_rate": 0.1,
                "paired_transition_unsafe_allow_episode_count": 4,
                "recovery_success_episode_count": 5,
                "recovery_deadlock_episode_count": 6,
            }
            for arm, baseline in (
                ("semantic_only", "vla_only"),
                ("dual", "execution_only"),
            )
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
    selective_rows = _selective_rows(_analysis())
    assert len(condition_rows) == 8
    assert len(risk_rows) == 4
    assert len(selective_rows) == 2
    markdown = _markdown_tables(condition_rows, risk_rows, selective_rows)
    assert "60/120 (50.00%)" in markdown
    assert "20/100 (20.00%)" in markdown
    assert "48/120 (40.00%)" in markdown
    assert "2 (20.00%)" in markdown
    assert "3 (10.00%)" in markdown
    assert "120/120" in markdown
    assert "attacked LIBERO cost/collision" in markdown
    assert "positive attacked-minus-clean delta" in markdown
