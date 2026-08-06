from __future__ import annotations

import pytest

from scripts.run_four_arm_v4_l1_progress_projection_clean import (
    ProgressProjectionCleanRunnerError,
    _online_metrics,
)


def _candidate(reason: str, *, violations=()) -> dict:
    return {
        "eligible_selected_source_candidate_index": 0,
        "candidates": [
            {
                "progress_projection": {"reason": reason},
                "checked": {
                    "hard_violation_atoms": list(violations),
                },
            }
        ],
    }


def test_online_metrics_count_projection_and_release_bypass() -> None:
    payload = {
        "observation_frame_audits": [
            {
                "online_progress_projection_v3": _candidate(
                    "minimum_l2_terminal_progress_projection"
                )
            },
            {
                "online_progress_projection_v3": _candidate(
                    "nominal_checker_eligible_without_projection:release"
                )
            },
        ]
    }

    metrics = _online_metrics(payload, l1_enabled=True)

    assert metrics["online_audit_count"] == 2
    assert metrics["online_eligible_audit_count"] == 2
    assert metrics["online_selected_hard_violation_count"] == 0
    assert metrics["online_release_bypass_count"] == 1


def test_non_l1_metrics_require_absent_projection_audits() -> None:
    payload = {"observation_frame_audits": [{}]}

    assert _online_metrics(payload, l1_enabled=False) == {
        "online_audit_count": 0,
        "online_eligible_audit_count": 0,
        "online_selected_hard_violation_count": 0,
        "online_projection_reason_counts": {},
        "online_release_bypass_count": 0,
    }


def test_non_l1_metrics_reject_projection_audit() -> None:
    payload = {
        "observation_frame_audits": [
            {
                "online_progress_projection_v3": _candidate(
                    "numeric_envelope_only"
                )
            }
        ]
    }

    with pytest.raises(ProgressProjectionCleanRunnerError):
        _online_metrics(payload, l1_enabled=False)
