#!/usr/bin/env python3
"""Run v15.2 current-edge-priority recovery development."""

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
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as online  # noqa: E402
from scripts import run_v15_current_edge_recovery_development as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-priority-"
    "recovery-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15-current-edge-priority-"
    "recovery-development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_current_edge_priority_recovery_development"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_"
    "priority_recovery_development_protocol.json"
)
_BASE_ENRICH = predecessor._development_enrich
_INCOMPATIBLE_FLOOR_ONLY_GATE = "v15_recovery_prevention_identity"


class V15CurrentEdgePriorityDevelopmentError(RuntimeError):
    """Raised when priority-recovery development evidence differs."""


def _priority_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters: Counter[str] = Counter()
    metadata_mismatches = 0
    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        l2_enabled = arm in predecessor._L2_ARMS
        episode = load_json_object(REPO_ROOT / str(artifact["path"]))
        metadata = episode["metadata"]
        expected = {
            "runner_variant": online.RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                online.BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "current_edge_priority_recovery_active": l2_enabled,
            "recovery_candidate_priority": (
                [
                    "v14_frozen_guard_margins",
                    "current_edge",
                    "floor_edge",
                ]
                if l2_enabled
                else None
            ),
            "current_edge_priority_source_action_substitution": False,
            "current_edge_priority_outcome_informed_successor": True,
            "current_edge_priority_physical_authority_claim": False,
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
                raise V15CurrentEdgePriorityDevelopmentError(
                    f"v15.2 audit identity differs: {episode_id}"
                )
            counters["policy_audit_count"] += 1
            if not l2_enabled:
                counters["disabled_audit_count"] += 1
                counters["disabled_priority_active_count"] += int(
                    audit.get("current_edge_priority_recovery_active")
                    is True
                )
                continue
            counters["l2_audit_count"] += 1
            if audit.get("triggered") is not True:
                continue
            candidates = audit.get("candidates")
            if not isinstance(candidates, list):
                raise V15CurrentEdgePriorityDevelopmentError(
                    "v15.2 triggered audit lacks candidates"
                )
            margins = [float(row["guard_margin_rad"]) for row in candidates]
            if margins[: len(online.BRAKE_MARGINS_RAD)] != list(
                online.BRAKE_MARGINS_RAD
            ):
                counters["v14_candidate_order_mismatch_count"] += 1
            floor_index = margins.index(online.RECOVERY_GUARD_MARGIN_RAD)
            current = audit.get(
                "current_edge_recovery_configured_margin_rad"
            )
            if current is not None:
                counters["current_edge_configured_count"] += 1
                current_index = margins.index(float(current))
                counters["priority_order_mismatch_count"] += int(
                    current_index >= floor_index
                )
            counters["floor_selected_count_v15_2"] += int(
                audit.get("floor_guard_recovery_selected") is True
            )
            counters["current_edge_selected_count_v15_2"] += int(
                audit.get("current_edge_recovery_selected") is True
            )

    aggregate = evidence["aggregate"]
    expected_policy = int(aggregate["policy_step_count"])
    expected_l2 = int(aggregate["l2_policy_step_count"])
    metrics = {
        **dict(sorted(counters.items())),
        "priority_metadata_mismatch_count": metadata_mismatches,
    }
    gates = {
        "v15_2_priority_metadata_matches": metadata_mismatches == 0,
        "v15_2_priority_audit_coverage": (
            counters["policy_audit_count"] == expected_policy
            and counters["l2_audit_count"] == expected_l2
            and counters["disabled_audit_count"]
            == expected_policy - expected_l2
            and counters["disabled_priority_active_count"] == 0
        ),
        "v15_2_v14_candidate_order_preserved": (
            counters["v14_candidate_order_mismatch_count"] == 0
        ),
        "v15_2_current_edge_precedes_floor_when_configured": (
            counters["priority_order_mismatch_count"] == 0
        ),
    }
    return metrics, gates


def _development_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    metrics, gates = _priority_metrics(protocol, enriched)
    gate_results = {
        name: passed
        for name, passed in enriched["gate_results"].items()
        if name != _INCOMPATIBLE_FLOOR_ONLY_GATE
    }
    gate_results.update(gates)
    data_gates = {
        name: passed
        for name, passed in gate_results.items()
        if name not in predecessor._UTILITY_GATES
    }
    data_complete = bool(
        data_gates and all(value is True for value in data_gates.values())
    )
    descriptive_utility = all(
        gate_results.get(name) is True
        for name in predecessor._UTILITY_GATES
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
        "incompatible_floor_only_gate_removed_before_execution": True,
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "simulator_safety_claim_authorized": False,
        "method_claim": (
            "outcome-informed development of a buffer-preserving ordered "
            "current-edge/floor-edge simulator backup guard"
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
            "priority-recovery-development-preflight.v1"
        ),
        "current_edge_priority_successor_role": True,
        "incompatible_floor_only_gate_removed_before_execution": True,
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
