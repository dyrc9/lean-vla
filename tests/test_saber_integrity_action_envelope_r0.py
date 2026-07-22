from __future__ import annotations

from scripts.run_saber_integrity_action_envelope_r0 import _validate_integrity_trace


def _payload(*, trace_action: list[float]) -> dict:
    final = [0.6000000000000001, 0.7999999999999999]
    return {
        "trace": [
            {
                "phase": "policy",
                "raw_action": [3.0, 4.0],
                "action": trace_action,
                "integrity_execution_audit": {
                    "method_id": "proofalign-integrity-v1",
                    "method_arm": "execution_only",
                    "authorization_verdict": "allow",
                    "receipt_digest": "a" * 64,
                    "intervention": {
                        "intervention_kind": "project_or_brake",
                        "nominal_command": [3.0, 4.0],
                        "final_command": final,
                        "witness_digest": "b" * 64,
                    },
                },
            }
        ]
    }


def test_integrity_trace_requires_the_exact_reauthorized_command_representation() -> None:
    exact = [0.6000000000000001, 0.7999999999999999]
    rounded_float32_like = [0.6000000238418579, 0.800000011920929]

    assert _validate_integrity_trace(_payload(trace_action=exact), l2_limit=1.0) == []
    assert _validate_integrity_trace(_payload(trace_action=rounded_float32_like), l2_limit=1.0) == [
        "policy step 0 executed action differs from reauthorized final command"
    ]
