from __future__ import annotations

from scripts import (
    freeze_v15_floor_guard_recovery_development_terminal as terminal,
)


def test_terminal_preserves_partial_recovery_without_utility_claim() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["development_data_complete"] is True
    assert summary["descriptive_clean_utility_gate_passed"] is False
    assert summary["mechanism"]["recovery_selected_count"] == 12
    assert summary["mechanism"][
        "recovery_prevented_deadlock_count"
    ] == 12
    assert summary["mechanism"]["residual_deadlock_count"] == 8
    assert summary["mechanism"][
        "recovery_selected_floor_violation_count"
    ] == 0
    assert summary["interpretation"][
        "recovery_development_success"
    ] is False


def test_same_seed_comparison_fixes_no_task_success_gain() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()
    comparison = summary["same_seed_v14_comparison"]

    assert comparison["paired_l2_episode_count"] == 14
    assert comparison["v14_deadlock_episode_count"] == 10
    assert comparison["v15_deadlock_episode_count"] == 8
    assert comparison["v14_task_success_count"] == 3
    assert comparison["v15_task_success_count"] == 3
    assert len(summary["residual_deadlocks"]) == 8
