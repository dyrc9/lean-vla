from __future__ import annotations

from proofalign.action_abstraction import action_from_dict
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.simulator import DiscreteSimulator


def test_dual_alignment_allows_safe_pick(safe_state, safe_spec):
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    before = safe_state
    after = DiscreteSimulator().execute(before, action)

    result = DualAlignmentChecker().check_dual_alignment(intent, before, action, after, safe_spec)

    assert result.passed
    assert result.suggested_decision.value == "allow"


def test_dual_alignment_rejects_intent_failure_before_effect(safe_state, safe_spec):
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "knife", "part": "blade"})
    before = safe_state
    after = DiscreteSimulator().execute(before, action)

    result = DualAlignmentChecker().check_dual_alignment(intent, before, action, after, safe_spec)

    assert not result.passed
    assert result.suggested_decision.value == "reject"
    assert result.layer == "dual"
