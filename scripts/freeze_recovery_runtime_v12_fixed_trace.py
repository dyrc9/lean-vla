#!/usr/bin/env python3
"""Freeze/check the v12.2 zero-policy recovery-runtime fixed trace."""

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
    / "proofalign_recovery_runtime_v12_fixed_trace_protocol.json"
)
PREDECESSOR_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_escape_recovery_v12_simulator_"
    "preflight_terminal_summary.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_recovery_runtime_v12_fixed_trace_"
    "20260729_fresh1"
)
SCHEMA = "proofalign.recovery-runtime-v12-fixed-trace-protocol.v1"
PROTOCOL_ID = "proofalign-recovery-runtime-v12-fixed-trace-20260729"
SOURCE_PATHS = (
    "src/proofalign/recoverable_alignment_v12.py",
    "src/proofalign/recovery_runtime_v12.py",
    "scripts/freeze_recovery_runtime_v12_fixed_trace.py",
    "scripts/run_recovery_runtime_v12_fixed_trace.py",
    "tests/test_recovery_runtime_v12.py",
)
CASES = (
    ("happy_exact", "allow"),
    ("authorization_replay", "reject"),
    ("step_substitution", "reject"),
    ("cross_boundary_session", "reject"),
    ("sink_substitution", "reject"),
    ("expired_before_dispatch", "reject"),
    ("incomplete_completion", "reject"),
    ("stale_observation_epoch", "reject"),
    ("unsafe_post_state", "reject"),
    ("fresh_policy_state_binding", "allow_exact_only"),
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


def build_protocol() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_PATH)
    if (
        predecessor.get("classification")
        != "escape_recovery_v12_simulator_preflight_pass"
        or predecessor.get("qualification_pass") is not True
        or predecessor["lifecycle"]["outcome_rollout_authorized"] is not False
    ):
        raise RuntimeError("v12.1 predecessor is not qualified")
    source_bindings = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing v12.2 fixed-trace source: {relative}")
        source_bindings[relative] = _sha256(path)
    return {
        "schema": SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": "authorized_zero_policy_fixed_trace",
        "created_at": "2026-07-29T18:30:00+08:00",
        "outcome_informed": True,
        "predecessor": {
            "path": str(PREDECESSOR_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(PREDECESSOR_PATH),
            "classification": predecessor["classification"],
            "unchanged": True,
        },
        "cases": [
            {
                "case_id": case_id,
                "expected_classification": expected,
            }
            for case_id, expected in CASES
        ],
        "case_count": len(CASES),
        "gates": {
            "valid_case_count_min": len(CASES),
            "expected_classification_rate_min": 1.0,
            "happy_receipt_identity_rate_min": 1.0,
            "old_policy_authorization_accept_count_max": 0,
            "recovery_authorization_replay_accept_count_max": 0,
            "policy_load_count_max": 0,
            "policy_action_dispatch_count_max": 0,
            "simulator_create_count_max": 0,
            "outcome_read_count_max": 0,
            "runtime_exception_count_max": 0,
        },
        "execution_boundary": {
            "in_memory_recovery_sink_authorized": True,
            "policy_load_authorized": False,
            "policy_action_dispatch_authorized": False,
            "simulator_create_authorized": False,
            "task_outcome_read_authorized": False,
            "efficacy_rollout_authorized": False,
        },
        "claim_boundary": (
            "This fixed trace qualifies typed recovery authorization, "
            "single-use ordered 7D recovery receipts, substitution/replay "
            "rejection, old-policy revocation, fresh observation epoch, and "
            "fresh-policy state binding with an in-memory sink. It loads no "
            "policy, creates no simulator, reads no task outcome, and does "
            "not establish dynamics fidelity, arbitrary-state recovery, "
            "clean utility, attacked efficacy, deployment, or physical "
            "safety."
        ),
        "lifecycle": {
            "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "overwrite_allowed": False,
            "outcome_rollout_authorized": False,
            "clean_rollout_authorized": False,
            "next_step_if_pass": (
                "Freeze and run a 7-joint upper/lower no-outcome LIBERO "
                "simulator qualification through the typed runtime."
            ),
            "next_step_if_nonpass": (
                "Freeze the nonpass and redesign the v12.2 runtime under a "
                "new protocol."
            ),
        },
        "source_bindings": source_bindings,
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
