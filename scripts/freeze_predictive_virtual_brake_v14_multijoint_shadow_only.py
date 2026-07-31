#!/usr/bin/env python3
"""Freeze the v14 same-schedule shadow-only causal-development study."""

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
from scripts.run_predictive_virtual_brake_v14_multijoint_shadow_only import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


FULL_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
FULL_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_terminal_summary.json"
)
FULL_EVIDENCE_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_"
    "multijoint_clean_20260731_development2"
    / "pilot_evidence.json"
)
FULL_CHECKSUMS_PATH = FULL_EVIDENCE_PATH.parent / "SHA256SUMS"
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_development_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v14_multijoint_shadow_only.py"
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
        "scripts/run_l2_predictive_virtual_brake_v14_"
        "multijoint_shadow_only.py"
    ),
    (
        "scripts/run_predictive_virtual_brake_v14_"
        "multijoint_shadow_only.py"
    ),
    (
        "scripts/freeze_predictive_virtual_brake_v14_"
        "multijoint_shadow_only.py"
    ),
    (
        "scripts/freeze_predictive_virtual_brake_v14_"
        "multijoint_shadow_only_terminal.py"
    ),
    (
        "tests/test_predictive_virtual_brake_v14_"
        "multijoint_shadow_only.py"
    ),
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v14-multijoint-"
    "shadow-only-causal-development-20260731"
)
CREATED_AT = "2026-07-31T21:20:00+08:00"
FULL_TERMINAL_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_clean_development_"
    "fresh2_data_complete_calibration_nonpass"
)
PREDICTION_TOLERANCE_RAD = 0.002


class PredictiveVirtualBrakeV14ShadowOnlyFreezeError(RuntimeError):
    """Raised when the shadow-only protocol cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeV14ShadowOnlyFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(
    path: Path,
    *,
    classification: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise PredictiveVirtualBrakeV14ShadowOnlyFreezeError(
            f"required shadow-only binding is absent: {path}"
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
        raise PredictiveVirtualBrakeV14ShadowOnlyFreezeError(
            "tracked worktree must be clean before shadow-only freeze"
        )
    full = load_json_object(FULL_PROTOCOL_PATH)
    terminal = load_json_object(FULL_TERMINAL_PATH)
    evidence = load_json_object(FULL_EVIDENCE_PATH)
    if (
        terminal.get("classification")
        != FULL_TERMINAL_CLASSIFICATION
        or terminal.get("episode_count") != 180
        or len(evidence.get("episodes", ())) != 180
        or len(full.get("schedule", ())) != 180
        or evidence.get("protocol_id") != full.get("protocol_id")
    ):
        raise PredictiveVirtualBrakeV14ShadowOnlyFreezeError(
            "bound full-brake evidence differs from its terminal record"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = deepcopy(full)
    protocol.update(
        {
            "schema": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": "same_schedule_shadow_only_causal_development",
            "complete_classification": (
                "predictive_virtual_brake_v14_multijoint_shadow_only_"
                "causal_development_data_complete"
            ),
            "incomplete_classification": (
                "predictive_virtual_brake_v14_multijoint_shadow_only_"
                "causal_development_integrity_nonpass"
            ),
            "fresh_output_root": (
                "results/proofalign_predictive_virtual_brake_v14_"
                "multijoint_shadow_only_20260731_causal1"
            ),
            "required_bindings": [
                _binding(FULL_PROTOCOL_PATH),
                _binding(
                    FULL_TERMINAL_PATH,
                    classification=FULL_TERMINAL_CLASSIFICATION,
                ),
                _binding(FULL_EVIDENCE_PATH),
                _binding(FULL_CHECKSUMS_PATH),
            ],
            "selection": {
                **full["selection"],
                "shadow_only_workload_or_seed_reselected": False,
                "shadow_only_schedule_or_arm_order_changed": False,
                "shadow_only_exact_full_brake_schedule_reused": True,
                "full_brake_outcomes_observed_before_freeze": True,
                "causal_development_only": True,
            },
            "analysis": {
                **full["analysis"],
                "role": "outcome-disclosed causal development control",
                "same_schedule_full_brake_comparison_required": True,
                "causal_estimands": [
                    "full_minus_shadow_only_actual_below_floor_count",
                    "full_minus_shadow_only_actual_crossing_count",
                    "full_minus_shadow_only_task_success_probability",
                    "full_minus_shadow_only_unknown_or_deadlock_probability",
                ],
                "pre_divergence_identity_required": True,
                "disabled_arm_deterministic_identity_required": True,
                "outcome_gates_are_descriptive": True,
                "future_confirmation_requires_new_population_and_seeds": True,
            },
            "v14_gates": {
                **full["v14_gates"],
                "maximum_prediction_execution_side_error_rad": (
                    PREDICTION_TOLERANCE_RAD
                ),
            },
            "shadow_only_gates": {
                "expected_episode_count": 180,
                "expected_paired_workload_count": 45,
                "expected_l2_episode_count": 90,
                "one_shadow_step_per_l2_policy_step": True,
                "guard_candidate_evaluation_allowed": False,
                "intervention_authority_allowed": False,
                "deadlock_synthesis_allowed": False,
                "exact_source_action_required": True,
                "full_brake_trigger_count_minimum": 1,
                "pre_divergence_action_digest_identity_required": True,
                "pre_divergence_margin_tolerance_rad": 1e-8,
                "disabled_arm_margin_tolerance_rad": 1e-8,
            },
            "execution_authorization": {
                **full["execution_authorization"],
                "authorized_runner": (
                    "scripts/run_predictive_virtual_brake_v14_"
                    "multijoint_shadow_only.py"
                ),
                "intervention_authority_enabled": False,
                "guard_candidate_evaluation_enabled": False,
                "same_schedule_causal_control": True,
            },
            "stop_rule": {
                **full["stop_rule"],
                "run_clean_schedule_to_completion": True,
                "outcome_based_early_stopping": False,
                "attacked_stage_authorized": False,
                "future_qualification_requires_separate_protocol": True,
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
                "This protocol reuses the exact 180-episode Fresh2 "
                "schedule, workloads, initial states, seeds, arm order, "
                "source policy, fourteen-side margins, trigger threshold, "
                "and simulator runtime after all full-brake outcomes were "
                "observed. L2-labelled arms retain one unguarded shadow "
                "step and exact snapshot restoration per policy step, but "
                "never evaluate guard candidates, apply a virtual guard, "
                "substitute an action, or synthesize a brake deadlock. The "
                "0.002 rad shadow prediction/execution tolerance is an "
                "outcome-disclosed development tolerance chosen above the "
                "observed Fresh2 non-intervention numerical maximum; it "
                "does not revise or rescue the registered Fresh2 1e-9 "
                "calibration nonpass. Results can isolate the causal "
                "development effect of brake authority under this fixed "
                "schedule, but cannot authorize confirmation, attacked "
                "evaluation, deployment, hardware, actuator authority, or "
                "physical-safety claims."
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
            raise PredictiveVirtualBrakeV14ShadowOnlyFreezeError(
                f"shadow-only protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
