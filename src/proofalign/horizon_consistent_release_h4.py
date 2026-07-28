"""Verb-specific H4 release micro-block over the H10 spatial-action stack."""

from __future__ import annotations

from typing import Any

import numpy as np

from proofalign.horizon_consistent_release import (
    HorizonConsistentReleaseCandidatePolicy,
    canonicalize_release_action_block,
)
from proofalign.semantic_action_selection import (
    select_checked_action_block,
)
from proofalign.semantic_local_checker import parse_semantic_subtask
from scripts import run_l2_execution_attack_eval_v3 as v3


RELEASE_MICRO_BLOCK_STEPS = 4


class HorizonConsistentReleaseH4Error(RuntimeError):
    """Raised when the H4 release boundary cannot be preserved."""


class HorizonConsistentReleaseH4CandidatePolicy(
    HorizonConsistentReleaseCandidatePolicy
):
    """Authorize an exact H4 open-gripper block only for release."""

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        result = super().infer(element)
        wrapper = self.wrapper
        request = self.request
        if wrapper is None or request is None:
            raise HorizonConsistentReleaseH4Error(
                "H4 release successor lacks semantic bindings"
            )
        semantic_subtask = request.artifact.selected_subtask
        if parse_semantic_subtask(semantic_subtask).verb != "release":
            return result
        source = np.asarray(result["actions"], dtype=np.float64)
        final, actuator = canonicalize_release_action_block(
            source,
            block_steps=RELEASE_MICRO_BLOCK_STEPS,
        )
        exact = final[:RELEASE_MICRO_BLOCK_STEPS]
        shape = (RELEASE_MICRO_BLOCK_STEPS, 7)
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
        returned = exact.copy()
        if not eligible:
            returned[:, 6] = 1.0
        if not self.audits:
            raise HorizonConsistentReleaseH4Error(
                "H4 release successor lacks predecessor audit"
            )
        predecessor = self.audits[-1]
        candidate = predecessor["candidates"][0]
        predecessor.update(
            {
                "schema": (
                    "proofalign.semantic-progress-projection-selection.v6"
                ),
                "replan_steps": 10,
                "authorized_action_block_steps": (
                    RELEASE_MICRO_BLOCK_STEPS
                ),
                "selection_reason": (
                    "release_h4_actuator_canonicalization_eligible"
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
        projection = dict(candidate["progress_projection"])
        projection.update(
            {
                "accepted": eligible,
                "projected": bool(
                    actuator["changed_gripper_step_count"]
                ),
                "reason": (
                    "release_h4_open_gripper_canonicalization"
                    if eligible
                    else "release_h4_canonicalization_failed_closed"
                ),
                "command_shape": shape,
                "projection_l2": actuator[
                    "gripper_projection_l2"
                ],
                "config_digest": actuator["config_digest"],
                "actuator_canonicalization": actuator,
                "authorized_action_block_steps": (
                    RELEASE_MICRO_BLOCK_STEPS
                ),
            }
        )
        candidate["progress_projection"] = projection
        candidate["checked"] = v3._checked_payload(
            checked,
            local,
            projection_l2=float(
                actuator["gripper_projection_l2"]
            ),
            eligible=eligible,
        )
        return {**result, "actions": returned}


__all__ = [
    "HorizonConsistentReleaseH4CandidatePolicy",
    "HorizonConsistentReleaseH4Error",
    "RELEASE_MICRO_BLOCK_STEPS",
]
