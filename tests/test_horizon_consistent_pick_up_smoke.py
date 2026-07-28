from __future__ import annotations

from scripts import (
    freeze_horizon_consistent_pick_up_phase_transition_smoke as phase_freeze,
)
from scripts import (
    freeze_horizon_consistent_pick_up_regression_smoke as regression_freeze,
)
from scripts.run_horizon_consistent_pick_up_regression_smoke import (
    PROTOCOL_SCHEMA,
)


def _allow_dirty_test_build(monkeypatch, module) -> None:
    original = module._git

    def patched(*args):
        if args[:2] == (
            "status",
            "--porcelain=v1",
        ):
            return ""
        return original(*args)

    monkeypatch.setattr(module, "_git", patched)


def test_regression_smoke_protocol_stays_narrow(monkeypatch) -> None:
    _allow_dirty_test_build(monkeypatch, regression_freeze)
    protocol = regression_freeze.build_protocol()

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


def test_phase_transition_smoke_extends_only_the_regression_horizon(
    monkeypatch,
) -> None:
    _allow_dirty_test_build(monkeypatch, phase_freeze)
    protocol = phase_freeze.build_protocol()

    assert protocol["workload"]["max_steps"] == 100
    assert protocol["design"]["maximum_steps_extended_from"] == 80
    assert protocol["design"]["required_next_semantic_phase"] == "move"
    assert protocol["gates"][
        "minimum_complete_move_transaction_count"
    ] == 1
    assert protocol["gates"]["minimum_move_effect_allow_count"] == 1
    assert protocol["execution_authorization"][
        "clean_efficacy_rollout"
    ] is False
    assert protocol["execution_authorization"][
        "attacked_rollout"
    ] is False
