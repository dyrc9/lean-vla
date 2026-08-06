#!/usr/bin/env python3
"""Run the frozen v15.14 unified-force-envelope clean qualification."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery as online,
)
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_force_attributed_recovery as disabled_online,
)
from scripts import (  # noqa: E402
    run_v15_force_attributed_recovery_task_utility_qualification as predecessor,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.14-unified-force-envelope-"
    "recovery-task-utility-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.14-unified-force-envelope-"
    "recovery-task-utility-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_14_unified_force_envelope_task_utility_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_14_unified_force_envelope_"
    "task_utility_qualification_fresh1_protocol.json"
)
_L2_ARMS = {"execution_only", "dual"}
_UTILITY_GATES = predecessor._UTILITY_GATES
_BASE_ENRICH = predecessor._BASE_ENRICH
_SAME_MODEL_CANDIDATE_ID = "nominal_same_model_identity"
_LEGACY_UNGUARDED_CALIBRATION_GATE = (
    "v9_v14_prediction_execution_calibration"
)
_TASK_STATE_TRIGGER_MARGIN_RAD = 0.30
_TASK_RECOVERY_FORCE_INCREMENT_LIMIT = 10000.0
_TASK_METHOD_VERSION = "v15.14"


class V15BoundedStateTriggeredTaskUtilityError(RuntimeError):
    """Raised when v15.14 clean task-utility evidence differs."""


def _normalize_disabled_episode(payload: dict[str, Any]) -> dict[str, Any]:
    """Give disabled arms the v15.14 audit identity without enabling L2."""

    metadata = dict(payload["metadata"])
    if bool(metadata["l2_execution_integrity"]):
        raise V15BoundedStateTriggeredTaskUtilityError(
            "disabled-arm adapter received an enabled L2 episode"
        )
    metadata.update(
        {
            "runner_variant": online.RUNNER_VARIANT,
            "predictive_virtual_brake_schema": None,
            "bounded_state_triggered_recovery_active": False,
            "bounded_state_trigger_margin_rad": None,
            "bounded_guarded_candidate_rollout_budget": None,
            "bounded_state_target_offset_rad": None,
            "unguarded_shadow_rollout_active": False,
            "bounded_state_triggered_change_source_action": False,
            "bounded_state_triggered_outcome_informed_successor": True,
            "bounded_state_triggered_hard_real_time_claim": False,
            "bounded_state_triggered_physical_authority_claim": False,
            "bounded_disabled_arm_annotation_adapter": True,
            "task_runtime_method_version": _TASK_METHOD_VERSION,
            "task_runtime_state_trigger_margin_rad": None,
            "task_runtime_recovery_force_increment_limit": None,
            "task_runtime_same_model_identity_adapter_active": False,
            "task_runtime_model_mismatch_injected": False,
            "task_runtime_actual_parameter_read_by_selector": False,
            "task_runtime_task_outcome_read": False,
            "task_runtime_wait_step_adapter_active": False,
            "task_runtime_wait_step_adapter_count": 0,
            "task_runtime_bounded_core_bind_active": False,
            "task_runtime_bounded_core_bind_count": 0,
            "task_runtime_direct_adaptive_core_binding": False,
            "task_runtime_captured_v14_core_binding": False,
            "task_runtime_captured_v13_base_binding": False,
            "legacy_same_model_force_identity_gate_active": False,
            "v15_11_registered_force_envelope_gate_active": False,
        }
    )
    for trace in payload["trace"]:
        if trace.get("phase") != "policy":
            continue
        audit = trace.get("predictive_virtual_brake")
        if not isinstance(audit, dict) or audit.get("enabled") is not False:
            raise V15BoundedStateTriggeredTaskUtilityError(
                "disabled arm lacks a disabled predictive audit"
            )
        audit.update(
            {
                "schema": online.BRAKE_AUDIT_SCHEMA,
                "bounded_state_triggered_recovery_active": False,
                "state_triggered_screen_active": False,
                "state_trigger_reference": None,
                "state_trigger_margin_rad": None,
                "unguarded_shadow_rollout_performed": False,
                "bounded_guarded_candidate_rollout_budget": 0,
                "bounded_guarded_candidate_rollout_count": 0,
                "bounded_state_target_offset_rad": None,
                "bounded_state_triggered_change_source_action": False,
                "bounded_state_triggered_task_outcome_informed": False,
                "bounded_state_triggered_outcome_informed_successor": True,
                "bounded_disabled_arm_annotation_adapter": True,
                "task_runtime_method_version": _TASK_METHOD_VERSION,
                "task_runtime_state_trigger_margin_rad": None,
                "task_runtime_recovery_force_increment_limit": None,
                "task_runtime_same_model_identity_adapter_active": False,
                "task_runtime_wait_step_adapter_active": False,
                "task_runtime_bounded_core_bind_active": False,
                "task_runtime_direct_adaptive_core_binding": False,
                "task_runtime_captured_v14_core_binding": False,
                "task_runtime_captured_v13_base_binding": False,
                "legacy_same_model_force_identity_gate_active": False,
                "v15_11_registered_force_envelope_gate_active": False,
            }
        )
    payload["metadata"] = metadata
    disabled_online.v1._persist_annotated_episode(payload)
    return payload


def _wait_safe_incremental_step(
    incremental_class: type,
    original_step: Any,
    runtime_audit: dict[str, int],
    self: Any,
    action: Any,
) -> Any:
    """Bypass incremental post-audit enrichment only for wait steps."""

    if self._call_index < self._wait_steps:
        runtime_audit["wait_step_count"] += 1
        return super(incremental_class, self).step(action)
    runtime_audit["policy_core_bind_count"] += 1
    return original_step(self, action)


def _enrich_task_runtime_adaptive_audit(audit: dict[str, Any]) -> None:
    """Apply the frozen v15.6 enrichment after the directly bound core."""

    candidates = audit.get("candidates", [])
    all_candidates = audit.pop("_adaptive_all_evaluated_candidates", candidates)
    if not isinstance(candidates, list) or not isinstance(all_candidates, list):
        raise V15BoundedStateTriggeredTaskUtilityError(
            "task runtime adaptive audit lacks candidates"
        )
    selected_margin = audit.get("selected_guard_margin_rad")
    selected_profile = audit.get("selected_candidate_profile_id")
    selected_rows = [
        row
        for row in all_candidates
        if selected_margin is not None
        and float(row["guard_margin_rad"]) == float(selected_margin)
        and row["candidate_profile_id"] == selected_profile
    ]
    if len(selected_rows) > 1:
        raise V15BoundedStateTriggeredTaskUtilityError(
            "task runtime adaptive selected candidate is ambiguous"
        )
    selected = selected_rows[0] if selected_rows else None
    absolute_force_error = (
        0.0
        if selected is None
        else abs(
            float(
                selected[
                    "predicted_post_step_maximum_abs_risk_constraint_force"
                ]
            )
            - float(audit["post_step_maximum_abs_risk_constraint_force"])
        )
    )
    positive_increment_error = (
        0.0
        if selected is None
        else abs(
            float(
                selected[
                    "predicted_post_step_maximum_positive_joint_increment"
                ]
            )
            - float(
                audit[
                    "post_step_maximum_positive_joint_increment_over_pre_step"
                ]
            )
        )
    )
    prediction_identity = bool(
        absolute_force_error <= 1e-12
        and positive_increment_error <= 1e-12
    )
    standard_base_eligible = sum(
        row.get("base_safety_eligible") is True
        for row in all_candidates
        if row.get("recovery_candidate") is not True
    )
    baseline_would_deadlock = bool(
        audit.get("triggered") is True and standard_base_eligible == 0
    )
    current_edge = audit.get("current_edge_recovery_configured_margin_rad")
    recovery_selected = bool(
        selected is not None and selected["recovery_candidate"] is True
    )
    fallback_selected = bool(
        selected is not None and selected["fallback_profile"] is True
    )
    extended_selected = bool(
        selected is not None
        and selected["candidate_profile_id"] == "soft_extended_recovery"
    )
    for row in all_candidates:
        if "physical_guard_margin_rad" in row:
            row["compatibility_guard_margin_rad"] = row["guard_margin_rad"]
            row["guard_margin_rad"] = row.pop("physical_guard_margin_rad")
    audit.update(
        {
            "schema": online.adaptive.BRAKE_AUDIT_SCHEMA,
            "force_constrained_recovery_active": bool(
                audit.get("enabled") is True
            ),
            "adaptive_force_recovery_active": bool(audit.get("enabled") is True),
            "adaptive_proactive_trigger_margin_rad": (
                online.adaptive.PROACTIVE_TRIGGER_MARGIN_RAD
            ),
            "force_constrained_guard_solref": (
                list(selected["guard_solref"])
                if selected is not None
                else list(online.adaptive.SOFT_GUARD_SOLREF)
            ),
            "candidate_post_force_prediction_active": bool(
                audit.get("enabled") is True
            ),
            "selected_post_force_prediction_execution_identity": (
                prediction_identity
            ),
            "selected_post_force_prediction_absolute_error": (
                absolute_force_error
            ),
            "selected_post_force_positive_increment_absolute_error": (
                positive_increment_error
            ),
            "legacy_same_model_force_identity_gate_active": False,
            "v15_11_registered_force_envelope_gate_active": True,
            "base_safety_eligible_candidate_count": sum(
                row.get("base_safety_eligible") is True
                for row in all_candidates
            ),
            "force_feasible_candidate_count": sum(
                row.get("force_feasible") is True
                and row.get("base_safety_eligible") is True
                for row in all_candidates
            ),
            "force_rejected_base_eligible_candidate_count": sum(
                row.get("base_safety_eligible") is True
                and row.get("force_feasible") is not True
                for row in all_candidates
            ),
            "selected_force_feasible": bool(
                selected is None or selected.get("force_feasible") is True
            ),
            "v14_baseline_eligible_candidate_count": standard_base_eligible,
            "v14_baseline_would_deadlock": baseline_would_deadlock,
            "floor_guard_recovery_selected": bool(
                selected_margin is not None
                and float(selected_margin)
                == online.adaptive.RECOVERY_GUARD_MARGIN_RAD
            ),
            "current_edge_recovery_selected": bool(
                recovery_selected
                and selected_margin is not None
                and current_edge is not None
                and np.isclose(
                    float(selected_margin),
                    float(current_edge),
                    rtol=0.0,
                    atol=(
                        online.adaptive.predecessor.CURRENT_EDGE_EPSILON_RAD
                        * 2.0
                    ),
                )
            ),
            "floor_or_current_edge_recovery_selected": recovery_selected,
            "floor_or_current_edge_recovery_prevented_deadlock": bool(
                baseline_would_deadlock
                and recovery_selected
                and audit.get("deadlock") is False
            ),
            "adaptive_recovery_ladder_active": True,
            "adaptive_extended_recovery_evaluated": bool(
                audit.get("extended_recovery_evaluated") is True
            ),
            "adaptive_extended_recovery_selected": extended_selected,
            "adaptive_fallback_profile_evaluated": bool(
                audit.get("fallback_profile_evaluated") is True
            ),
            "adaptive_fallback_profile_selected": fallback_selected,
            "selected_candidate_profile_id": selected_profile,
            "force_constraints_change_source_action": False,
            "force_constraints_task_outcome_informed": False,
            "force_constraints_physical_authority_claim": False,
            "candidates": all_candidates,
            "task_runtime_direct_adaptive_core_binding": True,
            "task_runtime_captured_v14_core_binding": True,
            "task_runtime_captured_v13_base_binding": True,
        }
    )


@contextmanager
def _patched_same_model_runtime() -> Iterator[dict[str, int]]:
    original_calibrate = online.observed_force._calibrate_shadow_model
    original_attach = online.pre_step._attach_setup_calibration
    original_state_trigger_margin = online.STATE_TRIGGER_MARGIN_RAD
    force_module = online.adaptive.predecessor
    original_recovery_scope_force_limit = (
        force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
    )
    original_recovery_post_force_limit = (
        force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
    )
    incremental_class = online.pre_step._INCREMENTAL_BASE_CLASS
    original_incremental_step = incremental_class.step
    adaptive_class = online.adaptive.MultiJointAdaptiveForceRecoveryEnvironment
    original_adaptive_step = adaptive_class.step
    v14_core_class = online.v14.MultiJointPredictiveVirtualBrakeEnvironment
    v13_base_class = online.v14.core.PredictiveVirtualBrakeEnvironment
    top_class = online.MultiJointBoundedStateTriggeredRecoveryEnvironment
    original_top_step = top_class.step
    runtime_audit = {
        "wait_step_count": 0,
        "policy_core_bind_count": 0,
        "bounded_core_call_count": 0,
        "bounded_policy_audit_count": 0,
    }

    def bounded_core(self: Any, action: Any) -> Any:
        before = len(self.observations)
        runtime_audit["bounded_core_call_count"] += 1
        runtime_v13_class = online.v14.core.PredictiveVirtualBrakeEnvironment
        online.v14.core.PredictiveVirtualBrakeEnvironment = v13_base_class
        try:
            transition = online._bounded_state_triggered_core_step(self, action)
        finally:
            online.v14.core.PredictiveVirtualBrakeEnvironment = (
                runtime_v13_class
            )
        if len(self.observations) > before:
            audit = self.observations[-1]
            if (
                not isinstance(audit, dict)
                or "bounded_guarded_candidate_rollout_count" not in audit
            ):
                raise V15BoundedStateTriggeredTaskUtilityError(
                    "task runtime did not bind the v15.14 bounded core"
                )
            runtime_audit["bounded_policy_audit_count"] += 1
        return transition

    def calibrate(env: Any) -> dict[str, Any]:
        result = original_calibrate(env)
        if result.get("active") is True:
            return result
        return _same_model_calibration_from_unavailable(result)

    def attach(audit: dict[str, Any], calibration: Mapping[str, Any]) -> None:
        if calibration.get("task_runtime_same_model_identity_adapter") is True:
            _attach_same_model_calibration_from_identity(audit, calibration)
        else:
            original_attach(audit, calibration)

    def incremental_step(self: Any, action: Any) -> Any:
        return _wait_safe_incremental_step(
            incremental_class,
            original_incremental_step,
            runtime_audit,
            self,
            action,
        )

    def adaptive_step(self: Any, action: Any) -> Any:
        before = len(self.observations)
        original_v14_step = v14_core_class.step
        original_config = (
            online.adaptive.priority.CurrentEdgePriorityRecoveryConfig
        )
        v14_core_class.step = bounded_core
        online.adaptive.priority.CurrentEdgePriorityRecoveryConfig = (
            online.adaptive.AdaptiveForceRecoveryConfig
        )
        try:
            transition = super(adaptive_class, self).step(action)
        finally:
            online.adaptive.priority.CurrentEdgePriorityRecoveryConfig = (
                original_config
            )
            v14_core_class.step = original_v14_step
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise V15BoundedStateTriggeredTaskUtilityError(
                "task runtime adaptive environment produced a non-object audit"
            )
        _enrich_task_runtime_adaptive_audit(audit)
        return transition

    def diagnostic_top_step(self: Any, action: Any) -> Any:
        try:
            return original_top_step(self, action)
        except KeyError as exc:
            audit = self.observations[-1] if self.observations else None
            details = {
                "missing_key": str(exc),
                "runtime_audit": dict(runtime_audit),
                "observation_count": len(self.observations),
                "last_schema": (
                    audit.get("schema") if isinstance(audit, dict) else None
                ),
                "last_keys": (
                    sorted(audit) if isinstance(audit, dict) else None
                ),
            }
            raise V15BoundedStateTriggeredTaskUtilityError(
                f"task-runtime bounded-core diagnostic: {details}"
            ) from exc

    online.observed_force._calibrate_shadow_model = calibrate
    online.pre_step._attach_setup_calibration = attach
    online.STATE_TRIGGER_MARGIN_RAD = _TASK_STATE_TRIGGER_MARGIN_RAD
    force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT = (
        _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
    )
    force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT = (
        _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
    )
    incremental_class.step = incremental_step
    adaptive_class.step = adaptive_step
    top_class.step = diagnostic_top_step
    try:
        yield runtime_audit
    finally:
        top_class.step = original_top_step
        adaptive_class.step = original_adaptive_step
        incremental_class.step = original_incremental_step
        online.pre_step._attach_setup_calibration = original_attach
        online.observed_force._calibrate_shadow_model = original_calibrate
        online.STATE_TRIGGER_MARGIN_RAD = original_state_trigger_margin
        force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT = (
            original_recovery_scope_force_limit
        )
        force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT = (
            original_recovery_post_force_limit
        )


def _same_model_calibration_from_unavailable(
    result: Mapping[str, Any]
) -> dict[str, Any]:
    """Return an explicit nominal binding for a same-model task runtime."""

    if (
        result.get("interface_available") is not False
        or result.get("active") is not False
        or result.get("bind_identity") is not True
    ):
        raise V15BoundedStateTriggeredTaskUtilityError(
            "same-model runtime calibration contract differs"
        )
    return {
        "interface_available": False,
        "active": True,
        "candidate_count": 1,
        "selected_candidate_id": _SAME_MODEL_CANDIDATE_ID,
        "selected_residual": 0.0,
        "minimum_residual_candidate_count": 1,
        "bind_identity": True,
        "latency_seconds": 0.0,
        "candidate_residuals": [
            {
                "candidate_id": _SAME_MODEL_CANDIDATE_ID,
                "maximum_abs_force_residual": 0.0,
            }
        ],
        "task_runtime_same_model_identity_adapter": True,
        "model_mismatch_injected": False,
        "actual_parameter_read_by_selector": False,
        "task_outcome_read": False,
    }


def _attach_same_model_calibration_from_identity(
    audit: dict[str, Any], calibration: Mapping[str, Any]
) -> None:
    """Audit nominal identity without claiming model-bank calibration."""

    if (
        calibration.get("interface_available") is not False
        or calibration.get("active") is not True
        or calibration.get("candidate_count") != 1
        or calibration.get("selected_candidate_id") != _SAME_MODEL_CANDIDATE_ID
        or calibration.get("selected_residual") != 0.0
        or calibration.get("bind_identity") is not True
        or calibration.get("model_mismatch_injected") is not False
        or calibration.get("actual_parameter_read_by_selector") is not False
        or calibration.get("task_outcome_read") is not False
    ):
        raise V15BoundedStateTriggeredTaskUtilityError(
            "same-model identity binding is incomplete"
        )
    original_screen_latency = float(audit["screen_latency_seconds"])
    audit.update(
        {
            "schema": online.pre_step.BRAKE_AUDIT_SCHEMA,
            "pre_step_shadow_calibration_active": True,
            "pre_step_shadow_calibration_reused": True,
            "pre_step_shadow_model_bank_candidate_count": 1,
            "pre_step_shadow_selected_candidate_id": _SAME_MODEL_CANDIDATE_ID,
            "pre_step_shadow_selected_residual": 0.0,
            "pre_step_shadow_minimum_residual_candidate_count": 1,
            "pre_step_shadow_bind_identity": True,
            "pre_step_shadow_calibration_latency_seconds": 0.0,
            "pre_step_shadow_calibration_outside_action_critical_path": True,
            "pre_step_shadow_calibration_change_source_action": False,
            "pre_step_shadow_calibration_task_outcome_informed": False,
            "task_runtime_same_model_identity_adapter_active": True,
            "task_runtime_model_mismatch_injected": False,
            "task_runtime_actual_parameter_read_by_selector": False,
            "task_runtime_task_outcome_read": False,
        }
    )
    if float(audit["screen_latency_seconds"]) != original_screen_latency:
        raise V15BoundedStateTriggeredTaskUtilityError(
            "same-model identity binding changed action screen latency"
        )


def _run_episode_adapter(**kwargs: Any) -> dict[str, Any]:
    args = kwargs.get("args")
    enabled = getattr(args, "l2_execution_integrity", None) == "on"
    if enabled:
        with _patched_same_model_runtime() as runtime_audit:
            payload = online.run_episode(**kwargs)
        expected_wait_steps = int(getattr(args, "num_steps_wait"))
        if runtime_audit["wait_step_count"] != expected_wait_steps:
            raise V15BoundedStateTriggeredTaskUtilityError(
                "task-runtime wait-step adapter coverage differs"
            )
        policy_audit_count = sum(
            trace.get("phase") == "policy" for trace in payload["trace"]
        )
        if (
            runtime_audit["policy_core_bind_count"] != policy_audit_count
            or runtime_audit["bounded_policy_audit_count"]
            != policy_audit_count
            or runtime_audit["bounded_core_call_count"]
            != expected_wait_steps + policy_audit_count
        ):
            raise V15BoundedStateTriggeredTaskUtilityError(
                "task-runtime bounded-core coverage differs"
            )
        metadata = dict(payload["metadata"])
        metadata.update(
            {
                "bounded_state_triggered_outcome_informed_successor": True,
                "task_runtime_method_version": _TASK_METHOD_VERSION,
                "task_runtime_state_trigger_margin_rad": (
                    _TASK_STATE_TRIGGER_MARGIN_RAD
                ),
                "task_runtime_recovery_force_increment_limit": (
                    _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
                ),
                "task_runtime_same_model_identity_adapter_active": True,
                "task_runtime_model_mismatch_injected": False,
                "task_runtime_actual_parameter_read_by_selector": False,
                "task_runtime_task_outcome_read": False,
                "task_runtime_wait_step_adapter_active": True,
                "task_runtime_wait_step_adapter_count": runtime_audit[
                    "wait_step_count"
                ],
                "task_runtime_bounded_core_bind_active": True,
                "task_runtime_bounded_core_bind_count": runtime_audit[
                    "policy_core_bind_count"
                ],
                "task_runtime_direct_adaptive_core_binding": True,
                "task_runtime_captured_v14_core_binding": True,
                "task_runtime_captured_v13_base_binding": True,
                "legacy_same_model_force_identity_gate_active": False,
                "v15_11_registered_force_envelope_gate_active": True,
            }
        )
        for trace in payload["trace"]:
            if trace.get("phase") != "policy":
                continue
            audit = trace.get("predictive_virtual_brake")
            if not isinstance(audit, dict) or audit.get("enabled") is not True:
                raise V15BoundedStateTriggeredTaskUtilityError(
                    "enabled arm lacks predictive audit"
                )
            audit.update(
                {
                    "bounded_state_triggered_outcome_informed_successor": True,
                    "task_runtime_method_version": _TASK_METHOD_VERSION,
                    "task_runtime_state_trigger_margin_rad": (
                        _TASK_STATE_TRIGGER_MARGIN_RAD
                    ),
                    "task_runtime_recovery_force_increment_limit": (
                        _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
                    ),
                    "task_runtime_wait_step_adapter_active": True,
                    "task_runtime_wait_step_adapter_count": runtime_audit[
                        "wait_step_count"
                    ],
                    "task_runtime_bounded_core_bind_active": True,
                    "task_runtime_bounded_core_bind_count": runtime_audit[
                        "policy_core_bind_count"
                    ],
                    "task_runtime_direct_adaptive_core_binding": True,
                    "task_runtime_captured_v14_core_binding": True,
                    "task_runtime_captured_v13_base_binding": True,
                    "legacy_same_model_force_identity_gate_active": False,
                    "v15_11_registered_force_envelope_gate_active": True,
                }
            )
        payload["metadata"] = metadata
        disabled_online.v1._persist_annotated_episode(payload)
        return payload
    return _normalize_disabled_episode(disabled_online.run_episode(**kwargs))


class _OnlineAdapter:
    """Expose v15.14 plus legacy constants required by four-arm audit."""

    RUNNER_VARIANT = online.RUNNER_VARIANT
    BRAKE_AUDIT_SCHEMA = online.BRAKE_AUDIT_SCHEMA
    JOINT_COUNT = disabled_online.JOINT_COUNT
    JOINT_SIDES = disabled_online.JOINT_SIDES
    TARGET_JOINT_INDEX = disabled_online.TARGET_JOINT_INDEX
    TARGET_JOINT_SIDE = disabled_online.TARGET_JOINT_SIDE
    BRAKE_MARGINS_RAD = disabled_online.BRAKE_MARGINS_RAD
    TRIGGER_MARGIN_RAD = disabled_online.TRIGGER_MARGIN_RAD
    SAFE_MARGIN_FLOOR_RAD = disabled_online.SAFE_MARGIN_FLOOR_RAD
    GUARD_SOLREF = disabled_online.GUARD_SOLREF
    GUARD_SOLIMP = disabled_online.GUARD_SOLIMP
    run_episode = staticmethod(_run_episode_adapter)


def _v15_11_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters: Counter[str] = Counter()
    metadata_mismatches = 0
    latencies: list[float] = []
    prediction_errors: list[float] = []
    legacy_force_prediction_errors: list[float] = []
    forces: list[float] = []
    maximum_rollout_count = 0
    expected_wait_steps = int(protocol["episode_constants"]["num_steps_wait"])

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        l2_enabled = arm in _L2_ARMS
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        metadata = episode["metadata"]
        expected_metadata = {
            "runner_variant": online.RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                online.BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "bounded_state_triggered_recovery_active": l2_enabled,
            "bounded_state_trigger_margin_rad": (
                _TASK_STATE_TRIGGER_MARGIN_RAD if l2_enabled else None
            ),
            "bounded_guarded_candidate_rollout_budget": (
                online.MAX_GUARDED_CANDIDATE_ROLLOUTS
                if l2_enabled
                else None
            ),
            "bounded_state_target_offset_rad": (
                online.STATE_TARGET_OFFSET_RAD if l2_enabled else None
            ),
            "unguarded_shadow_rollout_active": False,
            "bounded_state_triggered_change_source_action": False,
            "bounded_state_triggered_outcome_informed_successor": True,
            "bounded_state_triggered_hard_real_time_claim": False,
            "bounded_state_triggered_physical_authority_claim": False,
            "task_runtime_same_model_identity_adapter_active": l2_enabled,
            "task_runtime_method_version": _TASK_METHOD_VERSION,
            "task_runtime_state_trigger_margin_rad": (
                _TASK_STATE_TRIGGER_MARGIN_RAD if l2_enabled else None
            ),
            "task_runtime_recovery_force_increment_limit": (
                _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
                if l2_enabled
                else None
            ),
            "task_runtime_model_mismatch_injected": False,
            "task_runtime_actual_parameter_read_by_selector": False,
            "task_runtime_task_outcome_read": False,
            "task_runtime_wait_step_adapter_active": l2_enabled,
            "task_runtime_wait_step_adapter_count": (
                expected_wait_steps if l2_enabled else 0
            ),
            "task_runtime_bounded_core_bind_active": l2_enabled,
            "task_runtime_direct_adaptive_core_binding": l2_enabled,
            "task_runtime_captured_v14_core_binding": l2_enabled,
            "task_runtime_captured_v13_base_binding": l2_enabled,
            "legacy_same_model_force_identity_gate_active": False,
            "v15_11_registered_force_envelope_gate_active": l2_enabled,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value
            for key, value in expected_metadata.items()
        )

        for trace in episode["trace"]:
            if trace.get("phase") != "policy":
                continue
            counters["policy_audit_count"] += 1
            audit = trace.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
                or audit.get("enabled") is not l2_enabled
            ):
                raise V15BoundedStateTriggeredTaskUtilityError(
                    f"v15.14 audit identity differs: {episode_id}"
                )
            if not l2_enabled:
                counters["disabled_audit_count"] += 1
                counters["disabled_bounded_active_count"] += int(
                    audit.get("bounded_state_triggered_recovery_active")
                    is not False
                )
                counters["disabled_rollout_count"] += int(
                    audit.get("bounded_guarded_candidate_rollout_count", 0)
                )
                continue

            counters["l2_audit_count"] += 1
            counters["same_model_identity_failure_count"] += int(
                audit.get("task_runtime_same_model_identity_adapter_active")
                is not True
                or audit.get("task_runtime_model_mismatch_injected") is not False
                or audit.get("task_runtime_actual_parameter_read_by_selector")
                is not False
                or audit.get("task_runtime_task_outcome_read") is not False
                or audit.get("pre_step_shadow_model_bank_candidate_count") != 1
                or audit.get("pre_step_shadow_selected_candidate_id")
                != _SAME_MODEL_CANDIDATE_ID
                or audit.get("pre_step_shadow_bind_identity") is not True
            )
            counters["wait_step_adapter_failure_count"] += int(
                audit.get("task_runtime_wait_step_adapter_active") is not True
                or audit.get("task_runtime_wait_step_adapter_count")
                != expected_wait_steps
            )
            counters["bounded_core_bind_failure_count"] += int(
                audit.get("task_runtime_bounded_core_bind_active") is not True
                or int(audit.get("task_runtime_bounded_core_bind_count", 0))
                <= 0
                or audit.get("task_runtime_direct_adaptive_core_binding")
                is not True
                or audit.get("task_runtime_captured_v14_core_binding")
                is not True
                or audit.get("task_runtime_captured_v13_base_binding")
                is not True
                or audit.get("legacy_same_model_force_identity_gate_active")
                is not False
                or audit.get("v15_11_registered_force_envelope_gate_active")
                is not True
            )
            counters["legacy_force_identity_divergence_count"] += int(
                audit.get("selected_post_force_prediction_execution_identity")
                is not True
            )
            legacy_force_prediction_errors.extend(
                (
                    abs(
                        float(
                            audit.get(
                                "selected_post_force_prediction_absolute_error",
                                0.0,
                            )
                        )
                    ),
                    abs(
                        float(
                            audit.get(
                                "selected_post_force_positive_increment_absolute_error",
                                0.0,
                            )
                        )
                    ),
                )
            )
            counters["bounded_inactive_count"] += int(
                audit.get("bounded_state_triggered_recovery_active")
                is not True
            )
            counters["state_trigger_identity_failure_count"] += int(
                audit.get("state_triggered_screen_active") is not True
                or audit.get("state_trigger_reference")
                != "current_joint_side_margins"
                or audit.get("state_trigger_margin_rad")
                != _TASK_STATE_TRIGGER_MARGIN_RAD
            )
            counters["task_trigger_successor_identity_failure_count"] += int(
                audit.get("bounded_state_triggered_outcome_informed_successor")
                is not True
                or audit.get("task_runtime_method_version")
                != _TASK_METHOD_VERSION
                or audit.get("task_runtime_state_trigger_margin_rad")
                != _TASK_STATE_TRIGGER_MARGIN_RAD
                or audit.get("task_runtime_recovery_force_increment_limit")
                != _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
            )
            counters["task_outcome_interference_count"] += int(
                audit.get("bounded_state_triggered_task_outcome_informed")
                is not False
            )
            counters["unguarded_shadow_rollout_count"] += int(
                audit.get("unguarded_shadow_rollout_performed") is not False
            )
            rollout_count = int(
                audit.get("bounded_guarded_candidate_rollout_count", -1)
            )
            maximum_rollout_count = max(maximum_rollout_count, rollout_count)
            counters["rollout_budget_violation_count"] += int(
                rollout_count < 0
                or rollout_count > online.MAX_GUARDED_CANDIDATE_ROLLOUTS
            )
            counters["deadlock_count"] += int(audit.get("deadlock") is True)
            counters["actual_crossing_count"] += int(
                float(audit["actual_minimum_margin_rad"]) < 0.0
            )
            signals = trace.get("saber_constraint_signals")
            if not isinstance(signals, Mapping):
                raise V15BoundedStateTriggeredTaskUtilityError(
                    f"v15.14 trace lacks constraint signals: {episode_id}"
                )
            counters["joint_limit_violation_step_count"] += int(
                signals.get("joint_limit_violation") is True
            )
            if audit.get("screen_performed") is True:
                latency = float(audit["screen_latency_seconds"])
                latencies.append(latency)
                counters["screen_latency_100ms_miss_count"] += int(
                    latency > 0.1
                )
            error = audit.get("prediction_execution_margin_error_rad")
            if error is not None:
                prediction_errors.append(abs(float(error)))
            force_values = [
                float(audit.get("maximum_abs_target_constraint_force", 0.0)),
                float(
                    audit.get(
                        "guard_scope_reported_maximum_abs_risk_constraint_force",
                        0.0,
                    )
                ),
                float(
                    audit.get(
                        "post_step_maximum_abs_risk_constraint_force", 0.0
                    )
                ),
            ]
            force_values.extend(
                float(row.get("maximum_abs_constraint_force", 0.0))
                for row in audit.get("candidates", ())
                if isinstance(row, Mapping)
            )
            forces.extend(force_values)

    aggregate = evidence["aggregate"]
    expected_policy = int(aggregate["policy_step_count"])
    expected_l2 = int(aggregate["l2_policy_step_count"])
    latency_count = len(latencies)
    maximum_latency = max(latencies, default=0.0)
    latency_p95 = (
        float(np.percentile(np.asarray(latencies), 95))
        if latencies
        else 0.0
    )
    miss_rate = (
        counters["screen_latency_100ms_miss_count"] / latency_count
        if latency_count
        else 0.0
    )
    metrics = {
        **dict(sorted(counters.items())),
        "metadata_mismatch_count": metadata_mismatches,
        "maximum_guarded_candidate_rollouts_per_action": (
            maximum_rollout_count
        ),
        "maximum_abs_constraint_force": max(forces, default=0.0),
        "maximum_prediction_execution_error_rad": max(
            prediction_errors, default=0.0
        ),
        "maximum_legacy_force_prediction_absolute_error": max(
            legacy_force_prediction_errors, default=0.0
        ),
        "screen_latency_sample_count": latency_count,
        "maximum_screen_latency_seconds": maximum_latency,
        "screen_latency_p95_seconds": latency_p95,
        "screen_latency_100ms_miss_rate": miss_rate,
    }
    gate = protocol["v15_11_gates"]
    gates = {
        "v15_14_unified_force_envelope_identity": (
            protocol["design"].get("task_runtime_method_version")
            == _TASK_METHOD_VERSION
            and protocol["design"].get("state_trigger_margin_rad")
            == _TASK_STATE_TRIGGER_MARGIN_RAD
            and protocol["design"].get("predecessor_state_trigger_margin_rad")
            == _TASK_STATE_TRIGGER_MARGIN_RAD
            and protocol["design"].get("predecessor_method_version")
            == "v15.13"
            and protocol["design"].get(
                "recovery_force_increment_limit"
            )
            == _TASK_RECOVERY_FORCE_INCREMENT_LIMIT
            and protocol["design"].get(
                "predecessor_recovery_force_increment_limit"
            )
            == 2000.0
            and protocol["design"].get(
                "task_outcomes_used_for_method_successor_design"
            )
            is True
            and protocol["design"].get("safe_margin_floor_rad")
            == disabled_online.SAFE_MARGIN_FLOOR_RAD
            and counters["task_trigger_successor_identity_failure_count"] == 0
        ),
        "v15_11_metadata_matches": metadata_mismatches == 0,
        "v15_11_audit_coverage": (
            counters["policy_audit_count"] == expected_policy
            and counters["l2_audit_count"] == expected_l2
            and counters["disabled_audit_count"]
            == expected_policy - expected_l2
        ),
        "v15_11_disabled_arm_noninterference": (
            counters["disabled_bounded_active_count"] == 0
            and counters["disabled_rollout_count"] == 0
        ),
        "v15_11_same_model_task_runtime_identity": (
            counters["same_model_identity_failure_count"] == 0
        ),
        "v15_11_wait_step_task_runtime_identity": (
            counters["wait_step_adapter_failure_count"] == 0
        ),
        "v15_11_bounded_core_task_runtime_identity": (
            counters["bounded_core_bind_failure_count"] == 0
        ),
        "v15_11_bounded_state_trigger_identity": (
            counters["bounded_inactive_count"] == 0
            and counters["state_trigger_identity_failure_count"] == 0
            and counters["task_outcome_interference_count"] == 0
        ),
        "v15_11_zero_unguarded_shadow_rollout": (
            counters["unguarded_shadow_rollout_count"] == 0
        ),
        "v15_11_state_only_trigger_replaces_v14_unguarded_calibration": (
            protocol["design"].get(
                "legacy_v14_unguarded_prediction_calibration_gate_active"
            )
            is False
            and protocol["design"].get(
                "v15_11_selected_prediction_calibration_gate_active"
            )
            is True
            and counters["unguarded_shadow_rollout_count"] == 0
            and metrics["maximum_prediction_execution_error_rad"]
            <= gate["maximum_prediction_execution_error_rad"]
        ),
        "v15_11_guarded_candidate_rollout_budget": (
            counters["rollout_budget_violation_count"] == 0
            and maximum_rollout_count
            <= gate["maximum_guarded_candidate_rollouts_per_action"]
        ),
        "v15_11_zero_deadlock": (
            counters["deadlock_count"] <= gate["maximum_deadlock_count"]
        ),
        "v15_11_zero_actual_crossing": (
            counters["actual_crossing_count"]
            <= gate["maximum_actual_crossing_count"]
        ),
        "v15_11_zero_joint_limit_violation": (
            counters["joint_limit_violation_step_count"]
            <= gate["maximum_joint_limit_violation_step_count"]
        ),
        "v15_11_force_envelope": (
            metrics["maximum_abs_constraint_force"]
            <= gate["maximum_abs_constraint_force"]
        ),
        "v15_11_prediction_execution_error": (
            metrics["maximum_prediction_execution_error_rad"]
            <= gate["maximum_prediction_execution_error_rad"]
        ),
        "v15_11_latency_max": (
            maximum_latency <= gate["maximum_screen_latency_seconds"]
        ),
        "v15_11_latency_p95": (
            latency_p95 <= gate["maximum_screen_latency_p95_seconds"]
        ),
        "v15_11_latency_100ms_miss_rate": (
            miss_rate <= gate["maximum_screen_latency_100ms_miss_rate"]
        ),
    }
    return metrics, gates


def _qualification_enrich(
    protocol: Mapping[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    legacy_metrics, legacy_gates = predecessor._v15_3_metrics(
        protocol, enriched
    )
    metrics, gates = _v15_11_metrics(protocol, enriched)
    inherited_gate_results = dict(enriched["gate_results"])
    inherited_observation = inherited_gate_results.pop(
        _LEGACY_UNGUARDED_CALIBRATION_GATE, None
    )
    legacy_gate_results = dict(legacy_gates)
    legacy_observation = legacy_gate_results.pop(
        _LEGACY_UNGUARDED_CALIBRATION_GATE, inherited_observation
    )
    if (
        protocol["design"].get(
            "legacy_v14_unguarded_prediction_calibration_gate_active"
        )
        is not False
        or protocol["design"].get(
            "v15_11_selected_prediction_calibration_gate_active"
        )
        is not True
        or legacy_observation is None
    ):
        raise V15BoundedStateTriggeredTaskUtilityError(
            "v15.14 state-only calibration replacement differs"
        )
    gate_results = {
        **inherited_gate_results,
        **legacy_gate_results,
        **gates,
    }
    qualification_pass = bool(
        gate_results and all(value is True for value in gate_results.values())
    )
    utility_passed = all(
        gate_results.get(name) is True for name in _UTILITY_GATES
    )
    return {
        **enriched,
        "schema": EVIDENCE_SCHEMA,
        "classification": protocol[
            "pass_classification"
            if qualification_pass
            else "nonpass_classification"
        ],
        "gate_results": gate_results,
        "aggregate": {
            **enriched["aggregate"],
            **legacy_metrics,
            **metrics,
        },
        "nonapplicable_legacy_gate_observations": {
            _LEGACY_UNGUARDED_CALIBRATION_GATE: legacy_observation,
        },
        "qualification_pass": qualification_pass,
        "clean_utility_gate_passed": utility_passed,
        "task_utility_qualification_claim_authorized": qualification_pass,
        "held_out_population": True,
        "task_outcomes_observed_before_protocol_freeze": False,
        "model_mismatch_qualification_predecessor_bound": True,
        "attacked_stage_authorized": qualification_pass,
        "confirmatory_claim_authorized": False,
        "simulator_safety_claim_authorized_by_this_experiment": False,
        "method_claim": (
            "held-out clean task utility for frozen v15.14 unified-force-"
            "envelope bounded state-triggered observed-force simulator "
            "recovery"
        ),
    }


@contextmanager
def _patched_predecessor() -> Iterator[None]:
    originals = (
        predecessor.PROTOCOL_SCHEMA,
        predecessor.EVIDENCE_SCHEMA,
        predecessor.AUTHORIZED_STATUS,
        predecessor.DEFAULT_PROTOCOL,
        predecessor._qualification_enrich,
        predecessor.online,
    )
    predecessor.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    predecessor.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    predecessor.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    predecessor.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    predecessor._qualification_enrich = _qualification_enrich
    predecessor.online = _OnlineAdapter
    try:
        yield
    finally:
        (
            predecessor.PROTOCOL_SCHEMA,
            predecessor.EVIDENCE_SCHEMA,
            predecessor.AUTHORIZED_STATUS,
            predecessor.DEFAULT_PROTOCOL,
            predecessor._qualification_enrich,
            predecessor.online,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_predecessor():
        report = predecessor.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v15.14-unified-force-"
            "envelope-task-utility-qualification-preflight.v1"
        ),
        "qualification_role": True,
        "model_mismatch_qualification_predecessor_bound": True,
        "selected_pair_task_outcomes_observed_before_freeze": False,
        "globally_held_out_population": True,
        "confirmatory_safety_claim_authorized": False,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_predecessor():
        return predecessor.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    with _patched_predecessor():
        return predecessor.validate_results(
            protocol, protocol_path=protocol_path
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    elif args.execute:
        if args.policy_gpu is None or args.egl_gpu is None:
            parser.error("--execute requires --policy-gpu and --egl-gpu")
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol, protocol_path=protocol_path
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
