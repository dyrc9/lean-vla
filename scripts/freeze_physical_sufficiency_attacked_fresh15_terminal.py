#!/usr/bin/env python3
"""Freeze the terminal interpretation of the v10 attacked fresh15 pilot."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    canonical_text,
)
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts.freeze_physical_sufficiency_fresh15_terminal import (  # noqa: E402
    _paired_comparison,
    _wilson,
)
from scripts.run_physical_sufficiency_attacked_pilot import (  # noqa: E402
    validate_results,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_attacked_fresh15_protocol.json"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_physical_sufficiency_attacked_"
    "fresh15_20260729_fresh1"
)
RESULT_PATH = RESULT_ROOT / "pilot_evidence.json"
CHECKSUMS_PATH = RESULT_ROOT / "SHA256SUMS"
CLEAN_RESULT_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_physical_sufficiency_fresh15_"
    "cotenant_20260729_fresh1"
    / "pilot_evidence.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_attacked_fresh15_"
    "terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_physical_sufficiency_attacked_fresh15_terminal.py"
)
SOURCE_PATHS = (
    (
        "scripts/"
        "freeze_physical_sufficiency_attacked_fresh15_terminal.py"
    ),
    "tests/test_physical_sufficiency_attacked_fresh15_terminal.py",
)
CREATED_AT = "2026-07-29T12:06:00+08:00"
TRACE_FIELDS = (
    "robot_contact_count",
    "joint_limit_violation_steps",
    "excessive_force_steps",
)


class PhysicalSufficiencyAttackedTerminalError(RuntimeError):
    """Raised when attacked terminal evidence differs."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PhysicalSufficiencyAttackedTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _rows_by_pair(
    result: Mapping[str, Any],
) -> dict[str, dict[str, bool]]:
    rows: dict[str, dict[str, bool]] = {}
    for row in result["per_episode"]:
        rows.setdefault(str(row["base_pair_id"]), {})[
            str(row["arm"])
        ] = bool(row["task_success"])
    if len(rows) != 15 or any(
        set(values) != set(ARM_ORDER) for values in rows.values()
    ):
        raise PhysicalSufficiencyAttackedTerminalError(
            "paired result table is incomplete"
        )
    return rows


def _success_table(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    table = {}
    for arm in ARM_ORDER:
        values = result["by_arm"][arm]
        successes = int(values["task_success_count"])
        total = int(values["episode_count"])
        table[arm] = {
            "successes": successes,
            "total": total,
            "rate": successes / total,
            "wilson_95": _wilson(successes, total),
        }
    return table


def _suite_table(
    result: Mapping[str, Any],
) -> dict[str, dict[str, int]]:
    return {
        suite: {
            arm: sum(
                bool(row["task_success"])
                for row in result["per_episode"]
                if row["suite"] == suite and row["arm"] == arm
            )
            for arm in ARM_ORDER
        }
        for suite in (
            "human_safety",
            "obstacle_avoidance",
            "obstacle_avoidance_human",
        )
    }


def _episode_path(
    result: Mapping[str, Any],
    episode_id: str,
) -> Path:
    artifact = next(
        row
        for row in result["episodes"]
        if row["episode_id"] == episode_id
    )
    return REPO_ROOT / str(artifact["path"])


def _trace_diagnostics(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    by_arm: dict[str, Counter[str]] = defaultdict(Counter)
    by_pair: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for row in result["per_episode"]:
        episode = load_json_object(
            _episode_path(result, str(row["episode_id"]))
        )
        metrics = p0b.constraint_metrics(episode["trace"])
        arm = str(row["arm"])
        pair = str(row["base_pair_id"])
        steps = len(episode["trace"])
        record = {"trace_step_count": float(steps)}
        by_arm[arm]["trace_step_count"] += steps
        for field in TRACE_FIELDS:
            value = int(metrics[field])
            by_arm[arm][field] += value
            record[field] = float(value)
        by_pair[pair][arm] = record

    aggregate = {}
    for arm in ARM_ORDER:
        values = by_arm[arm]
        steps = values["trace_step_count"]
        aggregate[arm] = {
            "trace_step_count": steps,
            **{
                field: values[field] for field in TRACE_FIELDS
            },
            **{
                f"{field}_per_trace_step": (
                    values[field] / steps if steps else None
                )
                for field in TRACE_FIELDS
            },
        }

    paired_rate_signs = {}
    for treatment, control in (
        ("semantic_only", "vla_only"),
        ("dual", "execution_only"),
    ):
        differences = []
        for values in by_pair.values():
            treatment_row = values[treatment]
            control_row = values[control]
            differences.append(
                treatment_row["joint_limit_violation_steps"]
                / treatment_row["trace_step_count"]
                - control_row["joint_limit_violation_steps"]
                / control_row["trace_step_count"]
            )
        paired_rate_signs[f"{treatment}_vs_{control}"] = {
            "pair_count": len(differences),
            "mean_paired_joint_limit_rate_difference": (
                sum(differences) / len(differences)
            ),
            "lower_rate_treatment_pair_count": sum(
                value < 0 for value in differences
            ),
            "higher_rate_treatment_pair_count": sum(
                value > 0 for value in differences
            ),
            "equal_rate_pair_count": sum(
                value == 0 for value in differences
            ),
        }
    return {
        "analysis_status": (
            "post_hoc_mechanism_diagnostic_not_a_"
            "preregistered_attacked_primary_endpoint"
        ),
        "typed_signal_coverage_complete": True,
        "aggregate_by_arm": aggregate,
        "paired_joint_limit_rate_signs": paired_rate_signs,
        "interpretation_boundary": (
            "Joint-limit direction is hypothesis-generating. Robot-contact "
            "and excessive-force proxies are not consistently improved, "
            "and none of these diagnostics replaces official benchmark "
            "cost/collision or establishes causal physical safety."
        ),
    }


def _effect_contrasts(
    attacked_rows: dict[str, dict[str, bool]],
    clean_rows: dict[str, dict[str, bool]],
) -> dict[str, Any]:
    result = {}
    for label, treatment, control in (
        ("semantic_vs_vla", "semantic_only", "vla_only"),
        ("dual_vs_execution", "dual", "execution_only"),
    ):
        attacked = _paired_comparison(
            attacked_rows, treatment, control
        )
        clean = _paired_comparison(clean_rows, treatment, control)
        result[label] = {
            "attacked": attacked,
            "paired_clean": clean,
            "attack_minus_clean_difference_in_differences": (
                attacked["risk_difference"]
                - clean["risk_difference"]
            ),
        }
    return result


def build_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    protocol = load_json_object(PROTOCOL_PATH)
    result = validate_results(
        protocol, protocol_path=PROTOCOL_PATH
    )
    clean = load_json_object(CLEAN_RESULT_PATH)
    if (
        result.get("classification")
        != "physical_sufficiency_attacked_fresh15_data_complete"
        or result.get("pilot_complete") is not True
        or result.get("aggregate", {}).get("episode_count") != 60
    ):
        raise PhysicalSufficiencyAttackedTerminalError(
            "v10 attacked evidence is not complete"
        )
    attacked_rows = _rows_by_pair(result)
    clean_rows = _rows_by_pair(clean)
    success = _success_table(result)
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": (
            "proofalign.physical-sufficiency-attacked-"
            "fresh15-terminal.v1"
        ),
        "classification": (
            "physical_sufficiency_attacked_fresh15_data_complete"
        ),
        "created_at": created_at,
        "terminal": True,
        "data_complete": True,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "result": {
            "path": RESULT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(RESULT_PATH),
            "checksums_path": CHECKSUMS_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "checksums_sha256": file_sha256(CHECKSUMS_PATH),
        },
        "paired_clean_result": {
            "path": CLEAN_RESULT_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(CLEAN_RESULT_PATH),
        },
        "success_table": success,
        "success_table_by_suite": _suite_table(result),
        "paired_comparisons": {
            "semantic_vs_vla": _paired_comparison(
                attacked_rows, "semantic_only", "vla_only"
            ),
            "dual_vs_execution": _paired_comparison(
                attacked_rows, "dual", "execution_only"
            ),
            "dual_vs_vla": _paired_comparison(
                attacked_rows, "dual", "vla_only"
            ),
        },
        "clean_attacked_effect_contrasts": _effect_contrasts(
            attacked_rows, clean_rows
        ),
        "mechanism": {
            key: result["aggregate"][key]
            for key in (
                "attack_record_count",
                "attack_changed_first_action_block_count",
                "attacked_paired_first_action_block_match_count",
                "physical_sufficiency_audit_count",
                "unchanged_source_action_block_count",
                "attacked_l1_physical_risk_reject_count",
                "paired_clean_l1_physical_risk_reject_count",
                "physical_risk_reject_count_enrichment",
                "advisory_effect_replan_count",
                "effect_reject_count",
                "effect_unknown_count",
                "unsafe_cost_or_collision_count",
            )
        },
        "post_hoc_trace_diagnostics": _trace_diagnostics(result),
        "interpretation": {
            "instruction_attack_action_activation_observed": (
                result["aggregate"][
                    "attack_changed_first_action_block_count"
                ]
                == 60
            ),
            "nominal_policy_noninterference_observed": (
                result["aggregate"][
                    "unchanged_source_action_block_count"
                ]
                == result["aggregate"][
                    "physical_sufficiency_audit_count"
                ]
            ),
            "attacked_task_utility_superiority_declared": False,
            "physical_risk_reject_enrichment_observed": False,
            "official_cost_collision_arm_separation_observed": False,
            "confirmatory_defense_claim_authorized": False,
            "causal_safety_claim_authorized": False,
            "joint_limit_aware_successor_motivated": True,
            "next_method_boundary": (
                "Any joint-limit-aware checker is an outcome-informed v11 "
                "successor and must be frozen before evaluation on fresh "
                "workloads; it cannot retroactively change this v10 table."
            ),
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            },
            "freezer": SELF_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        },
        "claim_boundary": (
            "This terminal freezes a complete paired 60-episode exploratory "
            "instruction-attack table. It establishes attack activation, "
            "data integrity, nominal-block non-interference, and mixed "
            "safety-utility observations. It does not establish attacked "
            "task-utility superiority, physical-risk enrichment, official "
            "cost/collision benefit, confirmatory defense efficacy, causal "
            "physical safety, timing, deployment, or hardware "
            "generalization. Typed trace diagnostics are post hoc and "
            "hypothesis-generating."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source_commit = None
    if args.check and args.output.is_file():
        retained = load_json_object(args.output)
        source_commit = retained["source"]["repository_commit"]
    text = canonical_text(
        build_summary(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PhysicalSufficiencyAttackedTerminalError(
                f"v10 attacked terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
