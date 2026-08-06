#!/usr/bin/env python3
"""Post-nonpass L1 availability repair over the frozen v1 online runner.

This version leaves the original runner and its terminal evidence untouched.
For L1-enabled arms it adds two explicitly audited benchmark-only mechanisms:

1. exact destination site/body geometry from the trusted LIBERO simulator;
2. bounded K-candidate policy sampling before the frozen checker selects one
   source block for the existing proposal/authorization transaction.

The selected source block is rechecked by the frozen v1 wrapper.  No threshold
is changed, and L2 behavior remains delegated to the frozen v1 successor.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any, Callable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.digests import digest_text  # noqa: E402
from proofalign.semantic_action_selection import (  # noqa: E402
    CheckedActionBlock,
    select_checked_action_block,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    EntityPosition,
    TrustedLocalObservation,
)
from proofalign.semantic_policy_wrapper import (  # noqa: E402
    SemanticPolicyPreparation,
    SemanticPolicyRequest,
    TrustedSemanticPolicyWrapper,
)
from proofalign.semantic_trust import (  # noqa: E402
    SemanticTrustPolicy,
    TrustedComponentIdentity,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402


CANDIDATE_AUDIT_SCHEMA = (
    "proofalign.semantic-bounded-candidate-selection.v2"
)
GEOMETRY_AUDIT_SCHEMA = "proofalign.libero-privileged-geometry-tap.v2"
RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v2"


class L1AvailabilityRepairError(RuntimeError):
    """Raised when the v2 repair cannot preserve its audit boundary."""


def _array_digest(value: Any) -> str:
    array = np.ascontiguousarray(np.asarray(value))
    header = (
        str(array.dtype)
        + "|"
        + ",".join(str(item) for item in array.shape)
    ).encode("utf-8")
    return sha256(header + b"\0" + array.tobytes(order="C")).hexdigest()


def _underlying_libero_env(env: Any) -> Any:
    current = env
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        candidate = getattr(current, "_env", None)
        if candidate is not None:
            current = candidate
            continue
        candidate = getattr(current, "env", None)
        if candidate is not None and candidate is not current:
            current = candidate
            continue
        break
    return current


class TrustedLiberoGeometryTap:
    """Resolve only frozen task destinations from exact simulator entities."""

    def __init__(self) -> None:
        self.env: Any | None = None
        self.required_entity_ids: tuple[str, ...] = ()
        self.source_counts: Counter[str] = Counter()
        self.unresolved_counts: Counter[str] = Counter()

    def bind_env(self, env: Any) -> None:
        if self.env is not None:
            raise L1AvailabilityRepairError(
                "geometry tap cannot bind more than one episode environment"
            )
        self.env = env

    def bind_required_entities(self, values: tuple[str, ...]) -> None:
        required = tuple(sorted(dict.fromkeys(values)))
        if self.required_entity_ids and self.required_entity_ids != required:
            raise L1AvailabilityRepairError(
                "geometry tap task destinations changed within one episode"
            )
        self.required_entity_ids = required

    def resolve(self) -> tuple[EntityPosition, ...]:
        if self.env is None:
            raise L1AvailabilityRepairError(
                "geometry tap has no bound episode environment"
            )
        env = self.env
        sim = getattr(env, "sim", None)
        if sim is None:
            raise L1AvailabilityRepairError(
                "trusted LIBERO simulator is unavailable"
            )
        raw = _underlying_libero_env(env)
        resolved = []
        for entity_id in self.required_entity_ids:
            position = self._site_position(sim, entity_id)
            source = "exact_sim_site"
            if position is None:
                position = self._body_position(raw, sim, entity_id)
                source = "exact_sim_body"
            if position is None:
                self.unresolved_counts[entity_id] += 1
                continue
            self.source_counts[f"{entity_id}:{source}"] += 1
            resolved.append(EntityPosition(entity_id, position))
        return tuple(resolved)

    @staticmethod
    def _site_position(
        sim: Any,
        entity_id: str,
    ) -> tuple[float, float, float] | None:
        try:
            site_id = sim.model.site_name2id(entity_id)
            if site_id < 0:
                return None
            value = np.asarray(
                sim.data.get_site_xpos(entity_id), dtype=np.float64
            )
        except Exception:
            return None
        if value.shape != (3,) or not np.isfinite(value).all():
            return None
        return tuple(float(item) for item in value)

    @staticmethod
    def _body_position(
        raw: Any,
        sim: Any,
        entity_id: str,
    ) -> tuple[float, float, float] | None:
        body_ids = getattr(raw, "obj_body_id", None)
        if not isinstance(body_ids, dict) or entity_id not in body_ids:
            return None
        try:
            value = np.asarray(
                sim.data.body_xpos[body_ids[entity_id]],
                dtype=np.float64,
            )
        except Exception:
            return None
        if value.shape != (3,) or not np.isfinite(value).all():
            return None
        return tuple(float(item) for item in value)

    def audit_payload(self) -> dict[str, Any]:
        return {
            "schema": GEOMETRY_AUDIT_SCHEMA,
            "benchmark_only": True,
            "deployment_attestation": False,
            "required_entity_ids": self.required_entity_ids,
            "source_counts": dict(sorted(self.source_counts.items())),
            "unresolved_counts": dict(
                sorted(self.unresolved_counts.items())
            ),
        }


class BoundedCandidatePolicy:
    """Sample K source chunks and expose one checker-selected chunk."""

    def __init__(
        self,
        inner: Any,
        *,
        candidate_count: int,
        replan_steps: int,
    ) -> None:
        if candidate_count < 1:
            raise ValueError("candidate_count must be positive")
        self.inner = inner
        self.candidate_count = int(candidate_count)
        self.replan_steps = int(replan_steps)
        self.wrapper: TrustedSemanticPolicyWrapper | None = None
        self.request: SemanticPolicyRequest | None = None
        self.audits: list[dict[str, Any]] = []

    @property
    def _rng(self) -> Any:
        return self.inner._rng

    @_rng.setter
    def _rng(self, value: Any) -> None:
        self.inner._rng = value

    def bind_wrapper(self, wrapper: TrustedSemanticPolicyWrapper) -> None:
        self.wrapper = wrapper

    def bind_preparation(
        self,
        preparation: SemanticPolicyPreparation,
    ) -> None:
        self.request = preparation.request

    def infer(self, element: dict[str, Any]) -> dict[str, Any]:
        wrapper = self.wrapper
        request = self.request
        if wrapper is None or request is None:
            raise L1AvailabilityRepairError(
                "candidate policy lacks a bound semantic request"
            )

        results = []
        checked: list[CheckedActionBlock] = []
        candidate_rows = []
        for index in range(self.candidate_count):
            result = self.inner.infer(element)
            chunk = np.asarray(result["actions"])
            if chunk.ndim != 2 or len(chunk) < self.replan_steps:
                raise L1AvailabilityRepairError(
                    "candidate policy returned an invalid ActionBlock"
                )
            executable = np.asarray(
                chunk[: self.replan_steps], dtype=np.float64
            )
            final = np.clip(executable, -1.0, 1.0)
            candidate, local = wrapper.checker.checked_candidate(
                candidate_index=index,
                semantic_subtask_digest=(
                    request.artifact.artifact_digest
                ),
                semantic_subtask=request.artifact.selected_subtask,
                observation=request.local_observation,
                nominal_command=tuple(
                    float(value) for value in executable.reshape(-1)
                ),
                final_command=tuple(
                    float(value) for value in final.reshape(-1)
                ),
                command_shape=tuple(executable.shape),
                expected_state_epoch=request.context.state_epoch,
                release_destination=request.release_destination,
            )
            results.append((result, chunk))
            checked.append(candidate)
            candidate_rows.append(
                {
                    "source_candidate_index": index,
                    "source_policy_chunk_sha256": _array_digest(chunk),
                    "source_policy_chunk_shape": tuple(chunk.shape),
                    "checked": {
                        "known": candidate.known,
                        "semantic_compatible": (
                            candidate.semantic_compatible
                        ),
                        "post_projection_compatible": (
                            candidate.post_projection_compatible
                        ),
                        "hard_violation_atoms": (
                            candidate.hard_violation_atoms
                        ),
                        "progress_margin": candidate.progress_margin,
                        "projection_l2": candidate.projection_l2,
                        "unknown_reason": local.unknown_reason,
                    },
                }
            )

        selection = select_checked_action_block(
            checked,
            expected_semantic_subtask_digest=(
                request.artifact.artifact_digest
            ),
            min_progress_margin=wrapper.min_progress_margin,
            max_projection_l2=wrapper.max_projection_l2,
        )
        selected_index = selection.selected_candidate_index
        fallback_used = selected_index is None
        if selected_index is None:
            selected_index = min(
                range(len(checked)),
                key=lambda index: (
                    -checked[index].progress_margin,
                    checked[index].projection_l2,
                    index,
                ),
            )
        selected_result, selected_chunk = results[selected_index]
        self.audits.append(
            {
                "schema": CANDIDATE_AUDIT_SCHEMA,
                "candidate_count": self.candidate_count,
                "replan_steps": self.replan_steps,
                "selection_reason": selection.reason,
                "eligible_selected_source_candidate_index": (
                    selection.selected_candidate_index
                ),
                "returned_source_candidate_index": selected_index,
                "fallback_for_fail_closed_recheck": fallback_used,
                "returned_source_policy_chunk_sha256": _array_digest(
                    selected_chunk
                ),
                "candidates": candidate_rows,
            }
        )
        return {**selected_result, "actions": selected_chunk}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def _patched_local_observation_class(
    geometry: TrustedLiberoGeometryTap,
) -> type:
    original = TrustedLocalObservation

    class V2TrustedLocalObservation(original):
        @classmethod
        def from_libero_observation(
            cls,
            observation: dict[str, Any],
            *,
            state_epoch: int,
        ) -> TrustedLocalObservation:
            base_observation = original.from_libero_observation(
                observation,
                state_epoch=state_epoch,
            )
            entities = {
                item.entity_id: item
                for item in base_observation.entity_positions
            }
            for item in geometry.resolve():
                entities[item.entity_id] = item
            return original(
                state_epoch=state_epoch,
                eef_position=base_observation.eef_position,
                gripper_qpos=base_observation.gripper_qpos,
                entity_positions=tuple(entities.values()),
            )

    return V2TrustedLocalObservation


def _patched_wrapper_class(
    *,
    geometry: TrustedLiberoGeometryTap,
    policy: BoundedCandidatePolicy,
) -> type:
    original = TrustedSemanticPolicyWrapper

    class V2TrustedSemanticPolicyWrapper(original):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            destinations = tuple(
                goal.destination
                for goal in self.graph.goals
                if goal.destination is not None
            )
            geometry.bind_required_entities(destinations)
            self.observation_tap = TrustedComponentIdentity(
                "libero_raw_observation_plus_privileged_geometry_tap_v2",
                digest_text(
                    "libero-raw-observation-plus-exact-sim-geometry-v2"
                ),
            )
            self.trust_policy = SemanticTrustPolicy(
                task_sources=(self.task_source,),
                observation_taps=(self.observation_tap,),
                secure_splits=(self.secure_split,),
                selector_models=(self.selector_model,),
                selector_config_digests=(
                    self.selector_config_digest,
                ),
            )
            policy.bind_wrapper(self)

        def begin_policy_call(
            self,
            **kwargs: Any,
        ) -> SemanticPolicyPreparation:
            preparation = super().begin_policy_call(**kwargs)
            policy.bind_preparation(preparation)
            return preparation

    return V2TrustedSemanticPolicyWrapper


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v2 episode while preserving the frozen v1 implementation."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    if not l1_enabled:
        payload = v1.run_episode(**kwargs)
        metadata = dict(payload["metadata"])
        metadata["runner_variant"] = RUNNER_VARIANT
        metadata["l1_availability_repair_active"] = False
        payload["metadata"] = metadata
        v1._persist_annotated_episode(payload)
        return payload

    candidate_count = int(
        getattr(args, "semantic_candidate_count", 4)
    )
    geometry = TrustedLiberoGeometryTap()
    policy = BoundedCandidatePolicy(
        kwargs["policy"],
        candidate_count=candidate_count,
        replan_steps=int(args.replan_steps),
    )
    patched_kwargs = {**kwargs, "policy": policy}

    original_create_env: Callable[..., Any] = base.create_env
    original_observation_class = base.TrustedLocalObservation
    original_wrapper_class = base.TrustedSemanticPolicyWrapper

    def create_env(*create_args: Any, **create_kwargs: Any) -> Any:
        env = original_create_env(*create_args, **create_kwargs)
        geometry.bind_env(env)
        return env

    base.create_env = create_env
    base.TrustedLocalObservation = _patched_local_observation_class(
        geometry
    )
    base.TrustedSemanticPolicyWrapper = _patched_wrapper_class(
        geometry=geometry,
        policy=policy,
    )
    try:
        payload = v1.run_episode(**patched_kwargs)
    finally:
        base.create_env = original_create_env
        base.TrustedLocalObservation = original_observation_class
        base.TrustedSemanticPolicyWrapper = original_wrapper_class

    frame_audits = payload.get("observation_frame_audits")
    if not isinstance(frame_audits, list):
        raise L1AvailabilityRepairError(
            "v1 payload lacks observation frame audits"
        )
    if len(policy.audits) != len(frame_audits):
        raise L1AvailabilityRepairError(
            "candidate audits do not match policy frame audits"
        )
    payload["observation_frame_audits"] = [
        {
            **frame,
            "bounded_candidate_selection_v2": audit,
        }
        for frame, audit in zip(
            frame_audits, policy.audits, strict=True
        )
    ]
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "l1_availability_repair_active": True,
            "semantic_candidate_count": candidate_count,
            "semantic_geometry_source": (
                "libero_exact_sim_site_body_privileged_benchmark_v2"
            ),
            "semantic_deployment_attestation": False,
            "post_outcome_repair": True,
        }
    )
    payload["metadata"] = metadata
    payload["trusted_geometry_audit_v2"] = geometry.audit_payload()
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-count", type=int, default=4)
    args = parser.parse_args()
    if args.candidate_count < 1:
        parser.error("--candidate-count must be positive")
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "candidate_count": args.candidate_count,
            "execution_authorized": False,
            "note": (
                "Import run_episode from this module through a frozen "
                "post-outcome protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
