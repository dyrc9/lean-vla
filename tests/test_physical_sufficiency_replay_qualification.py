from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_physical_sufficiency_replay_qualification import (
    OUTPUT_PATH,
    build_protocol,
)
from scripts.run_physical_sufficiency_replay_qualification import (
    build_result,
)


def test_physical_sufficiency_replay_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    result = build_result(retained, protocol_path=OUTPUT_PATH)
    assert result["qualification_pass"] is True
    assert result["aggregate"][
        "successor_recovered_semantic_unknown_count"
    ] == 6
    assert result["aggregate"][
        "successor_retained_physical_reject_count"
    ] == 3
    assert result["aggregate"]["successor_effect_replan_count"] == 4
    assert result["counterfactual_success_rate_computed"] is False
