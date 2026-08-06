#!/usr/bin/env python3
"""Freeze/check the v12.3 recovery snapshot-boundary qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recovery_snapshot_v12_qualification_protocol.json"
)
PREDECESSOR_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_prefix_recovery_v12_multijoint_"
    "qualification_terminal_summary.json"
)
PREDECESSOR_LEDGER_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_prefix_recovery_v12_multijoint_"
    "qualification_20260729_fresh1"
    / "qualification_ledger.jsonl"
)
PREDECESSOR_SUMMARY_PATH = (
    PREDECESSOR_LEDGER_PATH.parent / "summary.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_recovery_snapshot_v12_qualification_"
    "20260729_fresh1"
)
SCHEMA = "proofalign.recovery-snapshot-v12-qualification-protocol.v1"
PROTOCOL_ID = "proofalign-recovery-snapshot-v12-qualification-20260729"
SOURCE_PATHS = (
    "src/proofalign/simulator_snapshot_v12.py",
    "scripts/freeze_recovery_snapshot_v12_qualification.py",
    "scripts/run_recovery_snapshot_v12_qualification.py",
    "tests/test_simulator_snapshot_v12.py",
)
RUNTIME_PATHS = (
    "external/LIBERO-Safety/third_party/robosuite-1.4/"
    "robosuite/utils/binding_utils.py",
    "external/LIBERO-Safety/third_party/robosuite-1.4/"
    "robosuite/controllers/osc.py",
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _candidate_actions() -> dict[str, list[float]]:
    actions = {}
    for axis, axis_name in enumerate(("x", "y", "z", "rx", "ry", "rz")):
        for sign, sign_name in ((1.0, "positive"), (-1.0, "negative")):
            action = [0.0] * 7
            action[axis] = sign
            action[6] = -1.0
            actions[f"{sign_name}_{axis_name}"] = action
    actions["hold"] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]
    return actions


def build_protocol() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_PATH)
    summary = _load(PREDECESSOR_SUMMARY_PATH)
    rows = _load_rows(PREDECESSOR_LEDGER_PATH)
    if (
        predecessor.get("classification")
        != "prefix_recovery_v12_multijoint_qualification_nonpass"
        or predecessor.get("qualification_pass") is not False
        or predecessor.get("failed_gates")
        != ["shadow_restore_identity"]
        or summary["metrics"]["recovery_candidate_coverage"]
        < 0.90
        or summary["metrics"]["selected_replay_terminal_safe_rate"]
        != 1.0
        or summary["metrics"]["recovery_completion_rate"] != 1.0
    ):
        raise RuntimeError(
            "v12.2 predecessor is not the expected restore-only nonpass"
        )
    if len(rows) != 210:
        raise RuntimeError("v12.3 requires 210 predecessor rows")
    source_bindings = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise RuntimeError(
                f"missing v12.3 snapshot source: {relative}"
            )
        source_bindings[relative] = _sha256(path)
    runtime_bindings = {}
    for relative in RUNTIME_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing snapshot runtime: {relative}")
        runtime_bindings[relative] = _sha256(path)
    pair_order = []
    seen = set()
    cases = []
    for row in rows:
        if row["base_pair_id"] not in seen:
            seen.add(row["base_pair_id"])
            pair_order.append(
                {
                    key: row[key]
                    for key in (
                        "base_pair_id",
                        "suite",
                        "task_id",
                        "init_state_id",
                        "bddl_path",
                        "trusted_instruction",
                    )
                }
            )
        cases.append(
            {
                "case_id": row["case_id"],
                "base_pair_id": row["base_pair_id"],
                "joint_index": row["joint_index"],
                "side": row["side"],
                "selected_candidate_id": row[
                    "selected_candidate_id"
                ],
                "selected_prefix_steps": row[
                    "selected_prefix_steps"
                ],
            }
        )
    return {
        "schema": SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": "authorized_no_outcome_snapshot_boundary_qualification",
        "created_at": "2026-07-29T20:00:00+08:00",
        "outcome_informed": True,
        "predecessor": {
            "path": str(PREDECESSOR_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(PREDECESSOR_PATH),
            "classification": predecessor["classification"],
            "qualification_pass": False,
            "failed_gates": predecessor["failed_gates"],
            "unchanged": True,
        },
        "predecessor_evidence": {
            "summary_path": str(
                PREDECESSOR_SUMMARY_PATH.relative_to(REPO_ROOT)
            ),
            "summary_sha256": _sha256(PREDECESSOR_SUMMARY_PATH),
            "ledger_path": str(
                PREDECESSOR_LEDGER_PATH.relative_to(REPO_ROOT)
            ),
            "ledger_sha256": _sha256(PREDECESSOR_LEDGER_PATH),
            "positive_metrics_reused_without_reclassification": {
                key: summary["metrics"][key]
                for key in (
                    "recovery_candidate_coverage",
                    "worst_suite_recovery_coverage",
                    "worst_joint_side_recovery_coverage",
                    "selected_replay_terminal_safe_rate",
                    "selected_replay_joint_limit_crossing_count",
                    "selected_replay_transient_loss_count",
                    "recovery_completion_rate",
                    "receipt_identity_rate",
                    "old_policy_authorization_accept_count",
                    "recovery_authorization_replay_accept_count",
                    "fresh_policy_authorization_rate",
                )
            },
        },
        "measurement_redesign": {
            "reason": (
                "The v12.2 gate combined trigger-state shadow restores with "
                "qualification-harness cleanup into one full-simulator "
                "bitwise flag. All nine failures occurred on the first "
                "joint0-lower case of an environment while selected replay "
                "identity and completion remained valid."
            ),
            "trigger_snapshot_gate": (
                "Require full MjSimState and trusted arm qpos/qvel identity "
                "after replaying the frozen selected recovery probe."
            ),
            "harness_cleanup_gate": (
                "Require exact trusted arm qpos/qvel restoration. Report "
                "full-state bitwise identity, differing count, and maximum "
                "error separately because forward may canonicalize non-arm "
                "object quaternions."
            ),
            "old_v12_2_gate_unchanged": True,
        },
        "population": {
            "pair_count": len(pair_order),
            "case_count": len(cases),
            "pairs": pair_order,
            "cases": cases,
            "environment_seed": 463,
        },
        "probe": {
            "camera_names": ["agentview"],
            "image_size": 64,
            "control_frequency_hz": 20,
            "environment_horizon": 100000,
            "injected_limit_margin_rad": 0.05,
            "fallback_probe_action": [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                -1.0,
            ],
            "candidate_actions": _candidate_actions(),
        },
        "gates": {
            "valid_case_count_min": len(cases),
            "baseline_model_trigger_rate_min": 1.0,
            "trigger_full_state_bitwise_identity_rate_min": 1.0,
            "trigger_trusted_arm_bitwise_identity_rate_min": 1.0,
            "harness_trusted_arm_bitwise_identity_rate_min": 1.0,
            "runtime_exception_count_max": 0,
            "policy_load_count_max": 0,
            "policy_action_dispatch_count_max": 0,
            "outcome_read_count_max": 0,
        },
        "execution_boundary": {
            "simulator_reset_authorized": True,
            "synthetic_joint_state_injection_authorized": True,
            "frozen_recovery_probe_env_step_authorized": True,
            "snapshot_restore_authorized": True,
            "task_outcome_read_authorized": False,
            "policy_load_authorized": False,
            "policy_action_dispatch_authorized": False,
            "efficacy_rollout_authorized": False,
        },
        "resource_gate": {
            "selected_gpu_memory_used_mib_max_exclusive": 30000,
            "minimum_free_disk_gib": 10,
        },
        "claim_boundary": (
            "This result-informed successor decomposes the sole failed v12.2 "
            "restore gate. It replays the frozen selected recovery action "
            "prefix (or one hold step for the sole abstention) solely to "
            "measure trigger MjSimState restoration and qualification-"
            "harness trusted arm restoration across the same 210 cases. It "
            "does not relabel the v12.2 nonpass, load or dispatch a policy, "
            "read task outcomes, establish controller-internal state "
            "restoration for nominal policy screening, clean utility, "
            "attacked efficacy, deployment, or physical safety."
        ),
        "lifecycle": {
            "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "overwrite_allowed": False,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step_if_pass": (
                "Freeze a no-outcome policy-prefix predictive-shadow "
                "qualification that explicitly snapshots controller state."
            ),
            "next_step_if_nonpass": (
                "Freeze the nonpass and redesign simulator/controller "
                "snapshot semantics under a new protocol."
            ),
        },
        "source_bindings": source_bindings,
        "runtime_bindings": runtime_bindings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical(build_protocol())
    if args.check:
        if not PROTOCOL_PATH.is_file():
            raise SystemExit(f"missing: {PROTOCOL_PATH}")
        if PROTOCOL_PATH.read_text() != expected:
            raise SystemExit(f"stale: {PROTOCOL_PATH}")
        print(f"current: {PROTOCOL_PATH}")
        return 0
    if PROTOCOL_PATH.exists():
        raise SystemExit(
            f"refusing to overwrite protocol: {PROTOCOL_PATH}"
        )
    PROTOCOL_PATH.write_text(expected)
    print(f"wrote: {PROTOCOL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
