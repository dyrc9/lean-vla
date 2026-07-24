"""Deterministic selection boundary for semantic-subtask ActionBlocks.

The semantic subtask is fixed before policy sampling.  A policy may propose one
or more ActionBlocks for that same subtask; consumer-side checkers annotate each
block, and this module chooses among only the feasible checked blocks.

This module does not infer a subtask from an action and does not turn a semantic
mismatch into a different subtask.  Numeric projection is accepted only within
a caller-frozen budget and must remain semantically compatible after projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Iterable, Sequence

from proofalign.digests import digest_payload


class ActionSelectionError(ValueError):
    """Raised when checked ActionBlock inputs are malformed."""


def _finite_tuple(values: Iterable[float], *, name: str) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ActionSelectionError(f"{name} must be numeric") from exc
    if not frozen or any(not isfinite(value) for value in frozen):
        raise ActionSelectionError(f"{name} must be non-empty and finite")
    return frozen


def _require_shape(shape: Sequence[int], *, value_count: int) -> tuple[int, int]:
    if (
        len(shape) != 2
        or any(type(value) is not int or value <= 0 for value in shape)
        or shape[0] * shape[1] != value_count
    ):
        raise ActionSelectionError(
            "command_shape must contain two positive integers matching the flattened block"
        )
    return int(shape[0]), int(shape[1])


def _require_atoms(values: Iterable[str], *, name: str) -> tuple[str, ...]:
    frozen = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in frozen):
        raise ActionSelectionError(f"{name} must contain non-empty strings")
    if len(frozen) != len(set(frozen)):
        raise ActionSelectionError(f"{name} must not contain duplicates")
    return frozen


def _require_digest(value: str, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ActionSelectionError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _l2_delta(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sqrt(
        sum(
            (right_value - left_value) ** 2
            for left_value, right_value in zip(left, right, strict=True)
        )
    )


def _smoothness_l2(command: tuple[float, ...], shape: tuple[int, int]) -> float:
    action_count, action_dimension = shape
    if action_count == 1:
        return 0.0
    squared = 0.0
    for action_index in range(1, action_count):
        current_start = action_index * action_dimension
        previous_start = (action_index - 1) * action_dimension
        for offset in range(action_dimension):
            delta = command[current_start + offset] - command[previous_start + offset]
            squared += delta * delta
    return sqrt(squared)


@dataclass(frozen=True)
class CheckedActionBlock:
    """One policy proposal plus frozen consumer-side check results."""

    candidate_index: int
    semantic_subtask_digest: str
    nominal_command: tuple[float, ...]
    final_command: tuple[float, ...]
    command_shape: tuple[int, int]
    known: bool
    semantic_compatible: bool
    post_projection_compatible: bool
    hard_violation_atoms: tuple[str, ...] = ()
    progress_margin: float = 0.0

    def __post_init__(self) -> None:
        if type(self.candidate_index) is not int or self.candidate_index < 0:
            raise ActionSelectionError("candidate_index must be a non-negative integer")
        _require_digest(
            self.semantic_subtask_digest,
            name="semantic_subtask_digest",
        )
        nominal = _finite_tuple(self.nominal_command, name="nominal_command")
        final = _finite_tuple(self.final_command, name="final_command")
        if len(nominal) != len(final):
            raise ActionSelectionError(
                "nominal and final commands must have identical lengths"
            )
        shape = _require_shape(self.command_shape, value_count=len(nominal))
        violations = _require_atoms(
            self.hard_violation_atoms, name="hard_violation_atoms"
        )
        if not isinstance(self.progress_margin, (int, float)) or isinstance(
            self.progress_margin, bool
        ):
            raise ActionSelectionError("progress_margin must be numeric")
        margin = float(self.progress_margin)
        if not isfinite(margin):
            raise ActionSelectionError("progress_margin must be finite")
        for name in ("known", "semantic_compatible", "post_projection_compatible"):
            if type(getattr(self, name)) is not bool:
                raise ActionSelectionError(f"{name} must be boolean")
        object.__setattr__(self, "nominal_command", nominal)
        object.__setattr__(self, "final_command", final)
        object.__setattr__(self, "command_shape", shape)
        object.__setattr__(self, "hard_violation_atoms", violations)
        object.__setattr__(self, "progress_margin", margin)

    @property
    def projection_l2(self) -> float:
        return _l2_delta(self.nominal_command, self.final_command)

    @property
    def smoothness_l2(self) -> float:
        return _smoothness_l2(self.final_command, self.command_shape)

    @property
    def final_action_block_digest(self) -> str:
        return digest_payload(
            {
                "schema": "proofalign.semantic-selected-action-block.v1",
                "semantic_subtask_digest": self.semantic_subtask_digest,
                "command": self.final_command,
                "command_shape": self.command_shape,
            }
        )


@dataclass(frozen=True)
class CandidateDisposition:
    candidate_index: int
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ActionSelectionDecision:
    """Deterministic result of filtering and lexicographic selection."""

    selected: CheckedActionBlock | None
    dispositions: tuple[CandidateDisposition, ...]
    reason: str

    @property
    def selected_candidate_index(self) -> int | None:
        return None if self.selected is None else self.selected.candidate_index


def _rejection_reasons(
    candidate: CheckedActionBlock,
    *,
    min_progress_margin: float,
    max_projection_l2: float,
) -> tuple[str, ...]:
    reasons = []
    if not candidate.known:
        reasons.append("unknown")
    if not candidate.semantic_compatible:
        reasons.append("semantic_mismatch")
    if candidate.hard_violation_atoms:
        reasons.append("hard_violation")
    if candidate.projection_l2 > max_projection_l2:
        reasons.append("projection_budget_exceeded")
    if not candidate.post_projection_compatible:
        reasons.append("post_projection_semantic_mismatch")
    if candidate.progress_margin < min_progress_margin:
        reasons.append("progress_margin_below_threshold")
    return tuple(reasons)


def select_checked_action_block(
    candidates: Sequence[CheckedActionBlock],
    *,
    expected_semantic_subtask_digest: str,
    min_progress_margin: float,
    max_projection_l2: float,
) -> ActionSelectionDecision:
    """Filter checked blocks and select one without changing the fixed subtask.

    Eligible blocks are ordered lexicographically by:

    1. larger semantic progress margin;
    2. smaller numeric projection;
    3. smoother final ActionBlock;
    4. smaller stable candidate index.
    """

    expected_digest = _require_digest(
        expected_semantic_subtask_digest,
        name="expected_semantic_subtask_digest",
    )
    if not isinstance(min_progress_margin, (int, float)) or isinstance(
        min_progress_margin, bool
    ):
        raise ActionSelectionError("min_progress_margin must be numeric")
    if not isinstance(max_projection_l2, (int, float)) or isinstance(
        max_projection_l2, bool
    ):
        raise ActionSelectionError("max_projection_l2 must be numeric")
    min_margin = float(min_progress_margin)
    max_projection = float(max_projection_l2)
    if not isfinite(min_margin):
        raise ActionSelectionError("min_progress_margin must be finite")
    if not isfinite(max_projection) or max_projection < 0:
        raise ActionSelectionError("max_projection_l2 must be finite and non-negative")
    if not candidates:
        return ActionSelectionDecision(
            selected=None, dispositions=(), reason="no_policy_candidate"
        )

    indices = [candidate.candidate_index for candidate in candidates]
    if len(indices) != len(set(indices)):
        raise ActionSelectionError("candidate indices must be unique")
    subtask_digests = {candidate.semantic_subtask_digest for candidate in candidates}
    if len(subtask_digests) != 1:
        raise ActionSelectionError(
            "all candidates must be conditioned on the same fixed semantic subtask"
        )
    if subtask_digests != {expected_digest}:
        raise ActionSelectionError(
            "candidate semantic subtask does not match the trusted expected subtask"
        )
    shapes = {candidate.command_shape for candidate in candidates}
    if len(shapes) != 1:
        raise ActionSelectionError(
            "all candidates must have the same executable-prefix shape"
        )

    dispositions = []
    eligible = []
    for candidate in sorted(candidates, key=lambda value: value.candidate_index):
        reasons = _rejection_reasons(
            candidate,
            min_progress_margin=min_margin,
            max_projection_l2=max_projection,
        )
        dispositions.append(
            CandidateDisposition(
                candidate_index=candidate.candidate_index,
                eligible=not reasons,
                reasons=reasons,
            )
        )
        if not reasons:
            eligible.append(candidate)
    if not eligible:
        return ActionSelectionDecision(
            selected=None,
            dispositions=tuple(dispositions),
            reason="no_feasible_checked_action_block",
        )

    selected = min(
        eligible,
        key=lambda candidate: (
            -candidate.progress_margin,
            candidate.projection_l2,
            candidate.smoothness_l2,
            candidate.candidate_index,
        ),
    )
    return ActionSelectionDecision(
        selected=selected,
        dispositions=tuple(dispositions),
        reason="selected_feasible_checked_action_block",
    )


__all__ = [
    "ActionSelectionDecision",
    "ActionSelectionError",
    "CandidateDisposition",
    "CheckedActionBlock",
    "select_checked_action_block",
]
