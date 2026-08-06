from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_current_edge_priority_recovery_stress_qualification_fresh2 as freezer,
)
from scripts import (
    run_v15_current_edge_priority_recovery_stress_qualification_fresh2 as runner,
)


def test_compatibility_view_adds_only_required_analysis_aliases() -> None:
    protocol = {
        "gates": {
            "v15_2_selected_floor_violation_count_max": 0,
            "other_gate": 7,
        }
    }

    compatible = runner._compatibility_protocol(protocol)

    assert protocol == {
        "gates": {
            "v15_2_selected_floor_violation_count_max": 0,
            "other_gate": 7,
        }
    }
    assert compatible["gates"] == {
        "v15_2_selected_floor_violation_count_max": 0,
        "selected_floor_violation_count_max": 0,
        "control_period_seconds": 0.05,
        "other_gate": 7,
    }


def test_analyze_supplies_aliases_without_changing_registered_protocol(
    monkeypatch,
) -> None:
    protocol = {
        "gates": {"v15_2_selected_floor_violation_count_max": 0}
    }
    observed = {}

    def fake_analyze(received, rows, **kwargs):
        observed["protocol"] = received
        observed["rows"] = rows
        observed["kwargs"] = kwargs
        return {"metric": 1}, {"gate": True}

    monkeypatch.setattr(runner.predecessor, "_analyze", fake_analyze)

    result = runner._analyze(
        protocol,
        [],
        restore_failure_count=0,
        maximum_no_guard_shadow_error=0.0,
        contact_reports=[],
    )

    assert result == ({"metric": 1}, {"gate": True})
    assert observed["protocol"]["gates"][
        "selected_floor_violation_count_max"
    ] == 0
    assert observed["protocol"]["gates"]["control_period_seconds"] == 0.05
    assert protocol == {
        "gates": {"v15_2_selected_floor_violation_count_max": 0}
    }


def test_frozen_fresh2_protocol_is_current_and_unchanged_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)
    source = load_json_object(freezer.FRESH1_PROTOCOL_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
    assert retained["environments"] == source["environments"]
    assert retained["gates"] == source["gates"]
    assert retained["execution_authorization"] == source[
        "execution_authorization"
    ]
