from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_bounded_state_triggered_task_utility_qualification as freezer,
)


def test_clean_freezer_excludes_all_registered_prior_pairs() -> None:
    prior = freezer._prior_pairs()
    base = load_json_object(freezer.BASE_POPULATION_PROTOCOL)
    selected = freezer._select_workloads(base["workloads"], prior)
    assert len(selected) == 18
    assert len(freezer._pairs(selected)) == 18
    assert not (freezer._pairs(selected) & prior)
    assert all(
        len(
            {
                row["task_id"]
                for row in selected
                if row["suite"] == suite
            }
        )
        == 6
        for suite in freezer.SUITES
    )


def test_clean_schedule_is_balanced_and_paired() -> None:
    prior = freezer._prior_pairs()
    base = load_json_object(freezer.BASE_POPULATION_PROTOCOL)
    workloads = freezer._select_workloads(base["workloads"], prior)
    schedule = freezer._build_schedule(workloads)
    assert len(schedule) == 72
    assert {row["arm"] for row in schedule} == set(freezer.ARM_ORDER)
    assert all(
        sum(row["base_pair_id"] == workload["base_pair_id"] for row in schedule)
        == 4
        for workload in workloads
    )


def test_clean_freezer_binds_fresh4_and_prior_task_utility() -> None:
    assert freezer.METHOD_QUALIFICATION_PROTOCOL in (
        freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert freezer.OLD_CLEAN_PROTOCOL in freezer.PRIOR_POPULATION_PROTOCOLS
    assert freezer.OLD_ATTACKED_PROTOCOL in freezer.PRIOR_POPULATION_PROTOCOLS
    assert (
        freezer.FAILED_CLEAN_FRESH1_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH2_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH3_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH4_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH5_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH6_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH7_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH8_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH9_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_FRESH10_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_V15_12_FRESH1_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert (
        freezer.FAILED_CLEAN_V15_13_FRESH1_PROTOCOL
        in freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert freezer.FAILED_CLEAN_FRESH1_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH2_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH3_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH4_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH5_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH6_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH7_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH8_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH9_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_FRESH10_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_V15_12_FRESH1_MANIFEST.is_file()
    assert freezer.FAILED_CLEAN_V15_13_FRESH1_MANIFEST.is_file()
