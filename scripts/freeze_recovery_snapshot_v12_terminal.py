#!/usr/bin/env python3
"""Freeze/check the v12.3 recovery snapshot terminal."""

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

from scripts.freeze_recovery_snapshot_v12_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    build_protocol,
)
from scripts.run_recovery_snapshot_v12_qualification import (  # noqa: E402
    ROW_SCHEMA,
    _summarize,
)


TERMINAL_SCHEMA = (
    "proofalign.recovery-snapshot-v12-qualification-terminal.v1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recovery_snapshot_v12_"
    "qualification_terminal_summary.json"
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


def _verify_checksums(
    path: Path, files: tuple[Path, ...]
) -> None:
    expected = "".join(
        f"{_sha256(item)}  {item.name}\n"
        for item in sorted(files)
    )
    if path.read_text() != expected:
        raise RuntimeError("v12.3 snapshot checksums are stale")


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
            raise RuntimeError(f"missing v12.3 artifact: {path}")
    _verify_checksums(
        checksums_path,
        (ledger_path, manifest_path, summary_path),
    )
    rows = [
        json.loads(line)
        for line in ledger_path.read_text().splitlines()
        if line.strip()
    ]
    if not all(row.get("schema") == ROW_SCHEMA for row in rows):
        raise RuntimeError("unexpected v12.3 ledger row")
    expected_ids = [
        case["case_id"] for case in protocol["population"]["cases"]
    ]
    if [row["case_id"] for row in rows] != expected_ids:
        raise RuntimeError("v12.3 ledger population differs")
    observed = _load(summary_path)
    recomputed = _summarize(
        protocol,
        rows,
        selected_gpu=observed["selected_gpu"],
    )
    if observed != recomputed:
        raise RuntimeError("v12.3 summary is stale")
    passed = bool(observed["qualification_pass"])
    return {
        "schema": TERMINAL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": observed["classification"],
        "qualification_pass": passed,
        "claim_boundary": observed["claim_boundary"],
        "metrics": observed["metrics"],
        "predecessor_positive_metrics": observed[
            "predecessor_positive_metrics"
        ],
        "gate_conditions": observed["gate_conditions"],
        "execution_boundary": observed["execution_boundary"],
        "lifecycle": {
            "terminal": True,
            "overwrite_allowed": False,
            "v12_2_nonpass_unchanged": True,
            "policy_prefix_shadow_qualification_authorized": passed,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step": observed["lifecycle"]["next_step"],
        },
        "interpretation": {
            "positive": (
                "Across all 210 frozen cases, trigger-state MjSimState and "
                "trusted arm qpos/qvel restored with bitwise identity. "
                "Qualification-harness trusted arm qpos/qvel also restored "
                "with bitwise identity."
            ),
            "diagnostic": (
                "Harness full-state bitwise identity remained 201/210. The "
                "nine first-case differences affected 40 non-arm values with "
                "maximum absolute error 2.220446049250313e-16, while trusted "
                "arm identity remained 210/210."
            ),
            "limit": (
                "This result-informed pass does not relabel the v12.2 "
                "nonpass and does not qualify controller-internal snapshots "
                "for nominal policy-prefix prediction, clean utility, "
                "attacked efficacy, deployment, or physical safety."
            ),
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
            f"refusing to overwrite terminal: {TERMINAL_PATH}"
        )
    TERMINAL_PATH.write_text(expected)
    print(f"wrote: {TERMINAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
