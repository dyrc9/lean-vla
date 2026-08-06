#!/usr/bin/env python3
"""Run a held-out, same-lane component ablation of the v15 recovery stack.

This runner deliberately reads no policy or task outcome.  It compares the
incremental recovery implementations on the same injected simulator state so
that version history is not mistaken for a paired component ablation.
"""

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
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as priority_online,
)
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_current_edge_recovery as current_online,
)
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_floor_guard_recovery as floor_online,
)
from scripts import (  # noqa: E402
    run_v15_force_attributed_recovery_stress_qualification as base,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-recovery-component-"
    "ablation-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-recovery-component-"
    "ablation-qualification-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_recovery_component_ablation_qualification"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_recovery_component_"
    "ablation_qualification_protocol.json"
)

FLOOR_BASELINE = "v15_floor_edge_recovery"
CURRENT_BASELINE = "v15_1_current_edge_recovery"
PRIORITY_BASELINE = "v15_2_current_edge_priority_recovery"
V15_3_BASELINE = base.V15_BASELINE
BASELINES = (
    "no_guard",
    "reactive_stop",
    "shadow_only",
    "v14_predictive_brake",
    FLOOR_BASELINE,
    CURRENT_BASELINE,
    PRIORITY_BASELINE,
    V15_3_BASELINE,
)
RECOVERY_BASELINES = (
    FLOOR_BASELINE,
    CURRENT_BASELINE,
    PRIORITY_BASELINE,
    V15_3_BASELINE,
)


class V15RecoveryComponentAblationError(RuntimeError):
    """Raised when the component ablation differs from its frozen protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15RecoveryComponentAblationError(
            "component-ablation output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15RecoveryComponentAblationError(
            "component-ablation output root resolves to repository"
        )
    return root


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "held_out_component_ablation_claim": True,
        "task_utility_claim": False,
        "model_mismatch_claim": False,
        "real_time_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization") != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["doses"]
        != [dict(row) for row in base.calibration.v14.pilot.DOSES]
        or protocol["design"]["baselines"] != list(BASELINES)
        or protocol["design"]["horizon_steps"]
        != base.calibration.v14.pilot.HORIZON_STEPS
    ):
        raise V15RecoveryComponentAblationError(
            "unsupported or unauthorized component-ablation protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15RecoveryComponentAblationError(
                f"component-ablation source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15RecoveryComponentAblationError(
                "component-ablation predecessor binding differs: "
                + str(binding["path"])
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15RecoveryComponentAblationError as exc:
        blockers.append(str(exc))
    if base.calibration._git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh component-ablation output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15-recovery-component-"
            "ablation-qualification-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "expected_stress_lane_count": protocol["gates"]["expected_stress_lane_count"],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_baseline_lane_count"
        ],
        "output_root_absent": not output_root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "task_utility_claim_authorized": False,
        "model_mismatch_claim_authorized": False,
        "real_time_claim_authorized": False,
    }


def _recovery_result(
    env: Any,
    *,
    wrapper_class: type,
    expected_schema: str,
) -> dict[str, Any]:
    """Return the common stress report for one incremental recovery wrapper."""

    v14 = base.calibration.v14
    wrapper = wrapper_class(env, wait_steps=0, enabled=True, config=None)
    matrices = []
    for _ in range(v14.pilot.HORIZON_STEPS):
        # Task outcomes are intentionally discarded by this mechanism test.
        wrapper.step(v14.pilot.HOLD_ACTION)
        observation = wrapper.observations[-1]
        if observation["deadlock"] is not True:
            matrices.append(
                v14.pilot.full_clean_margin_matrix(
                    observation["actual_joint_side_margins"]
                )
            )
        if observation["deadlock"] is True:
            break
    observations = wrapper.observations
    latencies = [float(row["screen_latency_seconds"]) for row in observations]
    selected = [
        row
        for row in observations
        if row.get("floor_guard_recovery_selected") is True
        or row.get("current_edge_recovery_selected") is True
    ]
    selected_actual = [
        float(row["actual_minimum_margin_rad"])
        for row in selected
        if row.get("actual_minimum_margin_rad") is not None
    ]
    prediction_errors = [
        abs(float(row["prediction_execution_margin_error_rad"]))
        for row in observations
        if row.get("prediction_execution_margin_error_rad") is not None
    ]
    prevented = [
        row
        for row in observations
        if row.get("floor_guard_recovery_prevented_deadlock") is True
        or row.get("floor_or_current_edge_recovery_prevented_deadlock") is True
    ]
    return {
        "executed_step_count": sum(row["deadlock"] is not True for row in observations),
        "policy_decision_count": len(observations),
        "trigger_count": sum(row["triggered"] is True for row in observations),
        "intervention_count": sum(row["intervened"] is True for row in observations),
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
            row["shadow_restore_identity"] is not True for row in observations
        ),
        "exact_action_mismatch_count": sum(
            row["deadlock"] is not True and row["exact_action_identity"] is not True
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
            v14.pilot._margin_rows(matrix) for matrix in matrices
        ],
        "component_schema_mismatch_count": sum(
            row.get("schema") != expected_schema for row in observations
        ),
        "v14_baseline_would_deadlock_count": sum(
            row.get("v14_baseline_would_deadlock") is True for row in observations
        ),
        "recovery_prevented_deadlock_count": len(prevented),
        "current_edge_attempted_count": sum(
            row.get("current_edge_recovery_attempted") is True for row in observations
        ),
        "current_edge_selected_count": sum(
            row.get("current_edge_recovery_selected") is True for row in observations
        ),
        "floor_edge_attempted_count": sum(
            row.get("floor_guard_recovery_attempted") is True for row in observations
        ),
        "floor_edge_selected_count": sum(
            row.get("floor_guard_recovery_selected") is True for row in observations
        ),
        "selected_recovery_count": len(selected),
        "selected_floor_violation_count": sum(
            value < floor_online.SAFE_MARGIN_FLOOR_RAD for value in selected_actual
        ),
        "selected_actual_minimum_margin_rad": (
            min(selected_actual) if selected_actual else None
        ),
        "maximum_prediction_execution_error_rad": (
            max(prediction_errors) if prediction_errors else 0.0
        ),
        **v14.pilot._exposure(matrices),
    }


def _dispatch_baseline(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    *,
    baseline: str,
) -> dict[str, Any]:
    v14 = base.calibration.v14
    if baseline == "no_guard":
        return v14._direct_result(env, qidx, limits, reactive=False)
    if baseline == "reactive_stop":
        return v14._direct_result(env, qidx, limits, reactive=True)
    if baseline == "shadow_only":
        return v14._run_screened(env, qidx, limits, baseline="shadow_only")
    if baseline == "v14_predictive_brake":
        return v14._run_screened(env, qidx, limits, baseline="predictive_brake")
    if baseline == FLOOR_BASELINE:
        return _recovery_result(
            env,
            wrapper_class=floor_online.MultiJointFloorGuardRecoveryEnvironment,
            expected_schema=floor_online.BRAKE_AUDIT_SCHEMA,
        )
    if baseline == CURRENT_BASELINE:
        return _recovery_result(
            env,
            wrapper_class=current_online.MultiJointCurrentEdgeRecoveryEnvironment,
            expected_schema=current_online.BRAKE_AUDIT_SCHEMA,
        )
    if baseline == PRIORITY_BASELINE:
        return _recovery_result(
            env,
            wrapper_class=(
                priority_online.MultiJointCurrentEdgePriorityRecoveryEnvironment
            ),
            expected_schema=priority_online.BRAKE_AUDIT_SCHEMA,
        )
    if baseline == V15_3_BASELINE:
        return base.force_development._run_screened(env)
    raise V15RecoveryComponentAblationError(
        f"unsupported component-ablation baseline: {baseline}"
    )


def _run_environment(
    spec: Mapping[str, Any], *, gpu: int
) -> tuple[list[dict[str, Any]], int]:
    v14 = base.calibration.v14
    runtime = v14.base.load_libero_task_runtime(
        benchmark_name=str(spec["suite"]),
        task_id=int(spec["task_id"]),
        init_state_id=int(spec["init_state_id"]),
        bddl_file=str(REPO_ROOT / str(spec["bddl_path"])),
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
            source_id=f"v15-component-ablation:{spec['environment_id']}:canonical",
        )
        for joint_index in range(v14.full.JOINT_COUNT):
            for side in v14.full.JOINT_SIDES:
                for dose in v14.pilot.DOSES:
                    restored = v14.full.core.restore_warmstart_policy_shadow_snapshot(
                        env, robot, canonical
                    )
                    identity = v14.full.core._restore_identity(restored)
                    restore_failures += int(not identity)
                    if not identity:
                        raise V15RecoveryComponentAblationError(
                            "component-ablation canonical restore lost identity"
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
                    injected = v14.full.core.capture_warmstart_policy_shadow_snapshot(
                        env,
                        robot,
                        source_id=(
                            f"v15-component-ablation:{spec['environment_id']}:"
                            f"joint{joint_index}:{side}:{dose['dose']}"
                        ),
                    )
                    initial = v14.pilot._margin_matrix(env, qidx, limits)
                    baselines = {}
                    for baseline in BASELINES:
                        restored = (
                            v14.full.core.restore_warmstart_policy_shadow_snapshot(
                                env, robot, injected
                            )
                        )
                        identity = v14.full.core._restore_identity(restored)
                        restore_failures += int(not identity)
                        if not identity:
                            raise V15RecoveryComponentAblationError(
                                "component-ablation baseline restore lost identity"
                            )
                        baselines[baseline] = _dispatch_baseline(
                            env, qidx, limits, baseline=baseline
                        )
                    rows.append(
                        {
                            "environment_id": str(spec["environment_id"]),
                            "suite": str(spec["suite"]),
                            "task_id": int(spec["task_id"]),
                            "init_state_id": int(spec["init_state_id"]),
                            "lane_id": (
                                f"{spec['environment_id']}:joint{joint_index}:"
                                f"{side}:{dose['dose']}"
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
    original = base.calibration.v14.pilot.BASELINES
    base.calibration.v14.pilot.BASELINES = BASELINES
    try:
        yield
    finally:
        base.calibration.v14.pilot.BASELINES = original


def _margin_trace(report: Mapping[str, Any]) -> np.ndarray:
    values = []
    for step in report["actual_joint_side_margins"]:
        values.append(base.calibration.v14.pilot.full_clean_margin_matrix(step))
    if not values:
        return np.empty((0, 7, 2), dtype=np.float64)
    return np.asarray(values, dtype=np.float64)


def _v15_2_v15_3_identity(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    scalar_fields = (
        "executed_step_count",
        "policy_decision_count",
        "trigger_count",
        "intervention_count",
        "deadlock_count",
        "reactive_stop_count",
        "shadow_env_step_count",
        "restore_failure_count",
        "exact_action_mismatch_count",
        "below_floor_count",
        "crossing_count",
        "observed_state_count",
        "observed_side_value_count",
        "current_edge_selected_count",
        "floor_edge_selected_count",
        "selected_recovery_count",
        "selected_floor_violation_count",
    )
    scalar_mismatches = 0
    trace_shape_mismatches = 0
    maximum_margin_error = 0.0
    for row in rows:
        prior = row["baselines"][PRIORITY_BASELINE]
        attributed = row["baselines"][V15_3_BASELINE]
        scalar_mismatches += sum(
            prior.get(field) != attributed.get(field) for field in scalar_fields
        )
        prior_trace = _margin_trace(prior)
        attributed_trace = _margin_trace(attributed)
        if prior_trace.shape != attributed_trace.shape:
            trace_shape_mismatches += 1
            continue
        if prior_trace.size:
            maximum_margin_error = max(
                maximum_margin_error,
                float(np.max(np.abs(prior_trace - attributed_trace))),
            )
    return {
        "lane_count": len(rows),
        "scalar_mismatch_count": scalar_mismatches,
        "trace_shape_mismatch_lane_count": trace_shape_mismatches,
        "maximum_actual_margin_trace_error_rad": maximum_margin_error,
        "force_attribution_changes_mechanism": False,
    }


def _component_metrics(rows: list[Mapping[str, Any]], baseline: str) -> dict[str, Any]:
    reports = [row["baselines"][baseline] for row in rows]
    sum_fields = (
        "component_schema_mismatch_count",
        "v14_baseline_would_deadlock_count",
        "recovery_prevented_deadlock_count",
        "current_edge_attempted_count",
        "current_edge_selected_count",
        "floor_edge_attempted_count",
        "floor_edge_selected_count",
        "selected_recovery_count",
        "selected_floor_violation_count",
    )
    return {
        "lane_count": len(reports),
        **{
            field: sum(int(report.get(field, 0)) for report in reports)
            for field in sum_fields
        },
        "deadlock_lane_count": sum(
            int(report["deadlock_count"] > 0) for report in reports
        ),
        "crossing_count": sum(int(report["crossing_count"]) for report in reports),
        "below_floor_count": sum(
            int(report["below_floor_count"]) for report in reports
        ),
        "maximum_prediction_execution_error_rad": max(
            (
                float(report.get("maximum_prediction_execution_error_rad", 0.0))
                for report in reports
            ),
            default=0.0,
        ),
    }


def _shadow_identity(rows: list[Mapping[str, Any]]) -> float:
    maximum = 0.0
    for row in rows:
        no_guard = _margin_trace(row["baselines"]["no_guard"])
        shadow = _margin_trace(row["baselines"]["shadow_only"])
        if no_guard.shape != shadow.shape:
            return float("inf")
        if no_guard.size:
            maximum = max(maximum, float(np.max(np.abs(no_guard - shadow))))
    return maximum


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    shadow_error = _shadow_identity(rows)
    compatibility = dict(protocol)
    compatibility["gates"] = {
        **dict(protocol["gates"]),
        "no_guard_shadow_maximum_side_error_rad": protocol["gates"][
            "shadow_trace_maximum_side_error_rad"
        ],
    }
    with _patched_baselines():
        aggregate, inherited = base.calibration.v14._analyze(
            compatibility,
            rows,
            restore_failure_count=restore_failure_count,
            maximum_no_guard_shadow_error=shadow_error,
        )
    components = {
        baseline: _component_metrics(rows, baseline) for baseline in RECOVERY_BASELINES
    }
    identity = _v15_2_v15_3_identity(rows)
    recovery = base._recovery_metrics(rows)
    force = base._qualification_force_metrics(rows)
    contacts = base.calibration.audit._contact_aggregate(contact_reports)
    deadline = base.calibration.audit._deadline_report(
        rows,
        baseline=V15_3_BASELINE,
        deadline_seconds=float(protocol["gates"]["latency_budget_seconds"]),
    )
    gates = protocol["gates"]
    v14_force = float(aggregate["v14_predictive_brake_maximum_abs_constraint_force"])

    def maximum(group: str, field: str) -> float | None:
        value = force[group][field]["maximum"]
        return float(value) if value is not None else None

    attributable = maximum(
        "all_interventions",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
    )
    attributable_ratio = (
        attributable / v14_force if attributable is not None and v14_force > 0 else None
    )
    recovery_attributable = maximum(
        "recovery_interventions",
        "guard_scope_maximum_positive_joint_increment_over_pre_step",
    )
    post_absolute = maximum(
        "all_interventions", "post_step_maximum_abs_risk_constraint_force"
    )
    post_increment = maximum(
        "all_interventions",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    recovery_post_increment = maximum(
        "recovery_interventions",
        "post_step_maximum_positive_joint_increment_over_pre_step",
    )
    retained = (
        "environment_count",
        "environment_lane_coverage",
        "stress_lane_count",
        "baseline_lane_count",
        "restore_identity",
        "no_guard_shadow_trace_identity",
        "zero_policy_or_outcome_fields",
    )
    gate_results = {name: inherited[name] for name in retained}
    gate_results.update(
        {
            "expected_total_baseline_lane_count": (
                sum(int(aggregate[f"{name}_lane_count"]) for name in BASELINES)
                == gates["expected_baseline_lane_count"]
            ),
            "exact_action_identity": all(
                int(aggregate[f"{name}_exact_action_mismatch_count"])
                <= gates["exact_action_mismatch_count_max"]
                for name in BASELINES
            ),
            "stress_activation_crossing": (
                aggregate["no_guard_crossing_count"]
                >= gates["no_guard_crossing_count_min"]
            ),
            "stress_activation_below_floor": (
                aggregate["no_guard_below_floor_count"]
                >= gates["no_guard_below_floor_count_min"]
            ),
            "reactive_crossing_not_above_no_guard": (
                aggregate["reactive_stop_crossing_count"]
                <= aggregate["no_guard_crossing_count"]
            ),
            "reactive_below_floor_not_above_no_guard": (
                aggregate["reactive_stop_below_floor_count"]
                <= aggregate["no_guard_below_floor_count"]
            ),
            "v14_containment": (
                aggregate["v14_predictive_brake_crossing_count"] == 0
                and aggregate["v14_predictive_brake_below_floor_count"] == 0
            ),
            "v14_deadlock_activation": (
                aggregate["v14_predictive_brake_deadlock_lane_count"]
                >= gates["v14_deadlock_lane_count_min"]
            ),
            "all_recovery_variants_contain": all(
                components[name]["crossing_count"]
                <= gates["recovery_crossing_count_max"]
                and components[name]["below_floor_count"]
                <= gates["recovery_below_floor_count_max"]
                and components[name]["selected_floor_violation_count"]
                <= gates["selected_floor_violation_count_max"]
                for name in RECOVERY_BASELINES
            ),
            "all_component_schemas_match": all(
                components[name]["component_schema_mismatch_count"] == 0
                for name in (
                    FLOOR_BASELINE,
                    CURRENT_BASELINE,
                    PRIORITY_BASELINE,
                )
            ),
            "floor_recovery_activates": (
                components[FLOOR_BASELINE]["selected_recovery_count"]
                >= gates["component_selected_recovery_count_min"]
            ),
            "floor_recovery_reduces_deadlock_lanes": (
                components[FLOOR_BASELINE]["deadlock_lane_count"]
                < aggregate["v14_predictive_brake_deadlock_lane_count"]
            ),
            "current_edge_recovery_activates": (
                components[CURRENT_BASELINE]["current_edge_selected_count"]
                >= gates["component_selected_recovery_count_min"]
            ),
            "current_edge_deadlock_not_above_floor": (
                components[CURRENT_BASELINE]["deadlock_lane_count"]
                <= components[FLOOR_BASELINE]["deadlock_lane_count"]
            ),
            "priority_recovery_activates": (
                components[PRIORITY_BASELINE]["current_edge_selected_count"]
                >= gates["component_selected_recovery_count_min"]
            ),
            "priority_zero_residual_deadlock": (
                components[PRIORITY_BASELINE]["deadlock_lane_count"]
                <= gates["priority_residual_deadlock_lane_count_max"]
            ),
            "priority_uses_current_edge_before_floor": (
                components[PRIORITY_BASELINE]["floor_edge_selected_count"]
                <= gates["priority_floor_edge_selected_count_max"]
            ),
            "v15_3_zero_residual_deadlock": (
                components[V15_3_BASELINE]["deadlock_lane_count"]
                <= gates["v15_3_residual_deadlock_lane_count_max"]
            ),
            "v15_3_schema_identity": (recovery["v15_3_schema_mismatch_count"] == 0),
            "v15_3_force_attribution_active": (
                recovery["v15_3_force_attribution_inactive_count"] == 0
            ),
            "v15_2_candidate_priority_identity": (
                recovery["v15_2_priority_mismatch_count"] == 0
            ),
            "v15_3_recovery_prevention_identity": (
                recovery["paired_deadlock_lane_identity"] is True
                and recovery["v14_baseline_would_deadlock_count"]
                == recovery["recovery_prevented_deadlock_count"]
                and recovery["v15_3_v14_would_deadlock_lane_count"]
                == recovery["v15_3_recovery_prevented_deadlock_lane_count"]
            ),
            "v15_2_v15_3_scalar_identity": (identity["scalar_mismatch_count"] == 0),
            "v15_2_v15_3_trace_shape_identity": (
                identity["trace_shape_mismatch_lane_count"] == 0
            ),
            "v15_2_v15_3_margin_trace_identity": (
                identity["maximum_actual_margin_trace_error_rad"]
                <= gates["v15_2_v15_3_margin_trace_error_rad_max"]
            ),
            "v15_3_prediction_execution_error": (
                recovery["maximum_prediction_execution_error_rad"]
                <= gates["prediction_execution_error_rad_max"]
            ),
            "force_recomputation_identity": (
                force["legacy_force_recomputation_mismatch_count"]
                <= gates["force_recomputation_mismatch_count_max"]
            ),
            "v15_3_attributable_force_envelope": (
                attributable is not None
                and attributable <= gates["maximum_attributable_joint_force_increment"]
            ),
            "v15_3_relative_attributable_force_envelope": (
                attributable_ratio is not None
                and attributable_ratio
                <= gates["maximum_attributable_increment_to_v14_legacy_force_ratio"]
            ),
            "v15_3_post_step_absolute_force_envelope": (
                post_absolute is not None
                and post_absolute <= gates["maximum_post_step_absolute_risk_force"]
            ),
            "v15_3_post_step_increment_envelope": (
                post_increment is not None
                and post_increment
                <= gates["maximum_post_step_positive_joint_increment"]
            ),
            "v15_3_recovery_attributable_force_envelope": (
                recovery_attributable is not None
                and recovery_attributable
                <= gates["maximum_recovery_attributable_joint_force_increment"]
            ),
            "v15_3_recovery_post_step_increment_envelope": (
                recovery_post_increment is not None
                and recovery_post_increment
                <= gates["maximum_recovery_post_step_positive_joint_increment"]
            ),
            "active_contact_capacity_warning_free": (
                contacts["phases"]["active"]["contact_capacity_warning_count"]
                <= gates["active_contact_capacity_warning_count_max"]
            ),
            "active_contact_capacity_unsaturated": (
                contacts["phases"]["active"]["contact_saturation_count"]
                <= gates["active_contact_saturation_count_max"]
            ),
            "v15_3_latency_p95": (
                aggregate[f"{V15_3_BASELINE}_screen_latency_seconds_p95"] is not None
                and aggregate[f"{V15_3_BASELINE}_screen_latency_seconds_p95"]
                <= gates["screen_latency_seconds_p95_max"]
            ),
            "v15_3_latency_max": (
                aggregate[f"{V15_3_BASELINE}_screen_latency_seconds_max"] is not None
                and aggregate[f"{V15_3_BASELINE}_screen_latency_seconds_max"]
                <= gates["screen_latency_seconds_max"]
            ),
            "v15_3_100ms_deadline_miss_rate": (
                deadline["miss_rate"] is not None
                and deadline["miss_rate"] <= gates["screen_latency_100ms_miss_rate_max"]
            ),
        }
    )
    metrics = {
        "aggregate": aggregate,
        "components": components,
        "v15_2_v15_3_execution_identity": identity,
        "recovery": recovery,
        "force_attribution": force,
        "force_comparison": {
            "v14_legacy_maximum_abs_constraint_force": v14_force,
            "v15_3_maximum_attributable_joint_force_increment": attributable,
            "attributable_increment_to_v14_legacy_force_ratio": (attributable_ratio),
            "v15_3_maximum_post_step_absolute_risk_force": post_absolute,
            "v15_3_maximum_post_step_positive_joint_increment": post_increment,
            "v15_3_maximum_recovery_attributable_joint_force_increment": (
                recovery_attributable
            ),
            "v15_3_maximum_recovery_post_step_positive_joint_increment": (
                recovery_post_increment
            ),
        },
        "contact_capacity": contacts,
        "contact_reports": contact_reports,
        "v15_3_latency_budget": deadline,
        "claim_roles": {
            "paired_component_ablation": True,
            "force_attribution_changes_mechanism": False,
            "policy_or_task_outcome": False,
            "model_mismatch": False,
            "physical_safety": False,
        },
    }
    return metrics, gate_results


def _run_audited_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
    warnings: Any,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    environment_id = str(spec["environment_id"])
    warnings.environment_id = environment_id
    warnings.phase = "prebinding"
    contacts = base.calibration.audit._ContactAudit(environment_id)
    original_create = base.calibration.v14.base.create_env

    def audited_create(runtime: Any, args: Any) -> Any:
        warnings.phase = "prebinding"
        env = original_create(runtime, args)
        return base.calibration.audit._AuditedEnvironment(
            env, contacts=contacts, warnings=warnings
        )

    base.calibration.v14.base.create_env = audited_create
    try:
        rows, failures = _run_environment(spec, gpu=gpu)
    finally:
        base.calibration.v14.base.create_env = original_create
    return rows, failures, contacts.report(warnings)


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15RecoveryComponentAblationError(
            "component-ablation preflight failed: " + "; ".join(report["blockers"])
        )
    base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15RecoveryComponentAblationError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = base.calibration.audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, contacts = _run_audited_environment(
                spec, gpu=gpu, warnings=warnings
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
        "held_out_component_ablation_claim_authorized": qualification_pass,
        "task_utility_claim_authorized": False,
        "model_mismatch_claim_authorized": False,
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
            int(metrics["aggregate"][f"{name}_lane_count"]) for name in BASELINES
        ),
        "evidence_path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "checksums_path": checksums_path.relative_to(REPO_ROOT).as_posix(),
    }


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15RecoveryComponentAblationError(
            "component-ablation evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15RecoveryComponentAblationError(
            "component-ablation checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
        or evidence.get("task_utility_claim_authorized") is not False
        or evidence.get("model_mismatch_claim_authorized") is not False
        or evidence["integrity"]
        != {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        }
    ):
        raise V15RecoveryComponentAblationError(
            "component-ablation evidence identity differs"
        )
    recorded = evidence["analysis"]
    metrics, gates = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(recorded["aggregate"]["restore_failure_count"]),
        contact_reports=recorded["contact_reports"],
    )
    if (
        metrics != recorded
        or gates != evidence["gate_results"]
        or evidence["qualification_pass"] is not all(gates.values())
    ):
        raise V15RecoveryComponentAblationError("component-ablation analysis is stale")
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
        payload = execute(protocol, protocol_path=protocol_path, gpu=args.gpu)
    else:
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
