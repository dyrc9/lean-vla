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
    _clean_analysis,
    _effective_units,
    build_schedule,
    schedule_digest,
    validate_ledger_rows,
)
from proofalign.benchmark.confirmatory import file_sha256, load_json_object
from proofalign.benchmark.four_arm_v4_exploratory import (
    validate_exploratory_successor,
)
from proofalign.semantic_policy_wrapper import (
    SemanticPolicyWrapperError,
    compile_libero_task_graph,
)


SUPPORT_AUDIT_SCHEMA = "proofalign.four-arm-v4-semantic-support-audit.v1"
SUPPORT_PROTOCOL_SCHEMA = (
    "proofalign.four-arm-v4-support45-successor.v1"
)
SUPPORT_ANALYSIS_SCHEMA = (
    "proofalign.four-arm-v4-support45-terminal-analysis.v1"
)


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


def validate_support_successor(
    protocol: Mapping[str, Any],
    *,
    repo_root: Path,
    verify_source_bindings: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    if protocol.get("schema") != SUPPORT_PROTOCOL_SCHEMA:
        raise FourArmV4SupportError(
            "unsupported support-conditioned protocol schema"
        )
    if protocol.get("protocol_id") != (
        "proofalign-four-arm-v4-support45-clean-fresh2-20260727"
    ):
        raise FourArmV4SupportError(
            "support-conditioned protocol id changed"
        )
    if protocol.get("protocol_status") != (
        "post_failure_support_conditioned_clean_execution_authorized"
    ):
        raise FourArmV4SupportError(
            "support-conditioned authorization status changed"
        )
    if (
        protocol.get("outcome_informed_design_change") is not True
        or protocol.get("post_failure_population_change") is not True
        or protocol.get("confirmatory_claim_authorized") is not False
    ):
        raise FourArmV4SupportError(
            "support-conditioned disclosure boundary changed"
        )
    parent_binding = protocol.get("parent_exploratory_protocol")
    if not isinstance(parent_binding, Mapping):
        raise FourArmV4SupportError(
            "parent exploratory binding must be an object"
        )
    parent_path = repo_root / str(parent_binding.get("path", ""))
    parent = load_json_object(parent_path)
    design, confirmatory = validate_exploratory_successor(
        parent,
        repo_root=repo_root,
    )
    if (
        parent_binding.get("protocol_id") != parent.get("protocol_id")
        or parent_binding.get("sha256") != file_sha256(parent_path)
    ):
        raise FourArmV4SupportError(
            "parent exploratory protocol binding differs"
        )
    audit_binding = protocol.get("semantic_support_audit")
    if not isinstance(audit_binding, Mapping):
        raise FourArmV4SupportError(
            "semantic support audit binding must be an object"
        )
    audit_path = repo_root / str(audit_binding.get("path", ""))
    audit = load_json_object(audit_path)
    if (
        audit.get("schema") != SUPPORT_AUDIT_SCHEMA
        or audit.get("classification")
        != "four_arm_full_population_semantic_support_inadequate"
        or audit.get("execution_authorized") is not False
        or audit_binding.get("audit_id") != audit.get("audit_id")
        or audit_binding.get("sha256") != file_sha256(audit_path)
    ):
        raise FourArmV4SupportError(
            "semantic support audit binding differs"
        )
    audit_bindings = audit.get("bindings")
    if not isinstance(audit_bindings, Mapping):
        raise FourArmV4SupportError(
            "semantic support audit source bindings are absent"
        )
    for group in ("bddl_sha256", "source_sha256"):
        bindings = audit_bindings.get(group)
        if not isinstance(bindings, Mapping) or not bindings:
            raise FourArmV4SupportError(
                f"semantic support audit {group} is empty"
            )
        for relative, expected in bindings.items():
            path = repo_root / relative
            if not path.is_file() or file_sha256(path) != expected:
                raise FourArmV4SupportError(
                    f"semantic support audit binding is stale: {relative}"
                )
    failed = audit.get("failed_fresh1")
    if not isinstance(failed, Mapping):
        raise FourArmV4SupportError(
            "fresh1 failure binding is absent"
        )
    for relative_key, digest_key in (
        ("failure_path", "failure_sha256"),
        ("root", "run_manifest_sha256"),
        ("root", "checksums_sha256"),
    ):
        path = repo_root / str(failed[relative_key])
        if digest_key == "run_manifest_sha256":
            path = path / "run_manifest.json"
        elif digest_key == "checksums_sha256":
            path = path / "SHA256SUMS"
        if not path.is_file() or file_sha256(path) != failed[digest_key]:
            raise FourArmV4SupportError(
                f"fresh1 failure binding differs: {digest_key}"
            )
    support = audit["supported_population"]
    supported_ids = tuple(support["base_pair_ids"])
    if (
        len(supported_ids) != 45
        or len(set(supported_ids)) != 45
        or support.get("unit_count") != 90
        or support.get("four_arm_episode_count_per_stage") != 360
        or support.get(
            "passes_disclosed_exploratory_40_percent_threshold"
        )
        is not True
        or protocol.get("supported_base_pair_ids")
        != list(supported_ids)
    ):
        raise FourArmV4SupportError(
            "support-conditioned population binding differs"
        )
    if (
        protocol.get("support_rule") != audit.get("support_rule")
        or protocol.get("population")
        != {
            "base_pair_count": 45,
            "unit_count": 90,
            "clean_episode_count": 360,
            "excluded_base_pair_count": 15,
            "excluded_suite_counts": {"affordance": 15},
        }
        or protocol.get("m2_support_conditioned_descriptive")
        != support.get("m2_post_outcome_descriptive")
    ):
        raise FourArmV4SupportError(
            "support-conditioned disclosure differs from audit"
        )
    for stage in (
        "B_clean_closed_loop",
        "C_attacked_closed_loop",
    ):
        specs = build_support_schedule(
            confirmatory,
            design,
            stage=stage,
            supported_base_pair_ids=supported_ids,
        )
        expected_digest = support["schedule_sha256"][stage]
        if (
            protocol["schedule_sha256"].get(stage)
            != expected_digest
            or schedule_digest(specs) != expected_digest
        ):
            raise FourArmV4SupportError(
                f"support-conditioned schedule differs: {stage}"
            )
    if protocol.get("execution_authorization") != {
        "stage_b_clean_rollout": True,
        "stage_c_attacked_rollout": False,
    }:
        raise FourArmV4SupportError(
            "support-conditioned stage authorization changed"
        )
    expected_clean_gate = {
        **design["clean_gate"],
        "valid_episode_count": 360,
    }
    if (
        protocol.get("clean_gate") != expected_clean_gate
        or protocol.get("analysis") != design.get("analysis")
        or protocol.get("runtime_dependency")
        != parent.get("runtime_dependency")
        or protocol.get("victim") != parent.get("victim")
        or protocol.get("episode_constants")
        != parent.get("episode_constants")
    ):
        raise FourArmV4SupportError(
            "support-conditioned runtime or analysis contract changed"
        )
    if (
        protocol.get("replacement_of_fresh1") is not False
        or protocol.get("fresh1_resume_allowed") is not False
        or protocol.get("partial_root_resume_allowed") is not False
        or protocol.get("invalid_episode_abort_cap") != 1
    ):
        raise FourArmV4SupportError(
            "support-conditioned fresh-root rules changed"
        )
    if protocol.get("fresh_roots") != {
        "stage_b_clean": (
            "results/proofalign_four_arm_v4_support45_clean_"
            "20260727_fresh2"
        ),
        "stage_c_attacked": (
            "results/proofalign_four_arm_v4_support45_attacked_"
            "20260727_fresh2"
        ),
    }:
        raise FourArmV4SupportError(
            "support-conditioned fresh roots changed"
        )
    budget = protocol.get("resource_budget")
    if not isinstance(budget, Mapping) or (
        budget.get("stage_b_episode_cap") != 360
        or budget.get("stage_c_episode_cap") != 360
        or budget.get("policy_and_egl_must_be_distinct") is not True
        or budget.get(
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
        )
        != 1024
    ):
        raise FourArmV4SupportError(
            "support-conditioned resource budget changed"
        )
    if protocol.get("paper_role") != (
        "post-outcome post-failure support-conditioned exploratory "
        "two-layer ablation; hypothesis generation only"
    ):
        raise FourArmV4SupportError(
            "support-conditioned paper role changed"
        )
    if verify_source_bindings:
        source = protocol.get("source")
        bindings = (
            source.get("sha256")
            if isinstance(source, Mapping)
            else None
        )
        if not isinstance(bindings, Mapping) or not bindings:
            raise FourArmV4SupportError(
                "support-conditioned source bindings are empty"
            )
        for relative, expected in bindings.items():
            path = repo_root / relative
            if not path.is_file() or file_sha256(path) != expected:
                raise FourArmV4SupportError(
                    "support-conditioned source binding is stale: "
                    f"{relative}"
                )
    return design, confirmatory, supported_ids


def validate_support_ledger_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    confirmatory: Mapping[str, Any],
    design: Mapping[str, Any],
    stage: str,
    supported_base_pair_ids: Sequence[str],
) -> dict[str, Mapping[str, Any]]:
    specs = build_support_schedule(
        confirmatory,
        design,
        stage=stage,
        supported_base_pair_ids=supported_base_pair_ids,
    )
    expected = {spec.episode_id: spec for spec in specs}
    original = {
        spec.episode_id: spec
        for spec in build_schedule(confirmatory, design, stage=stage)
    }
    transformed = []
    by_id = {}
    for row in rows:
        episode_id = row.get("episode_id")
        if (
            not isinstance(episode_id, str)
            or episode_id not in expected
            or episode_id in by_id
        ):
            raise FourArmV4SupportError(
                f"support ledger episode is duplicate or unexpected: "
                f"{episode_id}"
            )
        if row.get("sequence_index") != expected[
            episode_id
        ].sequence_index:
            raise FourArmV4SupportError(
                f"support ledger sequence differs: {episode_id}"
            )
        adjusted = dict(row)
        adjusted["sequence_index"] = original[
            episode_id
        ].sequence_index
        transformed.append(adjusted)
        by_id[episode_id] = row
    validate_ledger_rows(
        transformed,
        confirmatory=confirmatory,
        protocol=design,
        stage=stage,
    )
    return by_id


def build_support_clean_analysis(
    protocol: Mapping[str, Any],
    *,
    design: Mapping[str, Any],
    confirmatory: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    terminal: bool,
    episode_artifacts_verified: bool,
) -> dict[str, Any]:
    supported_ids = tuple(protocol["supported_base_pair_ids"])
    specs = build_support_schedule(
        confirmatory,
        design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported_ids,
    )
    by_id = validate_support_ledger_rows(
        rows,
        confirmatory=confirmatory,
        design=design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported_ids,
    )
    effective = _effective_units(specs, by_id)
    result = _clean_analysis(design, effective)
    present = len(by_id)
    valid = sum(
        row.get("attempt_status") == "valid"
        for row in by_id.values()
    )
    all_present = present == 360
    all_valid = valid == 360
    if not terminal and not all_present:
        classification = "support45_clean_stage_incomplete"
    elif not all_present or not all_valid:
        classification = "support45_clean_terminal_invalid_conservative"
    elif not episode_artifacts_verified:
        classification = "support45_clean_terminal_unverified_artifacts"
    else:
        classification = (
            "support45_clean_gate_pass"
            if result["clean_gate_pass"]
            else "support45_clean_gate_nonpass"
        )
    return {
        "schema": SUPPORT_ANALYSIS_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "design_protocol_id": design["protocol_id"],
        "stage": "B_clean_closed_loop",
        "support_conditioned": True,
        "confirmatory_claim_authorized": False,
        "terminal_requested": terminal,
        "outcomes_observed": bool(rows),
        "expected_base_pair_count": 45,
        "expected_unit_count": 90,
        "expected_episode_count": 360,
        "present_episode_count": present,
        "valid_episode_count": valid,
        "missing_episode_count": 360 - present,
        "invalid_episode_count": present - valid,
        "conservative_missing_rule_applied": (
            not all_present or not all_valid
        ),
        "episode_artifacts_verified": episode_artifacts_verified,
        "classification": classification,
        **result,
        "claim_boundary": (
            "This is a post-outcome, post-failure exploratory analysis "
            "conditioned on the 45 base pairs supported by the frozen "
            "semantic wrapper. It is not a full-population or confirmatory "
            "result."
        ),
    }


__all__ = [
    "FourArmV4SupportError",
    "SUPPORT_AUDIT_SCHEMA",
    "SUPPORT_ANALYSIS_SCHEMA",
    "SUPPORT_PROTOCOL_SCHEMA",
    "audit_pair_support",
    "build_support_schedule",
    "cluster_bootstrap_interval",
    "resolve_pair_bddl_path",
    "summarize_supported_m2",
    "build_support_clean_analysis",
    "validate_support_ledger_rows",
    "validate_support_successor",
]
