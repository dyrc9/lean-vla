#!/usr/bin/env python3
"""Freeze/check the v12.4b warm-start-complete shadow protocol."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "qualification_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "qualification_20260729_fresh1"
)
PREDECESSOR_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "qualification_protocol.json"
)
PREDECESSOR_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "qualification_terminal_summary.json"
)
PILOT_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "engineering_pilot_20260729"
    / "summary.json"
)
SCHEMA = (
    "proofalign.warmstart-policy-prefix-shadow-v12-"
    "qualification-protocol.v1"
)
PROTOCOL_ID = (
    "proofalign-warmstart-policy-prefix-shadow-v12-"
    "qualification-20260729"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/freeze_warmstart_policy_prefix_shadow_v12_qualification.py",
    "scripts/run_warmstart_policy_prefix_shadow_v12_qualification.py",
    "tests/test_policy_prefix_shadow_warmstart_v12.py",
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


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    return completed.stdout.strip()


def _source_commit() -> str:
    return _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        *SOURCE_PATHS,
    )


def build_protocol() -> dict[str, Any]:
    predecessor_protocol = _load(PREDECESSOR_PROTOCOL_PATH)
    terminal = _load(PREDECESSOR_TERMINAL_PATH)
    pilot = _load(PILOT_PATH)
    if (
        terminal.get("qualification_pass") is not True
        or terminal["lifecycle"]["warmstart_successor_authorized"]
        is not True
        or terminal["limitation"]["outlier_injection"]
        != "joint1_upper"
        or pilot.get("classification")
        != "warmstart_policy_prefix_shadow_v12_engineering_pilot_complete"
        or pilot["metrics"][
            "repeat_trajectory_within_tolerance_rate"
        ]
        != 1.0
        or pilot["metrics"]["qacc_warmstart_restore_identity_rate"]
        != 1.0
        or pilot["execution_boundary"]["outcome_read_count"] != 0
    ):
        raise RuntimeError(
            "v12.4b predecessor or engineering pilot is incomplete"
        )
    gates = dict(predecessor_protocol["gates"])
    gates["repeat_trajectory_within_tolerance_rate_min"] = 1.0
    gates["qacc_warmstart_restore_identity_rate_min"] = 1.0
    return {
        "schema": SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": (
            "authorized_no_outcome_warmstart_shadow_qualification"
        ),
        "created_at": "2026-07-29T23:00:00+08:00",
        "outcome_informed": True,
        "predecessor": {
            "protocol_path": str(
                PREDECESSOR_PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "protocol_sha256": _sha256(
                PREDECESSOR_PROTOCOL_PATH
            ),
            "terminal_path": str(
                PREDECESSOR_TERMINAL_PATH.relative_to(REPO_ROOT)
            ),
            "terminal_sha256": _sha256(
                PREDECESSOR_TERMINAL_PATH
            ),
            "classification": terminal["classification"],
            "qualification_pass": True,
            "unchanged": True,
        },
        "engineering_pilot": {
            "path": str(PILOT_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(PILOT_PATH),
            "case_count": 2,
            "population_overlap": (
                "Intentional result-informed replay of the sole v12.4a "
                "joint1-upper outlier before refreezing the full population."
            ),
            "metrics": pilot["metrics"],
        },
        "mechanism_change": {
            "added_snapshot_field": "sim.data.qacc_warmstart",
            "reason": (
                "MuJoCo iterative contact constraints consume the solver "
                "warm-start vector, which is absent from MjSimState."
            ),
            "controller_snapshot_unchanged": True,
            "decision_thresholds_unchanged": True,
            "trajectory_tolerance_rad_unchanged": True,
        },
        "population": predecessor_protocol["population"],
        "episode": predecessor_protocol["episode"],
        "gates": gates,
        "execution_boundary": predecessor_protocol[
            "execution_boundary"
        ],
        "resource_gate": predecessor_protocol["resource_gate"],
        "lifecycle": {
            "fresh_output_root": str(
                OUTPUT_ROOT.relative_to(REPO_ROOT)
            ),
            "overwrite_allowed": False,
            "next_step_if_pass": (
                "Retain warm-start-complete fixed-prefix mechanics, but "
                "wait for a GPU that passes fresh OpenPI policy loading "
                "before integrated qualification."
            ),
            "next_step_if_nonpass": (
                "Freeze the nonpass and keep the v12.4a 29/30 fidelity "
                "boundary without further outcome rollout."
            ),
            "fresh_policy_qualification_complete": False,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
        },
        "source": {
            "repository_commit": _source_commit(),
            "sha256": {
                relative: _sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            },
        },
        "claim_boundary": (
            "This result-informed v12.4b successor changes only the "
            "controller-shadow snapshot by binding MuJoCo qacc_warmstart, "
            "then reruns the same fixed outcome-known prefix population and "
            "unchanged 0.02-rad tolerance. It reads no outcome, loads no "
            "policy, dispatches no live action, and does not close fresh "
            "policy inference, clean utility, attacked efficacy, deployment, "
            "or physical safety."
        ),
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
