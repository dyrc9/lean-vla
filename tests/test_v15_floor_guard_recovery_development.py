from __future__ import annotations

from collections import Counter

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v15_floor_guard_recovery_development as freezer


def test_development_selects_all_and_only_disclosed_deadlock_pairs() -> None:
    terminal = load_json_object(freezer.V14_TERMINAL_PATH)

    selected = freezer._selected_base_pairs(terminal)

    assert len(selected) == 7
    assert set(selected) == {
        str(row["base_pair_id"]) for row in terminal["deadlock_cases"]
    }


def test_development_schedule_is_complete_four_arm_replay() -> None:
    source = load_json_object(freezer.V14_PROTOCOL_PATH)
    terminal = load_json_object(freezer.V14_TERMINAL_PATH)
    selected = freezer._selected_base_pairs(terminal)

    schedule = freezer._development_schedule(source, selected)

    assert len(schedule) == 28
    assert [row["sequence_index"] for row in schedule] == list(range(28))
    assert Counter(row["arm"] for row in schedule) == {
        "vla_only": 7,
        "execution_only": 7,
        "semantic_only": 7,
        "dual": 7,
    }
    assert all(
        row["episode_id"].startswith(freezer.STAGE + "_")
        for row in schedule
    )


def test_frozen_development_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)

    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
