from __future__ import annotations

from scripts.freeze_horizon_consistent_pick_up_regression_smoke import (
    build_protocol,
)
from scripts.run_horizon_consistent_pick_up_regression_smoke import (
    PROTOCOL_SCHEMA,
)


def test_regression_smoke_protocol_stays_narrow() -> None:
    protocol = build_protocol()

    assert protocol["schema"] == PROTOCOL_SCHEMA
    assert protocol["execution_authorization"] == {
        "clean_dual_regression_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }
    assert protocol["workload"]["max_steps"] == 80
    assert protocol["design"]["pair_reused_from_failed_screening"]
    assert protocol["gates"]["minimum_complete_transaction_count"] == 6
    assert protocol["gates"]["maximum_effect_reject_count"] == 0
    assert protocol["gates"][
        "minimum_horizon_without_holding_count"
    ] == 1
    assert protocol["gates"]["task_success_required"] is False
