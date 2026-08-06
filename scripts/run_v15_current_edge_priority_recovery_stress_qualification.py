#!/usr/bin/env python3
"""Run held-out v15.2 recovery stress qualification."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v15_current_edge_priority_recovery_stress_calibration as calibration  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-qualification-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_2_recovery_stress_qualification"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_protocol.json"
)


class V15RecoveryStressQualificationError(RuntimeError):
    """Raised when held-out qualification differs from its protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15RecoveryStressQualificationError(
            "qualification output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15RecoveryStressQualificationError(
            "qualification output root resolves to repository"
        )
    return root


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "held_out_mechanism_claim": True,
        "task_utility_claim": False,
        "real_time_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["doses"]
        != [dict(row) for row in calibration.v14.pilot.DOSES]
        or protocol["design"]["baselines"]
        != list(calibration.BASELINES)
        or protocol["design"]["horizon_steps"]
        != calibration.v14.pilot.HORIZON_STEPS
    ):
        raise V15RecoveryStressQualificationError(
            "unsupported or unauthorized qualification protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15RecoveryStressQualificationError(
                f"qualification source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V15RecoveryStressQualificationError(
                "qualification predecessor binding differs: "
                + str(binding["path"])
            )


def preflight(
    protocol: Mapping[str, Any],
    *,
    gpu: int,
) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15RecoveryStressQualificationError as exc:
        blockers.append(str(exc))
    if calibration._git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh qualification output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.2-current-edge-"
            "priority-recovery-stress-qualification-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "expected_stress_lane_count": protocol["gates"][
            "expected_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_baseline_lane_count"
        ],
        "output_root_absent": not output_root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "real_time_claim_authorized": False,
    }


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    maximum_no_guard_shadow_error: float,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    calibration_metrics, calibration_gates = calibration._analyze(
        protocol,
        rows,
        restore_failure_count=restore_failure_count,
        maximum_no_guard_shadow_error=maximum_no_guard_shadow_error,
        contact_reports=contact_reports,
    )
    aggregate = calibration_metrics["aggregate"]
    recovery = calibration_metrics["recovery"]
    gates = protocol["gates"]
    thresholds = calibration.audit._threshold_identity(
        rows,
        thresholds=[float(value) for value in gates["thresholds_rad"]],
    )
    deadline_100ms = calibration.audit._deadline_report(
        rows,
        baseline="v15_2_recovery",
        deadline_seconds=float(gates["latency_budget_seconds"]),
    )
    medium = aggregate["by_dose"]["medium"]
    high = aggregate["by_dose"]["high"]
    no_guard_stress_crossing_count = int(
        medium["no_guard_crossing_count"]
        + high["no_guard_crossing_count"]
    )
    v14_force = float(
        aggregate["v14_predictive_brake_maximum_abs_constraint_force"]
    )
    v15_force = float(
        aggregate["v15_2_recovery_maximum_abs_constraint_force"]
    )
    force_ratio = v15_force / v14_force if v14_force > 0 else None
    v15_p95 = aggregate[
        "v15_2_recovery_screen_latency_seconds_p95"
    ]
    v15_max = aggregate[
        "v15_2_recovery_screen_latency_seconds_max"
    ]
    retained_integrity_gates = (
        "environment_count",
        "environment_lane_coverage",
        "stress_lane_count",
        "baseline_lane_count",
        "restore_identity",
        "zero_policy_or_outcome_fields",
        "expected_total_baseline_lane_count",
        "exact_action_identity",
        "v15_2_schema_identity",
        "v15_2_candidate_priority_identity",
        "active_contact_capacity_warning_free",
        "active_contact_capacity_unsaturated",
    )
    gate_results = {
        name: calibration_gates[name] for name in retained_integrity_gates
    }
    gate_results.update(
        {
            "threshold_classification_identity": (
                thresholds["trace_length_mismatch_count"] == 0
                and not any(
                    thresholds[
                        "threshold_classification_disagreement_count"
                    ].values()
                )
            ),
            "stress_activation": (
                no_guard_stress_crossing_count
                >= gates["stress_activation_no_guard_crossing_count_min"]
            ),
            "v14_deadlock_activation": (
                recovery["v14_predictive_deadlock_lane_count"]
                >= gates["v14_predictive_deadlock_lane_count_min"]
            ),
            "v15_2_crossing_containment": (
                aggregate["v15_2_recovery_crossing_count"]
                <= gates["v15_2_crossing_count_max"]
            ),
            "v15_2_floor_containment": (
                aggregate["v15_2_recovery_below_floor_count"]
                <= gates["v15_2_below_floor_count_max"]
            ),
            "v15_2_zero_residual_deadlock": (
                recovery["v15_2_residual_deadlock_lane_count"]
                <= gates["v15_2_residual_deadlock_lane_count_max"]
            ),
            "v15_2_recovery_prevention_identity": (
                gates["v15_2_prevention_identity_required"] is True
                and recovery["paired_deadlock_lane_identity"] is True
                and recovery["v14_baseline_would_deadlock_count"]
                == recovery["recovery_prevented_deadlock_count"]
                and recovery["v15_2_v14_would_deadlock_lane_count"]
                == recovery[
                    "v15_2_recovery_prevented_deadlock_lane_count"
                ]
            ),
            "v15_2_selected_recovery_floor_containment": (
                recovery["selected_floor_violation_count"]
                <= gates["v15_2_selected_floor_violation_count_max"]
            ),
            "v15_2_availability_not_below_v14": (
                aggregate[
                    "v15_2_recovery_executed_step_availability"
                ]
                - aggregate[
                    "v14_predictive_brake_executed_step_availability"
                ]
                >= gates["v15_2_minus_v14_availability_min"]
            ),
            "v15_2_prediction_execution_error": (
                recovery["maximum_prediction_execution_error_rad"]
                <= gates[
                    "maximum_prediction_execution_error_rad_max"
                ]
            ),
            "v15_2_absolute_force_envelope": (
                v15_force
                <= gates["v15_2_maximum_abs_constraint_force_max"]
            ),
            "v15_2_relative_force_envelope": (
                force_ratio is not None
                and force_ratio
                <= gates["v15_2_to_v14_maximum_force_ratio_max"]
            ),
            "v15_2_latency_p95": (
                v15_p95 is not None
                and v15_p95
                <= gates["v15_2_screen_latency_p95_seconds_max"]
            ),
            "v15_2_latency_max": (
                v15_max is not None
                and v15_max
                <= gates["v15_2_screen_latency_seconds_max"]
            ),
            "v15_2_100ms_deadline_miss_rate": (
                deadline_100ms["miss_rate"] is not None
                and deadline_100ms["miss_rate"]
                <= gates["v15_2_100ms_deadline_miss_rate_max"]
            ),
        }
    )
    metrics = {
        **calibration_metrics,
        "registered_threshold_identity": thresholds,
        "stress_activation_no_guard_crossing_count": (
            no_guard_stress_crossing_count
        ),
        "force_comparison": {
            "v14_predictive_maximum_abs_constraint_force": v14_force,
            "v15_2_recovery_maximum_abs_constraint_force": v15_force,
            "v15_2_to_v14_ratio": force_ratio,
        },
        "v15_2_latency_budget": deadline_100ms,
        "raw_all_side_numeric_identity_diagnostic": {
            "registered_as_gate": False,
            "maximum_error_rad": maximum_no_guard_shadow_error,
            "within_legacy_0_001_rad_tolerance": (
                maximum_no_guard_shadow_error <= 0.001
            ),
        },
        "fifty_ms_deadline_diagnostic": (
            calibration_metrics["latency_deadlines"]["v15_2_recovery"]
        ),
    }
    return metrics, gate_results


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15RecoveryStressQualificationError(
            "qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15RecoveryStressQualificationError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = calibration.audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    maximum_error = 0.0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, error, contacts = (
                calibration._run_audited_environment(
                    spec,
                    gpu=gpu,
                    warnings=warnings,
                )
            )
            rows.extend(environment_rows)
            contact_reports.append(contacts)
            restore_failures += failures
            maximum_error = max(maximum_error, error)
    finally:
        mujoco.set_mju_user_warning(previous_warning_callback)
    metrics, gate_results = _analyze(
        protocol,
        rows,
        restore_failure_count=restore_failures,
        maximum_no_guard_shadow_error=maximum_error,
        contact_reports=contact_reports,
    )
    qualification_pass = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if qualification_pass
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": qualification_pass,
        "held_out_mechanism_claim_authorized": qualification_pass,
        "task_utility_claim_authorized": False,
        "real_time_claim_authorized": False,
        "protocol": {
            "path": protocol_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "protocol_id": protocol["protocol_id"],
        "integrity": {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        },
        "gate_results": gate_results,
        "analysis": metrics,
        "lanes": rows,
        "warning_messages": warnings.records,
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "qualification_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return {
        "classification": evidence["classification"],
        "qualification_pass": qualification_pass,
        "environment_count": metrics["aggregate"]["environment_count"],
        "stress_lane_count": metrics["aggregate"]["stress_lane_count"],
        "baseline_lane_count": sum(
            metrics["aggregate"][f"{baseline}_lane_count"]
            for baseline in calibration.BASELINES
        ),
        "evidence_path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "checksums_path": checksums_path.relative_to(REPO_ROOT).as_posix(),
    }


def validate_results(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15RecoveryStressQualificationError(
            "qualification evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15RecoveryStressQualificationError(
            "qualification checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
        or evidence["integrity"]
        != {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        }
    ):
        raise V15RecoveryStressQualificationError(
            "qualification evidence identity differs"
        )
    recorded = evidence["analysis"]
    metrics, gates = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(
            recorded["aggregate"]["restore_failure_count"]
        ),
        maximum_no_guard_shadow_error=float(
            recorded["aggregate"][
                "no_guard_shadow_maximum_side_error_rad"
            ]
        ),
        contact_reports=recorded["contact_reports"],
    )
    if (
        metrics != recorded
        or gates != evidence["gate_results"]
        or evidence["qualification_pass"] is not all(gates.values())
    ):
        raise V15RecoveryStressQualificationError(
            "qualification analysis is stale"
        )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=2)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(protocol, gpu=args.gpu)
    elif args.execute:
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    else:
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
