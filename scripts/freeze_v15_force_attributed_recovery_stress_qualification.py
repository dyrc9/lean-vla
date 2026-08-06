#!/usr/bin/env python3
"""Freeze held-out v15.3 force-attributed recovery qualification."""

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
from scripts import run_v15_force_attributed_recovery_stress_qualification as runner  # noqa: E402


V14_CLEAN_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
V14_STRESS_QUALIFICATION_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_qualification_protocol.json"
)
V15_2_DEVELOPMENT_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_development_protocol.json"
)
V15_2_CALIBRATION_PROTOCOL_PATH = runner.calibration.DEFAULT_PROTOCOL
V15_2_FRESH2_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_protocol.json"
)
V15_2_FRESH2_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_terminal_summary.json"
)
FORCE_DEVELOPMENT_PROTOCOL_PATH = runner.force_development.DEFAULT_PROTOCOL
FORCE_DEVELOPMENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attribution_"
    "stress_development_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_attributed_recovery_stress_qualification.py"
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
    "scripts/freeze_v15_force_attribution_stress_development_terminal.py",
    "scripts/run_v15_force_attributed_recovery_stress_qualification.py",
    "scripts/freeze_v15_force_attributed_recovery_stress_qualification.py",
    "tests/test_v15_force_attributed_recovery_stress_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-3-force-attributed-"
    "recovery-stress-qualification-20260731"
)
CREATED_AT = "2026-07-31T23:15:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-3-force-attributed-recovery-stress-"
    "qualification-population-v1"
)
SUITES = (
    "obstacle_avoidance",
    "human_safety",
    "obstacle_avoidance_human",
)


class V15ForceAttributedRecoveryQualificationFreezeError(RuntimeError):
    """Raised when held-out v15.3 qualification cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15ForceAttributedRecoveryQualificationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15ForceAttributedRecoveryQualificationFreezeError(
            f"qualification predecessor is absent: {path}"
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
            raise V15ForceAttributedRecoveryQualificationFreezeError(
                f"suite {suite} lacks fifteen task identities"
            )
        selected_tasks = sorted(
            task_rows,
            key=lambda task_id: (
                _score(f"{suite}|task|{task_id}"),
                task_id,
            ),
        )[:6]
        for task_id in selected_tasks:
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
                raise V15ForceAttributedRecoveryQualificationFreezeError(
                    f"suite {suite} task {task_id} lacks unseen init"
                )
            init_state_id = candidates[0]
            source = task_rows[task_id]
            selected.append(
                {
                    "environment_id": (
                        f"v15_3_force_recovery_stress_qual_{suite}_"
                        f"task{task_id}_init{init_state_id}"
                    ),
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": init_state_id,
                    "bddl_path": str(source["bddl_path"]),
                    "environment_seed": 4509,
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
        raise V15ForceAttributedRecoveryQualificationFreezeError(
            "worktree must be clean before v15.3 qualification freeze"
        )
    clean = load_json_object(V14_CLEAN_PROTOCOL_PATH)
    v14_qualification = load_json_object(
        V14_STRESS_QUALIFICATION_PROTOCOL_PATH
    )
    v15_development = load_json_object(V15_2_DEVELOPMENT_PROTOCOL_PATH)
    calibration_protocol = load_json_object(V15_2_CALIBRATION_PROTOCOL_PATH)
    fresh2_protocol = load_json_object(V15_2_FRESH2_PROTOCOL_PATH)
    fresh2_terminal = load_json_object(V15_2_FRESH2_TERMINAL_PATH)
    force_protocol = load_json_object(FORCE_DEVELOPMENT_PROTOCOL_PATH)
    force_terminal = load_json_object(FORCE_DEVELOPMENT_TERMINAL_PATH)
    frozen_gates = force_terminal.get(
        "frozen_future_qualification_gates"
    )
    if (
        len(clean.get("workloads", ())) != 45
        or len(v14_qualification.get("environments", ())) != 18
        or len(v15_development.get("schedule", ())) != 28
        or len(calibration_protocol.get("environments", ())) != 12
        or len(fresh2_protocol.get("environments", ())) != 18
        or fresh2_terminal.get("registered_qualification_pass") is not False
        or fresh2_terminal.get("registered_result_unchanged") is not True
        or len(force_protocol.get("environments", ())) != 18
        or force_terminal.get("development_data_complete") is not True
        or force_terminal.get("registered_as_qualification_pass") is not False
        or force_terminal.get("next_stage_decision", {}).get(
            "freeze_new_held_out_qualification_protocol"
        )
        is not True
        or not isinstance(frozen_gates, dict)
    ):
        raise V15ForceAttributedRecoveryQualificationFreezeError(
            "v15.3 qualification predecessors differ"
        )
    prior_pairs = _pairs(clean["workloads"])
    prior_pairs.update(_pairs(v14_qualification["environments"]))
    prior_pairs.update(_pairs(v15_development["schedule"]))
    prior_pairs.update(_pairs(calibration_protocol["environments"]))
    prior_pairs.update(_pairs(fresh2_protocol["environments"]))
    prior_pairs.update(_pairs(force_protocol["environments"]))
    environments = _select_environments(clean["workloads"], prior_pairs)
    if _pairs(environments) & prior_pairs:
        raise V15ForceAttributedRecoveryQualificationFreezeError(
            "v15.3 held-out population overlaps prior exact task/init pairs"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": (
            "held_out_outcome_blind_force_attributed_recovery_"
            "stress_qualification"
        ),
        "pass_classification": (
            "predictive_virtual_brake_v15_3_force_attributed_"
            "recovery_stress_qualification_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_3_force_attributed_"
            "recovery_stress_qualification_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_3_"
            "force_attributed_recovery_stress_qualification_"
            "20260731_fresh1"
        ),
        "required_bindings": [
            _binding(V14_CLEAN_PROTOCOL_PATH),
            _binding(V14_STRESS_QUALIFICATION_PROTOCOL_PATH),
            _binding(V15_2_DEVELOPMENT_PROTOCOL_PATH),
            _binding(V15_2_CALIBRATION_PROTOCOL_PATH),
            _binding(V15_2_FRESH2_PROTOCOL_PATH),
            _binding(V15_2_FRESH2_TERMINAL_PATH),
            _binding(FORCE_DEVELOPMENT_PROTOCOL_PATH),
            _binding(FORCE_DEVELOPMENT_TERMINAL_PATH),
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
            "environment_seed": 4509,
            "development_results_observed_before_freeze": True,
            "qualification_results_observed_before_freeze": False,
            "task_outcomes_used_for_selection": False,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [
                dict(row) for row in runner.calibration.v14.pilot.DOSES
            ],
            "baselines": list(runner.BASELINES),
            "horizon_steps": (
                runner.calibration.v14.pilot.HORIZON_STEPS
            ),
            "hold_action": (
                runner.calibration.v14.pilot.HOLD_ACTION.tolist()
            ),
            "primary_pair": [
                "v14_predictive_brake",
                runner.V15_BASELINE,
            ],
            "stress_activation_control": "no_guard",
            "mechanism_parameters_unchanged_from_v15_2": True,
            "force_attribution_changes_mechanism": False,
            "same_environment_shadow_baseline_included": False,
        },
        "analysis": {
            "role": (
                "held-out outcome-blind force-attributed simulator "
                "recovery qualification"
            ),
            "primary_estimands": [
                "v15.3 crossing, below-floor, and residual-deadlock counts",
                "paired v14 deadlock and v15.3 prevention identity",
                "executed-step availability",
                "per-risk-DOF attributable force increments",
            ],
            "system_estimands": [
                "100-ms research-simulator latency budget",
                "absolute and v14-relative attributable force envelopes",
                "post-step absolute and incremental force envelopes",
                "active contact warnings and saturation",
                "prediction-execution margin error",
            ],
            "legacy_total_force_is_diagnostic": True,
            "same_environment_shadow_trace_identity_measured": False,
            "fresh2_nonpass_superseded": False,
            "task_outcome_qualification_is_separate": True,
        },
        "gates": {
            **dict(frozen_gates),
            "expected_stress_lanes_per_environment": 42,
            "latency_budget_seconds": 0.10,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "held_out_mechanism_claim": True,
            "task_utility_claim": False,
            "same_environment_shadow_trace_identity_claim": False,
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
            "This qualification uses eighteen new exact task/init pairs "
            "and seed 4509, loads no policy, and reads no reward, done, "
            "task success, cost, or collision. A pass may support held-out "
            "simulator joint-limit-proxy containment, recovery from v14 "
            "predictive deadlock, availability, attributable generalized-"
            "constraint-force, and registered research-simulator latency "
            "claims under the frozen stress model. It does not supersede "
            "the fresh2 nonpass or establish exact same-environment shadow "
            "trace identity, task utility, attacked efficacy, real-time "
            "deployment, hardware behavior, actuator authority, or "
            "physical safety."
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
    protocol = build_protocol(
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
    text = canonical_text(protocol)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15ForceAttributedRecoveryQualificationFreezeError(
                f"v15.3 qualification protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
