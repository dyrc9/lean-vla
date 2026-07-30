from __future__ import annotations

from scripts.run_continuous_blend_recovery_pilot_v12 import (
    PARENT_PREFIX_ID,
    PERTURBATION_AMPLITUDES,
    PERTURBATION_AXES,
    Z_AMPLITUDES,
    local_blend_specs,
    pilot_config,
)


def test_continuous_blend_pilot_freezes_local_safe_search() -> None:
    config = pilot_config()
    specs = local_blend_specs(config)

    assert PARENT_PREFIX_ID == "positive_y@h5"
    assert len(Z_AMPLITUDES) == 4
    assert len(PERTURBATION_AXES) == 5
    assert len(PERTURBATION_AMPLITUDES) == 8
    assert len(specs) == 4 * (1 + 5 * 8) == 164
    assert len({spec["candidate_id"] for spec in specs}) == 164
    assert {spec["action_count"] for spec in specs} == {6}
    assert all(
        -1.0 <= value <= 1.0
        for spec in specs
        for action in spec["actions"]
        for value in action
    )
    assert all(spec["actions"][-1][2] > 0 for spec in specs)
    assert config["recovery"]["safe_margin_rad"] == 0.15
    assert (
        config["execution_boundary"][
            "typed_recovery_env_step_authorized"
        ]
        is False
    )
    assert (
        config["execution_boundary"]["policy_action_dispatch_authorized"]
        is False
    )
    assert (
        config["execution_boundary"]["task_outcome_read_authorized"]
        is False
    )
