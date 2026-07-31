from __future__ import annotations

from typing import Any

import pytest

from scripts import run_l2_predictive_virtual_brake_v13_fresh3 as online
from scripts import run_predictive_virtual_brake_v13_attacked as study


def test_attacked_outcomes_are_not_completion_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        study,
        "_BASE_V13_METRICS",
        lambda _protocol, _evidence: (
            {"episode_count": 180},
            {
                **{
                    name: False
                    for name in study.OUTCOME_GATE_NAMES
                },
                "integrity": True,
            },
        ),
    )

    metrics, gates = study._attacked_metrics({}, {})

    assert gates == {"integrity": True}
    assert metrics[
        "descriptive_attacked_outcome_gate_results"
    ] == {
        name: False for name in study.OUTCOME_GATE_NAMES
    }


def test_attacker_patch_is_scoped() -> None:
    physical = study.attacker.inherited
    base = physical.base
    original: tuple[Any, ...] = (
        study.attacker.PROTOCOL_SCHEMA,
        study.attacker.EVIDENCE_SCHEMA,
        study.attacker.AUTHORIZED_STATUS,
        study.attacker.STAGE,
        study.attacker.DEFAULT_PROTOCOL,
        study.attacker.online,
        study.attacker.validate_protocol,
        base._v10_metrics,
        physical._enrich,
        study.clean.EXPECTED_RUNNER,
        study.clean.online,
    )

    with study._patched_attacker():
        assert study.attacker.PROTOCOL_SCHEMA == (
            study.PROTOCOL_SCHEMA
        )
        assert study.attacker.EVIDENCE_SCHEMA == (
            study.EVIDENCE_SCHEMA
        )
        assert study.attacker.online is online
        assert base._v10_metrics is study._attacked_metrics
        assert physical._enrich is study._attacked_enrich
        assert study.clean.EXPECTED_RUNNER == online.RUNNER_VARIANT

    assert (
        study.attacker.PROTOCOL_SCHEMA,
        study.attacker.EVIDENCE_SCHEMA,
        study.attacker.AUTHORIZED_STATUS,
        study.attacker.STAGE,
        study.attacker.DEFAULT_PROTOCOL,
        study.attacker.online,
        study.attacker.validate_protocol,
        base._v10_metrics,
        physical._enrich,
        study.clean.EXPECTED_RUNNER,
        study.clean.online,
    ) == original


def test_attacked_execute_rejects_wrong_interpreter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(
        study.clean,
        "REQUIRED_INTERPRETER",
        tmp_path / "missing-openpi-python",
    )

    with pytest.raises(
        RuntimeError,
        match="external/openpi/.venv/bin/python",
    ):
        study.execute(
            {},
            protocol_path=tmp_path / "protocol.json",
            policy_gpu=1,
            egl_gpu=2,
        )
