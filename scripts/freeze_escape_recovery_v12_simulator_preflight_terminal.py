#!/usr/bin/env python3
"""Freeze/check the v12.1 no-outcome simulator-preflight terminal."""

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

from scripts.freeze_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    build_protocol,
)
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    ROW_SCHEMA,
    _summarize,
)


TERMINAL_SCHEMA = (
    "proofalign.escape-recovery-v12-simulator-preflight-terminal.v1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_escape_recovery_v12_simulator_"
    "preflight_terminal_summary.json"
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
    rows = [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not all(
        isinstance(row, dict) and row.get("schema") == ROW_SCHEMA
        for row in rows
    ):
        raise RuntimeError("unexpected v12.1 preflight ledger row")
    return rows


def _verify_checksums(
    checksums_path: Path,
    expected_paths: tuple[Path, ...],
) -> None:
    expected = "".join(
        f"{_sha256(path)}  {path.name}\n"
        for path in sorted(expected_paths)
    )
    if checksums_path.read_text() != expected:
        raise RuntimeError("v12.1 preflight checksums are stale")


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
            raise RuntimeError(f"missing v12.1 preflight artifact: {path}")
    _verify_checksums(
        checksums_path,
        (ledger_path, manifest_path, summary_path),
    )
    rows = _load_rows(ledger_path)
    expected_ids = [
        row["base_pair_id"] for row in protocol["population"]["pairs"]
    ]
    observed_ids = [row["base_pair_id"] for row in rows]
    if observed_ids != expected_ids:
        raise RuntimeError("v12.1 preflight ledger population differs")
    observed = _load(summary_path)
    recomputed = _summarize(
        protocol,
        rows,
        selected_gpu=observed["selected_gpu"],
    )
    if observed != recomputed:
        raise RuntimeError("v12.1 preflight summary is stale")
    manifest = _load(manifest_path)
    if manifest != {
        "schema": observed["schema"] + ".run-manifest",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "status": "complete",
        "row_count": len(rows),
        "outcomes_observed": False,
        "policy_loaded": False,
        "policy_action_dispatched": False,
    }:
        raise RuntimeError("v12.1 preflight manifest is stale")
    selected_counts: dict[str, int] = {}
    for row in rows:
        candidate_id = row["selected_candidate_id"]
        if candidate_id is not None:
            selected_counts[candidate_id] = (
                selected_counts.get(candidate_id, 0) + 1
            )
    passed = bool(observed["qualification_pass"])
    return {
        "schema": TERMINAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": observed["classification"],
        "qualification_pass": passed,
        "claim_boundary": observed["claim_boundary"],
        "metrics": observed["metrics"],
        "gate_conditions": observed["gate_conditions"],
        "selected_candidate_counts": selected_counts,
        "execution_boundary": observed["execution_boundary"],
        "lifecycle": {
            "terminal": True,
            "overwrite_allowed": False,
            "v11_terminal_unchanged": True,
            "contract_terminal_unchanged": True,
            "runtime_integration_work_authorized": passed,
            "runtime_transaction_qualified": False,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step": observed["lifecycle"]["next_step"],
        },
        "interpretation": {
            "positive": (
                "Across 45 frozen simulator-reset pairs, the frozen "
                "candidate library selected a recovery in every pair; each "
                "selected replay ended outside the model joint-limit region "
                "without crossing a hard joint limit, and revoked policy "
                "authorization was never accepted."
            ),
            "limits": [
                (
                    "All 45 selections used negative_ry, so this result does "
                    "not establish candidate diversity or arbitrary-joint "
                    "recovery."
                ),
                (
                    "Only 2/45 selected replays were bitwise identical to "
                    "their shadow trajectory. All 45 replays still cleared "
                    "the model trigger, but transaction-level tolerance and "
                    "fidelity require a separate frozen qualification."
                ),
                (
                    "The run emitted a MuJoCo ncon=5000 contact-capacity "
                    "warning. It caused no recorded runtime exception, but "
                    "remains a simulator diagnostic limitation."
                ),
                (
                    "No policy was loaded or dispatched and no task outcome "
                    "was read; clean utility, attacked efficacy, deployment, "
                    "and physical safety remain unqualified."
                ),
            ],
        },
        "source": {
            "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "protocol_sha256": _sha256(PROTOCOL_PATH),
            "predecessor": protocol["predecessor"],
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
            f"refusing to overwrite terminal summary: {TERMINAL_PATH}"
        )
    TERMINAL_PATH.write_text(expected)
    print(f"wrote: {TERMINAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
