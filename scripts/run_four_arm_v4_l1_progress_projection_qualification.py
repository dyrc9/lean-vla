#!/usr/bin/env python3
"""Qualify bounded semantic-progress projection without task outcomes."""

from __future__ import annotations

import argparse
from collections import Counter
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
from proofalign.semantic_progress_projection import (  # noqa: E402
    SemanticProgressProjectionConfig,
    project_semantic_progress,
)
from scripts import run_four_arm_v4_l1_block10_k4_qualification as parent  # noqa: E402
from scripts import run_four_arm_v4_l1_repair_qualification_v2 as launch  # noqa: E402
from scripts import run_l2_execution_attack_eval_v2 as candidate_runtime  # noqa: E402


base = parent.base
PROTOCOL_SCHEMA = (
    "proofalign.four-arm-v4-l1-progress-projection-"
    "qualification-protocol.v1"
)
ROW_SCHEMA = (
    "proofalign.four-arm-v4-l1-progress-projection-qualification-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.four-arm-v4-l1-progress-projection-"
    "qualification-summary.v1"
)
AUDIT_SCHEMA = "proofalign.semantic-progress-projection-selection.v1"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)
PARENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json"
)
_BASE_PREFLIGHT = base.preflight
_BASE_BUILD_SUMMARY = parent._BASE_BUILD_SUMMARY


class ProgressProjectionQualificationError(RuntimeError):
    """Raised when the progress-projection qualification fails closed."""


def _checked_payload(
    checked: Any,
    local: Any,
    *,
    projection_l2: float,
    eligible: bool,
) -> dict[str, Any]:
    return {
        "known": checked.known,
        "semantic_compatible": checked.semantic_compatible,
        "post_projection_compatible": (
            checked.post_projection_compatible
        ),
        "hard_violation_atoms": checked.hard_violation_atoms,
        "progress_margin": checked.progress_margin,
        "projection_l2": float(projection_l2),
        "unknown_reason": local.unknown_reason,
        "eligible_under_fixed_gate": eligible,
    }


class ProgressProjectionCandidatePolicy(
    candidate_runtime.BoundedCandidatePolicy
):
    """Apply one bounded, translation-only repair for the already-fixed Z_t."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        if self.candidate_count != 1 or self.replan_steps != 10:
            raise ProgressProjectionQualificationError(
                "progress projection requires frozen H10×K1"
            )
        if self.wrapper is None or self.request is None:
            raise ProgressProjectionQualificationError(
                "progress projection lacks semantic bindings"
            )
        source_result = self.inner.infer(element)
        source_chunk = np.asarray(
            source_result["actions"],
            dtype=np.float64,
        )
        if source_chunk.ndim != 2 or source_chunk.shape[1] != 7:
            raise ProgressProjectionQualificationError(
                "source policy returned a non-LIBERO ActionBlock"
            )
        if len(source_chunk) < self.replan_steps:
            raise ProgressProjectionQualificationError(
                "source policy chunk is shorter than ten actions"
            )
        nominal = np.asarray(
            source_chunk[: self.replan_steps],
            dtype=np.float64,
        )
        envelope = np.clip(nominal, -1.0, 1.0)
        wrapper = self.wrapper
        request = self.request
        nominal_checked, nominal_local = (
            wrapper.checker.checked_candidate(
                candidate_index=0,
                semantic_subtask_digest=(
                    request.artifact.artifact_digest
                ),
                semantic_subtask=request.artifact.selected_subtask,
                observation=request.local_observation,
                nominal_command=tuple(
                    float(value) for value in nominal.reshape(-1)
                ),
                final_command=tuple(
                    float(value) for value in envelope.reshape(-1)
                ),
                command_shape=tuple(nominal.shape),
                expected_state_epoch=request.context.state_epoch,
                release_destination=request.release_destination,
            )
        )
        config = SemanticProgressProjectionConfig(
            min_terminal_progress_m=wrapper.min_progress_margin,
            max_projection_l2=0.05,
            translation_scale_m=(
                wrapper.checker.config.translation_scale_m
            ),
        )
        projection = project_semantic_progress(
            semantic_subtask=request.artifact.selected_subtask,
            observation=request.local_observation,
            nominal_command=tuple(
                float(value) for value in nominal.reshape(-1)
            ),
            command_shape=tuple(nominal.shape),
            config=config,
        )
        final_checked = None
        final_local = None
        final = None
        if projection.final_command is not None:
            final = np.asarray(
                projection.final_command,
                dtype=np.float64,
            ).reshape(nominal.shape)
            final_checked, final_local = (
                wrapper.checker.checked_candidate(
                    candidate_index=0,
                    semantic_subtask_digest=(
                        request.artifact.artifact_digest
                    ),
                    semantic_subtask=(
                        request.artifact.selected_subtask
                    ),
                    observation=request.local_observation,
                    nominal_command=projection.final_command,
                    final_command=projection.final_command,
                    command_shape=tuple(final.shape),
                    expected_state_epoch=request.context.state_epoch,
                    release_destination=request.release_destination,
                )
            )
        eligible = bool(
            projection.accepted
            and projection.projection_l2 is not None
            and projection.projection_l2 <= config.max_projection_l2
            and projection.final_terminal_progress_m is not None
            and projection.final_terminal_progress_m
            >= config.min_terminal_progress_m
            and nominal_checked.known
            and not nominal_checked.hard_violation_atoms
            and final_checked is not None
            and final_checked.known
            and final_checked.semantic_compatible
            and final_checked.post_projection_compatible
            and not final_checked.hard_violation_atoms
        )
        returned_chunk = source_chunk.copy()
        if eligible:
            assert final is not None
            returned_chunk[: self.replan_steps] = final
        selected_index = 0 if eligible else None
        final_payload = (
            _checked_payload(
                final_checked,
                final_local,
                projection_l2=float(projection.projection_l2),
                eligible=eligible,
            )
            if final_checked is not None
            and final_local is not None
            and projection.projection_l2 is not None
            else {
                "known": False,
                "semantic_compatible": False,
                "post_projection_compatible": False,
                "hard_violation_atoms": (),
                "progress_margin": -1.0e30,
                "projection_l2": None,
                "unknown_reason": projection.reason,
                "eligible_under_fixed_gate": False,
            }
        )
        self.audits.append(
            {
                "schema": AUDIT_SCHEMA,
                "candidate_count": 1,
                "replan_steps": 10,
                "selection_reason": (
                    "bounded_progress_projection_eligible"
                    if eligible
                    else "no_feasible_projected_action_block"
                ),
                "eligible_selected_source_candidate_index": (
                    selected_index
                ),
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": not eligible,
                "returned_source_policy_chunk_sha256": (
                    candidate_runtime._array_digest(source_chunk)
                ),
                "returned_action_chunk_sha256": (
                    candidate_runtime._array_digest(returned_chunk)
                ),
                "candidates": [
                    {
                        "source_candidate_index": 0,
                        "source_policy_chunk_sha256": (
                            candidate_runtime._array_digest(source_chunk)
                        ),
                        "source_policy_chunk_shape": tuple(
                            source_chunk.shape
                        ),
                        "nominal_checked": _checked_payload(
                            nominal_checked,
                            nominal_local,
                            projection_l2=float(
                                np.linalg.norm(
                                    nominal.reshape(-1)
                                    - envelope.reshape(-1)
                                )
                            ),
                            eligible=False,
                        ),
                        "progress_projection": (
                            projection.audit_payload()
                        ),
                        "checked": final_payload,
                    }
                ],
            }
        )
        return {**source_result, "actions": returned_chunk}


def _validate_design(protocol: dict[str, Any]) -> None:
    repair = protocol["repair"]
    population = protocol["qualification_population"]
    pairs = population["frozen_pairs"]
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise ProgressProjectionQualificationError(
            "progress-projection protocol schema differs"
        )
    if protocol.get("execution_authorization") != {
        "qualification_probe": True,
        "task_outcome_rollout": False,
        "clean_rollout": False,
        "attacked_rollout": False,
    }:
        raise ProgressProjectionQualificationError(
            "progress-projection execution authorization differs"
        )
    if (
        repair.get("semantic_candidate_count") != 1
        or repair.get("replan_steps") != 10
        or repair.get("checked_action_block_steps") != 10
        or repair.get("min_progress_m") != 0.002
        or repair.get("threshold_changed") is not False
        or repair.get("semantic_progress_projection") != {
            "enabled": True,
            "max_projection_l2": 0.05,
            "min_terminal_progress_m": 0.002,
            "preserve_rotation_and_gripper": True,
            "reject_nominal_hard_violations": True,
            "supported_verbs": ["pick_up", "move", "place"],
            "translation_only": True,
        }
    ):
        raise ProgressProjectionQualificationError(
            "frozen progress-projection design differs"
        )
    if (
        len(pairs) != 45
        or len({pair["base_pair_id"] for pair in pairs}) != 45
        or population.get("base_pair_count") != 45
        or population.get("environment_seed") != 109
        or population.get("policy_seed") != 41
        or population.get("policy_inference_count") != 45
        or population.get("policy_conditioned_env_step_count") != 0
    ):
        raise ProgressProjectionQualificationError(
            "progress-projection qualification population differs"
        )


def validate_protocol(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> None:
    _validate_design(protocol)
    parent_binding = protocol["parent_block10_k4_terminal"]
    if (
        Path(parent_binding["path"])
        != PARENT_TERMINAL_PATH.relative_to(REPO_ROOT)
        or file_sha256(PARENT_TERMINAL_PATH)
        != parent_binding["sha256"]
    ):
        raise ProgressProjectionQualificationError(
            "parent H10×K4 terminal binding differs"
        )
    terminal = load_json_object(PARENT_TERMINAL_PATH)
    if (
        terminal.get("classification")
        != "l1_block10_k4_initial_availability_qualification_nonpass"
        or terminal.get("qualification_pass") is not False
    ):
        raise ProgressProjectionQualificationError(
            "parent H10×K4 result is not the frozen nonpass"
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
        raise ProgressProjectionQualificationError(
            "progress-projection source commit is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ProgressProjectionQualificationError(
                f"progress-projection source binding differs: {relative}"
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
            "proofalign.four-arm-v4-l1-progress-projection-preflight.v1"
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
    projections = [
        row["candidate_selection"]["candidates"][0][
            "progress_projection"
        ]
        for row in rows
        if row.get("candidate_selection") is not None
    ]
    reasons = Counter(item["reason"] for item in projections)
    accepted = [item for item in projections if item["accepted"]]
    applied = [item for item in accepted if item["projected"]]
    return {
        **summary,
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "l1_progress_projection_initial_availability_qualification_pass"
            if passed
            else "l1_progress_projection_initial_availability_qualification_nonpass"
        ),
        "checked_action_block_steps": 10,
        "semantic_candidate_count": 1,
        "projection_attempt_count": len(projections),
        "projection_accepted_count": len(accepted),
        "projection_applied_count": len(applied),
        "projection_reason_counts": dict(sorted(reasons.items())),
        "maximum_accepted_projection_l2": (
            max(float(item["projection_l2"]) for item in accepted)
            if accepted
            else None
        ),
        "parent_h10_k4_nonpass_unchanged": True,
        "claim_boundary": (
            "This post-outcome successor measures initial-state availability "
            "of a fixed-Z, translation-only, bounded minimum-L2 progress "
            "projection. It dispatches no policy action, observes no task "
            "outcome, and cannot establish clean trajectory retention, "
            "attacked efficacy, deployment perception, hardware safety, or "
            "a confirmatory result."
        ),
    }


def _install_runtime() -> None:
    base.validate_protocol = validate_protocol
    base.preflight = preflight
    base.build_summary = build_summary
    base.ROW_SCHEMA = ROW_SCHEMA
    base.BoundedCandidatePolicy = ProgressProjectionCandidatePolicy
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
