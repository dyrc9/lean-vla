from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts import (
    freeze_v15_14_unified_force_envelope_attacked_task_utility_qualification as freezer,
)
from scripts import (
    run_v15_14_unified_force_envelope_attacked_task_utility_qualification as runner,
)


def test_warning_audit_separates_time_zero_from_active_time() -> None:
    audit = runner._WarningAudit()
    audit.episode_id = "episode"
    audit("Too many contacts. (ncon = 5000) Time = 0.0000.")
    audit("Too many contacts. (ncon = 5000) Time = 1.2500.")
    report = audit.report()
    assert report["contact_capacity_warning_count"] == 2
    assert report["contact_capacity_time_zero_count"] == 1
    assert report["contact_capacity_nonzero_or_unknown_time_count"] == 1


def test_legacy_patch_selects_v15_14_clean_runner_and_restores() -> None:
    original_clean = runner.legacy.clean
    original_schema = runner.legacy.PROTOCOL_SCHEMA
    with runner._patched_legacy():
        assert runner.legacy.clean is runner.clean
        assert runner.legacy.PROTOCOL_SCHEMA == runner.PROTOCOL_SCHEMA
        assert runner.legacy.STAGE == runner.STAGE
    assert runner.legacy.clean is original_clean
    assert runner.legacy.PROTOCOL_SCHEMA == original_schema


def test_attack_records_are_forwarded_to_disabled_arms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record = {
        "suite": "suite",
        "task_id": 1,
        "init_state_id": 2,
        "original_instruction": "trusted",
        "perturbed_instruction": "attacked",
        "objective": "constraint_violation",
    }
    observed: dict[str, Any] = {}

    def fake_disabled(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        runner.clean.disabled_online, "run_episode", fake_disabled
    )
    with runner._patched_legacy():
        with runner.legacy._patched_attacked(
            {"attack_records": [record]}
        ):
            payload = runner.clean.disabled_online.run_episode(
                output_dir=tmp_path / "episode"
            )
    assert payload == {"ok": True}
    assert observed["attack_records"] == {("suite", 1, 2): record}


def test_schedule_retains_complete_clean_population_and_seeds() -> None:
    clean = load_json_object(freezer.CLEAN_PROTOCOL_PATH)
    schedule = freezer._schedule(clean)
    clean_by_key = {
        (row["base_pair_id"], row["arm"]): row
        for row in clean["schedule"]
    }
    assert len(schedule) == 72
    assert [row["sequence_index"] for row in schedule] == list(range(72))
    assert Counter(row["arm"] for row in schedule) == {
        arm: 18 for arm in ARM_ORDER
    }
    for row in schedule:
        source = clean_by_key[(row["base_pair_id"], row["arm"])]
        assert row["environment_seed"] == source["environment_seed"]
        assert row["policy_seed"] == source["policy_seed"]


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )
    assert rebuilt == retained
    assert len(retained["attack_records"]) == 18
    assert retained["selection"]["all_clean_pairs_retained"] is True
    assert retained["selection"][
        "attacked_task_outcomes_observed_before_freeze"
    ] is True
    assert retained["selection"][
        "fresh1_outcomes_used_for_pair_or_attack_record_selection"
    ] is False
