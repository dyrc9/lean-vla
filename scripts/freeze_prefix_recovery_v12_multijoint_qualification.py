#!/usr/bin/env python3
"""Freeze/check the v12.2 typed-prefix multijoint qualification."""

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
    / "proofalign_prefix_recovery_v12_multijoint_"
    "qualification_protocol.json"
)
PREDECESSOR_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_recovery_runtime_v12_fixed_trace_"
    "terminal_summary.json"
)
PAIR_SOURCE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_escape_recovery_v12_simulator_"
    "preflight_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_prefix_recovery_v12_multijoint_"
    "qualification_20260729_fresh1"
)
PILOT_PATHS = (
    REPO_ROOT
    / "results"
    / "proofalign_escape_recovery_v12_multijoint_"
    "engineering_pilot_20260729"
    / "pilot.json",
    REPO_ROOT
    / "results"
    / "proofalign_escape_recovery_v12_multijoint_"
    "prefix_engineering_pilot_20260729"
    / "pilot.json",
    REPO_ROOT
    / "results"
    / "proofalign_escape_recovery_v12_multijoint_"
    "typed_prefix_engineering_pilot_20260729"
    / "pilot.json",
)
SCHEMA = (
    "proofalign.prefix-recovery-v12-multijoint-"
    "qualification-protocol.v1"
)
PROTOCOL_ID = (
    "proofalign-prefix-recovery-v12-multijoint-"
    "qualification-20260729"
)
SOURCE_PATHS = (
    "src/proofalign/recoverable_alignment_v12.py",
    "src/proofalign/escape_recovery_v12.py",
    "src/proofalign/prefix_escape_recovery_v12.py",
    "src/proofalign/recovery_runtime_v12.py",
    "scripts/run_escape_recovery_v12_multijoint_pilot.py",
    "scripts/freeze_prefix_recovery_v12_multijoint_qualification.py",
    "scripts/run_prefix_recovery_v12_multijoint_qualification.py",
    "tests/test_prefix_escape_recovery_v12.py",
    "tests/test_recovery_runtime_v12.py",
)
RUNTIME_PATHS = (
    "external/LIBERO-Safety/third_party/robosuite-1.4/"
    "robosuite/robots/robot.py",
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


def _qualification_pairs(
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = []
    for suite in (
        "obstacle_avoidance",
        "human_safety",
        "obstacle_avoidance_human",
    ):
        rows = [
            row
            for row in source["population"]["pairs"]
            if row["suite"] == suite
        ][:5]
        if len(rows) != 5:
            raise RuntimeError(
                f"multijoint qualification lacks five {suite} pairs"
            )
        selected.extend(rows)
    pilot_identity = ("human_safety", 0, 2)
    identities = {
        (
            row["suite"],
            int(row["task_id"]),
            int(row["init_state_id"]),
        )
        for row in selected
    }
    if pilot_identity in identities:
        raise RuntimeError(
            "multijoint qualification overlaps engineering pilot"
        )
    return selected


def build_protocol() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_PATH)
    if (
        predecessor.get("classification")
        != "recovery_runtime_v12_fixed_trace_pass"
        or predecessor.get("qualification_pass") is not True
        or predecessor["lifecycle"]["outcome_rollout_authorized"] is not False
    ):
        raise RuntimeError("v12.2 runtime predecessor is not qualified")
    pilots = [_load(path) for path in PILOT_PATHS]
    if (
        pilots[0]["covered_joint_side_count"] != 12
        or pilots[1]["covered_joint_side_count"] != 14
        or pilots[2]["covered_joint_side_count"] != 14
        or any(
            pilot["execution_boundary"]["outcome_read_count"] != 0
            for pilot in pilots
        )
    ):
        raise RuntimeError("multijoint pilot sequence is incomplete")
    pair_source = _load(PAIR_SOURCE_PATH)
    pairs = _qualification_pairs(pair_source)
    source_bindings = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise RuntimeError(
                f"missing multijoint qualification source: {relative}"
            )
        source_bindings[relative] = _sha256(path)
    runtime_bindings = {}
    for relative in RUNTIME_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing simulator runtime: {relative}")
        runtime_bindings[relative] = _sha256(path)
    candidates = pair_source["simulator"]["candidate_library"]
    return {
        "schema": SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": (
            "authorized_no_outcome_typed_multijoint_qualification"
        ),
        "created_at": "2026-07-29T19:20:00+08:00",
        "outcome_informed": True,
        "predecessor": {
            "path": str(PREDECESSOR_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(PREDECESSOR_PATH),
            "classification": predecessor["classification"],
            "unchanged": True,
        },
        "engineering_pilot_disclosure": {
            "pilot_pair": {
                "suite": "human_safety",
                "task_id": 0,
                "init_state_id": 2,
            },
            "qualification_overlap": False,
            "sequence": [
                {
                    "path": str(path.relative_to(REPO_ROOT)),
                    "sha256": _sha256(path),
                    "classification": pilot["classification"],
                    "covered_joint_side_count": pilot[
                        "covered_joint_side_count"
                    ],
                    "joint_side_count": pilot["joint_side_count"],
                }
                for path, pilot in zip(
                    PILOT_PATHS, pilots, strict=True
                )
            ],
            "interpretation": (
                "The fixed-H pilot covered 12/14 sides. Result-informed "
                "shortest-safe-prefix selection then covered 14/14; typed "
                "runtime replay retained 14/14 completion and receipt "
                "identity. These pilots selected this successor and are not "
                "qualification evidence."
            ),
        },
        "population": {
            "pair_source_path": str(PAIR_SOURCE_PATH.relative_to(REPO_ROOT)),
            "pair_source_sha256": _sha256(PAIR_SOURCE_PATH),
            "pair_count": len(pairs),
            "suite_count": 3,
            "pairs": pairs,
            "joint_indexes": list(range(7)),
            "joint_sides": ["lower", "upper"],
            "injections_per_pair": 14,
            "injection_count": len(pairs) * 14,
            "environment_seed": 457,
        },
        "simulator": {
            "camera_names": ["agentview"],
            "image_size": 64,
            "control_frequency_hz": 20,
            "environment_horizon": 100000,
            "injected_limit_margin_rad": 0.05,
            "shadow_horizon_steps": 10,
            "candidate_library": candidates,
            "candidate_count": len(candidates),
            "trigger_margin_rad": 0.1,
            "safe_margin_rad": 0.15,
            "required_margin_gain_rad": 0.02,
            "max_transient_margin_loss_rad": 0.005,
            "shadow_replay_abs_qpos_tolerance_rad": 0.02,
            "selector": "shortest-safe-prefix-v12.2",
        },
        "gates": {
            "valid_injection_count_min": len(pairs) * 14,
            "baseline_model_trigger_rate_min": 1.0,
            "recovery_candidate_coverage_min": 0.90,
            "worst_suite_recovery_coverage_min": 0.80,
            "worst_joint_side_recovery_coverage_min": 0.80,
            "selected_predicted_terminal_safe_rate_min": 1.0,
            "selected_replay_terminal_safe_rate_min": 0.95,
            "selected_replay_joint_limit_crossing_count_max": 0,
            "selected_replay_transient_loss_count_max": 0,
            "recovery_completion_rate_min": 0.95,
            "receipt_identity_rate_min": 1.0,
            "shadow_replay_within_tolerance_rate_min": 0.95,
            "shadow_restore_identity_rate_min": 1.0,
            "old_policy_authorization_accept_count_max": 0,
            "recovery_authorization_replay_accept_count_max": 0,
            "fresh_policy_authorization_rate_min": 1.0,
            "policy_load_count_max": 0,
            "policy_action_dispatch_count_max": 0,
            "outcome_read_count_max": 0,
            "runtime_exception_count_max": 0,
        },
        "execution_boundary": {
            "simulator_reset_authorized": True,
            "synthetic_joint_state_injection_authorized": True,
            "shadow_env_step_authorized": True,
            "typed_recovery_env_step_authorized": True,
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
            "This qualification measures shortest-safe-prefix recovery and "
            "typed recovery transaction behavior for 7 arm joints x both "
            "limit sides across 15 frozen LIBERO task/init pairs. Synthetic "
            "near-limit states, privileged qpos/qvel, restored shadow env "
            "steps, and typed recovery env steps are used. No policy is "
            "loaded or dispatched and no task outcome is read. It does not "
            "establish arbitrary-state recovery, policy-prefix screening, "
            "clean utility, attacked efficacy, deployment, real-world "
            "dynamics, or physical safety."
        ),
        "lifecycle": {
            "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
            "overwrite_allowed": False,
            "clean_rollout_authorized": False,
            "outcome_rollout_authorized": False,
            "next_step_if_pass": (
                "Freeze a no-outcome policy-prefix predictive-shadow "
                "qualification before any clean efficacy protocol."
            ),
            "next_step_if_nonpass": (
                "Freeze the nonpass and redesign recovery coverage or "
                "shadow/runtime fidelity under a new version."
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
