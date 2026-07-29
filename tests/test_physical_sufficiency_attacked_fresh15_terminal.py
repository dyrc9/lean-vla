from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_physical_sufficiency_attacked_fresh15_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_attacked_fresh15_terminal_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert retained["data_complete"] is True
    assert retained["success_table"]["vla_only"]["successes"] == 8
    assert retained["success_table"]["semantic_only"]["successes"] == 7
    assert retained["paired_comparisons"]["semantic_vs_vla"][
        "risk_difference"
    ] == -(1 / 15)
    assert retained["mechanism"][
        "physical_risk_reject_count_enrichment"
    ] == -4
    assert retained["interpretation"][
        "confirmatory_defense_claim_authorized"
    ] is False
    diagnostics = retained["post_hoc_trace_diagnostics"]
    assert diagnostics["aggregate_by_arm"]["semantic_only"][
        "joint_limit_violation_steps"
    ] == 109
    assert diagnostics["aggregate_by_arm"]["vla_only"][
        "joint_limit_violation_steps"
    ] == 768
