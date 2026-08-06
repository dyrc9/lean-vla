#!/usr/bin/env python3
"""Run the outcome-disclosed v15.2 recovery stress calibration."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator, Mapping

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
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as recovery  # noqa: E402
from scripts import run_v14_multijoint_stress_development as v14  # noqa: E402
from scripts import run_v14_multijoint_stress_qualification as audit  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-calibration-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-calibration-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_2_recovery_stress_calibration"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_calibration_protocol.json"
)
BASELINES = (
    "no_guard",
    "shadow_only",
    "v14_predictive_brake",
    "v15_2_recovery",
)
RECOVERY_PRIORITY = [
    "v14_frozen_guard_margins",
    "current_edge",
    "floor_edge",
]


class V15RecoveryStressCalibrationError(RuntimeError):
    """Raised when calibration differs from its frozen protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15RecoveryStressCalibrationError(
            "calibration output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15RecoveryStressCalibrationError(
            "calibration output root resolves to repository"
        )
    return root


def _git_status() -> str:
    completed = subprocess.run(
        (
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryStressCalibrationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
        "qualification_gate_selection": True,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 12
        or protocol["design"]["doses"]
        != [dict(row) for row in v14.pilot.DOSES]
        or protocol["design"]["baselines"] != list(BASELINES)
        or protocol["design"]["horizon_steps"]
        != v14.pilot.HORIZON_STEPS
    ):
        raise V15RecoveryStressCalibrationError(
            "unsupported or unauthorized calibration protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15RecoveryStressCalibrationError(
                f"calibration source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V15RecoveryStressCalibrationError(
                "calibration predecessor binding differs: "
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
    except V15RecoveryStressCalibrationError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh calibration output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.2-current-edge-"
            "priority-recovery-stress-calibration-preflight.v1"
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
        "qualification_claim_authorized": False,
    }


def _run_recovery_screened(env: Any) -> dict[str, Any]:
    wrapper = recovery.MultiJointCurrentEdgePriorityRecoveryEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=None,
    )
    matrices = []
    latencies = []
    maximum_constraint_force = 0.0
    for _ in range(v14.pilot.HORIZON_STEPS):
        # Stress calibration intentionally discards reward, done, and info.
        wrapper.step(v14.pilot.HOLD_ACTION)
        observation = wrapper.observations[-1]
        latencies.append(float(observation["screen_latency_seconds"]))
        maximum_constraint_force = max(
            maximum_constraint_force,
            float(observation["maximum_abs_guarded_constraint_force"]),
        )
        if observation["deadlock"] is not True:
            matrices.append(
                v14.pilot.full_clean_margin_matrix(
                    observation["actual_joint_side_margins"]
                )
            )
        if observation["deadlock"] is True:
            break
    observations = wrapper.observations
    recovery_selected = [
        row
        for row in observations
        if row["floor_or_current_edge_recovery_selected"] is True
    ]
    selected_actual_margins = [
        float(row["actual_minimum_margin_rad"])
        for row in recovery_selected
        if row["actual_minimum_margin_rad"] is not None
    ]
    selected_guard_margins = [
        float(row["selected_guard_margin_rad"])
        for row in recovery_selected
        if row["selected_guard_margin_rad"] is not None
    ]
    prediction_errors = [
        abs(float(row["prediction_execution_margin_error_rad"]))
        for row in observations
        if row["prediction_execution_margin_error_rad"] is not None
    ]
    return {
        "executed_step_count": sum(
            row["deadlock"] is not True for row in observations
        ),
        "policy_decision_count": len(observations),
        "trigger_count": sum(
            row["triggered"] is True for row in observations
        ),
        "intervention_count": sum(
            row["intervened"] is True for row in observations
        ),
        "deadlock_count": sum(
            row["deadlock"] is True for row in observations
        ),
        "reactive_stop_count": 0,
        "stop_reason": (
            str(observations[-1]["deadlock_reason"])
            if observations and observations[-1]["deadlock"]
            else None
        ),
        "shadow_env_step_count": sum(
            int(row["shadow_env_step_count"]) for row in observations
        ),
        "restore_failure_count": sum(
            row["shadow_restore_identity"] is not True
            for row in observations
        ),
        "exact_action_mismatch_count": sum(
            row["deadlock"] is not True
            and row["exact_action_identity"] is not True
            for row in observations
        ),
        "screen_latency_seconds_values": latencies,
        "screen_latency_seconds_sum": float(sum(latencies)),
        "screen_latency_seconds_max": max(latencies) if latencies else 0.0,
        "maximum_abs_constraint_force": maximum_constraint_force,
        "actual_joint_side_margins": [
            v14.pilot._margin_rows(matrix) for matrix in matrices
        ],
        "v15_2_schema_mismatch_count": sum(
            row.get("schema") != recovery.BRAKE_AUDIT_SCHEMA
            for row in observations
        ),
        "v15_2_priority_mismatch_count": sum(
            row.get("recovery_candidate_priority") != RECOVERY_PRIORITY
            for row in observations
        ),
        "v14_baseline_would_deadlock_count": sum(
            row["v14_baseline_would_deadlock"] is True
            for row in observations
        ),
        "v14_baseline_would_deadlock_lane": any(
            row["v14_baseline_would_deadlock"] is True
            for row in observations
        ),
        "recovery_prevented_deadlock_count": sum(
            row["floor_or_current_edge_recovery_prevented_deadlock"]
            is True
            for row in observations
        ),
        "recovery_prevented_deadlock_lane": any(
            row["floor_or_current_edge_recovery_prevented_deadlock"]
            is True
            for row in observations
        ),
        "current_edge_attempted_count": sum(
            row["current_edge_recovery_attempted"] is True
            for row in observations
        ),
        "current_edge_eligible_count": sum(
            row["current_edge_recovery_eligible"] is True
            for row in observations
        ),
        "current_edge_selected_count": sum(
            row["current_edge_recovery_selected"] is True
            for row in observations
        ),
        "floor_edge_attempted_count": sum(
            row["floor_guard_recovery_attempted"] is True
            for row in observations
        ),
        "floor_edge_eligible_count": sum(
            row["floor_guard_recovery_eligible"] is True
            for row in observations
        ),
        "floor_edge_selected_count": sum(
            row["floor_guard_recovery_selected"] is True
            for row in observations
        ),
        "selected_recovery_count": len(recovery_selected),
        "selected_floor_violation_count": sum(
            value < recovery.SAFE_MARGIN_FLOOR_RAD
            for value in selected_actual_margins
        ),
        "selected_actual_minimum_margin_rad": (
            min(selected_actual_margins)
            if selected_actual_margins
            else None
        ),
        "selected_guard_minimum_margin_rad": (
            min(selected_guard_margins)
            if selected_guard_margins
            else None
        ),
        "maximum_prediction_execution_error_rad": (
            max(prediction_errors) if prediction_errors else 0.0
        ),
        **v14.pilot._exposure(matrices),
    }


@contextmanager
def _patched_stress_runtime() -> Iterator[None]:
    original_baselines = v14.pilot.BASELINES
    original_screened = v14._run_screened

    def dispatch(
        env: Any,
        qidx: np.ndarray,
        limits: np.ndarray,
        *,
        baseline: str,
    ) -> dict[str, Any]:
        if baseline == "shadow_only":
            return original_screened(
                env,
                qidx,
                limits,
                baseline="shadow_only",
            )
        if baseline == "v14_predictive_brake":
            return original_screened(
                env,
                qidx,
                limits,
                baseline="predictive_brake",
            )
        if baseline == "v15_2_recovery":
            return _run_recovery_screened(env)
        raise V15RecoveryStressCalibrationError(
            f"unsupported screened baseline: {baseline}"
        )

    v14.pilot.BASELINES = BASELINES
    v14._run_screened = dispatch
    try:
        yield
    finally:
        v14._run_screened = original_screened
        v14.pilot.BASELINES = original_baselines


def _run_audited_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
    warnings: audit._WarningAudit,
) -> tuple[list[dict[str, Any]], int, float, dict[str, Any]]:
    environment_id = str(spec["environment_id"])
    warnings.environment_id = environment_id
    warnings.phase = "prebinding"
    contacts = audit._ContactAudit(environment_id)
    original_create = v14.base.create_env

    def audited_create(runtime: Any, args: Any) -> audit._AuditedEnvironment:
        warnings.phase = "prebinding"
        env = original_create(runtime, args)
        return audit._AuditedEnvironment(
            env,
            contacts=contacts,
            warnings=warnings,
        )

    v14.base.create_env = audited_create
    try:
        with _patched_stress_runtime():
            rows, failures, error = v14._run_environment(spec, gpu=gpu)
    finally:
        v14.base.create_env = original_create
    return rows, failures, error, contacts.report(warnings)


def _recovery_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    reports = [row["baselines"]["v15_2_recovery"] for row in rows]
    sum_fields = (
        "v15_2_schema_mismatch_count",
        "v15_2_priority_mismatch_count",
        "v14_baseline_would_deadlock_count",
        "recovery_prevented_deadlock_count",
        "current_edge_attempted_count",
        "current_edge_eligible_count",
        "current_edge_selected_count",
        "floor_edge_attempted_count",
        "floor_edge_eligible_count",
        "floor_edge_selected_count",
        "selected_recovery_count",
        "selected_floor_violation_count",
    )
    v14_deadlock_lanes = sum(
        row["baselines"]["v14_predictive_brake"]["deadlock_count"] > 0
        for row in rows
    )
    would_deadlock_lanes = sum(
        report["v14_baseline_would_deadlock_lane"] is True
        for report in reports
    )
    prevented_lanes = sum(
        report["recovery_prevented_deadlock_lane"] is True
        for report in reports
    )
    selected_actual = [
        float(report["selected_actual_minimum_margin_rad"])
        for report in reports
        if report["selected_actual_minimum_margin_rad"] is not None
    ]
    selected_guard = [
        float(report["selected_guard_minimum_margin_rad"])
        for report in reports
        if report["selected_guard_minimum_margin_rad"] is not None
    ]
    return {
        **{
            field: sum(int(report[field]) for report in reports)
            for field in sum_fields
        },
        "v14_predictive_deadlock_lane_count": v14_deadlock_lanes,
        "v15_2_v14_would_deadlock_lane_count": would_deadlock_lanes,
        "v15_2_recovery_prevented_deadlock_lane_count": prevented_lanes,
        "paired_deadlock_lane_identity": (
            v14_deadlock_lanes == would_deadlock_lanes
        ),
        "v15_2_residual_deadlock_lane_count": sum(
            report["deadlock_count"] > 0 for report in reports
        ),
        "selected_actual_minimum_margin_rad": (
            min(selected_actual) if selected_actual else None
        ),
        "selected_guard_minimum_margin_rad": (
            min(selected_guard) if selected_guard else None
        ),
        "maximum_prediction_execution_error_rad": max(
            (
                float(report["maximum_prediction_execution_error_rad"])
                for report in reports
            ),
            default=0.0,
        ),
    }


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    maximum_no_guard_shadow_error: float,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    with _patched_stress_runtime():
        aggregate, inherited_gates = v14._analyze(
            protocol,
            rows,
            restore_failure_count=restore_failure_count,
            maximum_no_guard_shadow_error=(
                maximum_no_guard_shadow_error
            ),
        )
    recovery_metrics = _recovery_metrics(rows)
    contacts = audit._contact_aggregate(contact_reports)
    gates = protocol["gates"]
    gate_results = {
        **inherited_gates,
        "expected_total_baseline_lane_count": (
            sum(
                int(aggregate[f"{baseline}_lane_count"])
                for baseline in BASELINES
            )
            == gates["expected_baseline_lane_count"]
        ),
        "exact_action_identity": all(
            aggregate[f"{baseline}_exact_action_mismatch_count"] == 0
            for baseline in BASELINES
        ),
        "v15_2_schema_identity": (
            recovery_metrics["v15_2_schema_mismatch_count"] == 0
        ),
        "v15_2_candidate_priority_identity": (
            recovery_metrics["v15_2_priority_mismatch_count"] == 0
        ),
        "selected_recovery_floor_containment": (
            recovery_metrics["selected_floor_violation_count"]
            <= gates["selected_floor_violation_count_max"]
        ),
        "active_contact_capacity_warning_free": (
            contacts["phases"]["active"][
                "contact_capacity_warning_count"
            ]
            <= gates["active_contact_capacity_warning_count_max"]
        ),
        "active_contact_capacity_unsaturated": (
            contacts["phases"]["active"][
                "contact_saturation_count"
            ]
            <= gates["active_contact_saturation_count_max"]
        ),
    }
    metrics = {
        "aggregate": aggregate,
        "recovery": recovery_metrics,
        "contact_capacity": contacts,
        "contact_reports": contact_reports,
        "latency_deadlines": {
            baseline: audit._deadline_report(
                rows,
                baseline=baseline,
                deadline_seconds=float(gates["control_period_seconds"]),
            )
            for baseline in (
                "v14_predictive_brake",
                "v15_2_recovery",
            )
        },
        "performance_axes_registered_as_descriptive": True,
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
        raise V15RecoveryStressCalibrationError(
            "calibration preflight failed: "
            + "; ".join(report["blockers"])
        )
    v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15RecoveryStressCalibrationError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    maximum_error = 0.0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, error, contacts = (
                _run_audited_environment(
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
    data_complete = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["complete_classification"]
            if data_complete
            else protocol["incomplete_classification"]
        ),
        "development_data_complete": data_complete,
        "qualification_claim_authorized": False,
        "task_utility_claim_authorized": False,
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
    evidence_path = root / "calibration_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return {
        "classification": evidence["classification"],
        "development_data_complete": data_complete,
        "environment_count": metrics["aggregate"]["environment_count"],
        "stress_lane_count": metrics["aggregate"]["stress_lane_count"],
        "baseline_lane_count": sum(
            metrics["aggregate"][f"{baseline}_lane_count"]
            for baseline in BASELINES
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
    evidence_path = root / "calibration_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15RecoveryStressCalibrationError(
            "calibration evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15RecoveryStressCalibrationError(
            "calibration checksum manifest differs"
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
        raise V15RecoveryStressCalibrationError(
            "calibration evidence identity differs"
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
        or evidence["development_data_complete"]
        is not all(gates.values())
    ):
        raise V15RecoveryStressCalibrationError(
            "calibration analysis is stale"
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
