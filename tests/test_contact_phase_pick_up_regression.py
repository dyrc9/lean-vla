from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_contact_phase_pick_up_regression import (
    OUTPUT_PATH,
    build_protocol,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (
    build_specs,
)


def test_contact_phase_regression_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    specs = build_specs(retained)
    assert len(specs) == 2
    assert {spec.unit.suite for spec in specs} == {
        "human_safety",
        "obstacle_avoidance",
    }
    assert {spec.arm for spec in specs} == {"dual"}
    assert {
        (spec.unit.env_seed, spec.unit.policy_seed)
        for spec in specs
    } == {(139, 59)}
