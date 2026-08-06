#!/usr/bin/env python3
"""Develop v15.11 bounded screening on disclosed mismatch environments."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_rolling_prebound_model_mismatch_development as predecessor,
)


SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.11-bounded-state-triggered-"
    "model-mismatch-development-evidence.v1"
)
RAW_V15_BASELINE = predecessor.RAW_V15_BASELINE
_BASE_AGGREGATE = predecessor._aggregate
_BASE_CALIBRATED_RUNTIME = (
    predecessor.predecessor.predecessor._patched_calibrated_runtime
)


class V15BoundedStateTriggeredDevelopmentError(RuntimeError):
    """Raised when the disclosed v15.11 development contract differs."""


@contextmanager
def _patched_bounded_runtime() -> Iterator[None]:
    pre_step_development = predecessor.predecessor
    v158_development = pre_step_development.predecessor
    mismatch = v158_development.predecessor
    development = mismatch.predecessor.development
    v157_runner = development.recovery
    with _BASE_CALIBRATED_RUNTIME():
        original_environment = (
            v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
        )
        original_schema = v157_runner.BRAKE_AUDIT_SCHEMA
        original_run_screened = development._run_screened
        captured: list[Any] = []

        class CaptureBoundedEnvironment(
            recovery.MultiJointBoundedStateTriggeredRecoveryEnvironment
        ):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                captured.append(self)

        def run_screened(env: Any) -> dict[str, Any]:
            captured.clear()
            result = original_run_screened(env)
            if len(captured) != 1:
                raise V15BoundedStateTriggeredDevelopmentError(
                    "v15.11 screened wrapper creation count differs"
                )
            observations = captured[0].observations
            generations = [
                int(row["rolling_prebound_used_generation"])
                for row in observations
            ]
            if generations != list(range(len(observations))):
                raise V15BoundedStateTriggeredDevelopmentError(
                    "v15.11 rolling generation sequence differs"
                )
            rollout_counts = [
                int(row["bounded_guarded_candidate_rollout_count"])
                for row in observations
            ]
            deadlock_diagnostics = [
                {
                    "runner_step_id": int(row["runner_step_id"]),
                    "current_target_margin_rad": float(
                        row["current_target_margin_rad"]
                    ),
                    "deadlock_reason": row.get("deadlock_reason"),
                    "risk_sides": row.get("risk_sides"),
                    "candidates": row.get("candidates"),
                }
                for row in observations
                if row.get("deadlock") is True
            ]
            multi_candidate_diagnostics = [
                {
                    "runner_step_id": int(row["runner_step_id"]),
                    "current_target_margin_rad": float(
                        row["current_target_margin_rad"]
                    ),
                    "selected_guard_margin_rad": row.get(
                        "selected_guard_margin_rad"
                    ),
                    "selected_candidate_profile_id": row.get(
                        "selected_candidate_profile_id"
                    ),
                    "candidates": row.get("candidates"),
                }
                for row in observations
                if int(row["bounded_guarded_candidate_rollout_count"]) > 1
            ]
            result.update(
                {
                    "rolling_prebound_setup_calibration_count": 1,
                    "rolling_prebound_update_count": len(observations),
                    "rolling_prebound_inactive_count": sum(
                        row.get(
                            "rolling_prebound_shadow_calibration_active"
                        )
                        is not True
                        for row in observations
                    ),
                    "rolling_prebound_action_latency_contamination_count": sum(
                        row.get(
                            "rolling_prebound_update_outside_action_screen"
                        )
                        is not True
                        for row in observations
                    ),
                    "rolling_prebound_setup_latency_seconds": float(
                        observations[0][
                            "pre_step_shadow_calibration_latency_seconds"
                        ]
                    ),
                    "rolling_prebound_update_latency_seconds_values": [
                        float(row["rolling_prebound_update_latency_seconds"])
                        for row in observations
                    ],
                    "bounded_state_triggered_audit_count": len(observations),
                    "bounded_state_triggered_inactive_count": sum(
                        row.get("bounded_state_triggered_recovery_active")
                        is not True
                        for row in observations
                    ),
                    "bounded_state_trigger_margin_mismatch_count": sum(
                        row.get("state_trigger_margin_rad")
                        != recovery.STATE_TRIGGER_MARGIN_RAD
                        for row in observations
                    ),
                    "bounded_unguarded_rollout_count": sum(
                        row.get("unguarded_shadow_rollout_performed") is True
                        for row in observations
                    ),
                    "bounded_rollout_budget_violation_count": sum(
                        count
                        > recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS
                        for count in rollout_counts
                    ),
                    "bounded_guarded_candidate_rollout_count": sum(
                        rollout_counts
                    ),
                    "bounded_guarded_candidate_rollout_max": max(
                        rollout_counts, default=0
                    ),
                    "bounded_deadlock_diagnostics": deadlock_diagnostics,
                    "bounded_multi_candidate_diagnostics": (
                        multi_candidate_diagnostics
                    ),
                }
            )
            return result

        v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
            CaptureBoundedEnvironment
        )
        v157_runner.BRAKE_AUDIT_SCHEMA = recovery.BRAKE_AUDIT_SCHEMA
        development._run_screened = run_screened
        try:
            yield
        finally:
            development._run_screened = original_run_screened
            v157_runner.BRAKE_AUDIT_SCHEMA = original_schema
            v157_runner.MultiJointIncrementalAdaptiveForceRecoveryEnvironment = (
                original_environment
            )


def _aggregate(
    rows: list[Mapping[str, Any]], audits: list[Mapping[str, Any]]
) -> dict[str, Any]:
    metrics = _BASE_AGGREGATE(rows, audits)
    reports = [row["baselines"][RAW_V15_BASELINE] for row in rows]
    keys = (
        "bounded_state_triggered_audit_count",
        "bounded_state_triggered_inactive_count",
        "bounded_state_trigger_margin_mismatch_count",
        "bounded_unguarded_rollout_count",
        "bounded_rollout_budget_violation_count",
        "bounded_guarded_candidate_rollout_count",
    )
    return {
        **metrics,
        **{
            key: sum(int(report[key]) for report in reports)
            for key in keys
        },
        "bounded_guarded_candidate_rollout_max": max(
            int(report["bounded_guarded_candidate_rollout_max"])
            for report in reports
        ),
    }


def execute(*, gpu: int) -> dict[str, Any]:
    original_runtime = predecessor._patched_rolling_runtime
    original_aggregate = predecessor._aggregate
    predecessor._patched_rolling_runtime = _patched_bounded_runtime
    predecessor._aggregate = _aggregate
    try:
        payload = predecessor.execute(gpu=gpu)
    finally:
        predecessor._aggregate = original_aggregate
        predecessor._patched_rolling_runtime = original_runtime

    metrics = payload["metrics"]
    gates = dict(payload["gate_results"])
    gates.update(
        {
            "bounded_audit_step_coverage": metrics[
                "bounded_state_triggered_audit_count"
            ]
            == metrics["policy_step_count"],
            "bounded_state_trigger_active": metrics[
                "bounded_state_triggered_inactive_count"
            ]
            == 0,
            "bounded_state_trigger_identity": metrics[
                "bounded_state_trigger_margin_mismatch_count"
            ]
            == 0,
            "zero_unguarded_shadow_rollout": metrics[
                "bounded_unguarded_rollout_count"
            ]
            == 0,
            "guarded_candidate_rollout_budget": metrics[
                "bounded_rollout_budget_violation_count"
            ]
            == 0
            and metrics["bounded_guarded_candidate_rollout_max"]
            <= recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS,
        }
    )
    passed = all(gates.values())
    payload.update(
        {
            "schema": SCHEMA,
            "classification": (
                "outcome_disclosed_development_pass"
                if passed
                else "outcome_disclosed_development_nonpass"
            ),
            "development_pass": passed,
            "state_trigger_margin_rad": recovery.STATE_TRIGGER_MARGIN_RAD,
            "guarded_candidate_rollout_budget": (
                recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS
            ),
            "unguarded_shadow_rollout_active": False,
            "gate_results": gates,
        }
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = execute(gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0 if payload["development_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
