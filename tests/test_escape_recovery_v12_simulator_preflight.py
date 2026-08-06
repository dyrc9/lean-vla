from __future__ import annotations

from scripts.freeze_escape_recovery_v12_simulator_preflight import (
    build_protocol,
)
from scripts.freeze_escape_recovery_v12_simulator_preflight_terminal import (
    build_terminal,
)


def test_v12_simulator_preflight_protocol_remains_no_outcome() -> None:
    protocol = build_protocol()

    assert protocol["population"]["pair_count"] == 45
    assert protocol["execution_boundary"][
        "task_outcome_read_authorized"
    ] is False
    assert protocol["execution_boundary"][
        "policy_load_authorized"
    ] is False
    assert protocol["execution_boundary"][
        "policy_action_dispatch_authorized"
    ] is False
    assert protocol["lifecycle"]["outcome_rollout_authorized"] is False


def test_v12_simulator_preflight_terminal_freezes_narrow_pass() -> None:
    terminal = build_terminal()

    assert terminal["qualification_pass"] is True
    assert all(terminal["gate_conditions"].values())
    assert terminal["metrics"]["valid_pair_count"] == 45
    assert terminal["metrics"]["recovery_candidate_coverage"] == 1.0
    assert terminal["metrics"]["selected_terminal_safe_rate"] == 1.0
    assert terminal["metrics"]["selected_joint_limit_crossing_count"] == 0
    assert terminal["selected_candidate_counts"] == {"negative_ry": 45}
    assert terminal["metrics"]["selected_replay_identity_rate"] == 2 / 45
    assert terminal["lifecycle"]["runtime_transaction_qualified"] is False
    assert terminal["lifecycle"]["clean_rollout_authorized"] is False
    assert terminal["lifecycle"]["outcome_rollout_authorized"] is False
