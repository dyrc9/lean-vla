from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts.freeze_contact_phase_pick_up_scale45_four_arm import (
    FRESH_INIT_OFFSET,
    OUTPUT_PATH,
    QUALIFICATION_POPULATION_PATH,
    build_protocol,
    build_schedule,
    derive_scale45_workloads,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (
    build_specs,
)


def test_scale45_workloads_cover_all_tasks_with_fresh_states() -> None:
    qualification = load_json_object(QUALIFICATION_POPULATION_PATH)
    workloads = derive_scale45_workloads(qualification)

    assert len(workloads) == 45
    assert {
        suite: sum(row["suite"] == suite for row in workloads)
        for suite in {
            "human_safety",
            "obstacle_avoidance",
            "obstacle_avoidance_human",
        }
    } == {
        "human_safety": 15,
        "obstacle_avoidance": 15,
        "obstacle_avoidance_human": 15,
    }
    for row in workloads:
        assert row["init_state_id"] not in row[
            "prior_init_state_ids"
        ]
        assert row["init_state_id"] == (
            row["qualification_init_state_id"]
            + FRESH_INIT_OFFSET
        ) % 50


def test_scale45_schedule_is_paired_and_balanced() -> None:
    qualification = load_json_object(QUALIFICATION_POPULATION_PATH)
    workloads = derive_scale45_workloads(qualification)
    schedule = build_schedule(workloads)

    assert len(schedule) == 180
    assert {
        arm: sum(row["arm"] == arm for row in schedule)
        for arm in ARM_ORDER
    } == {arm: 45 for arm in ARM_ORDER}
    for workload in workloads:
        rows = [
            row
            for row in schedule
            if row["base_pair_id"] == workload["base_pair_id"]
        ]
        assert len(rows) == 4
        assert {row["arm"] for row in rows} == set(ARM_ORDER)
        assert {row["environment_seed"] for row in rows} == {157}
        assert {row["policy_seed"] for row in rows} == {71}


def test_scale45_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    assert retained["outcomes_observed_for_selection"] is False
    assert retained["design"]["episode_count_per_arm"] == 45
    specs = build_specs(retained)
    assert len(specs) == 180
    assert [spec.sequence_index for spec in specs] == list(range(180))
