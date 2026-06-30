from __future__ import annotations

from dataclasses import dataclass

import pytest

from proofalign.benchmark.libero_online_wrapper import (
    DefaultLiberoActionAbstractor,
    LiberoOnlineIntegrationError,
    ProofAlignLiberoWrapper,
    env_action_from_raw,
)
from proofalign.models import Decision, SafetySpec, WorldState


@dataclass
class FakeObjectModel:
    category_name: str
    root_body: str
    contact_geoms: list[str]


class FakeSimData:
    def __init__(self) -> None:
        self.body_xpos = [[0.2, 0.1, 0.0], [0.6, 0.1, 0.0]]
        self.site_xpos = [[0.0, 0.0, 0.0]]


class FakeSim:
    def __init__(self) -> None:
        self.data = FakeSimData()


class FakeLiberoEnv:
    def __init__(self) -> None:
        self.sim = FakeSim()
        self.objects_dict = {
            "mug": FakeObjectModel("mug", "mug_main", ["mug_g0"]),
            "knife": FakeObjectModel("knife", "knife_main", ["knife_g0"]),
        }
        self.fixtures_dict = {}
        self.object_sites_dict = {}
        self.obj_body_id = {"mug": 0, "knife": 1}
        self.held_object = None
        self.step_count = 0
        self.last_env_action = None

    def reset(self):
        self.held_object = None
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}

    def step(self, action):
        self.step_count += 1
        self.last_env_action = action
        self.held_object = "mug"
        return {"robot0_eef_pos": [0.2, 0.1, 0.0]}, 1.0, False, {"cost": {}}


def test_online_wrapper_blocks_intent_failure_before_env_step():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step({"proofalign_action": {"type": "Pick", "object": "knife", "part": "blade"}})

    assert result.decision == Decision.REJECT
    assert result.done is True
    assert env.step_count == 0
    assert result.info["proofalign_layer"] == "intent"


def test_online_wrapper_executes_raw_action_and_checks_effect():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step(
        {
            "raw_action": [0.1, 0.0, 0.0, 1.0],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision == Decision.ALLOW
    assert result.reward == 1.0
    assert env.step_count == 1
    assert env.last_env_action == [0.1, 0.0, 0.0, 1.0]
    assert result.step.effect_result and result.step.effect_result.passed


def test_default_abstractor_requires_symbolic_contract_for_continuous_action():
    abstractor = DefaultLiberoActionAbstractor()

    with pytest.raises(LiberoOnlineIntegrationError):
        abstractor.abstract(
            [0.1, 0.0, 0.0, 1.0],
            instruction="pick up the mug by the handle",
            observation={},
            state=WorldState(),
            spec=SafetySpec.from_dict({}),
            history=[],
        )


def test_raw_env_action_is_separated_from_symbolic_metadata():
    assert env_action_from_raw({"raw_action": [1, 2, 3], "proofalign_action": {"type": "Stop"}}) == [1, 2, 3]
    assert env_action_from_raw([1, 2, 3]) == [1, 2, 3]
