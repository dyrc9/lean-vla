from __future__ import annotations

from scripts import run_v15_dynamic_state_physics_development as runner


def test_compatibility_names_round_trip() -> None:
    old = {
        "baselines": {
            runner.OLD_V14_BASELINE: {
                "v15_3_schema_mismatch_count": 0,
            },
            runner.OLD_V15_BASELINE: {
                "dynamic_state_restore_failure_count": 0,
            },
        }
    }

    renamed = runner._replace_names(old)

    assert runner.V14_BASELINE in renamed["baselines"]
    assert runner.V15_BASELINE in renamed["baselines"]
    assert (
        renamed["baselines"][runner.V14_BASELINE][
            "v15_4_schema_mismatch_count"
        ]
        == 0
    )
    assert runner._replace_names(renamed, reverse=True) == old


def test_dynamic_runtime_patch_restores_predecessor_functions() -> None:
    core = runner.predecessor.base.calibration.v14.full.core
    force = runner.predecessor.base.force_development
    before = (
        core.capture_warmstart_policy_shadow_snapshot,
        core.restore_warmstart_policy_shadow_snapshot,
        core._restore_identity,
        force._run_screened,
    )

    with runner._patched_dynamic_runtime():
        assert (
            core.capture_warmstart_policy_shadow_snapshot
            is runner.capture_dynamic_state_policy_shadow_snapshot
        )
        assert force._run_screened is runner._run_screened

    after = (
        core.capture_warmstart_policy_shadow_snapshot,
        core.restore_warmstart_policy_shadow_snapshot,
        core._restore_identity,
        force._run_screened,
    )
    assert after == before
