from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from scripts import run_four_arm_v4_l1_block10_qualification as block10
from scripts.run_four_arm_v4_l1_block10_k4_qualification import (
    Block10K4CandidatePolicy,
    Block10K4QualificationError,
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
            "proofalign.four-arm-v4-l1-block10-k4-"
            "qualification-protocol.v1"
        ),
        "protocol_id": "h10-k4-fixture",
        "execution_authorization": {
            "qualification_probe": True,
            "task_outcome_rollout": False,
            "clean_rollout": False,
            "attacked_rollout": False,
        },
        "repair": {
            "semantic_candidate_count": 4,
            "replan_steps": 10,
            "checked_action_block_steps": 10,
            "min_progress_m": 0.002,
            "threshold_changed": False,
        },
        "qualification_population": {
            "frozen_pairs": pairs,
            "base_pair_count": 45,
            "environment_seed": 97,
            "policy_seed": 37,
            "policy_inference_count": 180,
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
        }
        for index, pair in enumerate(
            _protocol()["qualification_population"]["frozen_pairs"]
        )
    ]


def test_h10_k4_design_is_exact() -> None:
    _validate_design(_protocol())


def test_h10_k4_design_rejects_k1() -> None:
    protocol = _protocol()
    protocol["repair"]["semantic_candidate_count"] = 1

    with pytest.raises(Block10K4QualificationError):
        _validate_design(protocol)


def test_h10_k4_summary_uses_versioned_classification() -> None:
    summary = build_summary(_protocol(), _rows(eligible=42))

    assert summary["qualification_pass"]
    assert (
        summary["classification"]
        == "l1_block10_k4_initial_availability_qualification_pass"
    )
    assert summary["checked_action_block_steps"] == 10
    assert summary["semantic_candidate_count"] == 4


def test_h10_k4_records_cumulative_candidate_coverage(
    monkeypatch,
) -> None:
    checked = [
        {
            "known": True,
            "semantic_compatible": index >= 2,
            "post_projection_compatible": index >= 2,
            "hard_violation_atoms": (),
            "progress_margin": 0.003 if index >= 2 else 0.001,
            "projection_l2": 0.0,
            "unknown_reason": None,
        }
        for index in range(4)
    ]

    def block10_infer(self, element):
        del element
        self.audits.append(
            {
                "candidates": [
                    {"checked": value} for value in checked
                ],
                "returned_source_candidate_index": 2,
                "matched_block_size_shadow": {
                    "assessments": {
                        "2": {},
                        "5": {},
                        "10": {},
                    }
                },
            }
        )
        return {"actions": np.zeros((10, 7))}

    monkeypatch.setattr(
        block10.Block10CandidatePolicy,
        "infer",
        block10_infer,
    )
    policy = Block10K4CandidatePolicy(
        SimpleNamespace(),
        candidate_count=4,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        min_progress_margin=0.002,
        max_projection_l2=0.5,
    )

    policy.infer({})
    cumulative = policy.audits[-1][
        "matched_candidate_count_shadow"
    ]["cumulative"]

    assert not cumulative["1"]["at_least_one_eligible"]
    assert not cumulative["2"]["at_least_one_eligible"]
    assert cumulative["4"]["at_least_one_eligible"]
