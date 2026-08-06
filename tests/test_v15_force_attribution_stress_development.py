from __future__ import annotations

from typing import Any

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_force_attribution_stress_development as freezer
from scripts import run_v15_force_attribution_stress_development as runner


def _step(*, selected: bool, pre: float, reported: float, post: float) -> dict[str, Any]:
    return {
        "recovery_selected": selected,
        "pre_step_maximum_abs_risk_constraint_force": pre,
        "guard_scope_reported_maximum_abs_risk_constraint_force": reported,
        "post_step_maximum_abs_risk_constraint_force": post,
        "guard_scope_max_envelope_increment_over_pre_step": max(
            0.0, reported - pre
        ),
        "post_step_max_envelope_increment_over_pre_step": max(
            0.0, post - pre
        ),
        "post_step_max_envelope_reduction_from_pre_step": pre - post,
        "guard_scope_maximum_positive_joint_increment_over_pre_step": max(
            0.0, reported - pre
        ),
        "post_step_maximum_positive_joint_increment_over_pre_step": max(
            0.0, post - pre
        ),
        "guard_scope_legacy_force_recomputed_identity": True,
    }


def test_force_metrics_separate_total_force_from_positive_increment() -> None:
    rows = [
        {
            "baselines": {
                runner.BASELINE: {
                    "force_attribution_steps": [
                        _step(
                            selected=True,
                            pre=12000.0,
                            reported=10000.0,
                            post=200.0,
                        ),
                        _step(
                            selected=True,
                            pre=200.0,
                            reported=200.0,
                            post=350.0,
                        ),
                    ]
                }
            }
        }
    ]

    metrics = runner._force_metrics(rows)

    assert metrics["recovery_selected_step_count"] == 2
    assert metrics[
        "recovery_selected_reported_total_force_over_10000_count"
    ] == 0
    assert metrics[
        "recovery_selected_post_step_force_over_10000_count"
    ] == 0
    assert metrics[
        "recovery_selected_guard_scope_joint_amplification_over_1e_6_count"
    ] == 0
    assert metrics["recovery_selected_steps"][
        "pre_step_maximum_abs_risk_constraint_force"
    ]["maximum"] == 12000.0
    assert metrics["recovery_selected_steps"][
        "post_step_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] == 150.0


def test_frozen_force_development_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
