from __future__ import annotations

from scripts import freeze_predictive_virtual_brake_v14_multijoint_shadow_only_diagnostic as diagnostic


def test_bool_gates_requires_explicit_true() -> None:
    gates = diagnostic._bool_gates(
        {"a": True, "b": False, "c": 1},
        ("a", "b", "c", "d"),
    )

    assert gates == {
        "a": True,
        "b": False,
        "c": False,
        "d": False,
    }


def test_completed_local_diagnostic_preserves_registered_nonpass() -> None:
    required = (
        diagnostic.PROTOCOL_PATH,
        diagnostic.REGISTERED_TERMINAL_PATH,
        diagnostic.SHADOW_EVIDENCE_PATH,
        diagnostic.SHADOW_MANIFEST_PATH,
        diagnostic.SHADOW_CHECKSUMS_PATH,
    )
    if not all(path.is_file() for path in required):
        return

    report = diagnostic.build_diagnostic()

    assert report["registered_result"]["passed"] is False
    assert report["registered_result"]["classification_revised"] is False
    assert report["registered_result"]["failed_gates"] == [
        diagnostic.REGISTERED_CALIBRATION_GATE
    ]
    assert report["diagnostic_axes"][
        "mechanism_contract_complete"
    ] is True
    assert report["diagnostic_axes"][
        "causal_identity_diagnostic_complete"
    ] is True
    assert report["diagnostic_axes"][
        "descriptive_causal_safety_signal_observed"
    ] is True
    assert report["identity"][
        "pre_divergence_action_digest_mismatch_count"
    ] == 0
    assert report["identity"][
        "maximum_pre_divergence_margin_error_rad"
    ] == 0.0
