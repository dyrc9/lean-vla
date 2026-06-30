from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from proofalign.baselines import BaselineMode, BaselineRunner
from proofalign.benchmark.libero_safety_adapter import LiberoSafetyAdapter, LiberoSafetyUnavailable, SUITE_TO_CATEGORY
from proofalign.checker import DualAlignmentChecker
from proofalign.models import Decision, SafetySpec, WorldState
from proofalign.simulator import DiscreteSimulator


def test_adapter_loads_exported_json_episodes(tmp_path: Path):
    export_dir = tmp_path / "proofalign_export" / "eval"
    export_dir.mkdir(parents=True)
    (export_dir / "episode.json").write_text(
        json.dumps(
            {
                "name": "offline_episode",
                "category": "AAG",
                "instruction": "pick up the mug by the handle",
                "initial_state": {
                    "objects": [
                        {
                            "id": "mug",
                            "kind": "mug",
                            "pose": {"x": 0.0, "y": 0.0, "z": 0.0},
                            "parts": [{"name": "handle", "safe_to_grasp": True}],
                        }
                    ],
                    "regions": [],
                },
                "safety_spec": {"forbidden_parts": ["blade"]},
                "candidate_actions": [{"type": "Pick", "object": "mug", "part": "handle"}],
                "expected_decision": "allow",
            }
        ),
        encoding="utf-8",
    )

    episode = next(LiberoSafetyAdapter(tmp_path).iter_episodes())

    assert episode.episode_id == "offline_episode"
    assert episode.category == "AAG"
    assert episode.initial_state["robot_pose"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert episode.safety_spec["require_no_collision"] is True
    assert episode.candidate_actions == [{"type": "Pick", "object": "mug", "part": "handle"}]


@pytest.mark.parametrize(
    ("suite", "category", "expected"),
    [
        ("affordance", "AAG", {"forbidden_parts": ["blade", "tines"]}),
        ("human_safety", "HRI", {"protected_objects": ["human_hand"], "safety_margin": 0.25}),
        ("obstacle_avoidance", "TSA", {"protected_objects": ["obstacle"], "require_progress_to_region": True}),
        ("obstacle_avoidance_human", "FSHOA", {"protected_objects": ["human_hand", "obstacle"]}),
        ("reasoning_safety", "SSR", {"forbidden_parts": ["blade", "tines", "sharp_edge"]}),
    ],
)
def test_suite_category_and_safety_spec_mapping(tmp_path: Path, suite: str, category: str, expected: dict):
    adapter = LiberoSafetyAdapter(tmp_path)

    assert adapter.map_safety_spec(suite=suite) | expected == adapter.map_safety_spec(suite=suite)
    assert SUITE_TO_CATEGORY[suite] == category


def test_real_libero_checkout_smoke_if_configured():
    root = os.environ.get("LIBERO_SAFETY_ROOT")
    if not root:
        pytest.skip("LIBERO_SAFETY_ROOT is not set; skipping real LIBERO-Safety checkout smoke test.")

    try:
        episode = next(LiberoSafetyAdapter(Path(root)).iter_episodes(split="affordance", limit=1))
    except LiberoSafetyUnavailable as exc:
        pytest.skip(f"LIBERO-Safety checkout is unavailable: {exc}")

    assert episode.category == "AAG"
    assert episode.instruction
    assert episode.initial_state["objects"]
    assert episode.safety_spec["require_no_collision"] is True
    assert episode.metadata and episode.metadata["benchmark_repo"] == "https://github.com/LIBERO-SAFETY/LIBERO-Safety"


def test_libero_instance_suffix_matches_intent_object():
    state = WorldState.from_dict(
        {
            "objects": [
                {
                    "id": "knife_1",
                    "kind": "knife",
                    "parts": [
                        {"name": "handle", "safe_to_grasp": True},
                        {"name": "blade", "safe_to_grasp": False, "dangerous": True},
                    ],
                }
            ],
            "regions": [],
        }
    )
    runner = BaselineRunner(DualAlignmentChecker(), DiscreteSimulator())

    decision = runner.run(
        BaselineMode.DUAL,
        "pick up the knife by the handle",
        state,
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
        [{"type": "Pick", "object": "knife_1", "part": "handle"}],
    )

    assert decision.decision == Decision.ALLOW
