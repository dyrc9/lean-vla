from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_dynamic_state_physics_development as freezer
from scripts import run_v15_dynamic_state_physics_development as runner


def test_disclosed_population_contains_dynamic_and_static_tasks() -> None:
    predecessor = load_json_object(freezer.PREDECESSOR_PROTOCOL)

    assert len(predecessor["environments"]) == 18
    assert freezer._dynamic_environment_count(predecessor["environments"]) == 15


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
    assert retained["design"]["dynamic_environment_count"] == 15
    assert retained["gates"]["expected_v15_4_policy_step_count"] == 26460
    assert (
        retained["gates"][
            "minimum_dynamic_motion_generator_step_count"
        ]
        == 22050
    )
