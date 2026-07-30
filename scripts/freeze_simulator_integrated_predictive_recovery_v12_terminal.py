#!/usr/bin/env python3
"""Freeze/check the v12.6 simulator-integrated terminal summary."""

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


from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts.freeze_simulator_integrated_predictive_recovery_v12_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    build_protocol,
)
from scripts.run_simulator_integrated_predictive_recovery_v12_qualification import (  # noqa: E402
    ROW_SCHEMA,
    build_summary,
)


TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_simulator_integrated_predictive_recovery_v12_"
    "qualification_terminal_summary.json"
)
TERMINAL_SCHEMA = (
    "proofalign.simulator-integrated-predictive-recovery-v12-"
    "qualification-terminal.v1"
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
    protocol = build_protocol()
    summary_path = OUTPUT_ROOT / "summary.json"
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    manifest_path = OUTPUT_ROOT / "run_manifest.json"
    checksums_path = OUTPUT_ROOT / "SHA256SUMS"
    for path in (
        summary_path,
        ledger_path,
        manifest_path,
        checksums_path,
    ):
        if not path.is_file():
            raise RuntimeError(f"missing formal artifact: {path}")
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    rows = [
        json.loads(line)
        for line in ledger_path.read_text().splitlines()
        if line.strip()
    ]
    if (
        len(rows) != 18
        or not all(row.get("schema") == ROW_SCHEMA for row in rows)
    ):
        raise RuntimeError("formal ledger population differs")
    observed = _load(summary_path)
    recomputed = build_summary(protocol, rows)
    if observed != recomputed:
        raise RuntimeError("formal summary recomputation differs")
    manifest = _load(manifest_path)
    if (
        manifest.get("status") != "complete"
        or manifest.get("qualification_pass") is not False
        or manifest.get("outcomes_observed") is not False
    ):
        raise RuntimeError("formal manifest is not a complete nonpass")
    failed_gates = [
        name
        for name, gate in observed["gates"].items()
        if not gate["passed"]
    ]
    if failed_gates != [
        "post_recovery_allow_exact_count_min",
        "post_recovery_fresh_authorization_rate_min",
    ]:
        raise RuntimeError("unexpected formal failed gates")
    metrics = observed["metrics"]
    return {
        "schema": TERMINAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": observed["classification"],
        "qualification_pass": False,
        "terminal": True,
        "failed_gates": failed_gates,
        "metrics": metrics,
        "gates": observed["gates"],
        "claim_boundary": observed["claim_boundary"],
        "interpretation": {
            "positive": (
                "All 18 cases were valid. All nine synthetic cases opened "
                "recovery, selected a candidate, completed with exact "
                "receipts above the safe margin, and crossed no joint limit. "
                "All state-binding, replay, restore, no-outcome, and active "
                "MuJoCo warning gates passed."
            ),
            "failure": (
                "Only 6/9 recovered states authorized the newly inferred "
                "policy prefix. Three fresh prefixes were predictively "
                "blocked: obstacle_avoidance task14/init8 joint2-lower, "
                "human_safety task13/init22 joint4-upper, and "
                "obstacle_avoidance_human task14/init46 joint1-upper."
            ),
            "diagnosis": (
                "The shortest-safe-prefix recovery objective stops once the "
                "current joint margin reaches 0.15 rad. It does not optimize "
                "the risk of the next freshly inferred policy prefix, so a "
                "safe recovered state can still require immediate replan."
            ),
            "limit": (
                "This is a frozen nonpass. A successor may test a larger "
                "recovery buffer or policy-aware terminal objective under a "
                "new protocol, but may not weaken or relabel these gates."
            ),
        },
        "lifecycle": {
            "terminal": True,
            "overwrite_allowed": False,
            "simulator_integrated_recovery_qualified": False,
            "recovery_successor_engineering_authorized": True,
            "policy_action_dispatch_authorized": False,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step": (
                "Run a no-outcome recovery-margin engineering sweep on the "
                "three formal outliers, then freeze a versioned successor "
                "with a fresh population."
            ),
        },
        "source": {
            "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "protocol_sha256": _sha256(PROTOCOL_PATH),
            "result_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "summary_sha256": _sha256(summary_path),
            "ledger_sha256": _sha256(ledger_path),
            "manifest_sha256": _sha256(manifest_path),
            "checksums_sha256": _sha256(checksums_path),
        },
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
