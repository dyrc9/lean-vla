from __future__ import annotations

import math

import pytest

from proofalign.semantic_action_selection import (
    ActionSelectionError,
    CheckedActionBlock,
    select_checked_action_block,
)


SUBTASK_DIGEST = "a" * 64


def _candidate(
    index: int,
    *,
    nominal: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0),
    final: tuple[float, ...] | None = None,
    known: bool = True,
    compatible: bool = True,
    post_compatible: bool = True,
    violations: tuple[str, ...] = (),
    margin: float = 1.0,
    digest: str = SUBTASK_DIGEST,
) -> CheckedActionBlock:
    return CheckedActionBlock(
        candidate_index=index,
        semantic_subtask_digest=digest,
        nominal_command=nominal,
        final_command=nominal if final is None else final,
        command_shape=(2, 2),
        known=known,
        semantic_compatible=compatible,
        post_projection_compatible=post_compatible,
        hard_violation_atoms=violations,
        progress_margin=margin,
    )


def _select(*candidates: CheckedActionBlock):
    return select_checked_action_block(
        candidates,
        expected_semantic_subtask_digest=SUBTASK_DIGEST,
        min_progress_margin=0.5,
        max_projection_l2=0.5,
    )


def test_selector_rejects_unknown_semantic_mismatch_and_hard_violations() -> None:
    decision = _select(
        _candidate(0, known=False),
        _candidate(1, compatible=False),
        _candidate(2, violations=("workspace_exit",)),
        _candidate(3, margin=0.9),
    )

    assert decision.selected_candidate_index == 3
    assert decision.dispositions[0].reasons == ("unknown",)
    assert decision.dispositions[1].reasons == ("semantic_mismatch",)
    assert decision.dispositions[2].reasons == ("hard_violation",)
    assert decision.dispositions[3].eligible


def test_selector_never_repairs_semantic_mismatch_with_projection() -> None:
    decision = _select(
        _candidate(
            0,
            compatible=False,
            nominal=(0.0, 0.0, 0.0, 0.0),
            final=(0.1, 0.0, 0.0, 0.0),
            margin=10.0,
        )
    )

    assert decision.selected is None
    assert "semantic_mismatch" in decision.dispositions[0].reasons


def test_selector_requires_post_projection_semantic_compatibility_and_budget() -> None:
    decision = _select(
        _candidate(
            0,
            final=(0.1, 0.0, 0.0, 0.0),
            post_compatible=False,
        ),
        _candidate(
            1,
            final=(1.0, 0.0, 0.0, 0.0),
        ),
    )

    assert decision.selected is None
    assert decision.dispositions[0].reasons == ("post_projection_semantic_mismatch",)
    assert decision.dispositions[1].reasons == ("projection_budget_exceeded",)


def test_selector_uses_progress_then_projection_then_smoothness_then_index() -> None:
    higher_progress = _candidate(
        3,
        nominal=(0.0, 0.0, 0.0, 0.0),
        final=(0.2, 0.0, 0.2, 0.0),
        margin=2.0,
    )
    lower_progress = _candidate(0, margin=1.0)
    assert _select(lower_progress, higher_progress).selected_candidate_index == 3

    low_projection = _candidate(2, margin=1.0)
    high_projection = _candidate(
        1,
        final=(0.1, 0.0, 0.1, 0.0),
        margin=1.0,
    )
    assert _select(high_projection, low_projection).selected_candidate_index == 2

    rough = _candidate(6, nominal=(0.0, 0.0, 1.0, 0.0), margin=1.0)
    smooth = _candidate(7, margin=1.0)
    assert _select(rough, smooth).selected_candidate_index == 7

    lower_index = _candidate(4, margin=1.0)
    higher_index = _candidate(5, margin=1.0)
    assert _select(higher_index, lower_index).selected_candidate_index == 4


def test_selection_binds_projected_final_block_not_nominal_block() -> None:
    nominal = _candidate(0)
    projected = _candidate(
        0,
        final=(0.1, 0.0, 0.1, 0.0),
    )

    assert nominal.final_action_block_digest != projected.final_action_block_digest
    assert projected.projection_l2 == pytest.approx(math.sqrt(0.02))


def test_selector_rejects_mixed_subtasks_shapes_and_duplicate_indices() -> None:
    with pytest.raises(ActionSelectionError, match="same fixed semantic subtask"):
        _select(_candidate(0), _candidate(1, digest="b" * 64))
    with pytest.raises(ActionSelectionError, match="indices must be unique"):
        _select(_candidate(0), _candidate(0))
    with pytest.raises(ActionSelectionError, match="same executable-prefix shape"):
        select_checked_action_block(
            (
                _candidate(0),
                CheckedActionBlock(
                    candidate_index=1,
                    semantic_subtask_digest=SUBTASK_DIGEST,
                    nominal_command=(0.0, 0.0, 0.0),
                    final_command=(0.0, 0.0, 0.0),
                    command_shape=(1, 3),
                    known=True,
                    semantic_compatible=True,
                    post_projection_compatible=True,
                    progress_margin=1.0,
                ),
            ),
            expected_semantic_subtask_digest=SUBTASK_DIGEST,
            min_progress_margin=0.5,
            max_projection_l2=0.5,
        )


def test_selector_requires_exact_trusted_semantic_subtask_digest() -> None:
    with pytest.raises(ActionSelectionError, match="trusted expected subtask"):
        select_checked_action_block(
            (_candidate(0),),
            expected_semantic_subtask_digest="b" * 64,
            min_progress_margin=0.5,
            max_projection_l2=0.5,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("candidate_index", -1),
        ("semantic_subtask_digest", "bad"),
        ("progress_margin", math.nan),
    ),
)
def test_checked_action_block_rejects_malformed_fields(
    field: str, value: object
) -> None:
    kwargs = {
        "candidate_index": 0,
        "semantic_subtask_digest": SUBTASK_DIGEST,
        "nominal_command": (0.0, 0.0, 0.0, 0.0),
        "final_command": (0.0, 0.0, 0.0, 0.0),
        "command_shape": (2, 2),
        "known": True,
        "semantic_compatible": True,
        "post_projection_compatible": True,
        "progress_margin": 1.0,
    }
    kwargs[field] = value

    with pytest.raises(ActionSelectionError):
        CheckedActionBlock(**kwargs)  # type: ignore[arg-type]
