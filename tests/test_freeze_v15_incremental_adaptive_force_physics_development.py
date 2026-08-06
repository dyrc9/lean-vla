from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_incremental_adaptive_force_physics_development as freezer,
)
from scripts import (
    run_v15_incremental_adaptive_force_physics_development as runner,
)


def test_predecessor_terminal_authorizes_incremental_successor() -> None:
    terminal = load_json_object(freezer.PREDECESSOR_TERMINAL)

    assert terminal["registered_development_pass"] is False
    assert terminal["nonpass_axes"] == {
        "v15_3_latency_max": ["arm_friction_0_7x"]
    }
    assert terminal["next_stage_decision"][
        "develop_incremental_extended_search_successor"
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
    assert retained["design"]["incremental_extended_search"] is True
    assert retained["design"]["maximum_extended_candidates_per_increment"] == 1
    assert retained["design"][
        "extended_recovery_force_attribution_bound"
    ] is True
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
    assert retained["gates"]["expected_v15_7_policy_step_count"] == 26460
