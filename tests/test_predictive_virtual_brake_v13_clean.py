from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_predictive_virtual_brake_v13_clean as freezer
from scripts import run_l2_predictive_virtual_brake_v13 as online
from scripts import run_predictive_virtual_brake_v13_clean as clean


def test_outcome_blind_population_is_fresh_and_complete() -> None:
    source = load_json_object(freezer.POPULATION_SOURCE_PATH)
    v11 = load_json_object(
        freezer.V11_CLEAN_SCALE45_PROTOCOL_PATH
    )

    workloads = freezer.derive_workloads(source, v11)
    schedule = freezer.build_schedule(workloads)
    fresh1 = load_json_object(freezer.FRESH1_PROTOCOL_PATH)

    assert len(workloads) == 45
    assert len(schedule) == 180
    assert len(
        {
            (
                row["suite"],
                row["task_id"],
                row["init_state_id"],
            )
            for row in workloads
        }
    ) == 45
    assert all(
        row["init_state_id"] not in row["excluded_init_state_ids"]
        for row in workloads
    )
    by_pair: dict[str, set[str]] = {}
    for row in schedule:
        by_pair.setdefault(row["base_pair_id"], set()).add(
            row["arm"]
        )
    assert all(
        arms
        == {
            "vla_only",
            "semantic_only",
            "execution_only",
            "dual",
        }
        for arms in by_pair.values()
    )
    stable_fields = (
        "arm",
        "base_pair_id",
        "suite",
        "task_id",
        "init_state_id",
        "environment_seed",
        "policy_seed",
    )
    assert [
        tuple(row[field] for field in stable_fields)
        for row in schedule
    ] == [
        tuple(row[field] for field in stable_fields)
        for row in fresh1["schedule"]
    ]


def test_execute_rejects_validator_only_interpreter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        clean,
        "REQUIRED_INTERPRETER",
        tmp_path / "missing-openpi-python",
    )

    with pytest.raises(
        clean.PredictiveVirtualBrakeCleanError,
        match="external/openpi/.venv/bin/python",
    ):
        clean.execute(
            {},
            protocol_path=tmp_path / "protocol.json",
            policy_gpu=1,
            egl_gpu=2,
        )


def _audit(*, enabled: bool, intervention: bool = False) -> dict[str, Any]:
    return {
        "schema": online.BRAKE_AUDIT_SCHEMA,
        "runner_step_id": 0,
        "enabled": enabled,
        "screen_performed": enabled,
        "triggered": intervention,
        "intervened": intervention,
        "deadlock": False,
        "deadlock_reason": None,
        "source_action_digest": "source",
        "executed_action_digest": "source",
        "exact_action_identity": True,
        "unguarded_predicted_minimum_margin_rad": (
            0.14 if enabled else None
        ),
        "unguarded_predicted_target_margin_rad": (
            0.14 if enabled else None
        ),
        "selected_guard_margin_rad": (
            0.16 if intervention else None
        ),
        "selected_predicted_minimum_margin_rad": (
            0.16 if intervention else None
        ),
        "selected_predicted_target_margin_rad": (
            0.16 if intervention else None
        ),
        "actual_minimum_margin_rad": 0.16,
        "actual_target_margin_rad": 0.16,
        "prediction_execution_margin_error_rad": (
            0.0 if intervention else None
        ),
        "shadow_restore_identity": True if enabled else None,
        "candidate_restore_identity": True if enabled else None,
        "guard_scope_restored": True if intervention else None,
        "candidate_count": 1 if intervention else 0,
        "eligible_candidate_count": 1 if intervention else 0,
        "shadow_env_step_count": 2 if intervention else int(enabled),
        "screen_latency_seconds": 0.01 if enabled else 0.0,
        "maximum_abs_target_constraint_force": (
            12.0 if intervention else 0.0
        ),
        "torque_bound_violation_count": 0,
        "candidates": [],
    }


def _episode(
    arm: str,
    *,
    success: bool,
) -> dict[str, Any]:
    l2 = arm in {"execution_only", "dual"}
    return {
        "metadata": {
            "runner_variant": clean.EXPECTED_RUNNER,
            "four_arm_label": arm,
            "legacy_l2_execution_integrity_active": False,
            "predictive_virtual_brake_active": l2,
            "predictive_virtual_brake_schema": (
                online.BRAKE_AUDIT_SCHEMA if l2 else None
            ),
            "predictive_virtual_brake_target_joint_index": (
                online.TARGET_JOINT_INDEX if l2 else None
            ),
            "predictive_virtual_brake_target_joint_side": (
                online.TARGET_JOINT_SIDE if l2 else None
            ),
            "predictive_virtual_brake_trigger_margin_rad": (
                online.TRIGGER_MARGIN_RAD if l2 else None
            ),
            "predictive_virtual_brake_safe_margin_floor_rad": (
                online.SAFE_MARGIN_FLOOR_RAD if l2 else None
            ),
            "predictive_virtual_brake_guard_margins_rad": (
                list(online.BRAKE_MARGINS_RAD) if l2 else None
            ),
            "predictive_virtual_brake_guard_solref": (
                list(online.GUARD_SOLREF) if l2 else None
            ),
            "predictive_virtual_brake_guard_solimp": (
                list(online.GUARD_SOLIMP) if l2 else None
            ),
            "predictive_virtual_brake_action_substitution": False,
        },
        "task_success": success,
        "strict_success_no_cost": success,
        "unsafe_cost_or_collision": False,
        "decision": "env_done" if success else "max_steps",
        "trace": [
            {
                "phase": "policy",
                "step_id": 0,
                "predictive_virtual_brake": _audit(
                    enabled=l2,
                    intervention=arm == "execution_only",
                ),
                "saber_constraint_signals": {
                    "joint_limit_violation": False,
                },
            }
        ],
    }


def test_v13_metrics_include_paired_utility_and_mechanism_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clean, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        clean,
        "_BASE_V10_METRICS",
        lambda _protocol, _evidence: ({}, {}),
    )
    arms = (
        "vla_only",
        "semantic_only",
        "execution_only",
        "dual",
    )
    schedule = []
    artifacts = []
    for index, arm in enumerate(arms):
        episode_id = f"episode_{arm}"
        relative = Path("episodes") / f"{arm}.json"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_episode(arm, success=True)),
            encoding="utf-8",
        )
        schedule.append(
            {
                "episode_id": episode_id,
                "base_pair_id": "pair0",
                "arm": arm,
            }
        )
        artifacts.append(
            {
                "episode_id": episode_id,
                "path": relative.as_posix(),
            }
        )
    protocol = {
        "schedule": schedule,
        "analysis": {
            "bootstrap_resamples": 100,
            "bootstrap_seed_base": 7,
        },
        "v13_gates": {
            "paired_task_success_difference_lower_bound_min": -0.20,
        },
    }

    metrics, gates = clean._v13_metrics(
        protocol, {"episodes": artifacts}
    )

    assert metrics["paired_task_success_contrasts"][
        "execution_only_minus_vla_only"
    ]["estimate"] == 0.0
    assert metrics["intervention_count"] == 1
    assert metrics["maximum_abs_target_constraint_force"] == 12.0
    assert gates["execution_only_task_success_noninferiority"] is True
    assert gates["dual_task_success_noninferiority"] is True
    assert gates["shadow_restore_identity"] is True
    assert gates["exact_action_identity"] is True
