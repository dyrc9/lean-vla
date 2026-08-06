from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import (
    run_v15_incremental_adaptive_force_physics_qualification as runner,
)


def _minimal_protocol() -> dict:
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "status": runner.AUTHORIZED_STATUS,
        "execution_authorization": runner._expected_authorization(),
        "environments": [{} for _ in range(18)],
        "design": {
            "physics_conditions": [
                dict(row) for row in runner.PHYSICS_CONDITIONS
            ],
            "baselines": list(runner.BASELINES),
            "doses": [
                dict(row)
                for row in runner.development.v156.v155.v154.predecessor.base.calibration.v14.pilot.DOSES
            ],
            "qualification_population": True,
            "outcome_disclosed_population_reused": False,
            "dynamic_motion_generator_phase_bound": True,
            "gripper_current_action_bound": True,
            "incremental_extended_search": True,
            "maximum_extended_candidates_per_increment": 1,
            "extended_recovery_force_attribution_bound": True,
            "mechanism_parameters_unchanged_from_v15_7_development": True,
        },
        "selection": {
            "all_prior_exact_task_init_pairs_excluded": True,
            "physics_qualification_results_observed_before_freeze": False,
            "task_outcomes_used_for_selection": False,
        },
        "source": {"sha256": {}},
        "required_bindings": [],
    }


def test_minimal_registered_protocol_is_accepted() -> None:
    runner._verify_protocol(_minimal_protocol())


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("design", "qualification_population", False),
        ("design", "outcome_disclosed_population_reused", True),
        ("design", "incremental_extended_search", False),
        ("design", "maximum_extended_candidates_per_increment", 2),
        ("design", "mechanism_parameters_unchanged_from_v15_7_development", False),
        ("selection", "all_prior_exact_task_init_pairs_excluded", False),
        ("selection", "physics_qualification_results_observed_before_freeze", True),
        ("selection", "task_outcomes_used_for_selection", True),
    ],
)
def test_protocol_rejects_claim_population_or_mechanism_drift(
    section: str, field: str, value: object
) -> None:
    protocol = deepcopy(_minimal_protocol())
    protocol[section][field] = value
    with pytest.raises(
        runner.V15IncrementalAdaptiveForcePhysicsQualificationError
    ):
        runner._verify_protocol(protocol)


def test_output_root_must_remain_below_repository() -> None:
    with pytest.raises(
        runner.V15IncrementalAdaptiveForcePhysicsQualificationError
    ):
        runner._output_root({"fresh_output_root": "."})


def test_persisted_names_identify_v15_7() -> None:
    value = {
        "v15_6_metric": 1,
        "v15_5_dynamic_compatibility_metric": 2,
        "baseline": "v15_5_force_constrained_recovery",
    }
    persisted = runner._persist_names(value)
    assert persisted == {
        "v15_7_metric": 1,
        "v15_5_dynamic_compatibility_metric": 2,
        "baseline": runner.V15_BASELINE,
    }
