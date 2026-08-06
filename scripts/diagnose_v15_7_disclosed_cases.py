#!/usr/bin/env python3
"""Exercise v15.7 incremental search on disclosed regression cases."""

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
from scripts import diagnose_v15_6_disclosed_cases as v156  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_incremental_adaptive_force_recovery as recovery,
)


SCHEMA = "proofalign.v15.7-disclosed-incremental-search-regression.v1"
DEFAULT_SOURCE_PROTOCOL = disclosed.DEFAULT_SOURCE_PROTOCOL
CASES = v156.CASES


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
            guard_solref=recovery.predecessor.SOFT_GUARD_SOLREF,
            wrapper_class=(
                recovery.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
            ),
        )
        summary = v156._summary(result)
        summary["maximum_screen_latency_seconds"] = max(
            float(row["screen_latency_seconds"])
            for row in result["steps"]
        )
        summary["screen_latency_seconds"] = [
            float(row["screen_latency_seconds"]) for row in result["steps"]
        ]
        rows.append({**dict(case), "summary": summary, "result": result})
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
        "incremental_extended_search": True,
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
    payload = execute(load_json_object(args.source_protocol.resolve()), gpu=args.gpu)
    rendered = canonical_text(payload)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
