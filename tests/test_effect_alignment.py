from __future__ import annotations

from proofalign.action_abstraction import action_from_dict
from proofalign.checker import DualAlignmentChecker
from proofalign.simulator import DiscreteSimulator


def test_pick_effect_requires_object_held(safe_state, safe_spec):
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle", "fail_grasp": True})
    before = safe_state
    after = DiscreteSimulator().execute(before, action)

    result = DualAlignmentChecker().check_effect_alignment(before, action, after, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "replan"
    assert any("not held by gripper" in violation for violation in result.violations)


def test_collision_triggers_safe_stop(safe_state, safe_spec):
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle", "collision": True})
    before = safe_state
    after = DiscreteSimulator().execute(before, action)

    result = DualAlignmentChecker().check_effect_alignment(before, action, after, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "safe_stop"
    assert any("collision" in violation for violation in result.violations)


def test_human_hand_proximity_triggers_replan(safe_state, safe_spec):
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle", "human_hand_distance": 0.05})
    before = safe_state
    after = DiscreteSimulator().execute(before, action)

    result = DualAlignmentChecker().check_effect_alignment(before, action, after, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "replan"
    assert any("human hand distance" in violation for violation in result.violations)
