from __future__ import annotations

from proofalign.benchmark.libero_online_wrapper import LiberoStateObserver
from proofalign.benchmark.libero_postdispatch_oracle import (
    ORACLE_INFO_KEY,
    FrozenPostDispatchObservationBlackout,
)


class _ConstraintEnv:
    def __init__(self) -> None:
        self.cost = {}
        self.actions: list[list[float]] = []

    def step(self, action):
        self.actions.append(list(action))
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}, 0.0, False, {"cost": {}}

    def _check_constraint(self, done):
        assert done is False
        return dict(self.cost)


class _OuterEnv:
    def __init__(self, env) -> None:
        self.env = env

    def step(self, action):
        return self.env.step(action)


def _unknown(state) -> set[str]:
    return {
        note.removeprefix("ctda_unknown_observation:")
        for note in state.notes
        if note.startswith("ctda_unknown_observation:")
    }


def test_first_real_step_is_oracle_attested_then_hidden_for_one_observation() -> None:
    base = _ConstraintEnv()
    env = FrozenPostDispatchObservationBlackout(base, intervention_id="frozen-i1")
    observation, _reward, _done, info = env.step([0.1, 0.0, 0.0, 0.0])

    assert "cost" not in info
    assert info[ORACLE_INFO_KEY]["role"] == "post_policy_dispatch_observation_blackout"
    assert info[ORACLE_INFO_KEY]["observation_complete"] is True
    assert info[ORACLE_INFO_KEY]["positive_cost"] is False
    state = LiberoStateObserver().observe(env, observation, info)
    assert {"collision", "cost"}.issubset(_unknown(state))


def test_second_real_step_restores_simulator_safety_observation() -> None:
    base = _ConstraintEnv()
    env = FrozenPostDispatchObservationBlackout(base, intervention_id="frozen-i1")
    env.step([0.1, 0.0, 0.0, 0.0])
    observation, _reward, _done, info = env.step([0.0, 0.0, 0.0, 0.0])

    assert info["cost"] == {}
    assert info[ORACLE_INFO_KEY]["role"] == "restored_post_intervention_observation"
    assert info[ORACLE_INFO_KEY]["env_step_index"] == 2
    state = LiberoStateObserver().observe(env, observation, info)
    assert "collision" not in _unknown(state)
    assert "cost" not in _unknown(state)


def test_oracle_retains_positive_base_signal_without_fabricating_it() -> None:
    base = _ConstraintEnv()
    base.cost = {"checkcontact": 1}
    env = FrozenPostDispatchObservationBlackout(base, intervention_id="frozen-i1")
    _observation, _reward, _done, info = env.step([0.1, 0.0, 0.0, 0.0])

    oracle = info[ORACLE_INFO_KEY]
    assert oracle["positive_cost"] is True
    assert oracle["collision"] is True
    assert oracle["manufactures_collision_or_cost"] is False


def test_normal_unwrap_is_available_before_fault_and_restored_after_fallback() -> None:
    raw = _ConstraintEnv()
    env = FrozenPostDispatchObservationBlackout(
        _OuterEnv(raw), intervention_id="frozen-i1"
    )

    initial = LiberoStateObserver().observe(env)
    assert "collision" not in _unknown(initial)
    assert "cost" not in _unknown(initial)

    observation, _reward, _done, info = env.step([0.1, 0.0, 0.0, 0.0])
    blacked_out = LiberoStateObserver().observe(env, observation, info)
    assert {"collision", "cost"}.issubset(_unknown(blacked_out))

    observation, _reward, _done, info = env.step([0.0, 0.0, 0.0, 0.0])
    restored = LiberoStateObserver().observe(env, observation, info)
    assert "collision" not in _unknown(restored)
    assert "cost" not in _unknown(restored)
