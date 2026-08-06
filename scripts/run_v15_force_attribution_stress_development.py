#!/usr/bin/env python3
"""Run v15.3 force-attribution development on disclosed stress lanes."""

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
from scripts import run_l2_predictive_virtual_brake_v15_force_attributed_recovery as recovery  # noqa: E402
from scripts import run_v15_current_edge_priority_recovery_stress_calibration as calibration  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _robot_arrays,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attribution-"
    "stress-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attribution-"
    "stress-development-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_3_force_attribution_stress_development"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attribution_"
    "stress_development_protocol.json"
)
BASELINE = "v15_3_force_attributed_recovery"


class V15ForceAttributionStressDevelopmentError(RuntimeError):
    """Raised when v15.3 development differs from its protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15ForceAttributionStressDevelopmentError(
            "development output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15ForceAttributionStressDevelopmentError(
            "development output root resolves to repository"
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
        raise V15ForceAttributionStressDevelopmentError(
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
        "force_metric_development": True,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["doses"]
        != [dict(row) for row in calibration.v14.pilot.DOSES]
        or protocol["design"]["baseline"] != BASELINE
        or protocol["design"]["horizon_steps"]
        != calibration.v14.pilot.HORIZON_STEPS
    ):
        raise V15ForceAttributionStressDevelopmentError(
            "unsupported or unauthorized development protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15ForceAttributionStressDevelopmentError(
                f"development source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V15ForceAttributionStressDevelopmentError(
                "development predecessor binding differs: "
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
    except V15ForceAttributionStressDevelopmentError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh development output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.3-force-attribution-"
            "stress-development-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "expected_stress_lane_count": protocol["gates"][
            "expected_stress_lane_count"
        ],
        "output_root_absent": not root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "qualification_claim_authorized": False,
    }


def _run_screened(env: Any) -> dict[str, Any]:
    wrapper = recovery.MultiJointForceAttributedRecoveryEnvironment(
        env,
        wait_steps=0,
        enabled=True,
        config=None,
    )
    matrices = []
    for _ in range(calibration.v14.pilot.HORIZON_STEPS):
        wrapper.step(calibration.v14.pilot.HOLD_ACTION)
        observation = wrapper.observations[-1]
        if observation["deadlock"] is not True:
            matrices.append(
                calibration.v14.pilot.full_clean_margin_matrix(
                    observation["actual_joint_side_margins"]
                )
            )
        if observation["deadlock"] is True:
            break
    observations = wrapper.observations
    latencies = [
        float(row["screen_latency_seconds"]) for row in observations
    ]
    force_steps = [
        {
            "runner_step_id": int(row["runner_step_id"]),
            "triggered": bool(row["triggered"]),
            "intervened": bool(row["intervened"]),
            "recovery_selected": bool(
                row["recovery_selected_for_force_attribution"]
            ),
            "pre_step_maximum_abs_risk_constraint_force": float(
                row["pre_step_maximum_abs_risk_constraint_force"]
            ),
            "guard_scope_reported_maximum_abs_risk_constraint_force": float(
                row[
                    "guard_scope_reported_maximum_abs_risk_constraint_force"
                ]
            ),
            "post_step_maximum_abs_risk_constraint_force": float(
                row["post_step_maximum_abs_risk_constraint_force"]
            ),
            "guard_scope_max_envelope_increment_over_pre_step": float(
                row["guard_scope_max_envelope_increment_over_pre_step"]
            ),
            "post_step_max_envelope_increment_over_pre_step": float(
                row["post_step_max_envelope_increment_over_pre_step"]
            ),
            "post_step_max_envelope_reduction_from_pre_step": float(
                row["post_step_max_envelope_reduction_from_pre_step"]
            ),
            "guard_scope_controller_substep_count": int(
                row["guard_scope_controller_substep_count"]
            ),
            "guard_scope_maximum_positive_joint_increment_over_pre_step": float(
                row[
                    "guard_scope_maximum_positive_joint_increment_over_pre_step"
                ]
            ),
            "post_step_maximum_positive_joint_increment_over_pre_step": float(
                row[
                    "post_step_maximum_positive_joint_increment_over_pre_step"
                ]
            ),
            "guard_scope_legacy_force_recomputed_identity": bool(
                row["guard_scope_legacy_force_recomputed_identity"]
            ),
            "guard_scope_joint_peak_constraint_force": [
                dict(force_row)
                for force_row in row[
                    "guard_scope_joint_peak_constraint_force"
                ]
            ],
        }
        for row in observations
    ]
    selected = [row for row in observations if row["recovery_selected_for_force_attribution"]]
    selected_actual = [
        float(row["actual_minimum_margin_rad"])
        for row in selected
        if row["actual_minimum_margin_rad"] is not None
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
        "trigger_count": sum(row["triggered"] is True for row in observations),
        "intervention_count": sum(
            row["intervened"] is True for row in observations
        ),
        "deadlock_count": sum(row["deadlock"] is True for row in observations),
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
        "maximum_abs_constraint_force": max(
            (
                float(row["maximum_abs_guarded_constraint_force"])
                for row in observations
            ),
            default=0.0,
        ),
        "actual_joint_side_margins": [
            calibration.v14.pilot._margin_rows(matrix)
            for matrix in matrices
        ],
        "v15_3_schema_mismatch_count": sum(
            row.get("schema") != recovery.BRAKE_AUDIT_SCHEMA
            for row in observations
        ),
        "v15_3_force_attribution_inactive_count": sum(
            row.get("force_attribution_active") is not True
            for row in observations
        ),
        "v15_2_priority_mismatch_count": sum(
            row.get("recovery_candidate_priority")
            != calibration.RECOVERY_PRIORITY
            for row in observations
        ),
        "v14_baseline_would_deadlock_count": sum(
            row["v14_baseline_would_deadlock"] is True
            for row in observations
        ),
        "recovery_prevented_deadlock_count": sum(
            row["floor_or_current_edge_recovery_prevented_deadlock"]
            is True
            for row in observations
        ),
        "current_edge_selected_count": sum(
            row["current_edge_recovery_selected"] is True
            for row in observations
        ),
        "floor_edge_selected_count": sum(
            row["floor_guard_recovery_selected"] is True
            for row in observations
        ),
        "selected_recovery_count": len(selected),
        "selected_floor_violation_count": sum(
            value < recovery.SAFE_MARGIN_FLOOR_RAD
            for value in selected_actual
        ),
        "selected_actual_minimum_margin_rad": (
            min(selected_actual) if selected_actual else None
        ),
        "maximum_prediction_execution_error_rad": (
            max(prediction_errors) if prediction_errors else 0.0
        ),
        "force_attribution_steps": force_steps,
        **calibration.v14.pilot._exposure(matrices),
    }


def _run_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
) -> tuple[list[dict[str, Any]], int]:
    runtime = calibration.v14.base.load_libero_task_runtime(
        benchmark_name=str(spec["suite"]),
        task_id=int(spec["task_id"]),
        init_state_id=int(spec["init_state_id"]),
        bddl_file=str(REPO_ROOT / spec["bddl_path"]),
    )
    args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=gpu,
        control_freq=20,
        horizon=1000,
        seed=int(spec["environment_seed"]),
    )
    env = calibration.v14.base.create_env(runtime, args)
    rows = []
    restore_failures = 0
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = _robot_arrays(env)
        canonical = calibration.v14.full.core.capture_warmstart_policy_shadow_snapshot(
            env,
            robot,
            source_id=f"v15.3-force-development:{spec['environment_id']}:canonical",
        )
        for joint_index in range(recovery.JOINT_COUNT):
            for side in recovery.JOINT_SIDES:
                for dose in calibration.v14.pilot.DOSES:
                    restored = calibration.v14.full.core.restore_warmstart_policy_shadow_snapshot(
                        env, robot, canonical
                    )
                    identity = calibration.v14.full.core._restore_identity(
                        restored
                    )
                    restore_failures += int(not identity)
                    if not identity:
                        raise V15ForceAttributionStressDevelopmentError(
                            "canonical restore lost identity"
                        )
                    calibration.v14.pilot._inject(
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=joint_index,
                        side=side,
                        dose=dose,
                    )
                    initial = calibration.v14.pilot._margin_matrix(
                        env, qidx, limits
                    )
                    report = _run_screened(env)
                    rows.append(
                        {
                            "environment_id": str(spec["environment_id"]),
                            "suite": str(spec["suite"]),
                            "task_id": int(spec["task_id"]),
                            "init_state_id": int(spec["init_state_id"]),
                            "lane_id": (
                                f"{spec['environment_id']}:"
                                f"joint{joint_index}:{side}:{dose['dose']}"
                            ),
                            "joint_index": joint_index,
                            "side": side,
                            "dose": dict(dose),
                            "initial_joint_side_margins": (
                                calibration.v14.pilot._margin_rows(initial)
                            ),
                            "baselines": {BASELINE: report},
                        }
                    )
    finally:
        if hasattr(env, "close"):
            env.close()
    return rows, restore_failures


@contextmanager
def _patched_baseline() -> Iterator[None]:
    original = calibration.v14.pilot.BASELINES
    calibration.v14.pilot.BASELINES = (BASELINE,)
    try:
        yield
    finally:
        calibration.v14.pilot.BASELINES = original


def _force_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    steps = [
        step
        for row in rows
        for step in row["baselines"][BASELINE][
            "force_attribution_steps"
        ]
    ]
    selected = [step for step in steps if step["recovery_selected"]]

    def stats(field: str, source: list[Mapping[str, Any]]) -> dict[str, Any]:
        values = np.asarray(
            [float(row[field]) for row in source], dtype=np.float64
        )
        return {
            "count": int(values.size),
            "mean": float(np.mean(values)) if values.size else None,
            "p50": float(np.quantile(values, 0.50)) if values.size else None,
            "p95": float(np.quantile(values, 0.95)) if values.size else None,
            "p99": float(np.quantile(values, 0.99)) if values.size else None,
            "maximum": float(np.max(values)) if values.size else None,
        }

    fields = (
        "pre_step_maximum_abs_risk_constraint_force",
        "guard_scope_reported_maximum_abs_risk_constraint_force",
        "post_step_maximum_abs_risk_constraint_force",
        "guard_scope_max_envelope_increment_over_pre_step",
        "post_step_max_envelope_increment_over_pre_step",
        "post_step_max_envelope_reduction_from_pre_step",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    return {
        "all_steps": {field: stats(field, steps) for field in fields},
        "recovery_selected_steps": {
            field: stats(field, selected) for field in fields
        },
        "recovery_selected_step_count": len(selected),
        "recovery_selected_guard_scope_joint_amplification_over_1e_6_count": sum(
            float(
                row[
                    "guard_scope_maximum_positive_joint_increment_over_pre_step"
                ]
            )
            > 1e-6
            for row in selected
        ),
        "guard_scope_legacy_force_recomputed_mismatch_count": sum(
            row["guard_scope_legacy_force_recomputed_identity"] is not True
            for row in steps
        ),
        "recovery_selected_post_step_force_over_10000_count": sum(
            float(row["post_step_maximum_abs_risk_constraint_force"])
            > 10000.0
            for row in selected
        ),
        "recovery_selected_reported_total_force_over_10000_count": sum(
            float(
                row[
                    "guard_scope_reported_maximum_abs_risk_constraint_force"
                ]
            )
            > 10000.0
            for row in selected
        ),
    }


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    with _patched_baseline():
        aggregate, inherited = calibration.v14._analyze(
            protocol,
            rows,
            restore_failure_count=restore_failure_count,
            maximum_no_guard_shadow_error=0.0,
        )
    reports = [row["baselines"][BASELINE] for row in rows]
    contacts = calibration.audit._contact_aggregate(contact_reports)
    gates = protocol["gates"]
    gate_results = {
        "environment_count": inherited["environment_count"],
        "environment_lane_coverage": inherited[
            "environment_lane_coverage"
        ],
        "stress_lane_count": inherited["stress_lane_count"],
        "baseline_lane_count": inherited["baseline_lane_count"],
        "restore_identity": inherited["restore_identity"],
        "zero_policy_or_outcome_fields": inherited[
            "zero_policy_or_outcome_fields"
        ],
        "exact_action_identity": (
            aggregate[f"{BASELINE}_exact_action_mismatch_count"] == 0
        ),
        "v15_3_schema_identity": sum(
            int(report["v15_3_schema_mismatch_count"])
            for report in reports
        )
        == 0,
        "v15_3_force_attribution_active": sum(
            int(report["v15_3_force_attribution_inactive_count"])
            for report in reports
        )
        == 0,
        "v15_2_candidate_priority_identity": sum(
            int(report["v15_2_priority_mismatch_count"])
            for report in reports
        )
        == 0,
        "selected_recovery_floor_containment": sum(
            int(report["selected_floor_violation_count"])
            for report in reports
        )
        <= gates["selected_floor_violation_count_max"],
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
        "force_attribution": _force_metrics(rows),
        "recovery": {
            field: sum(int(report[field]) for report in reports)
            for field in (
                "v14_baseline_would_deadlock_count",
                "recovery_prevented_deadlock_count",
                "current_edge_selected_count",
                "floor_edge_selected_count",
                "selected_recovery_count",
                "selected_floor_violation_count",
                "deadlock_count",
                "below_floor_count",
                "crossing_count",
            )
        },
        "maximum_prediction_execution_error_rad": max(
            (
                float(report["maximum_prediction_execution_error_rad"])
                for report in reports
            ),
            default=0.0,
        ),
        "contact_capacity": contacts,
        "contact_reports": contact_reports,
        "performance_axes_registered_as_descriptive": True,
    }
    return metrics, gate_results


def _run_audited_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
    warnings: calibration.audit._WarningAudit,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    environment_id = str(spec["environment_id"])
    warnings.environment_id = environment_id
    warnings.phase = "prebinding"
    contacts = calibration.audit._ContactAudit(environment_id)
    original_create = calibration.v14.base.create_env

    def audited_create(runtime: Any, args: Any) -> calibration.audit._AuditedEnvironment:
        warnings.phase = "prebinding"
        env = original_create(runtime, args)
        return calibration.audit._AuditedEnvironment(
            env, contacts=contacts, warnings=warnings
        )

    calibration.v14.base.create_env = audited_create
    try:
        rows, failures = _run_environment(spec, gpu=gpu)
    finally:
        calibration.v14.base.create_env = original_create
    return rows, failures, contacts.report(warnings)


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15ForceAttributionStressDevelopmentError(
            "development preflight failed: "
            + "; ".join(report["blockers"])
        )
    calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15ForceAttributionStressDevelopmentError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = calibration.audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contacts = []
    restore_failures = 0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, contact = (
                _run_audited_environment(
                    spec, gpu=gpu, warnings=warnings
                )
            )
            rows.extend(environment_rows)
            contacts.append(contact)
            restore_failures += failures
    finally:
        mujoco.set_mju_user_warning(previous_warning_callback)
    metrics, gate_results = _analyze(
        protocol,
        rows,
        restore_failure_count=restore_failures,
        contact_reports=contacts,
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
        "force_metric_qualification_claim_authorized": False,
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
    evidence_path = root / "development_evidence.json"
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
    evidence_path = root / "development_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15ForceAttributionStressDevelopmentError(
            "development evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15ForceAttributionStressDevelopmentError(
            "development checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
    ):
        raise V15ForceAttributionStressDevelopmentError(
            "development evidence identity differs"
        )
    recorded = evidence["analysis"]
    metrics, gates = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(
            recorded["aggregate"]["restore_failure_count"]
        ),
        contact_reports=recorded["contact_reports"],
    )
    if (
        metrics != recorded
        or gates != evidence["gate_results"]
        or evidence["development_data_complete"]
        is not all(gates.values())
    ):
        raise V15ForceAttributionStressDevelopmentError(
            "development analysis is stale"
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
            protocol, protocol_path=protocol_path, gpu=args.gpu
        )
    else:
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
