from __future__ import annotations

from scripts import (
    freeze_v15_force_attributed_recovery_attacked_task_utility_qualification_terminal as terminal,
)


def test_terminal_preserves_registered_nonpass_and_completed_axes() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is False
    assert summary["registered_data_complete"] is True
    assert summary["failed_registered_gates"] == [
        "v9_dual_task_success_noninferiority"
    ]
    assert {
        arm: row["task_success_count"]
        for arm, row in summary["task_utility"]["by_arm"].items()
    } == terminal.EXPECTED_TASK_SUCCESS
    assert summary["task_utility"][
        "execution_only_noninferiority_passed"
    ] is True
    assert summary["task_utility"][
        "dual_noninferiority_passed"
    ] is False
    assert summary["nonpass_axis"]["lower_97_5_percentile"] == -2 / 9
    assert summary["nonpass_axis"]["registered_margin"] == -0.2
    assert summary["attack_activation"][
        "changed_first_action_block_count"
    ] == 72
    assert all(summary["completed_axes"].values())
    assert summary["mujoco_warning_audit"][
        "contact_capacity_time_zero_count"
    ] == 40
    assert summary["mujoco_warning_audit"][
        "contact_capacity_nonzero_or_unknown_time_count"
    ] == 0
    assert summary["next_stage_decision"][
        "relax_noninferiority_margin"
    ] is False


def test_frozen_terminal_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
