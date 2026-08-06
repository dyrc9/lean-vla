from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from scripts import run_v14_multijoint_stress_design_pilot as pilot


class _DirectEnvironment:
    def __init__(self) -> None:
        self.sim = SimpleNamespace(
            data=SimpleNamespace(
                qpos=np.zeros(7, dtype=np.float64),
                qfrc_constraint=np.zeros(7, dtype=np.float64),
            )
        )

    def step(self, _action: Any) -> tuple[dict, float, bool, dict]:
        self.sim.data.qpos[0] += 0.06
        return {}, 123.0, True, {"task_outcome": "ignored"}


def test_margin_matrix_round_trip() -> None:
    matrix = np.arange(14, dtype=np.float64).reshape(7, 2)
    rows = pilot._margin_rows(matrix)

    restored = pilot.full_clean_margin_matrix(rows)

    assert np.array_equal(restored, matrix)


def test_exposure_counts_all_joint_sides() -> None:
    first = np.full((7, 2), 0.2)
    second = np.full((7, 2), 0.2)
    second[3, 1] = 0.1
    second[5, 0] = -0.01

    report = pilot._exposure([first, second])

    assert report["observed_state_count"] == 2
    assert report["observed_side_value_count"] == 28
    assert report["below_floor_count"] == 2
    assert report["crossing_count"] == 1
    assert report["minimum_margin_rad"] == -0.01


def test_reactive_baseline_stops_only_after_unsafe_step() -> None:
    env = _DirectEnvironment()
    limits = np.column_stack(
        (np.full(7, -1.0), np.full(7, 0.2))
    )

    report = pilot._run_direct(
        env,
        np.arange(7),
        limits,
        reactive=True,
    )

    assert report["executed_step_count"] == 1
    assert report["reactive_stop_count"] == 1
    assert report["trigger_count"] == 1
    assert report["intervention_count"] == 0
    assert report["below_floor_count"] == 1
    assert report["stop_reason"] == "post_step_below_floor"


def test_pilot_grid_covers_every_joint_side_dose_and_baseline() -> None:
    assert len(pilot.DOSES) == 3
    assert set(pilot.BASELINES) == {
        "no_guard",
        "reactive_stop",
        "shadow_only",
        "predictive_brake",
    }
    assert (
        pilot.full.JOINT_COUNT
        * 2
        * len(pilot.DOSES)
        * len(pilot.BASELINES)
        == 168
    )
