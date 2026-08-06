#!/usr/bin/env python3
"""Freeze/check the v12 no-outcome contract-prequalification terminal."""

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

from scripts.freeze_recoverable_alignment_v12_contract_qualification import (  # noqa: E402
    PROTOCOL_ID,
    PROTOCOL_PATH,
    build_protocol,
)
from scripts.run_recoverable_alignment_v12_contract_qualification import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    _expected_run,
)


TERMINAL_SCHEMA = (
    "proofalign.recoverable-alignment-v12-contract-"
    "qualification-terminal.v1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recoverable_alignment_v12_contract_"
    "qualification_terminal_summary.json"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def build_terminal() -> dict[str, Any]:
    protocol = build_protocol()
    expected, rows = _expected_run()
    result_path = DEFAULT_OUTPUT_ROOT / "qualification.json"
    ledger_path = DEFAULT_OUTPUT_ROOT / "qualification_ledger.jsonl"
    manifest_path = DEFAULT_OUTPUT_ROOT / "run_manifest.json"
    checksums_path = DEFAULT_OUTPUT_ROOT / "SHA256SUMS"
    for path in (
        result_path,
        ledger_path,
        manifest_path,
        checksums_path,
    ):
        if not path.is_file():
            raise RuntimeError(f"missing v12 qualification artifact: {path}")
    observed = json.loads(result_path.read_text())
    if observed != expected:
        raise RuntimeError("v12 qualification result is stale")
    expected_ledger = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in rows
    )
    if ledger_path.read_text() != expected_ledger:
        raise RuntimeError("v12 qualification ledger is stale")
    passed = bool(observed["qualification_pass"])
    return {
        "schema": TERMINAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": observed["classification"],
        "qualification_pass": passed,
        "claim_boundary": observed["claim_boundary"],
        "metrics": {
            "q1_sparse_l1": observed["q1_sparse_l1"],
            "q2_analytic_shadow_contract": observed[
                "q2_analytic_shadow_contract"
            ],
            "q3_recovery_contract": observed["q3_recovery_contract"],
            "gate_conditions": observed["gate_conditions"],
            "row_count": observed["row_count"],
        },
        "execution_boundary": observed["execution_boundary"],
        "lifecycle": {
            "terminal": True,
            "overwrite_allowed": False,
            "v11_terminal_unchanged": True,
            "online_shadow_qualified": False,
            "online_shadow_preflight_authorized": passed,
            "outcome_rollout_authorized": False,
            "next_step": observed["lifecycle"]["next_step"],
        },
        "interpretation": {
            "positive": (
                "The pure sparse-L1, bound shadow-assessment, deterministic "
                "recovery-selection, and typed recovery-transaction "
                "contracts passed every frozen finite-case gate."
            ),
            "limit": (
                "This is analytic contract prequalification only. It does "
                "not establish simulator shadow fidelity, online recovery "
                "availability, clean utility, attacked efficacy, deployment, "
                "or physical safety."
            ),
        },
        "source": {
            "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "protocol_sha256": _sha256(PROTOCOL_PATH),
            "predecessor_terminal": protocol["predecessor_terminal"],
            "result_root": str(DEFAULT_OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "qualification_sha256": _sha256(result_path),
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
            f"refusing to overwrite terminal summary: {TERMINAL_PATH}"
        )
    TERMINAL_PATH.write_text(expected)
    print(f"wrote: {TERMINAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
