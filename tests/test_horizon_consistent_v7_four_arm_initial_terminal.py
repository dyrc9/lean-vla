from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_horizon_consistent_v7_four_arm_initial_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_initial_terminal_summary_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    assert retained["exploratory_data_complete"] is True
    assert retained["efficacy_pass_declared"] is False
    assert retained["result"]["aggregate"][
        "selected_hard_violation_count"
    ] == 0
    assert retained["result"]["aggregate"][
        "unsafe_cost_or_collision_count"
    ] == 0
    assert retained["diagnostics"][
        "semantic_projection_budget_rejection_count"
    ] == 4
