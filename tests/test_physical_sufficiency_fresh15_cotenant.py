from __future__ import annotations

from collections import Counter
from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_physical_sufficiency_fresh15_cotenant import (
    OUTPUT_PATH,
    V9_PROTOCOL_PATH,
    build_protocol,
    build_schedule,
    derive_workloads,
)
from scripts.run_physical_sufficiency_clean_pilot import (
    _patched_inherited,
)
from scripts import run_risk_selective_clean_pilot as inherited
from scripts import run_contact_phase_pick_up_clean_pilot as generic


def test_v10_workloads_are_balanced_and_new() -> None:
    v9 = load_json_object(V9_PROTOCOL_PATH)
    workloads = derive_workloads(v9)

    assert len(workloads) == 15
    assert Counter(row["suite"] for row in workloads) == {
        "human_safety": 5,
        "obstacle_avoidance": 5,
        "obstacle_avoidance_human": 5,
    }
    assert all(
        row["init_state_id"]
        not in row["prior_successor_init_state_ids"]
        for row in workloads
    )
    schedule = build_schedule(workloads)
    assert len(schedule) == 60
    assert all(
        Counter(
            item["arm"]
            for item in schedule
            if item["base_pair_id"] == row["base_pair_id"]
        )
        == {
            "vla_only": 1,
            "semantic_only": 1,
            "execution_only": 1,
            "dual": 1,
        }
        for row in workloads
    )


def test_v10_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    with _patched_inherited():
        with inherited._patched_generic():
            generic.validate_protocol(
                retained,
                protocol_path=OUTPUT_PATH,
            )
            specs = generic.build_specs(retained)
    assert len(specs) == 60
