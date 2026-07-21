"""Outcome-blind population and statistics helpers for SABER replications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import runpy
from typing import Any


class SaberReplicationDesignError(ValueError):
    """Raised when a frozen replication design is malformed."""


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rank(selection_seed: str, *parts: object) -> str:
    material = "|".join((selection_seed, *(str(part) for part in parts)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def load_official_task_map(path: Path) -> dict[str, dict[int, list[str]]]:
    if not path.is_file():
        raise SaberReplicationDesignError(f"official task map is missing: {path}")
    namespace = runpy.run_path(str(path))
    value = namespace.get("vla_safety_task_map")
    if not isinstance(value, dict):
        raise SaberReplicationDesignError("official task map did not define a mapping")
    return value


def build_stratified_population(
    *,
    protocol_id: str,
    design: Mapping[str, Any],
    task_map_path: Path,
    env_seed: int,
    policy_seed: int,
) -> list[dict[str, Any]]:
    """Build the exact outcome-blind population frozen by a large replication."""

    if design.get("selection_algorithm") != "sha256-ranked-stratified-v1":
        raise SaberReplicationDesignError("unexpected population-selection algorithm")
    selection_seed = design.get("selection_seed")
    suites = design.get("suites")
    levels = design.get("levels")
    tasks_per_level = design.get("tasks_per_level")
    init_min = design.get("init_state_min_inclusive")
    init_max = design.get("init_state_max_inclusive")
    if not isinstance(selection_seed, str) or not selection_seed:
        raise SaberReplicationDesignError("selection seed is missing")
    if not isinstance(suites, list) or not suites or not all(
        isinstance(item, str) and item for item in suites
    ):
        raise SaberReplicationDesignError("suite list is invalid")
    if levels != [0, 1, 2]:
        raise SaberReplicationDesignError("large replication must cover levels 0, 1, and 2")
    if type(tasks_per_level) is not int or tasks_per_level <= 0:
        raise SaberReplicationDesignError("tasks-per-level must be positive")
    if type(init_min) is not int or type(init_max) is not int or init_min > init_max:
        raise SaberReplicationDesignError("init-state range is invalid")

    task_map = load_official_task_map(task_map_path)
    effective_seed = f"{protocol_id}|{selection_seed}"
    population: list[dict[str, Any]] = []
    for suite in suites:
        suite_map = task_map.get(suite)
        if not isinstance(suite_map, dict):
            raise SaberReplicationDesignError(f"suite is absent from task map: {suite}")
        selected_tasks: list[tuple[int, int, int, str]] = []
        for level in levels:
            level_tasks = suite_map.get(level)
            if not isinstance(level_tasks, list) or len(level_tasks) < tasks_per_level:
                raise SaberReplicationDesignError(
                    f"suite/level lacks enough tasks: {suite}/L{level}"
                )
            ranked_offsets = sorted(
                range(len(level_tasks)),
                key=lambda offset: _rank(
                    effective_seed, "task", suite, level, offset
                ),
            )
            for offset in sorted(ranked_offsets[:tasks_per_level]):
                task_id = sum(len(suite_map[item]) for item in levels if item < level) + offset
                selected_tasks.append((task_id, level, offset, level_tasks[offset]))

        init_pool = list(range(init_min, init_max + 1))
        if len(init_pool) < len(selected_tasks):
            raise SaberReplicationDesignError("init-state range is too small")
        ranked_inits = sorted(
            init_pool,
            key=lambda init_id: _rank(effective_seed, "init", suite, init_id),
        )
        for (task_id, level, level_task_id, task_name), init_state_id in zip(
            sorted(selected_tasks), ranked_inits[: len(selected_tasks)], strict=True
        ):
            pair_id = (
                f"{suite}_task{task_id}_init{init_state_id}_"
                f"env{env_seed}_policy{policy_seed}"
            )
            population.append(
                {
                    "pair_id": pair_id,
                    "suite": suite,
                    "level": level,
                    "level_task_id": level_task_id,
                    "task_id": task_id,
                    "init_state_id": init_state_id,
                    "trusted_instruction": " ".join(task_name.split("_")),
                }
            )

    expected_count = design.get("expected_pair_count")
    if expected_count != len(population):
        raise SaberReplicationDesignError(
            f"population count differs from design: {len(population)} != {expected_count}"
        )
    identities = {
        (item["suite"], item["task_id"], item["init_state_id"])
        for item in population
    }
    if len(identities) != len(population):
        raise SaberReplicationDesignError("population identities are not unique")
    return population


def wilson_score_interval(
    successes: int,
    trials: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float] | None:
    """Return a two-sided Wilson score interval, or ``None`` for zero trials."""

    if type(successes) is not int or type(trials) is not int:
        raise SaberReplicationDesignError("successes and trials must be integers")
    if trials < 0 or successes < 0 or successes > trials:
        raise SaberReplicationDesignError("invalid binomial counts")
    if trials == 0:
        return None
    rate = successes / trials
    denominator = 1.0 + z * z / trials
    center = (rate + z * z / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt(rate * (1.0 - rate) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def probability_meeting_rate_gate(
    *,
    trials: int,
    true_rate: float,
    minimum_rate: float,
    minimum_count: int = 0,
) -> float:
    """Exact binomial probability of meeting a count-and-rate gate."""

    if trials <= 0:
        raise SaberReplicationDesignError("trials must be positive")
    if not 0.0 <= true_rate <= 1.0 or not 0.0 <= minimum_rate <= 1.0:
        raise SaberReplicationDesignError("rates must lie in [0, 1]")
    threshold = max(minimum_count, math.ceil(minimum_rate * trials - 1e-12))
    return sum(
        math.comb(trials, count)
        * true_rate**count
        * (1.0 - true_rate) ** (trials - count)
        for count in range(threshold, trials + 1)
    )


def population_projection(
    pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Drop generated attack fields before comparing a victim population."""

    fields = (
        "pair_id",
        "suite",
        "level",
        "level_task_id",
        "task_id",
        "init_state_id",
        "trusted_instruction",
    )
    return [{key: item.get(key) for key in fields} for item in pairs]
