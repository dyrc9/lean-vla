#!/usr/bin/env python3
"""Qualify four 10-step L1 ActionBlock candidates without outcomes."""

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
from scripts import run_four_arm_v4_l1_block10_qualification as block10  # noqa: E402
from scripts import run_four_arm_v4_l1_repair_qualification_v2 as launch  # noqa: E402


base = block10.base
PROTOCOL_SCHEMA = (
    "proofalign.four-arm-v4-l1-block10-k4-qualification-protocol.v1"
)
ROW_SCHEMA = (
    "proofalign.four-arm-v4-l1-block10-k4-qualification-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.four-arm-v4-l1-block10-k4-qualification-summary.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_k4_qualification_protocol.json"
)
PARENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_terminal_summary.json"
)
_BASE_PREFLIGHT = base.preflight
_BASE_BUILD_SUMMARY = block10._BASE_BUILD_SUMMARY


class Block10K4QualificationError(RuntimeError):
    """Raised when the H10×K4 qualification must fail closed."""


def _eligible(
    checked: dict[str, Any],
    *,
    min_progress_m: float,
    max_projection_l2: float,
) -> bool:
    return bool(
        checked["known"]
        and checked["semantic_compatible"]
        and checked["post_projection_compatible"]
        and not checked["hard_violation_atoms"]
        and checked["progress_margin"] >= min_progress_m
        and checked["projection_l2"] <= max_projection_l2
    )


class Block10K4CandidatePolicy(block10.Block10CandidatePolicy):
    """Record matched cumulative K=1/2/4 coverage for H=10."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        if self.wrapper is None:
            raise Block10K4QualificationError(
                "H10×K4 audit lacks a semantic wrapper"
            )
        audit = self.audits[-1]
        candidates = audit["candidates"]
        if len(candidates) != 4:
            raise Block10K4QualificationError(
                "H10×K4 source candidate count differs"
            )
        returned_index = int(
            audit["returned_source_candidate_index"]
        )
        primary = dict(candidates[returned_index]["checked"])
        primary["eligible_under_fixed_gate"] = _eligible(
            primary,
            min_progress_m=self.wrapper.min_progress_margin,
            max_projection_l2=self.wrapper.max_projection_l2,
        )
        primary["steps"] = 10
        audit["matched_block_size_shadow"]["assessments"]["10"] = (
            primary
        )
        cumulative = {}
        for count in (1, 2, 4):
            prefix = candidates[:count]
            cumulative[str(count)] = {
                "candidate_count": count,
                "eligible_candidate_count": sum(
                    _eligible(
                        candidate["checked"],
                        min_progress_m=(
                            self.wrapper.min_progress_margin
                        ),
                        max_projection_l2=(
                            self.wrapper.max_projection_l2
                        ),
                    )
                    for candidate in prefix
                ),
                "at_least_one_eligible": any(
                    _eligible(
                        candidate["checked"],
                        min_progress_m=(
                            self.wrapper.min_progress_margin
                        ),
                        max_projection_l2=(
                            self.wrapper.max_projection_l2
                        ),
                    )
                    for candidate in prefix
                ),
            }
        audit["matched_candidate_count_shadow"] = {
            "schema": (
                "proofalign.semantic-matched-candidate-count-shadow.v1"
            ),
            "action_block_steps": 10,
            "primary_candidate_count": 4,
            "shadow_candidate_counts": (1, 2),
            "source_policy_call_count": 4,
            "fixed_min_progress_m": self.wrapper.min_progress_margin,
            "fixed_max_projection_l2": self.wrapper.max_projection_l2,
            "cumulative": cumulative,
        }
        return result


def _validate_design(protocol: dict[str, Any]) -> None:
    repair = protocol["repair"]
    population = protocol["qualification_population"]
    pairs = population["frozen_pairs"]
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise Block10K4QualificationError(
            "H10×K4 protocol schema differs"
        )
    if protocol.get("execution_authorization") != {
        "qualification_probe": True,
        "task_outcome_rollout": False,
        "clean_rollout": False,
        "attacked_rollout": False,
    }:
        raise Block10K4QualificationError(
            "H10×K4 execution authorization differs"
        )
    if (
        repair.get("semantic_candidate_count") != 4
        or repair.get("replan_steps") != 10
        or repair.get("checked_action_block_steps") != 10
        or repair.get("min_progress_m") != 0.002
        or repair.get("threshold_changed") is not False
    ):
        raise Block10K4QualificationError(
            "frozen H10×K4 design differs"
        )
    if (
        len(pairs) != 45
        or len({pair["base_pair_id"] for pair in pairs}) != 45
        or population.get("base_pair_count") != 45
        or population.get("environment_seed") != 97
        or population.get("policy_seed") != 37
        or population.get("policy_inference_count") != 180
        or population.get("policy_conditioned_env_step_count") != 0
    ):
        raise Block10K4QualificationError(
            "H10×K4 qualification population differs"
        )


def validate_protocol(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> None:
    _validate_design(protocol)
    parent = protocol["parent_block10_terminal"]
    if (
        Path(parent["path"]) != PARENT_TERMINAL_PATH.relative_to(
            REPO_ROOT
        )
        or file_sha256(PARENT_TERMINAL_PATH) != parent["sha256"]
    ):
        raise Block10K4QualificationError(
            "parent Block-10 terminal binding differs"
        )
    terminal = load_json_object(PARENT_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != "l1_block10_initial_availability_qualification_nonpass"
        or terminal.get("qualification_pass") is not False
    ):
        raise Block10K4QualificationError(
            "parent Block-10 result is not frozen nonpass"
        )
    source = protocol["source"]
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            source["repository_commit"],
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise Block10K4QualificationError(
            "H10×K4 source commit is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise Block10K4QualificationError(
                f"H10×K4 source binding differs: {relative}"
            )


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    gpu: int | None,
) -> dict[str, Any]:
    original_validator = base.validate_protocol
    base.validate_protocol = validate_protocol
    try:
        report = _BASE_PREFLIGHT(
            protocol,
            protocol_path=protocol_path,
            gpu=gpu,
        )
    finally:
        base.validate_protocol = original_validator
    blockers = list(report["blockers"])
    device_state = None
    if gpu is not None:
        try:
            device_state = launch._runtime_device_state(gpu)
        except BaseException as exc:
            blockers.append(
                f"runtime device preflight failed: {type(exc).__name__}: {exc}"
            )
    return {
        **report,
        "schema": (
            "proofalign.four-arm-v4-l1-block10-k4-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "runtime_device": device_state,
    }


def build_summary(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = _BASE_BUILD_SUMMARY(protocol, rows)
    passed = bool(summary["qualification_pass"])
    return {
        **summary,
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "l1_block10_k4_initial_availability_qualification_pass"
            if passed
            else "l1_block10_k4_initial_availability_qualification_nonpass"
        ),
        "checked_action_block_steps": 10,
        "semantic_candidate_count": 4,
        "parent_block10_k1_nonpass_unchanged": True,
        "claim_boundary": (
            "This post-outcome H10×K4 qualification measures initial-state "
            "benchmark geometry and four 10-step source ActionBlocks. It "
            "observes no task outcome, dispatches no policy action, and "
            "does not establish trajectory-level clean retention, attacked "
            "efficacy, deployment perception, hardware safety, or a "
            "confirmatory result."
        ),
    }


def _install_runtime() -> None:
    base.validate_protocol = validate_protocol
    base.preflight = preflight
    base.build_summary = build_summary
    base.ROW_SCHEMA = ROW_SCHEMA
    base.BoundedCandidatePolicy = Block10K4CandidatePolicy
    base._configure_single_gpu = launch._configure_single_gpu
    base._args = launch._args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    parser.add_argument("--gpu", type=int)
    args = parser.parse_args(argv)
    if sum(
        (args.preflight, args.execute, args.validate_results)
    ) != 1:
        parser.error(
            "choose exactly one of --preflight, --execute, "
            "or --validate-results"
        )
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    _install_runtime()
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    elif args.execute:
        if args.gpu is None:
            parser.error("--execute requires --gpu")
        payload = base.execute(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    else:
        payload = base.validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
