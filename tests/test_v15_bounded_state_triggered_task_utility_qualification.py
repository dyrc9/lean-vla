from __future__ import annotations

from types import SimpleNamespace

from scripts import (
    run_v15_bounded_state_triggered_task_utility_qualification as qualification,
)


def test_clean_runner_declares_v15_14_identity() -> None:
    assert "v15.14" in qualification.PROTOCOL_SCHEMA
    assert "v15_14" in qualification.AUTHORIZED_STATUS
    assert qualification._TASK_METHOD_VERSION == "v15.14"
    assert qualification._TASK_STATE_TRIGGER_MARGIN_RAD == 0.30
    assert qualification._TASK_RECOVERY_FORCE_INCREMENT_LIMIT == 10000.0
    assert qualification._OnlineAdapter.SAFE_MARGIN_FLOOR_RAD == 0.15
    assert qualification._OnlineAdapter.RUNNER_VARIANT == (
        qualification.online.RUNNER_VARIANT
    )
    assert qualification._OnlineAdapter.BRAKE_AUDIT_SCHEMA == (
        qualification.online.BRAKE_AUDIT_SCHEMA
    )


def test_online_adapter_exposes_legacy_four_arm_constants() -> None:
    assert qualification._OnlineAdapter.SAFE_MARGIN_FLOOR_RAD == 0.15
    assert qualification._OnlineAdapter.TARGET_JOINT_INDEX is None
    assert len(qualification._OnlineAdapter.BRAKE_MARGINS_RAD) == 4


def test_task_runtime_temporarily_binds_and_restores_successor_limits() -> None:
    force_module = qualification.online.adaptive.predecessor
    original_trigger = qualification.online.STATE_TRIGGER_MARGIN_RAD
    original_scope_limit = (
        force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
    )
    original_post_limit = (
        force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
    )
    diagnosed_candidate = {
        "scope_positive_joint_increment": 2438.6361565595053,
        "post_step_absolute_risk_force": 0.1,
        "post_step_positive_joint_increment": 0.0,
    }
    assert force_module._force_feasible(
        diagnosed_candidate, recovery_candidate=True
    ) is False

    with qualification._patched_same_model_runtime():
        assert qualification.online.STATE_TRIGGER_MARGIN_RAD == 0.30
        assert (
            force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
            == 10000.0
        )
        assert (
            force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
            == 10000.0
        )
        assert force_module._force_feasible(
            diagnosed_candidate, recovery_candidate=True
        ) is True

    assert qualification.online.STATE_TRIGGER_MARGIN_RAD == original_trigger
    assert (
        force_module.MAXIMUM_RECOVERY_ATTRIBUTABLE_JOINT_FORCE_INCREMENT
        == original_scope_limit
    )
    assert (
        force_module.MAXIMUM_RECOVERY_POST_STEP_POSITIVE_JOINT_INCREMENT
        == original_post_limit
    )


def test_disabled_arm_adapter_changes_only_audit_identity(monkeypatch) -> None:
    payload = {
        "metadata": {
            "l2_execution_integrity": False,
            "runner_variant": "legacy",
        },
        "trace": [
            {
                "phase": "policy",
                "predictive_virtual_brake": {
                    "schema": "legacy",
                    "enabled": False,
                },
            }
        ],
    }
    monkeypatch.setattr(
        qualification.disabled_online,
        "run_episode",
        lambda **_kwargs: payload,
    )
    monkeypatch.setattr(
        qualification.disabled_online.v1,
        "_persist_annotated_episode",
        lambda _payload: None,
    )
    result = qualification._run_episode_adapter(
        args=SimpleNamespace(l2_execution_integrity="off")
    )
    assert result["metadata"]["runner_variant"] == (
        qualification.online.RUNNER_VARIANT
    )
    assert result["metadata"]["bounded_state_triggered_recovery_active"] is False
    audit = result["trace"][0]["predictive_virtual_brake"]
    assert audit["schema"] == qualification.online.BRAKE_AUDIT_SCHEMA
    assert audit["enabled"] is False
    assert audit["bounded_guarded_candidate_rollout_count"] == 0
    assert audit["unguarded_shadow_rollout_performed"] is False
    assert result["metadata"][
        "task_runtime_same_model_identity_adapter_active"
    ] is False
    assert result["metadata"]["task_runtime_method_version"] == "v15.14"
    assert result["metadata"]["task_runtime_state_trigger_margin_rad"] is None
    assert result["metadata"][
        "task_runtime_recovery_force_increment_limit"
    ] is None
    assert result["metadata"][
        "bounded_state_triggered_outcome_informed_successor"
    ] is True


def test_same_model_runtime_binds_one_explicit_nominal_identity() -> None:
    calibration = qualification._same_model_calibration_from_unavailable(
        {
            "interface_available": False,
            "active": False,
            "bind_identity": True,
        }
    )
    assert calibration["active"] is True
    assert calibration["interface_available"] is False
    assert calibration["candidate_count"] == 1
    assert calibration["selected_candidate_id"] == (
        qualification._SAME_MODEL_CANDIDATE_ID
    )
    assert calibration["model_mismatch_injected"] is False


def test_same_model_runtime_audit_does_not_claim_model_bank_calibration() -> None:
    calibration = qualification._same_model_calibration_from_unavailable(
        {
            "interface_available": False,
            "active": False,
            "bind_identity": True,
        }
    )
    audit = {"screen_latency_seconds": 0.025}
    qualification._attach_same_model_calibration_from_identity(
        audit, calibration
    )
    assert audit["pre_step_shadow_model_bank_candidate_count"] == 1
    assert audit["pre_step_shadow_selected_candidate_id"] == (
        qualification._SAME_MODEL_CANDIDATE_ID
    )
    assert audit["task_runtime_same_model_identity_adapter_active"] is True
    assert audit["task_runtime_model_mismatch_injected"] is False
    assert audit["screen_latency_seconds"] == 0.025


def test_wait_step_adapter_bypasses_incremental_post_audit_enrichment() -> None:
    calls = []

    class _Parent:
        def step(self, action):
            calls.append(("parent", action))
            self._call_index += 1
            return "wait-transition"

    class _Incremental(_Parent):
        pass

    env = _Incremental()
    env._call_index = 0
    env._wait_steps = 1
    runtime_audit = {"wait_step_count": 0, "policy_core_bind_count": 0}

    def original_step(self, action):
        calls.append(("incremental", action))
        return "policy-transition"

    wait = qualification._wait_safe_incremental_step(
        _Incremental,
        original_step,
        runtime_audit,
        env,
        "wait",
    )
    policy = qualification._wait_safe_incremental_step(
        _Incremental,
        original_step,
        runtime_audit,
        env,
        "policy",
    )

    assert wait == "wait-transition"
    assert policy == "policy-transition"
    assert runtime_audit["wait_step_count"] == 1
    assert calls == [("parent", "wait"), ("incremental", "policy")]
