"""Shortest-safe-prefix escape selection for v12.2.

The v12.1 simulator pilot used fixed ten-step primitives.  A multijoint
engineering pilot showed that some primitives enter the safe region and then
leave it again, while other useful directions cross a limit only late in the
ten-step block.  This successor evaluates every prefix from already-computed
shadow trajectories and retains the first eligible prefix per primitive.

No additional simulator step is required: prefix selection only slices
content-addressed commands and predicted joint trajectories.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from proofalign.digests import digest_payload
from proofalign.integrity_v4_models import command_digest
from proofalign.escape_recovery_v12 import (
    EscapeCandidateEvaluation,
    EscapeRecoveryConfig,
    select_escape_recovery_candidate,
)
from proofalign.recoverable_alignment_v12 import (
    RecoveryCandidate,
    ShadowJointAssessment,
    ShadowJointTrajectory,
    TrustedJointState,
)


PREFIX_ESCAPE_SCHEMA = "proofalign.prefix-escape-recovery-selection.v12.2"


@dataclass(frozen=True)
class PrefixEscapeRecoverySelection:
    selected: RecoveryCandidate | None
    selected_assessment: ShadowJointAssessment | None
    evaluations: tuple[EscapeCandidateEvaluation, ...]
    source_candidate_count: int
    evaluated_prefix_count: int
    config_digest: str
    selection_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_digest",
            digest_payload(
                {
                    "schema": PREFIX_ESCAPE_SCHEMA,
                    "selected_candidate_id": (
                        self.selected.candidate_id
                        if self.selected is not None
                        else None
                    ),
                    "selected_command_digest": (
                        self.selected.command_digest
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
                    "source_candidate_count": self.source_candidate_count,
                    "evaluated_prefix_count": self.evaluated_prefix_count,
                    "config_digest": self.config_digest,
                }
            ),
        )


def _prefix_candidate(
    state: TrustedJointState,
    candidate: RecoveryCandidate,
    steps: int,
) -> RecoveryCandidate:
    width = candidate.command_shape[1]
    command = candidate.command[: steps * width]
    positions = candidate.trajectory.positions[:steps]
    # Joint-limit crossing is recomputed by the prefix selector.  Other hard
    # atoms (for example workspace/contact evidence) remain fail closed.
    hard_atoms = tuple(
        atom
        for atom in candidate.hard_violation_atoms
        if atom != "joint_limit_crossed"
    )
    trajectory = ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(command),
        positions=positions,
        predictor_id=(
            candidate.trajectory.predictor_id
            + f":shortest-safe-prefix-v12.2:h{steps}"
        ),
    )
    return RecoveryCandidate(
        candidate_id=f"{candidate.candidate_id}@h{steps}",
        command=command,
        command_shape=(steps, width),
        trajectory=trajectory,
        hard_violation_atoms=hard_atoms,
    )


def select_prefix_escape_recovery_candidate(
    state: TrustedJointState,
    candidates: tuple[RecoveryCandidate, ...],
    *,
    config: EscapeRecoveryConfig | None = None,
) -> PrefixEscapeRecoverySelection:
    """Choose among the first eligible prefix of each source primitive."""

    selected_config = config or EscapeRecoveryConfig()
    retained = []
    evaluations = []
    for candidate in candidates:
        if (
            len(candidate.command_shape) != 2
            or candidate.command_shape[1] != 7
            or candidate.command_shape[0]
            != len(candidate.trajectory.positions)
        ):
            # The v12.2 recovery runtime only accepts an exact (H, 7)
            # command with one predicted joint row per action.
            continue
        for steps in range(1, candidate.command_shape[0] + 1):
            prefix = _prefix_candidate(state, candidate, steps)
            assessed = select_escape_recovery_candidate(
                state,
                (prefix,),
                config=selected_config,
            )
            evaluations.extend(assessed.evaluations)
            if assessed.selected is not None:
                retained.append(prefix)
                break
    if not retained:
        return PrefixEscapeRecoverySelection(
            selected=None,
            selected_assessment=None,
            evaluations=tuple(evaluations),
            source_candidate_count=len(candidates),
            evaluated_prefix_count=len(evaluations),
            config_digest=selected_config.config_digest,
        )
    final = select_escape_recovery_candidate(
        state,
        tuple(retained),
        config=selected_config,
    )
    return PrefixEscapeRecoverySelection(
        selected=final.selected,
        selected_assessment=final.selected_assessment,
        evaluations=tuple(evaluations),
        source_candidate_count=len(candidates),
        evaluated_prefix_count=len(evaluations),
        config_digest=selected_config.config_digest,
    )


__all__ = [
    "PREFIX_ESCAPE_SCHEMA",
    "PrefixEscapeRecoverySelection",
    "select_prefix_escape_recovery_candidate",
]
