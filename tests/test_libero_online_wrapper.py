from __future__ import annotations

from dataclasses import dataclass

import pytest

from proofalign.benchmark.libero_online_wrapper import (
    DefaultLiberoActionAbstractor,
    LiberoOnlineIntegrationError,
    ProofAlignLiberoWrapper,
    env_action_from_raw,
)
from proofalign.checker import _lean_trace_summary
from proofalign.models import Decision, SafetySpec, TraceSummary, WorldState


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
    def __init__(self, *, hold_on_step: bool = True, collision: bool = False, cost: dict | None = None) -> None:
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
        self.hold_on_step = hold_on_step
        self.collision = collision
        self.cost = cost if cost is not None else {}

    def reset(self):
        self.held_object = None
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}

    def step(self, action):
        self.step_count += 1
        self.last_env_action = action
        if self.hold_on_step:
            self.held_object = "mug"
        return {"robot0_eef_pos": [0.2, 0.1, 0.0]}, 1.0, False, {"cost": dict(self.cost), "collision": self.collision}


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


def test_chunk_allow_path_accumulates_trace_summary():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0], [0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        },
        max_chunk_steps=2,
        chunk_id="test_chunk",
    )

    assert result.decision == Decision.ALLOW
    assert env.step_count == 1
    assert result.step.chunk_id == "test_chunk"
    assert result.step.trace_summary
    assert result.step.trace_summary.num_raw_steps == 1
    assert result.step.trace_summary.object_became_held is True
    assert result.step.raw_actions == [[0.1, 0.0, 0.0, 0.0]]


def test_chunk_intent_reject_prevents_env_step():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "knife", "part": "blade"},
        },
        max_chunk_steps=2,
    )

    assert result.decision == Decision.REJECT
    assert env.step_count == 0
    assert result.step.trace_summary
    assert result.step.trace_summary.num_raw_steps == 0


def test_chunk_collision_or_cost_triggers_safe_stop():
    env = FakeLiberoEnv(collision=True, cost={"collision": 1})
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision == Decision.SAFE_STOP
    assert env.step_count == 1
    assert result.step.trace_summary
    assert result.step.trace_summary.collision is True
    assert result.step.trace_summary.cost_observed is True


def test_chunk_pick_postcondition_miss_triggers_replan():
    env = FakeLiberoEnv(hold_on_step=False)
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0], [0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        },
        max_chunk_steps=2,
    )

    assert result.decision == Decision.REPLAN
    assert env.step_count == 2
    assert result.step.effect_result
    assert "pick chunk postcondition failed" in result.step.effect_result.explanation


def test_lean_expression_builds_for_trace_summary():
    summary = TraceSummary(
        num_raw_steps=8,
        collision=False,
        cost={"collision": 0},
        cost_observed=False,
        min_human_hand_distance=0.31,
        min_obstacle_distance=0.27,
        moved_objects=["mug"],
        object_became_held=True,
    )

    expression = _lean_trace_summary(summary)

    assert "numSteps := 8" in expression
    assert "minHumanHandDistance := 31" in expression
    assert 'movedObjects := ["mug"]' in expression


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
