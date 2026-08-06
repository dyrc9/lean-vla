from __future__ import annotations

from scripts.run_simulator_recovery_bounded_replan_pilot_v12 import (
    FORMAL_PAIR_INDEX,
    MAX_REPLAN_ATTEMPTS,
    pilot_config,
)


def test_bounded_replan_reproduces_formal_seed_schedule() -> None:
    config = pilot_config()

    assert MAX_REPLAN_ATTEMPTS == 8
    assert (
        config["episode"]["post_recovery_replan_attempts"]
        == MAX_REPLAN_ATTEMPTS
    )
    assert set(FORMAL_PAIR_INDEX.values()) == {2, 4, 8}
    assert config["population"]["policy_seed_base"] == 401
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
