from __future__ import annotations

from scripts.freeze_integrated_predictive_recovery_v12_terminal import (
    build_terminal,
)


def test_integrated_predictive_recovery_terminal_boundary() -> None:
    terminal = build_terminal()

    assert terminal["qualification_pass"] is True
    assert terminal["metrics"]["valid_case_count"] == 60
    assert terminal["metrics"]["expected_route_rate"] == 1.0
    assert terminal["metrics"]["negative_path_sink_apply_count"] == 0
    assert terminal["metrics"]["outcome_read_count"] == 0
    assert (
        terminal["lifecycle"]["simulator_integrated_pilot_authorized"]
        is True
    )
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False
