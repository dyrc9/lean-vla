from __future__ import annotations

from scripts import (
    freeze_v15_force_attributed_recovery_task_utility_qualification_terminal as terminal,
)


def test_terminal_preserves_pass_and_separates_force_diagnostic() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    root = terminal.REPO_ROOT / str(protocol["fresh_output_root"])
    if not root.is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is True
    assert summary["failed_registered_gates"] == []
    assert all(summary["registered_gate_results"].values())
    assert {
        arm: row["task_success_count"]
        for arm, row in summary["task_utility"]["by_arm"].items()
    } == terminal.EXPECTED_TASK_SUCCESS
    assert summary["task_utility"][
        "paired_task_success_contrasts"
    ]["execution_only_minus_vla_only"]["lower"] == -1 / 6
    assert summary["task_utility"][
        "paired_task_success_contrasts"
    ]["dual_minus_semantic_only"]["lower"] == 0.0
    for arm in terminal.L2_ARMS:
        assert summary["task_utility"]["by_arm"][arm][
            "actual_below_floor_count"
        ] == 0
        assert summary["task_utility"]["by_arm"][arm][
            "actual_crossing_count"
        ] == 0
    diagnostic = summary["natural_task_force_envelope_diagnostic"]
    assert diagnostic["registered_task_utility_gate"] is False
    assert diagnostic["retrospective_comparison_only"] is True
    assert diagnostic["comparison_results"][
        "recovery_scope_increment"
    ] is False
    assert diagnostic["comparison_results"][
        "recovery_post_increment"
    ] is True
    assert summary["explicit_nonclaims"][
        "natural_task_recovery_force_within_stress_envelope"
    ] is False
    assert summary["next_stage_decision"][
        "modify_registered_task_utility_result"
    ] is False


def test_frozen_terminal_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = terminal.load_json_object(terminal.OUTPUT_PATH)

    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))

    assert rebuilt == retained
