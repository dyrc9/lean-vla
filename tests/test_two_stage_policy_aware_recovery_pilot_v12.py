from __future__ import annotations

from scripts.run_two_stage_policy_aware_recovery_pilot_v12 import (
    PARENT_PREFIX_IDS,
    SCREENING_SEED_OFFSETS,
    SECOND_STAGE_HORIZONS,
    TARGET_ID,
    composite_specs,
    pilot_config,
)


def test_two_stage_pilot_freezes_bounded_shadow_only_search() -> None:
    config = pilot_config()
    specs = composite_specs(config)

    assert config["population"]["pair_count"] == 1
    assert (
        config["population"]["pairs"][0]["base_pair_id"] == TARGET_ID
    )
    assert len(PARENT_PREFIX_IDS) == 4
    assert SECOND_STAGE_HORIZONS == (1, 2, 3)
    assert SCREENING_SEED_OFFSETS == (0, 1)
    assert len(specs) == 4 * 13 * 3 == 156
    assert len({spec["candidate_id"] for spec in specs}) == 156
    assert min(spec["action_count"] for spec in specs) == 4
    assert max(spec["action_count"] for spec in specs) == 9
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["execution_boundary"][
            "typed_recovery_env_step_authorized"
        ]
        is False
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
