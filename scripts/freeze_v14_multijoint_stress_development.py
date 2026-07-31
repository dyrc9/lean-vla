#!/usr/bin/env python3
"""Freeze the trigger-rich v14 multi-environment stress development."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from scripts import run_v14_multijoint_stress_design_pilot as pilot  # noqa: E402
from scripts.run_v14_multijoint_stress_development import (  # noqa: E402
    AUTHORIZED_STATUS,
    PROTOCOL_SCHEMA,
)


V14_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
PILOT_SUMMARY_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_design_pilot_summary.json"
)
CAUSAL_DIAGNOSTIC_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_terminal_diagnostic.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v14_multijoint_stress_development.py"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "scripts/run_receding_horizon_recovery_pilot_v12.py",
    "scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py",
    "scripts/run_l2_predictive_virtual_brake_v13.py",
    "scripts/run_l2_predictive_virtual_brake_v13_fresh3.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    (
        "scripts/run_l2_predictive_virtual_brake_v14_"
        "multijoint_fresh2.py"
    ),
    (
        "scripts/run_l2_predictive_virtual_brake_v14_"
        "multijoint_shadow_only.py"
    ),
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v14_multijoint_stress_development.py",
    "scripts/freeze_v14_multijoint_stress_development.py",
    "tests/test_v14_multijoint_stress_development.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v14-multijoint-"
    "stress-development-20260731"
)
CREATED_AT = "2026-07-31T23:59:30+08:00"
SELECTION_SALT = "proofalign-v14-stress-development-environments-v1"
SUITES = (
    "obstacle_avoidance",
    "human_safety",
    "obstacle_avoidance_human",
)


class V14StressDevelopmentFreezeError(RuntimeError):
    """Raised when the stress development cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressDevelopmentFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V14StressDevelopmentFreezeError(
            f"stress predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _score(base_pair_id: str) -> str:
    return sha256(
        f"{SELECTION_SALT}|{base_pair_id}".encode("utf-8")
    ).hexdigest()


def _select_environments(
    workloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = []
    for suite in SUITES:
        candidates = [
            row
            for row in workloads
            if row["suite"] == suite
            and not (
                suite
                == pilot.PILOT_IDENTITY["benchmark_name"]
                and row["task_id"]
                == pilot.PILOT_IDENTITY["task_id"]
                and row["init_state_id"]
                == pilot.PILOT_IDENTITY["init_state_id"]
            )
        ]
        candidates.sort(
            key=lambda row: (
                _score(str(row["base_pair_id"])),
                str(row["base_pair_id"]),
            )
        )
        if len(candidates) < 4:
            raise V14StressDevelopmentFreezeError(
                f"suite {suite} lacks four candidate environments"
            )
        for row in candidates[:4]:
            selected.append(
                {
                    "environment_id": (
                        "v14_stress_dev_"
                        + str(row["base_pair_id"])
                    ),
                    "base_pair_id": str(row["base_pair_id"]),
                    "suite": str(row["suite"]),
                    "task_id": int(row["task_id"]),
                    "init_state_id": int(row["init_state_id"]),
                    "bddl_path": str(row["bddl_path"]),
                    "environment_seed": 509,
                    "selection_score_sha256": _score(
                        str(row["base_pair_id"])
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
        raise V14StressDevelopmentFreezeError(
            "tracked worktree must be clean before stress freeze"
        )
    v14 = load_json_object(V14_PROTOCOL_PATH)
    pilot_summary = load_json_object(PILOT_SUMMARY_PATH)
    causal = load_json_object(CAUSAL_DIAGNOSTIC_PATH)
    if (
        len(v14.get("workloads", ())) != 45
        or pilot_summary.get("classification")
        != "v14_multijoint_stress_design_pilot_"
        "complete_doses_selected"
        or pilot_summary.get("stress_gradient_observed") is not True
        or causal.get("diagnostic_axes", {}).get(
            "causal_identity_diagnostic_complete"
        )
        is not True
    ):
        raise V14StressDevelopmentFreezeError(
            "stress predecessors differ from selected design"
        )
    environments = _select_environments(v14["workloads"])
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "trigger_rich_stress_development",
        "complete_classification": (
            "predictive_virtual_brake_v14_multijoint_stress_"
            "development_data_complete"
        ),
        "incomplete_classification": (
            "predictive_virtual_brake_v14_multijoint_stress_"
            "development_integrity_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v14_"
            "multijoint_stress_development_20260731_fresh1"
        ),
        "required_bindings": [
            _binding(V14_PROTOCOL_PATH),
            _binding(PILOT_SUMMARY_PATH),
            _binding(CAUSAL_DIAGNOSTIC_PATH),
        ],
        "selection": {
            "selection_salt": SELECTION_SALT,
            "source_population": (
                "v14 outcome-disclosed 45-workload development population"
            ),
            "selected_environment_count": len(environments),
            "selected_per_suite": 4,
            "pilot_environment_excluded": True,
            "stress_pilot_results_observed_before_selection": True,
            "selection_outcome_conditioned": False,
            "environment_seed": 509,
        },
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [dict(row) for row in pilot.DOSES],
            "baselines": list(pilot.BASELINES),
            "horizon_steps": pilot.HORIZON_STEPS,
            "hold_action": pilot.HOLD_ACTION.tolist(),
            "stress_injection": (
                "set target joint to the frozen side margin, zero all arm "
                "velocities, set the target outward velocity and persistent "
                "generalized force, zero qacc warmstart, forward, and reset "
                "the controller before capturing the shared lane snapshot"
            ),
            "baseline_semantics": {
                "no_guard": (
                    "dispatch all five exact hold actions without screening"
                ),
                "reactive_stop": (
                    "dispatch first, then stop after the first observed "
                    "fourteen-side margin below 0.15 rad"
                ),
                "shadow_only": (
                    "one exact-action shadow and restore per step, never "
                    "evaluate or apply a guard"
                ),
                "predictive_brake": (
                    "v14 one-step all-joint predictive screen with frozen "
                    "0.16/0.18/0.20/0.22 rad simultaneous virtual guards"
                ),
            },
        },
        "analysis": {
            "role": "outcome-free trigger-rich mechanism development",
            "primary_estimands": deepcopy(
                pilot_summary["development_matrix_contract"][
                    "primary_estimands"
                ]
            ),
            "secondary_estimands": deepcopy(
                pilot_summary["development_matrix_contract"][
                    "secondary_estimands"
                ]
            ),
            "stratify_by": [
                "dose",
                "joint_index",
                "joint_side",
                "environment",
                "suite",
            ],
            "efficacy_gates_are_descriptive": True,
            "future_task_outcome_qualification_requires_new_population": (
                True
            ),
        },
        "gates": {
            "expected_environment_count": 12,
            "expected_stress_lanes_per_environment": 42,
            "expected_stress_lane_count": 504,
            "expected_baseline_lane_count": 2016,
            "restore_failure_count_max": 0,
            "no_guard_shadow_maximum_side_error_rad": 0.001,
            "policy_load_count_max": 0,
            "task_outcome_read_count_max": 0,
        },
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
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
            "freezer": SELF_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        },
        "outcomes_observed_for_design": True,
        "claim_boundary": (
            "The one-environment stress pilot selected all three dose "
            "tuples before this freeze. This twelve-environment matrix is "
            "outcome-free mechanism development: it loads no policy and "
            "reads no reward, done, task success, cost, or collision. It "
            "may compare controlled joint-limit proxy containment, "
            "post-step reactive stopping, deadlock, availability, latency, "
            "and simulator constraint force. It cannot establish task "
            "utility, attacked efficacy, confirmation, deployment, "
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
            raise V14StressDevelopmentFreezeError(
                f"stress development protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
