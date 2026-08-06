from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_model_mismatch_qualification as freezer,
)
from scripts import (
    run_v15_incremental_adaptive_force_model_mismatch_qualification as runner,
)


EXPECTED_PAIRS = [
    ("obstacle_avoidance", 10, 11),
    ("obstacle_avoidance", 9, 4),
    ("obstacle_avoidance", 13, 37),
    ("obstacle_avoidance", 6, 34),
    ("obstacle_avoidance", 1, 41),
    ("obstacle_avoidance", 5, 5),
    ("human_safety", 12, 13),
    ("human_safety", 4, 34),
    ("human_safety", 2, 1),
    ("human_safety", 5, 10),
    ("human_safety", 10, 20),
    ("human_safety", 6, 41),
    ("obstacle_avoidance_human", 2, 44),
    ("obstacle_avoidance_human", 12, 27),
    ("obstacle_avoidance_human", 0, 37),
    ("obstacle_avoidance_human", 13, 9),
    ("obstacle_avoidance_human", 11, 46),
    ("obstacle_avoidance_human", 14, 45),
]


def test_selection_excludes_all_prior_exact_pairs() -> None:
    base = load_json_object(freezer.BASE_POPULATION_PROTOCOL)
    prior = freezer._prior_pairs()
    selected = freezer._select_environments(base["workloads"], prior)

    assert len(freezer.PRIOR_POPULATION_PROTOCOLS) == 42
    assert len(prior) == 311
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
    assert retained["selection"]["prior_population_protocol_count"] == 42
    assert retained["selection"]["prior_exact_pair_count"] == 311
    assert retained["design"]["actual_and_shadow_models_separated"] is True
    assert retained["design"]["actual_model_restored_before_execution"] is True
    assert retained["gates"]["prediction_execution_error_rad_max"] == 0.01
    assert retained["gates"]["expected_model_mismatch_predictive_run_count"] == 10584
    assert retained["gates"][
        "expected_nontrivial_model_mismatch_predictive_run_count"
    ] == 9072
