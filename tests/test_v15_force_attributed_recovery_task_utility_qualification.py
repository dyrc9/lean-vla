from __future__ import annotations

from collections import Counter

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts import (
    freeze_v15_force_attributed_recovery_task_utility_qualification as freezer,
)
from scripts import (
    run_v15_force_attributed_recovery_task_utility_qualification as runner,
)


def test_workloads_retain_all_stress_pairs_with_new_seeds() -> None:
    v14 = load_json_object(freezer.V14_DEVELOPMENT_PROTOCOL_PATH)
    stress = load_json_object(freezer.V15_3_STRESS_PROTOCOL_PATH)

    workloads = freezer._derive_workloads(v14, stress)

    assert len(workloads) == 18
    assert {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in workloads
    } == {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in stress["environments"]
    }
    assert all(row["environment_seed"] == 5509 for row in workloads)
    assert all(row["policy_seed"] == 1551 for row in workloads)


def test_schedule_is_deterministic_complete_and_rotated_by_pair() -> None:
    v14 = load_json_object(freezer.V14_DEVELOPMENT_PROTOCOL_PATH)
    stress = load_json_object(freezer.V15_3_STRESS_PROTOCOL_PATH)
    workloads = freezer._derive_workloads(v14, stress)

    first = freezer._build_schedule(workloads)
    second = freezer._build_schedule(workloads)

    assert first == second
    assert len(first) == 72
    assert [row["sequence_index"] for row in first] == list(range(72))
    assert Counter(row["arm"] for row in first) == {
        arm: 18 for arm in ARM_ORDER
    }
    for workload in workloads:
        rows = [
            row
            for row in first
            if row["base_pair_id"] == workload["base_pair_id"]
        ]
        assert len(rows) == 4
        assert {row["arm"] for row in rows} == set(ARM_ORDER)


def test_runner_patches_only_online_successor_and_protocol_identity() -> None:
    original = runner.predecessor.base.online

    with runner._patched_predecessor():
        assert runner.predecessor.base.online is runner.online
        assert runner.predecessor.PROTOCOL_SCHEMA == runner.PROTOCOL_SCHEMA
        assert runner.predecessor.AUTHORIZED_STATUS == runner.AUTHORIZED_STATUS

    assert runner.predecessor.base.online is original


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
    assert retained["analysis"]["noninferiority_margin"] == -0.2
    assert retained["selection"]["all_stress_pairs_retained"] is True
    assert retained["selection"][
        "selected_pair_task_outcomes_observed_before_freeze"
    ] is False
