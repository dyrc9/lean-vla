from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_horizon_consistent_pick_up_fresh_dual_pilot import (
    OUTPUT_PATH,
    build_protocol,
)
from scripts.run_horizon_consistent_pick_up_fresh_dual_pilot import (
    QUALIFICATION_PROTOCOL_PATH,
    derive_fresh_pilot_workloads,
    validate_protocol,
)


def test_fresh_pilot_workloads_are_balanced_and_disjoint() -> None:
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    workloads = derive_fresh_pilot_workloads(qualification)

    assert len(workloads) == 3
    assert len({row["suite"] for row in workloads}) == 3
    assert len({row["base_pair_id"] for row in workloads}) == 3
    for row in workloads:
        assert row["init_state_id"] not in row["prior_init_state_ids"]
        assert row["environment_seed"] == 131
        assert row["policy_seed"] == 53
        assert row["max_steps"] == 600


def test_frozen_fresh_pilot_protocol_is_current() -> None:
    retained = load_json_object(OUTPUT_PATH)
    validate_protocol(retained, protocol_path=Path(OUTPUT_PATH))
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert rebuilt == retained
