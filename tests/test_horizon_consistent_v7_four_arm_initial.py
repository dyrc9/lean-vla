from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts.freeze_horizon_consistent_v7_four_arm_initial import (
    build_protocol,
)
from scripts.run_horizon_consistent_v7_four_arm_initial import (
    QUALIFICATION_PROTOCOL_PATH,
    build_schedule_rows,
    build_specs,
    derive_initial_workloads,
    schedule_sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_initial_protocol.json"
)


def test_initial_workloads_are_fresh_and_cover_three_suites() -> None:
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    workloads = derive_initial_workloads(qualification)

    assert [row["suite"] for row in workloads] == [
        "human_safety",
        "obstacle_avoidance",
        "obstacle_avoidance_human",
    ]
    assert len(workloads) == 3
    for row in workloads:
        assert row["init_state_id"] not in row["prior_init_state_ids"]
        assert row["init_state_id"] == (
            row["qualification_init_state_id"] + 4
        ) % 50


def test_initial_schedule_has_three_paired_units_and_four_arms() -> None:
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    workloads = derive_initial_workloads(qualification)
    schedule = build_schedule_rows(workloads)

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
        assert len(rows) == 4
        assert {row["arm"] for row in rows} == set(ARM_ORDER)
        assert {row["environment_seed"] for row in rows} == {139}
        assert {row["policy_seed"] for row in rows} == {59}
    assert schedule_sha256(schedule) == schedule_sha256(
        build_schedule_rows(workloads)
    )


def test_initial_protocol_and_specs_are_current() -> None:
    if not PROTOCOL_PATH.is_file():
        return
    retained = load_json_object(PROTOCOL_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    specs = build_specs(retained)
    assert [spec.sequence_index for spec in specs] == list(range(12))
    assert [spec.episode_id for spec in specs] == [
        row["episode_id"] for row in retained["schedule"]
    ]
