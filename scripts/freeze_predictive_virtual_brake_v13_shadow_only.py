#!/usr/bin/env python3
"""Freeze the outcome-disclosed v13 clean shadow-only ablation."""

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
from scripts.freeze_predictive_virtual_brake_v13_clean import (  # noqa: E402
    _binding,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    schedule_sha256,
)
from scripts.run_predictive_virtual_brake_v13_shadow_only import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


CLEAN_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "fresh3_protocol.json"
)
CLEAN_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "fresh3_terminal_summary.json"
)
CLEAN_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v13_clean_"
    "20260731_fresh3"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_"
    "shadow_only_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v13_shadow_only.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v13.py",
    "scripts/run_l2_predictive_virtual_brake_v13_fresh3.py",
    "scripts/run_l2_predictive_virtual_brake_v13_shadow_only.py",
    "scripts/run_predictive_virtual_brake_v13_clean.py",
    "scripts/run_predictive_virtual_brake_v13_shadow_only.py",
    "scripts/freeze_predictive_virtual_brake_v13_shadow_only.py",
    "tests/test_l2_predictive_virtual_brake_v13.py",
    "tests/test_predictive_virtual_brake_v13_shadow_only.py",
)
STAGE = "predictive_virtual_brake_v13_shadow_only_clean_ablation"
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v13-shadow-only-20260731"
)
CREATED_AT = "2026-07-31T12:35:00+08:00"


class PredictiveVirtualBrakeShadowFreezeError(RuntimeError):
    """Raised when the shadow-only ablation cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeShadowFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _schedule(clean: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = f"{clean['stage']}_"
    rows = []
    for source in clean["schedule"]:
        if not str(source["episode_id"]).startswith(prefix):
            raise PredictiveVirtualBrakeShadowFreezeError(
                "clean episode identity does not match its stage"
            )
        row = dict(source)
        row["episode_id"] = (
            f"{STAGE}_{str(source['episode_id'])[len(prefix):]}"
        )
        row["sequence_index"] = len(rows)
        rows.append(row)
    return rows


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise PredictiveVirtualBrakeShadowFreezeError(
            "tracked worktree must be clean before shadow-only freeze"
        )
    clean = load_json_object(CLEAN_PROTOCOL_PATH)
    terminal = load_json_object(CLEAN_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != (
            "predictive_virtual_brake_v13_clean_fresh3_"
            "engineering_gate_pass"
        )
        or terminal.get("clean_utility_gate_passed") is not True
        or terminal["next_experiments"][
            "shadow_only_ablation_required"
        ]
        is not True
    ):
        raise PredictiveVirtualBrakeShadowFreezeError(
            "clean terminal does not require the causal ablation"
        )
    schedule = _schedule(clean)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        **clean,
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": STAGE,
        "complete_classification": (
            "predictive_virtual_brake_v13_shadow_only_complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v13_shadow_only_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v13_"
            "shadow_only_20260731_fresh1"
        ),
        "schedule": schedule,
        "schedule_sha256": schedule_sha256(schedule),
        "design": {
            **clean["design"],
            "condition": "clean_shadow_and_restore_only",
            "study_role": (
                "outcome-disclosed causal execution-path ablation"
            ),
            "guard_candidate_evaluation_enabled": False,
            "guard_intervention_enabled": False,
            "counterfactual_trigger_annotation_enabled": True,
            "same_workloads_seeds_arm_order_as_fresh3": True,
            "primary_estimands": [
                (
                    "shadow-only execution_only minus vla_only paired "
                    "task success"
                ),
                (
                    "shadow-only dual minus semantic_only paired task "
                    "success"
                ),
                (
                    "full-brake minus shadow-only task success, official "
                    "unsafe count, joint-limit exposure, and termination"
                ),
            ],
        },
        "analysis": {
            **clean["analysis"],
            "outcome_gates_are_descriptive_only": True,
            "full_brake_reference_path": (
                CLEAN_TERMINAL_PATH.relative_to(REPO_ROOT).as_posix()
            ),
        },
        "shadow_only_gates": {
            "expected_episode_count": 180,
            "expected_paired_workload_count": 45,
            "active_trigger_count_max": 0,
            "guard_intervention_count_max": 0,
            "shadow_restore_failure_count_max": 0,
            "exact_action_mismatch_count_max": 0,
        },
        "execution_authorization": {
            "clean_shadow_only_ablation": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "required_bindings": [
            *clean["required_bindings"],
            _binding(CLEAN_PROTOCOL_PATH),
            _binding(
                CLEAN_TERMINAL_PATH,
                classification=(
                    "predictive_virtual_brake_v13_clean_fresh3_"
                    "engineering_gate_pass"
                ),
            ),
            _binding(
                CLEAN_ROOT / "pilot_evidence.json",
                classification=(
                    "predictive_virtual_brake_v13_clean_outcome_"
                    "fresh3_complete"
                ),
            ),
            _binding(CLEAN_ROOT / "SHA256SUMS"),
        ],
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
            "This ablation was designed after all Fresh3 clean outcomes "
            "were observed. It changes only L2 guard behavior: every L2 "
            "policy step still performs the same one-step simulator "
            "shadow, warm-start-complete restore, and exact nominal action "
            "dispatch, but it never evaluates or applies a guard. The "
            "same 45 workloads, seeds, four arms, and order are retained. "
            "Results can diagnose shadow-path confounding but cannot be "
            "confirmatory or establish attacked, deployment, hardware, "
            "or arbitrary-joint safety."
        ),
    }


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
            raise PredictiveVirtualBrakeShadowFreezeError(
                f"v13 shadow-only protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
