from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from proofalign.task_conditioned_l1 import L1Verdict, TaskConditionedL1Error
from proofalign.task_conditioned_l1_v2 import TransitionShadowAssessment
from proofalign.task_conditioned_l1_v3 import (
    BoundedRetreatRecoveryCandidatePolicy,
    bounded_retreat_candidates,
    recovery_library_digest,
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


def _nominal() -> np.ndarray:
    return np.tile(
        np.asarray([0.8, 0.1, -0.1, 0.0, 0.0, 0.0, -1.0]),
        (10, 1),
    )


def _assessment(verdict: L1Verdict) -> TransitionShadowAssessment:
    return TransitionShadowAssessment(
        verdict=verdict,
        reason_atoms=(() if verdict is L1Verdict.ALLOW else ("joint_limit_violation_transition",)),
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


def test_bounded_retreat_library_is_fixed_unique_and_low_amplitude() -> None:
    first = bounded_retreat_candidates(_nominal())
    second = bounded_retreat_candidates(_nominal())
    assert [name for name, _ in first] == [name for name, _ in second]
    assert [block.tobytes() for _, block in first] == [block.tobytes() for _, block in second]
    assert len(first) == 31
    assert len({block.tobytes() for _, block in first}) == len(first)
    assert all(float(np.max(np.abs(block[:, :3]))) <= 0.25 for _, block in first)
    assert all(np.array_equal(block[:, 6], np.full(10, -1.0)) for _, block in first)
    assert len(recovery_library_digest()) == 64


def _policy(monkeypatch: pytest.MonkeyPatch, verdicts: list[L1Verdict]):
    nominal = _nominal()

    class Inner:
        _rng = None

        def infer(self, _element):
            return {"actions": nominal.copy()}

    class FakeShadow:
        def __init__(self, _bridge):
            self.verdicts = iter(verdicts)

        def assess(self, *_args, **_kwargs):
            return _assessment(next(self.verdicts))

    from proofalign import task_conditioned_l1_v3 as module

    monkeypatch.setattr(module, "TransitionAlignedShadowChecker", FakeShadow)

    class Bound(BoundedRetreatRecoveryCandidatePolicy):
        bridge = object()

    policy = Bound(Inner(), candidate_count=1, replan_steps=10)
    policy.wrapper = object()
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(selected_subtask="pick_up(target_1)"),
        context=SimpleNamespace(state_epoch=0),
    )
    return policy, nominal


def test_v3_selects_only_an_exact_shadow_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    policy, nominal = _policy(
        monkeypatch,
        [L1Verdict.REJECT, L1Verdict.REJECT, L1Verdict.ALLOW],
    )
    result = policy.infer({})
    audit = policy.audits[-1]
    assert audit["selected_kind"] == "source_reverse_4_then_hold"
    assert audit["recovery_library_size"] == 31
    assert audit["unqualified_fallback_dispatch_allowed"] is False
    assert not np.array_equal(result["actions"], nominal)


def test_v3_still_fails_closed_if_entire_library_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, _ = _policy(monkeypatch, [L1Verdict.REJECT] * 32)
    with pytest.raises(TaskConditionedL1Error, match="no qualified bounded-retreat"):
        policy.infer({})
