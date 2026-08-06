#!/usr/bin/env python3
"""Freeze v15.7 incremental-search development."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
    run_v15_incremental_adaptive_force_physics_development as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_incremental_adaptive_force_physics_development.py"
)
PREDECESSOR_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_adaptive_force_"
    "physics_development_protocol.json"
)
PREDECESSOR_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_adaptive_force_"
    "physics_development_terminal_summary.json"
)
SOURCE_PATHS = (
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "src/proofalign/policy_shadow_gripper_state_v15.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
    "scripts/run_l2_predictive_virtual_brake_v15_dynamic_state_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_force_constrained_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_adaptive_force_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_incremental_adaptive_force_recovery.py",
    "scripts/run_v15_dynamic_state_physics_development.py",
    "scripts/run_v15_force_constrained_physics_development.py",
    "scripts/run_v15_adaptive_force_physics_development.py",
    "scripts/run_v15_incremental_adaptive_force_physics_development.py",
    "scripts/freeze_v15_incremental_adaptive_force_physics_development.py",
    "scripts/diagnose_v15_7_disclosed_cases.py",
    "tests/test_v15_incremental_adaptive_force_recovery.py",
    "tests/test_v15_incremental_adaptive_force_physics_development.py",
    "tests/test_freeze_v15_incremental_adaptive_force_physics_development.py",
    "external/LIBERO-Safety/libero/libero/envs/bddl_base_domain.py",
    "external/LIBERO-Safety/libero/libero/envs/utils.py",
    "external/LIBERO-Safety/third_party/robosuite-1.4/robosuite/models/grippers/panda_gripper.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-7-incremental-adaptive-force-"
    "physics-development-20260801"
)
CREATED_AT = "2026-08-01T12:30:00+08:00"


class V15IncrementalAdaptiveForcePhysicsFreezeError(RuntimeError):
    """Raised when v15.7 development cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15IncrementalAdaptiveForcePhysicsFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15IncrementalAdaptiveForcePhysicsFreezeError(
            f"v15.7 predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def build_protocol(
    *, created_at: str = CREATED_AT, source_commit: str | None = None
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15IncrementalAdaptiveForcePhysicsFreezeError(
            "worktree must be clean before v15.7 development freeze"
        )
    predecessor = load_json_object(PREDECESSOR_PROTOCOL)
    terminal = load_json_object(PREDECESSOR_TERMINAL)
    if (
        terminal.get("registered_development_pass") is not False
        or terminal.get("registered_result_unchanged") is not True
        or terminal.get("next_stage_decision", {}).get(
            "develop_incremental_extended_search_successor"
        )
        is not True
        or terminal.get("next_stage_decision", {}).get(
            "correct_extended_recovery_force_attribution"
        )
        is not True
        or terminal.get("nonpass_axes")
        != {"v15_3_latency_max": ["arm_friction_0_7x"]}
    ):
        raise V15IncrementalAdaptiveForcePhysicsFreezeError(
            "v15.6 NONPASS did not authorize v15.7 development"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    source_hashes = {}
    for relative in SOURCE_PATHS:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise V15IncrementalAdaptiveForcePhysicsFreezeError(
                f"v15.7 source is absent: {relative}"
            )
        source_hashes[relative] = file_sha256(path)
    design = deepcopy(dict(predecessor["design"]))
    design.update(
        {
            "baselines": list(runner.BASELINES),
            "incremental_extended_search": True,
            "maximum_extended_candidates_per_increment": 1,
            "extended_recovery_force_attribution_bound": True,
            "proactive_trigger_and_force_thresholds_unchanged_from_v15_6": True,
        }
    )
    gates = deepcopy(dict(predecessor["gates"]))
    gates.update(
        {
            "expected_v15_7_policy_step_count": 26460,
            "maximum_incremental_extended_candidate_evaluated_per_step": 1,
        }
    )
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "status": runner.AUTHORIZED_STATUS,
        "created_at": created_at,
        "stage": (
            "outcome_disclosed_v15_7_incremental_adaptive_force_development"
        ),
        "pass_classification": (
            "predictive_virtual_brake_v15_7_incremental_adaptive_force_"
            "physics_development_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_7_incremental_adaptive_force_"
            "physics_development_nonpass"
        ),
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_7_"
            "incremental_adaptive_force_physics_development_20260801_fresh1"
        ),
        "required_bindings": [
            _binding(PREDECESSOR_PROTOCOL),
            _binding(PREDECESSOR_TERMINAL),
        ],
        "environments": [
            deepcopy(dict(row)) for row in predecessor["environments"]
        ],
        "design": design,
        "gates": gates,
        "execution_authorization": deepcopy(
            dict(predecessor["execution_authorization"])
        ),
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
            "This outcome-disclosed v15.7 development reuses the complete "
            "v15.6 development population after its immutable latency NONPASS. "
            "It preserves the 0.16 proactive trigger, 0.15 safety floor, candidate "
            "margins, solver profiles, force thresholds, and source actions. It "
            "changes only the extended ladder evaluation from a seven-candidate "
            "batch to ordered one-candidate increments with short-circuiting, and "
            "binds any selected intermediate margin as a recovery intervention "
            "before force attribution. A pass can select v15.7 for a separately "
            "frozen fresh qualification but cannot revise earlier NONPASS results "
            "or support qualification, model-mismatch, task-utility, hard-real-"
            "time, hardware, actuator-authority, or physical-safety claims."
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
        raise V15IncrementalAdaptiveForcePhysicsFreezeError(
            "v15.7 development protocol already exists"
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
