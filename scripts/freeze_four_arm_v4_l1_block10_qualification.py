#!/usr/bin/env python3
"""Freeze the post-outcome Block-10 no-outcome qualification."""

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
from scripts.run_four_arm_v4_l1_block10_qualification import (  # noqa: E402
    PROTOCOL_SCHEMA,
)


PARENT_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_fresh3_protocol.json"
)
PARENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_qualification_protocol.json"
)
SOURCE_PATHS = (
    "src/proofalign/semantic_action_selection.py",
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/semantic_trust.py",
    "scripts/run_liberosafety_pi05_openpi_eval.py",
    "scripts/run_l2_execution_attack_eval.py",
    "scripts/run_l2_execution_attack_eval_v2.py",
    "scripts/run_four_arm_v4_l1_repair_qualification.py",
    "scripts/run_four_arm_v4_l1_repair_qualification_v2.py",
    "scripts/run_four_arm_v4_l1_block10_qualification.py",
    "scripts/freeze_four_arm_v4_l1_block10_qualification.py",
    "tests/test_l1_block10_qualification.py",
    "tests/test_l1_repair_qualification.py",
    "tests/test_l1_repair_qualification_v2.py",
    "tests/test_semantic_online_runner_v2.py",
)
CREATED_AT = "2026-07-28T11:15:00+08:00"
USER_AUTHORIZATION = (
    "2026-07-28 user instruction after disclosure of the Block-5/K=4 "
    "qualification nonpass: increase ActionBlock size, validate a longer "
    "distance ActionBlock at once, and reserve a later block-size ablation."
)


class Block10FreezeError(RuntimeError):
    """Raised when the Block-10 protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Block10FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    user_authorization: str = USER_AUTHORIZATION,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise Block10FreezeError(
            "tracked worktree must be clean before Block-10 freeze"
        )
    parent = load_json_object(PARENT_PROTOCOL_PATH)
    terminal = load_json_object(PARENT_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != "l1_repair_initial_availability_qualification_nonpass"
        or terminal.get("qualification_pass") is not False
        or terminal.get("lifecycle", {}).get(
            "same_population_retry_authorized"
        )
        is not False
    ):
        raise Block10FreezeError(
            "parent Block-5/K=4 terminal result is not frozen nonpass"
        )
    old_pairs = parent["qualification_population"]["frozen_pairs"]
    pairs = []
    for pair in old_pairs:
        old_init = int(pair["init_state_id"])
        new_init = (old_init + 17) % 50
        if new_init == old_init:
            raise Block10FreezeError(
                "Block-10 split overlaps the parent init state"
            )
        pairs.append(
            {
                "base_pair_id": (
                    f"{pair['suite']}_task{pair['task_id']}_init{new_init}"
                ),
                "parent_base_pair_id": pair["base_pair_id"],
                "suite": pair["suite"],
                "task_id": int(pair["task_id"]),
                "init_state_id": new_init,
                "bddl_path": pair["bddl_path"],
                "trusted_instruction": pair["trusted_instruction"],
            }
        )
    if (
        len(pairs) != 45
        or len({pair["base_pair_id"] for pair in pairs}) != 45
    ):
        raise Block10FreezeError(
            "Block-10 split is not a unique 45-pair population"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    source_bindings = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise Block10FreezeError(
                f"Block-10 source is absent: {relative}"
            )
        source_bindings[relative] = file_sha256(path)
    episode_constants = dict(parent["episode_constants"])
    episode_constants["replan_steps"] = 10
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-four-arm-v4-l1-block10-qualification-20260728"
        ),
        "protocol_status": (
            "post_outcome_block10_no_task_outcome_qualification_authorized"
        ),
        "created_at": created_at,
        "user_authorization": user_authorization,
        "post_outcome_repair": True,
        "outcomes_observed_in_parent": True,
        "outcomes_observed_in_qualification": False,
        "confirmatory_claim_authorized": False,
        "parent_l1_repair_terminal": {
            "path": PARENT_TERMINAL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(PARENT_TERMINAL_PATH),
            "classification": terminal["classification"],
            "qualification_pass": terminal["qualification_pass"],
        },
        "parent_block5_k4_protocol": {
            "path": PARENT_PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(PARENT_PROTOCOL_PATH),
            "protocol_id": parent["protocol_id"],
        },
        "change_rationale": {
            "observed_parent_fact": (
                "K=1 through K=4 all covered the same 24/45 initial "
                "states; failed states had best five-step progress below "
                "the frozen 2 mm gate"
            ),
            "single_primary_change": (
                "assess one complete ten-step source ActionBlock instead "
                "of four separately sampled five-step prefixes"
            ),
            "threshold_relaxed": False,
            "old_nonpass_overwritten": False,
        },
        "repair": {
            "semantic_candidate_count": 1,
            "replan_steps": 10,
            "checked_action_block_steps": 10,
            "dispatched_action_block_steps_if_later_authorized": 10,
            "source_policy_chunk_steps": 10,
            "min_progress_m": 0.002,
            "threshold_changed": False,
            "max_projection_l2": 0.5,
            "geometry_rule": parent["repair"]["geometry_rule"],
            "geometry_trust_boundary": parent["repair"][
                "geometry_trust_boundary"
            ],
            "candidate_rule": (
                "one deterministic-seeded source policy call under one "
                "fixed trusted T+Z prompt; assess the full ten-step prefix "
                "with the frozen checker and do not dispatch if ineligible"
            ),
        },
        "qualification_population": {
            "frozen_pairs": pairs,
            "base_pair_count": 45,
            "environment_seed": 83,
            "policy_seed": 29,
            "stabilization_env_step_count_per_pair": int(
                parent["qualification_population"][
                    "stabilization_env_step_count_per_pair"
                ]
            ),
            "policy_conditioned_env_step_count": 0,
            "policy_inference_count": 45,
            "task_outcome_observation_forbidden": True,
            "split_construction": {
                "parent_init_state_count_per_task": 50,
                "rule": "(parent_init_state_id + 17) mod 50",
                "disjoint_from_parent_init_per_task": True,
                "runtime_count_audit_completed_before_freeze": True,
                "boundary": (
                    "Disjoint only from the immediately preceding "
                    "qualification init for each task; not a model-held-out "
                    "or confirmatory split."
                ),
            },
        },
        "qualification_gates": {
            "valid_row_count": 45,
            "geometry_ready_rate_min": 1.0,
            "eligible_candidate_rate_min": 0.9,
            "worst_suite_eligible_rate_min": 0.8,
            "selected_hard_violation_count_max": 0,
            "policy_conditioned_env_step_count_max": 0,
            "dispatch_count_max": 0,
            "task_outcome_count_max": 0,
            "primary_gate_block_steps": 10,
        },
        "matched_block_size_shadow": {
            "authorized": True,
            "source_policy_calls_added": 0,
            "source_chunk_shared": True,
            "primary_steps": 10,
            "shadow_only_steps": [2, 5],
            "fixed_min_progress_m_all_sizes": 0.002,
            "fixed_max_projection_l2_all_sizes": 0.5,
            "can_influence_primary_gate": False,
            "task_outcomes_observed": False,
            "purpose": (
                "Preserve matched H=2/5/10 initial availability data for a "
                "later paper ablation without rerunning or selecting block "
                "size from task outcomes."
            ),
        },
        "future_block_size_ablation": {
            "paper_table_reserved": True,
            "sizes": [2, 5, 10],
            "paired_unit": "task/init/source-policy-chunk",
            "primary_endpoint": (
                "eligible_under_the_same_absolute_2mm_and_0.5_projection_gate"
            ),
            "efficacy_rollout_authorized": False,
            "length_selection_from_this_result_forbidden": True,
        },
        "victim": parent["victim"],
        "episode_constants": episode_constants,
        "runtime_dependency": parent["runtime_dependency"],
        "required_runtime_interpreter": parent[
            "required_runtime_interpreter"
        ],
        "execution_authorization": {
            "qualification_probe": True,
            "task_outcome_rollout": False,
            "clean_rollout": False,
            "attacked_rollout": False,
        },
        "fresh_output_root": (
            "results/proofalign_four_arm_v4_l1_block10_qualification_"
            "20260728_fresh1"
        ),
        "resource_budget": parent["resource_budget"],
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "sha256": source_bindings,
        },
        "claim_boundary": (
            "This protocol was created after both the support45 clean "
            "nonpass and the Block-5/K=4 qualification nonpass. It "
            "authorizes only a zero-dispatch, no-task-outcome initial-state "
            "Block-10 qualification plus matched H=2/5 shadow assessments. "
            "Passing cannot overwrite either parent nonpass or establish "
            "clean trajectory retention, attack-defense efficacy, "
            "deployment perception, hardware safety, or a confirmatory "
            "result."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument(
        "--user-authorization", default=USER_AUTHORIZATION
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source_commit = None
    if args.check and args.output.is_file():
        retained = load_json_object(args.output)
        source_commit = retained.get("source", {}).get(
            "repository_commit"
        )
    text = canonical_text(
        build_protocol(
            created_at=args.created_at,
            user_authorization=args.user_authorization,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise Block10FreezeError(
                f"Block-10 protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
