from __future__ import annotations

from scripts import (
    run_v15_incremental_adaptive_force_physics_development as runner,
)


def test_name_mapping_round_trips_nested_evidence() -> None:
    value = {
        "v15_5_force_constrained_recovery": {
            "v15_5_metric": ["v15_5_force_constrained_recovery"]
        }
    }

    renamed = runner._replace_names(value)

    assert "v15_7_incremental_adaptive_force_recovery" in renamed
    assert runner._replace_names(renamed, reverse=True) == value


def test_runner_contract_patch_restores_base_module() -> None:
    original_schema = runner.v156.PROTOCOL_SCHEMA
    original_replace = runner.v156._replace_names

    with runner._patched_runner_contract():
        assert runner.v156.PROTOCOL_SCHEMA == runner.PROTOCOL_SCHEMA
        assert runner.v156._replace_names is runner._replace_names

    assert runner.v156.PROTOCOL_SCHEMA == original_schema
    assert runner.v156._replace_names is original_replace
