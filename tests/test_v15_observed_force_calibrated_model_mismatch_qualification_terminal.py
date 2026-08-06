from __future__ import annotations

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_observed_force_calibrated_model_mismatch_qualification_terminal as terminal,
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return terminal.build_summary()


def test_terminal_preserves_nonpass_and_completed_safety_axes(summary: dict) -> None:
    assert summary["registered_qualification_pass"] is False
    assert summary["model_mismatch_claim_authorized"] is False
    assert summary["registered_result_unchanged"] is True
    assert all(summary["completed_axes"].values())
    assert summary["cross_condition"]["total_residual_deadlock_lane_count"] == 0


def test_terminal_records_latency_nonpass(summary: dict) -> None:
    cross = summary["cross_condition"]
    assert cross["maximum_prediction_execution_error_rad"] == pytest.approx(
        0.0003710839715758141
    )
    assert cross["maximum_attributable_joint_force_increment"] == pytest.approx(
        9501.115017421129
    )
    assert cross["worst_latency_max_seconds"] == pytest.approx(
        0.3729915659641847
    )
    assert cross["worst_100ms_deadline_miss_rate"] == pytest.approx(
        0.03492063492063492
    )
    assert all(
        set(row["failed_registered_gates"])
        == {"v15_3_100ms_deadline_miss_rate", "v15_3_latency_max"}
        for row in summary["conditions"].values()
    )


def test_terminal_binds_full_population_and_evidence(summary: dict) -> None:
    assert summary["population"]["excluded_prior_exact_pair_count"] == 329
    assert summary["population"]["stress_lane_count"] == 5292
    assert summary["bindings"]["evidence"]["bytes"] == 189900160
    assert summary["bindings"]["evidence"]["sha256"] == (
        "89d978133e974047869c17b4e73515eded9c3ae19080026837b490f0e23c06eb"
    )
    assert summary["observed_force_calibration_metrics"]["evaluation_count"] == 26460
    assert summary["observed_force_calibration_metrics"]["nonminimum_bind_count"] == 0


def test_committed_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(created_at=str(retained["created_at"]))
    assert rebuilt == retained
