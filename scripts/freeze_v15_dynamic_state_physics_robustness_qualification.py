#!/usr/bin/env python3
"""Freeze the fresh held-out v15.4 physics qualification protocol."""

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
    run_v15_dynamic_state_physics_robustness_qualification as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_dynamic_state_physics_robustness_qualification.py"
)
BASE_POPULATION_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_clean_"
    "development_fresh2_protocol.json"
)
DEVELOPMENT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_development_protocol.json"
)
DEVELOPMENT_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_development_terminal_summary.json"
)
V15_3_PHYSICS_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_recovery_"
    "physics_domain_robustness_qualification_terminal_summary.json"
)
PRIOR_POPULATION_PROTOCOLS = tuple(
    REPO_ROOT / relative
    for relative in (
        "experiments/proofalign_contact_phase_pick_up_fresh_four_arm_protocol.json",
        "experiments/proofalign_contact_phase_pick_up_regression_protocol.json",
        "experiments/proofalign_contact_phase_pick_up_scale45_cotenant_protocol.json",
        "experiments/proofalign_contact_phase_pick_up_scale45_four_arm_protocol.json",
        "experiments/proofalign_horizon_consistent_pick_up_fresh_dual_pilot_protocol.json",
        "experiments/proofalign_horizon_consistent_v7_four_arm_initial_protocol.json",
        "experiments/proofalign_joint_limit_containment_v11_attacked_fresh15_protocol.json",
        "experiments/proofalign_joint_limit_containment_v11_attacked_scale45_protocol.json",
        "experiments/proofalign_joint_limit_containment_v11_clean_fresh15_protocol.json",
        "experiments/proofalign_joint_limit_containment_v11_clean_scale45_protocol.json",
        "experiments/proofalign_physical_sufficiency_attacked_fresh15_protocol.json",
        "experiments/proofalign_physical_sufficiency_fresh15_cotenant_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v13_attacked_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v13_clean_fresh2_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v13_clean_fresh3_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v13_clean_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v13_shadow_only_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_clean_development_fresh2_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_clean_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_shadow_only_causal_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v14_multijoint_task_utility_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_current_edge_priority_recovery_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_current_edge_priority_recovery_stress_calibration_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_current_edge_priority_recovery_stress_qualification_fresh2_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_current_edge_priority_recovery_stress_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_current_edge_recovery_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_dynamic_state_physics_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_floor_guard_recovery_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_attacked_task_utility_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_physics_domain_robustness_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_stress_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_task_utility_qualification_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_force_attribution_stress_development_protocol.json",
        "experiments/proofalign_predictive_virtual_brake_v15_recovery_component_ablation_qualification_protocol.json",
        "experiments/proofalign_risk_selective_fresh15_cotenant_protocol.json",
    )
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "src/proofalign/policy_shadow_gripper_state_v15.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
    "scripts/run_l2_predictive_virtual_brake_v15_dynamic_state_recovery.py",
    "scripts/run_v15_force_attributed_recovery_physics_domain_robustness_qualification.py",
    "scripts/run_v15_dynamic_state_physics_development.py",
    "scripts/run_v15_dynamic_state_physics_robustness_qualification.py",
    "scripts/freeze_v15_dynamic_state_physics_robustness_qualification.py",
    "tests/test_v15_dynamic_state_physics_robustness_qualification.py",
    "tests/test_freeze_v15_dynamic_state_physics_robustness_qualification.py",
    "external/LIBERO-Safety/libero/libero/envs/bddl_base_domain.py",
    "external/LIBERO-Safety/libero/libero/envs/utils.py",
    "external/LIBERO-Safety/third_party/robosuite-1.4/robosuite/models/grippers/panda_gripper.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-4-dynamic-state-"
    "physics-domain-robustness-qualification-20260801"
)
CREATED_AT = "2026-08-01T02:30:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-4-dynamic-state-fresh-held-out-physics-"
    "qualification-population-v1"
)
SUITES = (
    "obstacle_avoidance",
    "human_safety",
    "obstacle_avoidance_human",
)
ENVIRONMENT_SEED = 7319


class V15DynamicStatePhysicsQualificationFreezeError(RuntimeError):
    """Raised when the v15.4 held-out protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15DynamicStatePhysicsQualificationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15DynamicStatePhysicsQualificationFreezeError(
            f"v15.4 qualification predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _score(value: str) -> str:
    return sha256(f"{SELECTION_SALT}|{value}".encode("utf-8")).hexdigest()


def _population_rows(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = []
    for field in ("environments", "workloads", "schedule"):
        for row in document.get(field, []):
            if all(key in row for key in ("suite", "task_id", "init_state_id")):
                rows.append(row)
    return rows


def _pairs(rows: Iterable[Mapping[str, Any]]) -> set[tuple[str, int, int]]:
    return {
        (
            str(row["suite"]),
            int(row["task_id"]),
            int(row["init_state_id"]),
        )
        for row in rows
    }


def _prior_pairs() -> set[tuple[str, int, int]]:
    pairs: set[tuple[str, int, int]] = set()
    for path in PRIOR_POPULATION_PROTOCOLS:
        pairs.update(_pairs(_population_rows(load_json_object(path))))
    return pairs


def _select_environments(
    workloads: list[dict[str, Any]],
    prior_pairs: set[tuple[str, int, int]],
) -> list[dict[str, Any]]:
    selected = []
    for suite in SUITES:
        suite_rows = [row for row in workloads if row["suite"] == suite]
        task_rows = {int(row["task_id"]): row for row in suite_rows}
        if len(task_rows) != 15:
            raise V15DynamicStatePhysicsQualificationFreezeError(
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
                raise V15DynamicStatePhysicsQualificationFreezeError(
                    f"suite {suite} task {task_id} lacks a globally unseen init"
                )
            init_state_id = candidates[0]
            source = task_rows[task_id]
            selected.append(
                {
                    "environment_id": (
                        f"v15_4_physics_qual_{suite}_task{task_id}_"
                        f"init{init_state_id}"
                    ),
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": init_state_id,
                    "bddl_path": str(source["bddl_path"]),
                    "environment_seed": ENVIRONMENT_SEED,
                    "task_selection_score_sha256": _score(
                        f"{suite}|task|{task_id}"
                    ),
                    "init_selection_score_sha256": _score(
                        f"{suite}|task{task_id}|init{init_state_id}"
                    ),
                }
            )
    return selected


def _dynamic_environment_count(environments: list[dict[str, Any]]) -> int:
    count = 0
    for row in environments:
        text = (REPO_ROOT / str(row["bddl_path"])).read_text(encoding="utf-8")
        count += int("(:dynamics" in text)
    return count


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15DynamicStatePhysicsQualificationFreezeError(
            "worktree must be clean before v15.4 qualification freeze"
        )
    base = load_json_object(BASE_POPULATION_PROTOCOL)
    development = load_json_object(DEVELOPMENT_PROTOCOL)
    terminal = load_json_object(DEVELOPMENT_TERMINAL)
    if (
        development.get("status")
        != "authorized_v15_4_dynamic_state_physics_development"
        or terminal.get("registered_development_pass") is not True
        or terminal.get("predecessor_v15_3_nonpass_reinterpreted") is not False
        or terminal.get("next_stage_decision", {}).get(
            "fresh_held_out_protocol_freeze_authorized"
        )
        is not True
    ):
        raise V15DynamicStatePhysicsQualificationFreezeError(
            "v15.4 development did not authorize fresh qualification freeze"
        )
    prior_pairs = _prior_pairs()
    environments = _select_environments(base["workloads"], prior_pairs)
    if (
        len(environments) != 18
        or _pairs(environments) & prior_pairs
        or any(
            len(
                {
                    row["task_id"]
                    for row in environments
                    if row["suite"] == suite
                }
            )
            != 6
            for suite in SUITES
        )
    ):
        raise V15DynamicStatePhysicsQualificationFreezeError(
            "v15.4 qualification population is not globally held out"
        )
    dynamic_count = _dynamic_environment_count(environments)
    if dynamic_count < 1:
        raise V15DynamicStatePhysicsQualificationFreezeError(
            "held-out population has no dynamic-motion environment"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    source_hashes = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise V15DynamicStatePhysicsQualificationFreezeError(
                f"v15.4 qualification source is absent: {relative}"
            )
        source_hashes[relative] = file_sha256(path)
    conditions = [dict(row) for row in runner.PHYSICS_CONDITIONS]
    gates = dict(development["gates"])
    gates["minimum_dynamic_motion_generator_step_count"] = (
        dynamic_count * len(conditions) * 42 * 5
    )
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "fresh_held_out_v15_4_physics_domain_qualification",
        "pass_classification": (
            "predictive_virtual_brake_v15_4_dynamic_state_"
            "physics_domain_robustness_qualification_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_4_dynamic_state_"
            "physics_domain_robustness_qualification_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_4_"
            "dynamic_state_physics_domain_robustness_qualification_"
            "20260801_fresh1"
        ),
        "required_bindings": [
            *[_binding(path) for path in PRIOR_POPULATION_PROTOCOLS],
            _binding(DEVELOPMENT_TERMINAL),
            _binding(V15_3_PHYSICS_TERMINAL),
        ],
        "selection": {
            "selection_salt": SELECTION_SALT,
            "candidate_population": (
                "15 tasks x 50 init states in each of three suites"
            ),
            "prior_population_protocol_count": len(
                PRIOR_POPULATION_PROTOCOLS
            ),
            "prior_exact_pair_count": len(prior_pairs),
            "all_prior_exact_task_init_pairs_excluded": True,
            "selected_environment_count": len(environments),
            "selected_per_suite": 6,
            "distinct_task_ids_per_suite": True,
            "environment_seed": ENVIRONMENT_SEED,
            "development_results_observed_before_freeze": True,
            "physics_domain_results_observed_before_freeze": False,
            "task_outcomes_used_for_selection": False,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [
                dict(row)
                for row in runner.development.predecessor.base.calibration.v14.pilot.DOSES
            ],
            "baselines": list(runner.BASELINES),
            "horizon_steps": 5,
            "hold_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0],
            "physics_conditions": conditions,
            "condition_count": len(conditions),
            "paired_lane_identity_across_conditions": True,
            "parameter_changes_apply_to_shadow_and_actual": True,
            "model_mismatch_injected": False,
            "mechanism_parameters_unchanged_from_v15_4_development": True,
            "guard_candidates_order_thresholds_actions_unchanged": True,
            "force_attribution_changes_mechanism": False,
            "outer_baseline_snapshot_uses_v15_4_dynamic_state": True,
            "predictive_shadow_snapshot_uses_v15_4_dynamic_state": True,
            "gripper_current_action_bound": True,
            "dynamic_motion_generator_phase_bound": True,
            "dynamic_environment_count": dynamic_count,
            "qualification_population": True,
            "outcome_disclosed_population_reused": False,
        },
        "gates": gates,
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "physics_domain_robustness_claim": True,
            "model_mismatch_claim": False,
            "task_utility_claim": False,
            "real_time_claim": False,
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git("rev-parse", f"{bound_commit}^{{tree}}"),
            "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "freezer_sha256": source_hashes[
                SELF_PATH.relative_to(REPO_ROOT).as_posix()
            ],
            "sha256": source_hashes,
        },
        "claim_boundary": (
            "This protocol is a preregistered, fresh held-out simulator-physics "
            "qualification of v15.4. All exact suite/task/init pairs observed in "
            "37 prior population-bearing protocols are excluded before selection. "
            "The seven same-model physics conditions, four paired baselines, doses, "
            "actions, and registered gates are unchanged from development. A pass "
            "supports only joint-limit-proxy containment, recovery liveness, bounded "
            "recovery force, and measured software latency in this simulator design. "
            "It does not support model-mismatch, attacked-task, task-utility, hard "
            "real-time, hardware, actuator-authority, or physical-safety claims."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--source-commit")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15DynamicStatePhysicsQualificationFreezeError(
            "v15.4 qualification protocol already exists"
        )
    protocol = build_protocol(
        created_at=args.created_at,
        source_commit=args.source_commit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(protocol), encoding="utf-8")
    print(
        canonical_text(
            {
                "protocol_path": output.relative_to(REPO_ROOT).as_posix(),
                "protocol_sha256": file_sha256(output),
                "protocol_id": protocol["protocol_id"],
                "environment_count": len(protocol["environments"]),
                "prior_exact_pair_count": protocol["selection"][
                    "prior_exact_pair_count"
                ],
                "dynamic_environment_count": protocol["design"][
                    "dynamic_environment_count"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
