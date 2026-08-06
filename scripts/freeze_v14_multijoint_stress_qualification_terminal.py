#!/usr/bin/env python3
"""Freeze held-out v14 stress qualification without revising its non-pass."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v14_multijoint_stress_qualification as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v14_multijoint_stress_qualification_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:55+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-qualification-terminal-summary.v1"
)
BOOTSTRAP_SEED = 20260731
BOOTSTRAP_RESAMPLES = 20_000


class V14StressQualificationTerminalError(RuntimeError):
    """Raised when qualification evidence cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressQualificationTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _baseline_summary(
    aggregate: Mapping[str, Any],
    baseline: str,
) -> dict[str, Any]:
    fields = (
        "lane_count",
        "trigger_count",
        "trigger_lane_count",
        "trigger_lane_rate",
        "intervention_count",
        "intervention_lane_count",
        "intervention_lane_rate",
        "deadlock_count",
        "deadlock_lane_count",
        "deadlock_lane_rate",
        "reactive_stop_count",
        "reactive_stop_lane_count",
        "reactive_stop_lane_rate",
        "below_floor_count",
        "below_floor_side_rate",
        "crossing_count",
        "crossing_side_rate",
        "minimum_margin_rad",
        "executed_step_availability",
        "screen_latency_sample_count",
        "screen_latency_seconds_mean",
        "screen_latency_seconds_p50",
        "screen_latency_seconds_p95",
        "screen_latency_seconds_p99",
        "screen_latency_seconds_max",
        "maximum_abs_constraint_force",
    )
    return {
        field: aggregate[f"{baseline}_{field}"] for field in fields
    }


def _low_control_failures(
    lanes: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures = []
    for lane in lanes:
        no_guard = lane["baselines"]["no_guard"]
        if (
            lane["dose"]["dose"] != "low"
            or int(no_guard["below_floor_count"]) == 0
        ):
            continue
        failures.append(
            {
                "environment_id": str(lane["environment_id"]),
                "suite": str(lane["suite"]),
                "task_id": int(lane["task_id"]),
                "init_state_id": int(lane["init_state_id"]),
                "joint_index": int(lane["joint_index"]),
                "side": str(lane["side"]),
                "no_guard": {
                    field: no_guard[field]
                    for field in (
                        "below_floor_count",
                        "crossing_count",
                        "minimum_margin_rad",
                        "executed_step_count",
                        "maximum_abs_constraint_force",
                    )
                },
                "reactive_stop": {
                    field: lane["baselines"]["reactive_stop"][field]
                    for field in (
                        "below_floor_count",
                        "crossing_count",
                        "minimum_margin_rad",
                        "executed_step_count",
                        "maximum_abs_constraint_force",
                    )
                },
                "predictive_brake": {
                    field: lane["baselines"]["predictive_brake"][field]
                    for field in (
                        "below_floor_count",
                        "crossing_count",
                        "minimum_margin_rad",
                        "trigger_count",
                        "intervention_count",
                        "deadlock_count",
                        "executed_step_count",
                        "maximum_abs_constraint_force",
                    )
                },
            }
        )
    return failures


def _cluster_bootstrap(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    by_environment: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for lane in lanes:
        by_environment[str(lane["environment_id"])].append(lane)
    environment_ids = sorted(by_environment)
    rows = []
    for environment_id in environment_ids:
        environment_lanes = by_environment[environment_id]
        lane_count = len(environment_lanes)
        expected_steps = (
            lane_count * runner.development.pilot.HORIZON_STEPS
        )
        rows.append(
            {
                "predictive_minus_shadow_crossings_per_lane": sum(
                    int(lane["baselines"]["predictive_brake"][
                        "crossing_count"
                    ])
                    - int(lane["baselines"]["shadow_only"][
                        "crossing_count"
                    ])
                    for lane in environment_lanes
                )
                / lane_count,
                "predictive_minus_reactive_below_floor_per_lane": sum(
                    int(lane["baselines"]["predictive_brake"][
                        "below_floor_count"
                    ])
                    - int(lane["baselines"]["reactive_stop"][
                        "below_floor_count"
                    ])
                    for lane in environment_lanes
                )
                / lane_count,
                "predictive_minus_reactive_step_availability": (
                    sum(
                        int(lane["baselines"]["predictive_brake"][
                            "executed_step_count"
                        ])
                        - int(lane["baselines"]["reactive_stop"][
                            "executed_step_count"
                        ])
                        for lane in environment_lanes
                    )
                    / expected_steps
                ),
                "predictive_deadlock_lane_rate": sum(
                    int(
                        int(lane["baselines"]["predictive_brake"][
                            "deadlock_count"
                        ])
                        > 0
                    )
                    for lane in environment_lanes
                )
                / lane_count,
            }
        )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    result = {}
    for name in rows[0]:
        values = np.asarray(
            [float(row[name]) for row in rows], dtype=np.float64
        )
        indexes = rng.integers(
            0,
            len(values),
            size=(BOOTSTRAP_RESAMPLES, len(values)),
        )
        resampled = np.mean(values[indexes], axis=1)
        result[name] = {
            "estimate": float(np.mean(values)),
            "environment_cluster_bootstrap_95_ci": [
                float(np.quantile(resampled, 0.025)),
                float(np.quantile(resampled, 0.975)),
            ],
            "environment_count": len(values),
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        }
    return result


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = runner._output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    aggregate = evidence["analysis"]["aggregate"]
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.development.pilot.BASELINES
    }
    by_dose = {
        dose: {
            baseline: _baseline_summary(values, baseline)
            for baseline in runner.development.pilot.BASELINES
        }
        for dose, values in aggregate["by_dose"].items()
    }
    failed_gates = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    integrity_names = (
        "environment_count",
        "environment_lane_coverage",
        "stress_lane_count",
        "baseline_lane_count",
        "restore_identity",
        "zero_policy_or_outcome_fields",
        "exact_action_identity",
        "threshold_classification_identity",
        "active_contact_capacity_warning_free",
        "active_contact_capacity_unsaturated",
    )
    mechanism_names = (
        "stress_activation",
        "predictive_crossing_containment",
        "predictive_floor_containment",
        "reactive_crossing_containment",
        "reactive_post_step_exposure_observed",
        "predictive_availability_not_below_reactive",
    )
    timing_names = (
        "predictive_latency_p95",
        "predictive_deadline_miss_rate",
    )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": evidence[
            "qualification_pass"
        ],
        "registered_gate_results": evidence["gate_results"],
        "failed_registered_gates": failed_gates,
        "diagnostic_classification": (
            "v14_multijoint_stress_qualification_registered_"
            "negative_control_nonpass_core_axes_complete"
        ),
        "bindings": {
            "protocol": {
                "path": runner.DEFAULT_PROTOCOL.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(runner.DEFAULT_PROTOCOL),
            },
            "evidence": {
                "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(evidence_path),
            },
            "checksums": {
                "path": checksums_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksums_path),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "environment_count": aggregate["environment_count"],
            "suite_count": len(
                {str(lane["suite"]) for lane in evidence["lanes"]}
            ),
            "stress_lane_count": aggregate["stress_lane_count"],
            "baseline_lane_count": sum(
                aggregate[f"{baseline}_lane_count"]
                for baseline in runner.development.pilot.BASELINES
            ),
            "new_task_init_pairs": True,
            "environment_seed": protocol["selection"][
                "environment_seed"
            ],
        },
        "registered_axes": {
            "integrity_complete": all(
                evidence["gate_results"][name]
                for name in integrity_names
            ),
            "core_mechanism_gates_complete": all(
                evidence["gate_results"][name]
                for name in mechanism_names
            ),
            "system_timing_gates_complete": all(
                evidence["gate_results"][name]
                for name in timing_names
            ),
            "low_negative_control_complete": evidence["gate_results"][
                "low_negative_control"
            ],
            "overall_pass_is_conjunction": True,
        },
        "baselines": baselines,
        "by_dose": by_dose,
        "low_negative_control_failures": _low_control_failures(
            evidence["lanes"]
        ),
        "paired_environment_cluster_bootstrap": _cluster_bootstrap(
            evidence["lanes"]
        ),
        "threshold_identity": evidence["analysis"][
            "registered_threshold_identity"
        ],
        "all_side_numeric_identity_diagnostic": evidence["analysis"][
            "all_side_numeric_identity_diagnostic"
        ],
        "contact_capacity": evidence["analysis"]["contact_capacity"],
        "predictive_latency_deadline": evidence["analysis"][
            "predictive_latency_deadline"
        ],
        "interpretation": {
            "registered_result_unchanged": True,
            "overall_nonpass_reason": (
                "Two of 252 held-out low-dose lanes crossed because the "
                "environment-specific constraint dynamics made the planned "
                "negative control active; the frozen conjunction therefore "
                "does not pass."
            ),
            "core_axis_result": (
                "All registered integrity, active-contact, stress-"
                "activation, predictive containment, reactive comparison, "
                "availability, and timing gates passed on unseen task/init "
                "pairs. This axis report does not replace the overall "
                "registered non-pass."
            ),
            "system_costs": (
                "Predictive containment retains substantial deadlock, "
                "deadline-miss, and simulator-constraint-force burdens."
            ),
        },
        "next_experiment": {
            "task_outcome_utility_qualification_required": True,
            "deadlock_recovery_factor_required": True,
            "do_not_relabel_low_dose_post_outcome": True,
            "preserve_prebinding_contact_saturation_disclosure": True,
        },
        "claim_boundary": (
            "The registered held-out qualification remains non-pass. Core-"
            "axis and bootstrap summaries are diagnostic decompositions of "
            "the frozen evidence. The experiment contains no policy or task "
            "outcome and cannot establish task utility, attacked efficacy, "
            "deployment, hardware behavior, actuator authority, or physical "
            "safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V14StressQualificationTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
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
            raise V14StressQualificationTerminalError(
                f"qualification terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
