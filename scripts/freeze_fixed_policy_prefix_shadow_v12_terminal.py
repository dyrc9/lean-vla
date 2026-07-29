#!/usr/bin/env python3
"""Freeze/check the v12.4a fixed-prefix shadow terminal result."""

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
    / "proofalign_fixed_policy_prefix_shadow_v12_qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_fixed_policy_prefix_shadow_v12_qualification_"
    "20260729_fresh1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
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
    if (
        manifest.get("status") != "complete"
        or summary.get("classification")
        != "fixed_policy_prefix_shadow_v12_qualification_pass"
        or summary.get("qualification_pass") is not True
        or summary.get("failed_gates") != []
        or summary.get("outcomes_observed") is not False
        or summary.get("fresh_policy_qualification_complete") is not False
        or summary["metrics"]["valid_case_count"] != 30
        or summary["metrics"]["live_policy_dispatch_count"] != 0
        or summary["metrics"]["outcome_read_count"] != 0
    ):
        raise RuntimeError(
            "v12.4a result is not the expected terminal pass"
        )
    return {
        "schema": (
            "proofalign.fixed-policy-prefix-shadow-v12-terminal.v1"
        ),
        "classification": summary["classification"],
        "qualification_pass": True,
        "terminal": True,
        "metrics": summary["metrics"],
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
            "checksums_path": str(
                (RESULT_ROOT / "SHA256SUMS").relative_to(REPO_ROOT)
            ),
            "checksums_sha256": _sha256(
                RESULT_ROOT / "SHA256SUMS"
            ),
        },
        "limitation": {
            "repeat_trajectory_within_tolerance_rate": summary[
                "metrics"
            ]["repeat_trajectory_within_tolerance_rate"],
            "repeat_trajectory_max_abs_qpos_error_rad": summary[
                "metrics"
            ]["repeat_trajectory_max_abs_qpos_error_rad"],
            "outlier_case_id": (
                "obstacle_avoidance_human_task4_init17:"
                "synthetic_joint_pressure"
            ),
            "outlier_injection": "joint1_upper",
            "diagnostic_hypothesis": (
                "MjSimState and the v12.4a auxiliary snapshot omit "
                "qacc_warmstart. The sole divergence occurs in a synthetic "
                "state that enters dense contact / limit dynamics."
            ),
            "frozen_result_unchanged": True,
        },
        "lifecycle": {
            "fixed_prefix_controller_shadow_mechanics_qualified": True,
            "warmstart_successor_authorized": True,
            "fresh_policy_qualification_complete": False,
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
