#!/usr/bin/env python3
"""Freeze/check the v12.2 recovery-runtime fixed-trace terminal."""

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

from scripts.freeze_recovery_runtime_v12_fixed_trace import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    build_protocol,
)
from scripts.run_recovery_runtime_v12_fixed_trace import (  # noqa: E402
    _expected_run,
)


TERMINAL_SCHEMA = (
    "proofalign.recovery-runtime-v12-fixed-trace-terminal.v1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recovery_runtime_v12_fixed_trace_"
    "terminal_summary.json"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _verify_checksums(
    path: Path, files: tuple[Path, ...]
) -> None:
    expected = "".join(
        f"{_sha256(item)}  {item.name}\n"
        for item in sorted(files)
    )
    if path.read_text() != expected:
        raise RuntimeError("v12.2 fixed-trace checksums are stale")


def build_terminal() -> dict[str, Any]:
    protocol = build_protocol()
    result_path = OUTPUT_ROOT / "result.json"
    ledger_path = OUTPUT_ROOT / "ledger.jsonl"
    manifest_path = OUTPUT_ROOT / "run_manifest.json"
    checksums_path = OUTPUT_ROOT / "SHA256SUMS"
    for path in (
        result_path,
        ledger_path,
        manifest_path,
        checksums_path,
    ):
        if not path.is_file():
            raise RuntimeError(f"missing fixed-trace artifact: {path}")
    _verify_checksums(
        checksums_path,
        (ledger_path, manifest_path, result_path),
    )
    expected_result, expected_rows = _expected_run()
    observed_result = json.loads(result_path.read_text())
    if observed_result != expected_result:
        raise RuntimeError("v12.2 fixed-trace result is stale")
    expected_ledger = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in expected_rows
    )
    if ledger_path.read_text() != expected_ledger:
        raise RuntimeError("v12.2 fixed-trace ledger is stale")
    passed = bool(observed_result["qualification_pass"])
    return {
        "schema": TERMINAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": observed_result["classification"],
        "qualification_pass": passed,
        "claim_boundary": observed_result["claim_boundary"],
        "metrics": observed_result["metrics"],
        "gate_conditions": observed_result["gate_conditions"],
        "execution_boundary": observed_result["execution_boundary"],
        "lifecycle": {
            "terminal": True,
            "overwrite_allowed": False,
            "predecessor_unchanged": True,
            "multi_joint_simulator_preflight_authorized": passed,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step": observed_result["lifecycle"]["next_step"],
        },
        "interpretation": {
            "positive": (
                "All ten frozen typed-runtime traces matched their expected "
                "classification, including exact ordered recovery receipts, "
                "replay/substitution rejection, old-policy revocation, fresh "
                "observation epoch, and fresh-policy state binding."
            ),
            "limit": (
                "This used an in-memory recovery sink. It qualifies the "
                "transaction boundary only, not simulator dynamics, recovery "
                "coverage, task utility, attacked efficacy, deployment, or "
                "physical safety."
            ),
        },
        "source": {
            "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "protocol_sha256": _sha256(PROTOCOL_PATH),
            "predecessor": protocol["predecessor"],
            "result_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "result_sha256": _sha256(result_path),
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
