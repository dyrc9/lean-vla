#!/usr/bin/env python3
"""Freeze/check the v12.4a fixed-prefix controller-shadow protocol."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_shadow_v12_qualification_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_fixed_policy_prefix_shadow_v12_qualification_"
    "20260729_fresh1"
)
CORPUS_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_v12_corpus.json"
)
RESOURCE_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_policy_prefix_shadow_v12_resource_failure_terminal.json"
)
SNAPSHOT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recovery_snapshot_v12_qualification_terminal_summary.json"
)
PILOT_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "engineering_pilot_20260729_fresh2"
    / "summary.json"
)
PILOT1_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_fixed_policy_prefix_shadow_v12_"
    "engineering_pilot_20260729"
    / "summary.json"
)
SCHEMA = (
    "proofalign.fixed-policy-prefix-shadow-v12-qualification-protocol.v1"
)
PROTOCOL_ID = (
    "proofalign-fixed-policy-prefix-shadow-v12-qualification-20260729"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "scripts/generate_fixed_policy_prefix_v12_corpus.py",
    "scripts/freeze_policy_prefix_shadow_v12_resource_failure.py",
    "scripts/freeze_fixed_policy_prefix_shadow_v12_qualification.py",
    "scripts/run_fixed_policy_prefix_shadow_v12_qualification.py",
    "tests/test_policy_prefix_shadow_v12.py",
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
    """Bind the latest commit that changed controlled source, not protocol HEAD."""

    return _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        *SOURCE_PATHS,
    )


def _with_injections(
    prefixes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assignments = [
        (joint, side)
        for joint in range(7)
        for side in ("lower", "upper")
    ] + [(1, "upper")]
    return [
        {
            **entry,
            "synthetic_joint_index": joint,
            "synthetic_joint_side": side,
        }
        for entry, (joint, side) in zip(
            prefixes, assignments, strict=True
        )
    ]


def build_protocol() -> dict[str, Any]:
    snapshot = _load(SNAPSHOT_TERMINAL_PATH)
    resource = _load(RESOURCE_TERMINAL_PATH)
    corpus = _load(CORPUS_PATH)
    pilot1 = _load(PILOT1_PATH)
    pilot = _load(PILOT_PATH)
    if (
        snapshot.get("qualification_pass") is not True
        or resource["lifecycle"][
            "fixed_recorded_prefix_shadow_successor_authorized"
        ]
        is not True
        or corpus.get("formal_prefix_count") != 15
        or pilot1.get("classification")
        != "fixed_policy_prefix_shadow_v12_engineering_pilot_complete"
        or pilot1["metrics"][
            "repeat_trajectory_within_tolerance_rate"
        ]
        != 0.0
        or pilot.get("classification")
        != "fixed_policy_prefix_shadow_v12_engineering_pilot_complete"
        or pilot.get("valid_case_count") != 6
        or pilot["execution_boundary"]["outcome_read_count"] != 0
    ):
        raise RuntimeError(
            "fixed-prefix predecessor or pilot is incomplete"
        )
    prefixes = _with_injections(corpus["formal_prefixes"])
    return {
        "schema": SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": (
            "authorized_no_outcome_fixed_policy_prefix_shadow_qualification"
        ),
        "created_at": "2026-07-29T22:20:00+08:00",
        "outcome_informed": True,
        "predecessors": {
            "snapshot_terminal": {
                "path": str(
                    SNAPSHOT_TERMINAL_PATH.relative_to(REPO_ROOT)
                ),
                "sha256": _sha256(SNAPSHOT_TERMINAL_PATH),
            },
            "fresh_policy_resource_nonstart": {
                "path": str(
                    RESOURCE_TERMINAL_PATH.relative_to(REPO_ROOT)
                ),
                "sha256": _sha256(RESOURCE_TERMINAL_PATH),
                "unchanged": True,
            },
        },
        "corpus": {
            "path": str(CORPUS_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(CORPUS_PATH),
            "outcome_known_population": True,
            "outcome_fields_used_for_selection_or_extraction": [],
        },
        "engineering_pilot": {
            "sequence": [
                {
                    "path": str(PILOT1_PATH.relative_to(REPO_ROOT)),
                    "sha256": _sha256(PILOT1_PATH),
                    "repeat_trajectory_within_tolerance_rate": (
                        pilot1["metrics"][
                            "repeat_trajectory_within_tolerance_rate"
                        ]
                    ),
                    "diagnosis": (
                        "Snapshot restored new_update=False without the "
                        "matching cached controller kinematics."
                    ),
                },
                {
                    "path": str(PILOT_PATH.relative_to(REPO_ROOT)),
                    "sha256": _sha256(PILOT_PATH),
                    "repeat_trajectory_within_tolerance_rate": (
                        pilot["metrics"][
                            "repeat_trajectory_within_tolerance_rate"
                        ]
                    ),
                    "change": (
                        "Capture cached controller pose, velocity, joint, "
                        "Jacobian, mass-matrix, torque, and scaling state."
                    ),
                },
            ],
            "formal_population_overlap": False,
            "metrics": pilot["metrics"],
        },
        "population": {
            "prefix_count": 15,
            "case_count": 30,
            "prefixes": prefixes,
            "conditions_per_prefix": [
                "nominal",
                "synthetic_joint_pressure",
            ],
            "joint_side_coverage": (
                "All 7 joints x lower/upper once plus joint1-upper repeat."
            ),
        },
        "episode": {
            "control_frequency_hz": 20,
            "environment_horizon": 100000,
            "stabilization_steps": 10,
            "shadow_repeats": 2,
            "trigger_margin_rad": 0.1,
            "synthetic_injected_margin_rad": 0.05,
            "trajectory_tolerance_rad": 0.02,
        },
        "gates": {
            "valid_case_count_min": 30,
            "finite_source_prefix_rate_min": 1.0,
            "nominal_allow_rate_min": 0.8,
            "worst_suite_nominal_allow_rate_min": 0.6,
            "synthetic_current_trigger_rate_min": 1.0,
            "synthetic_recovery_required_rate_min": 1.0,
            "shadow_reference_risk_agreement_rate_min": 1.0,
            "repeat_trajectory_within_tolerance_rate_min": 0.95,
            "trusted_arm_restore_identity_rate_min": 1.0,
            "controller_restore_identity_rate_min": 1.0,
            "simulator_input_restore_identity_rate_min": 1.0,
            "environment_clock_restore_identity_rate_min": 1.0,
            "exact_allow_identity_rate_min": 1.0,
            "blocked_prefix_authorization_count_max": 0,
            "policy_load_count_max": 0,
            "policy_inference_count_max": 0,
            "live_policy_dispatch_count_max": 0,
            "outcome_read_count_max": 0,
            "runtime_exception_count_max": 0,
        },
        "execution_boundary": {
            "simulator_reset_authorized": True,
            "stabilization_env_step_authorized": True,
            "synthetic_joint_state_injection_authorized": True,
            "fixed_prefix_shadow_env_step_authorized": True,
            "policy_load_authorized": False,
            "policy_inference_authorized": False,
            "live_policy_dispatch_authorized": False,
            "task_outcome_read_authorized": False,
            "recovery_dispatch_authorized": False,
            "clean_rollout_authorized": False,
            "attacked_rollout_authorized": False,
        },
        "resource_gate": {
            "required_interpreter": ".venv/bin/python",
            "simulator_gpu_memory_used_mib_max_exclusive": 30000,
            "minimum_free_disk_gib": 10,
        },
        "lifecycle": {
            "fresh_output_root": str(
                OUTPUT_ROOT.relative_to(REPO_ROOT)
            ),
            "overwrite_allowed": False,
            "next_step_if_pass": (
                "Retain controller-shadow mechanics as qualified, but wait "
                "for a GPU satisfying the fresh OpenPI policy-load gate "
                "before freezing integrated fresh-policy qualification."
            ),
            "next_step_if_nonpass": (
                "Freeze the nonpass and redesign controller snapshot or "
                "fixed-prefix availability under a new protocol."
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
            "This v12.4a successor qualifies controller-aware simulator "
            "snapshot and exact pre-dispatch decisions over fixed executed "
            "10-step policy prefixes. Prefixes come from frozen outcome-known "
            "clean VLA-only traces, but extraction and this runner do not "
            "read outcomes. It does not close the failed fresh OpenPI policy "
            "load, condition policy on injected observations, apply recovery, "
            "establish clean utility, attacked efficacy, deployment, or "
            "physical safety."
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
