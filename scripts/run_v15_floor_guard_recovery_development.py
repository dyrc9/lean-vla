#!/usr/bin/env python3
"""Run outcome-informed v15 floor-guard recovery development."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import math
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
from scripts import run_l2_predictive_virtual_brake_v15_floor_guard_recovery as online  # noqa: E402
from scripts import run_v14_multijoint_task_utility_qualification as base  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-floor-guard-recovery-"
    "development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-floor-guard-recovery-"
    "development-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_floor_guard_recovery_development"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_floor_guard_"
    "recovery_development_protocol.json"
)
_BASE_ENRICH = base._qualification_enrich
_L2_ARMS = {"execution_only", "dual"}
_UTILITY_GATES = {
    "v9_execution_only_task_success_noninferiority",
    "v9_dual_task_success_noninferiority",
    "v9_execution_only_official_unsafe_nonincrease",
    "v9_dual_official_unsafe_nonincrease",
}


class V15RecoveryDevelopmentError(RuntimeError):
    """Raised when v15 development evidence loses its bindings."""


def _minimum_margin(value: Any) -> float:
    if not isinstance(value, list) or len(value) != online.JOINT_COUNT:
        raise V15RecoveryDevelopmentError(
            "v15 actual margin matrix lacks seven rows"
        )
    margins = []
    for expected_joint, row in enumerate(value):
        if (
            not isinstance(row, Mapping)
            or row.get("joint_index") != expected_joint
        ):
            raise V15RecoveryDevelopmentError(
                "v15 actual margin joint identity differs"
            )
        for key in ("lower_margin_rad", "upper_margin_rad"):
            margin = row.get(key)
            if (
                isinstance(margin, bool)
                or not isinstance(margin, (int, float))
                or not math.isfinite(float(margin))
            ):
                raise V15RecoveryDevelopmentError(
                    "v15 actual margin is not finite"
                )
            margins.append(float(margin))
    return min(margins)


def _recovery_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters: Counter[str] = Counter()
    metadata_mismatches = 0
    recovery_selected_minimum: float | None = None
    selected_floor_violations = 0

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
            "floor_guard_recovery_active": l2_enabled,
            "floor_guard_recovery_margin_rad": (
                online.RECOVERY_GUARD_MARGIN_RAD
                if l2_enabled
                else None
            ),
            "floor_guard_recovery_margin_epsilon_rad": (
                online.RECOVERY_MARGIN_EPSILON_RAD
                if l2_enabled
                else None
            ),
            "floor_guard_recovery_source_action_substitution": False,
            "floor_guard_recovery_outcome_informed_successor": True,
            "floor_guard_recovery_physical_authority_claim": False,
        }
        metadata_mismatches += sum(
            metadata.get(key) != expected
            for key, expected in expected_metadata.items()
        )

        for row in episode["trace"]:
            if row.get("phase") != "policy":
                continue
            audit = row.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
                or audit.get("enabled") is not l2_enabled
            ):
                raise V15RecoveryDevelopmentError(
                    f"v15 audit identity differs: {episode_id}"
                )
            counters["policy_audit_count"] += 1
            actual_minimum = _minimum_margin(
                audit.get("actual_joint_side_margins")
            )
            if not l2_enabled:
                counters["disabled_audit_count"] += 1
                counters["disabled_recovery_active_count"] += int(
                    audit.get("floor_guard_recovery_active") is True
                )
                continue

            counters["l2_audit_count"] += 1
            triggered = audit.get("triggered") is True
            attempted = (
                audit.get("floor_guard_recovery_attempted") is True
            )
            counters["trigger_count"] += int(triggered)
            counters["recovery_attempt_count"] += int(attempted)
            counters["recovery_eligible_count"] += int(
                audit.get("floor_guard_recovery_eligible") is True
            )
            selected = (
                audit.get("floor_guard_recovery_selected") is True
            )
            baseline_deadlock = (
                audit.get("v14_baseline_would_deadlock") is True
            )
            prevented = (
                audit.get("floor_guard_recovery_prevented_deadlock")
                is True
            )
            counters["v14_baseline_would_deadlock_count"] += int(
                baseline_deadlock
            )
            counters["recovery_selected_count"] += int(selected)
            counters["recovery_prevented_deadlock_count"] += int(
                prevented
            )
            counters["residual_deadlock_count"] += int(
                audit.get("deadlock") is True
            )
            counters["trigger_attempt_identity_mismatch_count"] += int(
                triggered != attempted
            )
            counters["recovery_selection_order_mismatch_count"] += int(
                selected and not baseline_deadlock
            )
            counters["recovery_prevention_identity_mismatch_count"] += int(
                prevented
                != (
                    baseline_deadlock
                    and selected
                    and audit.get("deadlock") is False
                )
            )
            if selected:
                recovery_selected_minimum = (
                    actual_minimum
                    if recovery_selected_minimum is None
                    else min(recovery_selected_minimum, actual_minimum)
                )
                selected_floor_violations += int(
                    actual_minimum < online.SAFE_MARGIN_FLOOR_RAD
                )
                counters[
                    "recovery_selected_exact_action_identity_count"
                ] += int(audit.get("exact_action_identity") is True)

    aggregate = evidence["aggregate"]
    expected_policy = int(aggregate["policy_step_count"])
    expected_l2 = int(aggregate["l2_policy_step_count"])
    metrics = {
        **dict(sorted(counters.items())),
        "metadata_mismatch_count": metadata_mismatches,
        "recovery_selected_minimum_actual_margin_rad": (
            recovery_selected_minimum
        ),
        "recovery_selected_floor_violation_count": (
            selected_floor_violations
        ),
    }
    gates = {
        "v15_recovery_metadata_matches": metadata_mismatches == 0,
        "v15_recovery_audit_coverage": (
            counters["policy_audit_count"] == expected_policy
            and counters["l2_audit_count"] == expected_l2
            and counters["disabled_audit_count"]
            == expected_policy - expected_l2
            and counters["disabled_recovery_active_count"] == 0
        ),
        "v15_every_trigger_evaluates_floor_fallback": (
            counters["trigger_attempt_identity_mismatch_count"] == 0
        ),
        "v15_floor_fallback_preserves_v14_candidate_precedence": (
            counters["recovery_selection_order_mismatch_count"] == 0
        ),
        "v15_recovery_prevention_identity": (
            counters[
                "recovery_prevention_identity_mismatch_count"
            ]
            == 0
        ),
        "v15_selected_recovery_preserves_floor": (
            selected_floor_violations == 0
            and counters[
                "recovery_selected_exact_action_identity_count"
            ]
            == counters["recovery_selected_count"]
        ),
    }
    return metrics, gates


def _development_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    metrics, gates = _recovery_metrics(protocol, enriched)
    gate_results = {**enriched["gate_results"], **gates}
    data_gates = {
        name: passed
        for name, passed in gate_results.items()
        if name not in _UTILITY_GATES
    }
    data_complete = bool(
        data_gates and all(passed is True for passed in data_gates.values())
    )
    descriptive_utility = all(
        gate_results.get(name) is True for name in _UTILITY_GATES
    )
    return {
        **enriched,
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["complete_classification"]
            if data_complete
            else protocol["incomplete_classification"]
        ),
        "gate_results": gate_results,
        "aggregate": {**enriched["aggregate"], **metrics},
        "pilot_complete": data_complete,
        "development_data_complete": data_complete,
        "qualification_pass": False,
        "clean_utility_gate_passed": descriptive_utility,
        "descriptive_clean_utility_gate_passed": descriptive_utility,
        "task_utility_qualification_claim_authorized": False,
        "held_out_population": False,
        "task_outcomes_observed_before_protocol_freeze": True,
        "outcome_informed_recovery_development": True,
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "simulator_safety_claim_authorized": False,
        "method_claim": (
            "outcome-informed development of a shadow-validated floor-edge "
            "simulator backup guard"
        ),
    }


@contextmanager
def _patched_base() -> Iterator[None]:
    originals = (
        base.PROTOCOL_SCHEMA,
        base.EVIDENCE_SCHEMA,
        base.AUTHORIZED_STATUS,
        base.DEFAULT_PROTOCOL,
        base._qualification_enrich,
        base.base.online,
    )
    base.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    base.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    base.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    base.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    base._qualification_enrich = _development_enrich
    base.base.online = online
    try:
        yield
    finally:
        (
            base.PROTOCOL_SCHEMA,
            base.EVIDENCE_SCHEMA,
            base.AUTHORIZED_STATUS,
            base.DEFAULT_PROTOCOL,
            base._qualification_enrich,
            base.base.online,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_base():
        report = base.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v15-floor-guard-"
            "recovery-development-preflight.v1"
        ),
        "qualification_role": False,
        "development_role": True,
        "outcome_informed_recovery_development": True,
        "task_outcomes_observed_before_protocol_freeze": True,
        "selected_pair_task_outcomes_observed_before_freeze": True,
        "development_pair_selection_conditioned_on_task_deadlock": True,
        "confirmatory_safety_claim_authorized": False,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_base():
        return base.execute(
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
    with _patched_base():
        return base.validate_results(
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
            parser.error("--execute requires --policy-gpu and --egl-gpu")
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
