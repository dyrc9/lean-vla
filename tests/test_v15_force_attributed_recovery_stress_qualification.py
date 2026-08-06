from __future__ import annotations

from collections import Counter
from typing import Any

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_force_attributed_recovery_stress_qualification as freezer,
)
from scripts import (
    run_v15_force_attributed_recovery_stress_qualification as runner,
)


def _prior_population() -> tuple[list[dict[str, Any]], set[tuple[str, int, int]]]:
    clean = load_json_object(freezer.V14_CLEAN_PROTOCOL_PATH)
    prior = freezer._pairs(clean["workloads"])
    for path, key in (
        (freezer.V14_STRESS_QUALIFICATION_PROTOCOL_PATH, "environments"),
        (freezer.V15_2_DEVELOPMENT_PROTOCOL_PATH, "schedule"),
        (freezer.V15_2_CALIBRATION_PROTOCOL_PATH, "environments"),
        (freezer.V15_2_FRESH2_PROTOCOL_PATH, "environments"),
        (freezer.FORCE_DEVELOPMENT_PROTOCOL_PATH, "environments"),
    ):
        prior.update(freezer._pairs(load_json_object(path)[key]))
    return clean["workloads"], prior


def test_population_is_deterministic_balanced_and_exact_pair_unseen() -> None:
    workloads, prior = _prior_population()

    first = freezer._select_environments(workloads, prior)
    second = freezer._select_environments(workloads, prior)

    assert first == second
    assert len(first) == 18
    assert not (freezer._pairs(first) & prior)
    assert Counter(row["suite"] for row in first) == {
        "obstacle_avoidance": 6,
        "human_safety": 6,
        "obstacle_avoidance_human": 6,
    }
    assert all(row["environment_seed"] == 4509 for row in first)
    for suite in freezer.SUITES:
        assert len(
            {
                row["task_id"]
                for row in first
                if row["suite"] == suite
            }
        ) == 6


def _step(
    *,
    intervened: bool,
    recovery: bool,
    pre: float,
    scope: float,
    post: float,
) -> dict[str, Any]:
    return {
        "intervened": intervened,
        "recovery_selected": recovery,
        "pre_step_maximum_abs_risk_constraint_force": pre,
        "guard_scope_reported_maximum_abs_risk_constraint_force": scope,
        "guard_scope_maximum_positive_joint_increment_over_pre_step": max(
            0.0, scope - pre
        ),
        "post_step_maximum_abs_risk_constraint_force": post,
        "post_step_maximum_positive_joint_increment_over_pre_step": max(
            0.0, post - pre
        ),
        "guard_scope_legacy_force_recomputed_identity": True,
    }


def test_force_metrics_partition_standard_and_recovery_interventions() -> None:
    rows = [
        {
            "baselines": {
                runner.V15_BASELINE: {
                    "force_attribution_steps": [
                        _step(
                            intervened=True,
                            recovery=False,
                            pre=100.0,
                            scope=500.0,
                            post=200.0,
                        ),
                        _step(
                            intervened=True,
                            recovery=True,
                            pre=12000.0,
                            scope=10000.0,
                            post=200.0,
                        ),
                        _step(
                            intervened=False,
                            recovery=False,
                            pre=0.0,
                            scope=0.0,
                            post=0.0,
                        ),
                    ]
                }
            }
        }
    ]

    metrics = runner._qualification_force_metrics(rows)

    assert metrics["step_count"] == 3
    assert metrics["intervention_step_count"] == 2
    assert metrics["standard_guard_intervention_step_count"] == 1
    assert metrics["recovery_intervention_step_count"] == 1
    assert metrics["legacy_force_recomputation_mismatch_count"] == 0
    assert metrics["all_interventions"][
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] == 400.0
    assert metrics["recovery_interventions"][
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] == 0.0


def test_force_metrics_retain_empty_nonpass_groups_without_crashing() -> None:
    rows = [
        {
            "baselines": {
                runner.V15_BASELINE: {
                    "force_attribution_steps": [
                        _step(
                            intervened=False,
                            recovery=False,
                            pre=0.0,
                            scope=0.0,
                            post=0.0,
                        )
                    ]
                }
            }
        }
    ]

    metrics = runner._qualification_force_metrics(rows)

    assert metrics["intervention_step_count"] == 0
    assert metrics["all_interventions"][
        "guard_scope_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] is None
    assert metrics["recovery_interventions"][
        "post_step_maximum_positive_joint_increment_over_pre_step"
    ]["maximum"] is None


def test_frozen_protocol_is_current_and_preserves_terminal_gates_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)
    terminal = load_json_object(freezer.FORCE_DEVELOPMENT_TERMINAL_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
    for name, value in terminal[
        "frozen_future_qualification_gates"
    ].items():
        assert retained["gates"][name] == value
    assert retained["design"]["baselines"] == list(runner.BASELINES)
    assert retained["execution_authorization"][
        "same_environment_shadow_trace_identity_claim"
    ] is False
