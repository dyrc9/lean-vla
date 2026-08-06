#!/usr/bin/env python3
"""Freeze the observation-plumbing-only v13 fresh3 full repeat."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import freeze_predictive_virtual_brake_v13_clean as predecessor  # noqa: E402
from scripts.run_predictive_virtual_brake_v13_clean_fresh3 import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


FRESH2_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "fresh2_protocol.json"
)
FRESH2_FAILURE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_"
    "fresh2_runner_failure.json"
)
FRESH2_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "20260731_fresh2"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "fresh3_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v13_clean_fresh3.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_receding_horizon_recovery_pilot_v12.py",
    "scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v13.py",
    "scripts/run_predictive_virtual_brake_v13_clean.py",
    "scripts/run_l2_predictive_virtual_brake_v13_fresh3.py",
    "scripts/run_predictive_virtual_brake_v13_clean_fresh3.py",
    "scripts/freeze_predictive_virtual_brake_v13_clean_fresh3.py",
    "tests/test_h3_hard_virtual_joint_guard_beam_pilot_v12.py",
    "tests/test_l2_predictive_virtual_brake_v13.py",
    "tests/test_predictive_virtual_brake_v13_clean.py",
    "tests/test_predictive_virtual_brake_v13_fresh3.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v13-clean-outcome-fresh3-"
    "20260731"
)
CREATED_AT = "2026-07-31T12:10:00+08:00"


class PredictiveVirtualBrakeFresh3FreezeError(RuntimeError):
    """Raised when the fresh3 repeat cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeFresh3FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    base = predecessor.build_protocol(
        created_at=created_at,
        source_commit=source_commit,
    )
    fresh2_protocol = load_json_object(FRESH2_PROTOCOL_PATH)
    failure = load_json_object(FRESH2_FAILURE_PATH)
    if (
        failure.get("classification")
        != (
            "predictive_virtual_brake_v13_fresh2_"
            "partial_outcome_runner_failure"
        )
        or failure["terminal_state"]["completed_episode_count"] != 70
        or failure["terminal_state"]["failed_sequence_index"] != 70
        or failure["scientific_status"]["clean_gate_estimable"]
        is not False
        or failure["scientific_status"]["attacked_stage_authorized"]
        is not False
        or failure["scientific_status"][
            "partial_outcomes_used_to_change_workloads_seeds_guard_"
            "thresholds_or_gates"
        ]
        is not False
        or base["workloads"] != fresh2_protocol["workloads"]
        or base["schedule"] != fresh2_protocol["schedule"]
        or base["design"] != fresh2_protocol["design"]
        or base["analysis"] != fresh2_protocol["analysis"]
        or base["v13_gates"] != fresh2_protocol["v13_gates"]
    ):
        raise PredictiveVirtualBrakeFresh3FreezeError(
            "fresh2 failure or unchanged-design binding differs"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    required_bindings = list(base["required_bindings"])
    required_bindings.extend(
        (
            predecessor._binding(FRESH2_PROTOCOL_PATH),
            predecessor._binding(
                FRESH2_FAILURE_PATH,
                classification=(
                    "predictive_virtual_brake_v13_fresh2_"
                    "partial_outcome_runner_failure"
                ),
            ),
            predecessor._binding(FRESH2_ROOT / "run_manifest.json"),
            predecessor._binding(FRESH2_ROOT / "SHA256SUMS"),
        )
    )
    protocol = {
        **base,
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": AUTHORIZED_STATUS,
        "created_at": created_at,
        # Keep the frozen fresh2 stage so every schedule identity, ordering,
        # arm rotation, workload, and seed remains byte-for-byte unchanged.
        "stage": fresh2_protocol["stage"],
        "complete_classification": (
            "predictive_virtual_brake_v13_clean_outcome_fresh3_"
            "complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v13_clean_outcome_fresh3_"
            "nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v13_"
            "clean_20260731_fresh3"
        ),
        "required_bindings": required_bindings,
        "selection": {
            **base["selection"],
            "fresh2_partial_outcomes_observed": True,
            "fresh2_completed_episode_count": 70,
            "fresh3_workload_or_seed_reselected": False,
            "fresh3_scientific_design_changed": False,
        },
        "retry_disclosure": {
            "fresh1_failure": "pre_outcome_missing_jax",
            "fresh2_failure": (
                "partial_outcome_deadlock_observation_plumbing"
            ),
            "fresh2_completed_episode_count": 70,
            "fresh2_failed_sequence_index": 70,
            "fresh3_change": (
                "return the discarded shadow transition observation only "
                "on the terminal done=True deadlock transition; no policy "
                "consumes it and no further action is dispatched"
            ),
            "workloads_changed": False,
            "seeds_changed": False,
            "guard_changed": False,
            "thresholds_changed": False,
            "estimands_changed": False,
            "gates_changed": False,
            "confirmatory_claim_authorized": False,
        },
        "stop_rule": {
            **base["stop_rule"],
            "fresh3_is_full_180_episode_repeat": True,
            "fresh2_partial_artifacts_reused": False,
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            },
            "freezer": SELF_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        },
        "outcomes_observed_for_selection": True,
        "outcome_conditioned_engineering_regression": True,
        "claim_boundary": (
            "Fresh3 is a full engineering repeat after 70 fresh2 task "
            "outcomes were observed. Those outcomes did not change any "
            "workload, seed, guard parameter, threshold, estimand, gate, "
            "schedule order, or arm rotation. The only change supplies a "
            "correctly shaped discarded-shadow observation on a terminal "
            "fail-closed transition; done=True prevents policy consumption "
            "or further dispatch. Fresh3 can estimate the preregistered "
            "clean utility gate as outcome-informed engineering evidence, "
            "not as an independent confirmatory result. All target-joint, "
            "simulator-only, attacked-efficacy, deployment, and hardware "
            "limitations from fresh2 remain."
        ),
    }
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    text = canonical_text(
        build_protocol(
            created_at=(
                str(retained["created_at"])
                if retained is not None
                else args.created_at
            ),
            source_commit=(
                str(retained["source"]["repository_commit"])
                if retained is not None
                else None
            ),
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PredictiveVirtualBrakeFresh3FreezeError(
                f"v13 fresh3 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
