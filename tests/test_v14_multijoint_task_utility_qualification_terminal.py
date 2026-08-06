from __future__ import annotations

from scripts import (
    freeze_v14_multijoint_task_utility_qualification_terminal as terminal,
)


def test_terminal_preserves_registered_nonpass_and_failed_gates() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not (
        terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    ).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is False
    assert summary["failed_registered_gates"] == [
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_task_success_noninferiority",
    ]
    assert summary["population"] == {
        "paired_task_init_count": 18,
        "episode_count": 72,
        "arm_count": 4,
        "episodes_per_arm": 18,
        "environment_seed": 2509,
        "policy_seed": 1251,
        "outcome_blind_before_protocol_freeze": True,
    }
    assert summary["task_outcomes"]["task_success_count"] == {
        "vla_only": 16,
        "execution_only": 10,
        "semantic_only": 15,
        "dual": 13,
    }
    assert summary["task_outcomes"][
        "official_unsafe_nonincrease_established"
    ] is True
    assert summary["interpretation"][
        "registered_result_unchanged"
    ] is True


def test_terminal_independent_scan_fixes_deadlock_and_containment() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not (
        terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    ).is_dir():
        return

    summary = terminal.build_summary()

    assert len(summary["deadlock_cases"]) == 10
    assert all(
        row["reason"] == "no_safe_multijoint_guard_candidate"
        for row in summary["deadlock_cases"]
    )
    assert all(
        row["eligible_candidate_count"] == 0
        for row in summary["deadlock_cases"]
    )
    assert summary["by_arm"]["execution_only"][
        "deadlock_episode_count"
    ] == 7
    assert summary["by_arm"]["dual"]["deadlock_episode_count"] == 3
    assert summary["mechanism"]["l2_actual_below_floor_count"] == 0
    assert summary["mechanism"]["l2_actual_crossing_count"] == 0
    assert summary["mechanism"]["disabled_actual_below_floor_count"] > 0
    assert summary["mechanism"]["disabled_actual_crossing_count"] > 0
    assert summary["calibration"]["registered_gate_passed"] is True
    assert summary["calibration"][
        "registered_observed_maximum_error_rad"
    ] <= summary["calibration"]["registered_maximum_error_rad"]
