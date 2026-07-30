from __future__ import annotations

from scripts.run_simulator_recovery_margin_sweep_v12 import (
    MARGINS_RAD,
    OUTLIER_IDS,
    sweep_config,
)


def test_margin_sweep_reuses_only_frozen_outliers() -> None:
    config = sweep_config()

    assert tuple(
        row["base_pair_id"] for row in config["population"]["pairs"]
    ) == OUTLIER_IDS
    assert MARGINS_RAD == (0.18, 0.20, 0.25, 0.30)
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
