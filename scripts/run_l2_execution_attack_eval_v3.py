#!/usr/bin/env python3
"""Online H10 progress projection over the frozen v2 semantic runner.

The fixed semantic subtask is never inferred from an action or relabeled.
For pick_up/move/place, one pi0.5 H10 source block receives at most one
translation-only bounded progress projection and is then rechecked.  Verbs
outside that projector's scope (notably release) may pass only when the
unmodified, numeric-enveloped source block already passes the frozen checker.
"""

from __future__ import annotations

import argparse
from math import sqrt
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.semantic_action_selection import (  # noqa: E402
    select_checked_action_block,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    parse_semantic_subtask,
)
from proofalign.semantic_progress_projection import (  # noqa: E402
    PROJECTION_SCHEMA,
    SemanticProgressProjectionConfig,
    project_semantic_progress,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v2 as v2  # noqa: E402


AUDIT_SCHEMA = "proofalign.semantic-progress-projection-selection.v3"
BYPASS_SCHEMA = "proofalign.semantic-progress-projection-bypass.v1"
RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v3"


class OnlineProgressProjectionError(RuntimeError):
    """Raised when online progress projection cannot preserve its boundary."""


def _l2(left: np.ndarray, right: np.ndarray) -> float:
    delta = left.reshape(-1) - right.reshape(-1)
    return sqrt(float(np.dot(delta, delta)))


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
        "eligible_under_fixed_gate": bool(eligible),
    }


def _bypass_payload(
    *,
    accepted: bool,
    reason: str,
    semantic_subtask: str,
    observation_digest: str,
    command_shape: tuple[int, int],
    projection_l2: float | None,
) -> dict[str, Any]:
    return {
        "schema": BYPASS_SCHEMA,
        "projector_schema": PROJECTION_SCHEMA,
        "accepted": accepted,
        "projected": False,
        "reason": reason,
        "semantic_subtask": semantic_subtask,
        "observation_digest": observation_digest,
        "command_shape": command_shape,
        "nominal_terminal_progress_m": None,
        "final_terminal_progress_m": None,
        "projection_l2": projection_l2,
        "config_digest": None,
        "goal_entity_id": None,
        "witness_digest": None,
    }


class OnlineProgressProjectionCandidatePolicy(v2.BoundedCandidatePolicy):
    """Generate one H10 block and authorize only the exact rechecked result."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        if self.candidate_count != 1 or self.replan_steps != 10:
            raise OnlineProgressProjectionError(
                "online progress projection requires frozen H10xK1"
            )
        wrapper = self.wrapper
        request = self.request
        if wrapper is None or request is None:
            raise OnlineProgressProjectionError(
                "online projection lacks semantic bindings"
            )
        source_result = self.inner.infer(element)
        source_chunk = np.asarray(
            source_result["actions"],
            dtype=np.float64,
        )
        if (
            source_chunk.ndim != 2
            or source_chunk.shape[1] != 7
            or len(source_chunk) < self.replan_steps
            or not np.isfinite(source_chunk).all()
        ):
            raise OnlineProgressProjectionError(
                "source policy returned an invalid LIBERO ActionBlock"
            )
        nominal = np.asarray(
            source_chunk[: self.replan_steps],
            dtype=np.float64,
        )
        envelope = np.clip(nominal, -1.0, 1.0)
        shape = tuple(nominal.shape)
        semantic_subtask = request.artifact.selected_subtask
        nominal_checked, nominal_local = wrapper.checker.checked_candidate(
            candidate_index=0,
            semantic_subtask_digest=request.artifact.artifact_digest,
            semantic_subtask=semantic_subtask,
            observation=request.local_observation,
            nominal_command=tuple(
                float(value) for value in nominal.reshape(-1)
            ),
            final_command=tuple(
                float(value) for value in envelope.reshape(-1)
            ),
            command_shape=shape,
            expected_state_epoch=request.context.state_epoch,
            release_destination=request.release_destination,
        )
        nominal_selection = select_checked_action_block(
            (nominal_checked,),
            expected_semantic_subtask_digest=(
                request.artifact.artifact_digest
            ),
            min_progress_margin=wrapper.min_progress_margin,
            max_projection_l2=wrapper.max_projection_l2,
        )
        nominal_eligible = nominal_selection.selected is not None
        verb = parse_semantic_subtask(semantic_subtask).verb
        config = SemanticProgressProjectionConfig(
            min_terminal_progress_m=wrapper.min_progress_margin,
            max_projection_l2=0.05,
            translation_scale_m=(
                wrapper.checker.config.translation_scale_m
            ),
        )

        final: np.ndarray | None = None
        final_checked = None
        final_local = None
        eligible = False
        if nominal_checked.hard_violation_atoms:
            projection_payload = _bypass_payload(
                accepted=False,
                reason="nominal_hard_violation_rejected_before_projection",
                semantic_subtask=semantic_subtask,
                observation_digest=(
                    request.local_observation.observation_digest
                ),
                command_shape=shape,
                projection_l2=None,
            )
        elif verb not in config.supported_verbs:
            eligible = nominal_eligible
            if eligible:
                final = envelope
                final_checked = nominal_checked
                final_local = nominal_local
            projection_payload = _bypass_payload(
                accepted=eligible,
                reason=(
                    f"nominal_checker_eligible_without_projection:{verb}"
                    if eligible
                    else f"unsupported_verb_not_nominally_eligible:{verb}"
                ),
                semantic_subtask=semantic_subtask,
                observation_digest=(
                    request.local_observation.observation_digest
                ),
                command_shape=shape,
                projection_l2=(
                    _l2(nominal, envelope) if eligible else None
                ),
            )
        else:
            projection = project_semantic_progress(
                semantic_subtask=semantic_subtask,
                observation=request.local_observation,
                nominal_command=tuple(
                    float(value) for value in nominal.reshape(-1)
                ),
                command_shape=shape,
                config=config,
            )
            projection_payload = projection.audit_payload()
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
                        semantic_subtask=semantic_subtask,
                        observation=request.local_observation,
                        nominal_command=projection.final_command,
                        final_command=projection.final_command,
                        command_shape=shape,
                        expected_state_epoch=request.context.state_epoch,
                        release_destination=request.release_destination,
                    )
                )
            eligible = bool(
                projection.accepted
                and projection.projection_l2 is not None
                and projection.projection_l2
                <= config.max_projection_l2
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
        if (
            final_checked is not None
            and final_local is not None
            and final is not None
        ):
            final_payload = _checked_payload(
                final_checked,
                final_local,
                projection_l2=_l2(nominal, final),
                eligible=eligible,
            )
        else:
            final_payload = {
                "known": False,
                "semantic_compatible": False,
                "post_projection_compatible": False,
                "hard_violation_atoms": (),
                "progress_margin": -1.0e30,
                "projection_l2": None,
                "unknown_reason": projection_payload["reason"],
                "eligible_under_fixed_gate": False,
            }
        self.audits.append(
            {
                "schema": AUDIT_SCHEMA,
                "candidate_count": 1,
                "replan_steps": 10,
                "fixed_semantic_subtask": semantic_subtask,
                "selection_reason": (
                    "online_progress_projection_eligible"
                    if eligible and verb in config.supported_verbs
                    else "nominal_checker_bypass_eligible"
                    if eligible
                    else "no_feasible_action_block"
                ),
                "eligible_selected_source_candidate_index": (
                    0 if eligible else None
                ),
                "returned_source_candidate_index": 0,
                "fallback_for_fail_closed_recheck": not eligible,
                "returned_source_policy_chunk_sha256": (
                    v2._array_digest(source_chunk)
                ),
                "returned_action_chunk_sha256": (
                    v2._array_digest(returned_chunk)
                ),
                "candidates": [
                    {
                        "source_candidate_index": 0,
                        "source_policy_chunk_sha256": (
                            v2._array_digest(source_chunk)
                        ),
                        "source_policy_chunk_shape": tuple(
                            source_chunk.shape
                        ),
                        "nominal_checked": _checked_payload(
                            nominal_checked,
                            nominal_local,
                            projection_l2=_l2(nominal, envelope),
                            eligible=nominal_eligible,
                        ),
                        "progress_projection": projection_payload,
                        "checked": final_payload,
                    }
                ],
            }
        )
        return {**source_result, "actions": returned_chunk}


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v3 episode while preserving all frozen predecessor modules."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    if l1_enabled and (
        int(getattr(args, "semantic_candidate_count", 1)) != 1
        or int(args.replan_steps) != 10
    ):
        raise OnlineProgressProjectionError(
            "v3 L1 execution requires semantic_candidate_count=1 and H10"
        )
    original = v2.BoundedCandidatePolicy
    v2.BoundedCandidatePolicy = OnlineProgressProjectionCandidatePolicy
    try:
        payload = v2.run_episode(**kwargs)
    finally:
        v2.BoundedCandidatePolicy = original
    frames = payload.get("observation_frame_audits")
    if l1_enabled:
        if not isinstance(frames, list):
            raise OnlineProgressProjectionError(
                "v2 payload lacks observation frame audits"
            )
        rewritten = []
        for frame in frames:
            prior = frame.get("bounded_candidate_selection_v2")
            if not isinstance(prior, dict):
                raise OnlineProgressProjectionError(
                    "v2 frame lacks the online candidate audit"
                )
            retained = dict(frame)
            retained.pop("bounded_candidate_selection_v2")
            retained["online_progress_projection_v3"] = prior
            rewritten.append(retained)
        payload["observation_frame_audits"] = rewritten
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "online_progress_projection_active": l1_enabled,
            "semantic_candidate_count": 1 if l1_enabled else None,
            "semantic_action_block_steps": 10 if l1_enabled else None,
            "release_projection_allowed": False,
            "release_nominal_checker_bypass_allowed": True,
        }
    )
    payload["metadata"] = metadata
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "execution_authorized": False,
            "note": (
                "Import run_episode through a separately frozen clean or "
                "attacked protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
