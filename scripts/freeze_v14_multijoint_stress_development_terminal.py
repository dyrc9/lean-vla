#!/usr/bin/env python3
"""Freeze the registered v14 stress-development result and diagnostics."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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
from scripts import run_v14_multijoint_stress_development as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v14_multijoint_stress_development_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:45+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-development-terminal-summary.v1"
)
THRESHOLDS_RAD = (0.0, 0.15, 0.16, 0.22, 0.30)
NEAR_LIMIT_DIAGNOSTIC_RAD = 0.30
CONTROL_PERIOD_SECONDS = 0.05


class V14StressDevelopmentTerminalError(RuntimeError):
    """Raised when retained stress evidence cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressDevelopmentTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _margin_matrix(rows: Any) -> np.ndarray:
    return runner.pilot.full_clean_margin_matrix(rows)


def _identity_diagnostic(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    all_errors: list[float] = []
    target_errors: list[float] = []
    near_limit_errors: list[float] = []
    far_from_limit_errors: list[float] = []
    disagreements: Counter[str] = Counter()
    per_environment: dict[str, float] = defaultdict(float)
    worst: dict[str, Any] | None = None
    trace_length_mismatch_count = 0
    for lane in lanes:
        no_guard = lane["baselines"]["no_guard"][
            "actual_joint_side_margins"
        ]
        shadow = lane["baselines"]["shadow_only"][
            "actual_joint_side_margins"
        ]
        if len(no_guard) != len(shadow):
            trace_length_mismatch_count += 1
            continue
        target_joint = int(lane["joint_index"])
        target_side = 0 if lane["side"] == "lower" else 1
        for step_index, (no_rows, shadow_rows) in enumerate(
            zip(no_guard, shadow, strict=True)
        ):
            no_matrix = _margin_matrix(no_rows)
            shadow_matrix = _margin_matrix(shadow_rows)
            errors = np.abs(no_matrix - shadow_matrix)
            minima = np.minimum(no_matrix, shadow_matrix)
            all_errors.extend(float(value) for value in errors.flat)
            target_errors.append(
                float(errors[target_joint, target_side])
            )
            near_limit_errors.extend(
                float(value)
                for value in errors[
                    minima < NEAR_LIMIT_DIAGNOSTIC_RAD
                ]
            )
            far_from_limit_errors.extend(
                float(value)
                for value in errors[
                    minima >= NEAR_LIMIT_DIAGNOSTIC_RAD
                ]
            )
            environment_id = str(lane["environment_id"])
            observed_max = float(np.max(errors))
            per_environment[environment_id] = max(
                per_environment[environment_id],
                observed_max,
            )
            index = np.unravel_index(
                int(np.argmax(errors)), errors.shape
            )
            if worst is None or observed_max > worst["error_rad"]:
                worst = {
                    "error_rad": observed_max,
                    "environment_id": environment_id,
                    "lane_id": str(lane["lane_id"]),
                    "step_index": step_index,
                    "joint_index": int(index[0]),
                    "side": "lower" if index[1] == 0 else "upper",
                    "no_guard_margin_rad": float(no_matrix[index]),
                    "shadow_only_margin_rad": float(
                        shadow_matrix[index]
                    ),
                }
            for threshold in THRESHOLDS_RAD:
                disagreements[str(threshold)] += int(
                    np.sum(
                        (no_matrix < threshold)
                        != (shadow_matrix < threshold)
                    )
                )
    errors_array = np.asarray(all_errors, dtype=np.float64)
    target_array = np.asarray(target_errors, dtype=np.float64)
    near_array = np.asarray(near_limit_errors, dtype=np.float64)
    far_array = np.asarray(far_from_limit_errors, dtype=np.float64)

    def stats(values: np.ndarray) -> dict[str, Any]:
        return {
            "count": int(values.size),
            "maximum_rad": (
                float(np.max(values)) if values.size else None
            ),
            "p99_rad": (
                float(np.quantile(values, 0.99))
                if values.size
                else None
            ),
        }

    return {
        "trace_length_mismatch_count": trace_length_mismatch_count,
        "all_joint_side_error": stats(errors_array),
        "target_joint_side_error": stats(target_array),
        "near_limit_under_0_30_rad_error": stats(near_array),
        "far_from_limit_error": stats(far_array),
        "threshold_classification_disagreement_count": {
            threshold: disagreements[threshold]
            for threshold in sorted(disagreements, key=float)
        },
        "all_registered_threshold_classifications_identical": (
            trace_length_mismatch_count == 0
            and not any(disagreements.values())
        ),
        "per_environment_maximum_error_rad": dict(
            sorted(per_environment.items())
        ),
        "worst_case": worst,
    }


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


def _latency_deadlines(
    lanes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    result = {}
    for baseline in ("shadow_only", "predictive_brake"):
        values = np.asarray(
            [
                float(value)
                for lane in lanes
                for value in lane["baselines"][baseline][
                    "screen_latency_seconds_values"
                ]
            ],
            dtype=np.float64,
        )
        misses = int(np.sum(values > CONTROL_PERIOD_SECONDS))
        result[baseline] = {
            "control_period_seconds": CONTROL_PERIOD_SECONDS,
            "sample_count": int(values.size),
            "deadline_miss_count": misses,
            "deadline_miss_rate": (
                misses / int(values.size) if values.size else None
            ),
        }
    return result


def _predictive_lane_states(
    lanes: list[Mapping[str, Any]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for lane in lanes:
        report = lane["baselines"]["predictive_brake"]
        triggered = int(report["trigger_count"]) > 0
        intervened = int(report["intervention_count"]) > 0
        deadlocked = int(report["deadlock_count"]) > 0
        counts[
            "triggered" if triggered else "not_triggered"
        ] += 1
        counts[
            ("intervened" if intervened else "not_intervened")
            + "_and_"
            + ("deadlocked" if deadlocked else "not_deadlocked")
        ] += 1
    return dict(sorted(counts.items()))


def _by_dose_summary(
    aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    result = {}
    for dose, values in aggregate["by_dose"].items():
        result[dose] = {
            baseline: _baseline_summary(values, baseline)
            for baseline in runner.pilot.BASELINES
        }
    return result


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = runner._output_root(protocol)
    evidence_path = root / "pilot_evidence.json"
    checksums_path = root / "SHA256SUMS"
    aggregate = evidence["aggregate"]
    identity = _identity_diagnostic(evidence["lanes"])
    baselines = {
        baseline: _baseline_summary(aggregate, baseline)
        for baseline in runner.pilot.BASELINES
    }
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_development_data_complete": evidence[
            "development_data_complete"
        ],
        "registered_gate_results": evidence["gate_results"],
        "diagnostic_classification": (
            "v14_multijoint_stress_development_registered_identity_"
            "nonpass_threshold_diagnostic_complete"
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
                for baseline in runner.pilot.BASELINES
            ),
            "joint_side_count_per_environment": 14,
            "dose_count": len(runner.pilot.DOSES),
        },
        "baselines": baselines,
        "by_dose": _by_dose_summary(aggregate),
        "predictive_lane_states": _predictive_lane_states(
            evidence["lanes"]
        ),
        "descriptive_contrasts": {
            "predictive_minus_shadow_crossing_count": (
                baselines["predictive_brake"]["crossing_count"]
                - baselines["shadow_only"]["crossing_count"]
            ),
            "predictive_minus_shadow_below_floor_count": (
                baselines["predictive_brake"]["below_floor_count"]
                - baselines["shadow_only"]["below_floor_count"]
            ),
            "predictive_minus_reactive_below_floor_count": (
                baselines["predictive_brake"]["below_floor_count"]
                - baselines["reactive_stop"]["below_floor_count"]
            ),
            "predictive_minus_reactive_executed_step_availability": (
                baselines["predictive_brake"][
                    "executed_step_availability"
                ]
                - baselines["reactive_stop"][
                    "executed_step_availability"
                ]
            ),
        },
        "no_guard_shadow_identity_diagnostic": identity,
        "latency_deadline_diagnostic": _latency_deadlines(
            evidence["lanes"]
        ),
        "runtime_warning_disclosure": {
            "contact_capacity_warning_observed_on_execution_stderr": True,
            "warning_count_checksum_bound": False,
            "interpretation": (
                "The execution console emitted MuJoCo ncon=5000 contact-"
                "arena warnings around environment setup. The retained "
                "evidence did not instrument the warning callback, so no "
                "count or active-stage attribution is claimed. A future "
                "qualification must pre-register prebinding and active "
                "contact-capacity audits."
            ),
        },
        "interpretation": {
            "registered_result_unchanged": True,
            "registered_nonpass_reason": (
                "The all-joint-side no-guard/shadow maximum error exceeds "
                "the frozen 0.001-rad identity tolerance."
            ),
            "descriptive_signal": (
                "Across this outcome-free development matrix, predictive "
                "braking removed all shadow crossings and below-floor "
                "values, whereas reactive stopping removed crossings only "
                "after below-floor exposure. Predictive braking also "
                "introduced deadlocks, deadline misses, and larger "
                "simulator constraint force."
            ),
            "threshold_diagnostic_does_not_revise_gate": True,
        },
        "next_qualification_contract": {
            "new_population_and_seeds_required": True,
            "method_and_analysis_must_be_frozen_before_execution": True,
            "retain_all_side_numeric_identity_as_diagnostic": True,
            "pre_register_threshold_classification_identity": True,
            "pre_register_contact_capacity_audits": True,
            "pre_register_50ms_deadline_miss_rate": True,
            "task_outcome_qualification_is_separate": True,
        },
        "claim_boundary": (
            "This terminal artifact preserves the registered integrity "
            "non-pass. Threshold identity and baseline contrasts are post-"
            "outcome diagnostics on an outcome-free development matrix. "
            "They do not establish confirmation, task utility, attacked "
            "efficacy, deployment, hardware behavior, actuator authority, "
            "or physical safety."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise V14StressDevelopmentTerminalError(
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
            raise V14StressDevelopmentTerminalError(
                f"stress terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
