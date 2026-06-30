from __future__ import annotations

from proofalign.action_abstraction import action_from_dict
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent


def test_safe_pick_action_passes_intent_alignment(safe_state, safe_spec):
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert result.passed
    assert result.suggested_decision.value == "allow"


def test_wrong_object_is_rejected(safe_state, safe_spec):
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "knife", "part": "handle"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "reject"
    assert any("expected object mug" in violation for violation in result.violations)


def test_wrong_grasp_part_is_rejected(safe_state, safe_spec):
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "rim"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "reject"
    assert any("expected part handle" in violation for violation in result.violations)


def test_action_toward_avoided_hand_is_rejected(safe_state, safe_spec):
    intent = parse_intent("place the mug on the plate while avoiding the human hand")
    action = action_from_dict({"type": "Pick", "object": "human_hand", "part": "palm"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "reject"
