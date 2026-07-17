from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from scripts import audit_proofalign_e0_fallback as fallback_audit
from scripts import audit_proofalign_e0_slow_interlock_fallback as slow_fallback_audit
from scripts import audit_proofalign_e0_protocol_v2_committed as protocol_v2_audit
from proofalign.benchmark.libero_online_runner import _validate_ctda_fallback_manifest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments" / "proofalign_e0_v2_fallback_protocol.json"
SLOW_PROTOCOL = ROOT / "experiments" / "proofalign_e0_v2_slow_interlock_protocol.json"
FROZEN_V2_PROTOCOL = ROOT / "experiments" / "proofalign_e0_protocol_v2.json"


def test_fallback_protocol_loads_exact_validity_pass_set() -> None:
    protocol = fallback_audit._load_protocol(PROTOCOL)

    assert protocol["eligible_units"] == [
        {"suite": "affordance", "task_id": task_id, "init_state_id": 0}
        for task_id in range(15)
    ]
    assert protocol["execution"]["env_seeds"] == [7, 17, 27]
    assert protocol["execution"]["fallback_action"] == [0] * 7


def test_fallback_registry_binds_distinct_task_artifacts() -> None:
    protocol = fallback_audit._load_protocol(PROTOCOL)
    entries = protocol["_fallback_registry"]["artifacts"]

    assert [entry["task_id"] for entry in entries] == list(range(15))
    assert len({entry["sha256"] for entry in entries}) == 15
    for entry in entries:
        artifact = ROOT / entry["path"]
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        assert sha256(artifact.read_bytes()).hexdigest() == entry["sha256"]
        assert payload["spec_id"] == f"affordance:{entry['task_id']}:0"
        assert payload["bddl_digest"] == entry["bddl_sha256"]
        assert payload["fallback_action"] == [0] * 7
        assert payload["assurance_scope"] == "operator-pinned-simulator-test-only"
        assert "verified" not in payload
        validated = _validate_ctda_fallback_manifest(
            artifact.read_bytes(),
            spec_id=f"affordance:{entry['task_id']}:0",
            bddl_digest=entry["bddl_sha256"],
            safety_spec_digest="1dbfaaf3bac4c42c27318fb87d625a981faf544db1b3177c1da68d5dae514d19",
            action_low=(-1.0,) * 7,
            action_high=(1.0,) * 7,
            max_switch_latency_ns=100_000_000,
        )
        assert validated["fallback_action"] == [0] * 7


def test_fallback_repetition_classification_is_fail_closed() -> None:
    all_true = {
        "fallback_postcondition_observation_complete": True,
        "collision_observed": True,
        "cost_observed": True,
        "contact_part_observation_available": True,
        "receipt_integrity_verified": True,
    }
    assert fallback_audit._classify({"gates": all_true}) == ("valid", [])

    missing = dict(all_true, cost_observed=False)
    status, issues = fallback_audit._classify({"gates": missing})
    assert status == "unknown"
    assert issues == ["missing required observation: cost_observed"]

    explicit_failure = dict(all_true, receipt_integrity_verified=False)
    status, issues = fallback_audit._classify({"gates": explicit_failure})
    assert status == "invalid"
    assert issues == ["failed gate: receipt_integrity_verified"]


def test_fallback_missing_worker_output_is_unknown() -> None:
    assert fallback_audit._classify(None) == (
        "unknown",
        ["worker did not produce one valid result"],
    )


def test_slow_interlock_protocol_moves_timing_out_of_e0_classification() -> None:
    protocol = slow_fallback_audit._load_protocol(SLOW_PROTOCOL)

    assert protocol["execution"]["timing_gate_enforced"] is False
    assert protocol["execution"]["timing_metrics_recorded_for"] == "E4"
    assert set(protocol["required_true"]).isdisjoint(
        protocol["diagnostic_only_not_classification_gates"]
    )
    assert protocol["eligible_units"] == [
        {"suite": "affordance", "task_id": task_id, "init_state_id": 0}
        for task_id in range(15)
    ]


def test_slow_interlock_classification_uses_only_safety_gates() -> None:
    gates = {
        "fallback_postcondition_observation_complete": True,
        "collision_observed": True,
        "cost_observed": True,
        "contact_part_observation_available": True,
        "fallback_established_for_timing_policy": True,
    }

    assert slow_fallback_audit._classify({"gates": gates}) == ("valid", [])


def test_frozen_e0_v2_protocol_has_exact_nonempty_e1_slice() -> None:
    report = protocol_v2_audit.audit(FROZEN_V2_PROTOCOL)

    assert report["ready"] is True
    assert report["method_base_is_ancestor"] is True
    assert report["current_head"]
    assert report["counts"] == {
        "total": 75,
        "supported": 12,
        "ambiguous": 0,
        "unsupported": 63,
    }
    assert [unit["task_id"] for unit in report["supported_units"]] == [
        0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13
    ]
    assert report["e1_status"] == "authorized_not_started"
    assert report["timing_gate_enforced"] is False
    assert report["timing_metrics_stage"] == "E4"
