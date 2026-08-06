from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_dynamic_state_physics_robustness_qualification as freezer,
)
from scripts import (
    run_v15_dynamic_state_physics_robustness_qualification as runner,
)


def test_selection_excludes_every_prior_exact_pair() -> None:
    base = load_json_object(freezer.BASE_POPULATION_PROTOCOL)
    prior = freezer._prior_pairs()
    selected = freezer._select_environments(base["workloads"], prior)

    assert len(freezer.PRIOR_POPULATION_PROTOCOLS) == 37
    assert len(prior) == 275
    assert len(selected) == 18
    assert not (freezer._pairs(selected) & prior)
    assert len(freezer._pairs(selected)) == 18
    assert all(
        len({row["task_id"] for row in selected if row["suite"] == suite})
        == 6
        for suite in freezer.SUITES
    )
    assert freezer._dynamic_environment_count(selected) > 0


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
    assert retained["design"]["qualification_population"] is True
    assert retained["design"]["outcome_disclosed_population_reused"] is False
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
    assert retained["gates"]["expected_total_baseline_lane_count"] == 21168
