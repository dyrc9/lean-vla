from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import (
    run_v15_dynamic_state_physics_robustness_qualification as runner,
)


def _minimal_protocol() -> dict:
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "status": runner.AUTHORIZED_STATUS,
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "physics_domain_robustness_claim": True,
            "model_mismatch_claim": False,
            "task_utility_claim": False,
            "real_time_claim": False,
        },
        "environments": [{} for _ in range(18)],
        "design": {
            "physics_conditions": [
                dict(row) for row in runner.PHYSICS_CONDITIONS
            ],
            "baselines": list(runner.BASELINES),
            "doses": [
                dict(row)
                for row in (
                    runner.development.predecessor.base.calibration.v14.pilot.DOSES
                )
            ],
            "qualification_population": True,
            "outcome_disclosed_population_reused": False,
            "dynamic_motion_generator_phase_bound": True,
            "gripper_current_action_bound": True,
        },
        "selection": {
            "all_prior_exact_task_init_pairs_excluded": True,
            "physics_domain_results_observed_before_freeze": False,
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
        ("design", "dynamic_motion_generator_phase_bound", False),
        ("design", "gripper_current_action_bound", False),
        ("selection", "all_prior_exact_task_init_pairs_excluded", False),
        ("selection", "physics_domain_results_observed_before_freeze", True),
    ],
)
def test_protocol_rejects_claim_or_population_drift(
    section: str, field: str, value: bool
) -> None:
    protocol = deepcopy(_minimal_protocol())
    protocol[section][field] = value
    with pytest.raises(runner.V15DynamicStatePhysicsQualificationError):
        runner._verify_protocol(protocol)


def test_output_root_must_remain_below_repository() -> None:
    with pytest.raises(runner.V15DynamicStatePhysicsQualificationError):
        runner._output_root({"fresh_output_root": "."})
