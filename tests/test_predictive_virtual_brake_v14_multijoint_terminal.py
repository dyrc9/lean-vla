from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_predictive_virtual_brake_v14_multijoint_clean_terminal as terminal


def test_fresh2_terminal_summary_preserves_calibration_nonpass() -> None:
    summary = terminal.build_summary()

    assert summary["classification"] == terminal.TERMINAL_CLASSIFICATION
    assert summary["episode_count"] == 180
    assert summary["mechanism"]["trigger_count"] == 29
    assert summary["mechanism"]["intervention_count"] == 12
    assert summary["mechanism"]["deadlock_count"] == 17
    assert summary["interpretation"][
        "l2_actual_below_floor_count"
    ] == 0
    assert summary["interpretation"][
        "l2_actual_crossing_count"
    ] == 0
    assert summary["calibration"][
        "risk_decision_false_safe_count"
    ] == 0
    assert summary["calibration"]["registered_gate_passed"] is False
    assert summary["task_outcomes"][
        "descriptive_clean_utility_gate_passed"
    ] is False


def test_fresh2_terminal_summary_is_current_when_present() -> None:
    if not terminal.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(terminal.OUTPUT_PATH)
    rebuilt = terminal.build_summary(
        created_at=str(retained["created_at"])
    )

    assert terminal.OUTPUT_PATH.read_text(
        encoding="utf-8"
    ) == terminal.canonical_text(rebuilt)
