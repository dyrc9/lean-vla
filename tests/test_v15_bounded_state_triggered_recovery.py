from __future__ import annotations

import inspect

from scripts import (
    run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery as recovery,
)
from scripts import (
    run_v15_bounded_state_triggered_model_mismatch_development as development,
)


def test_runner_declares_bounded_state_triggered_schema() -> None:
    assert "v15.11" in recovery.BRAKE_AUDIT_SCHEMA
    assert "bounded_state_triggered" in recovery.RUNNER_VARIANT


def test_state_trigger_covers_registered_brake_margins() -> None:
    assert recovery.STATE_TRIGGER_MARGIN_RAD == 0.24
    assert recovery.STATE_TRIGGER_MARGIN_RAD >= max(
        recovery.adaptive.BRAKE_MARGINS_RAD
    )


def test_candidate_rollout_budget_is_strictly_bounded() -> None:
    assert recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS == 2
    assert recovery.STATE_TARGET_OFFSET_RAD == 0.04


def test_development_aggregate_binds_predecessor_immutably() -> None:
    assert development._BASE_AGGREGATE is not development._aggregate
    assert development._BASE_CALIBRATED_RUNTIME is not (
        development._patched_bounded_runtime
    )


def test_placeholder_does_not_claim_a_simulator_evaluation() -> None:
    spec = {
        "guard_margin_rad": 0.16,
        "guard_solref": (0.006, 1.0),
        "profile_id": "soft_primary",
        "fallback_profile": False,
        "recovery_candidate": False,
    }
    row = recovery._placeholder_candidate(spec, precheck_inside=True)
    assert row["configuration_precheck_inside_guard_ranges"] is True
    assert row["configuration_inside_guard_ranges"] is False
    assert row["candidate_screened"] is False


def test_shadow_candidate_callsite_is_registered_for_role_audit() -> None:
    source = inspect.getsource(recovery._bounded_state_triggered_core_step)
    assert (
        "candidate_transition = (\n"
        "                    self._env.step(action)\n"
        "                )"
    ) in source
