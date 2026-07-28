#!/usr/bin/env python3
"""Qualify a single-candidate 10-step L1 ActionBlock without outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_four_arm_v4_l1_repair_qualification as base  # noqa: E402
from scripts import run_four_arm_v4_l1_repair_qualification_v2 as launch  # noqa: E402
from scripts.run_l2_execution_attack_eval_v2 import (  # noqa: E402
    BoundedCandidatePolicy,
)


PROTOCOL_SCHEMA = (
    "proofalign.four-arm-v4-l1-block10-qualification-protocol.v1"
)
ROW_SCHEMA = "proofalign.four-arm-v4-l1-block10-qualification-row.v1"
SUMMARY_SCHEMA = (
    "proofalign.four-arm-v4-l1-block10-qualification-summary.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_qualification_protocol.json"
)
PARENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_terminal_summary.json"
)
_BASE_PREFLIGHT = base.preflight
_BASE_BUILD_SUMMARY = base.build_summary


class Block10QualificationError(RuntimeError):
    """Raised when the Block-10 qualification must fail closed."""


class Block10CandidatePolicy(BoundedCandidatePolicy):
    """Gate on H=10 and record matched H=2/5/10 shadow assessments."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        if self.wrapper is None or self.request is None:
            raise Block10QualificationError(
                "Block-10 shadow assessment lacks semantic bindings"
            )
        chunk = np.asarray(result["actions"], dtype=np.float64)
        if chunk.ndim != 2 or len(chunk) < 10:
            raise Block10QualificationError(
                "Block-10 source chunk is shorter than ten actions"
            )
        primary = self.audits[-1]["candidates"][0]["checked"]
        assessments: dict[str, dict[str, Any]] = {"10": dict(primary)}
        for steps in (2, 5):
            nominal = chunk[:steps]
            final = np.clip(nominal, -1.0, 1.0)
            checked, local = self.wrapper.checker.checked_candidate(
                candidate_index=0,
                semantic_subtask_digest=(
                    self.request.artifact.artifact_digest
                ),
                semantic_subtask=(
                    self.request.artifact.selected_subtask
                ),
                observation=self.request.local_observation,
                nominal_command=tuple(
                    float(value) for value in nominal.reshape(-1)
                ),
                final_command=tuple(
                    float(value) for value in final.reshape(-1)
                ),
                command_shape=tuple(nominal.shape),
                expected_state_epoch=self.request.context.state_epoch,
                release_destination=self.request.release_destination,
            )
            assessments[str(steps)] = {
                "known": checked.known,
                "semantic_compatible": checked.semantic_compatible,
                "post_projection_compatible": (
                    checked.post_projection_compatible
                ),
                "hard_violation_atoms": checked.hard_violation_atoms,
                "progress_margin": checked.progress_margin,
                "projection_l2": checked.projection_l2,
                "unknown_reason": local.unknown_reason,
            }
        for steps, assessment in assessments.items():
            assessment["eligible_under_fixed_gate"] = bool(
                assessment["known"]
                and assessment["semantic_compatible"]
                and assessment["post_projection_compatible"]
                and not assessment["hard_violation_atoms"]
                and assessment["progress_margin"]
                >= self.wrapper.min_progress_margin
                and assessment["projection_l2"]
                <= self.wrapper.max_projection_l2
            )
            assessment["steps"] = int(steps)
        self.audits[-1]["matched_block_size_shadow"] = {
            "schema": (
                "proofalign.semantic-matched-block-size-shadow.v1"
            ),
            "source_policy_call_count": 1,
            "source_policy_chunk_sha256": self.audits[-1][
                "returned_source_policy_chunk_sha256"
            ],
            "primary_gate_steps": 10,
            "shadow_only_steps": (2, 5),
            "fixed_min_progress_m": self.wrapper.min_progress_margin,
            "fixed_max_projection_l2": self.wrapper.max_projection_l2,
            "assessments": assessments,
        }
        return result


def _validate_design(protocol: dict[str, Any]) -> None:
    repair = protocol["repair"]
    population = protocol["qualification_population"]
    pairs = population["frozen_pairs"]
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise Block10QualificationError(
            "Block-10 qualification protocol schema differs"
        )
    if protocol.get("execution_authorization") != {
        "qualification_probe": True,
        "task_outcome_rollout": False,
        "clean_rollout": False,
        "attacked_rollout": False,
    }:
        raise Block10QualificationError(
            "Block-10 execution authorization differs"
        )
    if (
        repair.get("semantic_candidate_count") != 1
        or repair.get("replan_steps") != 10
        or repair.get("checked_action_block_steps") != 10
        or repair.get("dispatched_action_block_steps_if_later_authorized")
        != 10
        or repair.get("min_progress_m") != 0.002
        or repair.get("threshold_changed") is not False
    ):
        raise Block10QualificationError(
            "frozen Block-10 design differs"
        )
    if (
        len(pairs) != 45
        or len({pair["base_pair_id"] for pair in pairs}) != 45
        or population.get("base_pair_count") != 45
        or population.get("environment_seed") != 83
        or population.get("policy_seed") != 29
        or population.get("policy_inference_count") != 45
        or population.get("policy_conditioned_env_step_count") != 0
    ):
        raise Block10QualificationError(
            "Block-10 qualification population differs"
        )


def validate_protocol(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> None:
    _validate_design(protocol)
    parent = protocol["parent_l1_repair_terminal"]
    if (
        Path(parent["path"]) != PARENT_TERMINAL_PATH.relative_to(REPO_ROOT)
        or file_sha256(PARENT_TERMINAL_PATH) != parent["sha256"]
    ):
        raise Block10QualificationError(
            "parent L1 repair terminal binding differs"
        )
    terminal = load_json_object(PARENT_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != "l1_repair_initial_availability_qualification_nonpass"
        or terminal.get("qualification_pass") is not False
    ):
        raise Block10QualificationError(
            "parent L1 repair result is not the frozen nonpass"
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
        raise Block10QualificationError(
            "Block-10 source commit is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise Block10QualificationError(
                f"Block-10 source binding differs: {relative}"
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
            "proofalign.four-arm-v4-l1-block10-qualification-preflight.v1"
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
            "l1_block10_initial_availability_qualification_pass"
            if passed
            else "l1_block10_initial_availability_qualification_nonpass"
        ),
        "checked_action_block_steps": 10,
        "semantic_candidate_count": 1,
        "parent_block5_k4_nonpass_unchanged": True,
        "claim_boundary": (
            "This post-outcome Block-10 qualification measures initial-state "
            "benchmark geometry and one 10-step checked source ActionBlock. "
            "It observes no task outcome, dispatches no policy action, and "
            "does not establish trajectory-level clean retention, attacked "
            "efficacy, deployment perception, hardware safety, or a "
            "confirmatory result."
        ),
    }


def _install_block10_runtime() -> None:
    base.validate_protocol = validate_protocol
    base.preflight = preflight
    base.build_summary = build_summary
    base.ROW_SCHEMA = ROW_SCHEMA
    base.BoundedCandidatePolicy = Block10CandidatePolicy
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
    _install_block10_runtime()
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
