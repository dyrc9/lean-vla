from __future__ import annotations

from scripts.run_h3_nullspace_exact_h1_replayfix_v12 import (
    pilot_config,
)


def test_replayfix_changes_only_audit_serialization() -> None:
    config = pilot_config()
    replay = config["mechanical_replay"]
    contract = config["controller_nullspace_exact_h1_contract"]

    assert replay["method_parameters_changed"] is False
    assert replay["population_changed"] is False
    assert replay["success_gate_changed"] is False
    assert contract["retreat_offsets_rad"] == [
        0.05,
        0.10,
        0.20,
        0.30,
        0.50,
    ]
    assert contract["minimum_margin_floor_rad"] == 0.15
    assert contract["exact_source_policy_action_required"] is True
    assert contract["action_substitution_authorized"] is False
    assert (
        contract["simulator_qpos_modified_by_configuration"] is False
    )
    assert (
        contract["simulator_qvel_modified_by_configuration"] is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
