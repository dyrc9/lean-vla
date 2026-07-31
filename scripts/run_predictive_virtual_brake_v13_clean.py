#!/usr/bin/env python3
"""Run or validate the frozen v13 clean task-outcome study."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
    cluster_bootstrap_paired_difference,
)
from scripts import run_l2_predictive_virtual_brake_v13 as online  # noqa: E402
from scripts import run_physical_sufficiency_clean_pilot as inherited  # noqa: E402
from scripts import run_risk_selective_clean_pilot as risk  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-clean-outcome-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-clean-outcome-evidence.v1"
)
EXPECTED_RUNNER = online.RUNNER_VARIANT
AUTHORIZED_STATUS = (
    "authorized_v13_predictive_virtual_brake_clean_outcome"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_clean_fresh2_protocol.json"
)
REQUIRED_INTERPRETER = (
    REPO_ROOT / "external" / "openpi" / ".venv" / "bin" / "python"
)
_BASE_V10_METRICS = inherited._v10_metrics
_BASE_ENRICH = risk._enrich


class PredictiveVirtualBrakeCleanError(RuntimeError):
    """Raised when the v13 clean study differs from its frozen protocol."""


def _episode_brake_metrics(
    episode: Mapping[str, Any],
    *,
    l2_enabled: bool,
) -> dict[str, Any]:
    policy_rows = [
        row
        for row in episode["trace"]
        if row.get("phase") == "policy"
    ]
    audits = []
    joint_limit_steps = 0
    for row in policy_rows:
        audit = row.get("predictive_virtual_brake")
        if (
            not isinstance(audit, Mapping)
            or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
        ):
            raise PredictiveVirtualBrakeCleanError(
                "policy step lacks a typed v13 virtual-brake audit"
            )
        audits.append(audit)
        signals = row.get("saber_constraint_signals")
        if not isinstance(signals, Mapping):
            raise PredictiveVirtualBrakeCleanError(
                "policy step lacks independent constraint signals"
            )
        if type(signals.get("joint_limit_violation")) is not bool:
            raise PredictiveVirtualBrakeCleanError(
                "joint-limit signal is not boolean"
            )
        joint_limit_steps += int(
            signals["joint_limit_violation"]
        )

    expected_enabled = sum(
        audit.get("enabled") is l2_enabled for audit in audits
    )
    expected_screen = sum(
        audit.get("screen_performed") is l2_enabled
        for audit in audits
    )
    triggered = [audit for audit in audits if audit["triggered"]]
    interventions = [
        audit for audit in audits if audit["intervened"]
    ]
    deadlocks = [audit for audit in audits if audit["deadlock"]]
    dispatched = [audit for audit in audits if not audit["deadlock"]]
    margins = [
        float(audit["actual_minimum_margin_rad"])
        for audit in audits
    ]
    latencies = [
        float(audit["screen_latency_seconds"])
        for audit in audits
        if audit["screen_performed"]
    ]
    prediction_errors = [
        float(audit["prediction_execution_margin_error_rad"])
        for audit in interventions
    ]
    forces = [
        float(audit["maximum_abs_target_constraint_force"])
        for audit in interventions
    ]
    return {
        "policy_step_count": len(policy_rows),
        "expected_enabled_audit_count": expected_enabled,
        "expected_screen_audit_count": expected_screen,
        "trigger_count": len(triggered),
        "intervention_count": len(interventions),
        "deadlock_count": len(deadlocks),
        "shadow_restore_failure_count": sum(
            audit["screen_performed"]
            and audit["shadow_restore_identity"] is not True
            for audit in audits
        ),
        "candidate_restore_failure_count": sum(
            audit["screen_performed"]
            and audit["candidate_restore_identity"] is not True
            for audit in audits
        ),
        "scope_restore_failure_count": sum(
            audit["intervened"]
            and audit["guard_scope_restored"] is not True
            for audit in audits
        ),
        "exact_action_mismatch_count": sum(
            audit["exact_action_identity"] is not True
            for audit in dispatched
        ),
        "torque_bound_violation_count": sum(
            int(audit["torque_bound_violation_count"])
            for audit in audits
        ),
        "intervention_floor_violation_count": sum(
            float(audit["actual_minimum_margin_rad"])
            < online.SAFE_MARGIN_FLOOR_RAD
            for audit in interventions
        ),
        "shadow_env_step_count": sum(
            int(audit["shadow_env_step_count"]) for audit in audits
        ),
        "joint_limit_violation_step_count": joint_limit_steps,
        "minimum_actual_margin_rad": min(margins) if margins else None,
        "maximum_prediction_execution_margin_error_rad": (
            max(prediction_errors) if prediction_errors else 0.0
        ),
        "maximum_abs_target_constraint_force": (
            max(forces) if forces else 0.0
        ),
        "screen_latency_seconds_sum": sum(latencies),
        "screen_latency_seconds_max": max(latencies)
        if latencies
        else 0.0,
    }


def _paired_units(
    protocol: Mapping[str, Any],
    episodes: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    pair_by_episode = {
        str(row["episode_id"]): str(row["base_pair_id"])
        for row in protocol["schedule"]
    }
    outcomes: dict[str, dict[str, bool]] = {}
    for episode in episodes:
        metadata = episode["metadata"]
        episode_id = str(metadata["v13_episode_id"])
        pair_id = pair_by_episode[episode_id]
        arm = str(metadata["four_arm_label"])
        pair = outcomes.setdefault(pair_id, {})
        if arm in pair:
            raise PredictiveVirtualBrakeCleanError(
                "duplicate arm within a paired workload"
            )
        pair[arm] = bool(episode["task_success"])
    expected = {
        "vla_only",
        "semantic_only",
        "execution_only",
        "dual",
    }
    if any(set(values) != expected for values in outcomes.values()):
        raise PredictiveVirtualBrakeCleanError(
            "paired workload does not contain all four arms"
        )
    return [
        {
            "base_pair_id": pair_id,
            "outcomes": outcomes[pair_id],
        }
        for pair_id in sorted(outcomes)
    ]


def _v13_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    inherited_metrics, inherited_gates = _BASE_V10_METRICS(
        protocol, evidence
    )
    schedule = {
        str(row["episode_id"]): row
        for row in protocol["schedule"]
    }
    episodes = []
    rows = []
    metadata_mismatches = 0
    by_arm_success: Counter[str] = Counter()
    by_arm_unsafe: Counter[str] = Counter()
    by_arm_deadlocks: Counter[str] = Counter()

    for artifact in evidence["episodes"]:
        episode = load_json_object(REPO_ROOT / artifact["path"])
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        metadata = episode["metadata"]
        arm = str(spec["arm"])
        l2_enabled = arm in {"execution_only", "dual"}
        expected_metadata = {
            "runner_variant": EXPECTED_RUNNER,
            "four_arm_label": arm,
            "legacy_l2_execution_integrity_active": False,
            "predictive_virtual_brake_active": l2_enabled,
            "predictive_virtual_brake_schema": (
                online.BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "predictive_virtual_brake_target_joint_index": (
                online.TARGET_JOINT_INDEX if l2_enabled else None
            ),
            "predictive_virtual_brake_target_joint_side": (
                online.TARGET_JOINT_SIDE if l2_enabled else None
            ),
            "predictive_virtual_brake_trigger_margin_rad": (
                online.TRIGGER_MARGIN_RAD if l2_enabled else None
            ),
            "predictive_virtual_brake_safe_margin_floor_rad": (
                online.SAFE_MARGIN_FLOOR_RAD if l2_enabled else None
            ),
            "predictive_virtual_brake_guard_margins_rad": (
                list(online.BRAKE_MARGINS_RAD)
                if l2_enabled
                else None
            ),
            "predictive_virtual_brake_guard_solref": (
                list(online.GUARD_SOLREF) if l2_enabled else None
            ),
            "predictive_virtual_brake_guard_solimp": (
                list(online.GUARD_SOLIMP) if l2_enabled else None
            ),
            "predictive_virtual_brake_action_substitution": False,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value
            for key, value in expected_metadata.items()
        )
        metadata["v13_episode_id"] = episode_id
        metrics = _episode_brake_metrics(
            episode, l2_enabled=l2_enabled
        )
        rows.append(
            {
                "episode_id": episode_id,
                "base_pair_id": spec["base_pair_id"],
                "arm": arm,
                "task_success": bool(episode["task_success"]),
                "strict_success_no_cost": bool(
                    episode["strict_success_no_cost"]
                ),
                "unsafe_cost_or_collision": bool(
                    episode["unsafe_cost_or_collision"]
                ),
                "decision": str(episode["decision"]),
                **metrics,
            }
        )
        episodes.append(episode)
        by_arm_success[arm] += int(episode["task_success"])
        by_arm_unsafe[arm] += int(
            episode["unsafe_cost_or_collision"]
        )
        by_arm_deadlocks[arm] += int(
            metrics["deadlock_count"] > 0
            or "unknown" in str(episode["decision"])
        )

    units = _paired_units(protocol, episodes)
    analysis = protocol["analysis"]
    contrasts = {}
    for index, (name, treatment, control) in enumerate(
        (
            (
                "execution_only_minus_vla_only",
                "execution_only",
                "vla_only",
            ),
            (
                "dual_minus_semantic_only",
                "dual",
                "semantic_only",
            ),
        )
    ):
        contrasts[name] = cluster_bootstrap_paired_difference(
            units,
            treatment=treatment,
            control=control,
            resamples=int(analysis["bootstrap_resamples"]),
            seed=int(analysis["bootstrap_seed_base"]) + index,
        )
        contrasts[name]["treatment_task_success_count"] = (
            by_arm_success[treatment]
        )
        contrasts[name]["control_task_success_count"] = (
            by_arm_success[control]
        )
        contrasts[name]["treatment_unsafe_count"] = (
            by_arm_unsafe[treatment]
        )
        contrasts[name]["control_unsafe_count"] = (
            by_arm_unsafe[control]
        )
        contrasts[name]["treatment_unknown_or_deadlock_count"] = (
            by_arm_deadlocks[treatment]
        )
        contrasts[name]["control_unknown_or_deadlock_count"] = (
            by_arm_deadlocks[control]
        )

    totals = {
        key: sum(int(row[key]) for row in rows)
        for key in (
            "policy_step_count",
            "expected_enabled_audit_count",
            "expected_screen_audit_count",
            "trigger_count",
            "intervention_count",
            "deadlock_count",
            "shadow_restore_failure_count",
            "candidate_restore_failure_count",
            "scope_restore_failure_count",
            "exact_action_mismatch_count",
            "torque_bound_violation_count",
            "intervention_floor_violation_count",
            "shadow_env_step_count",
            "joint_limit_violation_step_count",
        )
    }
    l2_policy_steps = sum(
        row["policy_step_count"]
        for row in rows
        if row["arm"] in {"execution_only", "dual"}
    )
    l2_enabled_audits = sum(
        row["expected_enabled_audit_count"]
        for row in rows
        if row["arm"] in {"execution_only", "dual"}
    )
    l2_screen_audits = sum(
        row["expected_screen_audit_count"]
        for row in rows
        if row["arm"] in {"execution_only", "dual"}
    )
    disabled_policy_steps = sum(
        row["policy_step_count"]
        for row in rows
        if row["arm"] in {"vla_only", "semantic_only"}
    )
    disabled_expected_audits = sum(
        row["expected_enabled_audit_count"]
        for row in rows
        if row["arm"] in {"vla_only", "semantic_only"}
    )
    gate = protocol["v13_gates"]
    utility_margin = float(
        gate["paired_task_success_difference_lower_bound_min"]
    )
    gate_results = {
        **inherited_gates,
        "virtual_brake_metadata_matches": metadata_mismatches == 0,
        "l2_audit_coverage": (
            l2_enabled_audits == l2_policy_steps
            and l2_screen_audits == l2_policy_steps
        ),
        "disabled_arm_noninterference_annotation": (
            disabled_expected_audits == disabled_policy_steps
        ),
        "shadow_restore_identity": (
            totals["shadow_restore_failure_count"] == 0
        ),
        "candidate_restore_identity": (
            totals["candidate_restore_failure_count"] == 0
        ),
        "guard_scope_restore_identity": (
            totals["scope_restore_failure_count"] == 0
        ),
        "exact_action_identity": (
            totals["exact_action_mismatch_count"] == 0
        ),
        "torque_bounds": (
            totals["torque_bound_violation_count"] == 0
        ),
        "intervention_margin_floor": (
            totals["intervention_floor_violation_count"] == 0
        ),
        "execution_only_task_success_noninferiority": (
            contrasts["execution_only_minus_vla_only"]["lower"]
            >= utility_margin
        ),
        "dual_task_success_noninferiority": (
            contrasts["dual_minus_semantic_only"]["lower"]
            >= utility_margin
        ),
        "execution_only_official_unsafe_nonincrease": (
            by_arm_unsafe["execution_only"]
            <= by_arm_unsafe["vla_only"]
        ),
        "dual_official_unsafe_nonincrease": (
            by_arm_unsafe["dual"]
            <= by_arm_unsafe["semantic_only"]
        ),
    }
    metrics = {
        **inherited_metrics,
        **totals,
        "virtual_brake_metadata_mismatch_count": (
            metadata_mismatches
        ),
        "l2_policy_step_count": l2_policy_steps,
        "l2_enabled_audit_count": l2_enabled_audits,
        "l2_screen_audit_count": l2_screen_audits,
        "disabled_policy_step_count": disabled_policy_steps,
        "disabled_expected_audit_count": disabled_expected_audits,
        "by_arm_task_success_count": dict(
            sorted(by_arm_success.items())
        ),
        "by_arm_unsafe_cost_or_collision_count": dict(
            sorted(by_arm_unsafe.items())
        ),
        "by_arm_unknown_or_deadlock_count": dict(
            sorted(by_arm_deadlocks.items())
        ),
        "paired_task_success_contrasts": contrasts,
        "maximum_prediction_execution_margin_error_rad": max(
            (
                row[
                    "maximum_prediction_execution_margin_error_rad"
                ]
                for row in rows
            ),
            default=0.0,
        ),
        "maximum_abs_target_constraint_force": max(
            (
                row["maximum_abs_target_constraint_force"]
                for row in rows
            ),
            default=0.0,
        ),
        "screen_latency_seconds_sum": sum(
            row["screen_latency_seconds_sum"] for row in rows
        ),
        "screen_latency_seconds_max": max(
            (
                row["screen_latency_seconds_max"] for row in rows
            ),
            default=0.0,
        ),
    }
    return metrics, gate_results


def _enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    utility_gate_names = (
        "v9_execution_only_task_success_noninferiority",
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_official_unsafe_nonincrease",
        "v9_dual_official_unsafe_nonincrease",
    )
    clean_utility_passed = all(
        enriched["gate_results"].get(name) is True
        for name in utility_gate_names
    )
    return {
        **enriched,
        "method_claim": (
            "target-specific one-step predictive simulator hard "
            "virtual brake with exact source-action identity"
        ),
        "clean_utility_gate_passed": clean_utility_passed,
        "attacked_stage_authorized": bool(
            enriched["pilot_complete"] and clean_utility_passed
        ),
        "confirmatory_claim_authorized": False,
        "task_outcome_observation_authorized": True,
    }


@contextmanager
def _patched_inherited() -> Iterator[None]:
    originals = (
        inherited.PROTOCOL_SCHEMA,
        inherited.EVIDENCE_SCHEMA,
        inherited.EXPECTED_RUNNER,
        inherited.AUTHORIZED_STATUS,
        inherited.DEFAULT_PROTOCOL,
        inherited.online,
        inherited._v10_metrics,
        risk._enrich,
    )
    inherited.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    inherited.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    inherited.EXPECTED_RUNNER = EXPECTED_RUNNER
    inherited.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    inherited.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    inherited.online = online
    inherited._v10_metrics = _v13_metrics
    risk._enrich = _enrich
    try:
        yield
    finally:
        (
            inherited.PROTOCOL_SCHEMA,
            inherited.EVIDENCE_SCHEMA,
            inherited.EXPECTED_RUNNER,
            inherited.AUTHORIZED_STATUS,
            inherited.DEFAULT_PROTOCOL,
            inherited.online,
            inherited._v10_metrics,
            risk._enrich,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_inherited():
        report = inherited.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    observed = Path(sys.executable).resolve()
    required = REQUIRED_INTERPRETER.resolve()
    interpreter_ready = observed == required
    blockers = list(report["blockers"])
    if not interpreter_ready:
        blockers.append(
            "v13 outcome rollout requires "
            "external/openpi/.venv/bin/python"
        )
    return {
        **report,
        "ready": not blockers,
        "required_interpreter": str(REQUIRED_INTERPRETER),
        "required_interpreter_resolved": str(required),
        "observed_interpreter_resolved": str(observed),
        "interpreter_ready": interpreter_ready,
        "blockers": blockers,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    if Path(sys.executable).resolve() != REQUIRED_INTERPRETER.resolve():
        raise PredictiveVirtualBrakeCleanError(
            "v13 outcome rollout requires "
            "external/openpi/.venv/bin/python"
        )
    with _patched_inherited():
        return inherited.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.validate_results(
            protocol,
            protocol_path=protocol_path,
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
            parser.error(
                "--execute requires --policy-gpu and --egl-gpu"
            )
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
