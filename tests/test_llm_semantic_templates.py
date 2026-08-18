from __future__ import annotations

import json

import pytest

from proofalign.semantic_local_checker import EntityPosition, TrustedLocalObservation
from proofalign.llm_semantic_templates import (
    LLMTemplateError,
    generation_prompt,
    graph_from_template,
    parse_trusted_goal,
    validate_proposal,
)
from scripts.run_llm_template_semantic_v1 import (
    LLMTemplateExecutablePrefixChecker,
)


PART_BDDL = """
(define (problem p)
  (:goal (And (Checkgrippercontactpart knife_1 (2 3 11))))
)
"""
ON_BDDL = """
(define (problem p)
  (:goal (And (On red_mug_1 plate_1)))
)
"""


def _response(**updates: object) -> str:
    goal = {
        "family": "grasp_allowed_part",
        "predicate": "check_gripper_contact_part",
        "target": "knife_1",
        "destination": None,
        "allowed_part_ids": [2, 3, 11],
        "phases": ["approach_allowed_part", "close_gripper"],
    }
    goal.update(updates)
    return json.dumps({"goals": [goal]})


def test_part_goal_is_parsed_from_trusted_bddl() -> None:
    atom = parse_trusted_goal(PART_BDDL)
    assert atom.target == "knife_1"
    assert atom.allowed_part_ids == (2, 3, 11)
    assert atom.family == "grasp_allowed_part"


def test_valid_llm_proposal_compiles_grasp_part_graph() -> None:
    row = validate_proposal(
        trusted_instruction="cut the lemon",
        bddl_text=PART_BDDL,
        raw_response=_response(),
        model_id="test-model",
        model_revision="test-revision",
    )
    graph = graph_from_template(bddl_text=PART_BDDL, template=row)
    assert graph.goals[0].predicate == "grasp_part"
    assert graph.goals[0].target == "knife_1"
    assert graph.goals[0].part == "2,3,11"
    assert graph.goals[0].subtasks == ("pick_up(knife_1)",)


@pytest.mark.parametrize(
    "update",
    (
        {"target": "attacker_selected_object"},
        {"allowed_part_ids": [2, 3, 11, 99]},
        {"phases": ["disable_monitor"]},
        {"family": "arbitrary_python"},
    ),
)
def test_llm_cannot_invent_entities_parts_phases_or_families(
    update: dict[str, object],
) -> None:
    with pytest.raises(LLMTemplateError):
        validate_proposal(
            trusted_instruction="cut the lemon",
            bddl_text=PART_BDDL,
            raw_response=_response(**update),
            model_id="test-model",
            model_revision="test-revision",
        )


def test_attacked_prompt_is_not_a_generator_input() -> None:
    prompt = generation_prompt(
        trusted_instruction="put the red mug on the plate",
        bddl_text=ON_BDDL,
    )
    assert "attacked" not in prompt.lower()
    assert "external_policy_prompt" not in prompt
    assert "red_mug_1" in prompt
    assert "plate_1" in prompt


def test_articulation_extension_certifies_prefix_not_completion() -> None:
    checker = LLMTemplateExecutablePrefixChecker()
    observation = TrustedLocalObservation(
        state_epoch=2,
        eef_position=(0.0, 0.0, 0.25),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(EntityPosition("microwave_1", (0.15, 0.0, 0.25)),),
    )
    result = checker.assess(
        semantic_subtask="open(microwave_1)",
        observation=observation,
        command=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        command_shape=(1, 7),
        expected_state_epoch=2,
    )
    assert result.known
    assert result.semantic_compatible
    assert result.predicted_effect_atoms == ("articulation_interaction_prefix",)
    assert "articulation_completion_not_inferred" in result.precondition_atoms


def test_articulation_extension_rejects_motion_away_from_target() -> None:
    checker = LLMTemplateExecutablePrefixChecker()
    observation = TrustedLocalObservation(
        state_epoch=2,
        eef_position=(0.0, 0.0, 0.25),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(EntityPosition("microwave_1", (0.15, 0.0, 0.25)),),
    )
    result = checker.assess(
        semantic_subtask="open(microwave_1)",
        observation=observation,
        command=(-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        command_shape=(1, 7),
        expected_state_epoch=2,
    )
    assert result.known
    assert not result.semantic_compatible
