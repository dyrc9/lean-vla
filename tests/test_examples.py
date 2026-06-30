from __future__ import annotations

import json
from pathlib import Path

from proofalign.executor import SafetyExecutor
from proofalign.models import SafetySpec, WorldState


ROOT = Path(__file__).resolve().parents[1]


def test_all_json_examples_match_expected_decisions():
    for path in sorted((ROOT / "examples" / "tasks").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        decision = SafetyExecutor().run(
            data["instruction"],
            WorldState.from_dict(data["initial_state"]),
            SafetySpec.from_dict(data.get("safety_spec")),
            data["candidate_actions"],
        )

        assert decision.decision.value == data["expected_decision"], path.name


def test_dangerous_instruction_is_rejected_before_execution():
    data = json.loads((ROOT / "examples" / "tasks" / "ssr_dangerous_instruction.json").read_text(encoding="utf-8"))
    decision = SafetyExecutor().run(
        data["instruction"],
        WorldState.from_dict(data["initial_state"]),
        SafetySpec.from_dict(data.get("safety_spec")),
        data["candidate_actions"],
    )

    assert decision.decision.value == "reject"
    assert len(decision.trace) == 1
    assert decision.trace[0].effect_result is None
