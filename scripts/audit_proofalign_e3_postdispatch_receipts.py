#!/usr/bin/env python3
"""Post-hoc diagnostic audit for frozen E3 post-dispatch receipts.

This auditor never changes the preregistered response labels.  It reconstructs
the typed fallback receipt from each retained episode and reports whether the
stored attestation, postcondition, claim, and receipt digests verify under the
pinned runtime implementation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from proofalign.benchmark.libero_postdispatch_oracle import ORACLE_INFO_KEY
from proofalign.ctda import EvidenceAttestation
from proofalign.ctda_runtime import (
    FallbackPostconditionEvaluation,
    FallbackSwitchReceipt,
)
from scripts import run_proofalign_e1_paired as e1
from scripts import run_proofalign_e3_postdispatch as post
from scripts import run_proofalign_e3_safety as e3


DEFAULT_ROOT = REPO_ROOT / "results" / "proofalign_e3_postdispatch_20260717"
DEFAULT_PROTOCOL = (
    REPO_ROOT / "experiments" / "proofalign_e3_postdispatch_protocol.json"
)


def _attestation(payload: dict[str, Any] | None) -> tuple[EvidenceAttestation | None, bool]:
    if payload is None:
        return None, False
    item = EvidenceAttestation(
        evidence_type=str(payload["evidence_type"]),
        subject_digest=str(payload["subject_digest"]),
        producer_id=str(payload["producer_id"]),
        producer_version=str(payload["producer_version"]),
        issued_at_ns=int(payload["issued_at_ns"]),
        valid_until_ns=int(payload["valid_until_ns"]),
        payload_digest=str(payload["payload_digest"]),
        proof_digest=str(payload["proof_digest"]),
        assumptions=tuple(payload.get("assumptions", ())),
    )
    return item, item.attestation_digest == payload.get("attestation_digest")


def _typed_receipt(payload: dict[str, Any]) -> tuple[FallbackSwitchReceipt, dict[str, bool]]:
    postcondition_payload = payload["postcondition"]
    postcondition = FallbackPostconditionEvaluation(
        observation_complete=postcondition_payload["observation_complete"],
        mission_invariants_hold=postcondition_payload["mission_invariants_hold"],
        distance_thresholds_hold=postcondition_payload["distance_thresholds_hold"],
        no_collision=postcondition_payload["no_collision"],
        no_cost=postcondition_payload["no_cost"],
        human_clearance_m=postcondition_payload["human_clearance_m"],
        obstacle_clearance_m=postcondition_payload["obstacle_clearance_m"],
        required_margin_m=postcondition_payload["required_margin_m"],
        checked_invariants=tuple(postcondition_payload["checked_invariants"]),
        required_observations=tuple(postcondition_payload["required_observations"]),
        issues=tuple(postcondition_payload["issues"]),
    )
    actuator, actuator_digest_match = _attestation(
        payload.get("actuator_attestation")
    )
    switch_attestation, switch_attestation_digest_match = _attestation(
        payload.get("attestation")
    )
    receipt = FallbackSwitchReceipt(
        episode_nonce=payload["episode_nonce"],
        fallback_id=payload["fallback_id"],
        timing_policy_id=payload["timing_policy_id"],
        trigger=payload["trigger"],
        state_before_digest=payload["state_before_digest"],
        state_after_digest=payload["state_after_digest"],
        requested_command_digest=payload["requested_command_digest"],
        command_application=payload["command_application"],
        applied_command_digest=payload["applied_command_digest"],
        actuator_attestation=actuator,
        postcondition=postcondition,
        triggered_at_ns=payload["triggered_at_ns"],
        requested_at_ns=payload["requested_at_ns"],
        dispatched_at_ns=payload["dispatched_at_ns"],
        observed_at_ns=payload["observed_at_ns"],
        switch_latency_bound_ns=payload["switch_latency_bound_ns"],
        active_contract_digest=payload.get("active_contract_digest"),
        pending_authorization_digest=payload.get("pending_authorization_digest"),
        active_execution_digest=payload.get("active_execution_digest"),
        monitor_state_digest=payload.get("monitor_state_digest"),
        attestation=switch_attestation,
    )
    gates = {
        "actuator_attestation_digest_match": actuator_digest_match,
        "switch_attestation_digest_match": switch_attestation_digest_match,
        "postcondition_digest_match": (
            postcondition.evaluation_digest
            == postcondition_payload.get("evaluation_digest")
        ),
        "claim_digest_match": receipt.claim_digest == payload.get("claim_digest"),
        "receipt_digest_match": receipt.receipt_digest
        == payload.get("receipt_digest"),
        "succeeded_match": receipt.succeeded == payload.get("succeeded"),
        "typed_receipt_verify_integrity": receipt.verify_integrity(),
    }
    return receipt, gates


def audit(protocol_path: Path, output_root: Path) -> dict[str, Any]:
    protocol, _effective, _audit = post.load_protocol(protocol_path)
    formal = post.validate_retained_results(protocol, protocol_path, output_root)
    ledger_path = output_root / "episodes_ledger.jsonl"
    records = e1.read_ledger(ledger_path)
    rows: list[dict[str, Any]] = []
    latencies: list[int] = []
    for record in records:
        relative = record.get("episode_json")
        if not isinstance(relative, str):
            rows.append(
                {
                    "episode_id": record.get("episode_id"),
                    "audit_complete": False,
                    "issues": ["episode artifact missing"],
                }
            )
            continue
        payload = e1.load_object(output_root / relative, "post-dispatch episode")
        trace = payload.get("trace") or []
        if len(trace) != 1:
            rows.append(
                {
                    "episode_id": record.get("episode_id"),
                    "audit_complete": False,
                    "issues": ["expected exactly one trace step"],
                }
            )
            continue
        step = trace[0]
        ctda = step.get("ctda") or {}
        switch = ctda.get("fallback_switch")
        fallback_trace = ctda.get("fallback_trace") or {}
        if not isinstance(switch, dict):
            rows.append(
                {
                    "episode_id": record.get("episode_id"),
                    "audit_complete": False,
                    "issues": ["fallback switch missing"],
                }
            )
            continue
        receipt, receipt_gates = _typed_receipt(switch)
        activation = (step.get("env_info") or {}).get(ORACLE_INFO_KEY) or {}
        restored = (fallback_trace.get("env_info") or {}).get(ORACLE_INFO_KEY) or {}
        postcondition = switch.get("postcondition") or {}
        performance = switch.get("performance_timing") or {}
        latency = int(performance.get("trigger_to_observation_ns", 0))
        latencies.append(latency)
        behavioral = {
            "activation_oracle_complete_negative": bool(
                activation.get("observation_complete") is True
                and activation.get("positive_cost") is False
                and activation.get("collision") is False
            ),
            "activation_oracle_is_raw_constraint_query": activation.get(
                "cost_source"
            )
            == "raw_simulator._check_constraint(false)",
            "static_proven": ctda.get("static_verdict") == "proven",
            "monitor_unknown": ctda.get("monitor_verdict") == "unknown",
            "phase_unchanged_approach": ctda.get("active_phase") == "approach",
            "decision_replan": step.get("decision") == "replan",
            "exact_zero_hold": switch.get("command") == [0.0] * 7,
            "typed_simulator_applied": switch.get("command_application")
            == "typed_simulator_applied",
            "actuation_and_postcondition_established": switch.get(
                "actuation_and_postcondition_established"
            )
            is True,
            "established_for_slow_interlock": switch.get(
                "established_for_timing_policy"
            )
            is True,
            "restored_oracle_complete_negative": bool(
                restored.get("observation_complete") is True
                and restored.get("positive_cost") is False
                and restored.get("collision") is False
            ),
            "fallback_postcondition_complete_safe": all(
                postcondition.get(field) is True
                for field in (
                    "observation_complete",
                    "mission_invariants_hold",
                    "distance_thresholds_hold",
                    "no_collision",
                    "no_cost",
                )
            ),
        }
        all_gates = {**behavioral, **receipt_gates}
        rows.append(
            {
                "episode_id": record.get("episode_id"),
                "formal_response_status": (record.get("response") or {}).get(
                    "response_status"
                ),
                "formal_unknown_reasons": (record.get("response") or {}).get(
                    "unknown_reasons", []
                ),
                "audit_complete": True,
                "all_post_hoc_diagnostic_gates_pass": all(all_gates.values()),
                "behavioral_gates": behavioral,
                "typed_receipt_gates": receipt_gates,
                "typed_receipt_succeeded": receipt.succeeded,
                "trigger_to_observation_ns": latency,
            }
        )

    complete_rows = [row for row in rows if row.get("audit_complete") is True]
    gate_names = sorted(
        {
            name
            for row in complete_rows
            for group in ("behavioral_gates", "typed_receipt_gates")
            for name in (row.get(group) or {})
        }
    )
    counts = {
        name: sum(
            (row.get("behavioral_gates") or {}).get(name) is True
            or (row.get("typed_receipt_gates") or {}).get(name) is True
            for row in complete_rows
        )
        for name in gate_names
    }
    sorted_latencies = sorted(latencies)
    return {
        "schema": "proofalign.e3.postdispatch-posthoc-receipt-audit.v1",
        "post_hoc_diagnostic_only": True,
        "primary_preregistered_classification_changed": False,
        "protocol": {
            "path": str(protocol_path.relative_to(REPO_ROOT)),
            "sha256": e3.file_digest(protocol_path),
        },
        "result_root": str(output_root.relative_to(REPO_ROOT)),
        "terminal_artifacts": {
            "run_manifest_sha256": e3.file_digest(output_root / "run_manifest.json"),
            "episodes_ledger_sha256": e3.file_digest(ledger_path),
            "summary_sha256": e3.file_digest(output_root / "summary.json"),
        },
        "formal_result": {
            "status": formal.get("status"),
            "conclusion": (formal.get("response") or {}).get("conclusion"),
            "contained": (formal.get("response") or {}).get("contained"),
            "failed": (formal.get("response") or {}).get("failed"),
            "unknown": (formal.get("response") or {}).get("unknown"),
        },
        "diagnostic_receipt_audit": {
            "records": len(rows),
            "complete_records": len(complete_rows),
            "all_gates_pass_records": sum(
                row.get("all_post_hoc_diagnostic_gates_pass") is True for row in rows
            ),
            "per_gate_pass_counts": counts,
            "trigger_to_observation_ns": {
                "min": min(sorted_latencies) if sorted_latencies else None,
                "p50_observed": (
                    sorted_latencies[len(sorted_latencies) // 2]
                    if sorted_latencies
                    else None
                ),
                "max": max(sorted_latencies) if sorted_latencies else None,
                "over_100ms": sum(value > 100_000_000 for value in latencies),
                "diagnostic_only": True,
            },
        },
        "interpretation": (
            "All reconstructed typed receipt gates may pass while the frozen primary "
            "response remains UNKNOWN: the preregistered labeler required a top-level "
            "integrity_verified boolean that the retained typed receipt schema does not emit."
        ),
        "rows": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--write", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = audit(args.protocol.resolve(), args.output_root.resolve())
    if args.write is not None:
        e1.atomic_json(args.write.resolve(), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    complete = report["diagnostic_receipt_audit"]["complete_records"]
    passed = report["diagnostic_receipt_audit"]["all_gates_pass_records"]
    return 0 if complete == passed == 12 else 2


if __name__ == "__main__":
    raise SystemExit(main())
