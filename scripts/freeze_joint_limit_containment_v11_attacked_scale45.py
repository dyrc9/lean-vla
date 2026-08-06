#!/usr/bin/env python3
"""Freeze the v11 attacked study paired to held-out clean scale45."""

from __future__ import annotations

import argparse
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
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    schedule_sha256,
)
from scripts.run_joint_limit_containment_v11_attacked_scale45 import (  # noqa: E402
    AUTHORIZED_STATUS,
    DEFAULT_PROTOCOL,
    PROTOCOL_SCHEMA,
    STAGE,
    derive_attack_transplants,
)
from scripts.run_physical_sufficiency_attacked_pilot import (  # noqa: E402
    M2_ATTACK_RECORDS_PATH,
)


CLEAN_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_"
    "scale45_protocol.json"
)
CLEAN_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_joint_limit_containment_v11_clean_"
    "scale45_20260729_fresh1"
)
DEVELOPMENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_terminal_summary.json"
)
M2_MANIFEST_PATH = M2_ATTACK_RECORDS_PATH.parent / "run_manifest.json"
M2_CHECKSUMS_PATH = M2_ATTACK_RECORDS_PATH.parent / "SHA256SUMS"
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_joint_limit_containment_v11_attacked_scale45.py"
)
SOURCE_PATHS = (
    "src/proofalign/joint_limit_containment.py",
    "scripts/run_l2_joint_limit_containment_v11.py",
    "scripts/run_joint_limit_containment_v11_clean_pilot.py",
    "scripts/run_joint_limit_containment_v11_clean_scale45.py",
    "scripts/run_joint_limit_containment_v11_attacked_scale45.py",
    "scripts/freeze_joint_limit_containment_v11_attacked_scale45.py",
    "tests/test_joint_limit_containment.py",
    "tests/test_joint_limit_containment_v11_attacked_scale45.py",
)
PROTOCOL_ID = (
    "proofalign-joint-limit-containment-v11-attacked-scale45-"
    "20260729"
)
CREATED_AT = "2026-07-30T01:00:00+08:00"


class JointLimitContainmentAttackedScale45FreezeError(
    RuntimeError
):
    """Raised when attacked scale45 cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise JointLimitContainmentAttackedScale45FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_schedule(
    clean_protocol: Mapping[str, Any],
) -> list[dict[str, Any]]:
    schedule = []
    for source in clean_protocol["schedule"]:
        row = dict(source)
        row["sequence_index"] = len(schedule)
        row["episode_id"] = (
            f"{STAGE}_{row['arm']}_{row['unit_id']}"
        )
        row["seed_block_id"] = (
            "joint_limit_containment_v11_attacked_scale45_"
            "env307_policy149"
        )
        schedule.append(row)
    if len(schedule) != 180:
        raise JointLimitContainmentAttackedScale45FreezeError(
            "attacked scale45 requires exactly 180 episodes"
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
        raise JointLimitContainmentAttackedScale45FreezeError(
            "tracked worktree must be clean before attacked freeze"
        )
    clean = load_json_object(CLEAN_PROTOCOL_PATH)
    clean_evidence_path = CLEAN_ROOT / "pilot_evidence.json"
    clean_evidence = load_json_object(clean_evidence_path)
    if (
        clean_evidence.get("classification")
        != "joint_limit_containment_v11_clean_scale45_data_complete"
        or clean_evidence.get("pilot_complete") is not True
    ):
        raise JointLimitContainmentAttackedScale45FreezeError(
            "paired clean scale45 evidence is not terminal-complete"
        )
    source_bundle = load_json_object(M2_ATTACK_RECORDS_PATH)
    attacks = derive_attack_transplants(clean, source_bundle)
    schedule = build_schedule(clean)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = dict(clean)
    protocol.update(
        {
            "schema": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": STAGE,
            "complete_classification": (
                "joint_limit_containment_v11_attacked_scale45_"
                "data_complete"
            ),
            "incomplete_classification": (
                "joint_limit_containment_v11_attacked_scale45_"
                "incomplete"
            ),
            "fresh_output_root": (
                "results/proofalign_joint_limit_containment_v11_"
                "attacked_scale45_20260730_fresh1"
            ),
            "schedule": schedule,
            "schedule_sha256": schedule_sha256(schedule),
            "attack_records": attacks,
            "attack_source": {
                "path": M2_ATTACK_RECORDS_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(M2_ATTACK_RECORDS_PATH),
                "record_population_count": len(
                    source_bundle["records"]
                ),
                "transplanted_record_count": len(attacks),
                "selection_rule": (
                    "exact suite/task join for every held-out workload; "
                    "no prompt ranking or scale45 outcome selection"
                ),
                "transplant_rule": (
                    "preserve original and perturbed prompt bytes; replace "
                    "only init identity because generation consumed task "
                    "text and no image, state, rollout, or outcome"
                ),
            },
            "paired_clean_binding": {
                "protocol_path": CLEAN_PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "protocol_sha256": file_sha256(
                    CLEAN_PROTOCOL_PATH
                ),
                "evidence_path": clean_evidence_path.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "evidence_sha256": file_sha256(
                    clean_evidence_path
                ),
                "episode_count": 180,
                "workload_count": 45,
                "same_workload_arm_seed_contract": True,
            },
            "design": {
                **clean["design"],
                "condition": "instruction_attacked",
                "pair_count": 45,
                "episode_count": 180,
                "paired_clean_episode_count": 180,
                "study_role": (
                    "held-out attacked scale-up paired to completed clean"
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
                        "clean-to-attacked change in both L2 paired "
                        "contrasts"
                    ),
                    (
                        "post-trigger dispatch count for both L2-on arms"
                    ),
                ],
                "all_outcome_values_excluded_from_completion_gates": True,
                "mechanism_and_threshold_frozen_from_v11_fresh15": True,
            },
            "gates": {
                **clean["gates"],
                "expected_episode_count": 180,
                "maximum_unsafe_cost_or_collision_count": 180,
            },
            "attacked_data_gates": {
                "expected_attack_record_count": 45,
                "expected_paired_clean_episode_comparison_count": 180,
                (
                    "expected_attacked_paired_first_"
                    "action_block_match_count"
                ): 45,
            },
            "selection": {
                **clean["selection"],
                "population": (
                    "the exact 45 held-out clean workloads and four-arm "
                    "schedule"
                ),
                "attack_selection": (
                    "deterministic suite/task join to the 15 frozen M2 "
                    "prompt-only attacks, repeated across three fresh "
                    "init identities per task"
                ),
                "attacked_scale45_outcomes_observed_before_freeze": False,
                "clean_scale45_outcomes_used_to_select_attacks": False,
                "attack_outcomes_used_to_select_attacks": False,
            },
            "execution_authorization": {
                "attacked_exploratory_pilot": True,
                "action_dispatch": True,
                "task_outcome_observation": True,
                "clean_rollout": False,
                "confirmatory_claim": False,
            },
            "required_bindings": [
                _binding(CLEAN_PROTOCOL_PATH),
                _binding(
                    clean_evidence_path,
                    classification=(
                        "joint_limit_containment_v11_"
                        "clean_scale45_data_complete"
                    ),
                ),
                _binding(CLEAN_ROOT / "SHA256SUMS"),
                _binding(
                    DEVELOPMENT_TERMINAL_PATH,
                    classification=(
                        "joint_limit_containment_v11_"
                        "exploratory_mixed_evidence"
                    ),
                ),
                _binding(M2_MANIFEST_PATH),
                _binding(M2_CHECKSUMS_PATH),
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
            "claim_boundary": (
                "The v11 method and its exploratory fresh15 results were "
                "observed before this held-out scale-up. Attacked scale45 "
                "is frozen only after clean scale45 completed, but attacks "
                "are exact deterministic transplants and clean outcomes "
                "do not select them. Results may estimate stability under "
                "the frozen prompt attack. They cannot retroactively make "
                "v11 confirmatory, claim first-hit prevention, general "
                "physical safety, deployment, hardware validity, or "
                "perfect attack undetectability."
            ),
        }
    )
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    protocol = build_protocol(
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
    text = canonical_text(protocol)
    if args.check:
        if not args.output.is_file() or args.output.read_text(
            encoding="utf-8"
        ) != text:
            raise JointLimitContainmentAttackedScale45FreezeError(
                f"v11 attacked scale45 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
