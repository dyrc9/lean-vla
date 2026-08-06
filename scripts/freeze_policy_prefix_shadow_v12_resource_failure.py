#!/usr/bin/env python3
"""Freeze/check the fresh-policy pilot resource failure."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FAILED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_prefix_shadow_v12_engineering_pilot_"
    "20260729_resource_failed1"
)
MANIFEST_PATH = FAILED_ROOT / "run_manifest.json"
CHECKSUM_PATH = FAILED_ROOT / "SHA256SUMS"
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_policy_prefix_shadow_v12_resource_failure_terminal.json"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def build_terminal() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text())
    if (
        manifest.get("status") != "terminal_failed_closed"
        or "RESOURCE_EXHAUSTED" not in manifest.get("error", "")
        or manifest.get("outcomes_observed") is not False
        or manifest.get("protocol_id") != "engineering-pilot"
    ):
        raise RuntimeError(
            "fresh-policy pilot is not the expected resource failure"
        )
    return {
        "schema": "proofalign.policy-prefix-shadow-v12-resource-terminal.v1",
        "classification": (
            "policy_prefix_shadow_v12_policy_load_resource_nonstart"
        ),
        "terminal": True,
        "qualification_started": False,
        "policy_inference_count": 0,
        "simulator_case_count": 0,
        "outcome_read_count": 0,
        "live_policy_dispatch_count": 0,
        "failure": {
            "stage": "checkpoint_restore_before_policy_inference",
            "error": manifest["error"],
            "policy_gpu": manifest["policy_gpu"],
            "policy_gpu_memory_used_mib_at_preflight": manifest[
                "preflight"
            ]["selected_policy_gpu"]["memory_used_mib"],
            "policy_gpu_memory_total_mib": manifest["preflight"][
                "selected_policy_gpu"
            ]["memory_total_mib"],
        },
        "source": {
            "manifest_path": str(
                MANIFEST_PATH.relative_to(REPO_ROOT)
            ),
            "manifest_sha256": _sha256(MANIFEST_PATH),
            "checksums_path": str(
                CHECKSUM_PATH.relative_to(REPO_ROOT)
            ),
            "checksums_sha256": _sha256(CHECKSUM_PATH),
        },
        "lifecycle": {
            "fresh_policy_pilot_root_reusable": False,
            "fresh_policy_qualification_authorized": False,
            "fixed_recorded_prefix_shadow_successor_authorized": True,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
        },
        "claim_boundary": (
            "The engineering launch failed closed while restoring the "
            "OpenPI checkpoint because the selected co-tenant GPU lacked "
            "memory. It produced no policy prefix and is not evidence about "
            "predictor accuracy, controller restoration, clean utility, or "
            "efficacy. A separately labeled fixed-recorded-prefix successor "
            "may qualify controller-shadow mechanics without claiming "
            "fresh-policy closure."
        ),
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
