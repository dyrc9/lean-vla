from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_force_attributed_recovery_physics_domain_robustness_qualification as freezer,
)
from scripts import (
    run_v15_force_attributed_recovery_physics_domain_robustness_qualification as runner,
)


class _Simulation:
    def __init__(self) -> None:
        self.forward_count = 0
        self.model = SimpleNamespace(
            jnt_bodyid=np.arange(8, dtype=int),
            body_mass=np.arange(1.0, 9.0),
            dof_damping=np.arange(1.0, 9.0),
            geom_bodyid=np.repeat(np.arange(8, dtype=int), 2),
            geom_friction=np.ones((16, 3), dtype=np.float64),
        )

    def forward(self) -> None:
        self.forward_count += 1


def test_physics_condition_scales_only_registered_arm_parameters() -> None:
    sim = _Simulation()
    env = SimpleNamespace(sim=sim)
    robot = SimpleNamespace(_ref_joint_indexes=np.arange(1, 8, dtype=int))
    condition = {
        "condition_id": "combined",
        "arm_mass_scale": 0.8,
        "joint_damping_scale": 1.3,
        "arm_sliding_friction_scale": 0.7,
    }
    original_world_mass = float(sim.model.body_mass[0])
    original_world_friction = sim.model.geom_friction[:2, 0].copy()

    audit = runner._apply_physics_condition(
        env, robot, np.arange(1, 8, dtype=int), condition
    )

    assert audit["expected_parameter_identity"] is True
    assert audit["model_mismatch_injected"] is False
    assert sim.forward_count == 1
    assert sim.model.body_mass[0] == original_world_mass
    assert np.array_equal(
        sim.model.geom_friction[:2, 0], original_world_friction
    )
    assert np.allclose(sim.model.body_mass[1:8], np.arange(2.0, 9.0) * 0.8)
    assert np.allclose(
        sim.model.dof_damping[1:8], np.arange(2.0, 9.0) * 1.3
    )
    assert np.allclose(sim.model.geom_friction[2:, 0], 0.7)


def test_frozen_condition_matrix_is_unique_and_one_factor_at_a_time() -> None:
    conditions = runner.PHYSICS_CONDITIONS

    assert len(conditions) == 7
    assert len({row["condition_id"] for row in conditions}) == 7
    assert conditions[0]["condition_id"] == "nominal"
    for row in conditions[1:]:
        changed = sum(
            float(row[key]) != 1.0
            for key in (
                "arm_mass_scale",
                "joint_damping_scale",
                "arm_sliding_friction_scale",
            )
        )
        assert changed == 1


def test_selected_population_excludes_all_predecessor_pairs() -> None:
    clean = load_json_object(freezer.V14_CLEAN_PROTOCOL_PATH)
    sources = [
        load_json_object(freezer.V14_STRESS_PROTOCOL_PATH)["environments"],
        load_json_object(freezer.V15_DEVELOPMENT_PROTOCOL_PATH)["schedule"],
        load_json_object(freezer.V15_CALIBRATION_PROTOCOL_PATH)[
            "environments"
        ],
        load_json_object(freezer.V15_FRESH2_PROTOCOL_PATH)["environments"],
        load_json_object(freezer.FORCE_DEVELOPMENT_PROTOCOL_PATH)[
            "environments"
        ],
        load_json_object(freezer.V15_STRESS_PROTOCOL_PATH)["environments"],
    ]
    prior = freezer._pairs(clean["workloads"])
    for rows in sources:
        prior.update(freezer._pairs(rows))

    selected = freezer._select_environments(clean["workloads"], prior)

    assert len(selected) == 18
    assert not (freezer._pairs(selected) & prior)
    assert all(row["environment_seed"] == 6509 for row in selected)


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
    assert retained["selection"][
        "physics_domain_results_observed_before_freeze"
    ] is False
    assert retained["design"]["model_mismatch_injected"] is False
    assert retained["gates"]["expected_total_stress_lane_count"] == 5292
    assert retained["gates"]["expected_total_baseline_lane_count"] == 21168
