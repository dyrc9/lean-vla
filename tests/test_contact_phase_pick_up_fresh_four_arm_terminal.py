from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_contact_phase_pick_up_fresh_four_arm_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_contact_phase_fresh_terminal_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    assert retained["preliminary_paper_table_available"] is True
    assert retained["efficacy_pass_declared"] is False
    assert retained["attacked_defense_evaluated"] is False
    assert retained["preliminary_success_table"] == {
        "vla_only": {
            "successes": 2,
            "episodes": 3,
            "rate": 2 / 3,
        },
        "semantic_only": {
            "successes": 0,
            "episodes": 3,
            "rate": 0.0,
        },
        "execution_only": {
            "successes": 2,
            "episodes": 3,
            "rate": 2 / 3,
        },
        "dual": {
            "successes": 0,
            "episodes": 3,
            "rate": 0.0,
        },
    }
    assert retained["diagnostics"][
        "contact_phase_recovery_count"
    ] == 4
    assert retained["diagnostics"][
        "contact_phase_command_change_count"
    ] == 0
    independent = retained["diagnostics"][
        "independent_constraint_signals"
    ]["aggregate"]
    assert independent["episodes_with_joint_limit_violation"] > 0
    assert independent["episodes_with_excessive_force"] == 0
