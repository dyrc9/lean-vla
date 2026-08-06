from __future__ import annotations

from scripts.freeze_prefix_recovery_v12_multijoint_terminal import (
    build_terminal as build_multijoint_terminal,
)
from scripts.freeze_recovery_runtime_v12_fixed_trace_terminal import (
    build_terminal as build_runtime_terminal,
)
from scripts.freeze_recovery_snapshot_v12_terminal import (
    build_terminal as build_snapshot_terminal,
)


def test_v12_2_runtime_fixed_trace_qualifies_transaction_only() -> None:
    terminal = build_runtime_terminal()

    assert terminal["qualification_pass"] is True
    assert terminal["metrics"]["valid_case_count"] == 10
    assert terminal["metrics"]["expected_classification_rate"] == 1.0
    assert terminal["metrics"]["happy_receipt_identity_rate"] == 1.0
    assert terminal["lifecycle"]["outcome_rollout_authorized"] is False


def test_v12_2_multijoint_nonpass_remains_frozen() -> None:
    terminal = build_multijoint_terminal()

    assert terminal["qualification_pass"] is False
    assert terminal["failed_gates"] == ["shadow_restore_identity"]
    assert terminal["metrics"]["recovery_candidate_coverage"] == 209 / 210
    assert terminal["metrics"]["recovery_completion_rate"] == 1.0
    assert terminal["lifecycle"][
        "policy_prefix_shadow_qualification_authorized"
    ] is False


def test_v12_3_snapshot_pass_does_not_relabel_v12_2() -> None:
    terminal = build_snapshot_terminal()

    assert terminal["qualification_pass"] is True
    assert terminal["metrics"][
        "trigger_full_state_bitwise_identity_rate"
    ] == 1.0
    assert terminal["metrics"][
        "harness_trusted_arm_bitwise_identity_rate"
    ] == 1.0
    assert terminal["metrics"][
        "harness_full_state_bitwise_identity_rate"
    ] == 201 / 210
    assert terminal["lifecycle"]["v12_2_nonpass_unchanged"] is True
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False
    assert terminal["lifecycle"]["outcome_rollout_authorized"] is False
