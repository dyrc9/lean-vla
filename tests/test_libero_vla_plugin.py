from __future__ import annotations

from dataclasses import dataclass

from experiments.libero_vla_plugin import (
    LiberoVLAActionAbstractor,
    extract_proprio,
    heuristic_contract_from_instruction,
    make_oft_observation,
)
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import ActionKind, Object, ObjectPart, Pose, SafetySpec, WorldState


def test_heuristic_contract_marks_dangerous_instruction_reject():
    contract = heuristic_contract_from_instruction("stab the hand with the knife")

    assert contract["type"] == "Reject"


def test_vla_abstractor_resolves_object_and_emits_intermediate_move():
    state = WorldState(
        objects={
            "akita_black_bowl_1": Object(
                "akita_black_bowl_1",
                "bowl",
                Pose(0.4, 0.0, 0.0),
                {"body": ObjectPart("body")},
            )
        },
        robot_pose=Pose(0.0, 0.0, 0.0),
    )
    abstractor = LiberoVLAActionAbstractor()

    action = abstractor.abstract(
        {"raw_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]},
        instruction="pick up the bowl",
        observation={},
        state=state,
        spec=SafetySpec.from_dict({}),
        history=[],
    )

    assert action.kind == ActionKind.MOVE_TO
    assert action.object_id == "akita_black_bowl_1"


def test_pick_intent_allows_vla_intermediate_move_to_target():
    state = WorldState(
        objects={"mug": Object("mug", "mug", Pose(0.2, 0.0, 0.0), {"body": ObjectPart("body")})}
    )
    abstractor = LiberoVLAActionAbstractor()
    action = abstractor.abstract(
        {"proofalign_action": {"type": "Pick", "object": "mug", "part": "body"}, "raw_action": [0, 0, 0, 0, 0, 0, 0]},
        instruction="pick up the mug",
        observation={},
        state=state,
        spec=SafetySpec.from_dict({}),
        history=[],
    )

    result = DualAlignmentChecker().check_intent_alignment(
        parse_intent("pick up the mug"),
        state,
        action,
        SafetySpec.from_dict({}),
    )

    assert result.passed


def test_oft_observation_extracts_images_and_padded_proprio():
    observation = {
        "agentview_image": [[[0, 0, 0]]],
        "robot0_eye_in_hand_image": [[[1, 1, 1]]],
        "robot0_eef_pos": [0.1, 0.2, 0.3],
        "robot0_gripper_qpos": [0.4],
    }

    obs = make_oft_observation(
        observation,
        "pick up the mug",
        image_key=None,
        wrist_image_key=None,
        state_key=None,
        proprio_dim=8,
    )

    assert obs["task_description"] == "pick up the mug"
    assert obs["full_image"].shape == (1, 1, 3)
    assert obs["wrist_image"].shape == (1, 1, 3)
    assert obs["state"].tolist() == [0.1, 0.2, 0.3, 0.4, 0.0, 0.0, 0.0, 0.0]


def test_extract_proprio_uses_explicit_state_key_first():
    observation = {"state": [1, 2], "robot0_eef_pos": [3, 4, 5]}

    assert extract_proprio(observation, "state", 4) == [1.0, 2.0, 3.0, 4.0]
