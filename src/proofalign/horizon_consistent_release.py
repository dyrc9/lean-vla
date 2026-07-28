"""Semantic actuator canonicalization for a finite release ActionBlock.

The trusted task graph decides when ``release`` is the active semantic
subtask.  This module does not infer or relabel that subtask.  It preserves
the policy's enveloped Cartesian and rotational channels and canonicalizes
only the gripper channel to an open command for the complete H10 window.
"""

from __future__ import annotations

from hashlib import sha256
from math import sqrt
from typing import Any

import numpy as np

from proofalign.digests import digest_payload
from proofalign.semantic_action_selection import (
    select_checked_action_block,
)
from proofalign.semantic_local_checker import parse_semantic_subtask
from scripts import run_l2_execution_attack_eval_v3 as v3


RELEASE_CANONICALIZATION_SCHEMA = (
    "proofalign.semantic-release-actuator-canonicalization.v1"
)
RELEASE_OPEN_COMMAND = -1.0
RELEASE_BLOCK_STEPS = 10


class HorizonConsistentReleaseError(RuntimeError):
    """Raised when release canonicalization cannot preserve its boundary."""


def canonicalize_release_action_block(
    command: np.ndarray,
    *,
    block_steps: int = RELEASE_BLOCK_STEPS,
    open_command: float = RELEASE_OPEN_COMMAND,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return an H10 release block with only the gripper channel changed."""

    source = np.asarray(command, dtype=np.float64)
    if (
        source.ndim != 2
        or source.shape[1] != 7
        or len(source) < block_steps
        or block_steps <= 0
        or not np.isfinite(source).all()
        or not np.isfinite(open_command)
        or not -1.0 <= open_command <= 1.0
    ):
        raise HorizonConsistentReleaseError(
            "release canonicalization requires a finite Hx7 block"
        )
    envelope = np.clip(source, -1.0, 1.0)
    final = envelope.copy()
    nominal_gripper = envelope[:block_steps, 6].copy()
    final[:block_steps, 6] = float(open_command)
    delta = final[:block_steps, 6] - nominal_gripper
    changed = int(np.count_nonzero(np.abs(delta) > 1.0e-12))
    audit = {
        "schema": RELEASE_CANONICALIZATION_SCHEMA,
        "block_steps": block_steps,
        "open_command": float(open_command),
        "changed_gripper_step_count": changed,
        "gripper_projection_l2": sqrt(float(np.dot(delta, delta))),
        "cartesian_rotation_channels_preserved": bool(
            np.array_equal(
                envelope[:block_steps, :6],
                final[:block_steps, :6],
            )
        ),
        "terminal_open_command_count": int(
            np.count_nonzero(
                final[:block_steps, 6] == float(open_command)
            )
        ),
        "source_block_sha256": sha256(
            np.ascontiguousarray(source[:block_steps]).tobytes()
        ).hexdigest(),
        "final_block_sha256": sha256(
            np.ascontiguousarray(final[:block_steps]).tobytes()
        ).hexdigest(),
        "config_digest": digest_payload(
            {
                "schema": RELEASE_CANONICALIZATION_SCHEMA,
                "block_steps": block_steps,
                "open_command": float(open_command),
                "preserved_channels": (0, 1, 2, 3, 4, 5),
                "canonicalized_channel": 6,
            }
        ),
    }
    return final, audit


class HorizonConsistentReleaseCandidatePolicy(
    v3.OnlineProgressProjectionCandidatePolicy
):
    """Add a task-graph-gated release actuator layer after v3 projection."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        wrapper = self.wrapper
        request = self.request
        if wrapper is None or request is None:
            raise HorizonConsistentReleaseError(
                "release successor lacks semantic bindings"
            )
        semantic_subtask = request.artifact.selected_subtask
        if parse_semantic_subtask(semantic_subtask).verb != "release":
            return result
        returned = np.asarray(result["actions"], dtype=np.float64)
        final, release_audit = canonicalize_release_action_block(
            returned,
            block_steps=self.replan_steps,
        )
        shape = (self.replan_steps, 7)
        exact = final[: self.replan_steps]
        checked, local = wrapper.checker.checked_candidate(
            candidate_index=0,
            semantic_subtask_digest=request.artifact.artifact_digest,
            semantic_subtask=semantic_subtask,
            observation=request.local_observation,
            nominal_command=tuple(
                float(value) for value in exact.reshape(-1)
            ),
            final_command=tuple(
                float(value) for value in exact.reshape(-1)
            ),
            command_shape=shape,
            expected_state_epoch=request.context.state_epoch,
            release_destination=request.release_destination,
        )
        selection = select_checked_action_block(
            (checked,),
            expected_semantic_subtask_digest=(
                request.artifact.artifact_digest
            ),
            min_progress_margin=wrapper.min_progress_margin,
            max_projection_l2=wrapper.max_projection_l2,
        )
        eligible = selection.selected is not None
        if eligible:
            returned = final
        else:
            # Ensure downstream wrapper recheck also fails before dispatch.
            returned = np.clip(returned, -1.0, 1.0)
            returned[: self.replan_steps, 6] = 1.0
        if not self.audits:
            raise HorizonConsistentReleaseError(
                "release successor lacks predecessor audit"
            )
        predecessor = self.audits[-1]
        candidate = predecessor["candidates"][0]
        projection_payload = {
            "schema": RELEASE_CANONICALIZATION_SCHEMA,
            "projector_schema": RELEASE_CANONICALIZATION_SCHEMA,
            "accepted": eligible,
            "projected": bool(
                release_audit["changed_gripper_step_count"]
            ),
            "reason": (
                "release_open_gripper_canonicalization"
                if eligible
                else "release_canonicalization_failed_closed"
            ),
            "semantic_subtask": semantic_subtask,
            "observation_digest": (
                request.local_observation.observation_digest
            ),
            "command_shape": shape,
            "nominal_terminal_progress_m": None,
            "final_terminal_progress_m": None,
            "projection_l2": release_audit[
                "gripper_projection_l2"
            ],
            "config_digest": release_audit["config_digest"],
            "goal_entity_id": request.release_destination,
            "witness_digest": digest_payload(release_audit),
            "actuator_canonicalization": release_audit,
        }
        final_payload = v3._checked_payload(
            checked,
            local,
            projection_l2=float(
                release_audit["gripper_projection_l2"]
            ),
            eligible=eligible,
        )
        predecessor.update(
            {
                "schema": (
                    "proofalign.semantic-progress-projection-selection.v5"
                ),
                "selection_reason": (
                    "release_actuator_canonicalization_eligible"
                    if eligible
                    else "no_feasible_action_block"
                ),
                "eligible_selected_source_candidate_index": (
                    0 if eligible else None
                ),
                "fallback_for_fail_closed_recheck": not eligible,
                "returned_action_chunk_sha256": v3.v2._array_digest(
                    returned
                ),
            }
        )
        candidate["progress_projection"] = projection_payload
        candidate["checked"] = final_payload
        return {**result, "actions": returned}


__all__ = [
    "HorizonConsistentReleaseCandidatePolicy",
    "HorizonConsistentReleaseError",
    "RELEASE_BLOCK_STEPS",
    "RELEASE_CANONICALIZATION_SCHEMA",
    "RELEASE_OPEN_COMMAND",
    "canonicalize_release_action_block",
]
