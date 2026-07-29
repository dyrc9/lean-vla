"""Simulator-facing escape-recovery refinement for v12.

The analytic v12 contract prequalification initially required every predicted
recovery step to be outside the 0.1-rad trigger region.  A no-outcome
single-environment engineering probe showed that this is physically
inappropriate: a controller necessarily starts inside the region and may need
several monotone escape steps before reaching the safe margin.

This successor preserves that diagnostic and uses a separately versioned
criterion.  A recovery trajectory may begin inside the trigger region only if
it never crosses a joint limit, does not lose more than a frozen transient
margin budget, and reaches the independently frozen safe margin by the end of
the block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Sequence

import numpy as np

from proofalign.digests import digest_payload
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    RecoverableAlignmentV12Error,
    ShadowJointAssessment,
    TrustedJointState,
    assess_shadow_joint_trajectory,
)


ESCAPE_RECOVERY_SCHEMA = "proofalign.escape-recovery-selection.v12.1"
TRUSTED_LIBERO_JOINT_SOURCE = (
    "libero-robosuite-ref-joint-state-privileged"
)


@dataclass(frozen=True)
class EscapeRecoveryConfig:
    trigger_margin_rad: float = 0.1
    safe_margin_rad: float = 0.15
    required_margin_gain_rad: float = 0.02
    max_transient_margin_loss_rad: float = 0.005

    def __post_init__(self) -> None:
        for name in (
            "trigger_margin_rad",
            "safe_margin_rad",
            "required_margin_gain_rad",
            "max_transient_margin_loss_rad",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(float(value))
                or float(value) < 0
            ):
                raise RecoverableAlignmentV12Error(
                    f"{name} must be finite and non-negative"
                )
        if self.trigger_margin_rad <= 0 or self.safe_margin_rad <= 0:
            raise RecoverableAlignmentV12Error(
                "trigger and safe margins must be positive"
            )
        if self.safe_margin_rad <= self.trigger_margin_rad:
            raise RecoverableAlignmentV12Error(
                "safe margin must exceed trigger margin"
            )

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "schema": ESCAPE_RECOVERY_SCHEMA + ".config",
                **self.__dict__,
            }
        )


@dataclass(frozen=True)
class EscapeCandidateEvaluation:
    candidate_id: str
    known: bool
    eligible: bool
    baseline_margin: float
    minimum_margin: float | None
    terminal_margin: float | None
    first_safe_step: int | None
    reasons: tuple[str, ...]
    shadow_assessment_digest: str
    evaluation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluation_digest",
            digest_payload(
                {
                    "schema": ESCAPE_RECOVERY_SCHEMA + ".candidate",
                    "candidate_id": self.candidate_id,
                    "known": self.known,
                    "eligible": self.eligible,
                    "baseline_margin": self.baseline_margin,
                    "minimum_margin": self.minimum_margin,
                    "terminal_margin": self.terminal_margin,
                    "first_safe_step": self.first_safe_step,
                    "reasons": self.reasons,
                    "shadow_assessment_digest": (
                        self.shadow_assessment_digest
                    ),
                }
            ),
        )


@dataclass(frozen=True)
class EscapeRecoverySelection:
    selected: RecoveryCandidate | None
    selected_assessment: ShadowJointAssessment | None
    evaluations: tuple[EscapeCandidateEvaluation, ...]
    config_digest: str
    selection_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_digest",
            digest_payload(
                {
                    "schema": ESCAPE_RECOVERY_SCHEMA,
                    "selected_candidate_id": (
                        self.selected.candidate_id
                        if self.selected is not None
                        else None
                    ),
                    "selected_assessment_digest": (
                        self.selected_assessment.assessment_digest
                        if self.selected_assessment is not None
                        else None
                    ),
                    "evaluations": tuple(
                        row.evaluation_digest for row in self.evaluations
                    ),
                    "config_digest": self.config_digest,
                }
            ),
        )


def _margins(
    state: TrustedJointState,
    positions: Sequence[Sequence[float]],
) -> tuple[float, ...]:
    return tuple(
        min(
            min(value - low, high - value)
            for value, low, high in zip(
                row,
                state.joint_lower,
                state.joint_upper,
                strict=True,
            )
        )
        for row in positions
    )


def select_escape_recovery_candidate(
    state: TrustedJointState,
    candidates: Sequence[RecoveryCandidate],
    *,
    config: EscapeRecoveryConfig | None = None,
) -> EscapeRecoverySelection:
    """Select a bounded escape trajectory while preserving fail-closed binds."""

    selected_config = config or EscapeRecoveryConfig()
    evaluations: list[
        tuple[
            EscapeCandidateEvaluation,
            RecoveryCandidate,
            ShadowJointAssessment,
        ]
    ] = []
    for candidate in candidates:
        assessment = assess_shadow_joint_trajectory(
            state,
            candidate.trajectory,
            trigger_margin_rad=selected_config.trigger_margin_rad,
        )
        reasons = []
        margins: tuple[float, ...] = ()
        first_safe = None
        if not assessment.known:
            reasons.extend(assessment.issues)
        else:
            margins = _margins(state, candidate.trajectory.positions)
            first_safe = next(
                (
                    index
                    for index, margin in enumerate(margins)
                    if margin >= selected_config.safe_margin_rad
                ),
                None,
            )
            if min(margins) < 0:
                reasons.append("joint_limit_crossed")
            if min(margins) < (
                state.minimum_margin
                - selected_config.max_transient_margin_loss_rad
            ):
                reasons.append("transient_margin_loss_exceeded")
            if first_safe is None:
                reasons.append("safe_margin_not_reached")
            if margins[-1] < (
                state.minimum_margin
                + selected_config.required_margin_gain_rad
            ):
                reasons.append("insufficient_terminal_margin_gain")
        if candidate.hard_violation_atoms:
            reasons.extend(candidate.hard_violation_atoms)
        reasons = list(dict.fromkeys(reasons))
        evaluation = EscapeCandidateEvaluation(
            candidate_id=candidate.candidate_id,
            known=assessment.known,
            eligible=not reasons,
            baseline_margin=state.minimum_margin,
            minimum_margin=min(margins) if margins else None,
            terminal_margin=margins[-1] if margins else None,
            first_safe_step=first_safe,
            reasons=tuple(reasons),
            shadow_assessment_digest=assessment.assessment_digest,
        )
        evaluations.append((evaluation, candidate, assessment))
    eligible = [row for row in evaluations if row[0].eligible]
    if not eligible:
        return EscapeRecoverySelection(
            selected=None,
            selected_assessment=None,
            evaluations=tuple(row[0] for row in evaluations),
            config_digest=selected_config.config_digest,
        )
    eligible.sort(
        key=lambda row: (
            row[0].first_safe_step,
            -float(row[0].terminal_margin),
            -float(row[0].minimum_margin),
            row[0].candidate_id,
        )
    )
    selected = eligible[0]
    return EscapeRecoverySelection(
        selected=selected[1],
        selected_assessment=selected[2],
        evaluations=tuple(row[0] for row in evaluations),
        config_digest=selected_config.config_digest,
    )


def trusted_joint_state_from_libero(
    env: Any,
    *,
    state_epoch: int,
    source_id: str,
) -> TrustedJointState:
    """Extract the exact arm joint state and model ranges from LIBERO."""

    robots = getattr(env, "robots", None)
    if not isinstance(robots, (list, tuple)) or len(robots) != 1:
        raise RecoverableAlignmentV12Error(
            "v12.1 requires exactly one trusted robot"
        )
    robot = robots[0]
    sim = getattr(env, "sim", None)
    if sim is None:
        raise RecoverableAlignmentV12Error(
            "trusted simulator state is unavailable"
        )
    try:
        position_indexes = np.asarray(
            robot._ref_joint_pos_indexes, dtype=int
        )
        velocity_indexes = np.asarray(
            robot._ref_joint_vel_indexes, dtype=int
        )
        model_indexes = np.asarray(
            robot._ref_joint_indexes, dtype=int
        )
        qpos = np.asarray(
            sim.data.qpos[position_indexes], dtype=np.float64
        )
        qvel = np.asarray(
            sim.data.qvel[velocity_indexes], dtype=np.float64
        )
        limits = np.asarray(
            sim.model.jnt_range[model_indexes], dtype=np.float64
        )
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise RecoverableAlignmentV12Error(
            "trusted LIBERO joint-state extraction failed"
        ) from exc
    if limits.shape != (len(qpos), 2):
        raise RecoverableAlignmentV12Error(
            "trusted joint-limit shape differs from arm qpos"
        )
    return TrustedJointState(
        state_epoch=state_epoch,
        qpos=tuple(float(value) for value in qpos),
        qvel=tuple(float(value) for value in qvel),
        joint_lower=tuple(float(value) for value in limits[:, 0]),
        joint_upper=tuple(float(value) for value in limits[:, 1]),
        source_id=(
            f"{TRUSTED_LIBERO_JOINT_SOURCE}:{source_id}"
        ),
    )


__all__ = [
    "ESCAPE_RECOVERY_SCHEMA",
    "TRUSTED_LIBERO_JOINT_SOURCE",
    "EscapeCandidateEvaluation",
    "EscapeRecoveryConfig",
    "EscapeRecoverySelection",
    "select_escape_recovery_candidate",
    "trusted_joint_state_from_libero",
]
