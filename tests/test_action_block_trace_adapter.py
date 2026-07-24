from __future__ import annotations

import pytest

from proofalign.benchmark.action_block_trace_adapter import (
    ActionBlockTraceError,
    adapt_victim_episode,
)


def _audit(index: int) -> dict[str, object]:
    return {
        "policy_call_index": index,
        "policy_action_chunk_sha256": f"{index + 1:064x}",
        "clean_frame_sha256": f"{index + 10:064x}",
        "attacked_frame_sha256": f"{index + 10:064x}",
        "attack_type": "none",
        "changed": False,
    }


def test_adapter_exports_exact_consumed_prefixes_without_outcomes() -> None:
    payload = {
        "task_success": True,
        "unsafe_cost_or_collision": True,
        "trace": [
            {"phase": "wait", "action": [0.0] * 7},
            {
                "phase": "policy",
                "raw_action": [0.1] * 7,
                "policy_call": _audit(0),
                "reward": 99,
            },
            {"phase": "policy", "raw_action": [0.2] * 7, "env_info": {"cost": 1}},
            {
                "phase": "policy",
                "raw_action": [0.3] * 7,
                "policy_call": _audit(1),
            },
        ],
    }

    adapted = adapt_victim_episode(payload, episode_nonce="unit")

    assert adapted["outcome_fields_read"] == []
    assert adapted["unused_policy_chunk_tail_reconstructed"] is False
    assert len(adapted["action_blocks"]) == 2
    assert adapted["action_blocks"][0]["action_count"] == 2
    assert adapted["action_blocks"][0]["action_dimension"] == 7
    assert len(adapted["action_blocks"][0]["action_block"]["command"]) == 14


def test_adapter_rejects_unbound_policy_actions() -> None:
    with pytest.raises(ActionBlockTraceError, match="before its policy-call audit"):
        adapt_victim_episode(
            {"trace": [{"phase": "policy", "raw_action": [0.1] * 7}]},
            episode_nonce="unit",
        )


def test_adapter_rejects_action_dimension_drift() -> None:
    with pytest.raises(ActionBlockTraceError, match="dimension changes"):
        adapt_victim_episode(
            {
                "trace": [
                    {
                        "phase": "policy",
                        "raw_action": [0.1] * 7,
                        "policy_call": _audit(0),
                    },
                    {"phase": "policy", "raw_action": [0.2] * 6},
                ]
            },
            episode_nonce="unit",
        )
