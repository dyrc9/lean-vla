#!/usr/bin/env python3
"""Freeze held-out v15.3 simulator-physics domain qualification."""

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
    freeze_v15_force_attributed_recovery_stress_qualification as previous_freezer,
)
from scripts import (  # noqa: E402
    freeze_v15_force_attributed_recovery_attacked_task_utility_qualification_terminal as attacked_terminal,
)
from scripts import (  # noqa: E402
    freeze_v15_force_attributed_recovery_task_utility_qualification_terminal as task_terminal,
)
from scripts import (  # noqa: E402
    run_v15_force_attributed_recovery_physics_domain_robustness_qualification as runner,
)


V14_CLEAN_PROTOCOL_PATH = previous_freezer.V14_CLEAN_PROTOCOL_PATH
V14_STRESS_PROTOCOL_PATH = (
    previous_freezer.V14_STRESS_QUALIFICATION_PROTOCOL_PATH
)
V15_DEVELOPMENT_PROTOCOL_PATH = (
    previous_freezer.V15_2_DEVELOPMENT_PROTOCOL_PATH
)
V15_CALIBRATION_PROTOCOL_PATH = previous_freezer.V15_2_CALIBRATION_PROTOCOL_PATH
V15_FRESH2_PROTOCOL_PATH = previous_freezer.V15_2_FRESH2_PROTOCOL_PATH
FORCE_DEVELOPMENT_PROTOCOL_PATH = (
    previous_freezer.FORCE_DEVELOPMENT_PROTOCOL_PATH
)
V15_STRESS_PROTOCOL_PATH = previous_freezer.OUTPUT_PATH
V15_STRESS_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_stress_qualification_terminal_summary.json"
)
TASK_TERMINAL_PATH = task_terminal.OUTPUT_PATH
ATTACKED_TERMINAL_PATH = attacked_terminal.OUTPUT_PATH
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attributed_recovery_physics_domain_"
    "robustness_qualification.py"
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
    "scripts/run_v14_multijoint_stress_qualification.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_calibration.py",
    "scripts/run_v15_force_attribution_stress_development.py",
    "scripts/run_v15_force_attributed_recovery_stress_qualification.py",
    "scripts/run_v15_force_attributed_recovery_physics_domain_robustness_qualification.py",
    "scripts/freeze_v15_force_attributed_recovery_physics_domain_robustness_qualification.py",
    "tests/test_v15_force_attributed_recovery_physics_domain_robustness_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-3-force-attributed-"
    "recovery-physics-domain-robustness-qualification-20260801"
)
CREATED_AT = "2026-08-01T01:30:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-3-force-recovery-physics-domain-robustness-"
    "qualification-population-v1"
)
SUITES = previous_freezer.SUITES
ENVIRONMENT_SEED = 6509


class V15PhysicsDomainRobustnessFreezeError(RuntimeError):
    """Raised when physics-domain qualification cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15PhysicsDomainRobustnessFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15PhysicsDomainRobustnessFreezeError(
            f"physics-domain predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _score(value: str) -> str:
    return sha256(
        f"{SELECTION_SALT}|{value}".encode("utf-8")
    ).hexdigest()


def _pairs(rows: Iterable[Mapping[str, Any]]) -> set[tuple[str, int, int]]:
    return {
        (
            str(row["suite"]),
            int(row["task_id"]),
            int(row["init_state_id"]),
        )
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
            raise V15PhysicsDomainRobustnessFreezeError(
                f"suite {suite} lacks fifteen task identities"
            )
        task_ids = sorted(
            task_rows,
            key=lambda task_id: (
                _score(f"{suite}|task|{task_id}"),
                task_id,
            ),
        )[:6]
        for task_id in task_ids:
            candidates = [
                init_state_id
                for init_state_id in range(50)
                if (suite, task_id, init_state_id) not in prior_pairs
            ]
            candidates.sort(
                key=lambda init_state_id: (
                    _score(
                        f"{suite}|task{task_id}|init{init_state_id}"
                    ),
                    init_state_id,
                )
            )
            if not candidates:
                raise V15PhysicsDomainRobustnessFreezeError(
                    f"suite {suite} task {task_id} lacks unseen init"
                )
            init_state_id = candidates[0]
            source = task_rows[task_id]
            selected.append(
                {
                    "environment_id": (
                        f"v15_3_physics_robust_{suite}_task{task_id}_"
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


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15PhysicsDomainRobustnessFreezeError(
            "worktree must be clean before physics-domain freeze"
        )
    clean = load_json_object(V14_CLEAN_PROTOCOL_PATH)
    v14_stress = load_json_object(V14_STRESS_PROTOCOL_PATH)
    v15_development = load_json_object(V15_DEVELOPMENT_PROTOCOL_PATH)
    calibration = load_json_object(V15_CALIBRATION_PROTOCOL_PATH)
    fresh2 = load_json_object(V15_FRESH2_PROTOCOL_PATH)
    force_development = load_json_object(FORCE_DEVELOPMENT_PROTOCOL_PATH)
    v15_stress = load_json_object(V15_STRESS_PROTOCOL_PATH)
    v15_stress_terminal = load_json_object(V15_STRESS_TERMINAL_PATH)
    task = load_json_object(TASK_TERMINAL_PATH)
    attacked = load_json_object(ATTACKED_TERMINAL_PATH)
    if (
        len(clean.get("workloads", ())) != 45
        or len(v14_stress.get("environments", ())) != 18
        or len(v15_development.get("schedule", ())) != 28
        or len(calibration.get("environments", ())) != 12
        or len(fresh2.get("environments", ())) != 18
        or len(force_development.get("environments", ())) != 18
        or len(v15_stress.get("environments", ())) != 18
        or v15_stress_terminal.get("registered_qualification_pass")
        is not True
        or task.get("registered_qualification_pass") is not True
        or attacked.get("registered_data_complete") is not True
        or attacked.get("next_stage_decision", {}).get(
            "proceed_to_new_physics_domain_robustness_population"
        )
        is not True
    ):
        raise V15PhysicsDomainRobustnessFreezeError(
            "physics-domain predecessors differ"
        )
    prior_pairs = _pairs(clean["workloads"])
    prior_pairs.update(_pairs(v14_stress["environments"]))
    prior_pairs.update(_pairs(v15_development["schedule"]))
    prior_pairs.update(_pairs(calibration["environments"]))
    prior_pairs.update(_pairs(fresh2["environments"]))
    prior_pairs.update(_pairs(force_development["environments"]))
    prior_pairs.update(_pairs(v15_stress["environments"]))
    environments = _select_environments(clean["workloads"], prior_pairs)
    if len(environments) != 18 or _pairs(environments) & prior_pairs:
        raise V15PhysicsDomainRobustnessFreezeError(
            "physics-domain population is not held out"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    conditions = [dict(row) for row in runner.PHYSICS_CONDITIONS]
    per_condition_lanes = 18 * 7 * 2 * 3
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": (
            "held_out_v15_3_force_attributed_recovery_"
            "physics_domain_robustness_qualification"
        ),
        "pass_classification": (
            "predictive_virtual_brake_v15_3_force_attributed_recovery_"
            "physics_domain_robustness_qualification_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_3_force_attributed_recovery_"
            "physics_domain_robustness_qualification_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_3_"
            "force_attributed_recovery_physics_domain_robustness_"
            "qualification_20260801_fresh1"
        ),
        "required_bindings": [
            _binding(V14_CLEAN_PROTOCOL_PATH),
            _binding(V14_STRESS_PROTOCOL_PATH),
            _binding(V15_DEVELOPMENT_PROTOCOL_PATH),
            _binding(V15_CALIBRATION_PROTOCOL_PATH),
            _binding(V15_FRESH2_PROTOCOL_PATH),
            _binding(FORCE_DEVELOPMENT_PROTOCOL_PATH),
            _binding(V15_STRESS_PROTOCOL_PATH),
            _binding(V15_STRESS_TERMINAL_PATH),
            _binding(TASK_TERMINAL_PATH),
            _binding(ATTACKED_TERMINAL_PATH),
        ],
        "selection": {
            "selection_salt": SELECTION_SALT,
            "candidate_population": (
                "15 tasks x 50 init states in each of three suites"
            ),
            "all_prior_exact_task_init_pairs_excluded": True,
            "prior_exact_pair_count": len(prior_pairs),
            "selected_environment_count": len(environments),
            "selected_per_suite": 6,
            "distinct_task_ids_per_suite": True,
            "environment_seed": ENVIRONMENT_SEED,
            "stress_and_task_results_observed_before_freeze": True,
            "physics_domain_results_observed_before_freeze": False,
            "task_outcomes_used_for_selection": False,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [
                dict(row) for row in runner.base.calibration.v14.pilot.DOSES
            ],
            "baselines": list(runner.BASELINES),
            "horizon_steps": (
                runner.base.calibration.v14.pilot.HORIZON_STEPS
            ),
            "hold_action": (
                runner.base.calibration.v14.pilot.HOLD_ACTION.tolist()
            ),
            "physics_conditions": conditions,
            "condition_count": len(conditions),
            "paired_lane_identity_across_conditions": True,
            "parameter_changes_apply_to_shadow_and_actual": True,
            "model_mismatch_injected": False,
            "mechanism_parameters_unchanged_from_v15_3": True,
            "force_attribution_changes_mechanism": False,
        },
        "analysis": {
            "role": (
                "held-out paired simulator-physics domain robustness "
                "qualification and same-population baseline consolidation"
            ),
            "primary_estimands": [
                "per-domain v15.3 crossing, below-floor, and deadlock counts",
                "per-domain paired v14 deadlock recovery identity",
                "per-domain attributable and post-step force envelopes",
                "per-domain active contact capacity and latency gates",
            ],
            "comparative_estimands": [
                "reactive-stop crossing versus no guard",
                "v15.3 below-floor burden versus reactive stop",
                "v15.3 executed-step availability versus v14",
            ],
            "condition_is_statistical_unit_for_robustness_summary": True,
            "task_outcomes_read": False,
            "same_model_shadow_and_actual": True,
            "model_mismatch_claim": False,
        },
        "gates": {
            **dict(v15_stress["gates"]),
            "expected_condition_count": len(conditions),
            "expected_environment_count": 18,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": per_condition_lanes,
            "expected_baseline_lane_count": (
                per_condition_lanes * len(runner.BASELINES)
            ),
            "expected_total_stress_lane_count": (
                per_condition_lanes * len(conditions)
            ),
            "expected_total_baseline_lane_count": (
                per_condition_lanes
                * len(conditions)
                * len(runner.BASELINES)
            ),
        },
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
            "This outcome-blind qualification uses eighteen new exact "
            "task/init pairs and seven frozen same-simulator physics domains: "
            "nominal plus arm mass, joint damping, and arm sliding friction "
            "scales. Each perturbed model is shared by shadow prediction and "
            "actual execution, so a pass supports parameter-domain robustness, "
            "not simulator-model mismatch robustness. No policy, reward, done, "
            "task success, cost, or collision outcome is read. No task-utility, "
            "arbitrary-attack, real-time, hardware, actuator-authority, or "
            "physical-safety claim is authorized."
        ),
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
    text = canonical_text(
        build_protocol(
            created_at=(
                str(retained["created_at"])
                if retained is not None
                else args.created_at
            ),
            source_commit=(
                str(retained["source"]["repository_commit"])
                if retained is not None
                else None
            ),
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15PhysicsDomainRobustnessFreezeError(
                f"physics-domain protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
