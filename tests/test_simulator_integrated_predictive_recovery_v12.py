from __future__ import annotations

import numpy as np

from scripts.run_simulator_integrated_predictive_recovery_v12_pilot import (
    SimulatorRecoverySink,
    pilot_config,
)


def test_simulator_recovery_sink_applies_exact_action() -> None:
    calls: list[np.ndarray] = []

    class Env:
        def step(self, action: np.ndarray):
            calls.append(action.copy())
            return ({"ignored": True}, 123.0, True, {"success": True})

    sink = SimulatorRecoverySink(Env())
    action = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)

    applied = sink.apply_recovery(action, now_ns=10)

    assert applied.action == action
    assert sink.apply_count == 1
    assert np.array_equal(calls[0], np.asarray(action))


def test_pilot_population_is_new_and_no_outcome() -> None:
    config = pilot_config()

    assert config["population"]["pair_count"] == 3
    assert {
        row["base_pair_id"]
        for row in config["population"]["pairs"]
    } == {
        "obstacle_avoidance_task11_init44",
        "human_safety_task11_init43",
        "obstacle_avoidance_human_task11_init24",
    }
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
