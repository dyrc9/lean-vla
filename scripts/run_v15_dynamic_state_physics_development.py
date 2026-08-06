#!/usr/bin/env python3
"""Develop v15.4 on the outcome-disclosed v15.3 physics population.

The predecessor physics result disclosed that the shared replay harness did
not restore two Python-side states: the gripper action accumulator and the
dynamic-obstacle motion-generator phase.  This development successor keeps
the v15.3 guard candidates, ordering, thresholds, actions, force metrics,
physics conditions, and task/init population unchanged.  It routes every
outer baseline restore and every predictive shadow restore through the v15.4
dynamic-state snapshot.

This is result-informed development evidence.  It cannot revise the frozen
v15.3 NONPASS or authorize held-out/model-mismatch/task-utility claims.
"""

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
from proofalign.policy_shadow_dynamic_state_v15 import (  # noqa: E402
    DynamicStatePolicyShadowRestoreAssessment,
    capture_dynamic_state_policy_shadow_snapshot,
    restore_dynamic_state_policy_shadow_snapshot,
)
from scripts import run_l2_predictive_virtual_brake_v15_dynamic_state_recovery as recovery  # noqa: E402
from scripts import run_v15_force_attributed_recovery_physics_domain_robustness_qualification as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.4-dynamic-state-"
    "physics-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.4-dynamic-state-"
    "physics-development-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_4_dynamic_state_physics_development"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_development_protocol.json"
)
OLD_V15_BASELINE = predecessor.V15_BASELINE
V15_BASELINE = "v15_4_dynamic_state_recovery"
OLD_V14_BASELINE = "v14_predictive_brake"
V14_BASELINE = "v14_dynamic_state_predictive_brake"
BASELINES = (
    "no_guard",
    "reactive_stop",
    V14_BASELINE,
    V15_BASELINE,
)


class V15DynamicStatePhysicsDevelopmentError(RuntimeError):
    """Raised when the v15.4 development contract differs."""


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
        raise V15DynamicStatePhysicsDevelopmentError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development output root resolves to repository"
        )
    return root


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "outcome_disclosed_development": True,
        "qualification_claim": False,
        "model_mismatch_claim": False,
        "task_utility_claim": False,
        "real_time_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["physics_conditions"]
        != [dict(row) for row in predecessor.PHYSICS_CONDITIONS]
        or protocol["design"]["baselines"] != list(BASELINES)
        or protocol["design"]["doses"]
        != [
            dict(row)
            for row in predecessor.base.calibration.v14.pilot.DOSES
        ]
    ):
        raise V15DynamicStatePhysicsDevelopmentError(
            "unsupported or unauthorized v15.4 development protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15DynamicStatePhysicsDevelopmentError(
                f"v15.4 development source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15DynamicStatePhysicsDevelopmentError(
                "v15.4 development binding differs: "
                + str(binding["path"])
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15DynamicStatePhysicsDevelopmentError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh v15.4 development output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.4-dynamic-state-"
            "physics-development-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "condition_count": len(protocol["design"]["physics_conditions"]),
        "expected_stress_lane_count": protocol["gates"][
            "expected_total_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_total_baseline_lane_count"
        ],
        "output_root_absent": not root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "qualification_claim_authorized": False,
        "model_mismatch_claim_authorized": False,
    }


def _run_screened(env: Any) -> dict[str, Any]:
    calibration = predecessor.base.calibration
    wrapper = recovery.MultiJointDynamicStateRecoveryEnvironment(
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
    selected = [
        row
        for row in observations
        if row["recovery_selected_for_force_attribution"] is True
    ]
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
        # Compatibility names are consumed only by the frozen predecessor
        # analyzer and are renamed in persisted v15.4 evidence.
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
            != predecessor.base.calibration.RECOVERY_PRIORITY
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
        "dynamic_state_audit_count": len(observations),
        "dynamic_state_restore_failure_count": sum(
            row.get("dynamic_state_restore_identity") is not True
            for row in observations
        ),
        "dynamic_state_restore_assessment_count": sum(
            int(row["dynamic_state_restore_assessment_count"])
            for row in observations
        ),
        "dynamic_motion_generator_step_count": sum(
            int(row["dynamic_motion_generator_count"]) > 0
            for row in observations
        ),
        "gripper_pre_post_action_rows": [
            {
                "runner_step_id": int(row["runner_step_id"]),
                "pre": list(row["pre_step_gripper_current_action"]),
                "post": list(row["post_step_gripper_current_action"]),
            }
            for row in observations
        ],
        **calibration.v14.pilot._exposure(matrices),
    }


@contextmanager
def _patched_dynamic_runtime() -> Iterator[None]:
    """Use v15.4 snapshots for outer pairing and all predictive baselines."""

    core = predecessor.base.calibration.v14.full.core
    force_development = predecessor.base.force_development
    original_capture = core.capture_warmstart_policy_shadow_snapshot
    original_restore = core.restore_warmstart_policy_shadow_snapshot
    original_identity = core._restore_identity
    original_screened = force_development._run_screened

    def identity(assessment: Any) -> bool:
        return bool(
            original_identity(assessment)
            and isinstance(
                assessment,
                DynamicStatePolicyShadowRestoreAssessment,
            )
            and assessment.runtime_side_state_identity
        )

    core.capture_warmstart_policy_shadow_snapshot = (
        capture_dynamic_state_policy_shadow_snapshot
    )
    core.restore_warmstart_policy_shadow_snapshot = (
        restore_dynamic_state_policy_shadow_snapshot
    )
    core._restore_identity = identity
    force_development._run_screened = _run_screened
    try:
        yield
    finally:
        force_development._run_screened = original_screened
        core._restore_identity = original_identity
        core.restore_warmstart_policy_shadow_snapshot = original_restore
        core.capture_warmstart_policy_shadow_snapshot = original_capture


def _replace_names(value: Any, *, reverse: bool = False) -> Any:
    pairs = (
        (
            (V15_BASELINE, OLD_V15_BASELINE),
            (V14_BASELINE, OLD_V14_BASELINE),
            ("v15_4", "v15_3"),
        )
        if reverse
        else (
            (OLD_V15_BASELINE, V15_BASELINE),
            ("v15_3", "v15_4"),
            (OLD_V14_BASELINE, V14_BASELINE),
        )
    )

    def replace(text: str) -> str:
        result = text
        for old, new in pairs:
            result = result.replace(old, new)
        return result

    if isinstance(value, dict):
        return {
            replace(str(key)): _replace_names(item, reverse=reverse)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_names(item, reverse=reverse) for item in value]
    if isinstance(value, tuple):
        return tuple(
            _replace_names(item, reverse=reverse) for item in value
        )
    if isinstance(value, str):
        return replace(value)
    return value


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failures: Mapping[str, int],
    contact_reports: list[Mapping[str, Any]],
    physics_audits: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    compatibility_protocol = _replace_names(protocol, reverse=True)
    analysis, gates = predecessor._analyze(
        compatibility_protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    reports = [
        row["baselines"][OLD_V15_BASELINE] for row in rows
    ]
    state_metrics = {
        "v15_4_dynamic_state_audit_count": sum(
            int(report["dynamic_state_audit_count"])
            for report in reports
        ),
        "v15_4_dynamic_state_restore_failure_count": sum(
            int(report["dynamic_state_restore_failure_count"])
            for report in reports
        ),
        "v15_4_dynamic_state_restore_assessment_count": sum(
            int(report["dynamic_state_restore_assessment_count"])
            for report in reports
        ),
        "v15_4_dynamic_motion_generator_step_count": sum(
            int(report["dynamic_motion_generator_step_count"])
            for report in reports
        ),
    }
    gates = {
        **gates,
        "v15_4_dynamic_state_audit_coverage": (
            state_metrics["v15_4_dynamic_state_audit_count"]
            == protocol["gates"]["expected_v15_4_policy_step_count"]
        ),
        "v15_4_dynamic_state_restore_identity": (
            state_metrics[
                "v15_4_dynamic_state_restore_failure_count"
            ]
            == 0
        ),
        "v15_4_dynamic_motion_generator_activated": (
            state_metrics[
                "v15_4_dynamic_motion_generator_step_count"
            ]
            >= protocol["gates"][
                "minimum_dynamic_motion_generator_step_count"
            ]
        ),
    }
    analysis = {
        **analysis,
        "dynamic_state_metrics": state_metrics,
        "predecessor_nonpass_reinterpreted": False,
        "development_population_outcome_disclosed": True,
    }
    return analysis, gates


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development preflight failed: "
            + "; ".join(report["blockers"])
        )
    predecessor.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15DynamicStatePhysicsDevelopmentError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = predecessor.base.calibration.audit._WarningAudit()
    rows = []
    contact_reports = []
    physics_audits = []
    restore_failures = {
        str(row["condition_id"]): 0
        for row in predecessor.PHYSICS_CONDITIONS
    }
    mujoco.set_mju_user_warning(warnings)
    try:
        with _patched_dynamic_runtime():
            for condition in predecessor.PHYSICS_CONDITIONS:
                condition_id = str(condition["condition_id"])
                for spec in protocol["environments"]:
                    observed, failures, contacts, physics_audit = (
                        predecessor._run_audited_environment(
                            spec,
                            condition,
                            gpu=gpu,
                            warnings=warnings,
                        )
                    )
                    rows.extend(observed)
                    restore_failures[condition_id] += failures
                    contact_reports.append(contacts)
                    physics_audits.append(physics_audit)
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    analysis, gate_results = _analyze(
        protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    passed = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "development_pass": passed,
        "qualification_claim_authorized": False,
        "model_mismatch_claim_authorized": False,
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
        "baseline_execution_identity": {
            V14_BASELINE: (
                "Frozen v14 guard logic under the v15.4 dynamic-state "
                "snapshot harness."
            ),
            V15_BASELINE: (
                "Frozen v15.3 guard logic and force attribution under "
                "the v15.4 dynamic-state snapshot harness."
            ),
        },
        "gate_results": _replace_names(gate_results),
        "analysis": _replace_names(analysis),
        "lanes": _replace_names(rows),
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "development_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksum_path = root / "SHA256SUMS"
    checksum_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return evidence


def validate_results(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "development_evidence.json"
    checksum_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksum_path.is_file():
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development evidence is absent"
        )
    if checksum_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development evidence binding differs"
        )
    rows = _replace_names(evidence["lanes"], reverse=True)
    analysis, gates = _analyze(
        protocol,
        rows,
        restore_failures=evidence["analysis"][
            "restore_failure_count_by_condition"
        ],
        contact_reports=evidence["analysis"]["contact_reports"],
        physics_audits=evidence["analysis"][
            "physics_parameter_audits"
        ],
    )
    if (
        canonical_text(_replace_names(analysis))
        != canonical_text(evidence["analysis"])
        or canonical_text(_replace_names(gates))
        != canonical_text(evidence["gate_results"])
        or bool(evidence["development_pass"]) != all(gates.values())
    ):
        raise V15DynamicStatePhysicsDevelopmentError(
            "v15.4 development recomputation differs"
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        print(canonical_text(preflight(protocol, gpu=args.gpu)), end="")
        return 0
    if args.validate_results:
        evidence = validate_results(
            protocol, protocol_path=protocol_path
        )
        print(
            canonical_text(
                {
                    "schema": EVIDENCE_SCHEMA + ".validation",
                    "valid": True,
                    "development_pass": evidence["development_pass"],
                    "classification": evidence["classification"],
                }
            ),
            end="",
        )
        return 0
    evidence = execute(protocol, protocol_path=protocol_path, gpu=args.gpu)
    print(
        canonical_text(
            {
                "schema": EVIDENCE_SCHEMA + ".completion",
                "development_pass": evidence["development_pass"],
                "classification": evidence["classification"],
                "output_root": _output_root(protocol).relative_to(
                    REPO_ROOT
                ).as_posix(),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
