from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from proofalign.semantic_local_checker import LocalActionAssessment
from proofalign.digests import digest_text
from proofalign.semantic_local_checker import EntityPosition, TrustedLocalObservation
from proofalign.semantic_policy_wrapper import TrustedSemanticPolicyWrapper
from proofalign.semantic_trust import UntrustedPolicyView
from proofalign.task_conditioned_l1 import L1Verdict
from proofalign.task_conditioned_l1_v2 import TransitionShadowAssessment
from proofalign.task_conditioned_l1_v4 import (
    ABORT_SENTINEL_VALUE,
    QualifiedNoDispatchBoundary,
    QualifiedNoDispatchChecker,
    QualifiedNoDispatchRecoveryCandidatePolicy,
    _is_abort_command,
    no_dispatch_protocol_digest,
    reset_qualified_abort_state,
)
from scripts.run_l1_task_conditioned_successor_v4 import (
    _patched_v4_checker_bindings,
    annotate_payload,
)


class _Model:
    def __init__(self, geoms: tuple[str, ...]) -> None:
        self.contact_geoms = geoms


def _contract():
    from proofalign.task_conditioned_l1 import compile_contact_contract

    gripper = _Model(("left_finger", "right_finger"))
    env = SimpleNamespace(
        robots=[
            SimpleNamespace(
                robot_model=_Model(("arm_link", "left_finger", "right_finger")),
                gripper=gripper,
            )
        ],
        objects_dict={"target_1": _Model(("target_geom",))},
        fixtures_dict={},
    )
    return compile_contact_contract(env, "pick_up(target_1)", None)


def _assessment(verdict: L1Verdict) -> TransitionShadowAssessment:
    return TransitionShadowAssessment(
        verdict=verdict,
        reason_atoms=(
            () if verdict is L1Verdict.ALLOW else ("joint_limit_violation_transition",)
        ),
        structured_effects=(),
        shadow_step_count=10,
        baseline_contact_count=0,
        maximum_contact_count=0,
        baseline_joint_limit_violation=False,
        baseline_robot_force_newtons=0.0,
        maximum_robot_force_newtons=0.0,
        qualified_restore_identity=True,
        full_simulator_state_bitwise_identity=False,
        full_simulator_state_max_abs_error=0.0,
        full_simulator_state_differing_value_count=0,
        restore_assessment_digest="a" * 64,
        latency_ns=1,
        contract=_contract(),
    )


def _policy(monkeypatch: pytest.MonkeyPatch, verdicts: list[L1Verdict]):
    nominal = np.tile(
        np.asarray([0.8, 0.1, -0.1, 0.0, 0.0, 0.0, -1.0]),
        (10, 1),
    )

    class Inner:
        _rng = None

        def infer(self, _element):
            return {"actions": nominal.copy()}

    class FakeShadow:
        def __init__(self, _bridge):
            self.verdicts = iter(verdicts)

        def assess(self, *_args, **_kwargs):
            return _assessment(next(self.verdicts))

    from proofalign import task_conditioned_l1_v4 as module

    monkeypatch.setattr(module, "TransitionAlignedShadowChecker", FakeShadow)

    class Bound(QualifiedNoDispatchRecoveryCandidatePolicy):
        bridge = object()

    policy = Bound(Inner(), candidate_count=1, replan_steps=10)
    policy.wrapper = object()
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(selected_subtask="pick_up(target_1)"),
        context=SimpleNamespace(state_epoch=0),
    )
    return policy, nominal


def test_v4_returns_internal_sentinel_only_when_every_recovery_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, nominal = _policy(monkeypatch, [L1Verdict.REJECT] * 56)
    result = policy.infer({})
    audit = policy.audits[-1]
    assert np.all(result["actions"][:10] == ABORT_SENTINEL_VALUE)
    assert not np.array_equal(result["actions"], nominal)
    assert audit["qualified_no_dispatch_abort"] is True
    assert audit["dispatch_intent"] == "none"
    assert audit["selected_action_block_sha256"] is None
    assert audit["recovery_verdict_counts"] == {"reject": 55}
    assert audit["unqualified_fallback_dispatch_allowed"] is False
    assert audit["sentinel_is_authorizable"] is False
    assert len(no_dispatch_protocol_digest()) == 64


def test_v4_keeps_exact_shadow_allow_recovery_dispatchable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, nominal = _policy(
        monkeypatch,
        [L1Verdict.REJECT, L1Verdict.ALLOW],
    )
    result = policy.infer({})
    audit = policy.audits[-1]
    assert audit["qualified_no_dispatch_abort"] is False
    assert audit["dispatch_intent"] == "exact_action_block"
    assert audit["selected_kind"] == "source_reverse_2_then_hold"
    assert not np.array_equal(result["actions"], nominal)


def test_v4_checker_and_boundary_both_reject_armed_abort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from proofalign import task_conditioned_l1_v4 as module
    from proofalign.risk_selective_semantic import (
        RiskSelectiveSemanticExecutablePrefixChecker,
    )

    predecessor = LocalActionAssessment(
        known=True,
        semantic_compatible=True,
        motion_atoms=(),
        precondition_atoms=(),
        predicted_effect_atoms=(),
        violation_atoms=(),
        progress_margin=1.0,
        target="target_1",
        part=None,
        region=None,
        unknown_reason=None,
    )
    monkeypatch.setattr(
        RiskSelectiveSemanticExecutablePrefixChecker,
        "predecessor_assess",
        lambda _self, **_kwargs: predecessor,
    )
    module._QUALIFIED_ABORT_ARMED = True
    command = np.full((10, 7), ABORT_SENTINEL_VALUE)
    assessed = QualifiedNoDispatchChecker().assess(
        semantic_subtask="pick_up(target_1)",
        observation=object(),
        command=command.reshape(-1),
        command_shape=command.shape,
        expected_state_epoch=0,
        release_destination=None,
    )
    assert assessed.known is True
    assert assessed.semantic_compatible is False
    assert assessed.violation_atoms == ("qualified_no_dispatch_abort",)

    opened = QualifiedNoDispatchBoundary(object()).open(object(), now_ns=0)
    assert opened.verdict.value == "reject"
    assert opened.session is None
    assert opened.issues == ("qualified L1 no-dispatch abort",)
    reset_qualified_abort_state()


def test_v4_sentinel_requires_exact_finite_shape_and_annotation_marks_abort() -> None:
    command = np.full((10, 7), ABORT_SENTINEL_VALUE)
    assert _is_abort_command(command.reshape(-1), command.shape) is True
    command[0, 0] = 1.0
    assert _is_abort_command(command.reshape(-1), command.shape) is False

    payload = {
        "task_success": True,
        "strict_success_no_cost": True,
        "success_by_done": True,
        "decision": "env_done",
        "metadata": {},
        "observation_frame_audits": [
            {
                "online_progress_projection_v3": {
                    "schema": "proofalign.task-conditioned-l1.v4.candidate-decision",
                    "qualified_no_dispatch_abort": True,
                }
            }
        ],
    }
    annotated = annotate_payload(payload, l1_enabled=True)
    assert annotated["decision"] == "l1_qualified_no_dispatch_abort"
    assert annotated["task_success"] is False
    assert annotated["strict_success_no_cost"] is False
    assert annotated["metadata"]["l1_qualified_no_dispatch_abort_count"] == 1


def test_v4_real_semantic_wrapper_builds_no_contract_for_abort_sentinel() -> None:
    from proofalign import task_conditioned_l1_v4 as module

    bddl = """
    (define (problem transport)
      (:domain robosuite)
      (:objects red_mug_1 - red_mug plate_1 - plate)
      (:init (On red_mug_1 main_table_region))
      (:goal (And (On red_mug_1 plate_1)))
    )
    """
    observation = TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.25),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("red_mug_1", (0.15, 0.0, 0.25)),
            EntityPosition("plate_1", (0.40, 0.0, 0.25)),
        ),
    )
    with _patched_v4_checker_bindings():
        wrapper = TrustedSemanticPolicyWrapper(
            episode_nonce="v4-abort-test",
            trusted_task="put the red mug on the plate",
            bddl_text=bddl,
        )
        preparation = wrapper.begin_policy_call(
            proposal_index=0,
            local_observation=observation,
            trusted_observation_digest=digest_text("trusted-view"),
            external_policy_prompt="put the red mug on the plate",
            generated_at_ns=10,
        )
        assert preparation.request is not None
        module._QUALIFIED_ABORT_ARMED = True
        command = np.full((10, 7), ABORT_SENTINEL_VALUE)
        decision = wrapper.complete_policy_call(
            preparation.request,
            policy_view=UntrustedPolicyView(
                policy_prompt="put the red mug on the plate",
                policy_observation_digest=digest_text("policy-view"),
            ),
            source_policy_chunk_digest=digest_text("abort-chunk"),
            nominal_command=command.reshape(-1),
            command_shape=command.shape,
            proposed_at_ns=20,
            assessed_at_ns=21,
            contract_issued_at_ns=22,
        )
    assert decision.accepted is False
    assert decision.executable_prefix is None
    assert decision.execution_contract is None
    assert decision.checked_candidate.semantic_compatible is False
    assert "qualified_no_dispatch_abort" in decision.checked_candidate.hard_violation_atoms
    reset_qualified_abort_state()
