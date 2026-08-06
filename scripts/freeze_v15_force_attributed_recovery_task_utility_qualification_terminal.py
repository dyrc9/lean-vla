#!/usr/bin/env python3
"""Freeze the registered v15.3 held-out task-utility qualification pass."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
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
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import freeze_v14_multijoint_task_utility_qualification_terminal as v14_terminal  # noqa: E402
from scripts import run_v15_force_attributed_recovery_task_utility_qualification as runner  # noqa: E402


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_task_utility_qualification_terminal_summary.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attributed_recovery_task_utility_"
    "qualification_terminal.py"
)
CREATED_AT = "2026-07-31T23:59:59+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-task-utility-qualification-terminal-summary.v1"
)
EXPECTED_CLASSIFICATION = (
    "predictive_virtual_brake_v15_3_force_attributed_"
    "recovery_task_utility_qualification_pass"
)
ARM_ORDER = ("vla_only", "execution_only", "semantic_only", "dual")
L2_ARMS = ("execution_only", "dual")
EXPECTED_TASK_SUCCESS = {
    "vla_only": 11,
    "execution_only": 11,
    "semantic_only": 11,
    "dual": 12,
}
STRESS_FORCE_LIMITS = {
    "all_scope_increment": 10000.0,
    "all_post_absolute": 10000.0,
    "all_post_increment": 10000.0,
    "recovery_scope_increment": 1250.0,
    "recovery_post_increment": 1250.0,
}


class V15TaskUtilityTerminalError(RuntimeError):
    """Raised when retained v15.3 task-utility evidence differs."""


def _force_scan(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    schedule = {
        str(row["episode_id"]): row for row in protocol["schedule"]
    }
    counters: dict[str, Counter[str]] = {
        arm: Counter() for arm in ARM_ORDER
    }
    groups: dict[str, list[float]] = {
        "all_scope_increment": [],
        "all_post_absolute": [],
        "all_post_increment": [],
        "recovery_scope_increment": [],
        "recovery_post_absolute": [],
        "recovery_post_increment": [],
        "standard_scope_increment": [],
        "standard_post_absolute": [],
        "standard_post_increment": [],
    }
    worst_rows: dict[str, dict[str, Any] | None] = {
        key: None for key in groups
    }

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule.get(episode_id)
        if spec is None:
            raise V15TaskUtilityTerminalError(
                f"episode absent from schedule: {episode_id}"
            )
        episode_path = REPO_ROOT / str(artifact["path"])
        if file_sha256(episode_path) != artifact["sha256"]:
            raise V15TaskUtilityTerminalError(
                f"episode hash differs: {episode_id}"
            )
        episode = load_json_object(episode_path)
        arm = str(spec["arm"])
        l2_enabled = arm in L2_ARMS
        for trace in episode["trace"]:
            if trace.get("phase") != "policy":
                continue
            audit = trace.get("predictive_virtual_brake")
            if not isinstance(audit, Mapping):
                raise V15TaskUtilityTerminalError(
                    f"v15.3 audit absent: {episode_id}"
                )
            counters[arm]["policy_audit_count"] += 1
            if bool(audit.get("enabled")) != l2_enabled:
                raise V15TaskUtilityTerminalError(
                    f"v15.3 enablement differs: {episode_id}"
                )
            if not l2_enabled:
                counters[arm]["disabled_audit_count"] += 1
                continue
            counters[arm]["l2_audit_count"] += 1
            counters[arm]["trigger_count"] += int(audit["triggered"])
            counters[arm]["intervention_count"] += int(
                audit["intervened"]
            )
            counters[arm]["deadlock_count"] += int(audit["deadlock"])
            recovery = bool(
                audit.get("floor_or_current_edge_recovery_selected")
            )
            counters[arm]["recovery_selected_count"] += int(recovery)
            counters[arm]["recovery_prevented_deadlock_count"] += int(
                audit.get(
                    "floor_or_current_edge_recovery_prevented_deadlock"
                )
                is True
            )
            if audit.get("intervened") is not True:
                continue
            scope = float(
                audit[
                    "guard_scope_maximum_positive_joint_increment_over_pre_step"
                ]
            )
            post_absolute = float(
                audit["post_step_maximum_abs_risk_constraint_force"]
            )
            post_increment = float(
                audit[
                    "post_step_maximum_positive_joint_increment_over_pre_step"
                ]
            )
            kind = "recovery" if recovery else "standard"
            row = {
                "episode_id": episode_id,
                "arm": arm,
                "base_pair_id": str(spec["base_pair_id"]),
                "runner_step_id": int(audit["runner_step_id"]),
                "kind": kind,
                "guard_scope_positive_joint_increment": scope,
                "post_step_absolute_risk_force": post_absolute,
                "post_step_positive_joint_increment": post_increment,
                "pre_step_absolute_risk_force": float(
                    audit[
                        "pre_step_maximum_abs_risk_constraint_force"
                    ]
                ),
                "legacy_guard_scope_absolute_risk_force": float(
                    audit[
                        "guard_scope_reported_maximum_abs_risk_constraint_force"
                    ]
                ),
            }
            values = {
                "all_scope_increment": scope,
                "all_post_absolute": post_absolute,
                "all_post_increment": post_increment,
                f"{kind}_scope_increment": scope,
                f"{kind}_post_absolute": post_absolute,
                f"{kind}_post_increment": post_increment,
            }
            for name, value in values.items():
                groups[name].append(value)
                retained = worst_rows[name]
                if (
                    retained is None
                    or value
                    > float(retained["value"])
                ):
                    worst_rows[name] = {"value": value, **row}

    return {
        "by_arm": {
            arm: dict(sorted(counters[arm].items()))
            for arm in ARM_ORDER
        },
        "distributions": {
            name: v14_terminal._quantiles(values)
            for name, values in groups.items()
        },
        "worst_cases": worst_rows,
    }


def _stress_force_diagnostic(force: Mapping[str, Any]) -> dict[str, Any]:
    distributions = force["distributions"]
    observed = {
        name: distributions[name]["maximum"]
        for name in STRESS_FORCE_LIMITS
    }
    gates = {
        name: value is not None and float(value) <= STRESS_FORCE_LIMITS[name]
        for name, value in observed.items()
    }
    return {
        "registered_task_utility_gate": False,
        "retrospective_comparison_only": True,
        "stress_thresholds_were_not_registered_for_natural_task_rollouts": True,
        "thresholds": STRESS_FORCE_LIMITS,
        "observed": observed,
        "comparison_results": gates,
        "all_comparisons_pass": all(gates.values()),
        "interpretation": (
            "The registered task-utility result is unchanged. Natural-policy "
            "temporary virtual-constraint force does not inherit the separate "
            "stress qualification envelope; post-step force remains inside it."
        ),
    }


def build_summary(*, created_at: str = CREATED_AT) -> dict[str, Any]:
    protocol = load_json_object(runner.DEFAULT_PROTOCOL)
    evidence = runner.validate_results(
        protocol,
        protocol_path=runner.DEFAULT_PROTOCOL,
    )
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    evidence_path = root / "pilot_evidence.json"
    manifest_path = root / "run_manifest.json"
    checksums_path = root / "SHA256SUMS"
    manifest = load_json_object(manifest_path)
    entries = v14_terminal._checksum_entries(checksums_path)
    failed = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if (
        evidence.get("classification") != EXPECTED_CLASSIFICATION
        or evidence.get("qualification_pass") is not True
        or evidence.get("task_utility_qualification_claim_authorized")
        is not True
        or evidence.get("pilot_complete") is not True
        or len(evidence.get("episodes", ())) != 72
        or manifest.get("status") != "complete"
        or len(manifest.get("completed_episode_ids", ())) != 72
        or manifest.get("error") is not None
        or len(entries) != 75
        or failed
    ):
        raise V15TaskUtilityTerminalError(
            "v15.3 task-utility terminal population differs"
        )
    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15TaskUtilityTerminalError(
                f"v15.3 task-utility checksum differs: {relative}"
            )

    scan = v14_terminal._scan_episodes(protocol, evidence)
    by_arm = scan["by_arm"]
    if (
        {arm: by_arm[arm]["task_success_count"] for arm in ARM_ORDER}
        != EXPECTED_TASK_SUCCESS
        or by_arm["execution_only"]["deadlock_episode_count"] != 1
        or by_arm["dual"]["deadlock_episode_count"] != 0
        or any(
            by_arm[arm]["actual_below_floor_count"] != 0
            or by_arm[arm]["actual_crossing_count"] != 0
            for arm in L2_ARMS
        )
    ):
        raise V15TaskUtilityTerminalError(
            "v15.3 task-utility independent scan differs"
        )
    force = _force_scan(protocol, evidence)
    diagnostic = _stress_force_diagnostic(force)
    if (
        diagnostic["comparison_results"]["recovery_scope_increment"]
        is not False
        or diagnostic["comparison_results"]["recovery_post_increment"]
        is not True
    ):
        raise V15TaskUtilityTerminalError(
            "v15.3 natural-task force diagnostic differs"
        )
    contrasts = evidence["aggregate"]["paired_task_success_contrasts"]
    if (
        contrasts["execution_only_minus_vla_only"]["lower"]
        < protocol["analysis"]["noninferiority_margin"]
        or contrasts["dual_minus_semantic_only"]["lower"]
        < protocol["analysis"]["noninferiority_margin"]
    ):
        raise V15TaskUtilityTerminalError(
            "v15.3 registered noninferiority differs"
        )

    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "registered_classification": evidence["classification"],
        "registered_qualification_pass": True,
        "registered_result_unchanged": True,
        "failed_registered_gates": failed,
        "registered_gate_results": evidence["gate_results"],
        "bindings": {
            "protocol": {
                "path": runner.DEFAULT_PROTOCOL.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(runner.DEFAULT_PROTOCOL),
            },
            "evidence": {
                "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(evidence_path),
            },
            "manifest": {
                "path": manifest_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(manifest_path),
            },
            "checksums": {
                "path": checksums_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(checksums_path),
                "entry_count": len(entries),
            },
            "freezer": {
                "path": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(SELF_PATH),
            },
        },
        "population": {
            "paired_task_init_count": 18,
            "episode_count": 72,
            "episodes_per_arm": 18,
            "environment_seed": protocol["selection"]["environment_seed"],
            "policy_seed": protocol["selection"]["policy_seed"],
            "outcome_blind_before_protocol_freeze": True,
            "all_stress_pairs_retained": True,
        },
        "task_utility": {
            "by_arm": by_arm,
            "paired_task_success_contrasts": contrasts,
            "registered_noninferiority_margin": protocol["analysis"][
                "noninferiority_margin"
            ],
            "official_unsafe_nonincrease_passed": True,
        },
        "mechanism": {
            "v15_3_force_audit": force,
            "screen_latency_seconds": scan["screen_latency_seconds"],
            "all_side_prediction_absolute_error_rad": scan[
                "all_side_prediction_absolute_error_rad"
            ],
            "deadlocks": scan["deadlocks"],
        },
        "natural_task_force_envelope_diagnostic": diagnostic,
        "unregistered_runtime_diagnostic": {
            "contact_capacity_warning_observed_in_interactive_stdout": True,
            "checksum_bound_warning_count_available": False,
            "registered_gate": False,
            "physical_contact_capacity_claim_authorized": False,
        },
        "qualified_claims": {
            "held_out_clean_task_success_noninferiority": True,
            "held_out_official_unsafe_nonincrease": True,
            "l2_joint_limit_floor_containment_in_these_task_rollouts": True,
            "v15_3_force_audit_integrity": True,
        },
        "explicit_nonclaims": {
            "natural_task_recovery_force_within_stress_envelope": False,
            "contact_capacity_warning_free": False,
            "attacked_efficacy": False,
            "real_time_deployment": False,
            "hardware_behavior": False,
            "actuator_authority": False,
            "physical_safety": False,
        },
        "next_stage_decision": {
            "registered_task_utility_qualification_complete": True,
            "freeze_attacked_successor_without_pair_filtering": True,
            "add_checksum_bound_contact_warning_audit": True,
            "treat_natural_task_force_as_new_robustness_endpoint": True,
            "modify_registered_task_utility_result": False,
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    summary = build_summary(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        )
    )
    text = canonical_text(summary)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15TaskUtilityTerminalError(
                f"v15.3 task-utility terminal is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
