from __future__ import annotations

from scripts.freeze_policy_prefix_shadow_v12_terminal import (
    build_terminal,
)


def test_fresh_policy_shadow_terminal_preserves_claim_boundary() -> None:
    terminal = build_terminal()

    assert terminal["qualification_pass"] is True
    assert terminal["metrics"]["policy_inference_count"] == 30
    assert terminal["metrics"]["live_policy_dispatch_count"] == 0
    assert terminal["metrics"]["outcome_read_count"] == 0
    assert (
        terminal["lifecycle"][
            "integrated_predictive_recovery_gate_authorized"
        ]
        is True
    )
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False


def test_fresh_policy_shadow_terminal_keeps_repeat_tail() -> None:
    terminal = build_terminal()
    tail = terminal["repeat_fidelity_tail"]

    assert tail["outlier_count"] == 1
    assert tail["outliers"][0]["decision_verdict"] == "recovery_required"
    assert tail["outliers"][0]["shadow_risk_predicted"] is True
    assert tail["outliers"][0]["reference_risk_predicted"] is True
