from __future__ import annotations

from collections import Counter

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_current_edge_recovery_development as freezer


def test_successor_schedule_retains_population_arms_and_seeds() -> None:
    source = load_json_object(freezer.PREDECESSOR_PROTOCOL_PATH)

    schedule = freezer._successor_schedule(source)

    assert len(schedule) == 28
    assert Counter(row["arm"] for row in schedule) == {
        "vla_only": 7,
        "execution_only": 7,
        "semantic_only": 7,
        "dual": 7,
    }
    assert {
        (row["base_pair_id"], row["environment_seed"], row["policy_seed"])
        for row in schedule
    } == {
        (row["base_pair_id"], row["environment_seed"], row["policy_seed"])
        for row in source["schedule"]
    }


def test_frozen_current_edge_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
