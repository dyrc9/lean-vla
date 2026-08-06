#!/usr/bin/env python3
"""Freeze the outcome-disclosed v15.4 dynamic-state physics development."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
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
from scripts import run_v15_dynamic_state_physics_development as runner  # noqa: E402


CREATED_AT = "2026-08-01T10:30:00+08:00"
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
PREDECESSOR_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_physics_domain_robustness_qualification_protocol.json"
)
PREDECESSOR_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_physics_domain_robustness_qualification_terminal_summary.json"
)
COMPONENT_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_recovery_component_"
    "ablation_qualification_terminal_summary.json"
)
SOURCE_FILES = (
    "external/LIBERO-Safety/libero/libero/envs/bddl_base_domain.py",
    "external/LIBERO-Safety/libero/libero/envs/utils.py",
    "external/LIBERO-Safety/third_party/robosuite-1.4/robosuite/models/grippers/panda_gripper.py",
    "scripts/run_l2_predictive_virtual_brake_v14_multijoint.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_priority_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_current_edge_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_floor_guard_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_force_attributed_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_dynamic_state_recovery.py",
    "scripts/run_v14_multijoint_stress_design_pilot.py",
    "scripts/run_v14_multijoint_stress_development.py",
    "scripts/run_v14_multijoint_stress_qualification.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_calibration.py",
    "scripts/run_v15_force_attribution_stress_development.py",
    "scripts/run_v15_force_attributed_recovery_stress_qualification.py",
    "scripts/run_v15_force_attributed_recovery_physics_domain_robustness_qualification.py",
    "scripts/run_v15_dynamic_state_physics_development.py",
    "scripts/freeze_v15_dynamic_state_physics_development.py",
    "src/proofalign/policy_prefix_shadow_v12.py",
    "src/proofalign/policy_prefix_shadow_warmstart_v12.py",
    "src/proofalign/policy_shadow_gripper_state_v15.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
    "tests/test_policy_shadow_gripper_state_v15.py",
    "tests/test_v15_dynamic_state_recovery.py",
    "tests/test_v15_dynamic_state_physics_development.py",
)


class V15DynamicStatePhysicsFreezeError(RuntimeError):
    """Raised when v15.4 development cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15DynamicStatePhysicsFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15DynamicStatePhysicsFreezeError(
            f"required v15.4 binding is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def _dynamic_environment_count(
    environments: list[Mapping[str, Any]],
) -> int:
    count = 0
    for spec in environments:
        path = REPO_ROOT / str(spec["bddl_path"])
        if not path.is_file():
            raise V15DynamicStatePhysicsFreezeError(
                f"v15.4 environment BDDL is absent: {path}"
            )
        count += int("(:dynamics" in path.read_text(encoding="utf-8"))
    return count


def _verify_predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = load_json_object(PREDECESSOR_PROTOCOL)
    terminal = load_json_object(PREDECESSOR_TERMINAL)
    if (
        terminal.get("registered_classification")
        != (
            "predictive_virtual_brake_v15_3_force_attributed_recovery_"
            "physics_domain_robustness_qualification_nonpass"
        )
        or terminal.get("registered_qualification_pass") is not False
        or "all_condition_registered_gates"
        not in terminal.get("failed_registered_gates", ())
        or len(
            terminal.get("cross_condition", {}).get(
                "recovery_attributable_force_nonpass_conditions", ()
            )
        )
        != 6
        or terminal.get("registered_result_unchanged") is not True
        or terminal.get("bindings", {}).get("protocol", {}).get("sha256")
        != file_sha256(PREDECESSOR_PROTOCOL)
        or len(protocol.get("environments", ())) != 18
        or _dynamic_environment_count(protocol["environments"]) != 15
    ):
        raise V15DynamicStatePhysicsFreezeError(
            "v15.3 disclosed NONPASS does not authorize v15.4 development"
        )
    return protocol, terminal


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15DynamicStatePhysicsFreezeError(
            "worktree must be clean before v15.4 development freeze"
        )
    commit = source_commit or _git("rev-parse", "HEAD")
    tree = _git("rev-parse", f"{commit}^{{tree}}")
    predecessor_protocol, _terminal = _verify_predecessor()
    source_hashes = {}
    for relative in SOURCE_FILES:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise V15DynamicStatePhysicsFreezeError(
                f"v15.4 source is absent: {relative}"
            )
        source_hashes[relative] = file_sha256(path)
    environments = []
    for row in predecessor_protocol["environments"]:
        copied = deepcopy(dict(row))
        copied["environment_id"] = str(copied["environment_id"]).replace(
            "v15_3_physics_robust",
            "v15_4_dynamic_state_physics_dev",
        )
        environments.append(copied)
    condition_count = len(runner.predecessor.PHYSICS_CONDITIONS)
    lanes_per_condition = len(environments) * 7 * 2 * 3
    policy_steps = lanes_per_condition * condition_count * 5
    dynamic_environment_count = _dynamic_environment_count(environments)
    dynamic_steps = (
        dynamic_environment_count * 7 * 2 * 3 * condition_count * 5
    )
    design = deepcopy(dict(predecessor_protocol["design"]))
    design.update(
        {
            "baselines": list(runner.BASELINES),
            "outcome_disclosed_population_reused": True,
            "mechanism_parameters_unchanged_from_v15_3": True,
            "guard_candidates_order_thresholds_actions_unchanged": True,
            "outer_baseline_snapshot_uses_v15_4_dynamic_state": True,
            "predictive_shadow_snapshot_uses_v15_4_dynamic_state": True,
            "gripper_current_action_bound": True,
            "dynamic_motion_generator_phase_bound": True,
            "dynamic_environment_count": dynamic_environment_count,
            "qualification_population": False,
        }
    )
    gates = runner._replace_names(
        deepcopy(dict(predecessor_protocol["gates"]))
    )
    gates.update(
        {
            "expected_v15_4_policy_step_count": policy_steps,
            "minimum_dynamic_motion_generator_step_count": dynamic_steps,
        }
    )
    return {
        "schema": runner.PROTOCOL_SCHEMA,
        "status": runner.AUTHORIZED_STATUS,
        "protocol_id": (
            "proofalign-predictive-virtual-brake-v15-4-dynamic-state-"
            "physics-development-20260801"
        ),
        "created_at": created_at,
        "source": {
            "repository_commit": commit,
            "repository_tree": tree,
            "freezer": (
                "scripts/freeze_v15_dynamic_state_physics_development.py"
            ),
            "freezer_sha256": source_hashes[
                "scripts/freeze_v15_dynamic_state_physics_development.py"
            ],
            "sha256": source_hashes,
        },
        "required_bindings": [
            _binding(PREDECESSOR_PROTOCOL),
            _binding(PREDECESSOR_TERMINAL),
            _binding(COMPONENT_TERMINAL),
        ],
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
        "design": design,
        "gates": gates,
        "environments": environments,
        "fresh_output_root": (
            "results/proofalign_predictive_virtual_brake_v15_4_"
            "dynamic_state_physics_development_20260801_fresh1"
        ),
        "pass_classification": (
            "predictive_virtual_brake_v15_4_dynamic_state_"
            "physics_development_pass"
        ),
        "nonpass_classification": (
            "predictive_virtual_brake_v15_4_dynamic_state_"
            "physics_development_nonpass"
        ),
        "claim_boundary": (
            "This result-informed development reuses the fully disclosed "
            "v15.3 physics population and all frozen safety, liveness, "
            "force, and latency thresholds. It changes only snapshot "
            "coverage by binding the Panda gripper current_action and "
            "LIBERO-Safety dynamic-motion generator phase in both outer "
            "baseline restores and predictive shadows. A pass may select "
            "v15.4 for a separately frozen fresh qualification; it cannot "
            "revise the v15.3 NONPASS or authorize qualification, model-"
            "mismatch, task-utility, real-time, hardware, actuator-"
            "authority, or physical-safety claims."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.force:
        raise V15DynamicStatePhysicsFreezeError(
            "v15.4 development protocol exists; use --force deliberately"
        )
    protocol = build_protocol(created_at=args.created_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(protocol), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
