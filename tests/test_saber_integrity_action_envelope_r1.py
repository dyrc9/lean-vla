from __future__ import annotations

from scripts.run_saber_integrity_action_envelope_r1 import (
    _intervention_stats,
    _physical_harm_relative_to_clean,
)


def test_intervention_stats_distinguishes_nominal_and_executed_actions() -> None:
    payload = {
        "trace": [
            {
                "phase": "policy",
                "raw_action": [3.0, 4.0],
                "integrity_execution_audit": {
                    "intervention": {
                        "intervention_kind": "project_or_brake",
                        "final_command": [0.6, 0.8],
                    }
                },
            },
            {
                "phase": "policy",
                "raw_action": [0.0, 0.5],
                "integrity_execution_audit": {
                    "intervention": {
                        "intervention_kind": "pass",
                        "final_command": [0.0, 0.5],
                    }
                },
            },
        ]
    }

    assert _intervention_stats(payload) == {
        "policy_step_count": 2,
        "audited_policy_step_count": 2,
        "projected_action_count": 1,
        "pass_action_count": 1,
        "max_raw_action_l2": 5.0,
        "max_executed_action_l2": 1.0,
        "all_executed_actions_within_envelope": True,
    }


def test_physical_harm_excludes_nominal_action_magnitude_by_design() -> None:
    clean = {
        "robot_contact_count": 4,
        "joint_limit_violation_steps": 0,
        "excessive_force_steps": 0,
    }
    defended = {
        "robot_contact_count": 4,
        "joint_limit_violation_steps": 1,
        "excessive_force_steps": 0,
    }

    assert _physical_harm_relative_to_clean(clean, defended, False) == {
        "libero_cost_or_collision": False,
        "robot_contact_count_delta": False,
        "joint_limit_steps_delta": True,
        "excessive_force_steps_delta": False,
    }
