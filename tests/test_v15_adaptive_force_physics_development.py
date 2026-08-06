from __future__ import annotations

from copy import deepcopy

from scripts import run_v15_adaptive_force_physics_development as runner


def test_name_mapping_round_trips_nested_evidence() -> None:
    value = {
        "v15_5_force_constrained_recovery": {
            "v15_5_metric": ["v15_5_force_constrained_recovery"]
        }
    }

    renamed = runner._replace_names(value)

    assert "v15_6_adaptive_force_recovery" in renamed
    assert runner._replace_names(renamed, reverse=True) == value


def test_screened_runtime_records_adaptive_audits(monkeypatch) -> None:
    class FakeEnvironment:
        observations = [
            {
                "adaptive_force_recovery_active": True,
                "force_constrained_recovery_active": True,
                "selected_post_force_prediction_execution_identity": True,
                "selected_force_feasible": True,
                "force_rejected_base_eligible_candidate_count": 2,
                "adaptive_proactive_trigger_margin_rad": 0.16,
                "adaptive_extended_recovery_evaluated": True,
                "adaptive_extended_recovery_selected": True,
                "adaptive_fallback_profile_evaluated": False,
                "adaptive_fallback_profile_selected": False,
            }
        ]

    def fake_init(self, *_args, **_kwargs):
        self.observations = deepcopy(FakeEnvironment.observations)

    def fake_run(_env):
        wrapper_class = (
            runner.v155.v154.recovery.MultiJointDynamicStateRecoveryEnvironment
        )
        wrapper_class(object(), wait_steps=0, enabled=True, config=None)
        return {}

    original = runner.v155.v154._run_screened
    monkeypatch.setattr(
        runner.recovery.MultiJointAdaptiveForceRecoveryEnvironment,
        "__init__",
        fake_init,
    )
    monkeypatch.setattr(runner.v155.v154, "_run_screened", fake_run)
    try:
        result = runner._run_screened(object())
    finally:
        monkeypatch.setattr(runner.v155.v154, "_run_screened", original)

    assert result["adaptive_force_audit_count"] == 1
    assert result["extended_recovery_selected_count"] == 1
    assert result["proactive_trigger_margin_mismatch_count"] == 0
