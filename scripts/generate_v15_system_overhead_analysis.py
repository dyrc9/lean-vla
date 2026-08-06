#!/usr/bin/env python3
"""Generate checksum-bound v15.3 task-rollout systems-overhead tables."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402


SCHEMA = "proofalign.v15-3-system-overhead-paper-analysis.v1"
CREATED_AT = "2026-08-01T03:00:00+08:00"
CLEAN_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_recovery_"
    "task_utility_qualification_terminal_summary.json"
)
ATTACKED_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_recovery_"
    "attacked_task_utility_qualification_terminal_summary.json"
)
OUTPUT_PATH = REPO_ROOT / "experiments" / "proofalign_v15_system_overhead_analysis.json"
MARKDOWN_PATH = REPO_ROOT / "docs" / "paper" / "v15_system_overhead_analysis.md"
SELF_PATH = REPO_ROOT / "scripts" / "generate_v15_system_overhead_analysis.py"
ARMS = ("vla_only", "execution_only", "semantic_only", "dual")
L2_ARMS = {"execution_only", "dual"}
CONTROL_PERIOD_SECONDS = 0.05
REGISTERED_LATENCY_BUDGET_SECONDS = 0.1


class V15SystemOverheadAnalysisError(RuntimeError):
    """Raised when a frozen task-rollout artifact differs from its binding."""


def _stats(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=np.float64)
    if not array.size:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "maximum": None,
        }
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "p50": float(np.quantile(array, 0.50)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
        "maximum": float(np.max(array)),
    }


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15SystemOverheadAnalysisError(f"bound artifact is absent: {path}")
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _resolve_binding(binding: Mapping[str, Any]) -> Path:
    path = REPO_ROOT / str(binding["path"])
    if not path.is_file() or file_sha256(path) != binding["sha256"]:
        raise V15SystemOverheadAnalysisError(
            f"terminal binding differs: {binding.get('path')}"
        )
    return path


def _screen_category(audit: Mapping[str, Any]) -> str:
    if audit.get("enabled") is not True:
        return "disabled"
    if audit.get("deadlock") is True:
        return "deadlock"
    if audit.get("recovery_selected_for_force_attribution") is True:
        return "recovery_intervention"
    if audit.get("intervened") is True:
        return "standard_intervention"
    if audit.get("triggered") is True:
        return "triggered_without_intervention"
    return "untriggered"


def _verify_episode(
    artifact: Mapping[str, Any], expected_episode_id: str
) -> dict[str, Any]:
    if artifact.get("episode_id") != expected_episode_id:
        raise V15SystemOverheadAnalysisError("episode ledger identity differs")
    path = REPO_ROOT / str(artifact["path"])
    if not path.is_file() or file_sha256(path) != artifact["sha256"]:
        raise V15SystemOverheadAnalysisError(
            f"episode artifact checksum differs: {artifact.get('path')}"
        )
    return load_json_object(path)


def _analyze_arm(
    *,
    arm: str,
    episode_specs: list[Mapping[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    screen_latencies = []
    env_step_times = []
    policy_times = []
    screen_to_env_step_ratios = []
    candidate_counts = []
    risk_side_counts = []
    shadow_step_counts = []
    by_category: dict[str, list[float]] = defaultdict(list)
    category_counts: Counter[str] = Counter()
    episode_screen_sums = []
    enabled_audit_count = 0
    disabled_audit_count = 0
    metadata_mismatch_count = 0
    exact_action_mismatch_count = 0
    restore_mismatch_count = 0
    verified = 0

    for spec in episode_specs:
        episode_id = str(spec["episode_id"])
        episode = _verify_episode(artifacts[episode_id], episode_id)
        verified += 1
        expected_enabled = arm in L2_ARMS
        metadata_mismatch_count += int(
            bool(episode["metadata"]["l2_execution_integrity"]) is not expected_enabled
        )
        episode_screen = 0.0
        for row in episode["trace"]:
            runtime = row.get("runtime_seconds")
            if isinstance(runtime, Mapping):
                if runtime.get("env_step") is not None:
                    env_step_times.append(float(runtime["env_step"]))
                if runtime.get("policy") is not None:
                    policy_times.append(float(runtime["policy"]))
            if row.get("phase") != "policy":
                continue
            audit = row.get("predictive_virtual_brake")
            if not isinstance(audit, Mapping):
                raise V15SystemOverheadAnalysisError(
                    f"policy row lacks predictive audit: {episode_id}"
                )
            enabled = audit.get("enabled") is True
            enabled_audit_count += int(enabled)
            disabled_audit_count += int(not enabled)
            if enabled is not expected_enabled:
                metadata_mismatch_count += 1
            if not enabled:
                continue
            latency = float(audit["screen_latency_seconds"])
            screen_latencies.append(latency)
            episode_screen += latency
            category = _screen_category(audit)
            category_counts[category] += 1
            by_category[category].append(latency)
            candidate_counts.append(int(audit["candidate_count"]))
            risk_sides = audit.get("risk_sides")
            risk_side_counts.append(
                len(risk_sides) if isinstance(risk_sides, list) else 0
            )
            shadow_step_counts.append(int(audit["shadow_env_step_count"]))
            exact_action_mismatch_count += int(
                audit.get("deadlock") is not True
                and audit.get("exact_action_identity") is not True
            )
            restore_mismatch_count += int(
                audit.get("shadow_restore_identity") is not True
            )
            runtime = row.get("runtime_seconds")
            if (
                isinstance(runtime, Mapping)
                and runtime.get("env_step") is not None
                and float(runtime["env_step"]) > 0
            ):
                screen_to_env_step_ratios.append(latency / float(runtime["env_step"]))
        if expected_enabled:
            episode_screen_sums.append(episode_screen)

    screen = np.asarray(screen_latencies, dtype=np.float64)
    control_misses = int(np.sum(screen > CONTROL_PERIOD_SECONDS))
    registered_misses = int(np.sum(screen > REGISTERED_LATENCY_BUDGET_SECONDS))
    episode_count = len(episode_specs)
    success_count = sum(bool(row["task_success"]) for row in episode_specs)
    unsafe_count = sum(bool(row["unsafe_cost_or_collision"]) for row in episode_specs)
    return {
        "episode_count": episode_count,
        "verified_episode_artifact_count": verified,
        "task_success_count": success_count,
        "unsafe_count": unsafe_count,
        "l2_enabled": arm in L2_ARMS,
        "enabled_policy_audit_count": enabled_audit_count,
        "disabled_policy_audit_count": disabled_audit_count,
        "metadata_or_enablement_mismatch_count": metadata_mismatch_count,
        "exact_action_mismatch_count": exact_action_mismatch_count,
        "shadow_restore_mismatch_count": restore_mismatch_count,
        "screen_category_counts": dict(sorted(category_counts.items())),
        "screen_latency_seconds": _stats(screen_latencies),
        "screen_latency_by_category_seconds": {
            category: _stats(values) for category, values in sorted(by_category.items())
        },
        "control_period_50ms_deadline": {
            "threshold_seconds": CONTROL_PERIOD_SECONDS,
            "miss_count": control_misses,
            "miss_rate": (
                control_misses / len(screen_latencies) if screen_latencies else None
            ),
            "registered_gate": False,
        },
        "registered_100ms_latency_budget": {
            "threshold_seconds": REGISTERED_LATENCY_BUDGET_SECONDS,
            "miss_count": registered_misses,
            "miss_rate": (
                registered_misses / len(screen_latencies) if screen_latencies else None
            ),
        },
        "candidate_count_per_enabled_screen": _stats(candidate_counts),
        "risk_side_count_per_enabled_screen": _stats(risk_side_counts),
        "shadow_env_step_count_per_enabled_screen": _stats(shadow_step_counts),
        "screen_seconds_per_episode": _stats(episode_screen_sums),
        "trace_env_step_wall_seconds": _stats(env_step_times),
        "trace_policy_wall_seconds": _stats(policy_times),
        "screen_to_trace_env_step_ratio_diagnostic": _stats(screen_to_env_step_ratios),
    }


def _analyze_condition(
    terminal: Mapping[str, Any], *, evidence_binding_name: str
) -> tuple[dict[str, Any], dict[str, str]]:
    evidence_path = _resolve_binding(terminal["bindings"][evidence_binding_name])
    evidence = load_json_object(evidence_path)
    episode_specs = evidence["per_episode"]
    artifacts = {str(row["episode_id"]): row for row in evidence["episodes"]}
    if (
        len(episode_specs) != 72
        or len(artifacts) != 72
        or set(artifacts) != {str(row["episode_id"]) for row in episode_specs}
    ):
        raise V15SystemOverheadAnalysisError("task-rollout episode population differs")
    by_arm = {}
    for arm in ARMS:
        arm_specs = [row for row in episode_specs if row["arm"] == arm]
        if len(arm_specs) != 18:
            raise V15SystemOverheadAnalysisError(
                f"task-rollout arm population differs: {arm}"
            )
        by_arm[arm] = _analyze_arm(
            arm=arm,
            episode_specs=arm_specs,
            artifacts=artifacts,
        )
    l2_latencies = []
    for arm in L2_ARMS:
        for spec in [row for row in episode_specs if row["arm"] == arm]:
            episode = load_json_object(
                REPO_ROOT / artifacts[str(spec["episode_id"])]["path"]
            )
            l2_latencies.extend(
                float(row["predictive_virtual_brake"]["screen_latency_seconds"])
                for row in episode["trace"]
                if row.get("phase") == "policy"
                and row["predictive_virtual_brake"].get("enabled") is True
            )
    return (
        {
            "episode_count": len(episode_specs),
            "verified_episode_artifact_count": sum(
                row["verified_episode_artifact_count"] for row in by_arm.values()
            ),
            "by_arm": by_arm,
            "combined_l2_screen_latency_seconds": _stats(l2_latencies),
        },
        _binding(evidence_path),
    )


def build_analysis() -> dict[str, Any]:
    clean_terminal = load_json_object(CLEAN_TERMINAL_PATH)
    attacked_terminal = load_json_object(ATTACKED_TERMINAL_PATH)
    if (
        clean_terminal.get("registered_qualification_pass") is not True
        or attacked_terminal.get("registered_data_complete") is not True
        or attacked_terminal.get("registered_qualification_pass") is not False
    ):
        raise V15SystemOverheadAnalysisError(
            "frozen clean/attacked terminal classifications differ"
        )
    clean, clean_evidence_binding = _analyze_condition(
        clean_terminal, evidence_binding_name="evidence"
    )
    attacked, attacked_evidence_binding = _analyze_condition(
        attacked_terminal, evidence_binding_name="attacked_evidence"
    )
    clean_terminal_latency = clean_terminal["mechanism"]["screen_latency_seconds"]
    attacked_terminal_latency = attacked_terminal["mechanism"]["screen_latency_seconds"]
    for observed, terminal in (
        (clean["combined_l2_screen_latency_seconds"], clean_terminal_latency),
        (attacked["combined_l2_screen_latency_seconds"], attacked_terminal_latency),
    ):
        for key in ("count", "mean", "p50", "p95", "p99", "maximum"):
            matches = (
                observed[key] == terminal[key]
                if key == "count"
                else np.isclose(
                    float(observed[key]),
                    float(terminal[key]),
                    rtol=0.0,
                    atol=1e-15,
                )
            )
            if not matches:
                raise V15SystemOverheadAnalysisError(
                    f"terminal latency recomputation differs: {key}"
                )
    return {
        "schema": SCHEMA,
        "created_at": CREATED_AT,
        "analysis_role": (
            "checksum_bound_posthoc_descriptive_systems_overhead_analysis"
        ),
        "bindings": {
            "generator": _binding(SELF_PATH),
            "clean_terminal": _binding(CLEAN_TERMINAL_PATH),
            "clean_evidence": clean_evidence_binding,
            "attacked_terminal": _binding(ATTACKED_TERMINAL_PATH),
            "attacked_evidence": attacked_evidence_binding,
        },
        "conditions": {"clean": clean, "attacked": attacked},
        "cross_condition": {
            "clean_l2_screen_count": clean["combined_l2_screen_latency_seconds"][
                "count"
            ],
            "attacked_l2_screen_count": attacked["combined_l2_screen_latency_seconds"][
                "count"
            ],
            "clean_l2_screen_p95_seconds": clean["combined_l2_screen_latency_seconds"][
                "p95"
            ],
            "attacked_l2_screen_p95_seconds": attacked[
                "combined_l2_screen_latency_seconds"
            ]["p95"],
            "clean_registered_qualification_pass": True,
            "attacked_registered_qualification_pass": False,
            "attacked_nonpass_axis": "dual_task_success_noninferiority",
        },
        "claim_boundary": (
            "This artifact is a checksum-bound post-hoc descriptive analysis "
            "of the frozen clean and attacked task rollouts. It supports "
            "research-simulator screening-cost, deadline-miss, intervention-"
            "category, candidate-count, and shadow-step reporting. The four "
            "arms follow different trajectories, so cross-arm wall-time "
            "differences are not causal overhead estimates. The 50 ms result "
            "is diagnostic; the registered task protocols use a 100 ms "
            "screening budget. This artifact does not change the attacked "
            "qualification nonpass and does not establish hard real-time, "
            "hardware, arbitrary-attack, actuator-authority, or physical-"
            "safety claims."
        ),
        "explicit_nonclaims": {
            "causal_cross_arm_wall_time_overhead": False,
            "hard_real_time": False,
            "hardware": False,
            "arbitrary_attack": False,
            "actuator_authority": False,
            "physical_safety": False,
            "attacked_nonpass_superseded": False,
        },
    }


def _format_ms(value: float | None) -> str:
    return "—" if value is None else f"{1000.0 * value:.2f}"


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# v15.3 task-rollout systems overhead",
        "",
        "该表由冻结 clean/attacked episode 逐文件校验 SHA 后重算，属于 checksum-bound",
        "post-hoc 描述分析，不修改任何注册结论。",
        "",
        "| Condition | Arm | Screens | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | 50 ms miss | 100 ms miss |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in ("clean", "attacked"):
        for arm in ("execution_only", "dual"):
            row = payload["conditions"][condition]["by_arm"][arm]
            latency = row["screen_latency_seconds"]
            miss50 = row["control_period_50ms_deadline"]
            miss100 = row["registered_100ms_latency_budget"]
            lines.append(
                "| "
                + " | ".join(
                    (
                        condition,
                        arm,
                        str(latency["count"]),
                        _format_ms(latency["p50"]),
                        _format_ms(latency["p95"]),
                        _format_ms(latency["p99"]),
                        _format_ms(latency["maximum"]),
                        f"{miss50['miss_count']}/{latency['count']}",
                        f"{miss100['miss_count']}/{latency['count']}",
                    )
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "| Condition | Arm | Untriggered | Standard | Recovery | Deadlock | Shadow steps / screen (mean) | Candidates / screen (mean) |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for condition in ("clean", "attacked"):
        for arm in ("execution_only", "dual"):
            row = payload["conditions"][condition]["by_arm"][arm]
            categories = row["screen_category_counts"]
            shadow = row["shadow_env_step_count_per_enabled_screen"]["mean"]
            candidates = row["candidate_count_per_enabled_screen"]["mean"]
            lines.append(
                "| "
                + " | ".join(
                    (
                        condition,
                        arm,
                        str(categories.get("untriggered", 0)),
                        str(categories.get("standard_intervention", 0)),
                        str(categories.get("recovery_intervention", 0)),
                        str(categories.get("deadlock", 0)),
                        "—" if shadow is None else f"{shadow:.2f}",
                        "—" if candidates is None else f"{candidates:.2f}",
                    )
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            payload["claim_boundary"],
            "",
            "尤其是：50 ms 是控制周期诊断，不是注册通过门；注册 task protocol 的 screening budget 是 100 ms。不同 arm 的任务轨迹和长度不同，因此不能把 cross-arm wall time 差直接解释为因果 overhead。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    payload = build_analysis()
    OUTPUT_PATH.write_text(canonical_text(payload), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(payload), encoding="utf-8")
    print(
        canonical_text(
            {
                "analysis_path": OUTPUT_PATH.relative_to(REPO_ROOT).as_posix(),
                "analysis_sha256": file_sha256(OUTPUT_PATH),
                "markdown_path": MARKDOWN_PATH.relative_to(REPO_ROOT).as_posix(),
                "markdown_sha256": file_sha256(MARKDOWN_PATH),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
