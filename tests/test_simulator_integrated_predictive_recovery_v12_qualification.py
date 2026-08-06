from __future__ import annotations

import json

from scripts.freeze_simulator_integrated_predictive_recovery_v12_qualification import (
    PILOT_SUMMARY_PATH,
    build_protocol,
)
from scripts.run_simulator_integrated_predictive_recovery_v12_qualification import (
    evaluate_gates,
)


def test_formal_population_is_disjoint_and_stresses_known_outlier() -> None:
    protocol = build_protocol()
    pairs = protocol["population"]["pairs"]

    assert len(pairs) == 9
    assert all("task11_" not in row["base_pair_id"] for row in pairs)
    assert {row["synthetic_joint_index"] for row in pairs} == set(range(7))
    assert sum(
        row["synthetic_joint_index"] == 1
        and row["synthetic_joint_side"] == "upper"
        for row in pairs
    ) == 3
    assert (
        protocol["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
    assert (
        protocol["execution_boundary"][
            "set_init_state_wrapper_authorized"
        ]
        is False
    )


def test_formal_gates_reject_active_mujoco_warning() -> None:
    protocol = build_protocol()
    pilot = json.loads(PILOT_SUMMARY_PATH.read_text())
    metrics = dict(pilot["metrics"])
    metrics.update(
        {
            "valid_case_count": 18,
            "post_recovery_allow_exact_count": 9,
            "policy_inference_count": 27,
        }
    )

    passing = evaluate_gates(protocol, metrics)
    assert all(gate["passed"] for gate in passing.values())

    metrics["mujoco_active_warning_count"] = 1
    failing = evaluate_gates(protocol, metrics)
    assert (
        failing["mujoco_active_warning_count_max"]["passed"] is False
    )
