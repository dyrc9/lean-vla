from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery as recovery,
)


def test_priority_config_preserves_v14_then_uses_current_before_floor() -> None:
    config = recovery.CurrentEdgePriorityRecoveryConfig(0.154)

    assert config.guard_margins_rad == (
        *recovery.BRAKE_MARGINS_RAD,
        0.154,
        recovery.RECOVERY_GUARD_MARGIN_RAD,
    )


def test_priority_config_uses_floor_when_current_edge_is_unavailable() -> None:
    config = recovery.CurrentEdgePriorityRecoveryConfig(None)

    assert config.guard_margins_rad == (
        *recovery.BRAKE_MARGINS_RAD,
        recovery.RECOVERY_GUARD_MARGIN_RAD,
    )
