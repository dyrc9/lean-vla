from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.semantic_local_checker import (
    EntityPosition,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)
from scripts.run_l2_execution_attack_eval_v3 import (
    OnlineProgressProjectionCandidatePolicy,
)


def _policy(
    actions: np.ndarray,
    *,
    subtask: str,
    observation: TrustedLocalObservation,
    release_destination: str | None = None,
) -> OnlineProgressProjectionCandidatePolicy:
    class Inner:
        @staticmethod
        def infer(element):
            del element
            return {"actions": actions.copy()}

    policy = OnlineProgressProjectionCandidatePolicy(
        Inner(),
        candidate_count=1,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        checker=SemanticExecutablePrefixChecker(),
        min_progress_margin=0.002,
        max_projection_l2=0.5,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            artifact_digest="a" * 64,
            selected_subtask=subtask,
        ),
        local_observation=observation,
        context=SimpleNamespace(state_epoch=observation.state_epoch),
        release_destination=release_destination,
    )
    return policy


def test_online_policy_projects_supported_fixed_subtask() -> None:
    observation = TrustedLocalObservation(
        state_epoch=3,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target", (0.1, 0.0, 0.5)),
        ),
    )
    policy = _policy(
        np.zeros((10, 7), dtype=np.float64),
        subtask="pick_up(target)",
        observation=observation,
    )

    result = policy.infer({})
    audit = policy.audits[-1]

    assert audit["fixed_semantic_subtask"] == "pick_up(target)"
    assert audit["eligible_selected_source_candidate_index"] == 0
    assert audit["selection_reason"] == (
        "online_progress_projection_eligible"
    )
    assert audit["candidates"][0]["progress_projection"]["schema"] == (
        "proofalign.semantic-progress-projection.v1"
    )
    assert np.all(result["actions"][:, 0] > 0)
    assert np.all(result["actions"][:, 1:] == 0)


def test_online_policy_allows_only_nominally_valid_release_bypass() -> None:
    observation = TrustedLocalObservation(
        state_epoch=4,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(-0.01, -0.01),
        entity_positions=(
            EntityPosition("target", (0.0, 0.0, 0.5)),
            EntityPosition("destination", (0.0, 0.0, 0.5)),
        ),
    )
    actions = np.zeros((10, 7), dtype=np.float64)
    actions[:, 6] = -1.0
    policy = _policy(
        actions,
        subtask="release(target)",
        observation=observation,
        release_destination="destination",
    )

    result = policy.infer({})
    audit = policy.audits[-1]
    projection = audit["candidates"][0]["progress_projection"]

    assert audit["eligible_selected_source_candidate_index"] == 0
    assert audit["selection_reason"] == "nominal_checker_bypass_eligible"
    assert projection["schema"] == (
        "proofalign.semantic-progress-projection-bypass.v1"
    )
    assert projection["reason"] == (
        "nominal_checker_eligible_without_projection:release"
    )
    assert np.array_equal(result["actions"], actions)


def test_online_policy_rejects_invalid_release_without_projection() -> None:
    observation = TrustedLocalObservation(
        state_epoch=5,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(-0.01, -0.01),
        entity_positions=(
            EntityPosition("target", (0.0, 0.0, 0.5)),
            EntityPosition("destination", (0.0, 0.0, 0.5)),
        ),
    )
    actions = np.zeros((10, 7), dtype=np.float64)
    actions[:, 6] = 1.0
    policy = _policy(
        actions,
        subtask="release(target)",
        observation=observation,
        release_destination="destination",
    )

    result = policy.infer({})
    audit = policy.audits[-1]
    projection = audit["candidates"][0]["progress_projection"]

    assert audit["eligible_selected_source_candidate_index"] is None
    assert audit["fallback_for_fail_closed_recheck"]
    assert projection["reason"] == (
        "nominal_hard_violation_rejected_before_projection"
    )
    assert "release_command_missing" in audit["candidates"][0][
        "nominal_checked"
    ]["hard_violation_atoms"]
    assert np.array_equal(result["actions"], actions)


def test_online_policy_rejects_hard_violation_before_projection() -> None:
    observation = TrustedLocalObservation(
        state_epoch=6,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target", (0.1, 0.0, 0.5)),
        ),
    )
    actions = np.zeros((10, 7), dtype=np.float64)
    actions[0, 0] = 2.0
    policy = _policy(
        actions,
        subtask="pick_up(target)",
        observation=observation,
    )

    policy.infer({})
    audit = policy.audits[-1]
    projection = audit["candidates"][0]["progress_projection"]

    assert audit["eligible_selected_source_candidate_index"] is None
    assert projection["reason"] == (
        "nominal_hard_violation_rejected_before_projection"
    )
