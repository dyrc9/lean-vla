from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from proofalign.task_conditioned_l1 import (
    AdvisoryAfterExactShadowChecker,
    L1Verdict,
    ShadowAssessment,
    TaskConditionedRecoveryCandidatePolicy,
    _pair_contact_atom,
    compile_contact_contract,
    recovery_candidates,
)
from proofalign.semantic_local_checker import EntityPosition, TrustedLocalObservation


class _Model:
    def __init__(self, geoms: tuple[str, ...]) -> None:
        self.contact_geoms = geoms


def _env() -> SimpleNamespace:
    gripper = _Model(("left_finger", "right_finger"))
    robot = SimpleNamespace(
        robot_model=_Model(("arm_link", "left_finger", "right_finger")),
        gripper=gripper,
    )
    return SimpleNamespace(
        robots=[robot],
        objects_dict={
            "target_1": _Model(("target_geom_0", "target_geom_1")),
            "plate_1": _Model(("plate_geom",)),
            "distractor_1": _Model(("distractor_geom",)),
        },
        fixtures_dict={},
    )


def _contract(phase: str = "pick_up"):
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
    return compile_contact_contract(
        _env(),
        (
            "pick_up(target_1)"
            if phase == "pick_up"
            else f"{phase}(target_1,plate_1)"
        ),
        template,
    )


def test_phase_and_part_specific_contact_contract() -> None:
    contract = _contract()
    assert contract.allowed_target_part_geoms == frozenset({"target_geom_1"})
    assert _pair_contact_atom(
        tuple(sorted(("left_finger", "target_geom_1"))), contract
    ) is None
    assert _pair_contact_atom(
        tuple(sorted(("left_finger", "target_geom_0"))), contract
    ).startswith("forbidden_robot_contact:gripper")
    assert _pair_contact_atom(
        tuple(sorted(("arm_link", "target_geom_1"))), contract
    ).startswith("forbidden_robot_contact:arm")


def test_destination_contact_only_allowed_in_terminal_phase() -> None:
    move = _contract("move")
    place = _contract("place")
    pair = tuple(sorted(("target_geom_1", "plate_geom")))
    assert _pair_contact_atom(pair, move) == (
        "forbidden_held_object_contact:plate_1"
    )
    assert _pair_contact_atom(pair, place) is None


def test_recovery_candidates_are_bounded_and_preserve_gripper() -> None:
    nominal = np.tile(
        np.asarray([0.8, -0.4, 0.2, 0.0, 0.0, 0.0, -1.0]),
        (10, 1),
    )
    rows = recovery_candidates(nominal)
    assert [row[0] for row in rows] == [
        "reverse_then_hold",
        "vertical_retreat_then_hold",
        "hold_and_reobserve",
    ]
    for _name, action in rows:
        assert action.shape == (10, 7)
        assert np.max(np.abs(action[:, :6])) <= 0.25
        assert np.all(action[:, 6] == -1.0)


def test_legacy_point_proxy_is_advisory_after_exact_shadow() -> None:
    checker = AdvisoryAfterExactShadowChecker()
    observation = TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.3),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target_1", (0.2, 0.0, 0.3)),
            EntityPosition("distractor_1", (-0.025, 0.0, 0.3)),
        ),
    )
    command = np.tile(
        np.asarray([-0.1, 0, 0, 0, 0, 0, -1.0]), (10, 1)
    )
    assessed = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=observation,
        command=tuple(command.reshape(-1)),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )
    assert assessed.known is True
    assert assessed.semantic_compatible is True
    assert assessed.violation_atoms == ()
    assert any(
        atom.startswith("legacy_proxy_advisory:")
        for atom in assessed.precondition_atoms
    )


def test_candidate_substitutes_separately_digested_recovery(monkeypatch) -> None:
    nominal = np.tile(
        np.asarray([0.8, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]), (10, 1)
    )

    class Inner:
        _rng = None

        def infer(self, _element):
            return {"actions": nominal.copy()}

    class FakeShadow:
        calls = 0

        def __init__(self, _bridge):
            pass

        def assess(self, _actions, *, semantic_subtask, source_id):
            del semantic_subtask, source_id
            self.calls += 1
            verdict = L1Verdict.REJECT if self.calls == 1 else L1Verdict.ALLOW
            contract = _contract()
            return ShadowAssessment(
                verdict=verdict,
                reason_atoms=("forbidden_robot_contact:arm:table",)
                if verdict is L1Verdict.REJECT
                else (),
                structured_effects=(),
                shadow_step_count=10,
                baseline_contact_count=1,
                maximum_contact_count=2,
                maximum_robot_force_newtons=2.0,
                restore_identity=True,
                restore_assessment_digest="a" * 64,
                latency_ns=1,
                contract=contract,
            )

    from proofalign import task_conditioned_l1 as module

    monkeypatch.setattr(module, "TaskConditionedShadowChecker", FakeShadow)

    class BoundPolicy(TaskConditionedRecoveryCandidatePolicy):
        bridge = object()

    policy = BoundPolicy(Inner(), candidate_count=1, replan_steps=10)
    policy.wrapper = object()
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(selected_subtask="pick_up(target_1)"),
        context=SimpleNamespace(state_epoch=0),
    )
    result = policy.infer({})
    assert not np.array_equal(result["actions"], nominal)
    assert policy.audits[-1]["fresh_recovery_transaction"] is True
    assert policy.audits[-1]["selected_kind"] == "reverse_then_hold"
    assert policy.audits[-1]["source_policy_chunk_sha256"] != (
        policy.audits[-1]["selected_action_block_sha256"]
    )

