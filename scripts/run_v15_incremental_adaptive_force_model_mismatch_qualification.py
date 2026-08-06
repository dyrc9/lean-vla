#!/usr/bin/env python3
"""Qualify frozen v15.7 under registered shadow/actual model mismatch."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import inspect
import linecache
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Iterator, Mapping

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
    run_v15_incremental_adaptive_force_physics_qualification as predecessor,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "model-mismatch-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "model-mismatch-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_7_incremental_adaptive_force_model_mismatch_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "model_mismatch_qualification_protocol.json"
)
V14_BASELINE = predecessor.V14_BASELINE
V15_BASELINE = predecessor.V15_BASELINE
BASELINES = predecessor.BASELINES
MODEL_MISMATCH_CONDITIONS = (
    {
        "condition_id": "matched_nominal",
        "actual_arm_mass_scale": 1.0,
        "actual_joint_damping_scale": 1.0,
        "actual_arm_sliding_friction_scale": 1.0,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_mass_0_8x_shadow_nominal",
        "actual_arm_mass_scale": 0.8,
        "actual_joint_damping_scale": 1.0,
        "actual_arm_sliding_friction_scale": 1.0,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_mass_1_2x_shadow_nominal",
        "actual_arm_mass_scale": 1.2,
        "actual_joint_damping_scale": 1.0,
        "actual_arm_sliding_friction_scale": 1.0,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_damping_0_7x_shadow_nominal",
        "actual_arm_mass_scale": 1.0,
        "actual_joint_damping_scale": 0.7,
        "actual_arm_sliding_friction_scale": 1.0,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_damping_1_3x_shadow_nominal",
        "actual_arm_mass_scale": 1.0,
        "actual_joint_damping_scale": 1.3,
        "actual_arm_sliding_friction_scale": 1.0,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_friction_0_7x_shadow_nominal",
        "actual_arm_mass_scale": 1.0,
        "actual_joint_damping_scale": 1.0,
        "actual_arm_sliding_friction_scale": 0.7,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "actual_friction_1_3x_shadow_nominal",
        "actual_arm_mass_scale": 1.0,
        "actual_joint_damping_scale": 1.0,
        "actual_arm_sliding_friction_scale": 1.3,
        "shadow_arm_mass_scale": 1.0,
        "shadow_joint_damping_scale": 1.0,
        "shadow_arm_sliding_friction_scale": 1.0,
    },
)


class V15IncrementalAdaptiveForceModelMismatchQualificationError(RuntimeError):
    """Raised when the frozen model-mismatch contract differs."""


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch output root resolves to repository"
        )
    return root


def _expected_authorization() -> dict[str, bool]:
    return {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "physics_domain_robustness_claim": False,
        "model_mismatch_claim": True,
        "task_utility_claim": False,
        "real_time_claim": False,
    }


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    design = protocol.get("design", {})
    selection = protocol.get("selection", {})
    gates = protocol.get("gates", {})
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != _expected_authorization()
        or len(protocol.get("environments", ())) != 18
        or design.get("model_mismatch_conditions")
        != [dict(row) for row in MODEL_MISMATCH_CONDITIONS]
        or design.get("baselines") != list(BASELINES)
        or design.get("doses")
        != [
            dict(row)
            for row in predecessor.development.v156.v155.v154.predecessor.base.calibration.v14.pilot.DOSES
        ]
        or design.get("qualification_population") is not True
        or design.get("outcome_disclosed_population_reused") is not False
        or design.get("actual_and_shadow_models_separated") is not True
        or design.get("actual_model_restored_before_execution") is not True
        or design.get("shadow_model_used_only_for_counterfactual_steps")
        is not True
        or design.get("mechanism_parameters_unchanged_from_v15_7") is not True
        or design.get(
            "same_model_safety_force_and_latency_thresholds_unchanged"
        )
        is not True
        or design.get("same_model_prediction_identity_replaced_by_mismatch_audit")
        is not True
        or design.get("incremental_extended_search") is not True
        or design.get("maximum_extended_candidates_per_increment") != 1
        or gates.get("prediction_execution_error_rad_max") != 0.01
        or gates.get("model_mismatch_prediction_execution_error_rad_max")
        != 0.01
        or gates.get("expected_model_mismatch_predictive_run_count") != 10584
        or gates.get(
            "expected_nontrivial_model_mismatch_predictive_run_count"
        )
        != 9072
        or selection.get("all_prior_exact_task_init_pairs_excluded") is not True
        or selection.get("model_mismatch_results_observed_before_freeze")
        is not False
        or selection.get("task_outcomes_used_for_selection") is not False
    ):
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "unsupported or unauthorized v15.7 model-mismatch protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
                f"model-mismatch source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
                "model-mismatch binding differs: " + str(binding["path"])
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15IncrementalAdaptiveForceModelMismatchQualificationError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh model-mismatch output root already exists")
    return {
        "schema": EVIDENCE_SCHEMA.replace("evidence.v1", "preflight.v1"),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "condition_count": len(
            protocol["design"]["model_mismatch_conditions"]
        ),
        "expected_stress_lane_count": protocol["gates"][
            "expected_total_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_total_baseline_lane_count"
        ],
        "output_root_absent": not root.exists(),
        "model_mismatch_claim_authorized_on_pass": True,
        "task_outcome_read_authorized": False,
    }


def _condition_for_compatibility(condition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(condition),
        "arm_mass_scale": float(condition["actual_arm_mass_scale"]),
        "joint_damping_scale": float(
            condition["actual_joint_damping_scale"]
        ),
        "arm_sliding_friction_scale": float(
            condition["actual_arm_sliding_friction_scale"]
        ),
    }


COMPATIBILITY_CONDITIONS = tuple(
    _condition_for_compatibility(row) for row in MODEL_MISMATCH_CONDITIONS
)


def _stats(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "minimum": float(np.min(array)) if array.size else None,
        "maximum": float(np.max(array)) if array.size else None,
        "mean": float(np.mean(array)) if array.size else None,
    }


class _StepModelController:
    def __init__(
        self,
        *,
        env: Any,
        model: Any,
        body_ids: np.ndarray,
        dof_ids: np.ndarray,
        geom_ids: np.ndarray,
        joint_ids: np.ndarray,
        actual_mass: np.ndarray,
        actual_damping: np.ndarray,
        actual_friction: np.ndarray,
        shadow_mass: np.ndarray,
        shadow_damping: np.ndarray,
        shadow_friction: np.ndarray,
        audit: dict[str, Any],
        role_classifier: Callable[[], str] | None = None,
    ) -> None:
        self.env = env
        self.model = model
        self.body_ids = body_ids
        self.dof_ids = dof_ids
        self.geom_ids = geom_ids
        self.joint_ids = joint_ids
        self.actual = (actual_mass, actual_damping, actual_friction)
        self.shadow = (shadow_mass, shadow_damping, shadow_friction)
        self.audit = audit
        self.role_classifier = role_classifier

    def _switch(self, target: str) -> bool:
        mass, damping, friction = self.actual if target == "actual" else self.shadow
        self.model.body_mass[self.body_ids] = mass
        self.model.dof_damping[self.dof_ids] = damping
        self.model.geom_friction[self.geom_ids, 0] = friction
        self.env.sim.forward()
        identity = bool(
            np.array_equal(self.model.body_mass[self.body_ids], mass)
            and np.array_equal(self.model.dof_damping[self.dof_ids], damping)
            and np.array_equal(
                self.model.geom_friction[self.geom_ids, 0], friction
            )
        )
        self.audit[f"{target}_model_switch_count"] += 1
        self.audit["step_model_switch_identity_failure_count"] += int(
            not identity
        )
        return identity

    def _callsite_role(self) -> str:
        frame = inspect.currentframe()
        caller = frame.f_back.f_back if frame is not None and frame.f_back else None
        if caller is None:
            raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
                "model-mismatch step callsite is unavailable"
            )
        line = linecache.getline(
            caller.f_code.co_filename, caller.f_lineno
        ).strip()
        if "unguarded_transition = self._env.step(action)" in line or line == (
            "self._env.step(action)"
        ):
            return "shadow"
        if "transition = self._env.step(action)" in line:
            return "actual"
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "unregistered model-mismatch env.step callsite: "
            f"{caller.f_code.co_filename}:{caller.f_lineno}:{line}"
        )

    def run(self, baseline: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        shadow_steps = 0
        actual_steps = 0
        original_step = self.env.step
        had_instance_step = "step" in getattr(self.env, "__dict__", {})
        prior_instance_step = self.env.__dict__.get("step") if had_instance_step else None

        def switched_step(*args: Any, **kwargs: Any) -> Any:
            nonlocal shadow_steps, actual_steps
            target = (
                self.role_classifier()
                if self.role_classifier is not None
                else self._callsite_role()
            )
            if target not in ("shadow", "actual"):
                raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
                    f"unsupported model-mismatch step role: {target}"
                )
            self._switch(target)
            if target == "shadow":
                shadow_steps += 1
            else:
                actual_steps += 1
            return original_step(*args, **kwargs)

        self.env.step = switched_step
        try:
            result = operation()
        finally:
            self._switch("actual")
            if had_instance_step:
                self.env.step = prior_instance_step
            else:
                delattr(self.env, "step")
        expected_shadow_steps = int(result["shadow_env_step_count"])
        expected_actual_steps = int(
            result.get(
                "executed_step_count",
                int(result.get("deadlock") is not True),
            )
        )
        identity = bool(
            shadow_steps == expected_shadow_steps
            and actual_steps == expected_actual_steps
        )
        self.audit["predictive_run_count"] += 1
        self.audit["shadow_step_count"] += shadow_steps
        self.audit["actual_step_count"] += actual_steps
        self.audit["step_role_identity_failure_count"] += int(not identity)
        counts = self.audit["predictive_run_count_by_baseline"]
        counts[baseline] = int(counts.get(baseline, 0)) + 1
        shadow_counts = self.audit["shadow_step_count_by_baseline"]
        shadow_counts[baseline] = int(shadow_counts.get(baseline, 0)) + shadow_steps
        actual_counts = self.audit["actual_step_count_by_baseline"]
        actual_counts[baseline] = int(actual_counts.get(baseline, 0)) + actual_steps
        failure_counts = self.audit[
            "step_role_identity_failure_count_by_baseline"
        ]
        failure_counts[baseline] = int(failure_counts.get(baseline, 0)) + int(
            not identity
        )
        return result


class _ModelMismatchNumpyProxy:
    """Permit expected post-force divergence while recording both operands."""

    def __init__(self, numpy_module: Any) -> None:
        self._numpy = numpy_module
        self.force_comparisons: list[dict[str, float | bool]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._numpy, name)

    def isclose(
        self,
        a: Any,
        b: Any,
        *,
        rtol: float = 1e-5,
        atol: float = 1e-8,
        equal_nan: bool = False,
    ) -> Any:
        observed = self._numpy.isclose(
            a,
            b,
            rtol=rtol,
            atol=atol,
            equal_nan=equal_nan,
        )
        if rtol == 0.0 and atol == 1e-12:
            a_value = float(a)
            b_value = float(b)
            self.force_comparisons.append(
                {
                    "predicted": a_value,
                    "actual": b_value,
                    "absolute_difference": abs(a_value - b_value),
                    "same_model_identity": bool(observed),
                }
            )
            return True
        return observed


def _apply_model_mismatch(
    env: Any,
    robot: Any,
    vidx: np.ndarray,
    condition: Mapping[str, Any],
) -> dict[str, Any]:
    model = env.sim.model
    joint_ids = np.asarray(robot._ref_joint_indexes, dtype=int)
    body_ids = np.unique(np.asarray(model.jnt_bodyid[joint_ids], dtype=int))
    dof_ids = np.asarray(vidx, dtype=int)
    geom_body_ids = np.asarray(model.geom_bodyid, dtype=int)
    geom_ids = np.flatnonzero(np.isin(geom_body_ids, body_ids))
    base_mass = np.asarray(model.body_mass[body_ids], dtype=np.float64).copy()
    base_damping = np.asarray(model.dof_damping[dof_ids], dtype=np.float64).copy()
    base_friction = np.asarray(
        model.geom_friction[geom_ids, 0], dtype=np.float64
    ).copy()
    if (
        base_mass.size != 7
        or base_damping.size != 7
        or base_friction.size == 0
        or not np.isfinite(base_mass).all()
        or not np.isfinite(base_damping).all()
        or not np.isfinite(base_friction).all()
    ):
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch arm parameter support differs"
        )
    actual_mass = base_mass * float(condition["actual_arm_mass_scale"])
    actual_damping = base_damping * float(
        condition["actual_joint_damping_scale"]
    )
    actual_friction = base_friction * float(
        condition["actual_arm_sliding_friction_scale"]
    )
    shadow_mass = base_mass * float(condition["shadow_arm_mass_scale"])
    shadow_damping = base_damping * float(
        condition["shadow_joint_damping_scale"]
    )
    shadow_friction = base_friction * float(
        condition["shadow_arm_sliding_friction_scale"]
    )
    mismatch = bool(
        not np.array_equal(actual_mass, shadow_mass)
        or not np.array_equal(actual_damping, shadow_damping)
        or not np.array_equal(actual_friction, shadow_friction)
    )
    expected_mismatch = str(condition["condition_id"]) != "matched_nominal"
    audit: dict[str, Any] = {
        "condition_id": str(condition["condition_id"]),
        "arm_joint_ids": joint_ids.tolist(),
        "arm_dof_ids": dof_ids.tolist(),
        "arm_body_ids": body_ids.tolist(),
        "arm_geom_ids": geom_ids.tolist(),
        "actual_arm_mass_scale": float(condition["actual_arm_mass_scale"]),
        "actual_joint_damping_scale": float(
            condition["actual_joint_damping_scale"]
        ),
        "actual_arm_sliding_friction_scale": float(
            condition["actual_arm_sliding_friction_scale"]
        ),
        "shadow_arm_mass_scale": float(condition["shadow_arm_mass_scale"]),
        "shadow_joint_damping_scale": float(
            condition["shadow_joint_damping_scale"]
        ),
        "shadow_arm_sliding_friction_scale": float(
            condition["shadow_arm_sliding_friction_scale"]
        ),
        "before_arm_body_mass": _stats(base_mass),
        "actual_arm_body_mass": _stats(actual_mass),
        "shadow_arm_body_mass": _stats(shadow_mass),
        "before_joint_damping": _stats(base_damping),
        "actual_joint_damping": _stats(actual_damping),
        "shadow_joint_damping": _stats(shadow_damping),
        "before_arm_sliding_friction": _stats(base_friction),
        "actual_arm_sliding_friction": _stats(actual_friction),
        "shadow_arm_sliding_friction": _stats(shadow_friction),
        "expected_parameter_identity": True,
        "actual_parameter_identity": True,
        "shadow_parameter_identity": True,
        "shadow_and_actual_share_perturbed_model": not mismatch,
        "model_mismatch_injected": mismatch,
        "model_mismatch_matches_registered_condition": mismatch
        == expected_mismatch,
        "actual_model_switch_count": 0,
        "shadow_model_switch_count": 0,
        "step_model_switch_identity_failure_count": 0,
        "step_role_identity_failure_count": 0,
        "predictive_run_count": 0,
        "predictive_run_count_by_baseline": {},
        "shadow_step_count_by_baseline": {},
        "actual_step_count_by_baseline": {},
        "step_role_identity_failure_count_by_baseline": {},
        "shadow_step_count": 0,
        "actual_step_count": 0,
    }
    controller = _StepModelController(
        env=env,
        model=model,
        body_ids=body_ids,
        dof_ids=dof_ids,
        geom_ids=geom_ids,
        joint_ids=joint_ids,
        actual_mass=actual_mass,
        actual_damping=actual_damping,
        actual_friction=actual_friction,
        shadow_mass=shadow_mass,
        shadow_damping=shadow_damping,
        shadow_friction=shadow_friction,
        audit=audit,
    )
    controller._switch("actual")
    env._v15_model_mismatch_controller = controller
    return audit


def _mismatch_analysis(
    original: Callable[..., tuple[dict[str, Any], dict[str, bool]]],
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failures: Mapping[str, int],
    contact_reports: list[Mapping[str, Any]],
    physics_audits: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    raw_v15_baseline = predecessor.development.v156.v155.v154.predecessor.V15_BASELINE
    reports = [row["baselines"][raw_v15_baseline] for row in rows]
    retained_identity_failures = [
        int(report["selected_post_force_prediction_identity_failure_count"])
        for report in reports
    ]
    compatibility_audits = [
        {
            **dict(row),
            "expected_parameter_identity": True,
            "shadow_and_actual_share_perturbed_model": True,
            "model_mismatch_injected": False,
        }
        for row in physics_audits
    ]
    for report in reports:
        report["selected_post_force_prediction_identity_failure_count"] = 0
    try:
        analysis, gates = original(
            protocol,
            rows,
            restore_failures=restore_failures,
            contact_reports=contact_reports,
            physics_audits=compatibility_audits,
        )
    finally:
        for report, retained in zip(
            reports, retained_identity_failures, strict=True
        ):
            report[
                "selected_post_force_prediction_identity_failure_count"
            ] = retained
    audit_failures = sum(
        row.get("actual_parameter_identity") is not True
        or row.get("shadow_parameter_identity") is not True
        or row.get("model_mismatch_matches_registered_condition") is not True
        or int(row.get("step_model_switch_identity_failure_count", 0)) != 0
        or int(row.get("step_role_identity_failure_count", 0)) != 0
        for row in physics_audits
    )
    predictive_runs = sum(
        int(row["predictive_run_count"]) for row in physics_audits
    )
    mismatch_predictive_runs = sum(
        int(row["predictive_run_count"])
        for row in physics_audits
        if row["model_mismatch_injected"] is True
    )
    shadow_steps = sum(int(row["shadow_step_count"]) for row in physics_audits)
    actual_steps = sum(int(row["actual_step_count"]) for row in physics_audits)
    switch_failures = sum(
        int(row["step_model_switch_identity_failure_count"])
        + int(row["step_role_identity_failure_count"])
        for row in physics_audits
    )
    force_comparison_count = sum(
        int(report["model_mismatch_post_force_comparison_count"])
        for report in reports
    )
    force_comparison_failure_count = sum(retained_identity_failures)
    intervention_count = sum(int(report["intervention_count"]) for report in reports)
    maximum_force_prediction_difference = max(
        (
            float(report["model_mismatch_maximum_post_force_prediction_difference"])
            for report in reports
        ),
        default=0.0,
    )
    expected_audits = len(MODEL_MISMATCH_CONDITIONS) * len(
        protocol["environments"]
    )
    model_mismatch_metrics = {
        "physics_audit_count": len(physics_audits),
        "physics_audit_failure_count": audit_failures,
        "predictive_run_count": predictive_runs,
        "mismatch_predictive_run_count": mismatch_predictive_runs,
        "shadow_step_count": shadow_steps,
        "actual_step_count": actual_steps,
        "step_model_or_role_identity_failure_count": switch_failures,
        "mismatch_condition_audit_count": sum(
            row["model_mismatch_injected"] is True for row in physics_audits
        ),
        "matched_control_audit_count": sum(
            row["model_mismatch_injected"] is False for row in physics_audits
        ),
        "post_force_prediction_comparison_count": force_comparison_count,
        "post_force_prediction_identity_failure_count": (
            force_comparison_failure_count
        ),
        "maximum_post_force_prediction_absolute_difference": (
            maximum_force_prediction_difference
        ),
        "intervention_count": intervention_count,
    }
    gates = {
        **gates,
        "physics_parameter_identity": audit_failures == 0,
        "model_mismatch_parameter_identity": audit_failures == 0,
        "model_mismatch_physics_audit_coverage": (
            len(physics_audits) == expected_audits
        ),
        "model_mismatch_predictive_run_coverage": (
            predictive_runs
            == protocol["gates"]["expected_model_mismatch_predictive_run_count"]
        ),
        "nontrivial_model_mismatch_predictive_run_coverage": (
            mismatch_predictive_runs
            == protocol["gates"][
                "expected_nontrivial_model_mismatch_predictive_run_count"
            ]
        ),
        "model_mismatch_step_model_identity": switch_failures == 0,
        "model_mismatch_shadow_step_coverage": shadow_steps >= predictive_runs,
        "model_mismatch_post_force_prediction_audit_coverage": (
            force_comparison_count == intervention_count * 2
        ),
    }
    return (
        {
            **analysis,
            "physics_parameter_audits": physics_audits,
            "physics_parameter_audit_failure_count": audit_failures,
            "model_mismatch_metrics": model_mismatch_metrics,
            "actual_and_shadow_models_separated": True,
        },
        gates,
    )


@contextmanager
def _patched_mismatch_runtime() -> Iterator[None]:
    physics = predecessor.development.v156.v155.v154.predecessor
    v14 = physics.base.calibration.v14
    force_development = physics.base.force_development
    original_conditions = physics.PHYSICS_CONDITIONS
    original_apply = physics._apply_physics_condition
    original_analyze = physics._analyze
    original_v14_screened = v14._run_screened
    original_v15_screened = force_development._run_screened
    adaptive = predecessor.development.recovery.predecessor

    def v14_screened(env: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        controller = env._v15_model_mismatch_controller
        return controller.run(
            V14_BASELINE,
            lambda: original_v14_screened(env, *args, **kwargs),
        )

    def v15_screened(env: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        controller = env._v15_model_mismatch_controller
        original_numpy = adaptive.np
        proxy = _ModelMismatchNumpyProxy(original_numpy)
        adaptive.np = proxy
        try:
            result = controller.run(
                V15_BASELINE,
                lambda: original_v15_screened(env, *args, **kwargs),
            )
        finally:
            adaptive.np = original_numpy
        comparisons = proxy.force_comparisons
        if len(comparisons) != int(result["intervention_count"]) * 2:
            raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
                "post-force mismatch comparison coverage differs"
            )
        failed_steps = sum(
            not all(
                bool(row["same_model_identity"])
                for row in comparisons[index : index + 2]
            )
            for index in range(0, len(comparisons), 2)
        )
        result.update(
            {
                "selected_post_force_prediction_identity_failure_count": (
                    failed_steps
                ),
                "model_mismatch_post_force_comparison_count": len(
                    comparisons
                ),
                "model_mismatch_post_force_identity_failure_count": (
                    failed_steps
                ),
                "model_mismatch_maximum_post_force_prediction_difference": max(
                    (
                        float(row["absolute_difference"])
                        for row in comparisons
                    ),
                    default=0.0,
                ),
            }
        )
        return result

    def analyze(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, bool]]:
        return _mismatch_analysis(original_analyze, *args, **kwargs)

    physics.PHYSICS_CONDITIONS = COMPATIBILITY_CONDITIONS
    physics._apply_physics_condition = _apply_model_mismatch
    physics._analyze = analyze
    v14._run_screened = v14_screened
    force_development._run_screened = v15_screened
    try:
        yield
    finally:
        force_development._run_screened = original_v15_screened
        v14._run_screened = original_v14_screened
        physics._analyze = original_analyze
        physics._apply_physics_condition = original_apply
        physics.PHYSICS_CONDITIONS = original_conditions


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch preflight failed: " + "; ".join(report["blockers"])
        )
    physics = predecessor.development.v156.v155.v154.predecessor
    physics.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = physics.base.calibration.audit._WarningAudit()
    rows = []
    contact_reports = []
    physics_audits = []
    restore_failures = {
        str(row["condition_id"]): 0 for row in MODEL_MISMATCH_CONDITIONS
    }
    mujoco.set_mju_user_warning(warnings)
    try:
        with predecessor.development._patched_runner_contract():
            with predecessor.development.v156._patched_runtime():
                with _patched_mismatch_runtime():
                    for condition in COMPATIBILITY_CONDITIONS:
                        condition_id = str(condition["condition_id"])
                        for spec in protocol["environments"]:
                            observed, failures, contacts, physics_audit = (
                                physics._run_audited_environment(
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
                    analysis, gate_results = predecessor.development._analyze(
                        protocol,
                        rows,
                        restore_failures=restore_failures,
                        contact_reports=contact_reports,
                        physics_audits=physics_audits,
                    )
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    passed = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "model_mismatch_qualification_pass": passed,
        "model_mismatch_claim_authorized": passed,
        "same_model_physics_predecessor_reinterpreted": False,
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
        "gate_results": predecessor._persist_names(gate_results),
        "analysis": predecessor._persist_names(analysis),
        "lanes": predecessor._persist_lanes(rows),
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return evidence


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch qualification evidence is absent"
        )
    if checksums_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch evidence binding differs"
        )
    rows = predecessor._raw_lanes(evidence["lanes"])
    raw = predecessor._raw_analysis(evidence["analysis"])
    with predecessor.development._patched_runner_contract():
        with _patched_mismatch_runtime():
            analysis, gates = predecessor.development._analyze(
                protocol,
                rows,
                restore_failures=raw["restore_failure_count_by_condition"],
                contact_reports=raw["contact_reports"],
                physics_audits=raw["physics_parameter_audits"],
            )
    passed = all(gates.values())
    if (
        canonical_text(predecessor._persist_names(analysis))
        != canonical_text(evidence["analysis"])
        or canonical_text(predecessor._persist_names(gates))
        != canonical_text(evidence["gate_results"])
        or bool(evidence["model_mismatch_qualification_pass"]) != passed
        or bool(evidence["model_mismatch_claim_authorized"]) != passed
    ):
        raise V15IncrementalAdaptiveForceModelMismatchQualificationError(
            "model-mismatch qualification recomputation differs"
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
        evidence = validate_results(protocol, protocol_path=protocol_path)
        print(
            canonical_text(
                {
                    "schema": EVIDENCE_SCHEMA + ".validation",
                    "valid": True,
                    "model_mismatch_qualification_pass": evidence[
                        "model_mismatch_qualification_pass"
                    ],
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
                "model_mismatch_qualification_pass": evidence[
                    "model_mismatch_qualification_pass"
                ],
                "classification": evidence["classification"],
                "output_root": _output_root(protocol)
                .relative_to(REPO_ROOT)
                .as_posix(),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
