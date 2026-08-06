#!/usr/bin/env python3
"""Run outcome-informed v15.1 current-edge recovery development."""

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
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_recovery as online  # noqa: E402
from scripts import run_v15_floor_guard_recovery_development as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-recovery-"
    "development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-recovery-"
    "development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_current_edge_recovery_development"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "recovery_development_protocol.json"
)
_BASE_ENRICH = predecessor._development_enrich
_UTILITY_GATES = predecessor._UTILITY_GATES
_L2_ARMS = predecessor._L2_ARMS


class V15CurrentEdgeDevelopmentError(RuntimeError):
    """Raised when current-edge development evidence differs."""


def _current_edge_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters: Counter[str] = Counter()
    metadata_mismatches = 0
    selected_minimum: float | None = None

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        l2_enabled = arm in _L2_ARMS
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        metadata = episode["metadata"]
        expected = {
            "runner_variant": online.RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                online.BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "current_edge_recovery_active": l2_enabled,
            "current_edge_recovery_epsilon_rad": (
                online.CURRENT_EDGE_EPSILON_RAD
                if l2_enabled
                else None
            ),
            "current_edge_recovery_source_action_substitution": False,
            "current_edge_recovery_outcome_informed_successor": True,
            "current_edge_recovery_physical_authority_claim": False,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value for key, value in expected.items()
        )
        for trace in episode["trace"]:
            if trace.get("phase") != "policy":
                continue
            audit = trace.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
                or audit.get("enabled") is not l2_enabled
            ):
                raise V15CurrentEdgeDevelopmentError(
                    f"v15.1 audit identity differs: {episode_id}"
                )
            counters["policy_audit_count"] += 1
            if not l2_enabled:
                counters["disabled_audit_count"] += 1
                counters["disabled_current_edge_active_count"] += int(
                    audit.get("current_edge_recovery_active") is True
                )
                continue
            counters["l2_audit_count"] += 1
            attempted = audit.get("current_edge_recovery_attempted") is True
            eligible = audit.get("current_edge_recovery_eligible") is True
            current_selected = (
                audit.get("current_edge_recovery_selected") is True
            )
            any_selected = (
                audit.get("floor_or_current_edge_recovery_selected")
                is True
            )
            baseline_deadlock = (
                audit.get("v14_baseline_would_deadlock") is True
            )
            prevented = (
                audit.get(
                    "floor_or_current_edge_recovery_prevented_deadlock"
                )
                is True
            )
            counters["current_edge_attempt_count"] += int(attempted)
            counters["current_edge_eligible_count"] += int(eligible)
            counters["current_edge_selected_count"] += int(
                current_selected
            )
            counters["total_recovery_selected_count"] += int(any_selected)
            counters["total_recovery_prevented_deadlock_count"] += int(
                prevented
            )
            counters["v14_baseline_would_deadlock_count_v15_1"] += int(
                baseline_deadlock
            )
            counters["residual_deadlock_count_v15_1"] += int(
                audit.get("deadlock") is True
            )
            counters["selection_order_mismatch_count"] += int(
                any_selected and not baseline_deadlock
            )
            counters["prevention_identity_mismatch_count"] += int(
                prevented
                != (
                    baseline_deadlock
                    and any_selected
                    and audit.get("deadlock") is False
                )
            )
            if any_selected:
                minimum = predecessor._minimum_margin(
                    audit.get("actual_joint_side_margins")
                )
                selected_minimum = (
                    minimum
                    if selected_minimum is None
                    else min(selected_minimum, minimum)
                )
                counters["selected_floor_violation_count"] += int(
                    minimum < online.SAFE_MARGIN_FLOOR_RAD
                )
                counters["selected_exact_action_identity_count"] += int(
                    audit.get("exact_action_identity") is True
                )

    aggregate = evidence["aggregate"]
    expected_policy = int(aggregate["policy_step_count"])
    expected_l2 = int(aggregate["l2_policy_step_count"])
    metrics = {
        **dict(sorted(counters.items())),
        "current_edge_metadata_mismatch_count": metadata_mismatches,
        "total_recovery_selected_minimum_actual_margin_rad": (
            selected_minimum
        ),
    }
    gates = {
        "v15_1_current_edge_metadata_matches": metadata_mismatches == 0,
        "v15_1_current_edge_audit_coverage": (
            counters["policy_audit_count"] == expected_policy
            and counters["l2_audit_count"] == expected_l2
            and counters["disabled_audit_count"]
            == expected_policy - expected_l2
            and counters["disabled_current_edge_active_count"] == 0
        ),
        "v15_1_recovery_preserves_v14_candidate_precedence": (
            counters["selection_order_mismatch_count"] == 0
        ),
        "v15_1_recovery_prevention_identity": (
            counters["prevention_identity_mismatch_count"] == 0
        ),
        "v15_1_selected_recovery_preserves_floor": (
            counters["selected_floor_violation_count"] == 0
            and counters["selected_exact_action_identity_count"]
            == counters["total_recovery_selected_count"]
        ),
    }
    return metrics, gates


def _development_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    metrics, gates = _current_edge_metrics(protocol, enriched)
    gate_results = {**enriched["gate_results"], **gates}
    data_gates = {
        name: passed
        for name, passed in gate_results.items()
        if name not in _UTILITY_GATES
    }
    data_complete = bool(
        data_gates and all(value is True for value in data_gates.values())
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
            "outcome-informed development of ordered floor-edge and "
            "current-edge shadow-validated simulator backup guards"
        ),
    }


@contextmanager
def _patched_predecessor() -> Iterator[None]:
    originals = (
        predecessor.PROTOCOL_SCHEMA,
        predecessor.EVIDENCE_SCHEMA,
        predecessor.AUTHORIZED_STATUS,
        predecessor.DEFAULT_PROTOCOL,
        predecessor._development_enrich,
        predecessor.online,
    )
    predecessor.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    predecessor.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    predecessor.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    predecessor.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    predecessor._development_enrich = _development_enrich
    predecessor.online = online
    try:
        yield
    finally:
        (
            predecessor.PROTOCOL_SCHEMA,
            predecessor.EVIDENCE_SCHEMA,
            predecessor.AUTHORIZED_STATUS,
            predecessor.DEFAULT_PROTOCOL,
            predecessor._development_enrich,
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
            "proofalign.predictive-virtual-brake-v15-current-edge-"
            "recovery-development-preflight.v1"
        ),
        "current_edge_successor_role": True,
        "qualification_role": False,
        "development_role": True,
        "selected_pair_task_outcomes_observed_before_freeze": True,
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
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_predecessor():
        return predecessor.validate_results(
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
