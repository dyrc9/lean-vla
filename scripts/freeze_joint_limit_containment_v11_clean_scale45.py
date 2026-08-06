#!/usr/bin/env python3
"""Freeze the v11 clean held-out scale45 validation study."""

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
from scripts.freeze_joint_limit_containment_v11_clean_fresh15 import (  # noqa: E402
    PRIOR_INIT_STATE_IDS,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    schedule_sha256,
)
from scripts.run_joint_limit_containment_v11_clean_scale45 import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


DEVELOPMENT_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_"
    "fresh15_protocol.json"
)
DEVELOPMENT_CLEAN_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_joint_limit_containment_v11_clean_"
    "fresh15_20260729_fresh1"
)
DEVELOPMENT_ATTACKED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_joint_limit_containment_v11_attacked_"
    "fresh15_20260729_fresh1"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_terminal_summary.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_"
    "scale45_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_joint_limit_containment_v11_clean_scale45.py"
)
SOURCE_PATHS = (
    "src/proofalign/joint_limit_containment.py",
    "scripts/run_l2_joint_limit_containment_v11.py",
    "scripts/run_joint_limit_containment_v11_clean_pilot.py",
    "scripts/run_joint_limit_containment_v11_clean_scale45.py",
    "scripts/freeze_joint_limit_containment_v11_clean_scale45.py",
    "tests/test_joint_limit_containment.py",
    "tests/test_joint_limit_containment_v11_clean_scale45.py",
)
PROTOCOL_ID = (
    "proofalign-joint-limit-containment-v11-clean-scale45-20260729"
)
STAGE = "joint_limit_containment_v11_clean_scale45"
SCHEDULE_SALT = "joint-limit-containment-v11-clean-scale45-schedule-v1"
INIT_SELECTION_SALT = (
    "proofalign-v11-clean-heldout-scale45-init-selection-v1"
)
CREATED_AT = "2026-07-29T23:45:00+08:00"
ENVIRONMENT_SEED = 307
POLICY_SEED = 149


class JointLimitContainmentScale45FreezeError(RuntimeError):
    """Raised when the held-out clean scale45 protocol cannot freeze."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise JointLimitContainmentScale45FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _select_init_states(
    suite: str,
    task_id: int,
    development_init: int,
) -> tuple[int, int, int]:
    excluded = set(PRIOR_INIT_STATE_IDS[(suite, task_id)])
    excluded.add(development_init)
    available = [
        init_state_id
        for init_state_id in range(50)
        if init_state_id not in excluded
    ]
    ordered = sorted(
        available,
        key=lambda init_state_id: sha256(
            (
                f"{INIT_SELECTION_SALT}:{suite}:{task_id}:"
                f"{init_state_id}"
            ).encode("utf-8")
        ).digest(),
    )
    selected = tuple(ordered[:3])
    if len(selected) != 3 or len(set(selected)) != 3:
        raise JointLimitContainmentScale45FreezeError(
            "scale45 init selection is not three distinct states"
        )
    return selected


def derive_workloads(
    development: Mapping[str, Any],
) -> list[dict[str, Any]]:
    workloads = []
    for source in development["workloads"]:
        suite = str(source["suite"])
        task_id = int(source["task_id"])
        development_init = int(source["init_state_id"])
        excluded = set(PRIOR_INIT_STATE_IDS[(suite, task_id)])
        excluded.add(development_init)
        for replicate_index, init_state_id in enumerate(
            _select_init_states(
                suite,
                task_id,
                development_init,
            )
        ):
            if init_state_id in excluded:
                raise JointLimitContainmentScale45FreezeError(
                    "held-out init overlaps a prior or development init"
                )
            workloads.append(
                {
                    "base_pair_id": (
                        f"{suite}_task{task_id}_init{init_state_id}"
                    ),
                    "suite": suite,
                    "task_id": task_id,
                    "replicate_index": replicate_index,
                    "init_state_id": init_state_id,
                    "excluded_init_state_ids": sorted(excluded),
                    "trusted_instruction": str(
                        source["trusted_instruction"]
                    ),
                    "environment_seed": ENVIRONMENT_SEED,
                    "policy_seed": POLICY_SEED,
                }
            )
    identities = {
        (
            str(row["suite"]),
            int(row["task_id"]),
            int(row["init_state_id"]),
        )
        for row in workloads
    }
    if len(workloads) != 45 or len(identities) != 45:
        raise JointLimitContainmentScale45FreezeError(
            "scale45 requires exactly 45 distinct task/init workloads"
        )
    return workloads


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
                        "joint_limit_containment_v11_scale45_"
                        f"env{ENVIRONMENT_SEED}_policy{POLICY_SEED}"
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
        raise JointLimitContainmentScale45FreezeError(
            "tracked worktree must be clean before scale45 freeze"
        )
    development = load_json_object(DEVELOPMENT_PROTOCOL_PATH)
    terminal = load_json_object(TERMINAL_PATH)
    if terminal.get("classification") != (
        "joint_limit_containment_v11_exploratory_mixed_evidence"
    ):
        raise JointLimitContainmentScale45FreezeError(
            "v11 development terminal classification differs"
        )
    workloads = derive_workloads(development)
    schedule = build_schedule(workloads)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = dict(development)
    protocol.update(
        {
            "schema": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": STAGE,
            "complete_classification": (
                "joint_limit_containment_v11_clean_scale45_"
                "data_complete"
            ),
            "incomplete_classification": (
                "joint_limit_containment_v11_clean_scale45_incomplete"
            ),
            "fresh_output_root": (
                "results/proofalign_joint_limit_containment_v11_"
                "clean_scale45_20260729_fresh1"
            ),
            "workloads": workloads,
            "schedule": schedule,
            "schedule_sha256": schedule_sha256(schedule),
            "selection": {
                "population": (
                    "the same 15 task identities with three held-out init "
                    "identities per task"
                ),
                "fresh_init_rule": (
                    "SHA-256 ordering of [0,49] after excluding every "
                    "task-specific pre-v11 identity and the v11 fresh15 "
                    "development identity; take the first three"
                ),
                "init_selection_salt": INIT_SELECTION_SALT,
                "selected_before_scale45_outcomes": True,
                "development_clean_and_attacked_outcomes_observed": True,
                "method_or_threshold_changed_after_fresh15": False,
            },
            "design": {
                **development["design"],
                "condition": "clean",
                "pair_count": 45,
                "episode_count": 180,
                "study_role": (
                    "held-out scale-up after exploratory development pilot"
                ),
                "primary_estimands": [
                    (
                        "execution_only minus vla_only paired task "
                        "success and joint-limit-step rate"
                    ),
                    (
                        "dual minus semantic_only paired task success "
                        "and joint-limit-step rate"
                    ),
                    (
                        "post-trigger dispatch count for both L2-on arms"
                    ),
                ],
                "all_outcome_values_excluded_from_completion_gates": True,
                "mechanism_and_threshold_frozen_from_v11_fresh15": True,
            },
            "gates": {
                **development["gates"],
                "expected_episode_count": 180,
                "maximum_unsafe_cost_or_collision_count": 180,
            },
            "v10_gates": {
                "expected_paired_workload_count": 45,
                "expected_paired_first_action_block_match_count": 45,
            },
            "v11_gates": {
                **development["v11_gates"],
                "expected_paired_workload_count": 45,
                "expected_paired_first_action_block_match_count": 45,
            },
            "required_bindings": [
                _binding(DEVELOPMENT_PROTOCOL_PATH),
                _binding(
                    DEVELOPMENT_CLEAN_ROOT / "pilot_evidence.json",
                    classification=(
                        "joint_limit_containment_v11_clean_data_complete"
                    ),
                ),
                _binding(DEVELOPMENT_CLEAN_ROOT / "SHA256SUMS"),
                _binding(
                    DEVELOPMENT_ATTACKED_ROOT / "pilot_evidence.json",
                    classification=(
                        "joint_limit_containment_v11_"
                        "attacked_data_complete"
                    ),
                ),
                _binding(DEVELOPMENT_ATTACKED_ROOT / "SHA256SUMS"),
                _binding(
                    TERMINAL_PATH,
                    classification=(
                        "joint_limit_containment_v11_"
                        "exploratory_mixed_evidence"
                    ),
                ),
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
                "The v11 method and threshold were designed after v10 and "
                "their exploratory fresh15 clean/attacked outcomes were "
                "observed before this scale-up froze. The 45 held-out "
                "workloads are fresh and no method parameter changes here. "
                "This study may estimate containment and utility stability, "
                "but cannot retroactively make v11 confirmatory, claim "
                "first-hit prevention, general physical safety, deployment, "
                "hardware validity, or attacked-defense efficacy."
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
            raise JointLimitContainmentScale45FreezeError(
                f"v11 clean scale45 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
