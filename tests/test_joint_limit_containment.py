from __future__ import annotations

from argparse import Namespace

import pytest

from proofalign.joint_limit_containment import (
    INDEPENDENT_SIGNAL_SCHEMA,
    JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,
    JOINT_LIMIT_VIOLATION_ATOM,
    observed_joint_limit_atoms,
)
from scripts import run_l2_joint_limit_containment_v11 as v11


SOURCE_DIGEST = "a" * 64


def _signals(*, violated: bool) -> dict[str, object]:
    return {
        "schema": INDEPENDENT_SIGNAL_SCHEMA,
        "joint_limit_violation": violated,
        "official_saber_source_sha256": SOURCE_DIGEST,
    }


def test_known_clear_signal_allows_next_dispatch() -> None:
    assert observed_joint_limit_atoms(
        _signals(violated=False)
    ) == ()


def test_observed_joint_limit_requires_containment() -> None:
    assert observed_joint_limit_atoms(
        _signals(violated=True)
    ) == (JOINT_LIMIT_VIOLATION_ATOM,)


@pytest.mark.parametrize(
    "signals",
    (
        None,
        {},
        {
            "schema": "wrong",
            "joint_limit_violation": False,
            "official_saber_source_sha256": SOURCE_DIGEST,
        },
        {
            "schema": INDEPENDENT_SIGNAL_SCHEMA,
            "joint_limit_violation": 0,
            "official_saber_source_sha256": SOURCE_DIGEST,
        },
        {
            "schema": INDEPENDENT_SIGNAL_SCHEMA,
            "joint_limit_violation": False,
            "official_saber_source_sha256": "not-a-digest",
        },
    ),
)
def test_missing_or_malformed_signal_fails_closed(
    signals: dict[str, object] | None,
) -> None:
    assert observed_joint_limit_atoms(signals) == (
        JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,
    )


@pytest.mark.parametrize(
    ("l1", "l2", "semantic_runtime", "active"),
    (
        ("off", "off", False, False),
        ("on", "off", True, False),
        ("off", "on", False, True),
        ("on", "on", True, True),
    ),
)
def test_v11_arms_containment_only_with_l2(
    monkeypatch: pytest.MonkeyPatch,
    l1: str,
    l2: str,
    semantic_runtime: bool,
    active: bool,
) -> None:
    called = {"contained": False, "uncontained": False}

    def fake_run_episode(**kwargs: object) -> dict[str, object]:
        del kwargs
        called["uncontained"] = True
        return {"metadata": {}}

    def fake_contained(
        kwargs: dict[str, object],
    ) -> dict[str, object]:
        del kwargs
        called["contained"] = True
        return {"metadata": {}}

    monkeypatch.setattr(v11.v10, "run_episode", fake_run_episode)
    monkeypatch.setattr(
        v11, "_run_with_containment", fake_contained
    )
    monkeypatch.setattr(
        v11.v1,
        "_persist_annotated_episode",
        lambda _payload: None,
    )
    payload = v11.run_episode(
        args=Namespace(
            l1_semantic_alignment=l1,
            l2_execution_integrity=l2,
            semantic_runtime=semantic_runtime,
        )
    )
    assert called["contained"] is active
    assert called["uncontained"] is (not active)
    assert payload["metadata"][
        "joint_limit_containment_active"
    ] is active
    assert payload["metadata"][
        "joint_limit_prevention_claim"
    ] is False


class _Robot:
    def __init__(self, values: list[bool]) -> None:
        self._values = iter(values)

    def check_q_limits(self) -> bool:
        return next(self._values)


class _Env:
    def __init__(self, values: list[bool]) -> None:
        self.robots = [_Robot(values)]
        self.calls = 0

    def step(self, _action: object) -> tuple[object, float, bool, dict]:
        self.calls += 1
        return object(), 0.0, False, {}


def test_environment_halts_on_first_post_wait_signal() -> None:
    env = _Env([False, True])
    wrapped = v11.JointLimitContainmentEnvironment(
        env, wait_steps=1
    )
    assert wrapped.step([0.0])[2] is False
    assert wrapped.step([0.0])[2] is False
    transition = wrapped.step([0.0])
    assert transition[2] is True
    assert transition[3][v11.CONTAINMENT_INFO_KEY] is True
    assert [
        row.joint_limit_violation
        for row in wrapped.observations
    ] == [False, True]


def test_trace_binding_refuses_signal_disagreement() -> None:
    payload = {
        "trace": [
            {
                "step_id": 10,
                "phase": "policy",
                "saber_constraint_signals": {
                    "joint_limit_violation": False
                },
            }
        ]
    }
    with pytest.raises(RuntimeError, match="disagrees"):
        v11._bind_containment_trace(
            payload,
            [
                v11.JointLimitObservation(
                    runner_step_id=10,
                    joint_limit_violation=True,
                    environment_done_before_containment=False,
                )
            ],
        )
