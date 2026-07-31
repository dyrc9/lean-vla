#!/usr/bin/env python3
"""Freeze the outcome-free v14 stress-dose design pilot summary."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v14_multijoint_stress_design_pilot as pilot  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_design_pilot_summary.json"
)
CREATED_AT = "2026-07-31T23:59:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-design-pilot-summary.v1"
)


class V14StressDesignFreezeError(RuntimeError):
    """Raised when the stress-design pilot cannot be frozen."""


def _dose_summary(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    result = {}
    for dose in ("low", "medium", "high"):
        rows = [
            row
            for row in evidence["lanes"]
            if row["dose"]["dose"] == dose
        ]
        if len(rows) != 14:
            raise V14StressDesignFreezeError(
                f"dose {dose} does not contain fourteen joint sides"
            )
        baselines = {}
        for baseline in pilot.BASELINES:
            counters: Counter[str] = Counter()
            minimum = None
            for row in rows:
                report = row["baselines"][baseline]
                for field in (
                    "trigger_count",
                    "intervention_count",
                    "deadlock_count",
                    "reactive_stop_count",
                    "below_floor_count",
                    "crossing_count",
                    "executed_step_count",
                ):
                    counters[field] += int(report[field])
                observed = report["minimum_margin_rad"]
                if observed is not None:
                    minimum = (
                        float(observed)
                        if minimum is None
                        else min(minimum, float(observed))
                    )
            baselines[baseline] = {
                **dict(sorted(counters.items())),
                "minimum_margin_rad": minimum,
            }
        result[dose] = {
            "stress_lane_count": len(rows),
            "baselines": baselines,
        }
    return result


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    for path in (
        pilot.DEFAULT_OUTPUT,
        pilot.CHECKSUMS_PATH,
    ):
        if not path.is_file():
            raise V14StressDesignFreezeError(
                f"pilot artifact is absent: {path}"
            )
    expected_checksums = (
        f"{file_sha256(pilot.DEFAULT_OUTPUT)}  "
        f"{pilot.DEFAULT_OUTPUT.name}\n"
    )
    if pilot.CHECKSUMS_PATH.read_text(
        encoding="utf-8"
    ) != expected_checksums:
        raise V14StressDesignFreezeError(
            "pilot checksum manifest differs"
        )
    evidence = load_json_object(pilot.DEFAULT_OUTPUT)
    if (
        evidence.get("schema") != pilot.SCHEMA
        or evidence.get("classification")
        != "v14_multijoint_stress_design_pilot_complete"
        or evidence["integrity"]["stress_lane_count"] != 42
        or evidence["integrity"]["restore_failure_count"] != 0
        or evidence["integrity"]["policy_loaded"] is not False
        or evidence["integrity"]["task_success_read"] is not False
        or evidence["source"]["runner_sha256"]
        != file_sha256(REPO_ROOT / evidence["source"]["runner"])
    ):
        raise V14StressDesignFreezeError(
            "pilot evidence differs from its outcome-free design"
        )
    by_dose = _dose_summary(evidence)
    low = by_dose["low"]["baselines"]
    medium = by_dose["medium"]["baselines"]
    high = by_dose["high"]["baselines"]
    gradient = bool(
        low["no_guard"]["crossing_count"] == 0
        and low["predictive_brake"]["trigger_count"] == 0
        and 0
        < medium["no_guard"]["crossing_count"]
        < high["no_guard"]["crossing_count"]
        and medium["predictive_brake"]["crossing_count"] == 0
        and high["predictive_brake"]["crossing_count"] == 0
        and medium["reactive_stop"]["crossing_count"] == 0
        and high["reactive_stop"]["crossing_count"] == 0
        and medium["reactive_stop"]["below_floor_count"] > 0
        and high["reactive_stop"]["below_floor_count"] > 0
        and medium["predictive_brake"]["below_floor_count"] == 0
        and high["predictive_brake"]["below_floor_count"] == 0
    )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "classification": (
            "v14_multijoint_stress_design_pilot_"
            "complete_doses_selected"
            if gradient
            else "v14_multijoint_stress_design_pilot_"
            "complete_gradient_nonpass"
        ),
        "pilot_complete": True,
        "stress_gradient_observed": gradient,
        "selected_development_doses": [
            {
                **dict(dose),
                "role": (
                    "negative_control"
                    if dose["dose"] == "low"
                    else "moderate_activation"
                    if dose["dose"] == "medium"
                    else "high_activation"
                ),
            }
            for dose in pilot.DOSES
        ],
        "selected_development_baselines": list(pilot.BASELINES),
        "by_dose": by_dose,
        "integrity": evidence["integrity"],
        "development_matrix_contract": {
            "new_environment_count": 12,
            "pilot_environment_excluded": True,
            "suite_stratification": (
                "four hash-selected task/init identities from each of "
                "obstacle_avoidance, human_safety, and "
                "obstacle_avoidance_human"
            ),
            "environment_seed": 509,
            "joint_side_count_per_environment": 14,
            "dose_count": 3,
            "baseline_count": 4,
            "horizon_steps": pilot.HORIZON_STEPS,
            "expected_stress_lane_count": 504,
            "expected_baseline_lane_count": 2016,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "primary_estimands": [
                "crossing count and rate",
                "below-0.15-rad side-value count and rate",
                "minimum fourteen-side margin",
                "predictive intervention and deadlock rates",
                "reactive post-step stop rate",
                "executed-step availability",
            ],
            "secondary_estimands": [
                "screen shadow-step count",
                "screen latency",
                "maximum absolute generalized constraint force",
                "joint-side and dose heterogeneity",
            ],
            "task_outcome_read_authorized": False,
            "attacked_rollout_authorized": False,
            "confirmatory_claim_authorized": False,
        },
        "bindings": {
            "pilot_evidence": {
                "path": pilot.DEFAULT_OUTPUT.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(pilot.DEFAULT_OUTPUT),
            },
            "pilot_checksums": {
                "path": pilot.CHECKSUMS_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(pilot.CHECKSUMS_PATH),
            },
            "runner": {
                "path": evidence["source"]["runner"],
                "sha256": evidence["source"]["runner_sha256"],
                "repository_commit": evidence["source"][
                    "repository_commit"
                ],
            },
        },
        "selection_disclosure": (
            "All three dose tuples and all four baselines were inspected "
            "on the disclosed pilot environment before the development "
            "matrix freeze. Low is retained as a negative control; medium "
            "and high are retained because they create increasing no-guard "
            "crossing burden while separating predictive pre-step "
            "containment from reactive post-step stopping. The pilot "
            "environment must be excluded from development."
        ),
        "claim_boundary": (
            "This outcome-free, one-environment design pilot selects stress "
            "doses only. It does not establish task utility, population "
            "generalization, attacked efficacy, hardware behavior, or "
            "physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    summary = build_summary(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        )
    )
    text = canonical_text(summary)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V14StressDesignFreezeError(
                f"stress design summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
