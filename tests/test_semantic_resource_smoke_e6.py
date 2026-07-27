from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.prepare_semantic_resource_smoke_e6 import (
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    ResourceSmokePreflightError,
    build_protocol,
    canonical_text,
    validate_protocol,
)
from scripts.run_semantic_resource_smoke_e6 import (
    AUTHORIZED_PROTOCOL_PATH,
    ResourceSmokeError,
    build_authorized_protocol,
    main as resource_smoke_main,
    measure_policy_workload,
    summarize_result,
    validate_authorized_protocol,
)


def test_e6_resource_smoke_preregistration_is_current() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    validate_protocol(protocol)
    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_protocol())
    assert protocol["workload"]["simulator_required"] is False
    assert protocol["workload"]["action_sink_required"] is False
    assert protocol["workload"]["reward_or_success_required"] is False
    assert not any(protocol["execution_authorization"].values())
    assert OUTPUT_ROOT.exists() is False


def test_e6_preregistration_rejects_implicit_authorization() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol["execution_authorization"][
        "model_load_authorized"
    ] = True

    with pytest.raises(
        ResourceSmokePreflightError,
        match="unexpectedly authorizes execution",
    ):
        validate_protocol(protocol)


def test_e6_executor_reports_current_authorization_state(
    capsys,
) -> None:
    assert resource_smoke_main(["--check-state"]) == 0
    report = json.loads(capsys.readouterr().out)
    if AUTHORIZED_PROTOCOL_PATH.exists():
        assert report["authorization_state"] == "authorized"
        assert report["measurement_state"] in {"pending", "complete"}
        boundary = (
            report
            if report["measurement_state"] == "complete"
            else report["prelaunch"]
        )
        assert boundary["simulator_created"] is False
        assert boundary["actions_dispatched"] is False
        assert boundary["outcomes_read"] is False
    else:
        assert report["authorization_state"] == "absent"
        assert report["measurement_state"] == "blocked"
        assert report["model_loaded"] is False
        assert report["simulator_created"] is False
        assert report["actions_dispatched"] is False
        assert report["outcomes_read"] is False


def test_e6_authorized_successor_preserves_preregistered_boundary() -> None:
    protocol = build_authorized_protocol(
        authorization_note="explicit test authorization",
        authorization_received_at="2026-07-25T12:00:00+08:00",
    )

    validate_authorized_protocol(protocol)
    assert protocol["execution_authorization"][
        "model_load_authorized"
    ] is True
    assert protocol["execution_authorization"][
        "gpu_execution_authorized"
    ] is True
    assert protocol["execution_authorization"][
        "simulator_creation_authorized"
    ] is False
    assert protocol["execution_authorization"][
        "action_dispatch_authorized"
    ] is False
    assert protocol["execution_authorization"][
        "outcome_read_authorized"
    ] is False

    mutated = json.loads(json.dumps(protocol))
    mutated["workload"]["measured_policy_passes"] = 1
    with pytest.raises(
        ResourceSmokeError,
        match="changed preregistered workload",
    ):
        validate_authorized_protocol(mutated)


class _FakeScorer:
    noise_shape = (2, 7)
    checkpoint_load_seconds = 1.5
    devices = ["CudaDevice(id=0)"]

    def __init__(self, _protocol) -> None:
        pass

    def infer(self, inputs, *, prompt, noise):
        del inputs, prompt
        return np.asarray(noise, dtype=np.float64), 0.01


def test_e6_mocked_workload_measures_all_calls_and_repeatability() -> None:
    protocol = build_authorized_protocol(
        authorization_note="explicit test authorization",
        authorization_received_at="2026-07-25T12:00:00+08:00",
    )
    e2_protocol = {
        "prompt_template": (
            "Task: {task}\nCurrent semantic subtask: {subtask}"
        ),
        "stage_subtasks": {
            "initial": {
                "expected": "pick_up(red_mug_1)",
            }
        },
        "base_noise_seed": 20260725,
    }
    snapshots = [
        {
            "case_id": f"case-{index:03d}",
            "task": "put the red mug on the plate",
            "stage": "initial",
            "input_digest": f"{index:064x}",
            "inputs": {},
        }
        for index in range(100)
    ]

    measurement = measure_policy_workload(
        protocol=protocol,
        e2_protocol=e2_protocol,
        snapshots=snapshots,
        scorer_factory=_FakeScorer,
    )

    assert len(measurement["rows"]) == 300
    assert measurement["repeat_comparison_count"] == 200
    assert measurement["repeat_exact_count"] == 200
    assert measurement["repeat_exact_rate"] == 1.0
    summary = summarize_result(
        protocol,
        measurement,
        {
            "peak_process_gpu_memory_mib": 1000,
            "peak_process_rss_mib": 2000.0,
            "output_bytes": 100_000,
            "query_errors": [],
        },
        {"maximum_component_p99_ns": 100_000},
    )
    assert summary["qualified"] is True
    assert all(summary["gate_results"].values())
