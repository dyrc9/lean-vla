from __future__ import annotations

from scripts.run_four_arm_v4_l1_repair_qualification import (
    build_summary,
)


def _protocol() -> dict:
    pairs = [
        {
            "base_pair_id": f"suite_{index}",
            "suite": f"suite_{index // 15}",
        }
        for index in range(45)
    ]
    return {
        "protocol_id": "qualification-fixture",
        "qualification_population": {"frozen_pairs": pairs},
        "qualification_gates": {
            "geometry_ready_rate_min": 1.0,
            "eligible_candidate_rate_min": 0.9,
            "worst_suite_eligible_rate_min": 0.8,
            "selected_hard_violation_count_max": 0,
        },
    }


def _rows(*, eligible_count: int) -> list[dict]:
    rows = []
    for index, pair in enumerate(
        _protocol()["qualification_population"]["frozen_pairs"]
    ):
        rows.append(
            {
                **pair,
                "valid": True,
                "known": True,
                "geometry_audit": {"unresolved_counts": {}},
                "eligible_candidate_selected": index < eligible_count,
                "selected_hard_violation_count": 0,
                "policy_conditioned_env_step_count": 0,
                "dispatch_count": 0,
                "task_outcome_observed": False,
            }
        )
    return rows


def test_repair_qualification_passes_only_complete_zero_dispatch_probe() -> None:
    summary = build_summary(_protocol(), _rows(eligible_count=42))

    assert summary["qualification_pass"]
    assert summary["geometry_ready_count"] == 45
    assert summary["eligible_candidate_count"] == 42
    assert summary["dispatch_count"] == 0
    assert summary["task_outcome_count"] == 0


def test_repair_qualification_fails_worst_suite_gate() -> None:
    rows = _rows(eligible_count=45)
    for row in rows:
        if row["suite"] == "suite_2" and row["base_pair_id"].endswith(
            ("30", "31", "32", "33")
        ):
            row["eligible_candidate_selected"] = False
    summary = build_summary(_protocol(), rows)

    assert not summary["qualification_pass"]
    assert not summary["gate_conditions"]["worst_suite_eligible_rate"]
