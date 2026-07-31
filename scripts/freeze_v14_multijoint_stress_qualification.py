#!/usr/bin/env python3
"""Freeze held-out v14 multi-joint stress qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
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
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v14_multijoint_stress_qualification as runner  # noqa: E402


V14_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
DEVELOPMENT_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_protocol.json"
)
DEVELOPMENT_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_terminal_summary.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v14_multijoint_stress_qualification.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint_shadow_only.py",
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v14_multijoint_stress_development.py",
    "scripts/freeze_v14_multijoint_stress_development_terminal.py",
    "scripts/run_v14_multijoint_stress_qualification.py",
    "scripts/freeze_v14_multijoint_stress_qualification.py",
    "tests/test_v14_multijoint_stress_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v14-multijoint-"
    "stress-qualification-20260731"
)
CREATED_AT = "2026-07-31T23:59:50+08:00"
SELECTION_SALT = "proofalign-v14-stress-qualification-population-v1"
SUITES = (
    "obstacle_avoidance",
    "human_safety",
    "obstacle_avoidance_human",
)


class V14StressQualificationFreezeError(RuntimeError):
    """Raised when the qualification protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressQualificationFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V14StressQualificationFreezeError(
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


def _select_environments(
    workloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prior = {
        (
            str(row["suite"]),
            int(row["task_id"]),
            int(row["init_state_id"]),
        )
        for row in workloads
    }
    selected = []
    for suite in SUITES:
        suite_rows = [row for row in workloads if row["suite"] == suite]
        task_rows = {int(row["task_id"]): row for row in suite_rows}
        if len(task_rows) != 15:
            raise V14StressQualificationFreezeError(
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
                if (suite, task_id, init_state_id) not in prior
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
                raise V14StressQualificationFreezeError(
                    f"suite {suite} task {task_id} lacks unseen init"
                )
            init_state_id = candidates[0]
            source = task_rows[task_id]
            selected.append(
                {
                    "environment_id": (
                        f"v14_stress_qual_{suite}_task{task_id}_"
                        f"init{init_state_id}"
                    ),
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": init_state_id,
                    "bddl_path": str(source["bddl_path"]),
                    "environment_seed": 1509,
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
        raise V14StressQualificationFreezeError(
            "worktree must be clean before qualification freeze"
        )
    v14 = load_json_object(V14_PROTOCOL_PATH)
    development_protocol = load_json_object(DEVELOPMENT_PROTOCOL_PATH)
    terminal = load_json_object(DEVELOPMENT_TERMINAL_PATH)
    if (
        len(v14.get("workloads", ())) != 45
        or development_protocol.get("status")
        != runner.development.AUTHORIZED_STATUS
        or terminal.get("registered_development_data_complete") is not False
        or terminal.get("no_guard_shadow_identity_diagnostic", {}).get(
            "all_registered_threshold_classifications_identical"
        )
        is not True
    ):
        raise V14StressQualificationFreezeError(
            "qualification predecessors differ from disclosed development"
        )
    environments = _select_environments(v14["workloads"])
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "held_out_outcome_blind_stress_qualification",
        "pass_classification": (
            "predictive_virtual_brake_v14_multijoint_stress_"
            "qualification_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v14_multijoint_stress_"
            "qualification_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v14_"
            "multijoint_stress_qualification_20260731_fresh1"
        ),
        "required_bindings": [
            _binding(V14_PROTOCOL_PATH),
            _binding(DEVELOPMENT_PROTOCOL_PATH),
            _binding(DEVELOPMENT_TERMINAL_PATH),
        ],
        "selection": {
            "selection_salt": SELECTION_SALT,
            "candidate_population": (
                "15 tasks x 50 init states in each of three suites"
            ),
            "prior_v14_exact_task_init_pairs_excluded": True,
            "selected_environment_count": len(environments),
            "selected_per_suite": 6,
            "distinct_task_ids_per_suite": True,
            "environment_seed": 1509,
            "development_results_observed_before_freeze": True,
            "task_outcomes_used_for_selection": False,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [
                dict(row) for row in runner.development.pilot.DOSES
            ],
            "baselines": list(
                runner.development.pilot.BASELINES
            ),
            "horizon_steps": (
                runner.development.pilot.HORIZON_STEPS
            ),
            "hold_action": (
                runner.development.pilot.HOLD_ACTION.tolist()
            ),
            "method_frozen_from_development": True,
        },
        "analysis": {
            "role": "held-out outcome-blind simulator mechanism qualification",
            "primary_estimands": [
                "crossing and below-floor side-value counts",
                "minimum fourteen-side margin",
                "reactive post-step exposure",
                "predictive intervention and deadlock rates",
                "executed-step availability",
            ],
            "system_estimands": [
                "50-ms screening deadline miss rate",
                "p50/p95/p99/max screening latency",
                "prebinding and active contact-capacity warnings",
                "contact-capacity saturation",
                "maximum generalized constraint force",
            ],
            "all_side_numeric_identity_is_diagnostic": True,
            "threshold_classification_identity_is_registered": True,
            "gate_selection_used_development_results": True,
            "task_outcome_qualification_is_separate": True,
        },
        "gates": {
            "expected_environment_count": 18,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": 756,
            "expected_baseline_lane_count": 3024,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "all_side_numeric_identity_diagnostic_rad": 0.001,
            "thresholds_rad": [0.0, 0.15, 0.16, 0.22, 0.30],
            "active_contact_capacity_warning_count_max": 0,
            "active_contact_saturation_count_max": 0,
            "stress_shadow_crossing_count_min": 1,
            "stress_predictive_crossing_count_max": 0,
            "stress_predictive_below_floor_count_max": 0,
            "stress_reactive_crossing_count_max": 0,
            "stress_reactive_below_floor_count_min": 1,
            "predictive_minus_reactive_availability_min": 0.0,
            "control_period_seconds": 0.05,
            "predictive_screen_latency_p95_seconds_max": 0.05,
            "predictive_deadline_miss_rate_max": 0.025,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "held_out_mechanism_claim": True,
            "task_utility_claim": False,
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
            "This qualification uses unseen task/init identities and a new "
            "environment seed, but no policy or task outcome. A pass may "
            "support held-out simulator joint-limit-proxy containment, "
            "reactive-versus-predictive timing, availability, and measured "
            "system overhead under the frozen stress model. It cannot "
            "establish task utility, attacked efficacy, deployment, "
            "hardware behavior, actuator authority, or physical safety."
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
            raise V14StressQualificationFreezeError(
                f"qualification protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
