from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_adaptive_force_recovery as recovery,
)


def test_adaptive_config_preserves_standard_order_and_adds_recovery_ladder() -> None:
    edge = 0.159
    config = recovery.AdaptiveForceRecoveryConfig(edge)

    assert config.guard_margins_rad[:4] == recovery.BRAKE_MARGINS_RAD
    assert config.trigger_margin_rad == 0.16
    assert config.safe_margin_floor_rad == 0.15
    assert config.recovery_margins_rad[0] == edge
    assert config.recovery_margins_rad[-1] == recovery.RECOVERY_GUARD_MARGIN_RAD
    assert len(config.recovery_margins_rad) == 9
    assert all(
        recovery.RECOVERY_GUARD_MARGIN_RAD < value < edge
        for value in config.recovery_margins_rad[1:-1]
    )


def test_adaptive_candidate_groups_use_stiff_profile_only_for_recovery() -> None:
    groups = recovery._candidate_groups(
        recovery.AdaptiveForceRecoveryConfig(0.159)
    )
    primary, extended, *fallbacks = groups

    assert len(groups) == 3
    assert len(primary) == 6
    assert len(extended) == 7
    assert all(len(fallback) == 9 for fallback in fallbacks)
    assert [row["guard_margin_rad"] for row in primary[:4]] == list(
        recovery.BRAKE_MARGINS_RAD
    )
    assert all(
        row["guard_solref"] == recovery.SOFT_GUARD_SOLREF
        for row in (*primary, *extended)
    )
    assert all(
        row["guard_solref"] == solref
        and row["recovery_candidate"] is True
        and row["fallback_profile"] is True
        for fallback, solref in zip(
            fallbacks, recovery.FALLBACK_GUARD_SOLREFS, strict=True
        )
        for row in fallback
    )


def test_registered_force_thresholds_are_inherited_unchanged() -> None:
    assert (
        recovery.predecessor.MAXIMUM_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
        == 10000.0
    )
    assert (
        recovery.predecessor.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
        == 1250.0
    )
    assert (
        recovery.predecessor.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
        == 1250.0
    )
