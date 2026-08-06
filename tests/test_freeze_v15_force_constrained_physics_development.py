from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_force_constrained_physics_development as freezer
from scripts import run_v15_force_constrained_physics_development as runner


def test_predecessor_terminal_authorizes_only_disclosed_development() -> None:
    terminal = load_json_object(freezer.PREDECESSOR_TERMINAL)

    assert terminal["registered_qualification_pass"] is False
    assert terminal["next_stage_decision"][
        "develop_force_constrained_successor"
    ] is True
    assert terminal["next_stage_decision"][
        "require_new_population_for_requalification"
    ] is True


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
    assert retained["design"]["qualification_population"] is False
    assert retained["design"]["outcome_disclosed_population_reused"] is True
    assert retained["design"]["candidate_post_force_prediction_active"] is True
    assert retained["design"]["force_constrained_guard_solref"] == [0.006, 1.0]
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
