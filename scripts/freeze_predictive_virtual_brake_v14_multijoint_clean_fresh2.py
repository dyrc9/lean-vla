#!/usr/bin/env python3
"""Freeze the v14 all-joint clean Fresh2 full development repeat."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from scripts.run_predictive_virtual_brake_v14_multijoint_clean_fresh2 import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


DEVELOPMENT1_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_protocol.json"
)
DEVELOPMENT1_FAILURE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "development1_runner_failure.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v14_multijoint_clean_fresh2.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_receding_horizon_recovery_pilot_v12.py",
    "scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v13.py",
    "scripts/run_l2_predictive_virtual_brake_v13_fresh3.py",
    "scripts/run_predictive_virtual_brake_v13_clean.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_predictive_virtual_brake_v14_multijoint_clean.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint_fresh2.py",
    "scripts/run_predictive_virtual_brake_v14_multijoint_clean_fresh2.py",
    (
        "scripts/freeze_predictive_virtual_brake_v14_multijoint_"
        "development1_failure.py"
    ),
    (
        "scripts/freeze_predictive_virtual_brake_v14_multijoint_"
        "clean_fresh2.py"
    ),
    "tests/test_l2_predictive_virtual_brake_v14_multijoint.py",
    "tests/test_predictive_virtual_brake_v14_multijoint_clean.py",
    (
        "tests/test_predictive_virtual_brake_v14_multijoint_"
        "fresh2.py"
    ),
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v14-multijoint-"
    "clean-development-fresh2-20260731"
)
CREATED_AT = "2026-07-31T16:25:00+08:00"
FAILURE_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_development1_"
    "partial_outcome_runner_failure"
)


class PredictiveVirtualBrakeV14Fresh2FreezeError(RuntimeError):
    """Raised when the Fresh2 repeat cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeV14Fresh2FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(
    path: Path,
    *,
    classification: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise PredictiveVirtualBrakeV14Fresh2FreezeError(
            f"required Fresh2 binding is absent: {path}"
        )
    row: dict[str, Any] = {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }
    if classification is not None:
        row["classification"] = classification
    return row


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise PredictiveVirtualBrakeV14Fresh2FreezeError(
            "tracked worktree must be clean before v14 Fresh2 freeze"
        )
    development1 = load_json_object(DEVELOPMENT1_PROTOCOL_PATH)
    failure = load_json_object(DEVELOPMENT1_FAILURE_PATH)
    if (
        failure.get("classification") != FAILURE_CLASSIFICATION
        or failure["terminal_state"]["completed_episode_count"] != 2
        or failure["terminal_state"]["failed_sequence_index"] != 2
        or failure["terminal_state"]["failed_arm"] != "vla_only"
        or failure["scientific_status"]["coverage_estimable"] is not False
        or failure["scientific_status"]["task_utility_estimable"]
        is not False
        or failure["scientific_status"][
            "fresh_successor_must_repeat_all_180_episodes"
        ]
        is not True
        or len(development1["schedule"]) != 180
    ):
        raise PredictiveVirtualBrakeV14Fresh2FreezeError(
            "development1 failure disclosure differs"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = deepcopy(development1)
    protocol.update(
        {
            "schema": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": AUTHORIZED_STATUS,
            "created_at": created_at,
            "complete_classification": (
                "predictive_virtual_brake_v14_multijoint_clean_"
                "development_fresh2_data_complete"
            ),
            "incomplete_classification": (
                "predictive_virtual_brake_v14_multijoint_clean_"
                "development_fresh2_integrity_nonpass"
            ),
            "fresh_output_root": (
                "results/proofalign_predictive_virtual_brake_v14_"
                "multijoint_clean_20260731_development2"
            ),
            "required_bindings": [
                _binding(DEVELOPMENT1_PROTOCOL_PATH),
                _binding(
                    DEVELOPMENT1_FAILURE_PATH,
                    classification=FAILURE_CLASSIFICATION,
                ),
            ],
            "selection": {
                **development1["selection"],
                "development1_partial_outcomes_observed": True,
                "development1_completed_episode_count": 2,
                "fresh2_workload_or_seed_reselected": False,
                "fresh2_scientific_parameters_changed": False,
                "fresh2_full_repeat_required": True,
            },
            "retry_disclosure": {
                "development1_status": (
                    "terminal_failed_closed_after_two_l2_outcomes"
                ),
                "development1_completed_episode_count": 2,
                "development1_failed_sequence_index": 2,
                "development1_failed_arm": "vla_only",
                "fresh2_change": (
                    "disabled arms now record fourteen-side actual margins "
                    "directly instead of invoking the inherited v13 "
                    "single-target post-state helper"
                ),
                "l2_online_mechanism_changed": False,
                "guard_changed": False,
                "thresholds_changed": False,
                "workloads_changed": False,
                "seeds_changed": False,
                "schedule_or_arm_order_changed": False,
                "estimands_changed": False,
                "gates_changed": False,
                "development1_artifacts_reused": False,
                "fresh2_is_full_180_episode_repeat": True,
                "confirmatory_claim_authorized": False,
            },
            "stop_rule": {
                **development1["stop_rule"],
                "fresh2_is_full_180_episode_repeat": True,
                "development1_partial_artifacts_reused": False,
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
                "Fresh2 is a complete development repeat after two "
                "development1 L2 task outcomes were observed. Those "
                "outcomes do not change any workload, init, environment "
                "seed, policy seed, arm order, L2 guard, threshold, "
                "estimand, gate, or analysis. The only code change removes "
                "a v13 single-target dependency from disabled-arm audit "
                "plumbing; disabled arms still dispatch the exact source "
                "action without screening. Development1 artifacts are "
                "sealed and excluded. Fresh2 repeats all 180 episodes in a "
                "new root. It remains outcome-disclosed development "
                "evidence and cannot authorize attacked evaluation, "
                "confirmation, actuator authority, deployment, hardware, "
                "or physical-safety claims."
            ),
        }
    )
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
            raise PredictiveVirtualBrakeV14Fresh2FreezeError(
                f"v14 Fresh2 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
