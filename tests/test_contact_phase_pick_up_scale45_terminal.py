from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_contact_phase_pick_up_scale45_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_scale45_terminal_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    assert retained["data_complete"] is True
    assert retained["result"]["aggregate"]["episode_count"] == 180
    assert retained["efficacy_pass_declared"] is False
    assert retained["attacked_defense_evaluated"] is False
    assert retained["co_tenant_resource_exception_active"] is True
    assert {
        arm: row["episodes"]
        for arm, row in retained["success_table"].items()
    } == {
        "vla_only": 45,
        "semantic_only": 45,
        "execution_only": 45,
        "dual": 45,
    }
    assert all(
        0.0 <= row["wilson_95_lower"] <= row["rate"]
        <= row["wilson_95_upper"] <= 1.0
        for row in retained["success_table"].values()
    )
    assert all(
        comparison["paired_task_count"] == 45
        for comparison in retained["paired_comparisons"].values()
    )
    assert retained["diagnostics"][
        "independent_constraint_signals"
    ]["aggregate"]["episode_count"] == 180
