from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_physical_sufficiency_fresh15_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_v10_fresh15_terminal_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert retained["data_complete"] is True
    assert retained["success_table"]["semantic_only"][
        "successes"
    ] == 7
    assert retained["success_table"]["vla_only"]["successes"] == 10
    assert retained["paired_comparisons"]["semantic_vs_vla"][
        "risk_difference"
    ] == -0.2
    assert retained["interpretation"][
        "clean_noninferiority_declared"
    ] is False
