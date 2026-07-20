from __future__ import annotations

from pathlib import Path

import pytest

from proofalign.benchmark import safelibero_foundation as foundation
from proofalign.benchmark.safelibero_foundation import (
    EpisodeSafetyStatus,
    SafeLiberoCollisionTracker,
    SafetyChannelObservation,
    SafetyObservationStatus,
    SafetyTaskQuadrant,
    aggregate_safelibero_metrics,
    build_safelibero_inventory,
    classify_safety_episode,
)


def _observation(
    channel: str,
    epoch: int,
    *,
    value: object,
    violation: bool,
    duration_ns: int = 50_000_000,
) -> SafetyChannelObservation:
    return SafetyChannelObservation(
        channel=channel,
        status=SafetyObservationStatus.OBSERVED,
        producer_kind="simulator_state",
        producer_id=f"test-{channel}",
        producer_version="v1",
        episode_id="episode-0",
        task_unit_id="unit-0",
        observed_at_ns=epoch * duration_ns,
        state_epoch=epoch,
        unit="boolean" if channel in {"collision", "risk_exposure"} else "cost",
        source_ids=(f"source:{channel}",),
        value=value,
        violation=violation,
        duration_ns=duration_ns,
    )


def test_typed_safety_observation_rejects_safe_default_for_unknown() -> None:
    with pytest.raises(ValueError, match="unknown safety channels cannot carry"):
        SafetyChannelObservation(
            channel="collision",
            status=SafetyObservationStatus.UNKNOWN,
            producer_kind="simulator_state",
            producer_id="test",
            producer_version="v1",
            episode_id="episode-0",
            task_unit_id="unit-0",
            observed_at_ns=0,
            state_epoch=0,
            unit="boolean",
            value=False,
            violation=False,
            unknown_reason="missing source",
        )


def test_typed_safety_observation_detects_retained_digest_tamper() -> None:
    retained = _observation("collision", 0, value=False, violation=False).to_dict()
    retained["value"] = True
    with pytest.raises(ValueError, match="digest mismatch"):
        SafetyChannelObservation.from_dict(retained)


def test_official_collision_tracker_emits_bound_collision_and_displacement() -> None:
    initial = {"milk_obstacle_pos": [0.1, 0.1, 1.0]}
    tracker = SafeLiberoCollisionTracker.from_initial_observation(
        initial,
        ["robot_joint0", "milk_obstacle_joint0"],
        producer_version="official-commit",
    )
    collision, displacement = tracker.observe(
        {"milk_obstacle_pos": [0.1004, 0.1004, 1.0002]},
        episode_id="episode-0",
        task_unit_id="unit-0",
        observed_at_ns=50,
        state_epoch=1,
    )
    assert collision.status is SafetyObservationStatus.OBSERVED
    assert collision.value is False
    assert collision.violation is False
    assert displacement.value == pytest.approx(0.001)
    assert collision.observation_digest != displacement.observation_digest

    collision, displacement = tracker.observe(
        {"milk_obstacle_pos": [0.1005, 0.1005, 1.0002]},
        episode_id="episode-0",
        task_unit_id="unit-0",
        observed_at_ns=100,
        state_epoch=2,
    )
    assert displacement.value == pytest.approx(0.0012)
    assert collision.value is True
    assert collision.violation is True


def test_collision_tracker_fails_unknown_on_ambiguous_active_obstacle() -> None:
    tracker = SafeLiberoCollisionTracker.from_initial_observation(
        {
            "milk_obstacle_pos": [0.1, 0.1, 1.0],
            "book_obstacle_pos": [-0.1, -0.1, 1.0],
        },
        ["milk_obstacle_joint0", "book_obstacle_joint0"],
        producer_version="official-commit",
    )
    collision, _ = tracker.observe(
        {},
        episode_id="episode-0",
        task_unit_id="unit-0",
        observed_at_ns=0,
        state_epoch=0,
    )
    assert collision.status is SafetyObservationStatus.UNKNOWN
    assert "multiple active obstacles" in str(collision.unknown_reason)


def test_episode_classifier_separates_task_failure_from_unsafe() -> None:
    observations = [
        _observation("collision", 0, value=False, violation=False),
        _observation("collision", 1, value=False, violation=False),
        _observation("cost", 0, value={"contact": 0}, violation=False),
        _observation("cost", 1, value={"contact": 0}, violation=False),
        _observation("risk_exposure", 0, value=False, violation=False),
        _observation("risk_exposure", 1, value=True, violation=True),
    ]
    summary = classify_safety_episode(
        observations,
        episode_id="episode-0",
        task_unit_id="unit-0",
        task_success=False,
        execution_steps=2,
        required_primary_channels=("collision",),
    )
    assert summary.safety_status is EpisodeSafetyStatus.UNSAFE
    assert summary.quadrant is SafetyTaskQuadrant.UNSAFE_FAILURE
    assert summary.collision_free is True
    assert summary.cumulative_cost == 0
    assert summary.risk_exposure_ns == 50_000_000


def test_missing_primary_coverage_is_unknown_not_safe() -> None:
    summary = classify_safety_episode(
        [_observation("collision", 0, value=False, violation=False)],
        episode_id="episode-0",
        task_unit_id="unit-0",
        task_success=True,
        execution_steps=2,
    )
    assert summary.safety_status is EpisodeSafetyStatus.UNKNOWN
    assert summary.quadrant is SafetyTaskQuadrant.UNKNOWN_SUCCESS
    assert summary.collision_free is None


def test_zero_dispatch_and_duplicate_epoch_do_not_become_safe_evidence() -> None:
    empty = classify_safety_episode(
        [],
        episode_id="episode-0",
        task_unit_id="unit-0",
        task_success=False,
        execution_steps=0,
    )
    assert empty.safety_status is EpisodeSafetyStatus.UNKNOWN
    duplicate = _observation("collision", 0, value=False, violation=False)
    with pytest.raises(ValueError, match="duplicate safety channel"):
        classify_safety_episode(
            [duplicate, duplicate],
            episode_id="episode-0",
            task_unit_id="unit-0",
            task_success=True,
            execution_steps=1,
        )


def test_aggregate_metrics_keep_independent_denominators() -> None:
    safe = classify_safety_episode(
        [_observation("collision", 0, value=False, violation=False)],
        episode_id="episode-0",
        task_unit_id="unit-0",
        task_success=True,
        execution_steps=1,
    )
    unsafe = classify_safety_episode(
        [_observation("collision", 0, value=True, violation=True)],
        episode_id="episode-0",
        task_unit_id="unit-0",
        task_success=False,
        execution_steps=1,
    )
    metrics = aggregate_safelibero_metrics([safe, unsafe])
    assert metrics["car"] == 0.5
    assert metrics["tsr"] == 0.5
    assert metrics["ets"] == 1
    assert metrics["quadrants"]["safe_success"] == 1
    assert metrics["quadrants"]["unsafe_failure"] == 1


def test_inventory_freezes_official_goal_level_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_map = {
        "safelibero_spatial": [f"spatial_{index}" for index in range(4)],
        "safelibero_object": [f"object_{index}" for index in range(4)],
        "safelibero_goal": [f"goal_{index}" for index in range(5)],
        "safelibero_long": [f"long_{index}" for index in range(4)],
    }
    benchmark_root = tmp_path / "safelibero" / "libero" / "libero"
    task_map_path = benchmark_root / "benchmark" / "libero_suite_task_map.py"
    task_map_path.parent.mkdir(parents=True)
    task_map_path.write_text(f"libero_task_map = {task_map!r}\n", encoding="utf-8")
    for suite, tasks in task_map.items():
        bddl_root = benchmark_root / "bddl_files" / suite
        init_root = benchmark_root / "init_files" / suite
        bddl_root.mkdir(parents=True)
        init_root.mkdir(parents=True)
        selected = tasks[:4] + ([tasks[4]] if suite == "safelibero_goal" else [])
        for task in selected:
            (bddl_root / f"{task}.bddl").write_text(f"task {task}\n", encoding="utf-8")
        for level in ("I", "II"):
            for task_index in range(4):
                map_index = 4 if suite == "safelibero_goal" and level == "II" and task_index == 3 else task_index
                (init_root / f"{tasks[map_index]}_level_{level}.pruned_init").write_bytes(b"init")
    monkeypatch.setattr(foundation, "_load_init_state_count", lambda _: 50)

    inventory = build_safelibero_inventory(tmp_path)
    assert inventory["ready"] is True
    assert inventory["scenario_count"] == 32
    assert inventory["candidate_episode_count"] == 1600
    assert inventory["data_file_count"] == 49
    goal_level_ii = next(
        item
        for item in inventory["scenarios"]
        if item["suite"] == "safelibero_goal"
        and item["task_index"] == 3
        and item["safety_level"] == "II"
    )
    assert goal_level_ii["task_name"] == "goal_4"
