#!/usr/bin/env python3
"""Freeze/check the v12.5 integrated fixed-trace terminal."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_integrated_predictive_recovery_v12_"
    "fixed_trace_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_integrated_predictive_recovery_v12_"
    "fixed_trace_20260730_fresh1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_integrated_predictive_recovery_v12_"
    "fixed_trace_terminal_summary.json"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def build_terminal() -> dict[str, Any]:
    protocol = _load(PROTOCOL_PATH)
    summary = _load(RESULT_ROOT / "summary.json")
    manifest = _load(RESULT_ROOT / "run_manifest.json")
    metrics = summary["metrics"]
    if (
        manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
        or manifest.get("policy_loaded") is not False
        or manifest.get("simulator_created") is not False
        or summary.get("classification")
        != "integrated_predictive_recovery_v12_fixed_trace_pass"
        or summary.get("qualification_pass") is not True
        or summary.get("failed_gates") != []
        or metrics["valid_case_count"] != 60
        or metrics["expected_route_rate"] != 1.0
        or metrics["receipt_identity_rate"] != 1.0
        or metrics["recovery_completion_rate"] != 1.0
        or metrics["fresh_policy_authorization_rate"] != 1.0
        or metrics["old_policy_authorization_accept_count"] != 0
        or metrics[
            "recovery_authorization_replay_accept_count"
        ]
        != 0
        or metrics["negative_path_sink_apply_count"] != 0
        or metrics["outcome_read_count"] != 0
    ):
        raise RuntimeError(
            "integrated predictive-recovery result is not terminal pass"
        )
    return {
        "schema": (
            "proofalign.integrated-predictive-recovery-v12-terminal.v1"
        ),
        "classification": summary["classification"],
        "qualification_pass": True,
        "terminal": True,
        "metrics": metrics,
        "gate_conditions": summary["gate_conditions"],
        "source": {
            "protocol_path": str(
                PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "protocol_sha256": _sha256(PROTOCOL_PATH),
            "summary_path": str(
                (RESULT_ROOT / "summary.json").relative_to(REPO_ROOT)
            ),
            "summary_sha256": _sha256(RESULT_ROOT / "summary.json"),
            "ledger_path": str(
                (
                    RESULT_ROOT / "qualification_ledger.jsonl"
                ).relative_to(REPO_ROOT)
            ),
            "ledger_sha256": _sha256(
                RESULT_ROOT / "qualification_ledger.jsonl"
            ),
            "manifest_path": str(
                (RESULT_ROOT / "run_manifest.json").relative_to(REPO_ROOT)
            ),
            "manifest_sha256": _sha256(
                RESULT_ROOT / "run_manifest.json"
            ),
            "checksums_path": str(
                (RESULT_ROOT / "SHA256SUMS").relative_to(REPO_ROOT)
            ),
            "checksums_sha256": _sha256(
                RESULT_ROOT / "SHA256SUMS"
            ),
        },
        "lifecycle": {
            "integrated_fixed_trace_qualified": True,
            "simulator_integrated_pilot_authorized": True,
            "clean_rollout_authorized": False,
            "attacked_rollout_authorized": False,
            "outcome_rollout_authorized": False,
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical(build_terminal())
    if args.check:
        if not TERMINAL_PATH.is_file():
            raise SystemExit(f"missing: {TERMINAL_PATH}")
        if TERMINAL_PATH.read_text() != expected:
            raise SystemExit(f"stale: {TERMINAL_PATH}")
        print(f"current: {TERMINAL_PATH}")
        return 0
    if TERMINAL_PATH.exists():
        raise SystemExit(
            f"refusing to overwrite terminal: {TERMINAL_PATH}"
        )
    TERMINAL_PATH.write_text(expected)
    print(f"wrote: {TERMINAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
