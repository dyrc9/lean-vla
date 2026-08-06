from __future__ import annotations

from scripts import (
    freeze_v15_current_edge_recovery_development_terminal as terminal,
)


def test_terminal_preserves_registered_identity_nonpass() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_development_data_complete"] is False
    assert summary["registered_failed_gates"] == [
        "v15_recovery_prevention_identity",
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_task_success_noninferiority",
    ]
    assert summary["registered_result_unchanged"] is True
    assert summary["registered_gate_diagnostic"][
        "successor_native_prevention_identity_passed"
    ] is True
    assert summary["registered_gate_diagnostic"][
        "does_not_revise_registered_nonpass"
    ] is True


def test_terminal_fixes_partial_current_edge_gain_and_remaining_cost() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["task_outcomes"]["task_success_count"] == {
        "vla_only": 5,
        "execution_only": 2,
        "semantic_only": 5,
        "dual": 3,
    }
    assert summary["mechanism"]["total_recovery_selected_count"] == 118
    assert summary["mechanism"]["current_edge_selected_count"] == 61
    assert summary["mechanism"]["residual_deadlock_count"] == 6
    assert summary["mechanism"]["selected_floor_violation_count"] == 0
    assert summary["same_seed_comparison"]["v14"] == {
        "deadlock_episode_count": 10,
        "task_success_count": 3,
    }
    assert summary["same_seed_comparison"]["current_edge"] == {
        "deadlock_episode_count": 6,
        "task_success_count": 5,
    }
    assert summary["interpretation"]["recovery_development_success"] is False
