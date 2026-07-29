#!/usr/bin/env python3
"""Freeze the terminal analysis of the 45-task v8 four-arm experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import math
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
from scripts.freeze_contact_phase_pick_up_scale45_cotenant import (  # noqa: E402
    OUTPUT_PATH as PROTOCOL_PATH,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    validate_results,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_contact_phase_pick_up_scale45_terminal.py"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_contact_phase_pick_up_scale45_cotenant_"
    "20260729_fresh1"
)
EVIDENCE_PATH = RESULT_ROOT / "pilot_evidence.json"
CHECKSUMS_PATH = RESULT_ROOT / "SHA256SUMS"
SOURCE_PATHS = (
    "scripts/freeze_contact_phase_pick_up_scale45_terminal.py",
    "tests/test_contact_phase_pick_up_scale45_terminal.py",
)
CREATED_AT = "2026-07-29T11:00:00+08:00"


class ContactPhaseScale45TerminalError(RuntimeError):
    """Raised when the scale45 result cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseScale45TerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _episode_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    path = REPO_ROOT / str(artifact["path"])
    if not path.is_file() or file_sha256(path) != artifact["sha256"]:
        raise ContactPhaseScale45TerminalError(
            f"episode binding differs: {path}"
        )
    return load_json_object(path)


def _wilson(successes: int, episodes: int) -> dict[str, Any]:
    if episodes <= 0:
        return {
            "successes": successes,
            "episodes": episodes,
            "rate": None,
            "wilson_95_lower": None,
            "wilson_95_upper": None,
        }
    z = 1.959963984540054
    rate = successes / episodes
    denominator = 1 + z * z / episodes
    center = (rate + z * z / (2 * episodes)) / denominator
    half_width = (
        z
        * math.sqrt(
            rate * (1 - rate) / episodes
            + z * z / (4 * episodes * episodes)
        )
        / denominator
    )
    return {
        "successes": successes,
        "episodes": episodes,
        "rate": rate,
        "wilson_95_lower": max(0.0, center - half_width),
        "wilson_95_upper": min(1.0, center + half_width),
    }


def _success_tables(
    evidence: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, dict[str, Any]]],
]:
    overall = {
        arm: _wilson(
            int(evidence["by_arm"][arm]["task_success_count"]),
            int(evidence["by_arm"][arm]["episode_count"]),
        )
        for arm in ARM_ORDER
    }
    suites = sorted(
        {str(row["suite"]) for row in evidence["per_episode"]}
    )
    by_suite = {}
    for suite in suites:
        by_suite[suite] = {}
        for arm in ARM_ORDER:
            rows = [
                row
                for row in evidence["per_episode"]
                if row["suite"] == suite and row["arm"] == arm
            ]
            by_suite[suite][arm] = _wilson(
                sum(bool(row["task_success"]) for row in rows),
                len(rows),
            )
    return overall, by_suite


def _exact_two_sided_sign_p(wins: int, losses: int) -> float | None:
    discordant = wins + losses
    if discordant == 0:
        return None
    tail = min(wins, losses)
    probability = (
        2
        * sum(
            math.comb(discordant, index)
            for index in range(tail + 1)
        )
        / (2**discordant)
    )
    return min(1.0, probability)


def _paired_comparison(
    evidence: Mapping[str, Any],
    *,
    treatment: str,
    control: str,
) -> dict[str, Any]:
    rows = {
        (str(row["base_pair_id"]), str(row["arm"])): row
        for row in evidence["per_episode"]
    }
    pair_ids = sorted(
        {
            str(row["base_pair_id"])
            for row in evidence["per_episode"]
        }
    )
    treatment_wins = 0
    control_wins = 0
    both_success = 0
    both_fail = 0
    for pair_id in pair_ids:
        treatment_success = bool(
            rows[(pair_id, treatment)]["task_success"]
        )
        control_success = bool(
            rows[(pair_id, control)]["task_success"]
        )
        if treatment_success and not control_success:
            treatment_wins += 1
        elif control_success and not treatment_success:
            control_wins += 1
        elif treatment_success:
            both_success += 1
        else:
            both_fail += 1
    return {
        "treatment": treatment,
        "control": control,
        "paired_task_count": len(pair_ids),
        "treatment_only_success": treatment_wins,
        "control_only_success": control_wins,
        "both_success": both_success,
        "both_fail": both_fail,
        "discordant_pair_count": treatment_wins + control_wins,
        "exact_two_sided_sign_p": _exact_two_sided_sign_p(
            treatment_wins, control_wins
        ),
        "analysis_status": "descriptive_exploratory_not_preregistered",
    }


def _independent_risk_diagnostics(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    rows_by_id = {
        str(row["episode_id"]): row
        for row in evidence["per_episode"]
    }
    per_episode = []
    count_fields = (
        "signal_step_count",
        "robot_contact_step_count",
        "robot_contact_count_sum",
        "joint_limit_violation_steps",
        "excessive_force_steps",
        "raw_action_magnitude_violation_steps",
    )
    for artifact in evidence["episodes"]:
        row = rows_by_id[str(artifact["episode_id"])]
        episode = _episode_payload(artifact)
        signals = [
            trace_row["saber_constraint_signals"]
            for trace_row in episode["trace"]
            if isinstance(trace_row, Mapping)
            and isinstance(
                trace_row.get("saber_constraint_signals"),
                Mapping,
            )
        ]
        per_episode.append(
            {
                "episode_id": row["episode_id"],
                "suite": row["suite"],
                "arm": row["arm"],
                "task_success": row["task_success"],
                "signal_step_count": len(signals),
                "robot_contact_step_count": sum(
                    int(signal.get("robot_contact_count", 0)) > 0
                    for signal in signals
                ),
                "robot_contact_count_sum": sum(
                    int(signal.get("robot_contact_count", 0))
                    for signal in signals
                ),
                "maximum_robot_contact_count": max(
                    (
                        int(signal.get("robot_contact_count", 0))
                        for signal in signals
                    ),
                    default=0,
                ),
                "joint_limit_violation_steps": sum(
                    bool(signal.get("joint_limit_violation"))
                    for signal in signals
                ),
                "excessive_force_steps": sum(
                    bool(signal.get("excessive_force"))
                    for signal in signals
                ),
                "raw_action_magnitude_violation_steps": sum(
                    bool(
                        signal.get(
                            "raw_action_magnitude_violation"
                        )
                    )
                    for signal in signals
                ),
            }
        )

    def aggregate(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
        result = {
            field: sum(int(row[field]) for row in rows)
            for field in count_fields
        }
        signal_steps = result["signal_step_count"]
        result.update(
            {
                "episode_count": len(rows),
                "episodes_with_robot_contact": sum(
                    int(row["robot_contact_step_count"]) > 0
                    for row in rows
                ),
                "episodes_with_joint_limit_violation": sum(
                    int(row["joint_limit_violation_steps"]) > 0
                    for row in rows
                ),
                "episodes_with_excessive_force": sum(
                    int(row["excessive_force_steps"]) > 0
                    for row in rows
                ),
                "joint_limit_violation_step_rate": (
                    result["joint_limit_violation_steps"]
                    / signal_steps
                    if signal_steps
                    else None
                ),
                "excessive_force_step_rate": (
                    result["excessive_force_steps"] / signal_steps
                    if signal_steps
                    else None
                ),
            }
        )
        return result

    suites = sorted({str(row["suite"]) for row in per_episode})
    return {
        "per_episode": per_episode,
        "by_arm": {
            arm: aggregate(
                [row for row in per_episode if row["arm"] == arm]
            )
            for arm in ARM_ORDER
        },
        "by_suite": {
            suite: aggregate(
                [row for row in per_episode if row["suite"] == suite]
            )
            for suite in suites
        },
        "aggregate": aggregate(per_episode),
        "interpretation": (
            "Independent per-step SABER signals are diagnostics, not the "
            "benchmark unsafe_cost_or_collision endpoint. Robot contacts "
            "include ordinary task contact. Exposure differs with episode "
            "length, so raw counts and rates are not causal safety effects."
        ),
    }


def _failure_diagnostics(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    failed = [
        row for row in evidence["per_episode"]
        if not row["task_success"]
    ]
    semantic_failed = [
        row for row in failed
        if row["arm"] in ("semantic_only", "dual")
    ]
    return {
        "all_failed_episode_count": len(failed),
        "all_failure_decision_counts": dict(
            sorted(Counter(row["decision"] for row in failed).items())
        ),
        "semantic_failed_episode_count": len(semantic_failed),
        "semantic_failure_decision_counts": dict(
            sorted(
                Counter(
                    row["decision"] for row in semantic_failed
                ).items()
            )
        ),
        "semantic_effect_issue_counts": dict(
            sorted(
                sum(
                    (
                        Counter(row["effect_issue_counts"])
                        for row in semantic_failed
                    ),
                    Counter(),
                ).items()
            )
        ),
        "semantic_projection_reason_counts": dict(
            sorted(
                sum(
                    (
                        Counter(row["projection_reason_counts"])
                        for row in semantic_failed
                    ),
                    Counter(),
                ).items()
            )
        ),
    }


def build_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ContactPhaseScale45TerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    if (
        int(evidence.get("aggregate", {}).get("episode_count", -1))
        != 180
        or len(evidence.get("per_episode", [])) != 180
        or len(evidence.get("episodes", [])) != 180
        or int(
            evidence["aggregate"].get(
                "runtime_exception_count", -1
            )
        )
        != 0
        or int(
            evidence["aggregate"].get(
                "metadata_mismatch_count", -1
            )
        )
        != 0
        or any(
            int(evidence["by_arm"][arm]["episode_count"]) != 45
            for arm in ARM_ORDER
        )
    ):
        raise ContactPhaseScale45TerminalError(
            "validated scale45 evidence is not data-complete"
        )
    overall, by_suite = _success_tables(evidence)
    risk = _independent_risk_diagnostics(evidence)
    comparisons = {
        "semantic_only_vs_vla_only": _paired_comparison(
            evidence,
            treatment="semantic_only",
            control="vla_only",
        ),
        "dual_vs_execution_only": _paired_comparison(
            evidence,
            treatment="dual",
            control="execution_only",
        ),
        "dual_vs_vla_only": _paired_comparison(
            evidence,
            treatment="dual",
            control="vla_only",
        ),
    }
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    aggregate = evidence["aggregate"]
    protocol_gate_pass = all(evidence["gate_results"].values())
    return {
        "schema": (
            "proofalign.contact-phase-pick-up-scale45-terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": (
            "contact_phase_pick_up_scale45_data_complete"
        ),
        "terminal": True,
        "data_complete": True,
        "protocol_gate_pass": protocol_gate_pass,
        "efficacy_pass_declared": False,
        "confirmatory_claim_authorized": False,
        "attacked_defense_evaluated": False,
        "co_tenant_resource_exception_active": True,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "result": {
            "root": RESULT_ROOT.relative_to(REPO_ROOT).as_posix(),
            "evidence_path": EVIDENCE_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "evidence_sha256": file_sha256(EVIDENCE_PATH),
            "checksums_path": CHECKSUMS_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "checksums_sha256": file_sha256(CHECKSUMS_PATH),
            "aggregate": aggregate,
            "gate_results": evidence["gate_results"],
            "by_arm": evidence["by_arm"],
        },
        "success_table": overall,
        "success_table_by_suite": by_suite,
        "paired_comparisons": comparisons,
        "diagnostics": {
            "failures": _failure_diagnostics(evidence),
            "independent_constraint_signals": risk,
        },
        "interpretation": {
            "primary": (
                "This table covers all 45 frozen tasks in the three "
                "selected suites with paired outcomes for all four arms. "
                "Success rates and intervals are descriptive exploratory "
                "estimates for the frozen clean implementation."
            ),
            "method_effect_boundary": (
                "Paired comparisons are post-pilot exploratory analyses. "
                "They quantify clean task utility but do not evaluate an "
                "execution attack or identify a defended-safety effect."
            ),
            "safety_boundary": (
                "Benchmark unsafe cost/collision, selected semantic hard "
                "violations, and independent SABER diagnostics are "
                "reported separately. None alone supports a deployment or "
                "hardware-safety claim."
            ),
            "resource_boundary": (
                "The schedule ran with pre-existing idle GPU allocations. "
                "Task outcomes remain usable as exploratory evidence, but "
                "no timing, throughput, or exclusive-resource comparison "
                "is authorized."
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
            "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        },
        "claim_boundary": (
            "This terminal freezes a complete 180-episode clean "
            "exploratory table with 45 paired tasks per arm. It does not "
            "declare efficacy, evaluate attacked defense, authorize a "
            "confirmatory claim, support a timing comparison, or "
            "generalize to deployment or hardware safety."
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
        source_commit = retained.get("source", {}).get(
            "repository_commit"
        )
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
            raise ContactPhaseScale45TerminalError(
                f"scale45 terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
