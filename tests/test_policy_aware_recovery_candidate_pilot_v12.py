from __future__ import annotations

from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (
    SCREENING_SEED_OFFSETS,
    pilot_config,
)


def test_policy_aware_candidate_pilot_is_shadow_only() -> None:
    config = pilot_config()

    assert SCREENING_SEED_OFFSETS == (0, 1)
    assert config["population"]["pair_count"] == 3
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
    assert "both frozen" in config["screening"]["candidate_rule"]
