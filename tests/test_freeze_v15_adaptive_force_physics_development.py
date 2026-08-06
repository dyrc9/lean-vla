from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_adaptive_force_physics_development as freezer
from scripts import run_v15_adaptive_force_physics_development as runner


def test_predecessor_terminal_authorizes_only_disclosed_development() -> None:
    terminal = load_json_object(freezer.PREDECESSOR_TERMINAL)

    assert terminal["registered_development_pass"] is False
    assert len(terminal["residual_deadlock_lanes"]) == 2
    assert terminal["next_stage_decision"][
        "develop_fail_safe_force_constrained_successor"
    ] is True
    assert terminal["next_stage_decision"][
        "fresh_requalification_authorized"
    ] is False


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
    assert retained["design"]["proactive_trigger_margin_rad"] == 0.16
    assert retained["design"]["safe_margin_floor_rad"] == 0.15
    assert retained["design"]["staged_candidate_evaluation"] is True
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
    assert retained["gates"]["expected_v15_6_policy_step_count"] == 26460
