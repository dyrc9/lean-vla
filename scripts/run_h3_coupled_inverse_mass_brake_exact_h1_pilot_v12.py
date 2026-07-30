#!/usr/bin/env python3
"""Evaluate a coupled inverse-mass torque shield for exact H1."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    PolicyPrefixShadowVerdict,
)
from scripts import run_h3_joint_anticipatory_brake_exact_h1_pilot_v12 as predecessor  # noqa: E402
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    RECEDING_CYCLE_COUNT,
    TARGET_ID,
    _run_case,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_joint_anticipatory_brake_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_coupled_inverse_mass_brake_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-coupled-inverse-mass-brake-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-coupled-inverse-mass-brake-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
TARGET_JOINT_INDEX = 1
TARGET_JOINT_SIDE = "upper"
TORQUE_VERTEX_BLEND_FRACTIONS = (0.25, 0.50, 0.75, 1.00)


class H3CoupledInverseMassBrakeExactH1PilotError(RuntimeError):
    """Raised when the coupled-brake pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_joint_anticipatory_brake_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_joint_anticipatory_brake_exact_h1_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("candidate_configuration_count") != 8
        or prior.get("candidate_configuration_qpos_identity_count")
        != 8
        or prior.get("candidate_configuration_qvel_identity_count")
        != 8
        or prior.get("candidate_controller_scope_restore_count") != 8
        or prior.get(
            "joint_anticipatory_brake_exact_h1_authorization_count"
        )
        != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3CoupledInverseMassBrakeExactH1PilotError(
            "single-joint anticipatory nonpass does not authorize successor"
        )
    config = deepcopy(predecessor.pilot_config())
    floor = float(config["recovery"]["safe_margin_rad"])
    config["protocol_id"] = (
        "engineering-h3-coupled-inverse-mass-brake-exact-h1-pilot"
    )
    config[
        "controller_coupled_inverse_mass_brake_exact_h1_contract"
    ] = {
        "type": "coupled_inverse_mass_torque_shield_exact_h1",
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "torque_vertex_blend_fractions": list(
            TORQUE_VERTEX_BLEND_FRACTIONS
        ),
        "vertex_rule": (
            "At every controller substep, solve the joint-1 row of the "
            "inverse mass matrix. Choose each of seven actuator bounds to "
            "minimize the resulting toward-limit acceleration term."
        ),
        "blend_rule": (
            "Interpolate from nominal clipped torque to the maximum "
            "away-acceleration actuator-box vertex."
        ),
        "selection_rule": (
            "Select the smallest blend fraction whose exact one-step "
            "replay stays at or above 0.15 rad and ends with toward-limit "
            "joint-1 velocity no greater than zero."
        ),
        "controller_goal_reset_before_action": True,
        "scope": "one exact source-policy action only",
        "wrapper_removed_immediately_after_action": True,
        "all_torques_within_actuator_limits": True,
        "terminal_non_toward_velocity_required": True,
        "simulator_qpos_modified_by_configuration": False,
        "simulator_qvel_modified_by_configuration": False,
        "exact_source_policy_action_required": True,
        "action_substitution_authorized": False,
        "minimum_margin_floor_rad": floor,
        "strict_no_crossing": True,
        "fresh_replan_after_each_advance": True,
        "recovery_contract_reused": False,
    }
    config["receding_horizon"].update(
        {
            "controller_joint_anticipatory_brake_exact_h1_fractions": [],
            "controller_coupled_inverse_mass_brake_exact_h1_fractions": list(
                TORQUE_VERTEX_BLEND_FRACTIONS
            ),
            "controller_coupled_inverse_mass_brake_target_joint_index": (
                TARGET_JOINT_INDEX
            ),
            "controller_coupled_inverse_mass_brake_target_joint_side": (
                TARGET_JOINT_SIDE
            ),
            "fallback_rule": (
                "After H3 block, restore the bound controller snapshot. "
                "For each frozen blend, reset the end-effector goal without "
                "changing qpos/qvel. At every controller substep of the "
                "same source-policy action, use the inverse-mass joint-1 "
                "row to construct the seven-axis actuator-box vertex with "
                "minimum toward-limit acceleration and blend from nominal "
                "torque. Authorize only if the 0.15-rad floor holds and "
                "terminal toward velocity is nonpositive. Execute the "
                "smallest safe blend and immediately fresh replan."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates a scoped "
        "coupled inverse-mass torque shield after H3 block_replan on the "
        "sole remaining known v12.6 outlier. It executes identical "
        "source-policy action bytes and uses the controller mass matrix to "
        "make the minimum frozen interpolation toward a seven-axis "
        "actuator-box vertex that maximizes joint-1 away-limit acceleration "
        "authority. Candidate eligibility requires the one-step 0.15-rad "
        "position floor, actuator-bound compliance, and nonpositive "
        "terminal toward-limit velocity. The wrapper is removed after one "
        "action and configuration does not change qpos/qvel. No action "
        "substitution, threshold change, live dispatch, typed recovery, or "
        "task-outcome read occurs. It is not qualification, task utility, "
        "deployment, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3CoupledInverseMassBrakeExactH1PilotError(
            "expected exactly the frozen target row"
        )
    row = rows[0]
    cycles = [
        cycle
        for lane in row["lane_results"]
        for cycle in lane["cycles"]
    ]
    attempts = [
        attempt
        for cycle in cycles
        for attempt in cycle["attempts"]
    ]
    fallbacks = [
        fallback
        for cycle in cycles
        for fallback in cycle[
            "coupled_inverse_mass_brake_exact_h1_fallbacks"
        ]
    ]
    authorized = [
        fallback for fallback in fallbacks if fallback["authorized"]
    ]
    executed = [
        fallback
        for fallback in authorized
        if fallback["executed_in_shadow"]
    ]
    candidates = [
        candidate
        for fallback in fallbacks
        for candidate in fallback["candidate_evaluations"]
    ]
    candidate_torque_samples = [
        sample
        for candidate in candidates
        for sample in candidate["controller_substep_torque_audit"]
    ]
    execution_torque_samples = [
        sample
        for fallback in executed
        for sample in fallback[
            "execution_controller_substep_torque_audit"
        ]
    ]
    config = pilot_config()
    contract = config[
        "controller_coupled_inverse_mass_brake_exact_h1_contract"
    ]
    completed_cycle_counts = {
        str(lane["base_seed"]): lane["completed_cycle_count"]
        for lane in row["lane_results"]
    }
    method_success = bool(
        row["receding_horizon_success"]
        and completed_cycle_counts
        == {
            str(seed): RECEDING_CYCLE_COUNT
            for seed in LANE_BASE_SEEDS
        }
        and all(
            fallback["exact_action_identity"] is True
            and fallback["execution_controller_scope_restored"] is True
            and fallback[
                "execution_terminal_non_toward_velocity"
            ]
            is True
            for fallback in executed
        )
        and all(
            candidate["configuration"][
                "configuration_qpos_identity"
            ]
            and candidate["configuration"][
                "configuration_qvel_identity"
            ]
            and candidate["controller_scope_restored"]
            for candidate in candidates
        )
        and not any(
            sample["torque_bound_violation"]
            for sample in (
                candidate_torque_samples + execution_torque_samples
            )
        )
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_coupled_inverse_mass_brake_exact_h1_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "torque_vertex_blend_fractions": list(
            TORQUE_VERTEX_BLEND_FRACTIONS
        ),
        "minimum_margin_floor_rad": contract[
            "minimum_margin_floor_rad"
        ],
        "action_substitution_authorized": False,
        "lane_count": len(row["lane_results"]),
        "lane_base_seeds": row["lane_base_seeds"],
        "planned_cycle_count_per_lane": RECEDING_CYCLE_COUNT,
        "completed_cycle_counts": completed_cycle_counts,
        "safe_lane_count": sum(
            lane["lane_safe"] for lane in row["lane_results"]
        ),
        "h3_coupled_inverse_mass_brake_exact_h1_success": (
            method_success
        ),
        "total_fresh_policy_attempt_count": len(attempts),
        "direct_h3_allow_attempt_count": sum(
            attempt["gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "coupled_inverse_mass_brake_exact_h1_screen_count": len(
            fallbacks
        ),
        "coupled_inverse_mass_brake_exact_h1_authorization_count": len(
            authorized
        ),
        "coupled_inverse_mass_brake_exact_h1_execution_count": len(
            executed
        ),
        "coupled_inverse_mass_brake_exact_h1_exact_action_identity_count": sum(
            fallback["exact_action_identity"] is True
            for fallback in executed
        ),
        "selected_torque_vertex_blend_fractions": [
            fallback["selected_blend_fraction"]
            for fallback in executed
        ],
        "candidate_terminal_non_toward_velocity_count": sum(
            candidate["terminal_non_toward_velocity"]
            for candidate in candidates
        ),
        "execution_terminal_non_toward_velocity_count": sum(
            fallback[
                "execution_terminal_non_toward_velocity"
            ]
            is True
            for fallback in executed
        ),
        "candidate_configuration_qpos_identity_count": sum(
            candidate["configuration"][
                "configuration_qpos_identity"
            ]
            for candidate in candidates
        ),
        "candidate_configuration_qvel_identity_count": sum(
            candidate["configuration"][
                "configuration_qvel_identity"
            ]
            for candidate in candidates
        ),
        "candidate_controller_scope_restore_count": sum(
            candidate["controller_scope_restored"]
            for candidate in candidates
        ),
        "candidate_configuration_count": len(candidates),
        "execution_controller_scope_restore_count": sum(
            fallback["execution_controller_scope_restored"] is True
            for fallback in executed
        ),
        "candidate_controller_substep_torque_sample_count": len(
            candidate_torque_samples
        ),
        "execution_controller_substep_torque_sample_count": len(
            execution_torque_samples
        ),
        "torque_bound_violation_count": sum(
            sample["torque_bound_violation"]
            for sample in (
                candidate_torque_samples + execution_torque_samples
            )
        ),
        "vertex_toward_acceleration_improvement_count": sum(
            sample["vertex_toward_acceleration_term"]
            <= sample["nominal_toward_acceleration_term"] + 1e-12
            for sample in candidate_torque_samples
        ),
        "maximum_mass_solve_abs_residual": max(
            (
                sample["mass_solve_max_abs_residual"]
                for sample in (
                    candidate_torque_samples
                    + execution_torque_samples
                )
            ),
            default=None,
        ),
        "maximum_prediction_execution_margin_error_rad": max(
            (
                fallback[
                    "prediction_execution_margin_error_rad"
                ]
                for fallback in executed
            ),
            default=None,
        ),
        "maximum_prediction_execution_target_joint_velocity_error_rad_s": max(
            (
                fallback[
                    "prediction_execution_target_joint_velocity_error_rad_s"
                ]
                for fallback in executed
            ),
            default=None,
        ),
        "branch_restore_identity_rate": float(
            row["branch_restore_identity"]
        ),
        "policy_load_count": row["policy_load_count"],
        "policy_inference_count": row["policy_inference_count"],
        "initial_policy_shadow_env_step_count": row[
            "initial_policy_shadow_env_step_count"
        ],
        "initial_recovery_candidate_shadow_env_step_count": row[
            "recovery_candidate_shadow_env_step_count"
        ],
        "full_prefix_shadow_env_step_count": row[
            "full_prefix_shadow_env_step_count"
        ],
        "h3_gate_shadow_env_step_count": row[
            "one_step_gate_shadow_env_step_count"
        ],
        "coupled_inverse_mass_brake_exact_h1_shadow_env_step_count": row[
            "coupled_inverse_mass_brake_exact_h1_shadow_env_step_count"
        ],
        "coupled_inverse_mass_brake_controller_configuration_count": row[
            "coupled_inverse_mass_brake_controller_configuration_count"
        ],
        "policy_conditioned_shadow_advance_env_step_count": row[
            "policy_conditioned_shadow_advance_env_step_count"
        ],
        "minimum_advanced_state_margin_rad": min(
            (
                cycle["advanced_state_minimum_margin_rad"]
                for cycle in cycles
                if cycle["first_action_shadow_advanced"]
            ),
            default=None,
        ),
        "active_warning_count": row["active_warning_count"],
        "active_contact_capacity_warning_count": row[
            "active_contact_capacity_warning_count"
        ],
        "contact_capacity_saturation_count": row[
            "contact_capacity_saturation_count"
        ],
        "live_policy_dispatch_count": 0,
        "typed_recovery_env_step_count": 0,
        "outcome_read_count": 0,
        "clean_rollout_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }


def _preflight(
    config: dict[str, Any],
    *,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    payload = base.fresh._preflight(
        config,
        output_root=OUTPUT_ROOT,
        policy_gpu=policy_gpu,
        egl_gpu=egl_gpu,
        formal=False,
    )
    status = base._git_status()
    if status:
        payload["blockers"].append(
            "H3 coupled inverse-mass pilot requires a clean worktree"
        )
        payload["ready"] = False
        payload["worktree_status"] = status.splitlines()
    return payload


def _run(*, policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    config = pilot_config()
    preflight = _preflight(
        config, policy_gpu=policy_gpu, egl_gpu=egl_gpu
    )
    if not preflight["ready"]:
        raise H3CoupledInverseMassBrakeExactH1PilotError(
            f"pilot preflight failed: {preflight['blockers']}"
        )
    device = base.fresh._configure_gpu(policy_gpu, egl_gpu)
    OUTPUT_ROOT.mkdir(parents=True)
    runtime_config = base.policy_loader.ensure_libero_runtime_config(
        OUTPUT_ROOT
    )
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    args = base.fresh._args(
        config,
        output_root=OUTPUT_ROOT,
        render_gpu_device_id=int(
            device["selected_egl_device_ordinal"]
        ),
    )
    manifest_path = OUTPUT_ROOT / "run_manifest.json"
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    manifest = {
        "schema": SUMMARY_SCHEMA + ".run-manifest",
        "status": "loading_policy",
        "created_at": saber_io.utc_now(),
        "policy_gpu": policy_gpu,
        "egl_gpu": egl_gpu,
        "device": device,
        "preflight": preflight,
        "runtime_config": runtime_config,
        "outcomes_observed": False,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy, jax, image_tools, runner = base.policy_loader.load_policy(
            base._policy_protocol(config), args
        )
        import mujoco

        previous_warning_callback = mujoco.get_mju_user_warning()
        warning_audit = base.MujocoWarningAudit()
        mujoco.set_mju_user_warning(warning_audit)
        manifest["status"] = (
            "running_no_outcome_h3_coupled_inverse_mass_brake_exact_h1"
        )
        saber_io.atomic_json(manifest_path, manifest)
        try:
            row = _run_case(
                config,
                config["population"]["pairs"][0],
                policy=policy,
                jax=jax,
                image_tools=image_tools,
                runner=runner,
                args=args,
                warning_audit=warning_audit,
                replan_attempts_per_cycle=1,
                maximum_recovery_escalations_per_cycle=0,
                maximum_safe_bridges_per_cycle=0,
                gate_horizon_steps=GATE_HORIZON_STEPS,
                controller_coupled_inverse_mass_brake_exact_h1_fractions=(
                    TORQUE_VERTEX_BLEND_FRACTIONS
                ),
                controller_coupled_inverse_mass_brake_target_joint_index=(
                    TARGET_JOINT_INDEX
                ),
                controller_coupled_inverse_mass_brake_target_joint_side=(
                    TARGET_JOINT_SIDE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.27",
            )
            saber_io.append_ledger(ledger_path, row)
        finally:
            mujoco.set_mju_user_warning(previous_warning_callback)
        summary = _summarize([row])
        saber_io.atomic_json(OUTPUT_ROOT / "summary.json", summary)
        manifest["status"] = "complete"
        manifest["classification"] = summary["classification"]
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        base.policy_loader.write_checksums(OUTPUT_ROOT)
        return summary
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        base.policy_loader.write_checksums(OUTPUT_ROOT)
        raise


def _validate() -> dict[str, Any]:
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    manifest = _load(OUTPUT_ROOT / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise H3CoupledInverseMassBrakeExactH1PilotError(
            "pilot manifest is incomplete"
        )
    rows = [
        json.loads(line)
        for line in (
            OUTPUT_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    retained = _load(OUTPUT_ROOT / "summary.json")
    recomputed = _summarize(rows)
    if retained != recomputed:
        raise H3CoupledInverseMassBrakeExactH1PilotError(
            "coupled-brake summary recomputation differs"
        )
    return recomputed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    if sum(
        (
            args.preflight,
            args.execute,
            args.validate_results,
        )
    ) != 1:
        parser.error(
            "choose exactly one of --preflight, --execute, "
            "--validate-results"
        )
    if args.validate_results:
        print(_canonical(_validate()))
        return 0
    if args.gpu is None or args.egl_gpu is None:
        parser.error("--gpu and --egl-gpu are required")
    config = pilot_config()
    if args.preflight:
        print(
            _canonical(
                _preflight(
                    config,
                    policy_gpu=args.gpu,
                    egl_gpu=args.egl_gpu,
                )
            )
        )
        return 0
    print(_canonical(_run(policy_gpu=args.gpu, egl_gpu=args.egl_gpu)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
