from __future__ import annotations

from dataclasses import dataclass

import pytest

from proofalign.benchmark import libero_online_wrapper as wrapper_module
from proofalign.benchmark.libero_online_wrapper import (
    DefaultLiberoActionAbstractor,
    LiberoOnlineIntegrationError,
    ProofAlignLiberoWrapper,
    env_action_from_raw,
)
from proofalign.checker import _lean_trace_summary
from proofalign.ctda import AuthorityEnvelope, MonitorVerdict, TimeBase, digest_text
from proofalign.ctda_runtime import (
    ConditionalKinematicConfig,
    CTDARuntimeSession,
    ExactAllowlistEvidenceIssuer,
)
from proofalign.models import Decision, SafetySpec, TraceSummary, WorldState


@dataclass
class FakeObjectModel:
    category_name: str
    root_body: str
    contact_geoms: list[str]


class FakeSimData:
    def __init__(self) -> None:
        self.body_xpos = [[0.2, 0.1, 0.0], [0.6, 0.1, 0.0]]
        self.site_xpos = [[0.0, 0.0, 0.0]]


class FakeSim:
    def __init__(self) -> None:
        self.data = FakeSimData()


class FakeLiberoEnv:
    def __init__(self, *, hold_on_step: bool = True, collision: bool = False, cost: dict | None = None) -> None:
        self.sim = FakeSim()
        self.objects_dict = {
            "mug": FakeObjectModel("mug", "mug_main", ["mug_g0"]),
            "knife": FakeObjectModel("knife", "knife_main", ["knife_g0"]),
        }
        self.fixtures_dict = {}
        self.object_sites_dict = {}
        self.obj_body_id = {"mug": 0, "knife": 1}
        self.held_object = None
        self.step_count = 0
        self.last_env_action = None
        self.hold_on_step = hold_on_step
        self.collision = collision
        self.cost = cost if cost is not None else {}
        self.min_distance_to_human_hand = 1.0
        self.min_distance_to_obstacle = 1.0

    def reset(self):
        self.held_object = None
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}

    def step(self, action):
        self.step_count += 1
        self.last_env_action = action
        if self.hold_on_step:
            self.held_object = "mug"
        return {"robot0_eef_pos": [0.2, 0.1, 0.0]}, 1.0, False, {"cost": dict(self.cost), "collision": self.collision}


class MissingSafetySignalsEnv(FakeLiberoEnv):
    def __init__(self) -> None:
        super().__init__()
        del self.collision
        del self.cost
        del self.min_distance_to_human_hand
        del self.min_distance_to_obstacle

    def step(self, action):
        self.step_count += 1
        self.last_env_action = action
        self.held_object = "mug"
        return {"robot0_eef_pos": [0.2, 0.1, 0.0]}, 1.0, False, {}


class StaticChunkPolicy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, instruction, observation, history):
        del instruction, observation, history
        self.calls += 1
        return {
            "raw_action": [[0.1, 0.0, 0.0, 0.0], [0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }


def test_online_wrapper_blocks_intent_failure_before_env_step():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step({"proofalign_action": {"type": "Pick", "object": "knife", "part": "blade"}})

    assert result.decision == Decision.REJECT
    assert result.done is True
    assert env.step_count == 0
    assert result.info["proofalign_layer"] == "intent"


def test_online_wrapper_executes_raw_action_and_checks_effect():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step(
        {
            "raw_action": [0.1, 0.0, 0.0, 1.0],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision == Decision.ALLOW
    assert result.reward == 1.0
    assert env.step_count == 1
    assert env.last_env_action == [0.1, 0.0, 0.0, 1.0]
    assert result.step.effect_result and result.step.effect_result.passed


def test_chunk_allow_path_accumulates_trace_summary():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0], [0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        },
        max_chunk_steps=2,
        chunk_id="test_chunk",
    )

    assert result.decision == Decision.ALLOW
    assert env.step_count == 1
    assert result.step.chunk_id == "test_chunk"
    assert result.step.trace_summary
    assert result.step.trace_summary.num_raw_steps == 1
    assert result.step.trace_summary.object_became_held is True
    assert result.step.raw_actions == [[0.1, 0.0, 0.0, 0.0]]


def test_chunk_intent_reject_prevents_env_step():
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"forbidden_parts": ["blade"], "reject_dangerous": True}),
    )
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "knife", "part": "blade"},
        },
        max_chunk_steps=2,
    )

    assert result.decision == Decision.REJECT
    assert env.step_count == 0
    assert result.step.trace_summary
    assert result.step.trace_summary.num_raw_steps == 0


def test_chunk_collision_or_cost_triggers_safe_stop():
    env = FakeLiberoEnv(collision=True, cost={"collision": 1})
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision == Decision.SAFE_STOP
    assert env.step_count == 1
    assert result.step.trace_summary
    assert result.step.trace_summary.collision is True
    assert result.step.trace_summary.cost_observed is True


def test_chunk_pick_postcondition_miss_triggers_replan():
    env = FakeLiberoEnv(hold_on_step=False)
    wrapper = ProofAlignLiberoWrapper(env, "pick up the mug by the handle", SafetySpec.from_dict({}))
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, 0.0], [0.1, 0.0, 0.0, 0.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        },
        max_chunk_steps=2,
    )

    assert result.decision == Decision.REPLAN
    assert env.step_count == 2
    assert result.step.effect_result
    assert "pick chunk postcondition failed" in result.step.effect_result.explanation


def test_run_episode_max_steps_counts_raw_env_steps():
    env = FakeLiberoEnv(hold_on_step=False)
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({}),
        max_chunk_steps=2,
        stop_on_replan=False,
    )
    wrapper.reset()
    policy = StaticChunkPolicy()

    wrapper.run_episode(policy, max_steps=5)

    assert env.step_count == 5
    assert policy.calls == 3
    assert [step.trace_summary.num_raw_steps for step in wrapper.trace if step.trace_summary] == [2, 2, 1]


def test_lean_expression_builds_for_trace_summary():
    summary = TraceSummary(
        num_raw_steps=8,
        collision=False,
        cost={"collision": 0},
        cost_observed=False,
        min_human_hand_distance=0.31,
        min_obstacle_distance=0.27,
        moved_objects=["mug"],
        object_became_held=True,
    )

    expression = _lean_trace_summary(summary)

    assert "numSteps := 8" in expression
    assert "minHumanHandDistance := 31" in expression
    assert 'movedObjects := ["mug"]' in expression


def test_default_abstractor_requires_symbolic_contract_for_continuous_action():
    abstractor = DefaultLiberoActionAbstractor()

    with pytest.raises(LiberoOnlineIntegrationError):
        abstractor.abstract(
            [0.1, 0.0, 0.0, 1.0],
            instruction="pick up the mug by the handle",
            observation={},
            state=WorldState(),
            spec=SafetySpec.from_dict({}),
            history=[],
        )


def test_raw_env_action_is_separated_from_symbolic_metadata():
    assert env_action_from_raw({"raw_action": [1, 2, 3], "proofalign_action": {"type": "Stop"}}) == [1, 2, 3]
    assert env_action_from_raw([1, 2, 3]) == [1, 2, 3]


def _enable_ctda(wrapper: ProofAlignLiberoWrapper, *, fallback_verified: bool) -> None:
    assert wrapper.current_state is not None
    wrapper.ctda_session = CTDARuntimeSession.from_legacy(
        wrapper.intent,
        wrapper.current_state,
        wrapper.spec,
        AuthorityEnvelope(
            "libero-test",
            "fake-env",
            "1",
            digest_text("fake-env-attestation"),
            authenticated=True,
        ),
        TimeBase("fake-clock", 20_000_000, 1_000_000, 1_000_000, 2_000_000),
        spec_id="fake-libero-pick",
        episode_nonce="fake-libero-pick-episode",
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
        config=ConditionalKinematicConfig(
            fallback_verified=fallback_verified,
            fallback_witness_digest=(digest_text("verified-hold") if fallback_verified else ""),
            fallback_action=((0.0, 0.0, 0.0, 0.0) if fallback_verified else ()),
            evidence_validity_ns=10**18,
            translation_scale_m=3.0,
        ),
    )


def test_ctda_wrapper_persists_bound_trace_evidence_on_allow() -> None:
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0], [0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.ALLOW
    assert env.step_count == 1
    assert env.last_env_action == (0.1, 0.0, 0.0, -1.0)
    assert result.info["proofalign_ctda"]["static_verdict"] == "proven"
    assert result.info["proofalign_ctda"]["monitor_verdict"] == "complete"
    assert result.info["proofalign_ctda"]["dispatch_monotonic_ns"] is not None
    assert result.info["proofalign_ctda"]["observe_monotonic_ns"] is not None
    assert result.step.ctda["candidate_digest"]
    assert result.step.ctda["record_digest"]
    assert result.step.ctda["plant_trace_digest"]
    assert result.step.ctda["symbolic_event_trace_digest"]
    assert result.step.ctda["record"]["candidate"]["proposal"]["proposed_horizon_ns"] == 20_000_000
    assert result.step.trace_summary
    assert result.step.trace_summary.num_raw_steps == 1


def test_ctda_wrapper_blocks_before_env_step_without_verified_fallback() -> None:
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=False)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.REPLAN
    assert env.step_count == 0
    assert result.step.trace_summary
    assert result.step.trace_summary.boundary_reason == "ctda_precheck"
    assert any("recoverable" in issue for issue in result.step.ctda["issues"])


def test_ctda_wrapper_fails_closed_when_safety_observations_are_missing() -> None:
    env = MissingSafetySignalsEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.REPLAN
    assert env.step_count == 0
    assert result.step.ctda["static_verdict"] == "unknown"
    assert any("missing trusted CTDA observation" in issue for issue in result.step.ctda["issues"])


def test_missing_safety_observations_keep_legacy_non_ctda_behavior() -> None:
    env = MissingSafetySignalsEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.ALLOW
    assert env.step_count == 1


def test_ctda_wrapper_rejects_stale_authorization_before_dispatch(monkeypatch) -> None:
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)
    timestamps = iter((1_000_000, 100_000_000))
    monkeypatch.setattr(wrapper_module, "monotonic_ns", lambda: next(timestamps))

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.REPLAN
    assert env.step_count == 0
    assert any("expired before command dispatch" in issue for issue in result.step.ctda["issues"])


def test_ctda_wrapper_rejects_authorized_command_tampering_before_dispatch(monkeypatch) -> None:
    env = FakeLiberoEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)
    assert wrapper.ctda_session is not None
    original_prepare = wrapper.ctda_session.prepare_prefix

    def tampered_prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        assert result.prepared is not None
        object.__setattr__(
            result.prepared,
            "authorized_actions",
            ((0.2, 0.0, 0.0, -1.0),),
        )
        return result

    monkeypatch.setattr(wrapper.ctda_session, "prepare_prefix", tampered_prepare)
    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert result.decision is Decision.SAFE_STOP
    assert env.step_count == 0
    assert any("command digest differs" in issue for issue in result.step.ctda["issues"])


def test_ctda_episode_with_pending_contract_does_not_finish_allow() -> None:
    env = FakeLiberoEnv(hold_on_step=False)
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({}), max_chunk_steps=8
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    decision = wrapper.run_episode(StaticChunkPolicy(), max_steps=1)

    assert env.step_count == 2
    assert wrapper.trace[-1].ctda["monitor_verdict"] == "safe_pending"
    fallback_switch = wrapper.trace[-1].ctda["fallback_switch"]
    assert fallback_switch["fallback_id"] == "hold"
    assert fallback_switch["succeeded"] is True
    assert fallback_switch["command"] == [0.0, 0.0, 0.0, 0.0]
    assert fallback_switch["state_before_digest"]
    assert fallback_switch["state_after_digest"]
    assert fallback_switch["attestation"]["evidence_type"] == "fallback_switch"
    assert fallback_switch["receipt_digest"]
    assert wrapper.trace[-1].ctda["fallback_trace"]["kind"] == "ctda_fallback"
    assert wrapper.ctda_session.supervisor.active_contract is None
    assert wrapper.ctda_session.supervisor.pending_authorization_digest is None
    assert wrapper.ctda_session.supervisor.monitor_state is None
    assert wrapper.ctda_session.active_execution is None
    assert wrapper.ctda_session.supervisor.terminal_verdict is MonitorVerdict.VIOLATED
    assert wrapper.trace[-1].decision is Decision.REPLAN
    assert wrapper.trace[-1].effect_result.layer == "ctda_fallback"
    assert len(wrapper.trace[-1].raw_actions) == 2
    assert len(wrapper.trace[-1].raw_action) == 2
    assert wrapper.trace[-1].trace_summary.num_raw_steps == 2
    assert wrapper.trace[-1].after is wrapper.current_state
    assert decision.decision is Decision.REPLAN
    assert "pending CTDA contract" in decision.explanation


def test_ctda_failed_fallback_establishment_escalates_to_safe_stop() -> None:
    class CollisionAfterDispatchEnv(FakeLiberoEnv):
        def step(self, action):
            self.collision = True
            return super().step(action)

    env = CollisionAfterDispatchEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    assert env.step_count == 2
    assert result.decision is Decision.SAFE_STOP
    assert result.step.ctda["fallback_switch"]["succeeded"] is False
    assert result.step.ctda["fallback_switch"]["command"] == [0.0, 0.0, 0.0, 0.0]
    assert result.step.ctda["fallback_trace"]["env_info"]["collision"] is True
    assert result.step.trace_summary.collision is True
    assert len(result.step.raw_actions) == result.step.trace_summary.num_raw_steps == 2
    assert any(
        "fallback did not establish its immediate postcondition" in issue
        for issue in result.step.effect_result.violations
    )


def test_ctda_pending_contract_failed_fallback_escalates_to_safe_stop() -> None:
    class CollisionOnFallbackEnv(FakeLiberoEnv):
        def __init__(self) -> None:
            super().__init__(hold_on_step=False)

        def step(self, action):
            if self.step_count >= 1:
                self.collision = True
            return super().step(action)

    env = CollisionOnFallbackEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({}), max_chunk_steps=8
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    decision = wrapper.run_episode(StaticChunkPolicy(), max_steps=1)

    assert env.step_count == 2
    assert decision.decision is Decision.SAFE_STOP
    assert wrapper.trace[-1].decision is Decision.SAFE_STOP
    assert wrapper.trace[-1].effect_result.layer == "ctda_fallback"
    assert wrapper.trace[-1].trace_summary.collision is True
    assert len(wrapper.trace[-1].raw_actions) == wrapper.trace[-1].trace_summary.num_raw_steps
    assert wrapper.trace[-1].ctda["fallback_switch"]["succeeded"] is False
    assert "did not establish its immediate postcondition" in decision.explanation


def test_ctda_pending_fallback_exception_is_persisted(monkeypatch) -> None:
    env = FakeLiberoEnv(hold_on_step=False)
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({}), max_chunk_steps=8
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    def fail_fallback(**kwargs):
        del kwargs
        raise RuntimeError("fallback actuator unavailable")

    monkeypatch.setattr(wrapper, "_execute_ctda_fallback", fail_fallback)
    decision = wrapper.run_episode(StaticChunkPolicy(), max_steps=1)

    assert decision.decision is Decision.SAFE_STOP
    assert wrapper.trace[-1].ctda["fallback_error"] == "fallback actuator unavailable"
    assert "fallback dispatch failed" in decision.explanation


def test_ctda_fallback_below_distance_threshold_cannot_succeed() -> None:
    class LowClearanceEnv(FakeLiberoEnv):
        def step(self, action):
            self.min_distance_to_obstacle = 0.01
            return super().step(action)

    env = LowClearanceEnv()
    wrapper = ProofAlignLiberoWrapper(
        env,
        "pick up the mug by the handle",
        SafetySpec.from_dict({"safety_margin": 0.2}),
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    fallback = result.step.ctda["fallback_switch"]
    assert result.decision is Decision.SAFE_STOP
    assert fallback["succeeded"] is False
    assert fallback["postcondition"]["distance_thresholds_hold"] is False
    assert fallback["postcondition"]["obstacle_clearance_m"] == 0.01


def test_ctda_fallback_observation_exception_persists_unknown_attempt(
    monkeypatch,
) -> None:
    class CollisionAfterDispatchEnv(FakeLiberoEnv):
        def step(self, action):
            self.collision = True
            return super().step(action)

    env = CollisionAfterDispatchEnv()
    wrapper = ProofAlignLiberoWrapper(
        env, "pick up the mug by the handle", SafetySpec.from_dict({})
    )
    wrapper.reset()
    _enable_ctda(wrapper, fallback_verified=True)
    original_observe = wrapper.state_observer.observe

    def fail_only_on_fallback(observed_env, observation=None, info=None):
        if env.step_count >= 2:
            raise RuntimeError("fallback camera unavailable")
        return original_observe(observed_env, observation, info)

    monkeypatch.setattr(wrapper.state_observer, "observe", fail_only_on_fallback)

    result = wrapper.step_chunk(
        {
            "raw_action": [[0.1, 0.0, 0.0, -1.0]],
            "proofalign_action": {"type": "Pick", "object": "mug", "part": "handle"},
        }
    )

    fallback = result.step.ctda["fallback_switch"]
    fallback_trace = result.step.ctda["fallback_trace"]
    assert result.decision is Decision.SAFE_STOP
    assert fallback["succeeded"] is False
    assert fallback["postcondition"]["observation_complete"] is False
    assert fallback["state_after_digest"] != fallback["state_before_digest"]
    assert fallback_trace["state_after"] is None
    assert fallback_trace["observation_error"] == "fallback camera unavailable"
    assert "fallback_observation_exception" in fallback_trace["env_info"]
    assert wrapper.ctda_session.last_fallback_receipt is not None
