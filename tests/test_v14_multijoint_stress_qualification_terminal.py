from __future__ import annotations

from scripts import (
    freeze_v14_multijoint_stress_qualification_terminal as terminal,
)


def test_terminal_preserves_nonpass_and_separates_registered_axes() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return

    summary = terminal.build_summary()

    assert summary["registered_qualification_pass"] is False
    assert summary["failed_registered_gates"] == [
        "low_negative_control"
    ]
    assert summary["registered_axes"] == {
        "integrity_complete": True,
        "core_mechanism_gates_complete": True,
        "system_timing_gates_complete": True,
        "low_negative_control_complete": False,
        "overall_pass_is_conjunction": True,
    }
    assert summary["population"] == {
        "environment_count": 18,
        "suite_count": 3,
        "stress_lane_count": 756,
        "baseline_lane_count": 3024,
        "new_task_init_pairs": True,
        "environment_seed": 1509,
    }
    assert len(summary["low_negative_control_failures"]) == 2
    assert summary["baselines"]["shadow_only"]["crossing_count"] == 818
    assert summary["baselines"]["predictive_brake"]["crossing_count"] == 0
    assert summary["baselines"]["reactive_stop"]["below_floor_count"] == 402
    assert summary["baselines"]["predictive_brake"]["below_floor_count"] == 0
    assert summary["contact_capacity"]["phases"]["active"][
        "contact_capacity_warning_count"
    ] == 0
    assert summary["contact_capacity"]["phases"]["prebinding"][
        "contact_capacity_warning_count"
    ] == 8
    assert summary["predictive_latency_deadline"]["miss_rate"] <= 0.025
    assert summary["interpretation"][
        "registered_result_unchanged"
    ] is True


def test_environment_cluster_bootstrap_is_deterministic() -> None:
    protocol = terminal.load_json_object(terminal.runner.DEFAULT_PROTOCOL)
    if not terminal.runner._output_root(protocol).is_dir():
        return
    evidence = terminal.runner.validate_results(
        protocol,
        protocol_path=terminal.runner.DEFAULT_PROTOCOL,
    )

    first = terminal._cluster_bootstrap(evidence["lanes"])
    second = terminal._cluster_bootstrap(evidence["lanes"])

    assert first == second
    assert first["predictive_minus_shadow_crossings_per_lane"][
        "estimate"
    ] < 0
    assert first["predictive_minus_reactive_below_floor_per_lane"][
        "estimate"
    ] < 0
