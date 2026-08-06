from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_physics_qualification as freezer,
)
from scripts import (
    run_v15_incremental_adaptive_force_physics_qualification as runner,
)


EXPECTED_PAIRS = [
    ("obstacle_avoidance", 0, 34),
    ("obstacle_avoidance", 11, 46),
    ("obstacle_avoidance", 9, 26),
    ("obstacle_avoidance", 4, 47),
    ("obstacle_avoidance", 7, 25),
    ("obstacle_avoidance", 6, 9),
    ("human_safety", 5, 38),
    ("human_safety", 13, 1),
    ("human_safety", 2, 17),
    ("human_safety", 9, 41),
    ("human_safety", 0, 2),
    ("human_safety", 12, 43),
    ("obstacle_avoidance_human", 4, 3),
    ("obstacle_avoidance_human", 5, 26),
    ("obstacle_avoidance_human", 12, 10),
    ("obstacle_avoidance_human", 9, 11),
    ("obstacle_avoidance_human", 3, 19),
    ("obstacle_avoidance_human", 14, 26),
]


def test_selection_excludes_all_prior_exact_pairs() -> None:
    base = load_json_object(freezer.BASE_POPULATION_PROTOCOL)
    prior = freezer._prior_pairs()
    selected = freezer._select_environments(base["workloads"], prior)

    assert len(freezer.PRIOR_POPULATION_PROTOCOLS) == 41
    assert len(prior) == 293
    assert len(selected) == 18
    assert not (freezer._pairs(selected) & prior)
    assert len(freezer._pairs(selected)) == 18
    assert [
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in selected
    ] == EXPECTED_PAIRS
    assert freezer._dynamic_environment_count(selected) == 15


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )
    assert retained == rebuilt
    assert retained["schema"] == runner.PROTOCOL_SCHEMA
    assert retained["selection"][
        "all_prior_exact_task_init_pairs_excluded"
    ] is True
    assert retained["selection"]["prior_population_protocol_count"] == 41
    assert retained["selection"]["prior_exact_pair_count"] == 293
    assert retained["design"]["qualification_population"] is True
    assert retained["design"]["outcome_disclosed_population_reused"] is False
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
    assert retained["gates"]["expected_total_baseline_lane_count"] == 21168
