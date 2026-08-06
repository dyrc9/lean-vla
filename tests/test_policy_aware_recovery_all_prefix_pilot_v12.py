from __future__ import annotations

from scripts.run_policy_aware_recovery_all_prefix_pilot_v12 import (
    SCREENING_SEED_OFFSETS,
    TARGET_IDS,
    pilot_config,
)


def test_all_prefix_pilot_targets_only_unresolved_cases() -> None:
    config = pilot_config()

    assert tuple(
        row["base_pair_id"] for row in config["population"]["pairs"]
    ) == TARGET_IDS
    assert SCREENING_SEED_OFFSETS == (0, 1)
    assert (
        config["screening"]["candidate_prefix_mode"]
        == "all_recovery_safe_prefixes"
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
