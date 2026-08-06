from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts.freeze_contact_phase_pick_up_fresh_four_arm import (
    OUTPUT_PATH,
    QUALIFICATION_POPULATION_PATH,
    build_protocol,
    build_schedule,
    derive_fresh_workloads,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (
    build_specs,
)


def test_contact_phase_fresh_workloads_are_disjoint() -> None:
    qualification = load_json_object(QUALIFICATION_POPULATION_PATH)
    workloads = derive_fresh_workloads(qualification)

    assert len(workloads) == 3
    assert {row["suite"] for row in workloads} == {
        "human_safety",
        "obstacle_avoidance",
        "obstacle_avoidance_human",
    }
    for row in workloads:
        assert row["init_state_id"] not in row[
            "prior_init_state_ids"
        ]
        assert row["init_state_id"] == (
            row["qualification_init_state_id"] + 5
        ) % 50


def test_contact_phase_fresh_schedule_is_paired_four_arm() -> None:
    qualification = load_json_object(QUALIFICATION_POPULATION_PATH)
    workloads = derive_fresh_workloads(qualification)
    schedule = build_schedule(workloads)

    assert len(schedule) == 12
    assert {
        arm: sum(row["arm"] == arm for row in schedule)
        for arm in ARM_ORDER
    } == {arm: 3 for arm in ARM_ORDER}
    for workload in workloads:
        rows = [
            row
            for row in schedule
            if row["base_pair_id"] == workload["base_pair_id"]
        ]
        assert {row["arm"] for row in rows} == set(ARM_ORDER)
        assert {row["environment_seed"] for row in rows} == {149}
        assert {row["policy_seed"] for row in rows} == {61}


def test_contact_phase_fresh_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    specs = build_specs(retained)
    assert len(specs) == 12
    assert [spec.sequence_index for spec in specs] == list(range(12))
