"""No-dispatch identity gate for the future online L1/L2 four-arm runner.

The gate starts from one frozen ``(H, 7)`` source action chunk and evaluates
the routing semantics of the four treatment arms without constructing a
policy, simulator, or action sink.  It proves source-chunk identity and the
expected P1/P2/P3 treatment truth table; it does not claim that the live
online runner already exposes independent L1/L2 switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Iterable, Sequence

from proofalign.benchmark.execution_attack_relay import (
    AttackPlacement,
    PublishedAffineFamily,
    published_affine_scenario,
)
from proofalign.benchmark.semantic_four_arm_runner import (
    ARM_ORDER,
    SemanticMethodArm,
)
from proofalign.digests import digest_payload


FOUR_ARM_IDENTITY_SCHEMA = "proofalign.l2-four-arm-identity.v1"


class L2FourArmIdentityError(ValueError):
    """Raised when a four-arm identity case is malformed."""


class IdentityLayerVerdict(str, Enum):
    DISABLED = "disabled"
    ALLOW = "allow"
    REJECT = "reject"
    UNKNOWN = "unknown"


def _action_chunk(
    value: Iterable[Iterable[float]],
) -> tuple[tuple[float, ...], ...]:
    try:
        chunk = tuple(
            tuple(float(component) for component in action)
            for action in value
        )
    except (TypeError, ValueError) as exc:
        raise L2FourArmIdentityError(
            "source action chunk must be numeric"
        ) from exc
    if not chunk:
        raise L2FourArmIdentityError(
            "source action chunk must contain at least one action"
        )
    if any(len(action) != 7 for action in chunk):
        raise L2FourArmIdentityError(
            "source action chunk must have shape (H, 7)"
        )
    if any(
        not isfinite(component)
        for action in chunk
        for component in action
    ):
        raise L2FourArmIdentityError(
            "source action chunk must be finite"
        )
    return chunk


def action_chunk_digest(
    chunk: Sequence[Sequence[float]],
) -> str:
    frozen = _action_chunk(chunk)
    return digest_payload(
        {
            "schema": f"{FOUR_ARM_IDENTITY_SCHEMA}.action-chunk",
            "shape": (len(frozen), 7),
            "actions": frozen,
        }
    )


def _attacked_chunk(
    chunk: tuple[tuple[float, ...], ...],
    family: PublishedAffineFamily,
) -> tuple[tuple[float, ...], ...]:
    scenario = published_affine_scenario(family)
    return tuple(
        scenario.apply_control_operator(action) for action in chunk
    )


@dataclass(frozen=True)
class L2FourArmIdentityCase:
    """One outcome-free shared-source-chunk treatment case."""

    unit_id: str
    source_action_chunk: tuple[tuple[float, ...], ...]
    semantic_verdict: IdentityLayerVerdict = IdentityLayerVerdict.ALLOW
    semantic_action_chunk: tuple[tuple[float, ...], ...] | None = None
    attack_family: PublishedAffineFamily = PublishedAffineFamily.NONE
    attack_placement: AttackPlacement | None = None

    def __post_init__(self) -> None:
        if not self.unit_id:
            raise L2FourArmIdentityError("unit_id must be non-empty")
        source = _action_chunk(self.source_action_chunk)
        object.__setattr__(self, "source_action_chunk", source)
        verdict = IdentityLayerVerdict(self.semantic_verdict)
        if verdict is IdentityLayerVerdict.DISABLED:
            raise L2FourArmIdentityError(
                "case semantic_verdict cannot be disabled"
            )
        object.__setattr__(self, "semantic_verdict", verdict)
        family = PublishedAffineFamily(self.attack_family)
        object.__setattr__(self, "attack_family", family)
        placement = (
            None
            if self.attack_placement is None
            else AttackPlacement(self.attack_placement)
        )
        object.__setattr__(self, "attack_placement", placement)
        if family is PublishedAffineFamily.NONE and placement is not None:
            raise L2FourArmIdentityError(
                "nominal case cannot specify an attack placement"
            )
        if family is not PublishedAffineFamily.NONE and placement is None:
            raise L2FourArmIdentityError(
                "attack case requires an attack placement"
            )
        semantic_chunk = self.semantic_action_chunk
        if semantic_chunk is not None:
            semantic_chunk = _action_chunk(semantic_chunk)
            if len(semantic_chunk) != len(source):
                raise L2FourArmIdentityError(
                    "semantic action chunk must preserve source horizon"
                )
            object.__setattr__(
                self,
                "semantic_action_chunk",
                semantic_chunk,
            )
        if (
            verdict is IdentityLayerVerdict.ALLOW
            and self.semantic_action_chunk is None
        ):
            object.__setattr__(
                self,
                "semantic_action_chunk",
                source,
            )


def _stopped_at_l1_row(
    *,
    case: L2FourArmIdentityCase,
    arm: SemanticMethodArm,
    source_digest: str,
) -> dict[str, Any]:
    verdict = case.semantic_verdict
    return {
        "schema": f"{FOUR_ARM_IDENTITY_SCHEMA}.row",
        "unit_id": case.unit_id,
        "arm": arm.value,
        "l1_semantic_alignment": True,
        "l2_execution_integrity": arm.execution_enabled,
        "source_action_chunk_digest": source_digest,
        "semantic_action_chunk_digest": None,
        "authorized_action_chunk_digest": None,
        "attacked_action_chunk_digest": None,
        "planned_env_input_chunk_digest": None,
        "reported_action_chunk_digest": None,
        "execution_attack_family": case.attack_family.value,
        "execution_attack_placement": (
            None
            if case.attack_placement is None
            else case.attack_placement.value
        ),
        "attack_changed_action": None,
        "l1_verdict": verdict.value,
        "l2_verdict": IdentityLayerVerdict.DISABLED.value,
        "core_verdict": verdict.value,
        "predicted_env_step_reached": False,
        "altered_env_steps_before_detection": 0,
        "detection_stage": (
            "l1_pre_dispatch_reject"
            if verdict is IdentityLayerVerdict.REJECT
            else "l1_unknown_fail_closed"
        ),
        "independent_trace_required": False,
        "dispatch_attempted": False,
    }


def _routed_row(
    *,
    case: L2FourArmIdentityCase,
    arm: SemanticMethodArm,
    source_digest: str,
) -> dict[str, Any]:
    l1_verdict = (
        IdentityLayerVerdict.ALLOW
        if arm.semantic_enabled
        else IdentityLayerVerdict.DISABLED
    )
    authorized = (
        case.semantic_action_chunk
        if arm.semantic_enabled
        else case.source_action_chunk
    )
    assert authorized is not None
    authorized_digest = action_chunk_digest(authorized)
    attacked = (
        authorized
        if case.attack_family is PublishedAffineFamily.NONE
        else _attacked_chunk(authorized, case.attack_family)
    )
    attacked_digest = action_chunk_digest(attacked)
    changed = attacked_digest != authorized_digest

    planned_env_input = authorized
    reported = authorized
    predicted_env_step_reached = True
    altered_steps_before_detection = 0
    independent_trace_required = False
    detection_stage = "none"
    l2_verdict = (
        IdentityLayerVerdict.ALLOW
        if arm.execution_enabled
        else IdentityLayerVerdict.DISABLED
    )

    if case.attack_family is not PublishedAffineFamily.NONE:
        assert case.attack_placement is not None
        if case.attack_placement is AttackPlacement.PRE_BOUNDARY:
            if arm.execution_enabled and changed:
                planned_env_input = None
                reported = None
                predicted_env_step_reached = False
                l2_verdict = IdentityLayerVerdict.REJECT
                detection_stage = "before_env_step"
            else:
                planned_env_input = attacked
                reported = attacked
        elif (
            case.attack_placement
            is AttackPlacement.POST_BOUNDARY_TRUTHFUL
        ):
            planned_env_input = attacked
            reported = attacked
            if arm.execution_enabled and changed:
                l2_verdict = IdentityLayerVerdict.REJECT
                altered_steps_before_detection = 1
                detection_stage = "after_first_env_step"
        elif (
            case.attack_placement
            is AttackPlacement.POST_BOUNDARY_FORGED
        ):
            planned_env_input = attacked
            reported = authorized
            independent_trace_required = changed
            if arm.execution_enabled and changed:
                detection_stage = "receipt_passes_observer_required"
        else:  # pragma: no cover - enum exhaustiveness.
            raise AssertionError(
                f"unhandled placement: {case.attack_placement}"
            )

    core_verdict = (
        IdentityLayerVerdict.REJECT
        if l2_verdict is IdentityLayerVerdict.REJECT
        else IdentityLayerVerdict.UNKNOWN
        if l2_verdict is IdentityLayerVerdict.UNKNOWN
        else IdentityLayerVerdict.ALLOW
    )
    return {
        "schema": f"{FOUR_ARM_IDENTITY_SCHEMA}.row",
        "unit_id": case.unit_id,
        "arm": arm.value,
        "l1_semantic_alignment": arm.semantic_enabled,
        "l2_execution_integrity": arm.execution_enabled,
        "source_action_chunk_digest": source_digest,
        "semantic_action_chunk_digest": (
            action_chunk_digest(case.semantic_action_chunk)
            if arm.semantic_enabled
            else None
        ),
        "authorized_action_chunk_digest": authorized_digest,
        "attacked_action_chunk_digest": attacked_digest,
        "planned_env_input_chunk_digest": (
            None
            if planned_env_input is None
            else action_chunk_digest(planned_env_input)
        ),
        "reported_action_chunk_digest": (
            None
            if reported is None
            else action_chunk_digest(reported)
        ),
        "execution_attack_family": case.attack_family.value,
        "execution_attack_placement": (
            None
            if case.attack_placement is None
            else case.attack_placement.value
        ),
        "attack_changed_action": changed,
        "l1_verdict": l1_verdict.value,
        "l2_verdict": l2_verdict.value,
        "core_verdict": core_verdict.value,
        "predicted_env_step_reached": predicted_env_step_reached,
        "altered_env_steps_before_detection": (
            altered_steps_before_detection
        ),
        "detection_stage": detection_stage,
        "independent_trace_required": independent_trace_required,
        "dispatch_attempted": False,
    }


def evaluate_l2_four_arm_identity(
    case: L2FourArmIdentityCase,
) -> dict[str, Any]:
    """Evaluate all four treatment routes without dispatch capability."""

    source_digest = action_chunk_digest(case.source_action_chunk)
    rows = []
    for arm in ARM_ORDER:
        if (
            arm.semantic_enabled
            and case.semantic_verdict
            in (
                IdentityLayerVerdict.REJECT,
                IdentityLayerVerdict.UNKNOWN,
            )
        ):
            row = _stopped_at_l1_row(
                case=case,
                arm=arm,
                source_digest=source_digest,
            )
        else:
            row = _routed_row(
                case=case,
                arm=arm,
                source_digest=source_digest,
            )
        rows.append(row)

    treatment_pairs = {
        (
            row["l1_semantic_alignment"],
            row["l2_execution_integrity"],
        )
        for row in rows
    }
    source_digests = {
        row["source_action_chunk_digest"] for row in rows
    }
    return {
        "schema": FOUR_ARM_IDENTITY_SCHEMA,
        "unit_id": case.unit_id,
        "source_action_chunk_shape": (
            len(case.source_action_chunk),
            7,
        ),
        "source_action_chunk_digest": source_digest,
        "arm_count": len(rows),
        "source_chunk_identity_pass": len(source_digests) == 1,
        "treatment_switch_identity_pass": treatment_pairs
        == {
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        },
        "dispatch_attempt_count": 0,
        "policy_loaded": False,
        "simulator_created": False,
        "sink_created": False,
        "outcomes_observed": False,
        "rows": rows,
    }


__all__ = [
    "FOUR_ARM_IDENTITY_SCHEMA",
    "IdentityLayerVerdict",
    "L2FourArmIdentityCase",
    "L2FourArmIdentityError",
    "action_chunk_digest",
    "evaluate_l2_four_arm_identity",
]
