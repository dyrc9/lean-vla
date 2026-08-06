#!/usr/bin/env python3
"""Exercise v15.6 on the three disclosed force/deadlock regressions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import diagnose_v15_4_force_nonpass as base  # noqa: E402
from scripts import diagnose_v15_5_deadlock_nonpass as disclosed  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_adaptive_force_recovery as recovery,
)


SCHEMA = "proofalign.v15.6-disclosed-force-deadlock-regression.v1"
DEFAULT_SOURCE_PROTOCOL = disclosed.DEFAULT_SOURCE_PROTOCOL
CASES = (*disclosed.CASES, *disclosed.REGRESSION_CASES)


def _maximum(steps: list[Mapping[str, Any]], field: str) -> float:
    return max((float(row[field]) for row in steps), default=0.0)


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(result["steps"])
    executed = [row for row in steps if row["deadlock"] is not True]
    recovery_steps = [row for row in executed if row["recovery_selected"] is True]
    return {
        "executed_step_count": int(result["executed_step_count"]),
        "deadlock_count": int(result["deadlock_count"]),
        "crossing_count": int(result["crossing_count"]),
        "below_floor_count": int(result["below_floor_count"]),
        "minimum_margin_rad": min(
            (float(row["actual_minimum_margin_rad"]) for row in executed),
            default=None,
        ),
        "maximum_attributable_force": _maximum(
            executed,
            "guard_scope_maximum_positive_joint_increment_over_pre_step",
        ),
        "maximum_post_step_absolute_force": _maximum(
            executed, "post_step_maximum_abs_risk_constraint_force"
        ),
        "maximum_post_step_increment": _maximum(
            executed,
            "post_step_maximum_positive_joint_increment_over_pre_step",
        ),
        "maximum_recovery_attributable_force": _maximum(
            recovery_steps,
            "guard_scope_maximum_positive_joint_increment_over_pre_step",
        ),
        "maximum_recovery_post_step_increment": _maximum(
            recovery_steps,
            "post_step_maximum_positive_joint_increment_over_pre_step",
        ),
        "fallback_selected_step_count": sum(
            str(row.get("selected_candidate_profile_id", "")).startswith(
                "stiff_recovery_fallback_"
            )
            for row in executed
        ),
        "selected_steps": [
            {
                "runner_step_id": int(row["runner_step_id"]),
                "guard_margin_rad": row["selected_guard_margin_rad"],
                "candidate_profile_id": row.get(
                    "selected_candidate_profile_id"
                ),
                "recovery_selected": bool(row["recovery_selected"]),
            }
            for row in executed
        ],
    }


def execute(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    spec = base._exactly_one(
        protocol["environments"],
        field="environment_id",
        value=disclosed.DISCLOSED_ENVIRONMENT_ID,
    )
    disclosed.development.v154.predecessor.base.calibration.v14._configure_environment(
        gpu
    )
    rows = []
    for case in CASES:
        condition = base._exactly_one(
            protocol["design"]["physics_conditions"],
            field="condition_id",
            value=case["condition_id"],
        )
        dose = base._exactly_one(
            protocol["design"]["doses"],
            field="dose",
            value=case["dose"],
        )
        result = base._run_case(
            spec,
            condition,
            dose,
            gpu=gpu,
            guard_solref=recovery.SOFT_GUARD_SOLREF,
            wrapper_class=recovery.MultiJointAdaptiveForceRecoveryEnvironment,
        )
        rows.append({**dict(case), "summary": _summary(result), "result": result})
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
        "soft_guard_solref": list(recovery.SOFT_GUARD_SOLREF),
        "proactive_trigger_margin_rad": (
            recovery.PROACTIVE_TRIGGER_MARGIN_RAD
        ),
        "fallback_guard_solrefs": [
            list(row) for row in recovery.FALLBACK_GUARD_SOLREFS
        ],
        "recovery_ladder_fractions": list(
            recovery.RECOVERY_LADDER_FRACTIONS
        ),
        "force_thresholds_unchanged": True,
        "cases": rows,
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
