from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_floor_guard_recovery as recovery,
)


def _candidate(margin: float, *, eligible: bool) -> dict[str, object]:
    return {
        "guard_margin_rad": margin,
        "eligible": eligible,
    }


def test_recovery_configuration_preserves_v14_order_then_fallback() -> None:
    config = recovery.FloorGuardRecoveryConfig()

    assert config.guard_margins_rad[:-1] == recovery.BRAKE_MARGINS_RAD
    assert config.guard_margins_rad[-1] == 0.150001
    assert config.safe_margin_floor_rad == 0.15
    assert config.guard_margins_rad[-1] > config.safe_margin_floor_rad
    assert config.guard_margins_rad[-1] < min(
        recovery.BRAKE_MARGINS_RAD
    )


def test_recovery_audit_identifies_prevented_v14_deadlock() -> None:
    audit = {
        "triggered": True,
        "deadlock": False,
        "selected_guard_margin_rad": 0.150001,
        "candidates": [
            *[
                _candidate(margin, eligible=False)
                for margin in recovery.BRAKE_MARGINS_RAD
            ],
            _candidate(0.150001, eligible=True),
        ],
    }

    recovery._enrich_recovery_audit(audit)

    assert audit["v14_baseline_would_deadlock"] is True
    assert audit["floor_guard_recovery_eligible"] is True
    assert audit["floor_guard_recovery_selected"] is True
    assert audit["floor_guard_recovery_prevented_deadlock"] is True
    assert audit["v14_baseline_eligible_candidate_count"] == 0


def test_recovery_does_not_replace_eligible_v14_candidate() -> None:
    audit = {
        "triggered": True,
        "deadlock": False,
        "selected_guard_margin_rad": 0.16,
        "candidates": [
            _candidate(0.16, eligible=True),
            *[
                _candidate(margin, eligible=False)
                for margin in recovery.BRAKE_MARGINS_RAD[1:]
            ],
            _candidate(0.150001, eligible=True),
        ],
    }

    recovery._enrich_recovery_audit(audit)

    assert audit["v14_baseline_would_deadlock"] is False
    assert audit["floor_guard_recovery_selected"] is False
    assert audit["floor_guard_recovery_prevented_deadlock"] is False
    assert audit["v14_baseline_eligible_candidate_count"] == 1
