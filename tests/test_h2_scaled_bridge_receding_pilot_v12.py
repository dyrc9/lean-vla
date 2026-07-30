from __future__ import annotations

from scripts.run_h2_scaled_bridge_receding_pilot_v12 import (
    BRIDGE_SCALES,
    GATE_HORIZON_STEPS,
    pilot_config,
)


def test_h2_scaled_bridge_preserves_thresholds_and_h1_advance() -> None:
    config = pilot_config()
    library = config["recovery"]["candidate_library"]

    assert GATE_HORIZON_STEPS == 2
    assert BRIDGE_SCALES == (0.1, 0.25, 0.5, 0.75, 1.0)
    assert len(library) == 12 * 5 + 1 == 61
    assert len({spec["candidate_id"] for spec in library}) == 61
    assert all(
        -1.0 <= value <= 1.0
        for spec in library
        for value in spec["action"]
    )
    assert config["recovery"]["required_margin_gain_rad"] == 0.02
    assert (
        config["receding_horizon"][
            "advanced_policy_action_steps_per_cycle"
        ]
        == 1
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
