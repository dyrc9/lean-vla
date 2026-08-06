#!/usr/bin/env python3
"""Add pre/in-scope/post force attribution to unchanged v15.2 recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as v14_core  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_3_"
    "force_attributed_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.3."
    "force-attributed-recovery.step"
)
JOINT_COUNT = predecessor.JOINT_COUNT
JOINT_SIDES = predecessor.JOINT_SIDES
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLREF = predecessor.GUARD_SOLREF
GUARD_SOLIMP = predecessor.GUARD_SOLIMP
RECOVERY_GUARD_MARGIN_RAD = predecessor.RECOVERY_GUARD_MARGIN_RAD
RECOVERY_MARGIN_EPSILON_RAD = predecessor.RECOVERY_MARGIN_EPSILON_RAD
CURRENT_EDGE_EPSILON_RAD = predecessor.CURRENT_EDGE_EPSILON_RAD


class ForceAttributionError(RuntimeError):
    """Raised when v15.3 cannot bind force attribution exactly."""


def _force_rows(values: np.ndarray) -> list[dict[str, Any]]:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (JOINT_COUNT,) or not np.isfinite(array).all():
        raise ForceAttributionError("invalid seven-joint constraint force")
    return [
        {
            "joint_index": joint_index,
            "dof_constraint_force": float(array[joint_index]),
            "absolute_dof_constraint_force": abs(
                float(array[joint_index])
            ),
        }
        for joint_index in range(JOINT_COUNT)
    ]


def _enrich_force_attribution(
    audit: dict[str, Any],
    *,
    pre_step_joint_constraint_force: np.ndarray,
    post_step_joint_constraint_force: np.ndarray,
    scoped_force_audits: list[list[dict[str, Any]]],
) -> None:
    pre = np.asarray(pre_step_joint_constraint_force, dtype=np.float64)
    post = np.asarray(post_step_joint_constraint_force, dtype=np.float64)
    if (
        pre.shape != (JOINT_COUNT,)
        or post.shape != (JOINT_COUNT,)
        or not np.isfinite(pre).all()
        or not np.isfinite(post).all()
    ):
        raise ForceAttributionError(
            "force attribution requires finite seven-joint vectors"
        )
    risks = audit.get("risk_sides")
    if not isinstance(risks, list):
        raise ForceAttributionError("v15.3 audit lacks risk sides")
    risk_indices = sorted(
        {
            int(row["joint_index"])
            for row in risks
            if isinstance(row, Mapping)
        }
    )
    if any(index < 0 or index >= JOINT_COUNT for index in risk_indices):
        raise ForceAttributionError("v15.3 risk joint index is invalid")
    pre_risk_max = (
        max(abs(float(pre[index])) for index in risk_indices)
        if risk_indices
        else 0.0
    )
    post_risk_max = (
        max(abs(float(post[index])) for index in risk_indices)
        if risk_indices
        else 0.0
    )
    reported = float(audit["maximum_abs_guarded_constraint_force"])
    if not np.isfinite(reported) or reported < 0:
        raise ForceAttributionError("reported guard-scope force is invalid")
    recovery_selected = bool(
        audit.get("floor_or_current_edge_recovery_selected") is True
    )
    expected_scope_count = sum(
        bool(row.get("configuration_inside_guard_ranges"))
        for row in audit.get("candidates", ())
        if isinstance(row, Mapping)
    ) + int(bool(audit.get("intervened")))
    if len(scoped_force_audits) != expected_scope_count:
        raise ForceAttributionError(
            "v15.3 guard-scope audit count differs from v15.2 execution"
        )
    selected_scope = (
        scoped_force_audits[-1] if audit.get("intervened") is True else []
    )
    scoped_by_joint: dict[int, list[float]] = {
        index: [] for index in risk_indices
    }
    for controller_row in selected_scope:
        sides = controller_row.get("guarded_sides")
        if not isinstance(sides, list):
            raise ForceAttributionError(
                "v15.3 guard-scope audit lacks guarded sides"
            )
        for side in sides:
            if not isinstance(side, Mapping):
                raise ForceAttributionError(
                    "v15.3 guard-scope side audit is invalid"
                )
            joint_index = int(side["joint_index"])
            value = float(side["dof_constraint_force"])
            if joint_index not in scoped_by_joint or not np.isfinite(value):
                raise ForceAttributionError(
                    "v15.3 guard-scope force does not match risk joints"
                )
            scoped_by_joint[joint_index].append(value)
    if recovery_selected and any(
        not values for values in scoped_by_joint.values()
    ):
        raise ForceAttributionError(
            "v15.3 selected recovery lacks per-joint scope samples"
        )
    scoped_peak_rows = []
    scoped_increments = []
    post_increments = []
    for index in risk_indices:
        values = scoped_by_joint[index]
        peak_signed = (
            max(values, key=lambda value: abs(value)) if values else 0.0
        )
        peak_abs = abs(float(peak_signed))
        pre_abs = abs(float(pre[index]))
        post_abs = abs(float(post[index]))
        scope_increment = max(0.0, peak_abs - pre_abs)
        post_increment = max(0.0, post_abs - pre_abs)
        scoped_increments.append(scope_increment)
        post_increments.append(post_increment)
        scoped_peak_rows.append(
            {
                "joint_index": index,
                "sample_count": len(values),
                "peak_signed_dof_constraint_force": float(peak_signed),
                "peak_absolute_dof_constraint_force": peak_abs,
                "pre_step_absolute_dof_constraint_force": pre_abs,
                "positive_absolute_increment_over_pre_step": (
                    scope_increment
                ),
            }
        )
    recomputed_reported = max(
        (
            row["peak_absolute_dof_constraint_force"]
            for row in scoped_peak_rows
        ),
        default=0.0,
    )
    if not np.isclose(recomputed_reported, reported, rtol=0.0, atol=1e-12):
        raise ForceAttributionError(
            "v15.3 per-joint scope peak differs from legacy total"
        )
    audit.update(
        {
            "schema": BRAKE_AUDIT_SCHEMA,
            "force_attribution_active": bool(
                audit.get("enabled") is True
            ),
            "force_attribution_units": (
                "mujoco_generalized_constraint_force"
            ),
            "force_attribution_risk_joint_indices": risk_indices,
            "pre_step_joint_constraint_force": _force_rows(pre),
            "post_step_joint_constraint_force": _force_rows(post),
            "pre_step_maximum_abs_risk_constraint_force": pre_risk_max,
            "guard_scope_reported_maximum_abs_risk_constraint_force": (
                reported
            ),
            "post_step_maximum_abs_risk_constraint_force": post_risk_max,
            "guard_scope_max_envelope_increment_over_pre_step": max(
                0.0, reported - pre_risk_max
            ),
            "post_step_max_envelope_increment_over_pre_step": max(
                0.0, post_risk_max - pre_risk_max
            ),
            "post_step_max_envelope_reduction_from_pre_step": (
                pre_risk_max - post_risk_max
            ),
            "guard_scope_controller_substep_count": len(selected_scope),
            "guard_scope_joint_peak_constraint_force": scoped_peak_rows,
            "guard_scope_maximum_positive_joint_increment_over_pre_step": (
                max(scoped_increments, default=0.0)
            ),
            "post_step_maximum_positive_joint_increment_over_pre_step": (
                max(post_increments, default=0.0)
            ),
            "guard_scope_legacy_force_recomputed_identity": True,
            "recovery_selected_for_force_attribution": recovery_selected,
            "force_attribution_changes_mechanism": False,
            "force_attribution_physical_authority_claim": False,
        }
    )


@contextmanager
def _capture_scoped_force_audits(
    sink: list[list[dict[str, Any]]],
) -> Iterator[None]:
    """Observe each v14 guard scope without changing its execution."""

    original = v14_core._scoped_multi_joint_guards

    @contextmanager
    def captured(
        env: Any,
        robot: Any,
        *,
        configurations: list[dict[str, Any]],
    ) -> Iterator[list[dict[str, Any]]]:
        with original(
            env,
            robot,
            configurations=configurations,
        ) as scoped_audit:
            yield scoped_audit
        sink.append(deepcopy(scoped_audit))

    v14_core._scoped_multi_joint_guards = captured
    try:
        yield
    finally:
        v14_core._scoped_multi_joint_guards = original


class MultiJointForceAttributedRecoveryEnvironment(
    predecessor.MultiJointCurrentEdgePriorityRecoveryEnvironment
):
    """Observe force before and after the unchanged v15.2 step."""

    def step(self, action: Any) -> Any:
        before_observation_count = len(self.observations)
        _robot, _qidx, vidx, _limits = self._arrays()
        pre = np.asarray(
            self._env.sim.data.qfrc_constraint[vidx],
            dtype=np.float64,
        ).copy()
        scoped_force_audits: list[list[dict[str, Any]]] = []
        with _capture_scoped_force_audits(scoped_force_audits):
            transition = super().step(action)
        post = np.asarray(
            self._env.sim.data.qfrc_constraint[vidx],
            dtype=np.float64,
        ).copy()
        if len(self.observations) == before_observation_count:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise ForceAttributionError(
                "v15.3 environment produced a non-object audit"
            )
        _enrich_force_attribution(
            audit,
            pre_step_joint_constraint_force=pre,
            post_step_joint_constraint_force=post,
            scoped_force_audits=scoped_force_audits,
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointCurrentEdgePriorityRecoveryEnvironment
    predecessor.MultiJointCurrentEdgePriorityRecoveryEnvironment = (
        MultiJointForceAttributedRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointCurrentEdgePriorityRecoveryEnvironment = (
            original
        )


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.3 force-attributed episode without changing control."""

    with _patched_predecessor_environment():
        payload = predecessor.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    l2_enabled = bool(metadata["l2_execution_integrity"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "force_attribution_active": l2_enabled,
            "force_attribution_changes_mechanism": False,
            "force_attribution_outcome_informed_successor": True,
            "force_attribution_physical_authority_claim": False,
        }
    )
    payload["metadata"] = metadata
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "execution_authorized": False,
            "note": (
                "Import through a frozen v15.3 force-attribution protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
