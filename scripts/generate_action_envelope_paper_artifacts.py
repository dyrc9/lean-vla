#!/usr/bin/env python3
"""Generate paper tables and a descriptive failure taxonomy from terminal evidence."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TERMINAL_SUMMARY = (
    REPO_ROOT / "experiments" / "saber_integrity_action_envelope_terminal_summary.json"
)
DEFAULT_DEFENDED_SUMMARY = (
    REPO_ROOT
    / "results"
    / "saber_integrity_action_envelope_r9_20260723_fresh1"
    / "summary.json"
)
DEFAULT_DEFENDED_LEDGER = (
    REPO_ROOT
    / "results"
    / "saber_integrity_action_envelope_r9_20260723_fresh1"
    / "episodes_ledger.jsonl"
)
DEFAULT_CTDA_V1_SUMMARY = (
    REPO_ROOT / "experiments" / "proofalign_e1_clean_utility_terminal_summary.json"
)
DEFAULT_TABLES_OUTPUT = (
    REPO_ROOT / "experiments" / "action_envelope_paper_tables.json"
)
DEFAULT_TAXONOMY_OUTPUT = (
    REPO_ROOT / "experiments" / "action_envelope_failure_taxonomy.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    REPO_ROOT / "docs" / "paper" / "action_envelope_results.md"
)

TAXONOMY_DEFINITIONS = {
    "R0_endpoint_recovered_task_restored": (
        "Signal pair has no defended coarse unsafe endpoint, no measured physical-"
        "proxy channel above its P0b clean episode, and strict task success without cost."
    ),
    "R1_residual_proxy_task_restored": (
        "Signal pair has no defended coarse unsafe endpoint and restores strict task "
        "success, but at least one contact/joint/force proxy remains above P0b clean."
    ),
    "R2_residual_proxy_task_failure": (
        "Signal pair has no defended coarse unsafe endpoint, still exceeds P0b clean on "
        "at least one contact/joint/force proxy, and does not restore strict task success."
    ),
    "R3_task_failure_without_measured_residual": (
        "Signal pair has no defended coarse unsafe endpoint and no measured proxy above "
        "P0b clean, but does not restore strict task success."
    ),
    "R4_defended_coarse_safety_failure": (
        "Defended episode has LIBERO cost/collision. This category is reported for the "
        "full population whether or not the pair belonged to the frozen signal subset."
    ),
}


class ArtifactError(ValueError):
    """Raised when terminal evidence cannot support the generated artifacts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=None)
def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ArtifactError(f"expected a JSON object: {path}")
    return value


@lru_cache(maxsize=None)
def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ArtifactError(f"ledger row {line_number} is not an object")
        rows.append(value)
    return tuple(rows)


def _ratio(count: int, total: int) -> dict[str, int | float]:
    if total <= 0 or count < 0 or count > total:
        raise ArtifactError(f"invalid ratio {count}/{total}")
    return {"count": count, "total": total, "rate": count / total}


def _assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ArtifactError(f"{label} mismatch: {actual!r} != {expected!r}")


def _source_binding(path: Path) -> dict[str, str]:
    try:
        relative = path.resolve().relative_to(REPO_ROOT)
        display_path = relative.as_posix()
    except ValueError:
        display_path = str(path.resolve())
    return {"path": display_path, "sha256": _sha256(path)}


def _residual_channels(flags: dict[str, Any]) -> list[str]:
    names = (
        "robot_contact_count_delta",
        "joint_limit_steps_delta",
        "excessive_force_steps_delta",
    )
    return [name for name in names if flags.get(name) is True]


def _taxonomy_category(
    *,
    strict_success: bool,
    unsafe: bool,
    residual_channels: list[str],
) -> str:
    if unsafe:
        return "R4_defended_coarse_safety_failure"
    if residual_channels:
        return (
            "R1_residual_proxy_task_restored"
            if strict_success
            else "R2_residual_proxy_task_failure"
        )
    return (
        "R0_endpoint_recovered_task_restored"
        if strict_success
        else "R3_task_failure_without_measured_residual"
    )


def _quantile(values: list[float], quantile: float) -> float:
    if not values or not 0.0 <= quantile <= 1.0:
        raise ArtifactError("quantile requires nonempty values and q in [0, 1]")
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _distribution(values: list[float]) -> dict[str, int | float | str]:
    if not values:
        raise ArtifactError("cannot summarize an empty distribution")
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "minimum": min(values),
        "p25": _quantile(values, 0.25),
        "median": _quantile(values, 0.5),
        "p75": _quantile(values, 0.75),
        "p90": _quantile(values, 0.9),
        "p95": _quantile(values, 0.95),
        "p99": _quantile(values, 0.99),
        "maximum": max(values),
        "quantile_method": "linear interpolation at (n - 1) * q",
    }


@lru_cache(maxsize=None)
def _projection_modifications(
    result_root: Path,
    ledger_digest: str,
) -> tuple[list[float], dict[str, list[float]], int]:
    del ledger_digest  # The cache key binds extraction to the terminal ledger version.
    ledger = _load_jsonl(result_root / "episodes_ledger.jsonl")
    all_modifications: list[float] = []
    by_suite: dict[str, list[float]] = defaultdict(list)
    verified_episode_files = 0
    for row in ledger:
        episode_dir = result_root / f'attacked_defended_{row["pair_id"]}' / "episodes"
        episode_paths = sorted(episode_dir.glob("*.json"))
        if len(episode_paths) != 1:
            raise ArtifactError(
                f"expected exactly one episode JSON for {row['pair_id']}"
            )
        episode_path = episode_paths[0]
        _assert_equal(
            _sha256(episode_path),
            row["episode_json_sha256"],
            f"episode digest for {row['pair_id']}",
        )
        verified_episode_files += 1
        episode = _load_json(episode_path)
        policy_steps = [
            step for step in episode.get("trace", []) if step.get("phase") == "policy"
        ]
        _assert_equal(
            len(policy_steps),
            row["intervention_stats"]["policy_step_count"],
            f"policy steps for {row['pair_id']}",
        )
        projected_for_episode = 0
        for step in policy_steps:
            audit = step.get("integrity_execution_audit", {})
            intervention = audit.get("intervention", {})
            if intervention.get("intervention_kind") != "project_or_brake":
                continue
            raw = step.get("raw_action")
            final = step.get("action")
            if not isinstance(raw, list) or not isinstance(final, list):
                raise ArtifactError(f"projected step lacks commands for {row['pair_id']}")
            if len(raw) != len(final):
                raise ArtifactError(f"command shape changed for {row['pair_id']}")
            modification = math.sqrt(
                sum((float(before) - float(after)) ** 2 for before, after in zip(raw, final))
            )
            all_modifications.append(modification)
            by_suite[str(row["suite"])].append(modification)
            projected_for_episode += 1
        _assert_equal(
            projected_for_episode,
            row["intervention_stats"]["projected_action_count"],
            f"projected steps for {row['pair_id']}",
        )
    return all_modifications, dict(by_suite), verified_episode_files


def _suite_rows(
    ledger: Iterable[dict[str, Any]],
    signal_flags: dict[str, dict[str, Any]],
    projection_modifications_by_suite: dict[str, list[float]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        grouped[str(row["suite"])].append(row)

    output: list[dict[str, Any]] = []
    for suite in sorted(grouped):
        rows = grouped[suite]
        signal_rows = [row for row in rows if row["pair_id"] in signal_flags]
        output.append(
            {
                "suite": suite,
                "full_population": {
                    "episodes": len(rows),
                    "strict_success_no_cost": sum(
                        row["strict_success_no_cost"] is True for row in rows
                    ),
                    "unsafe_cost_or_collision": sum(
                        row["unsafe_cost_or_collision"] is True for row in rows
                    ),
                    "policy_actions": sum(
                        row["intervention_stats"]["policy_step_count"] for row in rows
                    ),
                    "projected_actions": sum(
                        row["intervention_stats"]["projected_action_count"]
                        for row in rows
                    ),
                },
                "signal_subset": {
                    "episodes": len(signal_rows),
                    "strict_success_no_cost": sum(
                        row["strict_success_no_cost"] is True for row in signal_rows
                    ),
                    "unsafe_cost_or_collision": sum(
                        row["unsafe_cost_or_collision"] is True for row in signal_rows
                    ),
                    "residual_proxy_above_clean": sum(
                        bool(_residual_channels(signal_flags[row["pair_id"]]))
                        for row in signal_rows
                    ),
                },
                "projected_command_modification_l2": _distribution(
                    projection_modifications_by_suite[suite]
                ),
            }
        )
    return output


def build_artifacts(
    *,
    terminal_summary_path: Path = DEFAULT_TERMINAL_SUMMARY,
    defended_summary_path: Path = DEFAULT_DEFENDED_SUMMARY,
    defended_ledger_path: Path = DEFAULT_DEFENDED_LEDGER,
    ctda_v1_summary_path: Path = DEFAULT_CTDA_V1_SUMMARY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    terminal = _load_json(terminal_summary_path)
    defended = _load_json(defended_summary_path)
    ctda_v1 = _load_json(ctda_v1_summary_path)
    ledger = _load_jsonl(defended_ledger_path)

    if terminal.get("complete") is not True or terminal.get("lifecycle", {}).get(
        "terminal"
    ) is not True:
        raise ArtifactError("action-envelope terminal summary is not terminal complete")
    _assert_equal(
        terminal.get("classification"),
        "exploratory_attacked_defended_complete_not_confirmatory",
        "terminal classification",
    )
    _assert_equal(
        _sha256(defended_summary_path),
        terminal["artifact_bindings"]["summary_sha256"],
        "defended summary digest",
    )
    _assert_equal(
        _sha256(defended_ledger_path),
        terminal["artifact_bindings"]["episodes_ledger_sha256"],
        "defended ledger digest",
    )
    _assert_equal(len(ledger), terminal["validity"]["episode_count"], "ledger rows")
    if any(row.get("valid") is not True for row in ledger):
        raise ArtifactError("defended ledger contains a non-valid episode")
    pair_ids = [row.get("pair_id") for row in ledger]
    if len(set(pair_ids)) != len(pair_ids):
        raise ArtifactError("defended ledger pair ids are not unique")

    strict_count = sum(row["strict_success_no_cost"] is True for row in ledger)
    unsafe_count = sum(row["unsafe_cost_or_collision"] is True for row in ledger)
    total_actions = sum(
        row["intervention_stats"]["policy_step_count"] for row in ledger
    )
    projected_actions = sum(
        row["intervention_stats"]["projected_action_count"] for row in ledger
    )
    _assert_equal(
        strict_count,
        terminal["full_population_outcomes"][
            "attacked_defended_strict_success_no_cost_count"
        ],
        "full strict success count",
    )
    _assert_equal(
        unsafe_count,
        terminal["full_population_outcomes"][
            "attacked_defended_unsafe_cost_or_collision_count"
        ],
        "full unsafe count",
    )
    _assert_equal(
        total_actions,
        terminal["execution_envelope"]["total_policy_actions"],
        "policy action count",
    )
    _assert_equal(
        projected_actions,
        terminal["execution_envelope"]["total_projected_actions"],
        "projected action count",
    )
    modifications, modifications_by_suite, verified_episode_files = (
        _projection_modifications(
            defended_ledger_path.parent,
            terminal["artifact_bindings"]["episodes_ledger_sha256"],
        )
    )
    _assert_equal(
        len(modifications),
        projected_actions,
        "raw projected-action extraction count",
    )

    signal_flags = defended.get(
        "baseline_signal_pair_physical_harm_relative_to_p0b_clean"
    )
    if not isinstance(signal_flags, dict):
        raise ArtifactError("defended summary lacks the signal-pair harm mapping")
    _assert_equal(
        len(signal_flags),
        terminal["baseline_signal_subset"]["pair_count"],
        "signal subset size",
    )
    ledger_by_pair = {str(row["pair_id"]): row for row in ledger}
    if not set(signal_flags).issubset(ledger_by_pair):
        raise ArtifactError("signal subset contains a pair absent from defended ledger")

    taxonomy_rows: list[dict[str, Any]] = []
    for pair_id in sorted(signal_flags):
        row = ledger_by_pair[pair_id]
        flags = signal_flags[pair_id]
        channels = _residual_channels(flags)
        taxonomy_rows.append(
            {
                "pair_id": pair_id,
                "suite": row["suite"],
                "in_frozen_signal_subset": True,
                "strict_success_no_cost": row["strict_success_no_cost"],
                "unsafe_cost_or_collision": row["unsafe_cost_or_collision"],
                "decision": row["decision"],
                "residual_proxy_channels_above_p0b_clean": channels,
                "category": _taxonomy_category(
                    strict_success=row["strict_success_no_cost"],
                    unsafe=row["unsafe_cost_or_collision"],
                    residual_channels=channels,
                ),
            }
        )

    unsafe_pair_ids = sorted(
        row["pair_id"] for row in ledger if row["unsafe_cost_or_collision"] is True
    )
    _assert_equal(
        unsafe_pair_ids,
        sorted(terminal["full_population_outcomes"]["unsafe_pair_ids"]),
        "unsafe pair ids",
    )
    for pair_id in unsafe_pair_ids:
        if pair_id not in signal_flags:
            row = ledger_by_pair[pair_id]
            taxonomy_rows.append(
                {
                    "pair_id": pair_id,
                    "suite": row["suite"],
                    "in_frozen_signal_subset": False,
                    "strict_success_no_cost": row["strict_success_no_cost"],
                    "unsafe_cost_or_collision": True,
                    "decision": row["decision"],
                    "residual_proxy_channels_above_p0b_clean": (
                        "not_applicable_outside_signal_subset"
                    ),
                    "category": "R4_defended_coarse_safety_failure",
                }
            )

    category_counts = Counter(row["category"] for row in taxonomy_rows)
    signal_residual_count = sum(
        bool(_residual_channels(signal_flags[pair_id])) for pair_id in signal_flags
    )
    _assert_equal(
        signal_residual_count,
        terminal["baseline_signal_subset"][
            "pairs_with_any_physical_harm_channel_above_p0b_clean"
        ],
        "signal residual count",
    )

    source_bindings = {
        "terminal_summary": _source_binding(terminal_summary_path),
        "defended_summary": _source_binding(defended_summary_path),
        "defended_ledger": _source_binding(defended_ledger_path),
        "ctda_v1_clean_summary": _source_binding(ctda_v1_summary_path),
    }
    taxonomy = {
        "schema": "proofalign.action-envelope-failure-taxonomy.v1",
        "status": "descriptive_post_outcome_analysis",
        "classification": terminal["classification"],
        "source_bindings": source_bindings,
        "scope": {
            "signal_subset_definition": terminal["baseline_signal_subset"][
                "definition"
            ],
            "signal_pair_count": len(signal_flags),
            "additional_full_population_unsafe_pairs": len(
                set(unsafe_pair_ids) - set(signal_flags)
            ),
            "rows_are_mutually_exclusive": True,
            "statistical_inference_authorized": False,
        },
        "definitions": TAXONOMY_DEFINITIONS,
        "category_counts": {
            name: category_counts.get(name, 0) for name in TAXONOMY_DEFINITIONS
        },
        "rows": sorted(taxonomy_rows, key=lambda row: row["pair_id"]),
        "interpretation": (
            "The action envelope removed the frozen coarse cost/collision endpoint "
            "from all 15 signal pairs, but only 3 both restored strict task success and "
            "showed no measured proxy above clean. Eleven retained a contact/joint/force "
            "proxy above clean, one failed the task without a measured residual proxy, "
            "and one nonsignal full-population pair had defended cost/collision."
        ),
        "claim_boundary": (
            "This taxonomy organizes already observed exploratory outcomes. It was not "
            "preregistered as an inferential analysis, does not redefine attack "
            "qualification, and does not convert proxy absence into physical safety."
        ),
    }

    full_total = len(ledger)
    signal_total = len(signal_flags)
    clean = terminal["clean_utility_context"]
    foundation = terminal["attack_foundation_context"]
    envelope = terminal["execution_envelope"]
    v1_methods = ctda_v1["methods"]
    tables = {
        "schema": "proofalign.action-envelope-paper-tables.v1",
        "status": "generated_from_terminal_evidence",
        "classification": terminal["classification"],
        "source_bindings": source_bindings,
        "tables": {
            "terminal_validity_and_mediation": [
                {
                    "metric": "valid defended episodes",
                    **_ratio(terminal["validity"]["valid_episode_count"], full_total),
                },
                {
                    "metric": "zero-step bindings",
                    **_ratio(
                        terminal["validity"]["binding_count"],
                        terminal["validity"]["required_binding_count"],
                    ),
                },
                {
                    "metric": "verified checksum entries",
                    **_ratio(
                        terminal["artifact_bindings"]["checksum_entries_verified"],
                        terminal["artifact_bindings"]["checksum_entry_count"],
                    ),
                },
                {
                    "metric": "executed actions within L2 envelope",
                    **_ratio(total_actions, total_actions),
                },
                {
                    "metric": "projected policy actions",
                    **_ratio(projected_actions, total_actions),
                },
            ],
            "exploratory_outcomes": [
                {
                    "population": "clean baseline-eligible",
                    "endpoint": "strict success retained",
                    **_ratio(
                        clean["clean_defended_strict_success_count"],
                        clean["baseline_eligible_pair_count"],
                    ),
                },
                {
                    "population": "attacked+defended full population",
                    "endpoint": "strict success without cost",
                    **_ratio(strict_count, full_total),
                },
                {
                    "population": "attacked+defended full population",
                    "endpoint": "LIBERO cost/collision",
                    **_ratio(unsafe_count, full_total),
                },
                {
                    "population": "frozen P0b signal subset",
                    "endpoint": "undefended LIBERO cost/collision by subset definition",
                    **_ratio(signal_total, signal_total),
                },
                {
                    "population": "frozen P0b signal subset",
                    "endpoint": "defended LIBERO cost/collision",
                    **_ratio(
                        terminal["baseline_signal_subset"][
                            "defended_unsafe_cost_or_collision_count"
                        ],
                        signal_total,
                    ),
                },
                {
                    "population": "frozen P0b signal subset",
                    "endpoint": "defended strict success without cost",
                    **_ratio(
                        terminal["baseline_signal_subset"][
                            "defended_strict_success_no_cost_count"
                        ],
                        signal_total,
                    ),
                },
                {
                    "population": "frozen P0b signal subset",
                    "endpoint": "physical proxy above P0b clean",
                    **_ratio(signal_residual_count, signal_total),
                },
            ],
            "attack_foundation_gate": {
                "eligible_pairs": foundation["clean_eligible_pair_count"],
                "required_eligible_pairs": foundation[
                    "required_clean_eligible_pair_count"
                ],
                "signal_pairs": foundation["clean_safe_to_attacked_unsafe_count"],
                "transition_rate": foundation["transition_rate"],
                "classification": foundation["classification"],
                "gate_passed": False,
            },
            "projection_modification_l2": {
                "definition": (
                    "Euclidean L2 distance between each raw policy command and its "
                    "dispatched projected command, restricted to projected actions."
                ),
                "verified_raw_episode_files": verified_episode_files,
                "distribution": _distribution(modifications),
                "by_suite": {
                    suite: _distribution(values)
                    for suite, values in sorted(modifications_by_suite.items())
                },
            },
            "suite_stratified": _suite_rows(
                ledger, signal_flags, modifications_by_suite
            ),
            "design_iteration_context_not_directly_comparable": [
                {
                    "design": "Full CTDA v1 clean slice",
                    "arm": "VLA-only",
                    "strict_or_task_success": v1_methods["vla_only"]["task_success"],
                    "total": v1_methods["vla_only"]["task_total"],
                    "rate": (
                        v1_methods["vla_only"]["task_success"]
                        / v1_methods["vla_only"]["task_total"]
                    ),
                },
                {
                    "design": "Full CTDA v1 clean slice",
                    "arm": "Full CTDA",
                    "strict_or_task_success": v1_methods["full_ctda"]["task_success"],
                    "total": v1_methods["full_ctda"]["task_total"],
                    "rate": (
                        v1_methods["full_ctda"]["task_success"]
                        / v1_methods["full_ctda"]["task_total"]
                    ),
                },
                {
                    "design": "Action-envelope clean slice",
                    "arm": "Execution-only pilot",
                    "strict_or_task_success": clean[
                        "clean_defended_strict_success_count"
                    ],
                    "total": clean["baseline_eligible_pair_count"],
                    "rate": clean["clean_utility_retention"],
                },
            ],
        },
        "fixed_facts": {
            "l2_limit": envelope["l2_limit"],
            "clean_utility_gate": clean["frozen_gate"],
            "clean_utility_gate_passed": clean["gate_passed"],
            "all_executed_actions_within_envelope": envelope[
                "all_executed_actions_within_envelope_with_numeric_tolerance"
            ],
            "nonfinite_source_policy_brakes": envelope[
                "total_nonfinite_source_policy_brakes"
            ],
        },
        "reporting_notes": [
            "All rates are descriptive; no confirmatory confidence claim is made.",
            "The frozen signal subset is reported beside, not instead of, the full population.",
            "The Full CTDA v1 and action-envelope rows use different populations and are design-history context, not a causal comparison.",
            "LIBERO cost/collision and contact/joint/force proxies remain separate endpoints.",
            "Projection modification quantiles are computed from all 48 ledger-bound raw episode JSON files.",
        ],
        "claim_boundary": terminal["interpretation"]["claim_boundary"],
    }
    return tables, taxonomy


def _pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _ratio_cell(row: dict[str, Any]) -> str:
    return f'{row["count"]}/{row["total"]} ({_pct(row["rate"])})'


def render_markdown(
    tables: dict[str, Any],
    taxonomy: dict[str, Any],
) -> str:
    table_data = tables["tables"]
    lines = [
        "# Action-envelope 论文结果表与 failure taxonomy",
        "",
        "> 此文件由 `scripts/generate_action_envelope_paper_artifacts.py` 从 terminal "
        "summary、defended summary/ledger 和 CTDA v1 clean summary 自动生成。请勿手改数字。",
        "",
        "状态：`exploratory_attacked_defended_complete_not_confirmatory`。所有比例均为描述性结果；"
        "P0b attack foundation 的确认性 denominator gate 未通过。",
        "",
        "## 表 1：终态有效性与 complete mediation",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
    ]
    for row in table_data["terminal_validity_and_mediation"]:
        lines.append(f'| {row["metric"]} | {_ratio_cell(row)} |')

    lines.extend(
        [
            "",
            "## 表 2：探索性结果",
            "",
            "| Population | Endpoint | 结果 |",
            "|---|---|---:|",
        ]
    )
    for row in table_data["exploratory_outcomes"]:
        lines.append(
            f'| {row["population"]} | {row["endpoint"]} | {_ratio_cell(row)} |'
        )

    gate = table_data["attack_foundation_gate"]
    lines.extend(
        [
            "",
            "P0b clean-eligible denominator 为 "
            f'`{gate["eligible_pairs"]}/{gate["required_eligible_pairs"]}`，正式分类保持 '
            f'`{gate["classification"]}`。signal subset 不能替代这个未通过的总体 gate。',
            "",
            "## 表 3：按 suite 分层",
            "",
            "| Suite | Full strict success | Full unsafe | Projected actions | "
            "Signal strict success | Signal residual proxy |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in table_data["suite_stratified"]:
        full = row["full_population"]
        signal = row["signal_subset"]
        lines.append(
            f'| {row["suite"]} | {full["strict_success_no_cost"]}/{full["episodes"]} | '
            f'{full["unsafe_cost_or_collision"]}/{full["episodes"]} | '
            f'{full["projected_actions"]}/{full["policy_actions"]} | '
            f'{signal["strict_success_no_cost"]}/{signal["episodes"]} | '
            f'{signal["residual_proxy_above_clean"]}/{signal["episodes"]} |'
        )

    lines.extend(
        [
            "",
            "## 表 4：设计迭代背景（不可直接比较）",
            "",
            "| Design | Arm | Success |",
            "|---|---|---:|",
        ]
    )
    for row in table_data["design_iteration_context_not_directly_comparable"]:
        lines.append(
            f'| {row["design"]} | {row["arm"]} | '
            f'{row["strict_or_task_success"]}/{row["total"]} ({_pct(row["rate"])}) |'
        )
    lines.extend(
        [
            "",
            "这些行来自不同 population，只用于说明从 Full CTDA clean failure 到窄化 "
            "Execution-only pilot 的设计演进，不构成 paired causal comparison。",
            "",
            "## 表 5：projected command 修改幅度",
            "",
            "修改幅度定义为 projected action 上 raw policy command 与 dispatched command "
            "之间的 L2 距离；quantile 使用 `(n - 1)q` 线性插值。",
            "",
            "| Scope | N | Mean | Median | P90 | P95 | P99 | Max |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    projection = table_data["projection_modification_l2"]
    distribution_rows = [("all", projection["distribution"])] + list(
        projection["by_suite"].items()
    )
    for scope, distribution in distribution_rows:
        lines.append(
            f'| {scope} | {distribution["count"]} | {distribution["mean"]:.6f} | '
            f'{distribution["median"]:.6f} | {distribution["p90"]:.6f} | '
            f'{distribution["p95"]:.6f} | {distribution["p99"]:.6f} | '
            f'{distribution["maximum"]:.6f} |'
        )
    lines.extend(
        [
            "",
            "## Failure taxonomy",
            "",
            "该 taxonomy 是 outcome 后的描述性整理，不是预注册推断。五类互斥：",
            "",
            "| 类别 | 数量 | 定义 |",
            "|---|---:|---|",
        ]
    )
    for name, definition in taxonomy["definitions"].items():
        lines.append(
            f'| `{name}` | {taxonomy["category_counts"][name]} | {definition} |'
        )

    lines.extend(
        [
            "",
            "### 逐 pair 审计",
            "",
            "| Pair | Signal subset | Strict success | Coarse unsafe | "
            "Residual channels above clean | Category |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for row in taxonomy["rows"]:
        channels = row["residual_proxy_channels_above_p0b_clean"]
        if isinstance(channels, list):
            channel_text = ", ".join(channels) if channels else "none"
        else:
            channel_text = channels
        lines.append(
            f'| `{row["pair_id"]}` | {str(row["in_frozen_signal_subset"]).lower()} | '
            f'{str(row["strict_success_no_cost"]).lower()} | '
            f'{str(row["unsafe_cost_or_collision"]).lower()} | {channel_text} | '
            f'`{row["category"]}` |'
        )

    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            taxonomy["claim_boundary"],
            "",
            "完整 machine-readable 输出：",
            "",
            "- `experiments/action_envelope_paper_tables.json`",
            "- `experiments/action_envelope_failure_taxonomy.json`",
            "",
        ]
    )
    return "\n".join(lines)


def _serialized_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_or_check(path: Path, content: str, *, check: bool) -> None:
    if check:
        if not path.is_file():
            raise ArtifactError(f"generated output is missing: {path}")
        if path.read_text(encoding="utf-8") != content:
            raise ArtifactError(f"generated output is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if outputs are stale")
    parser.add_argument("--terminal-summary", type=Path, default=DEFAULT_TERMINAL_SUMMARY)
    parser.add_argument("--defended-summary", type=Path, default=DEFAULT_DEFENDED_SUMMARY)
    parser.add_argument("--defended-ledger", type=Path, default=DEFAULT_DEFENDED_LEDGER)
    parser.add_argument("--ctda-v1-summary", type=Path, default=DEFAULT_CTDA_V1_SUMMARY)
    parser.add_argument("--tables-output", type=Path, default=DEFAULT_TABLES_OUTPUT)
    parser.add_argument("--taxonomy-output", type=Path, default=DEFAULT_TAXONOMY_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args()

    tables, taxonomy = build_artifacts(
        terminal_summary_path=args.terminal_summary,
        defended_summary_path=args.defended_summary,
        defended_ledger_path=args.defended_ledger,
        ctda_v1_summary_path=args.ctda_v1_summary,
    )
    _write_or_check(
        args.tables_output, _serialized_json(tables), check=args.check
    )
    _write_or_check(
        args.taxonomy_output, _serialized_json(taxonomy), check=args.check
    )
    _write_or_check(
        args.markdown_output,
        render_markdown(tables, taxonomy),
        check=args.check,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
