"""Static semantic-support audit for a support-conditioned four-arm study."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import math
from pathlib import Path
import random
import re
from typing import Any, Mapping, Sequence

from proofalign.benchmark.four_arm_v4 import (
    FourArmV4EpisodeSpec,
    build_schedule,
)
from proofalign.semantic_policy_wrapper import (
    SemanticPolicyWrapperError,
    compile_libero_task_graph,
)


SUPPORT_AUDIT_SCHEMA = "proofalign.four-arm-v4-semantic-support-audit.v1"


class FourArmV4SupportError(ValueError):
    """Raised when the support-conditioned population is malformed."""


def _normalized_stem(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def resolve_pair_bddl_path(
    pair: Mapping[str, Any],
    *,
    repo_root: Path,
) -> Path:
    directory = (
        repo_root
        / "external"
        / "LIBERO-Safety"
        / "libero"
        / "libero"
        / "bddl_files"
        / str(pair["suite"])
        / f"L{int(pair['level'])}"
    )
    requested = _normalized_stem(str(pair["trusted_instruction"]))
    matches = [
        candidate
        for candidate in sorted(directory.glob("*.bddl"))
        if _normalized_stem(candidate.stem) == requested
    ]
    if len(matches) != 1:
        raise FourArmV4SupportError(
            f"expected one BDDL match for {pair['base_pair_id']}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _goal_predicates(bddl_text: str) -> tuple[str, ...]:
    goal_start = bddl_text.find("(:goal")
    if goal_start < 0:
        return ()
    return tuple(
        re.findall(
            r"\(([A-Za-z][A-Za-z0-9_]*)\b",
            bddl_text[goal_start:],
        )
    )


def audit_pair_support(
    pair: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    path = resolve_pair_bddl_path(pair, repo_root=repo_root)
    text = path.read_text(encoding="utf-8")
    try:
        graph = compile_libero_task_graph(text)
        supported = True
        error = None
        compiled_goals = [
            {
                "predicate": goal.predicate,
                "target": goal.target,
                "destination": goal.destination,
                "part": goal.part,
            }
            for goal in graph.goals
        ]
    except SemanticPolicyWrapperError as exc:
        supported = False
        error = f"{type(exc).__name__}: {exc}"
        compiled_goals = []
    return {
        "base_pair_id": pair["base_pair_id"],
        "suite": pair["suite"],
        "level": pair["level"],
        "task_id": pair["task_id"],
        "trusted_instruction": pair["trusted_instruction"],
        "bddl_path": path.relative_to(repo_root).as_posix(),
        "raw_goal_predicates": list(_goal_predicates(text)),
        "compiled_goals": compiled_goals,
        "semantic_wrapper_initialization_supported": supported,
        "unsupported_reason": error,
    }


def build_support_schedule(
    confirmatory: Mapping[str, Any],
    design: Mapping[str, Any],
    *,
    stage: str,
    supported_base_pair_ids: Sequence[str],
) -> list[FourArmV4EpisodeSpec]:
    allowed = set(supported_base_pair_ids)
    if len(allowed) != len(supported_base_pair_ids):
        raise FourArmV4SupportError(
            "supported base-pair ids contain duplicates"
        )
    original = build_schedule(confirmatory, design, stage=stage)
    filtered = [
        spec for spec in original if spec.unit.base_pair_id in allowed
    ]
    observed = {spec.unit.base_pair_id for spec in filtered}
    if observed != allowed:
        raise FourArmV4SupportError(
            "supported base-pair ids differ from the frozen population"
        )
    return [
        replace(spec, sequence_index=index)
        for index, spec in enumerate(filtered, 1)
    ]


def cluster_bootstrap_interval(
    unit_rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    by_pair: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        by_pair[str(row["base_pair_id"])].append(row)
    pair_ids = sorted(by_pair)
    if not pair_ids or resamples <= 0:
        raise FourArmV4SupportError(
            "bootstrap requires clusters and positive resamples"
        )
    rng = random.Random(seed)
    estimates = []
    zero_denominator = 0
    for _ in range(resamples):
        eligible = 0
        transitions = 0
        for _cluster_index in range(len(pair_ids)):
            rows = by_pair[pair_ids[rng.randrange(len(pair_ids))]]
            for row in rows:
                is_eligible = bool(row["clean_eligible"])
                eligible += int(is_eligible)
                transitions += int(
                    is_eligible and row["transition_observed"]
                )
        if not eligible:
            zero_denominator += 1
            estimates.append(0.0)
        else:
            estimates.append(transitions / eligible)
    estimates.sort()
    return {
        "method": "two-sided-percentile-base-pair-cluster-bootstrap",
        "resamples": resamples,
        "seed": seed,
        "lower": estimates[
            math.floor(0.025 * (len(estimates) - 1))
        ],
        "upper": estimates[
            math.ceil(0.975 * (len(estimates) - 1))
        ],
        "zero_denominator_resamples_counted_as_zero": zero_denominator,
    }


def summarize_supported_m2(
    summary: Mapping[str, Any],
    *,
    supported_base_pair_ids: Sequence[str],
    resamples: int = 100000,
    seed: int = 2026072301,
) -> dict[str, Any]:
    allowed = set(supported_base_pair_ids)
    units = [
        row
        for row in summary["units"]
        if row["base_pair_id"] in allowed
    ]
    observed_pairs = {row["base_pair_id"] for row in units}
    if observed_pairs != allowed:
        raise FourArmV4SupportError(
            "M2 summary does not cover the support-conditioned population"
        )
    eligible_units = sum(bool(row["clean_eligible"]) for row in units)
    transition_units = sum(
        bool(row["clean_eligible"] and row["transition_observed"])
        for row in units
    )
    eligible_pairs = len(
        {
            row["base_pair_id"]
            for row in units
            if row["clean_eligible"]
        }
    )
    transition_pairs = len(
        {
            row["base_pair_id"]
            for row in units
            if row["transition_observed"]
        }
    )
    return {
        "unit_count": len(units),
        "clean_eligible_unit_count": eligible_units,
        "clean_eligible_base_pair_count": eligible_pairs,
        "transition_unit_count": transition_units,
        "transition_base_pair_count": transition_pairs,
        "transition_rate": (
            transition_units / eligible_units
            if eligible_units
            else None
        ),
        "cluster_bootstrap_interval_95": cluster_bootstrap_interval(
            units,
            resamples=resamples,
            seed=seed,
        ),
    }


__all__ = [
    "FourArmV4SupportError",
    "SUPPORT_AUDIT_SCHEMA",
    "audit_pair_support",
    "build_support_schedule",
    "cluster_bootstrap_interval",
    "resolve_pair_bddl_path",
    "summarize_supported_m2",
]
