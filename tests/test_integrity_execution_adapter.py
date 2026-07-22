from __future__ import annotations

import pytest

from proofalign.benchmark.integrity_execution_adapter import (
    IntegrityExecutionAdapter,
    action_envelope_artifact,
)


def _artifact():
    return action_envelope_artifact(
        source_id="test",
        source_version="v1",
        artifact_digest="a" * 64,
        trusted_instruction="place the mug",
    )


def test_adapter_projects_before_its_only_environment_step() -> None:
    received: list[list[float]] = []

    def step(command: list[float]):
        received.append(command)
        return {"state": len(received)}, 1.0, False, {"cost": {}, "collision": False}

    adapter = IntegrityExecutionAdapter.create(
        artifact=_artifact(),
        episode_nonce="episode-a",
        l2_limit=1.0,
        step=step,
        normalize=lambda value: value,
    )

    observation, reward, done, info, audit = adapter.dispatch_and_step(
        raw_command=(3.0, 4.0), observation={"before": 0}
    )

    assert received == [pytest.approx([0.6, 0.8])]
    assert observation == {"state": 1}
    assert (reward, done, info) == (1.0, False, {"cost": {}, "collision": False})
    assert audit["authorization_verdict"] == "allow"
    assert audit["effect_verdict"] == "pending"
    assert audit["intervention"]["intervention_kind"] == "project_or_brake"


def test_adapter_preserves_an_in_envelope_action_and_binds_a_receipt() -> None:
    received: list[list[float]] = []
    adapter = IntegrityExecutionAdapter.create(
        artifact=_artifact(),
        episode_nonce="episode-b",
        l2_limit=1.0,
        step=lambda command: (received.append(command) or ({}, 0.0, False, {"cost": {}})),
        normalize=lambda value: value,
    )

    *_transition, audit = adapter.dispatch_and_step(
        raw_command=(0.6, 0.8), observation={"before": 0}
    )

    assert received == [pytest.approx([0.6, 0.8])]
    assert audit["receipt_digest"]
    assert audit["intervention"]["intervention_kind"] == "pass"


def test_adapter_reports_effect_rejection_when_the_environment_observes_cost() -> None:
    adapter = IntegrityExecutionAdapter.create(
        artifact=_artifact(),
        episode_nonce="episode-c",
        l2_limit=1.0,
        step=lambda command: ({}, 0.0, False, {"cost": {"contact": 1}}),
        normalize=lambda value: value,
    )

    *_transition, audit = adapter.dispatch_and_step(
        raw_command=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0), observation={"before": 0}
    )

    assert audit["effect_verdict"] == "reject"
