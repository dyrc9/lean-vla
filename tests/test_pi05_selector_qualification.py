from __future__ import annotations

import numpy as np

from scripts.run_pi05_selector_qualification_e1 import (
    CANDIDATES,
    STAGE_ORDER,
    stage_indices,
    summarize,
)
from scripts.validate_pi05_selector_qualification_e1 import build_report


def _protocol() -> dict:
    return {
        "unknown_rule": {
            "minimum_top1_margin_mean_log_probability": 0.25,
            "occlusion_kinds": (
                "main_image_zero",
                "wrist_image_zero",
            ),
        },
        "qualification_gates": {
            "minimum_coverage": 0.90,
            "minimum_known_legal_frontier_rate": 0.95,
            "minimum_worst_stage_known_legal_rate": 0.80,
            "minimum_occlusion_abstention_rate": 0.80,
            "minimum_repeat_exact_rate": 1.0,
            "maximum_warm_p95_seconds": 0.50,
        },
    }


def test_stage_indices_use_gripper_state_then_release_command() -> None:
    states = np.zeros((20, 8), dtype=np.float64)
    states[:, -2:] = (0.04, -0.04)
    states[5:, -2:] = (0.002, -0.002)
    actions = np.zeros((20, 7), dtype=np.float64)
    actions[:5, -1] = -1.0
    actions[5:15, -1] = 1.0
    actions[15:, -1] = -1.0

    assert stage_indices(
        states,
        actions,
        closed_qpos_max=0.025,
        release_action_max=-0.5,
        minimum_held_steps=4,
    ) == {
        "initial": 0,
        "post_grasp_boundary": 5,
        "held_mid": 10,
        "pre_release": 14,
        "release_command": 15,
    }


def test_summary_disqualifies_high_margin_illegal_stage_predictions() -> None:
    rows = []
    for index, stage in enumerate(STAGE_ORDER):
        legal = stage != "release_command"
        rows.append(
            {
                "case_id": f"case-{index}",
                "task": "task",
                "stage": stage,
                "top1": (
                    CANDIDATES[0] if legal else CANDIDATES[1]
                ),
                "top1_margin_mean_log_probability": 0.8,
                "top1_in_legal_frontier": legal,
                "score_seconds_including_first_compile": 0.1,
            }
        )
    repeats = [{"exact_repeat_match": True}]
    ablations = [
        {
            "ablation_kind": kind,
            "top1_margin_mean_log_probability": 0.8,
        }
        for kind in ("main_image_zero", "wrist_image_zero")
    ]

    summary = summarize(_protocol(), rows, repeats, ablations)

    assert summary["coverage"] == 1.0
    assert summary["qualified"] is False
    assert "worst_stage_known_legal" in summary["failed_gates"]
    assert "occlusion_abstention" in summary["failed_gates"]


def test_frozen_e1_artifact_validates_and_requires_fallback() -> None:
    report = build_report()

    assert report["valid"] is True
    assert report["classification"] == "raw_pi05_selector_disqualified"
    assert report["decision"] == {
        "fallback": "deterministic trusted geometry/task-graph FSM",
        "fallback_required": True,
        "raw_pi05_selector_authorized_for_l1": False,
    }
    assert report["no_outcome_boundary"] == {
        "training_performed": False,
        "actions_executed": False,
        "outcomes_read": False,
        "simulator_created": False,
    }
