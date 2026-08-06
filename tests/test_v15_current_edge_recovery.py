from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_current_edge_recovery as recovery,
)


def _candidate(margin: float, eligible: bool) -> dict[str, object]:
    return {"guard_margin_rad": margin, "eligible": eligible}


def test_current_edge_config_appends_after_frozen_candidates() -> None:
    config = recovery.CurrentEdgeRecoveryConfig(0.154)

    assert config.guard_margins_rad == (
        *recovery.BRAKE_MARGINS_RAD,
        recovery.RECOVERY_GUARD_MARGIN_RAD,
        0.154,
    )


def test_current_edge_is_selected_only_after_v14_and_floor_fail() -> None:
    edge = 0.154
    audit = {
        "triggered": True,
        "deadlock": False,
        "selected_guard_margin_rad": edge,
        "candidates": [
            *[_candidate(value, False) for value in recovery.BRAKE_MARGINS_RAD],
            _candidate(recovery.RECOVERY_GUARD_MARGIN_RAD, False),
            _candidate(edge, True),
        ],
    }

    recovery._enrich_current_edge_audit(
        audit,
        configured_current_edge_margin_rad=edge,
    )

    assert audit["v14_baseline_would_deadlock"] is True
    assert audit["current_edge_recovery_eligible"] is True
    assert audit["current_edge_recovery_selected"] is True
    assert audit["floor_or_current_edge_recovery_prevented_deadlock"] is True


def test_original_candidate_keeps_precedence_over_both_fallbacks() -> None:
    edge = 0.154
    audit = {
        "triggered": True,
        "deadlock": False,
        "selected_guard_margin_rad": 0.16,
        "candidates": [
            _candidate(0.16, True),
            *[_candidate(value, False) for value in recovery.BRAKE_MARGINS_RAD[1:]],
            _candidate(recovery.RECOVERY_GUARD_MARGIN_RAD, True),
            _candidate(edge, True),
        ],
    }

    recovery._enrich_current_edge_audit(
        audit,
        configured_current_edge_margin_rad=edge,
    )

    assert audit["v14_baseline_would_deadlock"] is False
    assert audit["current_edge_recovery_selected"] is False
    assert audit["floor_or_current_edge_recovery_selected"] is False
