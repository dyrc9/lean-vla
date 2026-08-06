from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.run_four_arm_v4_l1_block10_qualification import (
    Block10CandidatePolicy,
    Block10QualificationError,
    _validate_design,
    build_summary,
)
from scripts.run_l2_execution_attack_eval_v2 import (
    BoundedCandidatePolicy,
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
            "proofalign.four-arm-v4-l1-block10-qualification-protocol.v1"
        ),
        "protocol_id": "block10-fixture",
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
            "dispatched_action_block_steps_if_later_authorized": 10,
            "min_progress_m": 0.002,
            "threshold_changed": False,
        },
        "qualification_population": {
            "frozen_pairs": pairs,
            "base_pair_count": 45,
            "environment_seed": 83,
            "policy_seed": 29,
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
    rows = []
    for index, pair in enumerate(
        _protocol()["qualification_population"]["frozen_pairs"]
    ):
        rows.append(
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
            }
        )
    return rows


def test_block10_design_is_exact() -> None:
    _validate_design(_protocol())


def test_block10_design_rejects_shorter_prefix() -> None:
    protocol = _protocol()
    protocol["repair"]["replan_steps"] = 5

    with pytest.raises(Block10QualificationError):
        _validate_design(protocol)


def test_block10_summary_uses_versioned_classification() -> None:
    summary = build_summary(_protocol(), _rows(eligible=42))

    assert summary["qualification_pass"]
    assert (
        summary["classification"]
        == "l1_block10_initial_availability_qualification_pass"
    )
    assert summary["checked_action_block_steps"] == 10
    assert summary["semantic_candidate_count"] == 1


def test_block10_records_matched_shadow_without_extra_policy_call(
    monkeypatch,
) -> None:
    parent_calls = 0
    chunk = np.zeros((10, 7), dtype=np.float64)
    chunk[:, 0] = 0.005

    def parent_infer(self, element):
        nonlocal parent_calls
        del element
        parent_calls += 1
        self.audits.append(
            {
                "returned_source_policy_chunk_sha256": "a" * 64,
                "candidates": [
                    {
                        "checked": {
                            "known": True,
                            "semantic_compatible": True,
                            "post_projection_compatible": True,
                            "hard_violation_atoms": (),
                            "progress_margin": 0.0025,
                            "projection_l2": 0.0,
                            "unknown_reason": None,
                        }
                    }
                ],
            }
        )
        return {"actions": chunk}

    class Checker:
        @staticmethod
        def checked_candidate(**kwargs):
            steps = kwargs["command_shape"][0]
            progress = steps * 0.00025
            compatible = progress >= 0.002
            return (
                SimpleNamespace(
                    known=True,
                    semantic_compatible=compatible,
                    post_projection_compatible=compatible,
                    hard_violation_atoms=(),
                    progress_margin=progress,
                    projection_l2=0.0,
                ),
                SimpleNamespace(unknown_reason=None),
            )

    monkeypatch.setattr(BoundedCandidatePolicy, "infer", parent_infer)
    policy = Block10CandidatePolicy(
        SimpleNamespace(),
        candidate_count=1,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        checker=Checker(),
        min_progress_margin=0.002,
        max_projection_l2=0.5,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            artifact_digest="b" * 64,
            selected_subtask="pick_up(target)",
        ),
        local_observation=object(),
        context=SimpleNamespace(state_epoch=0),
        release_destination="destination",
    )

    observed = policy.infer({})
    shadow = policy.audits[-1]["matched_block_size_shadow"]

    assert observed["actions"] is chunk
    assert parent_calls == 1
    assert not shadow["assessments"]["2"]["eligible_under_fixed_gate"]
    assert not shadow["assessments"]["5"]["eligible_under_fixed_gate"]
    assert shadow["assessments"]["10"]["eligible_under_fixed_gate"]
