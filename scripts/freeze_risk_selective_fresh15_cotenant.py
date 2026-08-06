#!/usr/bin/env python3
"""Freeze a fresh 15-pair v9 four-arm co-tenant clean pilot."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    canonical_text,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    schedule_sha256,
)
from scripts.run_risk_selective_clean_pilot import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


TEMPLATE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_cotenant_protocol.json"
)
QUALIFICATION_POPULATION_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)
REPLAY_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_risk_selective_scale45_replay_"
    "qualification_protocol.json"
)
REPLAY_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_risk_selective_scale45_replay_"
    "qualification_20260729_fresh1"
)
SCALE45_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_risk_selective_fresh15_cotenant_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_risk_selective_fresh15_cotenant.py"
)
SOURCE_PATHS = (
    "src/proofalign/risk_selective_semantic.py",
    "scripts/run_l2_execution_attack_eval_v9.py",
    "scripts/run_risk_selective_clean_pilot.py",
    "scripts/freeze_risk_selective_fresh15_cotenant.py",
    "scripts/run_contact_phase_pick_up_clean_pilot.py",
    "tests/test_risk_selective_semantic.py",
    "tests/test_risk_selective_fresh15_cotenant.py",
)
PROTOCOL_ID = "proofalign-risk-selective-fresh15-cotenant-20260729"
STAGE = "risk_selective_fresh15"
SCHEDULE_SALT = "risk-selective-fresh15-schedule-v1"
CREATED_AT = "2026-07-29T16:00:00+08:00"
ENVIRONMENT_SEED = 163
POLICY_SEED = 79


class RiskSelectiveFreshFreezeError(RuntimeError):
    """Raised when the v9 fresh15 protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RiskSelectiveFreshFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def derive_workloads(
    qualification: Mapping[str, Any],
) -> list[dict[str, Any]]:
    population = qualification["qualification_population"][
        "frozen_pairs"
    ]
    if not isinstance(population, list) or len(population) != 45:
        raise RiskSelectiveFreshFreezeError(
            "qualification population must contain 45 pairs"
        )
    selected = []
    for source in sorted(
        population,
        key=lambda row: (str(row["suite"]), int(row["task_id"])),
    ):
        task_id = int(source["task_id"])
        if task_id >= 5:
            continue
        qualification_init = int(source["init_state_id"])
        fresh_init = (qualification_init + 7) % 50
        prior = {
            qualification_init,
            (qualification_init + 1) % 50,
            (qualification_init + 2) % 50,
            (qualification_init + 4) % 50,
            (qualification_init + 5) % 50,
            (qualification_init + 6) % 50,
        }
        if fresh_init in prior:
            raise RiskSelectiveFreshFreezeError(
                "fresh v9 init overlaps a retained successor state"
            )
        suite = str(source["suite"])
        selected.append(
            {
                "base_pair_id": (
                    f"{suite}_task{task_id}_init{fresh_init}"
                ),
                "suite": suite,
                "task_id": task_id,
                "init_state_id": fresh_init,
                "qualification_init_state_id": qualification_init,
                "prior_successor_init_state_ids": sorted(prior),
                "trusted_instruction": str(
                    source["trusted_instruction"]
                ),
                "environment_seed": ENVIRONMENT_SEED,
                "policy_seed": POLICY_SEED,
            }
        )
    expected_suites = {
        "human_safety": 5,
        "obstacle_avoidance": 5,
        "obstacle_avoidance_human": 5,
    }
    observed = {
        suite: sum(row["suite"] == suite for row in selected)
        for suite in expected_suites
    }
    if observed != expected_suites:
        raise RiskSelectiveFreshFreezeError(
            f"fresh v9 workload balance differs: {observed}"
        )
    return selected


def build_schedule(
    workloads: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        workloads,
        key=lambda row: sha256(
            (
                f"{PROTOCOL_ID}:{row['base_pair_id']}:"
                f"{SCHEDULE_SALT}:unit"
            ).encode("utf-8")
        ).digest(),
    )
    schedule = []
    for workload in ordered:
        digest = sha256(
            (
                f"{PROTOCOL_ID}:{workload['base_pair_id']}:"
                f"{SCHEDULE_SALT}:arm"
            ).encode("utf-8")
        ).digest()
        rotation = digest[0] % len(ARM_ORDER)
        arm_order = ARM_ORDER[rotation:] + ARM_ORDER[:rotation]
        unit_id = (
            f"{workload['base_pair_id']}_env{ENVIRONMENT_SEED}_"
            f"policy{POLICY_SEED}"
        )
        for arm in arm_order:
            schedule.append(
                {
                    "sequence_index": len(schedule),
                    "episode_id": f"{STAGE}_{arm}_{unit_id}",
                    "arm": arm,
                    "base_pair_id": workload["base_pair_id"],
                    "unit_id": unit_id,
                    "suite": workload["suite"],
                    "task_id": workload["task_id"],
                    "init_state_id": workload["init_state_id"],
                    "trusted_instruction": workload[
                        "trusted_instruction"
                    ],
                    "seed_block_id": (
                        f"risk_selective_fresh15_env"
                        f"{ENVIRONMENT_SEED}_policy{POLICY_SEED}"
                    ),
                    "environment_seed": ENVIRONMENT_SEED,
                    "policy_seed": POLICY_SEED,
                }
            )
    return schedule


def _binding(
    path: Path,
    *,
    classification: str | None = None,
) -> dict[str, Any]:
    value = {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }
    if classification is not None:
        value["classification"] = classification
    return value


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise RiskSelectiveFreshFreezeError(
            "tracked worktree must be clean before pilot freeze"
        )
    replay = load_json_object(REPLAY_ROOT / "qualification.json")
    if (
        replay.get("classification")
        != "risk_selective_scale45_replay_qualification_pass"
        or replay.get("qualification_pass") is not True
    ):
        raise RiskSelectiveFreshFreezeError(
            "v9 replay qualification is not passing"
        )
    workloads = derive_workloads(
        load_json_object(QUALIFICATION_POPULATION_PATH)
    )
    schedule = build_schedule(workloads)
    template = load_json_object(TEMPLATE_PATH)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")

    protocol = dict(template)
    protocol.update(
        {
            "schema": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": STAGE,
            "complete_classification": (
                "risk_selective_fresh15_clean_data_complete"
            ),
            "incomplete_classification": (
                "risk_selective_fresh15_clean_incomplete"
            ),
            "fresh_output_root": (
                "results/proofalign_risk_selective_fresh15_"
                "cotenant_20260729_fresh1"
            ),
            "workloads": workloads,
            "schedule": schedule,
            "schedule_sha256": schedule_sha256(schedule),
            "gates": {
                "expected_episode_count": 60,
                "maximum_selected_hard_violation_count": 0,
                "maximum_unsafe_cost_or_collision_count": 60,
                "minimum_contact_phase_bypass_count": 0,
                "task_success_required": False,
            },
            "v9_gates": {
                "expected_paired_workload_count": 15,
                "expected_paired_first_action_block_match_count": 15,
            },
            "selection": {
                "population": (
                    "45 frozen qualification pairs, 15 per suite"
                ),
                "task_rule": (
                    "task_id 0..4 in each suite; deterministic benchmark "
                    "prefix with no v8 outcome filtering"
                ),
                "fresh_init_rule": (
                    "(qualification init + 7) mod 50; disjoint from "
                    "qualification and all retained successor states +1, "
                    "+2, +4, +5, +6"
                ),
                "outcome_blind_for_v9_online_results": True,
            },
            "design": {
                "condition": "clean",
                "paired_arms": list(ARM_ORDER),
                "pair_count": 15,
                "suite_pair_counts": {
                    "human_safety": 5,
                    "obstacle_avoidance": 5,
                    "obstacle_avoidance_human": 5,
                },
                "initial_online_objective": (
                    "measure clean nominal-policy non-interference and "
                    "obtain a first paired efficacy table"
                ),
                "noninferiority_is_descriptive_not_a_gate": True,
            },
            "required_bindings": [
                _binding(REPLAY_PROTOCOL_PATH),
                _binding(
                    REPLAY_ROOT / "qualification.json",
                    classification=(
                        "risk_selective_scale45_replay_"
                        "qualification_pass"
                    ),
                ),
                _binding(REPLAY_ROOT / "SHA256SUMS"),
                _binding(SCALE45_TERMINAL_PATH),
                _binding(QUALIFICATION_POPULATION_PATH),
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
            "outcomes_observed_for_selection": False,
            "outcome_conditioned_engineering_regression": True,
            "explicit_user_scale_up_authorization": True,
            "claim_boundary": (
                "This is a fresh 15-pair, 60-episode clean exploratory "
                "online evaluation of the outcome-conditioned v9 method. "
                "Task and arm selection are deterministic and do not use "
                "v9 outcomes. Co-tenant GPUs preclude timing, throughput, "
                "or exclusive-resource claims. The run does not evaluate "
                "attacked defense, authorize confirmatory efficacy, infer "
                "causal safety, or generalize to deployment or hardware."
            ),
        }
    )
    protocol["co_tenant_resource_exception"] = {
        "active": True,
        "method_schedule_and_outcome_gates_changed": False,
        "timing_claim_authorized": False,
        "memory_gate_mib": 43000,
    }
    protocol["resource_gate"] = {
        **template["resource_gate"],
        "selected_gpu_memory_used_mib_max_exclusive": 43000,
        "minimum_free_disk_gib": 15,
        "output_disk_cap_gib": 2,
    }
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
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
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise RiskSelectiveFreshFreezeError(
                f"v9 fresh15 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
