#!/usr/bin/env python3
"""Freeze a new-population, same-lane v15 recovery component ablation."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    freeze_v15_force_attributed_recovery_physics_domain_robustness_qualification as physics_freezer,
)
from scripts import (  # noqa: E402
    run_v15_recovery_component_ablation_qualification as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT / "scripts" / "freeze_v15_recovery_component_ablation_qualification.py"
)
PHYSICS_PROTOCOL_PATH = physics_freezer.OUTPUT_PATH
PHYSICS_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_recovery_"
    "physics_domain_robustness_qualification_terminal_summary.json"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_l2_predictive_virtual_brake_v15_floor_guard_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_force_attributed_recovery.py",
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v14_multijoint_stress_development.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_calibration.py",
    "scripts/run_v15_force_attribution_stress_development.py",
    "scripts/run_v15_force_attributed_recovery_stress_qualification.py",
    "scripts/run_v15_recovery_component_ablation_qualification.py",
    "scripts/freeze_v15_recovery_component_ablation_qualification.py",
    "tests/test_v15_recovery_component_ablation_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-recovery-component-"
    "ablation-qualification-20260801"
)
CREATED_AT = "2026-08-01T02:30:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-recovery-component-ablation-qualification-population-v1"
)
ENVIRONMENT_SEED = 7509
SUITES = physics_freezer.SUITES


class V15RecoveryComponentAblationFreezeError(RuntimeError):
    """Raised when the component-ablation protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryComponentAblationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15RecoveryComponentAblationFreezeError(
            f"component-ablation predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _score(value: str) -> str:
    return sha256(f"{SELECTION_SALT}|{value}".encode()).hexdigest()


def _pairs(rows: Iterable[Mapping[str, Any]]) -> set[tuple[str, int, int]]:
    return {
        (str(row["suite"]), int(row["task_id"]), int(row["init_state_id"]))
        for row in rows
    }


def _select_environments(
    workloads: list[dict[str, Any]],
    prior_pairs: set[tuple[str, int, int]],
) -> list[dict[str, Any]]:
    selected = []
    for suite in SUITES:
        suite_rows = [row for row in workloads if row["suite"] == suite]
        task_rows = {int(row["task_id"]): row for row in suite_rows}
        if len(task_rows) != 15:
            raise V15RecoveryComponentAblationFreezeError(
                f"suite {suite} lacks fifteen task identities"
            )
        task_ids = sorted(
            task_rows,
            key=lambda task_id: (_score(f"{suite}|task|{task_id}"), task_id),
        )[:6]
        for task_id in task_ids:
            candidates = [
                init_state_id
                for init_state_id in range(50)
                if (suite, task_id, init_state_id) not in prior_pairs
            ]
            candidates.sort(
                key=lambda init_state_id: (
                    _score(f"{suite}|task{task_id}|init{init_state_id}"),
                    init_state_id,
                )
            )
            if not candidates:
                raise V15RecoveryComponentAblationFreezeError(
                    f"suite {suite} task {task_id} lacks unseen init"
                )
            init_state_id = candidates[0]
            source = task_rows[task_id]
            selected.append(
                {
                    "environment_id": (
                        f"v15_component_ablation_{suite}_task{task_id}_"
                        f"init{init_state_id}"
                    ),
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": init_state_id,
                    "bddl_path": str(source["bddl_path"]),
                    "environment_seed": ENVIRONMENT_SEED,
                    "task_selection_score_sha256": _score(f"{suite}|task|{task_id}"),
                    "init_selection_score_sha256": _score(
                        f"{suite}|task{task_id}|init{init_state_id}"
                    ),
                }
            )
    return selected


def _predecessors() -> tuple[list[dict[str, Any]], set[tuple[str, int, int]]]:
    clean = load_json_object(physics_freezer.V14_CLEAN_PROTOCOL_PATH)
    sources = (
        physics_freezer.V14_STRESS_PROTOCOL_PATH,
        physics_freezer.V15_DEVELOPMENT_PROTOCOL_PATH,
        physics_freezer.V15_CALIBRATION_PROTOCOL_PATH,
        physics_freezer.V15_FRESH2_PROTOCOL_PATH,
        physics_freezer.FORCE_DEVELOPMENT_PROTOCOL_PATH,
        physics_freezer.V15_STRESS_PROTOCOL_PATH,
        PHYSICS_PROTOCOL_PATH,
    )
    prior = _pairs(clean["workloads"])
    for path in sources:
        payload = load_json_object(path)
        rows = payload.get("environments", payload.get("schedule"))
        if not isinstance(rows, list):
            raise V15RecoveryComponentAblationFreezeError(
                f"predecessor population is absent: {path}"
            )
        prior.update(_pairs(rows))
    return clean["workloads"], prior


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15RecoveryComponentAblationFreezeError(
            "worktree must be clean before component-ablation freeze"
        )
    physics_terminal = load_json_object(PHYSICS_TERMINAL_PATH)
    if physics_terminal.get("registered_result_unchanged") is not True:
        raise V15RecoveryComponentAblationFreezeError(
            "physics-domain terminal result is absent or mutable"
        )
    workloads, prior = _predecessors()
    environments = _select_environments(workloads, prior)
    if len(environments) != 18 or _pairs(environments) & prior:
        raise V15RecoveryComponentAblationFreezeError(
            "component-ablation population is not held out"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    baseline_count = len(runner.BASELINES)
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "held_out_same_lane_v15_recovery_component_ablation",
        "pass_classification": (
            "predictive_virtual_brake_v15_recovery_component_"
            "ablation_qualification_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_recovery_component_"
            "ablation_qualification_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_recovery_"
            "component_ablation_qualification_20260801_fresh1"
        ),
        "required_bindings": [
            _binding(physics_freezer.V14_CLEAN_PROTOCOL_PATH),
            _binding(physics_freezer.V14_STRESS_PROTOCOL_PATH),
            _binding(physics_freezer.V15_DEVELOPMENT_PROTOCOL_PATH),
            _binding(physics_freezer.V15_CALIBRATION_PROTOCOL_PATH),
            _binding(physics_freezer.V15_FRESH2_PROTOCOL_PATH),
            _binding(physics_freezer.FORCE_DEVELOPMENT_PROTOCOL_PATH),
            _binding(physics_freezer.V15_STRESS_PROTOCOL_PATH),
            _binding(physics_freezer.V15_STRESS_TERMINAL_PATH),
            _binding(physics_freezer.TASK_TERMINAL_PATH),
            _binding(physics_freezer.ATTACKED_TERMINAL_PATH),
            _binding(PHYSICS_PROTOCOL_PATH),
            _binding(PHYSICS_TERMINAL_PATH),
        ],
        "selection": {
            "selection_salt": SELECTION_SALT,
            "candidate_population": (
                "15 tasks x 50 init states in each of three suites"
            ),
            "all_prior_exact_task_init_pairs_excluded": True,
            "prior_exact_pair_count": len(prior),
            "selected_environment_count": len(environments),
            "selected_per_suite": 6,
            "distinct_task_ids_per_suite": True,
            "environment_seed": ENVIRONMENT_SEED,
            "task_outcomes_used_for_selection": False,
            "component_ablation_results_observed_before_freeze": False,
            "prior_physics_results_observed_before_freeze": True,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "held_out_component_ablation_claim": True,
            "task_utility_claim": False,
            "model_mismatch_claim": False,
            "real_time_claim": False,
        },
        "design": {
            "baselines": list(runner.BASELINES),
            "incremental_components": [
                "v14 predictive brake",
                "plus floor-edge recovery",
                "plus current-edge recovery",
                "plus current-edge-before-floor priority",
                "plus non-mechanism-changing force attribution audit",
            ],
            "paired_same_injected_state": True,
            "nominal_physics_only": True,
            "model_mismatch_injected": False,
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "doses": [dict(row) for row in runner.base.calibration.v14.pilot.DOSES],
            "horizon_steps": runner.base.calibration.v14.pilot.HORIZON_STEPS,
            "hold_action": runner.base.calibration.v14.pilot.HOLD_ACTION.tolist(),
        },
        "gates": {
            "expected_environment_count": 18,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": 756,
            "expected_baseline_lane_count": 756 * baseline_count,
            "shadow_trace_maximum_side_error_rad": 0.001,
            "exact_action_mismatch_count_max": 0,
            "no_guard_crossing_count_min": 1,
            "no_guard_below_floor_count_min": 1,
            "v14_deadlock_lane_count_min": 1,
            "recovery_crossing_count_max": 0,
            "recovery_below_floor_count_max": 0,
            "selected_floor_violation_count_max": 0,
            "component_selected_recovery_count_min": 1,
            "priority_residual_deadlock_lane_count_max": 0,
            "priority_floor_edge_selected_count_max": 0,
            "v15_3_residual_deadlock_lane_count_max": 0,
            "v15_2_v15_3_margin_trace_error_rad_max": 1e-9,
            "prediction_execution_error_rad_max": 0.001,
            "force_recomputation_mismatch_count_max": 0,
            "maximum_attributable_joint_force_increment": 10000.0,
            "maximum_attributable_increment_to_v14_legacy_force_ratio": 1.25,
            "maximum_post_step_absolute_risk_force": 10000.0,
            "maximum_post_step_positive_joint_increment": 10000.0,
            "maximum_recovery_attributable_joint_force_increment": 1250.0,
            "maximum_recovery_post_step_positive_joint_increment": 1250.0,
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "latency_budget_seconds": 0.1,
            "screen_latency_seconds_p95_max": 0.1,
            "screen_latency_seconds_max": 0.2,
            "screen_latency_100ms_miss_rate_max": 0.025,
        },
        "environments": environments,
        "source": {
            "repository_commit": bound_commit,
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative) for relative in SOURCE_PATHS
            },
        },
        "claim_boundary": (
            "This outcome-blind qualification compares eight baselines on the "
            "same injected states from eighteen new exact task/init pairs. A "
            "pass supports paired simulator component-ablation claims for the "
            "incremental recovery stack and force-audit non-interference under "
            "the frozen nominal stress model. It does not establish task "
            "utility, attacked efficacy, physics-parameter or model-mismatch "
            "robustness, real-time deployment, hardware behavior, actuator "
            "authority, or physical safety."
        ),
        "freeze_policy": {
            "thresholds_must_not_be_relaxed_post_result": True,
            "all_selected_pairs_retained": True,
            "nonpass_must_be_terminalized_without_overwrite": True,
            "fresh_output_root_must_be_absent": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15RecoveryComponentAblationFreezeError(
            "component-ablation protocol already exists"
        )
    protocol = build_protocol(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(protocol), encoding="utf-8")
    print(
        canonical_text(
            {
                "protocol_path": output.relative_to(REPO_ROOT).as_posix(),
                "protocol_sha256": file_sha256(output),
                "environment_count": len(protocol["environments"]),
                "expected_stress_lane_count": protocol["gates"][
                    "expected_stress_lane_count"
                ],
                "expected_baseline_lane_count": protocol["gates"][
                    "expected_baseline_lane_count"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
