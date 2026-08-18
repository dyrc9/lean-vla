from __future__ import annotations

import json

import pytest

from scripts import analyze_l1_task_conditioned_experiment as analysis


def _row(
    condition: str,
    unit: str,
    arm: str,
    *,
    clean_eligible: bool = False,
    contact: int = 0,
    unsafe: bool = False,
    task_success: bool = True,
) -> dict:
    return {
        "condition": condition,
        "unit_id": unit,
        "base_pair_id": unit.rsplit("-", 1)[0],
        "seed_block_id": "seed-a",
        "arm": arm,
        "terminal_exception": False,
        "task_success": task_success,
        "strict_success_no_cost": task_success and not unsafe,
        "unsafe_cost_or_collision": unsafe,
        "valid_attempt": True,
        "clean_eligible": clean_eligible,
        "risk_metrics": {
            "robot_contact_count": contact,
            "joint_limit_violation_steps": 0,
            "excessive_force_steps": 0,
        },
    }


def test_full_population_pair_includes_libero_cost_collision() -> None:
    rows = [
        _row("clean", "pair-0", "vla_only"),
        _row("attacked", "pair-0", "vla_only", unsafe=True),
    ]
    pairs, summary = analysis._paired(rows)
    assert pairs[0]["risk_transitions"] == {
        "libero_cost_or_collision": True,
        "robot_contact_count_delta": False,
        "joint_limit_steps_delta": False,
        "excessive_force_steps_delta": False,
    }
    assert pairs[0]["any_risk_transition"] is True
    assert summary["vla_only"]["channel_transition_counts"][
        "libero_cost_or_collision"
    ] == 1


def test_registered_analysis_matches_four_channel_baseline_and_excludes_task_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    historical = tmp_path / "summary.json"
    historical_units = []
    for index in range(120):
        eligible = index < 86
        transition = index < 39
        historical_units.append(
            {
                "unit_id": f"historical-{index}",
                "clean_eligible": eligible,
                "transition_observed": transition if eligible else False,
                "transition": {
                    "channels": (
                        {
                            "libero_cost_or_collision": transition,
                            "robot_contact_count_delta": False,
                            "joint_limit_steps_delta": False,
                            "excessive_force_steps_delta": False,
                        }
                        if eligible else {}
                    )
                },
            }
        )
    historical.write_text(
        json.dumps(
            {
                "classification": "confirmatory_attack_foundation_nonpass",
                "clean_eligible_unit_count": 86,
                "transition_unit_count": 39,
                "task_failure_alone_counts_as_transition": False,
                "units": historical_units,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(analysis, "M2_SUMMARY", historical)
    monkeypatch.setattr(analysis, "BOOTSTRAP_RESAMPLES", 100)
    rows = []
    for arm in analysis.ARM_ORDER:
        rows.extend(
            [
                _row("clean", "pair-a-0", arm, clean_eligible=True),
                _row("attacked", "pair-a-0", arm, unsafe=True),
                _row("clean", "pair-b-0", arm, clean_eligible=True),
                _row(
                    "attacked", "pair-b-0", arm,
                    task_success=False,
                ),
                _row("clean", "pair-c-0", arm, clean_eligible=False),
                _row("attacked", "pair-c-0", arm, contact=5),
            ]
        )
    result = analysis._registered_risk_analysis(rows)
    assert result["channels"] == list(analysis.TRANSITION_CHANNELS)
    assert result["same_as_45_35_percent_baseline"] is True
    for arm in analysis.ARM_ORDER:
        arm_result = result["by_arm"][arm]
        assert arm_result["arm_specific_clean_eligible_count"] == 2
        assert arm_result["transition_count"] == 1
        assert arm_result["transition_rate"] == 0.5
        assert arm_result["channel_transition_counts"][
            "libero_cost_or_collision"
        ] == 1
    assert result["fixed_original_86_cohort"]["current_heldout_overlap_count"] == 0
    assert result["fixed_original_86_cohort"]["estimable"] is False
