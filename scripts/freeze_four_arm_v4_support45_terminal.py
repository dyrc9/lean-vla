#!/usr/bin/env python3
"""Freeze the terminal support45 clean result and its failure taxonomy."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
    read_ledger,
)
from scripts import run_saber_threat_validation_r5 as p0b_runner  # noqa: E402
from scripts.run_proofalign_four_arm_v4_support45_clean import (  # noqa: E402
    validate_results,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_support45_successor.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_support45_clean_terminal_summary.json"
)
LAUNCHER_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_four_arm_v4_support45_clean_launcher_20260727"
)
SEMANTIC_ARMS = ("semantic_only", "dual")
MIN_PROGRESS_M = 0.002


class Support45TerminalError(RuntimeError):
    """Raised when the terminal support45 summary cannot be frozen."""


def _counter_payload(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _arm_outcomes(
    rows: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    outcomes = {}
    for arm in ("vla_only", "semantic_only", "execution_only", "dual"):
        arm_rows = [row for row in rows if row["arm"] == arm]
        descriptive = analysis["arm_descriptives"][arm]
        outcomes[arm] = {
            "unit_count": len(arm_rows),
            "valid_count": sum(
                row["attempt_status"] == "valid" for row in arm_rows
            ),
            "task_success_count": sum(
                bool(row["task_success"]) for row in arm_rows
            ),
            "strict_success_no_cost_count": sum(
                bool(row["strict_success_no_cost"]) for row in arm_rows
            ),
            "phase_complete_count": sum(
                bool(row["phase_complete"]) for row in arm_rows
            ),
            "deadlock_count": sum(bool(row["deadlock"]) for row in arm_rows),
            "unknown_or_unbound_count": sum(
                bool(row["unknown_or_unbound"]) for row in arm_rows
            ),
            "unsafe_cost_or_collision_count": sum(
                bool(row["unsafe_cost_or_collision"]) for row in arm_rows
            ),
            "decision_counts": _counter_payload(
                [str(row["decision"]) for row in arm_rows]
            ),
            "strict_success_no_cost_rate": descriptive[
                "strict_success_no_cost_rate_conservative"
            ],
            "deadlock_rate": descriptive["deadlock_rate_conservative"],
            "unknown_or_unbound_rate": descriptive[
                "unknown_or_unbound_rate_conservative"
            ],
        }
    return outcomes


def _semantic_failure_taxonomy(
    rows: list[dict[str, Any]],
    *,
    output_root: Path,
) -> dict[str, Any]:
    reason_counts: dict[str, Counter[str]] = defaultdict(Counter)
    suite_decisions: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    unknown_pairs: set[str] = set()
    candidate_flags: dict[str, Counter[str]] = defaultdict(Counter)
    event_count_distributions: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        arm = str(row["arm"])
        if arm not in SEMANTIC_ARMS:
            continue
        artifact = load_json_object(output_root / row["episode_artifact_path"])
        events = artifact.get("semantic_events")
        if not isinstance(events, list) or not events:
            raise Support45TerminalError(
                f"semantic event history is absent: {row['episode_id']}"
            )
        terminal_event = events[-1]
        reason = str(terminal_event.get("reason"))
        reason_counts[arm][reason] += 1
        suite_decisions[arm][str(row["suite"])][str(row["decision"])] += 1
        event_count_distributions[arm][str(len(events))] += 1
        if reason == "missing_destination_geometry":
            unknown_pairs.add(str(row["base_pair_id"]))

        if row["decision"] != "semantic_action_rejected":
            continue
        audits = artifact.get("observation_frame_audits")
        if not isinstance(audits, list) or not audits:
            raise Support45TerminalError(
                f"semantic decision audit is absent: {row['episode_id']}"
            )
        candidate = audits[-1]["semantic_decision"]["checked_candidate"]
        flags = candidate_flags[arm]
        flags["candidate_count"] += 1
        flags["known_false"] += not bool(candidate["known"])
        flags["semantic_compatible_false"] += not bool(
            candidate["semantic_compatible"]
        )
        flags["post_projection_compatible_false"] += not bool(
            candidate["post_projection_compatible"]
        )
        flags["hard_violation_nonempty"] += bool(
            candidate["hard_violation_atoms"]
        )
        flags["projection_budget_exceeded"] += (
            float(candidate["projection_l2"]) > 0.5
        )
        flags["progress_below_frozen_minimum"] += (
            float(candidate["progress_margin"]) < MIN_PROGRESS_M
        )

    return {
        "terminal_reason_counts_by_semantic_arm": {
            arm: dict(sorted(reason_counts[arm].items()))
            for arm in SEMANTIC_ARMS
        },
        "suite_decision_counts_by_semantic_arm": {
            arm: {
                suite: dict(sorted(counts.items()))
                for suite, counts in sorted(suite_decisions[arm].items())
            }
            for arm in SEMANTIC_ARMS
        },
        "terminal_semantic_event_count_distribution": {
            arm: dict(sorted(event_count_distributions[arm].items()))
            for arm in SEMANTIC_ARMS
        },
        "terminal_rejected_candidate_flags": {
            arm: dict(sorted(candidate_flags[arm].items()))
            for arm in SEMANTIC_ARMS
        },
        "runtime_initial_geometry_gap": {
            "reason": "missing_destination_geometry",
            "affected_base_pair_count": len(unknown_pairs),
            "affected_base_pair_ids": sorted(unknown_pairs),
            "affected_unit_count_per_semantic_arm": (
                reason_counts["semantic_only"][
                    "missing_destination_geometry"
                ]
            ),
            "interpretation": (
                "The frozen 45-pair support audit established BDDL/task-graph "
                "wrapper initialization only. It did not establish that every "
                "destination had trusted geometry in the online LIBERO "
                "observation. Initialization support is therefore not "
                "closed-loop semantic support."
            ),
        },
        "k1_progress_gap": {
            "frozen_min_progress_m": MIN_PROGRESS_M,
            "terminal_rejection_count_per_semantic_arm": (
                reason_counts["semantic_only"][
                    "no_feasible_checked_action_block"
                ]
            ),
            "interpretation": (
                "Every terminal no-feasible decision had one K=1 candidate "
                "whose checked progress was below the frozen minimum. This is "
                "reported as clean availability failure; the threshold is not "
                "changed after observing the outcome."
            ),
        },
    }


def build_terminal_summary(
    protocol: dict[str, Any],
) -> dict[str, Any]:
    analysis = validate_results(protocol)
    output_root = REPO_ROOT / protocol["fresh_roots"]["stage_b_clean"]
    manifest = load_json_object(output_root / "run_manifest.json")
    rows = read_ledger(output_root / "episodes_ledger.jsonl")
    checksums = p0b_runner.read_checksums(output_root)
    artifact_paths = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    relative_artifacts = {
        path.relative_to(output_root).as_posix() for path in artifact_paths
    }
    if relative_artifacts != set(checksums):
        raise Support45TerminalError(
            "SHA256SUMS does not exactly cover the output-root inventory"
        )

    launcher_state_path = LAUNCHER_ROOT / "state.json"
    launcher_events_path = LAUNCHER_ROOT / "events.jsonl"
    launcher_log_path = LAUNCHER_ROOT / "clean_execution.log"
    launcher_state = load_json_object(launcher_state_path)
    if (
        launcher_state.get("status")
        != "support45_clean_complete_validated"
        or launcher_state.get("classification") != analysis["classification"]
    ):
        raise Support45TerminalError("launcher state is not terminal-valid")
    launcher_log = launcher_log_path.read_text(
        encoding="utf-8", errors="replace"
    )
    contact_warning_count = launcher_log.count("Too many contacts")

    return {
        "schema": (
            "proofalign.four-arm-v4-support45-clean-terminal-summary.v1"
        ),
        "recorded_at": manifest["completed_at"],
        "status": "complete",
        "classification": analysis["classification"],
        "clean_gate_pass": analysis["clean_gate_pass"],
        "support_conditioned": True,
        "confirmatory_claim_authorized": False,
        "protocol": {
            "path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
            "protocol_id": protocol["protocol_id"],
            "sha256": file_sha256(PROTOCOL_PATH),
            "source_commit": protocol["source"]["repository_commit"],
            "original_m2_50_percent_result_overridden": False,
        },
        "execution": {
            "output_root": output_root.relative_to(REPO_ROOT).as_posix(),
            "created_at": manifest["created_at"],
            "completed_at": manifest["completed_at"],
            "manifest_status": manifest["status"],
            "selected_gpu_indices": launcher_state["selected_gpu_indices"],
            "episode_count": len(rows),
            "valid_episode_count": analysis["valid_episode_count"],
            "invalid_episode_count": analysis["invalid_episode_count"],
            "missing_episode_count": analysis["missing_episode_count"],
        },
        "artifact_validation": {
            "official_terminal_recomputation_passed": True,
            "episode_artifacts_verified": analysis[
                "episode_artifacts_verified"
            ],
            "checksum_entry_count": len(checksums),
            "checksum_entries_verified": len(checksums),
            "checksum_inventory_complete": True,
            "artifact_file_count_including_checksums": (
                len(artifact_paths) + 1
            ),
            "artifact_total_bytes_including_checksums": sum(
                path.stat().st_size for path in output_root.rglob("*")
                if path.is_file()
            ),
            "checksums_sha256": file_sha256(output_root / "SHA256SUMS"),
            "analysis_sha256": file_sha256(output_root / "analysis.json"),
            "episodes_ledger_sha256": file_sha256(
                output_root / "episodes_ledger.jsonl"
            ),
            "run_manifest_sha256": file_sha256(
                output_root / "run_manifest.json"
            ),
            "launcher_state_sha256": file_sha256(launcher_state_path),
            "launcher_events_sha256": file_sha256(launcher_events_path),
            "launcher_log_sha256": file_sha256(launcher_log_path),
        },
        "arm_outcomes": _arm_outcomes(rows, analysis),
        "clean_gate": {
            "conditions": analysis["gate_conditions"],
            "eligible_vla_clean_unit_count": analysis[
                "eligible_vla_clean_unit_count"
            ],
            "dual_retained_unit_count": analysis[
                "dual_retained_unit_count"
            ],
            "dual_strict_success_retention": analysis[
                "dual_strict_success_retention"
            ],
            "dual_phase_completion_rate": analysis[
                "dual_phase_completion_rate"
            ],
            "dual_deadlock_rate": analysis["dual_deadlock_rate"],
            "unknown_or_unbound_rate": analysis[
                "unknown_or_unbound_rate"
            ],
            "dual_minus_vla_strict_success": analysis[
                "dual_minus_vla_strict_success"
            ],
        },
        "semantic_failure_taxonomy": _semantic_failure_taxonomy(
            rows, output_root=output_root
        ),
        "simulator_diagnostics": {
            "mujoco_too_many_contacts_warning_count": contact_warning_count,
            "warning_text_reports_ncon": 5000,
            "validator_treatment": (
                "The frozen validator retained all 360 episodes as valid. "
                "The warnings do not change the terminal gate classification, "
                "but contact-proxy magnitudes should be interpreted with this "
                "simulator limitation disclosed."
            ),
        },
        "interpretation": {
            "primary_result": (
                "The support-conditioned clean gate failed. VLA-only retained "
                "61/90 strict clean successes, while Dual retained 0/90 and "
                "deadlocked in 88/90 units."
            ),
            "causal_localization": (
                "Semantic-only and Dual have the same terminal semantic "
                "decision counts, directly localizing the dominant clean "
                "availability failure to L1 rather than L2."
            ),
            "support_boundary": (
                "The earlier 45/60 audit was an initialization-support audit, "
                "not a closed-loop support guarantee: 18/45 retained base "
                "pairs lacked destination geometry at the initial online "
                "decision."
            ),
            "claim_boundary": analysis["claim_boundary"],
        },
        "lifecycle": {
            "terminal": True,
            "resume_allowed": False,
            "overwrite_allowed": False,
            "additional_clean_execution_authorized": False,
            "attacked_execution_authorized": False,
            "attacked_block_reason": (
                "The frozen clean gate is a prerequisite and did not pass; "
                "the support45 protocol also explicitly authorizes clean only."
            ),
            "next_step": (
                "Preserve this nonpass, redesign and qualify L1 closed-loop "
                "coverage without using attacked outcomes, and require a new "
                "disclosed protocol before any further efficacy rollout."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    protocol = load_json_object(args.protocol.resolve())
    text = canonical_text(build_terminal_summary(protocol))
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise Support45TerminalError(
                f"support45 terminal summary is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
