from __future__ import annotations

from scripts import (
    freeze_v15_current_edge_priority_recovery_development_terminal as terminal,
)


def test_terminal_selects_candidate_without_claiming_qualification() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["development_data_complete"] is True
    assert summary["descriptive_clean_utility_gate_passed"] is False
    assert summary["failed_gates"] == [
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_task_success_noninferiority",
    ]
    assert summary["task_outcomes"]["task_success_count"] == {
        "vla_only": 5,
        "execution_only": 4,
        "semantic_only": 5,
        "dual": 4,
    }
    assert summary["development_selection"][
        "recovery_candidate_selected_for_stress_qualification"
    ] is True
    assert summary["development_selection"][
        "parameters_frozen_for_next_stage"
    ] is True


def test_terminal_fixes_zero_deadlock_and_explicit_costs() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["mechanism"]["current_edge_selected_count"] == 300
    assert summary["mechanism"]["floor_edge_selected_count"] == 0
    assert summary["mechanism"]["residual_deadlock_count"] == 0
    assert summary["mechanism"]["selected_floor_violation_count"] == 0
    assert summary["same_seed_development_comparison"][
        "v14_predictive_brake"
    ]["task_success_count"] == 3
    assert summary["same_seed_development_comparison"][
        "v15_2_current_then_floor_edge"
    ] == {
        "l2_episode_count": 14,
        "deadlock_episode_count": 0,
        "task_success_count": 8,
    }
    assert summary["mechanism"]["maximum_abs_constraint_force"] > 6000
    assert summary["screen_latency_seconds"]["maximum"] > 0.15
