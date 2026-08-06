from __future__ import annotations

from scripts import run_v15_force_constrained_physics_development as runner


def test_v15_5_names_round_trip() -> None:
    value = {
        "baselines": {
            runner.v154.V15_BASELINE: {
                "v15_4_dynamic_state_restore_failure_count": 0
            }
        }
    }

    renamed = runner._replace_names(value)

    assert runner.V15_BASELINE in renamed["baselines"]
    assert runner._replace_names(renamed, reverse=True) == value


def test_screened_runtime_patch_restores_predecessor_function() -> None:
    force = runner.v154.predecessor.base.force_development
    before = force._run_screened

    with runner._patched_runtime():
        assert force._run_screened is runner._run_screened

    assert force._run_screened is before
