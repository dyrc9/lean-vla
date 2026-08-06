from __future__ import annotations

from types import SimpleNamespace

from scripts import (
    run_l2_predictive_virtual_brake_v15_dynamic_state_recovery as recovery,
)


def test_patched_identity_requires_dynamic_state(monkeypatch) -> None:
    core = recovery.predecessor.v14_core.core
    monkeypatch.setattr(core, "_restore_identity", lambda _row: True)
    assessments = []

    with recovery._patched_dynamic_state_shadow(assessments):
        patched = core._restore_identity
        assert patched(SimpleNamespace()) is False


def test_gripper_action_normalizes_finite_vector() -> None:
    robot = SimpleNamespace(
        gripper=SimpleNamespace(current_action=[-0.1, 0.1])
    )

    assert recovery._gripper_action(robot) == [-0.1, 0.1]
