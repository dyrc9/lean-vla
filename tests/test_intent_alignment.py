from __future__ import annotations

from proofalign.action_abstraction import action_from_dict
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import SafetySpec


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


def test_place_parser_ignores_avoid_object_as_target():
    intent = parse_intent("place the mug on the plate while avoiding the human hand")

    assert intent.verb == "place"
    assert intent.target_object == "mug"
    assert intent.target_region == "plate"
    assert intent.avoid_objects == ["human_hand"]


def test_cut_food_with_knife_is_not_rejected_as_dangerous_instruction(safe_state, safe_spec):
    intent = parse_intent("grab the knife and cut the lemon on the cutting board")
    action = action_from_dict({"type": "MoveTo", "object": "knife", "pose": {"x": 0, "y": 0, "z": 0}})
    spec = SafetySpec(
        safety_margin=safe_spec.safety_margin,
        protected_objects=list(safe_spec.protected_objects),
        forbidden_objects=[],
        forbidden_parts=list(safe_spec.forbidden_parts),
    )

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, spec)

    assert intent.verb == "pick"
    assert intent.target_object == "knife"
    assert intent.target_part == "handle"
    assert result.passed


def test_cut_human_hand_is_rejected_as_dangerous_instruction(safe_state, safe_spec):
    intent = parse_intent("cut the human hand with the knife")
    action = action_from_dict({"type": "MoveTo", "object": "knife", "pose": {"x": 0, "y": 0, "z": 0}})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert intent.reject_required
    assert not result.passed


def test_multiword_object_place_instruction_aligns_with_resolved_object(safe_state, safe_spec):
    intent = parse_intent("pick up the akita black bowl on the stove and place it on the plate")
    action = action_from_dict({"type": "MoveTo", "object": "akita_black_bowl_1", "region": "plate"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert intent.verb == "place"
    assert intent.target_object == "akita_black_bowl"
    assert intent.target_region == "plate"
    assert result.passed


def test_bring_instruction_aligns_with_target_region(safe_state, safe_spec):
    intent = parse_intent("pick the akita black bowl next to the cookies box and bring it for me")
    action = action_from_dict({"type": "MoveTo", "object": "akita_black_bowl_1", "region": "target_region"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, safe_spec)

    assert intent.verb == "place"
    assert intent.target_object == "akita_black_bowl"
    assert intent.target_region == "target_region"
    assert result.passed
