from __future__ import annotations

from scripts import (
    run_l2_predictive_virtual_brake_v15_incremental_adaptive_force_recovery as recovery,
)


def test_incremental_candidate_groups_split_extended_ladder() -> None:
    config = recovery.predecessor.AdaptiveForceRecoveryConfig(0.159)
    groups = recovery._incremental_candidate_groups(config)

    assert len(groups[0]) == 6
    assert len(groups) == 9
    assert all(len(group) == 1 for group in groups[1:8])
    assert len(groups[8]) == 9
    assert all(
        group[0]["profile_id"] == "soft_extended_recovery"
        for group in groups[1:8]
    )


def test_extended_candidate_is_bound_as_recovery_before_attribution() -> None:
    called = []
    audit = {
        "selected_guard_margin_rad": 0.157,
        "selected_candidate_profile_id": "soft_extended_recovery",
        "v14_baseline_would_deadlock": True,
        "deadlock": False,
        "candidates": [
            {
                "guard_margin_rad": 0.157,
                "candidate_profile_id": "soft_extended_recovery",
            }
        ],
    }

    def original(row, **_kwargs):
        called.append(row["floor_or_current_edge_recovery_selected"])
        row["force_attribution_active"] = True

    recovery._adaptive_force_attribution(original, audit)

    assert called == [True]
    assert audit[
        "incremental_extended_recovery_force_attribution_bound"
    ] is True
