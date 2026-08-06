from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import (
    run_v15_incremental_adaptive_force_model_mismatch_qualification as runner,
)


def _minimal_protocol() -> dict:
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "status": runner.AUTHORIZED_STATUS,
        "execution_authorization": runner._expected_authorization(),
        "environments": [{} for _ in range(18)],
        "design": {
            "model_mismatch_conditions": [
                dict(row) for row in runner.MODEL_MISMATCH_CONDITIONS
            ],
            "baselines": list(runner.BASELINES),
            "doses": [
                dict(row)
                for row in runner.predecessor.development.v156.v155.v154.predecessor.base.calibration.v14.pilot.DOSES
            ],
            "qualification_population": True,
            "outcome_disclosed_population_reused": False,
            "actual_and_shadow_models_separated": True,
            "actual_model_restored_before_execution": True,
            "shadow_model_used_only_for_counterfactual_steps": True,
            "mechanism_parameters_unchanged_from_v15_7": True,
            "same_model_safety_force_and_latency_thresholds_unchanged": True,
            "same_model_prediction_identity_replaced_by_mismatch_audit": True,
            "incremental_extended_search": True,
            "maximum_extended_candidates_per_increment": 1,
        },
        "gates": {
            "prediction_execution_error_rad_max": 0.01,
            "model_mismatch_prediction_execution_error_rad_max": 0.01,
            "expected_model_mismatch_predictive_run_count": 10584,
            "expected_nontrivial_model_mismatch_predictive_run_count": 9072,
        },
        "selection": {
            "all_prior_exact_task_init_pairs_excluded": True,
            "model_mismatch_results_observed_before_freeze": False,
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
        ("design", "actual_and_shadow_models_separated", False),
        ("design", "actual_model_restored_before_execution", False),
        ("design", "shadow_model_used_only_for_counterfactual_steps", False),
        ("design", "mechanism_parameters_unchanged_from_v15_7", False),
        ("design", "same_model_safety_force_and_latency_thresholds_unchanged", False),
        ("design", "same_model_prediction_identity_replaced_by_mismatch_audit", False),
        ("selection", "all_prior_exact_task_init_pairs_excluded", False),
        ("selection", "model_mismatch_results_observed_before_freeze", True),
        ("selection", "task_outcomes_used_for_selection", True),
    ],
)
def test_protocol_rejects_population_model_or_selection_drift(
    section: str, field: str, value: object
) -> None:
    protocol = deepcopy(_minimal_protocol())
    protocol[section][field] = value
    with pytest.raises(
        runner.V15IncrementalAdaptiveForceModelMismatchQualificationError
    ):
        runner._verify_protocol(protocol)


def test_conditions_have_matched_control_and_six_nontrivial_mismatches() -> None:
    conditions = runner.MODEL_MISMATCH_CONDITIONS
    assert len(conditions) == 7
    assert conditions[0]["condition_id"] == "matched_nominal"
    for index, condition in enumerate(conditions):
        actual = (
            condition["actual_arm_mass_scale"],
            condition["actual_joint_damping_scale"],
            condition["actual_arm_sliding_friction_scale"],
        )
        shadow = (
            condition["shadow_arm_mass_scale"],
            condition["shadow_joint_damping_scale"],
            condition["shadow_arm_sliding_friction_scale"],
        )
        assert (actual == shadow) is (index == 0)


def test_protocol_rejects_mismatch_error_threshold_drift() -> None:
    protocol = _minimal_protocol()
    protocol["gates"]["prediction_execution_error_rad_max"] = 0.02
    with pytest.raises(
        runner.V15IncrementalAdaptiveForceModelMismatchQualificationError
    ):
        runner._verify_protocol(protocol)


class _DummySim:
    def __init__(self) -> None:
        self.model = SimpleNamespace(
            body_mass=np.ones(7, dtype=np.float64),
            dof_damping=np.ones(7, dtype=np.float64),
            geom_friction=np.ones((7, 3), dtype=np.float64),
            jnt_range=np.tile(np.asarray([-1.0, 1.0]), (7, 1)),
            jnt_solref=np.tile(np.asarray([0.02, 1.0]), (7, 1)),
            jnt_solimp=np.tile(
                np.asarray([0.9, 0.95, 0.001, 0.5, 2.0]), (7, 1)
            ),
        )

    def forward(self) -> None:
        return None


class _DummyEnvironment:
    def __init__(self) -> None:
        self.sim = _DummySim()
        self.observed_mass = []

    def step(self, action: object) -> object:
        del action
        self.observed_mass.append(float(self.sim.model.body_mass[0]))
        return None


def test_step_controller_uses_shadow_then_actual_for_repeated_signature() -> None:
    env = _DummyEnvironment()
    audit = {
        "actual_model_switch_count": 0,
        "shadow_model_switch_count": 0,
        "step_model_switch_identity_failure_count": 0,
        "step_role_identity_failure_count": 0,
        "predictive_run_count": 0,
        "predictive_run_count_by_baseline": {},
        "shadow_step_count_by_baseline": {},
        "actual_step_count_by_baseline": {},
        "step_role_identity_failure_count_by_baseline": {},
        "shadow_step_count": 0,
        "actual_step_count": 0,
    }
    controller = runner._StepModelController(
        env=env,
        model=env.sim.model,
        body_ids=np.arange(7),
        dof_ids=np.arange(7),
        geom_ids=np.arange(7),
        joint_ids=np.arange(7),
        actual_mass=np.full(7, 0.8),
        actual_damping=np.full(7, 0.7),
        actual_friction=np.full(7, 0.6),
        shadow_mass=np.ones(7),
        shadow_damping=np.ones(7),
        shadow_friction=np.ones(7),
        audit=audit,
        role_classifier=iter(("shadow", "actual")).__next__,
    )

    def operation() -> dict:
        env.step(None)
        env.step(None)
        return {"shadow_env_step_count": 1, "deadlock": False}

    controller.run("test", operation)
    assert env.observed_mass == [1.0, 0.8]
    assert np.array_equal(env.sim.model.body_mass, np.full(7, 0.8))
    assert audit["predictive_run_count"] == 1
    assert audit["shadow_step_count"] == 1
    assert audit["actual_step_count"] == 1
    assert audit["step_model_switch_identity_failure_count"] == 0
    assert audit["step_role_identity_failure_count"] == 0
    assert "step" not in env.__dict__


def test_numpy_proxy_records_expected_force_divergence_only() -> None:
    proxy = runner._ModelMismatchNumpyProxy(np)
    assert proxy.isclose(10.0, 11.0, rtol=0.0, atol=1e-12) is True
    assert proxy.isclose(0.15, 0.16, rtol=0.0, atol=1e-6) is np.False_
    assert proxy.force_comparisons == [
        {
            "predicted": 10.0,
            "actual": 11.0,
            "absolute_difference": 1.0,
            "same_model_identity": False,
        }
    ]


def test_output_root_must_remain_below_repository() -> None:
    with pytest.raises(
        runner.V15IncrementalAdaptiveForceModelMismatchQualificationError
    ):
        runner._output_root({"fresh_output_root": "."})
