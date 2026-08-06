#!/usr/bin/env python3
"""Freeze/check the fresh-policy v12.4 shadow qualification terminal."""

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
    / "proofalign_policy_prefix_shadow_v12_qualification_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_prefix_shadow_v12_qualification_"
    "20260729_fresh1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_policy_prefix_shadow_v12_qualification_"
    "terminal_summary.json"
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


def _ledger_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (
            RESULT_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]


def build_terminal() -> dict[str, Any]:
    protocol = _load(PROTOCOL_PATH)
    summary = _load(RESULT_ROOT / "summary.json")
    manifest = _load(RESULT_ROOT / "run_manifest.json")
    rows = _ledger_rows()
    metrics = summary["metrics"]
    if (
        manifest.get("status") != "complete"
        or manifest.get("outcomes_observed") is not False
        or summary.get("classification")
        != "policy_prefix_shadow_v12_qualification_pass"
        or summary.get("qualification_pass") is not True
        or summary.get("failed_gates") != []
        or summary.get("outcomes_observed") is not False
        or summary.get("clean_rollout_authorized") is not False
        or len(rows) != 30
        or metrics["valid_case_count"] != 30
        or metrics["policy_load_count"] != 1
        or metrics["policy_inference_count"] != 30
        or metrics["live_policy_dispatch_count"] != 0
        or metrics["outcome_read_count"] != 0
        or metrics["shadow_reference_risk_agreement_rate"] != 1.0
        or metrics["qacc_warmstart_restore_identity_rate"] != 1.0
        or metrics["repeat_trajectory_within_tolerance_rate"] < 0.95
    ):
        raise RuntimeError(
            "fresh-policy shadow result is not the expected terminal pass"
        )
    forbidden_outcome_keys = {
        "reward",
        "done",
        "success",
        "task_success",
        "cost",
        "collision",
    }
    if any(forbidden_outcome_keys & set(row) for row in rows):
        raise RuntimeError("fresh-policy shadow ledger contains outcome keys")
    repeat_outliers = [
        {
            "case_id": row["case_id"],
            "condition": row["condition"],
            "synthetic_joint_index": row["synthetic_joint_index"],
            "synthetic_joint_side": row["synthetic_joint_side"],
            "repeat_trajectory_max_abs_qpos_error_rad": row[
                "repeat_trajectory_max_abs_qpos_error_rad"
            ],
            "decision_verdict": row["decision"]["verdict"],
            "shadow_risk_predicted": row["shadow_assessment"][
                "risk_predicted"
            ],
            "reference_risk_predicted": row["reference_assessment"][
                "risk_predicted"
            ],
        }
        for row in rows
        if not row["repeat_trajectory_within_tolerance"]
    ]
    return {
        "schema": "proofalign.policy-prefix-shadow-v12-terminal.v1",
        "classification": summary["classification"],
        "qualification_pass": True,
        "terminal": True,
        "metrics": metrics,
        "gate_conditions": summary["gate_conditions"],
        "repeat_fidelity_tail": {
            "outlier_count": len(repeat_outliers),
            "outliers": repeat_outliers,
            "frozen_tolerance_rad": protocol["episode"][
                "trajectory_tolerance_rad"
            ],
            "dense_contact_warning_observed": True,
            "interpretation": (
                "The sole tail is a synthetic current-trigger case; both "
                "replays agree on risk and recovery_required. It does not "
                "change the frozen qualification pass."
            ),
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
            "fresh_policy_prefix_shadow_qualified": True,
            "integrated_predictive_recovery_gate_authorized": True,
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
