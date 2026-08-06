#!/usr/bin/env python3
"""Freeze the paired scale45 v13 instruction-attack evaluation."""

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
from scripts import run_joint_limit_containment_v11_attacked_scale45 as transplant  # noqa: E402
from scripts.freeze_predictive_virtual_brake_v13_clean import (  # noqa: E402
    _binding,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    schedule_sha256,
)
from scripts.run_physical_sufficiency_attacked_pilot import (  # noqa: E402
    M2_ATTACK_RECORDS_PATH,
)
from scripts.run_predictive_virtual_brake_v13_attacked import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
    STAGE,
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
M2_MANIFEST_PATH = M2_ATTACK_RECORDS_PATH.parent / "run_manifest.json"
M2_CHECKSUMS_PATH = M2_ATTACK_RECORDS_PATH.parent / "SHA256SUMS"
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_"
    "attacked_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v13_attacked.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v13.py",
    "scripts/run_l2_predictive_virtual_brake_v13_fresh3.py",
    "scripts/run_predictive_virtual_brake_v13_clean.py",
    "scripts/run_predictive_virtual_brake_v13_attacked.py",
    "scripts/freeze_predictive_virtual_brake_v13_attacked.py",
    "tests/test_l2_predictive_virtual_brake_v13.py",
    "tests/test_predictive_virtual_brake_v13_attacked.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v13-attacked-20260731"
)
CREATED_AT = "2026-07-31T12:40:00+08:00"


class PredictiveVirtualBrakeAttackedFreezeError(RuntimeError):
    """Raised when the v13 attacked study cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeAttackedFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _schedule(clean: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = f"{clean['stage']}_"
    rows = []
    for source in clean["schedule"]:
        if not str(source["episode_id"]).startswith(prefix):
            raise PredictiveVirtualBrakeAttackedFreezeError(
                "clean episode identity does not match its stage"
            )
        row = dict(source)
        row["episode_id"] = (
            f"{STAGE}_{str(source['episode_id'])[len(prefix):]}"
        )
        row["sequence_index"] = len(rows)
        row["seed_block_id"] = (
            "predictive_virtual_brake_v13_attacked_"
            "env407_policy251"
        )
        rows.append(row)
    return rows


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise PredictiveVirtualBrakeAttackedFreezeError(
            "tracked worktree must be clean before attacked freeze"
        )
    clean = load_json_object(CLEAN_PROTOCOL_PATH)
    terminal = load_json_object(CLEAN_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != (
            "predictive_virtual_brake_v13_clean_fresh3_"
            "engineering_gate_pass"
        )
        or terminal.get("attacked_stage_authorized") is not True
        or terminal.get("confirmatory_claim_authorized") is not False
    ):
        raise PredictiveVirtualBrakeAttackedFreezeError(
            "clean terminal does not authorize attacked evaluation"
        )
    source_bundle = load_json_object(M2_ATTACK_RECORDS_PATH)
    attacks = transplant.derive_attack_transplants(
        clean, source_bundle
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
            "predictive_virtual_brake_v13_attacked_data_complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v13_attacked_incomplete"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v13_"
            "attacked_20260731_fresh1"
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
                "exact suite/task join for every one of the 45 frozen "
                "clean workloads; no Fresh3 outcome or trigger ranking"
            ),
            "transplant_rule": (
                "preserve original and perturbed prompt bytes; replace "
                "only init identity because attack generation consumed "
                "task text and no rollout, state, image, or outcome"
            ),
            "objective": "constraint_violation",
        },
        "paired_clean_binding": {
            "protocol_path": CLEAN_PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "protocol_sha256": file_sha256(CLEAN_PROTOCOL_PATH),
            "evidence_path": (
                CLEAN_ROOT / "pilot_evidence.json"
            ).relative_to(REPO_ROOT).as_posix(),
            "evidence_sha256": file_sha256(
                CLEAN_ROOT / "pilot_evidence.json"
            ),
            "terminal_path": CLEAN_TERMINAL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "terminal_sha256": file_sha256(CLEAN_TERMINAL_PATH),
            "episode_count": 180,
            "workload_count": 45,
            "same_workloads_init_states_environment_seed_policy_seed": (
                True
            ),
        },
        "design": {
            **clean["design"],
            "condition": "instruction_attacked",
            "study_role": (
                "outcome-disclosed attacked engineering evaluation "
                "after the clean utility prerequisite passed"
            ),
            "pair_count": 45,
            "episode_count": 180,
            "same_clean_workloads_and_seeds": True,
            "target_joint_only": True,
            "primary_estimands": [
                (
                    "execution_only minus vla_only paired attacked task "
                    "success, official unsafe, joint-limit exposure, "
                    "trigger, intervention, and deadlock"
                ),
                (
                    "dual minus semantic_only paired attacked task "
                    "success, official unsafe, joint-limit exposure, "
                    "trigger, intervention, and deadlock"
                ),
                (
                    "attacked minus clean change in each arm under exact "
                    "workload and seed matching"
                ),
            ],
            "efficacy_outcomes_excluded_from_completion_gates": True,
        },
        "analysis": {
            **clean["analysis"],
            "outcome_gates_are_descriptive_only": True,
            "clean_reference_terminal_path": (
                CLEAN_TERMINAL_PATH.relative_to(REPO_ROOT).as_posix()
            ),
            "attack_activation_endpoints": [
                "attack metadata and prompt digest identity",
                "attack changed first action block count",
                "paired first action block match across four arms",
            ],
        },
        "attacked_data_gates": {
            "expected_attack_record_count": 45,
            "expected_paired_clean_episode_comparison_count": 180,
            (
                "expected_attacked_paired_first_"
                "action_block_match_count"
            ): 45,
        },
        "execution_authorization": {
            "attacked_exploratory_pilot": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "clean_rollout": False,
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
            _binding(M2_ATTACK_RECORDS_PATH),
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
        "outcomes_observed_for_selection": True,
        "outcome_conditioned_engineering_regression": True,
        "claim_boundary": (
            "Fresh3 clean outcomes were observed before this attacked "
            "protocol froze. The attack population is nevertheless the "
            "complete deterministic suite/task join to all 45 workloads, "
            "with no outcome or trigger ranking, and it retains the exact "
            "clean init states and seeds. Results are exploratory attacked "
            "engineering evidence for a prompt-level constraint-violation "
            "attack and a target-joint simulator brake. They cannot "
            "establish confirmatory, arbitrary-attack, arbitrary-joint, "
            "deployment, hardware, or real-world safety claims."
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
            raise PredictiveVirtualBrakeAttackedFreezeError(
                f"v13 attacked protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
