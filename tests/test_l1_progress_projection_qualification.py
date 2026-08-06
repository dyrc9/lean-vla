from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from proofalign.semantic_local_checker import (
    EntityPosition,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)
from scripts.run_four_arm_v4_l1_progress_projection_qualification import (
    ProgressProjectionCandidatePolicy,
    ProgressProjectionQualificationError,
    _validate_design,
    build_summary,
)


def _protocol() -> dict:
    pairs = [
        {
            "base_pair_id": f"suite_{index}",
            "suite": f"suite_{index // 15}",
        }
        for index in range(45)
    ]
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-progress-projection-"
            "qualification-protocol.v1"
        ),
        "protocol_id": "progress-projection-fixture",
        "execution_authorization": {
            "qualification_probe": True,
            "task_outcome_rollout": False,
            "clean_rollout": False,
            "attacked_rollout": False,
        },
        "repair": {
            "semantic_candidate_count": 1,
            "replan_steps": 10,
            "checked_action_block_steps": 10,
            "min_progress_m": 0.002,
            "threshold_changed": False,
            "semantic_progress_projection": {
                "enabled": True,
                "max_projection_l2": 0.05,
                "min_terminal_progress_m": 0.002,
                "preserve_rotation_and_gripper": True,
                "reject_nominal_hard_violations": True,
                "supported_verbs": ["pick_up", "move", "place"],
                "translation_only": True,
            },
        },
        "qualification_population": {
            "frozen_pairs": pairs,
            "base_pair_count": 45,
            "environment_seed": 109,
            "policy_seed": 41,
            "policy_inference_count": 45,
            "policy_conditioned_env_step_count": 0,
        },
        "qualification_gates": {
            "geometry_ready_rate_min": 1.0,
            "eligible_candidate_rate_min": 0.9,
            "worst_suite_eligible_rate_min": 0.8,
            "selected_hard_violation_count_max": 0,
        },
    }


def _rows(eligible: int) -> list[dict]:
    return [
        {
            **pair,
            "valid": True,
            "known": True,
            "geometry_audit": {"unresolved_counts": {}},
            "eligible_candidate_selected": index < eligible,
            "selected_hard_violation_count": 0,
            "policy_conditioned_env_step_count": 0,
            "dispatch_count": 0,
            "task_outcome_observed": False,
            "candidate_selection": {
                "candidates": [
                    {
                        "progress_projection": {
                            "accepted": index < eligible,
                            "projected": index < eligible,
                            "reason": (
                                "minimum_l2_terminal_progress_projection"
                                if index < eligible
                                else "semantic_projection_budget_exceeded"
                            ),
                            "projection_l2": (
                                0.01 if index < eligible else None
                            ),
                        }
                    }
                ]
            },
        }
        for index, pair in enumerate(
            _protocol()["qualification_population"]["frozen_pairs"]
        )
    ]


def test_progress_projection_design_is_exact() -> None:
    _validate_design(_protocol())


def test_progress_projection_design_rejects_threshold_change() -> None:
    protocol = _protocol()
    protocol["repair"]["min_progress_m"] = 0.001

    with pytest.raises(ProgressProjectionQualificationError):
        _validate_design(protocol)


def test_progress_projection_summary_is_versioned() -> None:
    summary = build_summary(_protocol(), _rows(eligible=42))

    assert summary["qualification_pass"]
    assert summary["classification"] == (
        "l1_progress_projection_initial_availability_qualification_pass"
    )
    assert summary["projection_attempt_count"] == 45
    assert summary["projection_accepted_count"] == 42
    assert summary["projection_applied_count"] == 42
    assert summary["maximum_accepted_projection_l2"] == 0.01


def test_candidate_policy_repairs_only_translation_and_rechecks() -> None:
    calls = 0

    class Inner:
        def infer(self, element):
            nonlocal calls
            del element
            calls += 1
            return {"actions": np.zeros((10, 7), dtype=np.float64)}

    observation = TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target", (0.1, 0.0, 0.5)),
        ),
    )
    checker = SemanticExecutablePrefixChecker()
    policy = ProgressProjectionCandidatePolicy(
        Inner(),
        candidate_count=1,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        checker=checker,
        min_progress_margin=0.002,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            artifact_digest="a" * 64,
            selected_subtask="pick_up(target)",
        ),
        local_observation=observation,
        context=SimpleNamespace(state_epoch=0),
        release_destination=None,
    )

    result = policy.infer({})
    audit = policy.audits[-1]
    candidate = audit["candidates"][0]

    assert calls == 1
    assert audit["eligible_selected_source_candidate_index"] == 0
    assert not candidate["nominal_checked"]["semantic_compatible"]
    assert candidate["checked"]["semantic_compatible"]
    assert candidate["checked"]["eligible_under_fixed_gate"]
    assert candidate["progress_projection"]["projection_l2"] < 0.05
    assert np.all(result["actions"][:, 0] > 0)
    assert np.all(result["actions"][:, 1:] == 0)


def test_candidate_policy_does_not_launder_nominal_hard_violation() -> None:
    class Inner:
        @staticmethod
        def infer(element):
            del element
            actions = np.zeros((10, 7), dtype=np.float64)
            actions[0, 0] = 2.0
            return {"actions": actions}

    observation = TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target", (0.1, 0.0, 0.5)),
        ),
    )
    policy = ProgressProjectionCandidatePolicy(
        Inner(),
        candidate_count=1,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        checker=SemanticExecutablePrefixChecker(),
        min_progress_margin=0.002,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            artifact_digest="a" * 64,
            selected_subtask="pick_up(target)",
        ),
        local_observation=observation,
        context=SimpleNamespace(state_epoch=0),
        release_destination=None,
    )

    policy.infer({})
    audit = policy.audits[-1]

    assert audit["eligible_selected_source_candidate_index"] is None
    assert audit["fallback_for_fail_closed_recheck"]
    assert "translation_velocity_limit" in audit["candidates"][0][
        "nominal_checked"
    ]["hard_violation_atoms"]
