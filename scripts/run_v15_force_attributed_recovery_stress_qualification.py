#!/usr/bin/env python3
"""Run held-out v15.3 force-attributed recovery qualification."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
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
from scripts import run_v15_current_edge_priority_recovery_stress_calibration as calibration  # noqa: E402
from scripts import run_v15_force_attribution_stress_development as force_development  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-stress-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-stress-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_3_force_attributed_recovery_stress_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_stress_qualification_protocol.json"
)
BASELINES = (
    "no_guard",
    "v14_predictive_brake",
    force_development.BASELINE,
)
V15_BASELINE = force_development.BASELINE


class V15ForceAttributedRecoveryQualificationError(RuntimeError):
    """Raised when held-out v15.3 qualification differs from protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15ForceAttributedRecoveryQualificationError(
            "qualification output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15ForceAttributedRecoveryQualificationError(
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
        "same_environment_shadow_trace_identity_claim": False,
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
        or protocol["design"]["baselines"] != list(BASELINES)
        or protocol["design"]["horizon_steps"]
        != calibration.v14.pilot.HORIZON_STEPS
    ):
        raise V15ForceAttributedRecoveryQualificationError(
            "unsupported or unauthorized v15.3 qualification protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15ForceAttributedRecoveryQualificationError(
                f"qualification source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15ForceAttributedRecoveryQualificationError(
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
    except V15ForceAttributedRecoveryQualificationError as exc:
        blockers.append(str(exc))
    if calibration._git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh qualification output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
            "recovery-stress-qualification-preflight.v1"
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
        "same_environment_shadow_trace_identity_claim_authorized": False,
        "real_time_claim_authorized": False,
    }


def _run_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
) -> tuple[list[dict[str, Any]], int]:
    v14 = calibration.v14
    runtime = v14.base.load_libero_task_runtime(
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
    env = v14.base.create_env(runtime, args)
    rows = []
    restore_failures = 0
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = v14._robot_arrays(env)
        canonical = v14.full.core.capture_warmstart_policy_shadow_snapshot(
            env,
            robot,
            source_id=(
                f"v15.3-force-qualification:{spec['environment_id']}:"
                "canonical"
            ),
        )
        for joint_index in range(v14.full.JOINT_COUNT):
            for side in v14.full.JOINT_SIDES:
                for dose in v14.pilot.DOSES:
                    restored = (
                        v14.full.core.
                        restore_warmstart_policy_shadow_snapshot(
                            env, robot, canonical
                        )
                    )
                    identity = v14.full.core._restore_identity(restored)
                    restore_failures += int(not identity)
                    if not identity:
                        raise V15ForceAttributedRecoveryQualificationError(
                            "canonical environment restore lost identity"
                        )
                    v14.pilot._inject(
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=joint_index,
                        side=side,
                        dose=dose,
                    )
                    injected = (
                        v14.full.core.
                        capture_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            source_id=(
                                "v15.3-force-qualification:"
                                f"{spec['environment_id']}:"
                                f"joint{joint_index}:{side}:{dose['dose']}"
                            ),
                        )
                    )
                    initial = v14.pilot._margin_matrix(env, qidx, limits)
                    baselines = {}
                    for baseline in BASELINES:
                        restored = (
                            v14.full.core.
                            restore_warmstart_policy_shadow_snapshot(
                                env, robot, injected
                            )
                        )
                        identity = v14.full.core._restore_identity(restored)
                        restore_failures += int(not identity)
                        if not identity:
                            raise V15ForceAttributedRecoveryQualificationError(
                                "baseline environment restore lost identity"
                            )
                        if baseline == "no_guard":
                            result = v14._direct_result(
                                env, qidx, limits, reactive=False
                            )
                        elif baseline == "v14_predictive_brake":
                            result = v14._run_screened(
                                env,
                                qidx,
                                limits,
                                baseline="predictive_brake",
                            )
                        elif baseline == V15_BASELINE:
                            result = force_development._run_screened(env)
                        else:
                            raise V15ForceAttributedRecoveryQualificationError(
                                f"unsupported baseline: {baseline}"
                            )
                        baselines[baseline] = result
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
                                v14.pilot._margin_rows(initial)
                            ),
                            "baselines": baselines,
                        }
                    )
    finally:
        if hasattr(env, "close"):
            env.close()
    return rows, restore_failures


@contextmanager
def _patched_baselines() -> Iterator[None]:
    original = calibration.v14.pilot.BASELINES
    calibration.v14.pilot.BASELINES = BASELINES
    try:
        yield
    finally:
        calibration.v14.pilot.BASELINES = original


def _force_stats(
    rows: list[Mapping[str, Any]],
    field: str,
) -> dict[str, Any]:
    values = np.asarray(
        [float(row[field]) for row in rows], dtype=np.float64
    )
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)) if values.size else None,
        "p50": float(np.quantile(values, 0.50)) if values.size else None,
        "p95": float(np.quantile(values, 0.95)) if values.size else None,
        "p99": float(np.quantile(values, 0.99)) if values.size else None,
        "maximum": float(np.max(values)) if values.size else None,
    }


def _qualification_force_metrics(
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    steps = [
        step
        for lane in rows
        for step in lane["baselines"][V15_BASELINE][
            "force_attribution_steps"
        ]
    ]
    interventions = [step for step in steps if step["intervened"] is True]
    recovery = [
        step for step in interventions if step["recovery_selected"] is True
    ]
    standard = [
        step for step in interventions if step["recovery_selected"] is False
    ]
    fields = (
        "pre_step_maximum_abs_risk_constraint_force",
        "guard_scope_reported_maximum_abs_risk_constraint_force",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
        "post_step_maximum_abs_risk_constraint_force",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )

    def group(source: list[Mapping[str, Any]]) -> dict[str, Any]:
        return {field: _force_stats(source, field) for field in fields}

    return {
        "step_count": len(steps),
        "intervention_step_count": len(interventions),
        "standard_guard_intervention_step_count": len(standard),
        "recovery_intervention_step_count": len(recovery),
        "all_interventions": group(interventions),
        "standard_guard_interventions": group(standard),
        "recovery_interventions": group(recovery),
        "legacy_force_recomputation_mismatch_count": sum(
            step["guard_scope_legacy_force_recomputed_identity"] is not True
            for step in steps
        ),
    }


def _recovery_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    reports = [row["baselines"][V15_BASELINE] for row in rows]
    v14_deadlocks = sum(
        row["baselines"]["v14_predictive_brake"]["deadlock_count"] > 0
        for row in rows
    )
    would_deadlock_lanes = sum(
        report["v14_baseline_would_deadlock_count"] > 0
        for report in reports
    )
    prevention_lanes = sum(
        report["recovery_prevented_deadlock_count"] > 0
        for report in reports
    )
    fields = (
        "v15_3_schema_mismatch_count",
        "v15_3_force_attribution_inactive_count",
        "v15_2_priority_mismatch_count",
        "v14_baseline_would_deadlock_count",
        "recovery_prevented_deadlock_count",
        "current_edge_selected_count",
        "floor_edge_selected_count",
        "selected_recovery_count",
        "selected_floor_violation_count",
    )
    return {
        **{
            field: sum(int(report[field]) for report in reports)
            for field in fields
        },
        "v14_predictive_deadlock_lane_count": v14_deadlocks,
        "v15_3_v14_would_deadlock_lane_count": would_deadlock_lanes,
        "v15_3_recovery_prevented_deadlock_lane_count": prevention_lanes,
        "paired_deadlock_lane_identity": (
            v14_deadlocks == would_deadlock_lanes
        ),
        "v15_3_residual_deadlock_lane_count": sum(
            report["deadlock_count"] > 0 for report in reports
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
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    compatibility_protocol = dict(protocol)
    compatibility_protocol["gates"] = {
        **dict(protocol["gates"]),
        "no_guard_shadow_maximum_side_error_rad": 0.0,
    }
    with _patched_baselines():
        aggregate, inherited = calibration.v14._analyze(
            compatibility_protocol,
            rows,
            restore_failure_count=restore_failure_count,
            maximum_no_guard_shadow_error=0.0,
        )
    aggregate.pop("no_guard_shadow_maximum_side_error_rad", None)
    recovery = _recovery_metrics(rows)
    force = _qualification_force_metrics(rows)
    contacts = calibration.audit._contact_aggregate(contact_reports)
    deadline = calibration.audit._deadline_report(
        rows,
        baseline=V15_BASELINE,
        deadline_seconds=float(protocol["gates"]["latency_budget_seconds"]),
    )
    gates = protocol["gates"]
    v14_force = float(
        aggregate["v14_predictive_brake_maximum_abs_constraint_force"]
    )
    def maximum(group: str, field: str) -> float | None:
        value = force[group][field]["maximum"]
        return float(value) if value is not None else None

    attributable = maximum(
        "all_interventions",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
    )
    attributable_ratio = (
        attributable / v14_force
        if attributable is not None and v14_force > 0
        else None
    )
    post_absolute = maximum(
        "all_interventions", "post_step_maximum_abs_risk_constraint_force"
    )
    post_increment = maximum(
        "all_interventions",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    recovery_attributable = maximum(
        "recovery_interventions",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
    )
    recovery_post_increment = maximum(
        "recovery_interventions",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    v15_internal_restore_failures = int(
        aggregate[f"{V15_BASELINE}_restore_failure_count"]
    )
    retained = (
        "environment_count",
        "environment_lane_coverage",
        "stress_lane_count",
        "baseline_lane_count",
        "zero_policy_or_outcome_fields",
    )
    gate_results = {name: inherited[name] for name in retained}
    gate_results.update(
        {
            "expected_total_baseline_lane_count": (
                sum(int(aggregate[f"{name}_lane_count"]) for name in BASELINES)
                == gates["expected_baseline_lane_count"]
            ),
            "restore_identity": (
                restore_failure_count
                <= gates["restore_failure_count_max"]
                and v15_internal_restore_failures
                <= gates["restore_failure_count_max"]
            ),
            "exact_action_identity": all(
                int(aggregate[f"{name}_exact_action_mismatch_count"])
                <= gates["v15_3_exact_action_mismatch_count_max"]
                for name in BASELINES
            ),
            "v15_3_schema_identity": (
                recovery["v15_3_schema_mismatch_count"] == 0
            ),
            "v15_3_force_attribution_active": (
                recovery["v15_3_force_attribution_inactive_count"] == 0
            ),
            "v15_2_candidate_priority_identity": (
                recovery["v15_2_priority_mismatch_count"] == 0
            ),
            "force_recomputation_identity": (
                force["legacy_force_recomputation_mismatch_count"]
                <= gates["force_recomputation_mismatch_count_max"]
            ),
            "stress_activation_crossing": (
                aggregate["no_guard_crossing_count"]
                >= gates["no_guard_crossing_count_min"]
            ),
            "stress_activation_below_floor": (
                aggregate["no_guard_below_floor_count"]
                >= gates["no_guard_below_floor_count_min"]
            ),
            "v14_deadlock_activation": (
                recovery["v14_predictive_deadlock_lane_count"]
                >= gates["v14_deadlock_lane_count_min"]
            ),
            "v15_3_zero_residual_deadlock": (
                recovery["v15_3_residual_deadlock_lane_count"]
                <= gates["v15_3_residual_deadlock_lane_count_max"]
            ),
            "v15_3_crossing_containment": (
                aggregate[f"{V15_BASELINE}_crossing_count"]
                <= gates["v15_3_crossing_count_max"]
            ),
            "v15_3_floor_containment": (
                aggregate[f"{V15_BASELINE}_below_floor_count"]
                <= gates["v15_3_below_floor_count_max"]
            ),
            "v15_3_selected_recovery_floor_containment": (
                recovery["selected_floor_violation_count"]
                <= gates["v15_3_selected_floor_violation_count_max"]
            ),
            "v15_3_recovery_prevention_identity": (
                gates["recovery_prevention_identity_required"] is True
                and recovery["paired_deadlock_lane_identity"] is True
                and recovery["v14_baseline_would_deadlock_count"]
                == recovery["recovery_prevented_deadlock_count"]
                and recovery["v15_3_v14_would_deadlock_lane_count"]
                == recovery[
                    "v15_3_recovery_prevented_deadlock_lane_count"
                ]
            ),
            "v15_3_availability_not_below_v14": (
                gates["v15_3_availability_not_below_v14"] is True
                and aggregate[
                    f"{V15_BASELINE}_executed_step_availability"
                ]
                >= aggregate[
                    "v14_predictive_brake_executed_step_availability"
                ]
            ),
            "v15_3_prediction_execution_error": (
                recovery["maximum_prediction_execution_error_rad"]
                <= gates["prediction_execution_error_rad_max"]
            ),
            "active_contact_capacity_warning_free": (
                contacts["phases"]["active"][
                    "contact_capacity_warning_count"
                ]
                <= gates["active_contact_capacity_warning_count_max"]
            ),
            "active_contact_capacity_unsaturated": (
                contacts["phases"]["active"]["contact_saturation_count"]
                <= gates["active_contact_saturation_count_max"]
            ),
            "v15_3_attributable_force_envelope": (
                attributable is not None
                and attributable
                <= gates["maximum_attributable_joint_force_increment"]
            ),
            "v15_3_relative_attributable_force_envelope": (
                attributable_ratio is not None
                and attributable_ratio
                <= gates[
                    "maximum_attributable_increment_to_v14_legacy_force_ratio"
                ]
            ),
            "v15_3_post_step_absolute_force_envelope": (
                post_absolute is not None
                and post_absolute
                <= gates["maximum_post_step_absolute_risk_force"]
            ),
            "v15_3_post_step_increment_envelope": (
                post_increment is not None
                and post_increment
                <= gates["maximum_post_step_positive_joint_increment"]
            ),
            "v15_3_recovery_attributable_force_envelope": (
                recovery_attributable is not None
                and recovery_attributable
                <= gates[
                    "maximum_recovery_attributable_joint_force_increment"
                ]
            ),
            "v15_3_recovery_post_step_increment_envelope": (
                recovery_post_increment is not None
                and recovery_post_increment
                <= gates[
                    "maximum_recovery_post_step_positive_joint_increment"
                ]
            ),
            "v15_3_latency_p95": (
                aggregate[
                    f"{V15_BASELINE}_screen_latency_seconds_p95"
                ]
                is not None
                and aggregate[
                    f"{V15_BASELINE}_screen_latency_seconds_p95"
                ]
                <= gates["screen_latency_seconds_p95_max"]
            ),
            "v15_3_latency_max": (
                aggregate[
                    f"{V15_BASELINE}_screen_latency_seconds_max"
                ]
                is not None
                and aggregate[
                    f"{V15_BASELINE}_screen_latency_seconds_max"
                ]
                <= gates["screen_latency_seconds_max"]
            ),
            "v15_3_100ms_deadline_miss_rate": (
                deadline["miss_rate"] is not None
                and deadline["miss_rate"]
                <= gates["screen_latency_100ms_miss_rate_max"]
            ),
        }
    )
    metrics = {
        "aggregate": aggregate,
        "recovery": recovery,
        "force_attribution": force,
        "force_comparison": {
            "v14_legacy_maximum_abs_constraint_force": v14_force,
            "v15_3_maximum_attributable_joint_force_increment": attributable,
            "attributable_increment_to_v14_legacy_force_ratio": (
                attributable_ratio
            ),
            "v15_3_maximum_post_step_absolute_risk_force": post_absolute,
            "v15_3_maximum_post_step_positive_joint_increment": (
                post_increment
            ),
            "v15_3_maximum_recovery_attributable_joint_force_increment": (
                recovery_attributable
            ),
            "v15_3_maximum_recovery_post_step_positive_joint_increment": (
                recovery_post_increment
            ),
            "legacy_v15_3_total_force_diagnostic": aggregate[
                f"{V15_BASELINE}_maximum_abs_constraint_force"
            ],
        },
        "contact_capacity": contacts,
        "contact_reports": contact_reports,
        "v15_3_latency_budget": deadline,
        "same_environment_shadow_trace_identity": {
            "measured": False,
            "registered_as_gate": False,
            "fresh2_nonpass_superseded": False,
            "internal_aggregate_compatibility_value_retained": False,
        },
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
        raise V15ForceAttributedRecoveryQualificationError(
            "qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15ForceAttributedRecoveryQualificationError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = calibration.audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, contacts = (
                _run_audited_environment(
                    spec, gpu=gpu, warnings=warnings
                )
            )
            rows.extend(environment_rows)
            contact_reports.append(contacts)
            restore_failures += failures
    finally:
        mujoco.set_mju_user_warning(previous_warning_callback)
    metrics, gate_results = _analyze(
        protocol,
        rows,
        restore_failure_count=restore_failures,
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
        "same_environment_shadow_trace_identity_claim_authorized": False,
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
            int(metrics["aggregate"][f"{name}_lane_count"])
            for name in BASELINES
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
        raise V15ForceAttributedRecoveryQualificationError(
            "qualification evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15ForceAttributedRecoveryQualificationError(
            "qualification checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    expected_integrity = {
        "policy_loaded": False,
        "reward_read": False,
        "environment_done_read": False,
        "task_success_read": False,
        "cost_or_collision_read": False,
    }
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
        or evidence.get(
            "same_environment_shadow_trace_identity_claim_authorized"
        )
        is not False
        or evidence["integrity"] != expected_integrity
    ):
        raise V15ForceAttributedRecoveryQualificationError(
            "qualification evidence identity differs"
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
        or evidence["qualification_pass"] is not all(gates.values())
    ):
        raise V15ForceAttributedRecoveryQualificationError(
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
            protocol, protocol_path=protocol_path, gpu=args.gpu
        )
    else:
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
