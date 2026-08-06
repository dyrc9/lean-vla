from __future__ import annotations

from collections import Counter
from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_physical_sufficiency_attacked_fresh15 import (
    CLEAN_PROTOCOL_PATH,
    M2_ATTACK_RECORDS_PATH,
    build_protocol,
    build_schedule,
)
from scripts.run_physical_sufficiency_attacked_pilot import (
    DEFAULT_PROTOCOL,
    attack_record_index,
    build_specs,
    derive_attack_transplants,
    validate_protocol,
)


def test_attack_transplants_preserve_frozen_task_prompts() -> None:
    clean = load_json_object(CLEAN_PROTOCOL_PATH)
    source = load_json_object(M2_ATTACK_RECORDS_PATH)
    records = derive_attack_transplants(clean, source)

    assert len(records) == 15
    assert Counter(row["suite"] for row in records) == {
        "human_safety": 5,
        "obstacle_avoidance": 5,
        "obstacle_avoidance_human": 5,
    }
    workloads = {
        (row["suite"], row["task_id"]): row
        for row in clean["workloads"]
    }
    assert all(
        row["original_instruction"]
        == workloads[(row["suite"], row["task_id"])][
            "trusted_instruction"
        ]
        and row["init_state_id"]
        == workloads[(row["suite"], row["task_id"])][
            "init_state_id"
        ]
        and row["transplant"]["prompt_text_changed"] is False
        for row in records
    )


def test_attacked_schedule_is_exact_clean_pair() -> None:
    clean = load_json_object(CLEAN_PROTOCOL_PATH)
    schedule = build_schedule(clean)

    assert len(schedule) == 60
    assert all(
        row["episode_id"].startswith(
            "physical_sufficiency_attacked_fresh15_"
        )
        for row in schedule
    )
    assert [
        (row["arm"], row["base_pair_id"], row["environment_seed"], row["policy_seed"])
        for row in schedule
    ] == [
        (row["arm"], row["base_pair_id"], row["environment_seed"], row["policy_seed"])
        for row in clean["schedule"]
    ]


def test_attacked_protocol_is_current_when_present() -> None:
    if not Path(DEFAULT_PROTOCOL).is_file():
        return
    retained = load_json_object(DEFAULT_PROTOCOL)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    validate_protocol(retained, protocol_path=DEFAULT_PROTOCOL)
    specs = build_specs(retained)
    assert len(specs) == 60
    assert all(spec.condition == "attacked" for spec in specs)
    assert len(attack_record_index(retained)) == 15
