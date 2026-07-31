from __future__ import annotations

from scripts import (
    freeze_v14_multijoint_stress_development_terminal as terminal,
)


def test_terminal_preserves_registered_nonpass_and_descriptive_signal() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_development_data_complete"] is False
    assert summary["registered_gate_results"] == {
        "baseline_lane_count": True,
        "environment_count": True,
        "environment_lane_coverage": True,
        "no_guard_shadow_trace_identity": False,
        "restore_identity": True,
        "stress_lane_count": True,
        "zero_policy_or_outcome_fields": True,
    }
    assert summary["population"] == {
        "environment_count": 12,
        "suite_count": 3,
        "stress_lane_count": 504,
        "baseline_lane_count": 2016,
        "joint_side_count_per_environment": 14,
        "dose_count": 3,
    }
    assert summary["baselines"]["shadow_only"]["crossing_count"] > 0
    assert summary["baselines"]["predictive_brake"]["crossing_count"] == 0
    assert summary["baselines"]["reactive_stop"]["below_floor_count"] > 0
    assert summary["baselines"]["predictive_brake"]["below_floor_count"] == 0
    identity = summary["no_guard_shadow_identity_diagnostic"]
    assert identity["all_joint_side_error"]["maximum_rad"] > 0.001
    assert identity[
        "all_registered_threshold_classifications_identical"
    ] is True
    assert not any(
        identity["threshold_classification_disagreement_count"].values()
    )
    assert summary["latency_deadline_diagnostic"]["predictive_brake"][
        "deadline_miss_count"
    ] > 0
    assert summary["interpretation"][
        "registered_result_unchanged"
    ] is True
