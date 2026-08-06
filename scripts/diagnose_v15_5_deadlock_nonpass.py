#!/usr/bin/env python3
"""Reproduce the two disclosed v15.5 residual-deadlock lanes."""

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

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import diagnose_v15_4_force_nonpass as diagnostic  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_force_constrained_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_force_constrained_physics_development as development,
)


SCHEMA = "proofalign.v15.5-disclosed-deadlock-nonpass-diagnostic.v1"
DEFAULT_SOURCE_PROTOCOL = development.DEFAULT_PROTOCOL
DISCLOSED_ENVIRONMENT_ID = "v15_4_physics_qual_human_safety_task13_init10"
CASES = (
    {
        "case_id": "low_mass_low_dose_late_deadlock",
        "condition_id": "arm_mass_0_8x",
        "dose": "low",
    },
    {
        "case_id": "low_friction_high_dose_early_deadlock",
        "condition_id": "arm_friction_0_7x",
        "dose": "high",
    },
)
REGRESSION_CASES = (
    {
        "case_id": "high_friction_high_dose_force_regression",
        "condition_id": "arm_friction_1_3x",
        "dose": "high",
    },
)
RECOVERY_LADDER_FRACTIONS = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)
SOLVER_PROFILES = (
    {"profile_id": "soft_0_006", "guard_solref": (0.006, 1.0)},
    {"profile_id": "stiff_0_004", "guard_solref": (0.004, 1.0)},
)
_ACTIVE_GUARD_SOLREF = recovery.FORCE_CONSTRAINED_GUARD_SOLREF


class V155DeadlockNonpassDiagnosticError(RuntimeError):
    """Raised when the disclosed v15.5 deadlock cannot be reproduced."""


class ExpandedForceConstrainedRecoveryConfig(
    recovery.ForceConstrainedRecoveryConfig
):
    """Add disclosed recovery margins while retaining force constraints."""

    def __init__(self, current_edge_margin_rad: float | None) -> None:
        super().__init__(current_edge_margin_rad)
        object.__setattr__(self, "guard_solref", _ACTIVE_GUARD_SOLREF)

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        edge = self.current_edge_margin_rad
        if edge is None:
            ladder: tuple[float, ...] = ()
        else:
            floor = recovery.RECOVERY_GUARD_MARGIN_RAD
            ladder = tuple(
                edge - fraction * (edge - floor)
                for fraction in RECOVERY_LADDER_FRACTIONS
            )
        middle = () if edge is None else (edge, *ladder)
        return (
            *recovery.BRAKE_MARGINS_RAD,
            *middle,
            recovery.RECOVERY_GUARD_MARGIN_RAD,
        )


@contextmanager
def _patched_expanded_candidates(
    guard_solref: tuple[float, float],
) -> Iterator[None]:
    global _ACTIVE_GUARD_SOLREF
    original = recovery.ForceConstrainedRecoveryConfig
    original_solref = _ACTIVE_GUARD_SOLREF
    _ACTIVE_GUARD_SOLREF = guard_solref
    recovery.ForceConstrainedRecoveryConfig = (
        ExpandedForceConstrainedRecoveryConfig
    )
    try:
        yield
    finally:
        recovery.ForceConstrainedRecoveryConfig = original
        _ACTIVE_GUARD_SOLREF = original_solref


def _deadlock_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    deadlocks = [row for row in result["steps"] if row["deadlock"] is True]
    if len(deadlocks) != 1 or int(result["deadlock_count"]) != 1:
        raise V155DeadlockNonpassDiagnosticError(
            "expected exactly one disclosed residual deadlock"
        )
    row = deadlocks[0]
    return {
        "runner_step_id": int(row["runner_step_id"]),
        "deadlock_reason": str(row["deadlock_reason"]),
        "current_minimum_margin_rad": float(
            row["current_minimum_margin_rad"]
        ),
        "unguarded_predicted_minimum_margin_rad": float(
            row["unguarded_predicted_minimum_margin_rad"]
        ),
        "base_safety_eligible_candidate_count": int(
            row["base_safety_eligible_candidate_count"]
        ),
        "force_feasible_base_candidate_count": int(
            row["force_feasible_base_candidate_count"]
        ),
        "force_rejected_base_eligible_candidate_count": int(
            row["force_rejected_base_eligible_candidate_count"]
        ),
        "candidate_count": len(row["candidates"]),
        "candidates": list(row["candidates"]),
    }


def execute(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    spec = diagnostic._exactly_one(
        protocol["environments"],
        field="environment_id",
        value=DISCLOSED_ENVIRONMENT_ID,
    )
    development.v154.predecessor.base.calibration.v14._configure_environment(gpu)
    rows = []
    resolved = []
    for case in CASES:
        condition = diagnostic._exactly_one(
            protocol["design"]["physics_conditions"],
            field="condition_id",
            value=case["condition_id"],
        )
        dose = diagnostic._exactly_one(
            protocol["design"]["doses"],
            field="dose",
            value=case["dose"],
        )
        resolved.append((case, condition, dose))
        result = diagnostic._run_case(
            spec,
            condition,
            dose,
            gpu=gpu,
            guard_solref=recovery.FORCE_CONSTRAINED_GUARD_SOLREF,
            wrapper_class=recovery.MultiJointForceConstrainedRecoveryEnvironment,
        )
        rows.append(
            {
                **dict(case),
                "result": result,
                "deadlock": _deadlock_summary(result),
            }
        )
    expanded_cells = []
    regression_resolved = []
    for case in REGRESSION_CASES:
        regression_resolved.append(
            (
                case,
                diagnostic._exactly_one(
                    protocol["design"]["physics_conditions"],
                    field="condition_id",
                    value=case["condition_id"],
                ),
                diagnostic._exactly_one(
                    protocol["design"]["doses"],
                    field="dose",
                    value=case["dose"],
                ),
            )
        )
    for profile in SOLVER_PROFILES:
        guard_solref = tuple(profile["guard_solref"])
        for case, condition, dose in (*resolved, *regression_resolved):
            with _patched_expanded_candidates(guard_solref):
                result = diagnostic._run_case(
                    spec,
                    condition,
                    dose,
                    gpu=gpu,
                    guard_solref=guard_solref,
                    wrapper_class=(
                        recovery.MultiJointForceConstrainedRecoveryEnvironment
                    ),
                )
            expanded_cells.append(
                {
                    "profile_id": str(profile["profile_id"]),
                    "guard_solref": list(guard_solref),
                    **dict(case),
                    "result": result,
                }
            )
    return {
        "schema": SCHEMA,
        "classification": "outcome_disclosed_development_diagnostic",
        "qualification_claim_authorized": False,
        "task_outcome_read": False,
        "policy_loaded": False,
        "fresh_environment_per_case": True,
        "source_protocol": DEFAULT_SOURCE_PROTOCOL.relative_to(
            REPO_ROOT
        ).as_posix(),
        "disclosed_environment_id": DISCLOSED_ENVIRONMENT_ID,
        "joint_index": diagnostic.DISCLOSED_JOINT_INDEX,
        "side": diagnostic.DISCLOSED_SIDE,
        "force_thresholds_unchanged": True,
        "diagnostic_recovery_ladder_fractions": list(
            RECOVERY_LADDER_FRACTIONS
        ),
        "cases": rows,
        "expanded_candidate_cells": expanded_cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-protocol", type=Path, default=DEFAULT_SOURCE_PROTOCOL
    )
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol = load_json_object(args.source_protocol.resolve())
    payload = execute(protocol, gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
