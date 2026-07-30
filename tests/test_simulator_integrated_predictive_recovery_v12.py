from __future__ import annotations

import numpy as np

from scripts.run_simulator_integrated_predictive_recovery_v12_pilot import (
    ContactCapacityAudit,
    SimulatorRecoverySink,
    _set_init_state_without_outcome,
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
    assert (
        config["execution_boundary"]["set_init_state_wrapper_authorized"]
        is False
    )


def test_direct_state_restore_does_not_query_task_success() -> None:
    calls: list[object] = []

    class Data:
        time = 9

    class Sim:
        data = Data()

        def forward(self) -> None:
            calls.append("forward")

    class Env:
        sim = Sim()

        def set_state(self, state: object) -> None:
            calls.append(("set_state", state))

        def check_success(self) -> None:
            raise AssertionError("outcome query must not be called")

        def set_init_state(self, state: object) -> None:
            raise AssertionError("outcome-querying wrapper must not be called")

        def _post_process(self) -> None:
            calls.append("post_process")

        def _update_observables(self, *, force: bool) -> None:
            calls.append(("update_observables", force))

    state = object()
    env = Env()

    _set_init_state_without_outcome(env, state)

    assert env.sim.data.time == 0
    assert calls == [
        ("set_state", state),
        "forward",
        "post_process",
        ("update_observables", True),
    ]


def test_contact_capacity_audit_counts_saturation() -> None:
    class Data:
        ncon = 7

    class Model:
        nconmax = 8

    class Sim:
        data = Data()
        model = Model()

    class Env:
        sim = Sim()

    env = Env()
    audit = ContactCapacityAudit()
    audit.observe(env)
    env.sim.data.ncon = 8
    audit.observe(env)

    assert audit.observation_count == 2
    assert audit.maximum_ncon == 8
    assert audit.minimum_nconmax == 8
    assert audit.saturation_count == 1
