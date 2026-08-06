#!/usr/bin/env python3
"""Freeze v15.5 development on the disclosed v15.4 qualification lanes."""

from __future__ import annotations

import argparse
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
from scripts import (  # noqa: E402
    run_v15_force_constrained_physics_development as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_force_constrained_physics_development.py"
)
PREDECESSOR_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_domain_robustness_qualification_protocol.json"
)
PREDECESSOR_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_domain_robustness_qualification_terminal_summary.json"
)
V154_DEVELOPMENT_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_dynamic_state_"
    "physics_development_terminal_summary.json"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "src/proofalign/policy_shadow_gripper_state_v15.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
    "scripts/run_l2_predictive_virtual_brake_v15_dynamic_state_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_force_constrained_recovery.py",
    "scripts/run_v15_dynamic_state_physics_development.py",
    "scripts/run_v15_force_constrained_physics_development.py",
    "scripts/freeze_v15_force_constrained_physics_development.py",
    "tests/test_v15_force_constrained_recovery.py",
    "tests/test_v15_force_constrained_physics_development.py",
    "tests/test_freeze_v15_force_constrained_physics_development.py",
    "external/LIBERO-Safety/libero/libero/envs/bddl_base_domain.py",
    "external/LIBERO-Safety/libero/libero/envs/utils.py",
    "external/LIBERO-Safety/third_party/robosuite-1.4/robosuite/models/grippers/panda_gripper.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-5-force-constrained-"
    "physics-development-20260801"
)
CREATED_AT = "2026-08-01T05:00:00+08:00"


class V15ForceConstrainedPhysicsFreezeError(RuntimeError):
    """Raised when the v15.5 development protocol cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15ForceConstrainedPhysicsFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15ForceConstrainedPhysicsFreezeError(
            f"v15.5 development predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15ForceConstrainedPhysicsFreezeError(
            "worktree must be clean before v15.5 development freeze"
        )
    predecessor = load_json_object(PREDECESSOR_PROTOCOL)
    terminal = load_json_object(PREDECESSOR_TERMINAL)
    if (
        terminal.get("registered_qualification_pass") is not False
        or terminal.get("next_stage_decision", {}).get(
            "develop_force_constrained_successor"
        )
        is not True
        or terminal.get("next_stage_decision", {}).get(
            "preserve_nonpass_without_rerun_or_threshold_relaxation"
        )
        is not True
    ):
        raise V15ForceConstrainedPhysicsFreezeError(
            "v15.4 nonpass did not authorize v15.5 development"
        )
    environments = [dict(row) for row in predecessor["environments"]]
    if len(environments) != 18:
        raise V15ForceConstrainedPhysicsFreezeError(
            "v15.5 disclosed population differs"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    source_hashes = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise V15ForceConstrainedPhysicsFreezeError(
                f"v15.5 development source is absent: {relative}"
            )
        source_hashes[relative] = file_sha256(path)
    conditions = [dict(row) for row in runner.PHYSICS_CONDITIONS]
    gates = dict(predecessor["gates"])
    gates.update(
        {
            "expected_v15_5_policy_step_count": 26460,
            "minimum_force_rejected_base_eligible_candidate_count": 1,
        }
    )
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": "outcome_disclosed_v15_5_force_constrained_development",
        "pass_classification": (
            "predictive_virtual_brake_v15_5_force_constrained_"
            "physics_development_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_5_force_constrained_"
            "physics_development_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_5_"
            "force_constrained_physics_development_20260801_fresh1"
        ),
        "required_bindings": [
            _binding(PREDECESSOR_PROTOCOL),
            _binding(PREDECESSOR_TERMINAL),
            _binding(V154_DEVELOPMENT_TERMINAL),
        ],
        "environments": environments,
        "design": {
            "joint_count": 7,
            "joint_sides": ["lower", "upper"],
            "joint_side_count_per_environment": 14,
            "doses": [dict(row) for row in predecessor["design"]["doses"]],
            "baselines": list(runner.BASELINES),
            "horizon_steps": 5,
            "hold_action": list(predecessor["design"]["hold_action"]),
            "physics_conditions": conditions,
            "condition_count": len(conditions),
            "paired_lane_identity_across_conditions": True,
            "parameter_changes_apply_to_shadow_and_actual": True,
            "model_mismatch_injected": False,
            "force_constrained_guard_solref": list(
                runner.recovery.FORCE_CONSTRAINED_GUARD_SOLREF
            ),
            "guard_solimp_unchanged": True,
            "candidate_margins_order_unchanged": True,
            "candidate_post_force_prediction_active": True,
            "registered_force_thresholds_unchanged": True,
            "source_policy_action_unchanged": True,
            "outer_baseline_snapshot_uses_v15_4_dynamic_state": True,
            "predictive_shadow_snapshot_uses_v15_4_dynamic_state": True,
            "gripper_current_action_bound": True,
            "dynamic_motion_generator_phase_bound": True,
            "dynamic_environment_count": predecessor["design"][
                "dynamic_environment_count"
            ],
            "qualification_population": False,
            "outcome_disclosed_population_reused": True,
        },
        "gates": gates,
        "execution_authorization": {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "outcome_disclosed_development": True,
            "qualification_claim": False,
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
            "This outcome-disclosed development reuses the complete frozen "
            "v15.4 held-out physics qualification population after its registered "
            "NONPASS. v15.5 changes only the simulator guard solver time constant "
            "from 0.004 to 0.006 and requires every selected candidate to satisfy "
            "the unchanged registered scope and predicted post-step force envelopes. "
            "The source action, candidate margins and order, safety floor, physics "
            "conditions, and all thresholds remain unchanged. A pass may select "
            "v15.5 for a separately frozen fresh qualification; it cannot revise "
            "the v15.4 NONPASS or support qualification, model-mismatch, task-utility, "
            "hard-real-time, hardware, actuator-authority, or physical-safety claims."
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
        raise V15ForceConstrainedPhysicsFreezeError(
            "v15.5 development protocol already exists"
        )
    protocol = build_protocol(
        created_at=args.created_at, source_commit=args.source_commit
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
                "condition_count": len(protocol["design"]["physics_conditions"]),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
