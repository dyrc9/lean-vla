from __future__ import annotations

from scripts.run_saber_integrity_action_envelope_r2 import (
    _intervention_stats,
    _validate_integrity_trace_v2,
)


def _step(*, guard_kind: str, raw: list[float], final: list[float]) -> dict:
    return {
        "phase": "policy",
        "raw_action": raw,
        "action": final,
        "integrity_execution_audit": {
            "method_id": "proofalign-integrity-v1",
            "method_arm": "execution_only",
            "authorization_verdict": "allow",
            "receipt_digest": "a" * 64,
            "pre_authorization_input_guard": {
                "schema": "proofalign.integrity-nonfinite-input-guard.v1",
                "kind": guard_kind,
                "source_command_sha256": "b" * 64,
                "source_command_shape": [7],
                "source_command_dtype": "float32",
                "nonfinite_indices": [2] if guard_kind.startswith("brake") else [],
            },
            "intervention": {
                "intervention_kind": "pass",
                "nominal_command": raw,
                "final_command": final,
                "witness_digest": None,
            },
        },
    }


def test_nonfinite_brake_is_auditable_and_dispatches_only_zero() -> None:
    payload = {"trace": [_step(guard_kind="brake_nonfinite_policy_command", raw=[0.0] * 7, final=[0.0] * 7)]}

    assert _validate_integrity_trace_v2(payload, l2_limit=1.0) == []
    assert _intervention_stats(payload)["nonfinite_source_policy_brake_count"] == 1
    assert _intervention_stats(payload)["all_executed_actions_within_envelope"] is True


def test_nonfinite_brake_rejects_a_nonzero_dispatch() -> None:
    payload = {"trace": [_step(guard_kind="brake_nonfinite_policy_command", raw=[0.0] * 7, final=[0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0])]}

    assert _validate_integrity_trace_v2(payload, l2_limit=1.0) == [
        "policy step 0 did not dispatch a deterministic zero brake"
    ]
