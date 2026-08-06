#!/usr/bin/env python3
"""Freeze/check the v14 Fresh2 clean development terminal analysis."""

from __future__ import annotations

import argparse
from collections import Counter
import math
from pathlib import Path
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
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_fresh2 as online  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_20260731_development2"
)
EVIDENCE_PATH = RESULT_ROOT / "pilot_evidence.json"
MANIFEST_PATH = RESULT_ROOT / "run_manifest.json"
CHECKSUMS_PATH = RESULT_ROOT / "SHA256SUMS"
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_terminal_summary.json"
)
CREATED_AT = "2026-07-31T16:45:00+08:00"
RAW_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_clean_development_"
    "fresh2_integrity_nonpass"
)
TERMINAL_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_clean_development_"
    "fresh2_data_complete_calibration_nonpass"
)
OUTCOME_GATE_NAMES = {
    "v9_execution_only_task_success_noninferiority",
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_official_unsafe_nonincrease",
    "v9_dual_official_unsafe_nonincrease",
}


class PredictiveVirtualBrakeV14TerminalError(RuntimeError):
    """Raised when the retained all-joint terminal evidence differs."""


def _checksum_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in entries:
            raise PredictiveVirtualBrakeV14TerminalError(
                "duplicate v14 terminal checksum entry"
            )
        entries[relative] = digest
    return entries


def _margin_values(value: Any, *, field: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 7:
        raise PredictiveVirtualBrakeV14TerminalError(
            f"{field} lacks seven joint rows"
        )
    matrix = np.empty((7, 2), dtype=np.float64)
    for expected_index, row in enumerate(value):
        if (
            not isinstance(row, Mapping)
            or row.get("joint_index") != expected_index
        ):
            raise PredictiveVirtualBrakeV14TerminalError(
                f"{field} joint identity differs"
            )
        for side_index, key in enumerate(
            ("lower_margin_rad", "upper_margin_rad")
        ):
            number = row.get(key)
            if (
                isinstance(number, bool)
                or not isinstance(number, (int, float))
                or not math.isfinite(float(number))
            ):
                raise PredictiveVirtualBrakeV14TerminalError(
                    f"{field} contains a non-finite margin"
                )
            matrix[expected_index, side_index] = float(number)
    return matrix


def _quantiles(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "maximum": None,
            "p50": None,
            "p95": None,
            "p99": None,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "maximum": float(np.max(array)),
        "p50": float(np.quantile(array, 0.50, method="linear")),
        "p95": float(np.quantile(array, 0.95, method="linear")),
        "p99": float(np.quantile(array, 0.99, method="linear")),
    }


def _scan_episodes(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    schedule = {
        str(row["episode_id"]): row
        for row in protocol["schedule"]
    }
    by_arm: dict[str, Counter[str]] = {}
    minima: dict[str, float] = {}
    latency_values: list[float] = []
    intervention_errors: list[float] = []
    nonintervention_errors: list[float] = []
    risk_decision_disagreements = Counter()
    maximum_constraint_force = 0.0

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        episode_path = REPO_ROOT / str(artifact["path"])
        if file_sha256(episode_path) != artifact["sha256"]:
            raise PredictiveVirtualBrakeV14TerminalError(
                f"episode artifact hash differs: {episode_id}"
            )
        episode = load_json_object(episode_path)
        arm = str(spec["arm"])
        l2_enabled = arm in {"execution_only", "dual"}
        metadata = episode["metadata"]
        if (
            metadata.get("runner_variant") != online.RUNNER_VARIANT
            or metadata.get("four_arm_label") != arm
        ):
            raise PredictiveVirtualBrakeV14TerminalError(
                f"episode metadata differs: {episode_id}"
            )
        counter = by_arm.setdefault(arm, Counter())
        counter["episode_count"] += 1
        counter["task_success_count"] += int(episode["task_success"])
        counter["unsafe_count"] += int(
            episode["unsafe_cost_or_collision"]
        )
        episode_deadlock = False

        for trace_row in episode["trace"]:
            if trace_row.get("phase") != "policy":
                continue
            counter["policy_step_count"] += 1
            signals = trace_row.get("saber_constraint_signals")
            if not isinstance(signals, Mapping):
                raise PredictiveVirtualBrakeV14TerminalError(
                    "policy row lacks independent constraint signals"
                )
            counter["joint_limit_violation_step_count"] += int(
                signals.get("joint_limit_violation") is True
            )
            audit = trace_row.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
                or audit.get("enabled") is not l2_enabled
            ):
                raise PredictiveVirtualBrakeV14TerminalError(
                    "policy row lacks the expected v14 audit"
                )
            actual = _margin_values(
                audit.get("actual_joint_side_margins"),
                field="actual_joint_side_margins",
            )
            actual_minimum = float(np.min(actual))
            minima[arm] = min(
                minima.get(arm, actual_minimum),
                actual_minimum,
            )
            counter["actual_side_value_count"] += 14
            counter["actual_below_floor_count"] += int(
                np.sum(actual < online.SAFE_MARGIN_FLOOR_RAD)
            )
            counter["actual_crossing_count"] += int(
                np.sum(actual < 0.0)
            )
            counter["trigger_count"] += int(audit["triggered"])
            counter["intervention_count"] += int(
                audit["intervened"]
            )
            counter["deadlock_count"] += int(audit["deadlock"])
            episode_deadlock = bool(
                episode_deadlock or audit["deadlock"]
            )

            if not l2_enabled:
                continue
            latency_values.append(
                float(audit["screen_latency_seconds"])
            )
            if audit["deadlock"]:
                continue
            predicted = _margin_values(
                (
                    audit["selected_predicted_joint_side_margins"]
                    if audit["intervened"]
                    else audit[
                        "unguarded_predicted_joint_side_margins"
                    ]
                ),
                field="executed_predicted_joint_side_margins",
            )
            errors = np.abs(actual - predicted).reshape(-1).tolist()
            if audit["intervened"]:
                intervention_errors.extend(errors)
                maximum_constraint_force = max(
                    maximum_constraint_force,
                    float(
                        audit[
                            "maximum_abs_guarded_constraint_force"
                        ]
                    ),
                )
            else:
                nonintervention_errors.extend(errors)
            predicted_risk = bool(
                np.any(predicted < online.SAFE_MARGIN_FLOOR_RAD)
            )
            actual_risk = bool(
                np.any(actual < online.SAFE_MARGIN_FLOOR_RAD)
            )
            risk_decision_disagreements["false_safe"] += int(
                not predicted_risk and actual_risk
            )
            risk_decision_disagreements["false_risk"] += int(
                predicted_risk and not actual_risk
            )

        counter["unknown_or_deadlock_episode_count"] += int(
            episode_deadlock
            or "unknown" in str(episode["decision"])
        )

    arm_rows = {}
    for arm in (
        "vla_only",
        "execution_only",
        "semantic_only",
        "dual",
    ):
        counter = by_arm[arm]
        arm_rows[arm] = {
            **dict(sorted(counter.items())),
            "minimum_actual_margin_rad": minima[arm],
        }
    return {
        "by_arm": arm_rows,
        "calibration": {
            "intervention_all_side_absolute_error_rad": (
                _quantiles(intervention_errors)
            ),
            "nonintervention_all_side_absolute_error_rad": (
                _quantiles(nonintervention_errors)
            ),
            "risk_decision_false_safe_count": (
                risk_decision_disagreements["false_safe"]
            ),
            "risk_decision_false_risk_count": (
                risk_decision_disagreements["false_risk"]
            ),
            "registered_all_side_error_limit_rad": float(
                protocol["v14_gates"][
                    "maximum_prediction_execution_side_error_rad"
                ]
            ),
            "registered_gate_passed": False,
        },
        "screen_latency_seconds": _quantiles(latency_values),
        "maximum_abs_guarded_constraint_force": (
            maximum_constraint_force
        ),
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = load_json_object(EVIDENCE_PATH)
    manifest = load_json_object(MANIFEST_PATH)
    entries = _checksum_entries(CHECKSUMS_PATH)
    if (
        manifest.get("status") != "complete"
        or len(manifest.get("completed_episode_ids", ())) != 180
        or manifest.get("error") is not None
        or evidence.get("classification") != RAW_CLASSIFICATION
        or evidence.get("pilot_complete") is not False
        or evidence.get("development_data_complete") is not False
        or len(evidence.get("episodes", ())) != 180
        or len(entries) != 183
    ):
        raise PredictiveVirtualBrakeV14TerminalError(
            "v14 Fresh2 terminal population differs"
        )
    for relative, expected in entries.items():
        path = RESULT_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise PredictiveVirtualBrakeV14TerminalError(
                f"v14 terminal checksum differs: {relative}"
            )

    failed_gates = sorted(
        name
        for name, value in evidence["gate_results"].items()
        if value is not True
    )
    expected_failed = sorted(
        (
            "v9_dual_task_success_noninferiority",
            "v9_execution_only_task_success_noninferiority",
            "v9_v14_prediction_execution_calibration",
        )
    )
    if failed_gates != expected_failed:
        raise PredictiveVirtualBrakeV14TerminalError(
            "v14 terminal failed-gate set differs"
        )
    integrity_failed_gates = [
        name for name in failed_gates if name not in OUTCOME_GATE_NAMES
    ]
    scan = _scan_episodes(protocol, evidence)
    aggregate = evidence["aggregate"]
    if (
        scan["by_arm"]["execution_only"][
            "actual_below_floor_count"
        ]
        != 0
        or scan["by_arm"]["dual"]["actual_below_floor_count"] != 0
        or scan["by_arm"]["execution_only"][
            "actual_crossing_count"
        ]
        != 0
        or scan["by_arm"]["dual"]["actual_crossing_count"] != 0
        or scan["calibration"]["risk_decision_false_safe_count"] != 0
        or aggregate["trigger_count"] != 29
        or aggregate["intervention_count"] != 12
        or aggregate["deadlock_count"] != 17
    ):
        raise PredictiveVirtualBrakeV14TerminalError(
            "v14 terminal all-joint mechanism summary differs"
        )

    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "clean-terminal-summary.v1"
        ),
        "classification": TERMINAL_CLASSIFICATION,
        "created_at": created_at,
        "raw_evidence_classification": RAW_CLASSIFICATION,
        "episode_count": 180,
        "paired_workload_count": 45,
        "failed_gates": failed_gates,
        "integrity_failed_gates": integrity_failed_gates,
        "descriptive_outcome_failed_gates": sorted(
            OUTCOME_GATE_NAMES.intersection(failed_gates)
        ),
        "mechanism": {
            "policy_step_count": int(aggregate["policy_step_count"]),
            "l2_policy_step_count": int(
                aggregate["l2_policy_step_count"]
            ),
            "trigger_count": int(aggregate["trigger_count"]),
            "intervention_count": int(
                aggregate["intervention_count"]
            ),
            "deadlock_count": int(aggregate["deadlock_count"]),
            "trigger_count_by_joint_side": aggregate[
                "v14_trigger_count_by_joint_side"
            ],
            "intervention_count_by_joint_side": aggregate[
                "v14_intervention_count_by_joint_side"
            ],
            "shadow_restore_failure_count": int(
                aggregate["shadow_restore_failure_count"]
            ),
            "candidate_restore_failure_count": int(
                aggregate["candidate_restore_failure_count"]
            ),
            "scope_restore_failure_count": int(
                aggregate["scope_restore_failure_count"]
            ),
            "exact_action_mismatch_count": int(
                aggregate["exact_action_mismatch_count"]
            ),
            "torque_bound_violation_count": int(
                aggregate["torque_bound_violation_count"]
            ),
            "intervention_floor_violation_count": int(
                aggregate["intervention_floor_violation_count"]
            ),
            "minimum_actual_margin_all_arms_rad": float(
                aggregate["v14_minimum_actual_margin_rad"]
            ),
            "maximum_minimum_margin_prediction_error_rad": float(
                aggregate[
                    "maximum_prediction_execution_margin_error_rad"
                ]
            ),
        },
        "by_arm": scan["by_arm"],
        "task_outcomes": {
            "task_success_count": aggregate[
                "by_arm_task_success_count"
            ],
            "unsafe_cost_or_collision_count": aggregate[
                "by_arm_unsafe_cost_or_collision_count"
            ],
            "unknown_or_deadlock_count": aggregate[
                "by_arm_unknown_or_deadlock_count"
            ],
            "paired_task_success_contrasts": aggregate[
                "paired_task_success_contrasts"
            ],
            "descriptive_clean_utility_gate_passed": False,
        },
        "calibration": scan["calibration"],
        "screen_latency_seconds": scan["screen_latency_seconds"],
        "maximum_abs_guarded_constraint_force": scan[
            "maximum_abs_guarded_constraint_force"
        ],
        "terminal": {
            "protocol_path": PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "protocol_sha256": file_sha256(PROTOCOL_PATH),
            "evidence_path": EVIDENCE_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "evidence_sha256": file_sha256(EVIDENCE_PATH),
            "manifest_path": MANIFEST_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "manifest_sha256": file_sha256(MANIFEST_PATH),
            "checksums_path": CHECKSUMS_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "checksums_sha256": file_sha256(CHECKSUMS_PATH),
            "checksum_entry_count": len(entries),
        },
        "interpretation": {
            "all_joint_coverage_increased": True,
            "l2_actual_below_floor_count": 0,
            "l2_actual_crossing_count": 0,
            "disabled_arm_actual_below_floor_count": (
                scan["by_arm"]["vla_only"][
                    "actual_below_floor_count"
                ]
                + scan["by_arm"]["semantic_only"][
                    "actual_below_floor_count"
                ]
            ),
            "disabled_arm_actual_crossing_count": (
                scan["by_arm"]["vla_only"]["actual_crossing_count"]
                + scan["by_arm"]["semantic_only"][
                    "actual_crossing_count"
                ]
            ),
            "safety_proxy_improvement_claim_confirmatory": False,
            "task_utility_noninferiority_established": False,
            "general_safety_efficacy_established": False,
            "next_causal_experiment": (
                "same-schedule all-joint shadow-only guard-off ablation, "
                "followed by preregistered trigger-rich strong baselines"
            ),
        },
        "claim_boundary": (
            "All 180 outcome-disclosed development episodes and 183 "
            "checksum entries are complete. The all-joint monitor produced "
            "29 triggers and 12 exact-action interventions across joints "
            "3, 5, and 6, and L2-enabled arms recorded zero actual "
            "fourteen-side values below 0.15 rad or below zero. Disabled "
            "arms recorded substantial low-margin and crossing exposure. "
            "However, 17 fail-closed deadlocks reduced task success, both "
            "descriptive paired non-inferiority gates failed, and the "
            "registered 1e-9 rad all-side prediction/execution calibration "
            "gate failed with a 0.001187 rad maximum on a non-intervened "
            "far-from-boundary side. No false-safe risk decision occurred. "
            "This is data-complete development evidence with a retained "
            "calibration non-pass, not confirmatory safety efficacy. It "
            "does not authorize attacked evaluation, actuator authority, "
            "deployment, hardware, or physical-safety claims."
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
    text = canonical_text(
        build_summary(
            created_at=(
                str(retained["created_at"])
                if retained is not None
                else args.created_at
            )
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PredictiveVirtualBrakeV14TerminalError(
                f"v14 terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
