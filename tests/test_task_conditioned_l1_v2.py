from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from proofalign.task_conditioned_l1 import L1Verdict, TaskConditionedL1Error
from proofalign.task_conditioned_l1_v2 import (
    TransitionAlignedRecoveryCandidatePolicy,
    TransitionShadowAssessment,
    _qualified_restore_identity,
    _transition_contact_atom,
)
from scripts.run_l2_execution_attack_eval_v2 import _array_digest


class _Model:
    def __init__(self, geoms: tuple[str, ...]) -> None:
        self.contact_geoms = geoms


def _contract(phase: str = "pick_up"):
    from proofalign.task_conditioned_l1 import compile_contact_contract

    gripper = _Model(("left_finger", "right_finger"))
    env = SimpleNamespace(
        robots=[
            SimpleNamespace(
                robot_model=_Model(
                    ("arm_link", "left_finger", "right_finger")
                ),
                gripper=gripper,
            )
        ],
        objects_dict={
            "target_1": _Model(("target_geom_0", "target_geom_1")),
            "plate_1": _Model(("plate_geom",)),
            "distractor_1": _Model(("distractor_geom",)),
        },
        fixtures_dict={},
    )
    template = {
        "template": {
            "goals": [
                {
                    "family": "grasp_allowed_part",
                    "target": "target_1",
                    "allowed_part_ids": [1],
                }
            ]
        }
    }
    subtask = (
        "pick_up(target_1)"
        if phase == "pick_up"
        else f"{phase}(target_1,plate_1)"
    )
    return compile_contact_contract(env, subtask, template)


def _restore(**overrides):
    values = {
        "trusted_arm_bitwise_identity": True,
        "controller_state_identity": True,
        "simulator_input_identity": True,
        "environment_clock_identity": True,
        "qacc_warmstart_identity": True,
        "runtime_side_state_identity": True,
        "full_simulator_state_bitwise_identity": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_v2_restore_uses_qualified_boundary_not_full_state_diagnostic() -> None:
    assert _qualified_restore_identity(_restore()) is True
    assert _qualified_restore_identity(
        _restore(controller_state_identity=False)
    ) is False


def test_held_object_contact_only_activates_while_grasped() -> None:
    contract = _contract("move")
    pair = tuple(sorted(("target_geom_1", "distractor_geom")))
    assert _transition_contact_atom(
        pair, contract, target_is_held=False
    ) is None
    assert _transition_contact_atom(
        pair, contract, target_is_held=True
    ) == "forbidden_held_object_contact:distractor_1"


def _assessment(verdict: L1Verdict) -> TransitionShadowAssessment:
    return TransitionShadowAssessment(
        verdict=verdict,
        reason_atoms=(() if verdict is L1Verdict.ALLOW else ("contact_capacity_saturated",)),
        structured_effects=(),
        shadow_step_count=10,
        baseline_contact_count=1,
        maximum_contact_count=2,
        baseline_joint_limit_violation=False,
        baseline_robot_force_newtons=0.0,
        maximum_robot_force_newtons=1.0,
        qualified_restore_identity=True,
        full_simulator_state_bitwise_identity=False,
        full_simulator_state_max_abs_error=0.0,
        full_simulator_state_differing_value_count=0,
        restore_assessment_digest="a" * 64,
        latency_ns=1,
        contract=_contract(),
    )


def _policy(monkeypatch, verdicts: list[L1Verdict]):
    nominal = np.tile(
        np.asarray([0.8, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]), (10, 1)
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

    from proofalign import task_conditioned_l1_v2 as module

    monkeypatch.setattr(module, "TransitionAlignedShadowChecker", FakeShadow)

    class Bound(TransitionAlignedRecoveryCandidatePolicy):
        bridge = object()

    policy = Bound(Inner(), candidate_count=1, replan_steps=10)
    policy.wrapper = object()
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(selected_subtask="pick_up(target_1)"),
        context=SimpleNamespace(state_epoch=0),
    )
    return policy, nominal


def test_v2_never_dispatches_unqualified_fallback(monkeypatch) -> None:
    policy, _nominal = _policy(
        monkeypatch,
        [L1Verdict.ABSTAIN] * 4,
    )
    with pytest.raises(
        TaskConditionedL1Error,
        match="no qualified fresh recovery ActionBlock",
    ):
        policy.infer({})


def test_v2_uses_shared_source_digest_and_qualified_recovery(monkeypatch) -> None:
    policy, nominal = _policy(
        monkeypatch,
        [L1Verdict.REJECT, L1Verdict.ALLOW],
    )
    result = policy.infer({})
    audit = policy.audits[-1]
    assert audit["source_policy_chunk_sha256"] == _array_digest(nominal)
    assert audit["source_digest_algorithm"] == "v2_array_digest_sha256"
    assert audit["selected_kind"] == "reverse_then_hold"
    assert not np.array_equal(result["actions"], nominal)
