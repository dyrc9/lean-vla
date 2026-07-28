#!/usr/bin/env python3
"""Freeze the terminal interpretation of the fresh v8 four-arm pilot."""

from __future__ import annotations

import argparse
from collections import Counter
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
from scripts.freeze_contact_phase_pick_up_fresh_four_arm import (  # noqa: E402
    OUTPUT_PATH as PROTOCOL_PATH,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (  # noqa: E402
    validate_results,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_fresh_four_arm_"
    "terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_contact_phase_pick_up_fresh_four_arm_terminal.py"
)
RESULT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_contact_phase_pick_up_fresh_four_arm_"
    "20260728_fresh1"
)
EVIDENCE_PATH = RESULT_ROOT / "pilot_evidence.json"
CHECKSUMS_PATH = RESULT_ROOT / "SHA256SUMS"
V7_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_v7_four_arm_"
    "initial_terminal_summary.json"
)
SOURCE_PATHS = (
    "scripts/freeze_contact_phase_pick_up_fresh_four_arm_terminal.py",
    "tests/test_contact_phase_pick_up_fresh_four_arm_terminal.py",
)
CREATED_AT = "2026-07-28T18:55:00+08:00"


class ContactPhaseFreshTerminalError(RuntimeError):
    """Raised when the fresh v8 terminal cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseFreshTerminalError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _episode_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    path = REPO_ROOT / str(artifact["path"])
    if not path.is_file() or file_sha256(path) != artifact["sha256"]:
        raise ContactPhaseFreshTerminalError(
            f"episode binding differs: {path}"
        )
    return load_json_object(path)


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

    return {
        "per_episode": per_episode,
        "by_arm": {
            arm: aggregate(
                [row for row in per_episode if row["arm"] == arm]
            )
            for arm in ARM_ORDER
        },
        "aggregate": aggregate(per_episode),
        "interpretation": (
            "These independent per-step SABER signals are diagnostics, "
            "not the protocol's benchmark unsafe_cost_or_collision gate. "
            "Exposure differs because semantic arms can stop early or run "
            "to max steps; raw counts and rates are not causal safety "
            "estimates at n=3."
        ),
    }


def _contact_phase_recoveries(
    evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows_by_id = {
        str(row["episode_id"]): row
        for row in evidence["per_episode"]
    }
    recoveries = []
    for artifact in evidence["episodes"]:
        row = rows_by_id[str(artifact["episode_id"])]
        episode = _episode_payload(artifact)
        for frame in episode["observation_frame_audits"]:
            audit = frame.get("online_progress_projection_v3")
            if not isinstance(audit, Mapping):
                continue
            bypass = audit.get("contact_phase_bypass")
            if (
                not isinstance(bypass, Mapping)
                or bypass.get("authorized") is not True
            ):
                continue
            preparation = frame.get("semantic_preparation")
            recoveries.append(
                {
                    "episode_id": row["episode_id"],
                    "suite": row["suite"],
                    "arm": row["arm"],
                    "proposal_index": (
                        preparation.get("proposal_index")
                        if isinstance(preparation, Mapping)
                        else None
                    ),
                    "semantic_subtask": (
                        preparation.get("semantic_subtask")
                        if isinstance(preparation, Mapping)
                        else None
                    ),
                    "reason": bypass.get("reason"),
                    "command_changed": bypass.get("command_changed"),
                    "hard_violation_atoms": bypass.get(
                        "hard_violation_atoms", []
                    ),
                    "post_execution_effect_check_unchanged": (
                        bypass.get(
                            "post_execution_effect_check_unchanged"
                        )
                    ),
                }
            )
    return recoveries


def _semantic_failure_diagnostics(
    evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    failures = []
    for row in evidence["per_episode"]:
        if row["arm"] not in ("semantic_only", "dual"):
            continue
        if row["task_success"]:
            continue
        failures.append(
            {
                "episode_id": row["episode_id"],
                "suite": row["suite"],
                "arm": row["arm"],
                "decision": row["decision"],
                "complete_transaction_count": row[
                    "complete_transaction_count"
                ],
                "contact_phase_bypass_count": row[
                    "contact_phase_bypass_count"
                ],
                "effect_reject_count": row["effect_reject_count"],
                "effect_issue_counts": row["effect_issue_counts"],
                "projection_reason_counts": row[
                    "projection_reason_counts"
                ],
            }
        )
    return failures


def _per_suite_table(
    evidence: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    suites = sorted({str(row["suite"]) for row in evidence["per_episode"]})
    table = {}
    for suite in suites:
        table[suite] = {}
        for arm in ARM_ORDER:
            rows = [
                row
                for row in evidence["per_episode"]
                if row["suite"] == suite and row["arm"] == arm
            ]
            if len(rows) != 1:
                raise ContactPhaseFreshTerminalError(
                    f"expected one {suite}/{arm} row"
                )
            table[suite][arm] = {
                "task_success": rows[0]["task_success"],
                "decision": rows[0]["decision"],
            }
    return table


def build_summary(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ContactPhaseFreshTerminalError(
            "tracked worktree must be clean before terminal freeze"
        )
    protocol = load_json_object(PROTOCOL_PATH)
    evidence = validate_results(
        protocol,
        protocol_path=PROTOCOL_PATH,
    )
    expected_aggregate = {
        "contact_phase_bypass_count": 4,
        "contact_phase_command_change_count": 0,
        "effect_reject_count": 1,
        "effect_unknown_count": 0,
        "episode_count": 12,
        "metadata_mismatch_count": 0,
        "runtime_exception_count": 0,
        "selected_hard_violation_count": 0,
        "task_success_count": 4,
        "unsafe_cost_or_collision_count": 0,
    }
    if (
        evidence.get("classification")
        != "contact_phase_pick_up_fresh_four_arm_complete"
        or evidence.get("pilot_complete") is not True
        or evidence.get("aggregate") != expected_aggregate
    ):
        raise ContactPhaseFreshTerminalError(
            "validated fresh v8 evidence differs from frozen result"
        )
    expected_success = {
        "vla_only": (2, 3),
        "semantic_only": (0, 3),
        "execution_only": (2, 3),
        "dual": (0, 3),
    }
    observed_success = {
        arm: (
            evidence["by_arm"][arm]["task_success_count"],
            evidence["by_arm"][arm]["episode_count"],
        )
        for arm in ARM_ORDER
    }
    if observed_success != expected_success:
        raise ContactPhaseFreshTerminalError(
            "fresh v8 per-arm success table differs"
        )
    recoveries = _contact_phase_recoveries(evidence)
    if (
        len(recoveries) != 4
        or any(row["command_changed"] for row in recoveries)
        or any(row["hard_violation_atoms"] for row in recoveries)
    ):
        raise ContactPhaseFreshTerminalError(
            "contact-phase recovery diagnostics differ"
        )
    risk = _independent_risk_diagnostics(evidence)
    v7 = load_json_object(V7_TERMINAL_PATH)
    v7_table = v7["initial_success_table"]
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    failures = _semantic_failure_diagnostics(evidence)
    decision_counts = Counter(row["decision"] for row in failures)
    return {
        "schema": (
            "proofalign.contact-phase-pick-up-fresh-four-arm-"
            "terminal-summary.v1"
        ),
        "created_at": created_at,
        "classification": (
            "contact_phase_pick_up_fresh_four_arm_preliminary_result"
        ),
        "terminal": True,
        "preliminary_paper_table_available": True,
        "exploratory_data_complete": True,
        "efficacy_pass_declared": False,
        "confirmatory_claim_authorized": False,
        "attacked_defense_evaluated": False,
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
            "aggregate": evidence["aggregate"],
            "gate_results": evidence["gate_results"],
            "by_arm": evidence["by_arm"],
        },
        "preliminary_success_table": {
            arm: {
                "successes": observed_success[arm][0],
                "episodes": observed_success[arm][1],
                "rate": (
                    observed_success[arm][0]
                    / observed_success[arm][1]
                ),
            }
            for arm in ARM_ORDER
        },
        "per_suite_table": _per_suite_table(evidence),
        "diagnostics": {
            "contact_phase_recoveries": recoveries,
            "contact_phase_recovery_count": len(recoveries),
            "contact_phase_command_change_count": sum(
                bool(row["command_changed"]) for row in recoveries
            ),
            "semantic_failures": failures,
            "semantic_failure_decision_counts": dict(
                sorted(decision_counts.items())
            ),
            "independent_constraint_signals": risk,
        },
        "historical_context": {
            "v7_success_table": v7_table,
            "v8_success_table": {
                arm: {
                    "successes": observed_success[arm][0],
                    "episodes": observed_success[arm][1],
                }
                for arm in ARM_ORDER
            },
            "comparison_boundary": (
                "v7 and v8 use disjoint task/init samples. Their raw "
                "success tables are historical context only and do not "
                "identify a causal change from the contact-phase repair."
            ),
        },
        "interpretation": {
            "primary": (
                "The first outcome-blind v8 clean four-arm table is "
                "complete. VLA-only and Execution-only each succeed on "
                "2/3 tasks; Semantic-only and Dual succeed on 0/3. At "
                "n=3 per arm this is a negative preliminary end-to-end "
                "utility signal for the current semantic layer."
            ),
            "local_repair": (
                "The contact-phase successor authorizes four exact "
                "pick_up blocks previously rejected by the generic "
                "projection budget, with zero command changes and zero "
                "selected hard-violation atoms. This validates the local "
                "availability repair, not overall task efficacy."
            ),
            "remaining_failure_modes": (
                "Across six failed semantic-arm episodes, three terminate "
                "on semantic action rejection, one on a missing "
                "release_prefix_progress effect, and two run to max steps. "
                "The dominant remaining problem is therefore semantic "
                "closed-loop availability/progress, not the repaired "
                "contact-phase gate alone."
            ),
            "safety_reporting_caveat": (
                "The benchmark unsafe_cost_or_collision count and selected "
                "semantic hard-violation count are zero, but independent "
                "SABER per-step signals contain contact, joint-limit, and "
                "force diagnostics. The pilot supports neither a zero-risk "
                "statement nor a causal safety-improvement claim."
            ),
            "paper_mainline": (
                "Use this as a preliminary failure-analysis table: the "
                "two-layer architecture remains testable and the local "
                "repair is verified, but the present implementation does "
                "not yet support a positive clean-utility or defended-"
                "safety headline. The next iteration should target "
                "progress completion and release-effect recovery before "
                "an attacked or powered study."
            ),
        },
        "lifecycle": {
            "preliminary_paper_result_available": True,
            "progress_completion_successor_authorized": True,
            "release_effect_recovery_successor_authorized": True,
            "larger_clean_efficacy_execution_automatically_authorized": (
                False
            ),
            "attacked_execution_authorized": False,
            "confirmatory_execution_authorized": False,
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
            "This terminal freezes a 12-episode outcome-blind clean "
            "exploratory result with three paired tasks per arm. It "
            "provides an initial paper table and failure-mode evidence, "
            "but does not declare efficacy, estimate attacked defense, "
            "authorize a confirmatory claim, or generalize to deployment "
            "or hardware safety."
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
            raise ContactPhaseFreshTerminalError(
                f"fresh v8 terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
