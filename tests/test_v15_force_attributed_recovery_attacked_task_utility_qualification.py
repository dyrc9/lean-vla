from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import ARM_ORDER
from scripts import (
    freeze_v15_force_attributed_recovery_attacked_task_utility_qualification as freezer,
)
from scripts import (
    run_v15_force_attributed_recovery_attacked_task_utility_qualification as runner,
)


def _record() -> dict[str, Any]:
    return {
        "suite": "suite",
        "task_id": 1,
        "init_state_id": 2,
        "original_instruction": "trusted",
        "perturbed_instruction": "attacked",
        "objective": "constraint_violation",
    }


def test_warning_audit_separates_time_zero_from_active_time() -> None:
    audit = runner._WarningAudit()
    audit.episode_id = "episode"

    audit("Too many contacts. (ncon = 5000) Time = 0.0000.")
    audit("Too many contacts. (ncon = 5000) Time = 1.2500.")
    audit("another warning")

    report = audit.report()
    assert report["contact_capacity_warning_count"] == 2
    assert report["contact_capacity_time_zero_count"] == 1
    assert report[
        "contact_capacity_nonzero_or_unknown_time_count"
    ] == 1
    assert report["counts"]["other_mujoco_warning"] == 1


def test_attacked_patch_forwards_exact_records_and_restores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(runner.clean.online, "run_episode", fake_run)
    original_validate = runner.generic.validate_protocol
    original_specs = runner.generic.build_specs
    protocol = {"attack_records": [_record()]}
    warnings = runner._WarningAudit()

    with runner._patched_attacked(protocol, warnings):
        payload = runner.clean.online.run_episode(
            output_dir=tmp_path / "episode"
        )
        assert payload == {"ok": True}
        assert observed["attack_records"] == {
            ("suite", 1, 2): _record()
        }
        assert warnings.episode_id is None
        assert runner.generic.build_specs is runner.attack_base.build_specs

    assert runner.generic.validate_protocol is original_validate
    assert runner.generic.build_specs is original_specs


def test_schedule_retains_complete_clean_population() -> None:
    clean = load_json_object(freezer.CLEAN_PROTOCOL_PATH)

    schedule = freezer._schedule(clean)

    assert len(schedule) == 72
    assert [row["sequence_index"] for row in schedule] == list(range(72))
    assert Counter(row["arm"] for row in schedule) == {
        arm: 18 for arm in ARM_ORDER
    }
    assert {
        (row["base_pair_id"], row["arm"]) for row in schedule
    } == {
        (row["base_pair_id"], row["arm"])
        for row in clean["schedule"]
    }


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
    ] is False
