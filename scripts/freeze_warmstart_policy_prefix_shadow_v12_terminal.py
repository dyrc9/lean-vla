#!/usr/bin/env python3
"""Freeze/check the v12.4b warm-start policy-shadow terminal result."""

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
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "qualification_20260729_fresh1"
)
PREDECESSOR_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "qualification_terminal_summary.json"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "qualification_terminal_summary.json"
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
    predecessor = _load(PREDECESSOR_TERMINAL_PATH)
    metrics = summary["metrics"]
    if (
        manifest.get("status") != "complete"
        or summary.get("classification")
        != "warmstart_policy_prefix_shadow_v12_qualification_pass"
        or summary.get("qualification_pass") is not True
        or summary.get("failed_gates") != []
        or summary.get("outcomes_observed") is not False
        or metrics["valid_case_count"] != 30
        or metrics["repeat_trajectory_within_tolerance_rate"]
        != 1.0
        or metrics["qacc_warmstart_restore_identity_rate"] != 1.0
        or metrics["policy_load_count"] != 0
        or metrics["live_policy_dispatch_count"] != 0
        or metrics["outcome_read_count"] != 0
        or predecessor.get("qualification_pass") is not True
    ):
        raise RuntimeError(
            "v12.4b result is not the expected terminal pass"
        )
    return {
        "schema": (
            "proofalign.warmstart-policy-prefix-shadow-v12-terminal.v1"
        ),
        "classification": summary["classification"],
        "qualification_pass": True,
        "terminal": True,
        "metrics": metrics,
        "gate_conditions": summary["gate_conditions"],
        "improvement_over_v12_4a": {
            "predecessor_path": str(
                PREDECESSOR_TERMINAL_PATH.relative_to(REPO_ROOT)
            ),
            "predecessor_sha256": _sha256(
                PREDECESSOR_TERMINAL_PATH
            ),
            "predecessor_repeat_within_tolerance_rate": (
                predecessor["metrics"][
                    "repeat_trajectory_within_tolerance_rate"
                ]
            ),
            "successor_repeat_within_tolerance_rate": metrics[
                "repeat_trajectory_within_tolerance_rate"
            ],
            "predecessor_max_abs_qpos_error_rad": predecessor[
                "metrics"
            ]["repeat_trajectory_max_abs_qpos_error_rad"],
            "successor_max_abs_qpos_error_rad": metrics[
                "repeat_trajectory_max_abs_qpos_error_rad"
            ],
            "only_mechanism_change": "bind_sim_data_qacc_warmstart",
            "predecessor_unchanged": True,
        },
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
            "checksums_path": str(
                (RESULT_ROOT / "SHA256SUMS").relative_to(REPO_ROOT)
            ),
            "checksums_sha256": _sha256(
                RESULT_ROOT / "SHA256SUMS"
            ),
        },
        "lifecycle": {
            "fixed_prefix_warmstart_shadow_qualified": True,
            "fresh_policy_qualification_complete": False,
            "fresh_policy_retry_authorized_when_resource_gate_passes": True,
            "clean_rollout_authorized": False,
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
