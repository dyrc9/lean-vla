from __future__ import annotations

from scripts.freeze_recoverable_alignment_v12_contract_qualification import (
    build_protocol,
)
from scripts.freeze_recoverable_alignment_v12_contract_terminal import (
    build_terminal,
)
from scripts.run_recoverable_alignment_v12_contract_qualification import (
    _expected_run,
)


def test_v12_contract_protocol_remains_no_outcome() -> None:
    protocol = build_protocol()

    assert protocol["status"] == (
        "authorized_no_outcome_contract_prequalification"
    )
    assert protocol["lifecycle"]["outcome_rollout_authorized"] is False
    assert protocol["gates"]["env_step_count_max"] == 0
    assert protocol["gates"]["outcome_read_count_max"] == 0
    assert protocol["predecessor_terminal"]["unchanged"] is True


def test_v12_contract_qualification_passes_frozen_gates() -> None:
    result, rows = _expected_run()

    assert result["qualification_pass"] is True
    assert all(result["gate_conditions"].values())
    assert result["row_count"] == 655
    assert len(rows) == 655
    assert result["q1_sparse_l1"][
        "clean_exact_passthrough_rate"
    ] == 1.0
    assert result["q1_sparse_l1"]["action_rewrite_count"] == 0
    assert result["q2_analytic_shadow_contract"][
        "false_trigger_rate"
    ] == 0.0
    assert result["q3_recovery_contract"][
        "old_policy_authorization_accept_count"
    ] == 0
    assert result["execution_boundary"] == {
        "simulator_create_count": 0,
        "env_step_count": 0,
        "policy_load_count": 0,
        "outcome_read_count": 0,
        "dispatch_count": 0,
    }


def test_v12_contract_terminal_does_not_authorize_outcome() -> None:
    terminal = build_terminal()

    assert terminal["qualification_pass"] is True
    assert terminal["lifecycle"]["online_shadow_qualified"] is False
    assert terminal["lifecycle"][
        "online_shadow_preflight_authorized"
    ] is True
    assert terminal["lifecycle"]["outcome_rollout_authorized"] is False
