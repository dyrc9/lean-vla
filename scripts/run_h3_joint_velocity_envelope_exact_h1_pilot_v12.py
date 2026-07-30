#!/usr/bin/env python3
"""Evaluate a scoped joint-limit velocity envelope for exact H1."""

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
from scripts import run_h3_joint_damping_exact_h1_pilot_v12 as predecessor  # noqa: E402
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
    / "proofalign_h3_joint_damping_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_joint_velocity_envelope_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-joint-velocity-envelope-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-joint-velocity-envelope-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
TARGET_JOINT_INDEX = 1
TARGET_JOINT_SIDE = "upper"
VELOCITY_ENVELOPE_SLOPES_PER_S = (
    0.0,
    0.5,
    1.0,
    2.0,
    4.0,
    8.0,
    16.0,
)


class H3JointVelocityEnvelopeExactH1PilotError(RuntimeError):
    """Raised when the velocity-envelope pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_joint_damping_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or prior.get("h3_joint_damping_exact_h1_success")
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 3, "10510": 3}
        or prior.get("candidate_configuration_count") != 36
        or prior.get("candidate_configuration_qpos_identity_count")
        != 36
        or prior.get("candidate_configuration_qvel_identity_count")
        != 36
        or prior.get("candidate_controller_scope_restore_count")
        != 36
        or prior.get("execution_controller_scope_restore_count") != 4
        or prior.get("joint_damping_exact_h1_exact_action_identity_count")
        != 4
        or prior.get("maximum_prediction_execution_margin_error_rad")
        != 0.0
        or prior.get("damping_direction_violation_count") != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3JointVelocityEnvelopeExactH1PilotError(
            "joint-damping nonpass does not authorize successor"
        )
    config = deepcopy(predecessor.pilot_config())
    floor = float(config["recovery"]["safe_margin_rad"])
    config["protocol_id"] = (
        "engineering-h3-joint-velocity-envelope-exact-h1-pilot"
    )
    config["controller_joint_velocity_envelope_exact_h1_contract"] = {
        "type": "one_sided_joint_limit_velocity_envelope_exact_h1",
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "slopes_per_s": list(VELOCITY_ENVELOPE_SLOPES_PER_S),
        "allowed_velocity_rule": (
            "v_toward_max = slope * max(target_margin - 0.15, 0)"
        ),
        "brake_rule": (
            "When measured toward-limit velocity exceeds the envelope, "
            "set target-joint torque to the away-from-limit actuator bound."
        ),
        "selection_rule": (
            "Among candidates whose exact one-step replay stays at or "
            "above 0.15 rad and whose terminal state satisfies the same "
            "velocity envelope, select the largest slope, then largest "
            "terminal margin."
        ),
        "controller_goal_reset_before_action": True,
        "scope": "one exact source-policy action only",
        "wrapper_removed_immediately_after_action": True,
        "torque_clipped_to_actuator_limits": True,
        "terminal_velocity_envelope_required": True,
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
            "controller_joint_damping_exact_h1_gains": [],
            "controller_joint_velocity_envelope_exact_h1_slopes": list(
                VELOCITY_ENVELOPE_SLOPES_PER_S
            ),
            "controller_joint_velocity_envelope_target_joint_index": (
                TARGET_JOINT_INDEX
            ),
            "controller_joint_velocity_envelope_target_joint_side": (
                TARGET_JOINT_SIDE
            ),
            "fallback_rule": (
                "After H3 block, restore the bound controller snapshot. "
                "For each frozen slope, reset the end-effector goal without "
                "changing qpos/qvel, wrap run_controller for exactly one "
                "source-policy action, and apply the one-sided velocity "
                "envelope at joint 1. Authorize only if both the 0.15-rad "
                "position floor and terminal velocity envelope hold. Use "
                "the largest safe slope and immediately fresh replan."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates a scoped "
        "one-sided joint-limit velocity envelope after H3 block_replan on "
        "the sole remaining known v12.6 outlier. It executes identical "
        "source-policy action bytes while overriding only joint-1 torque "
        "when measured toward-upper-limit velocity exceeds a frozen "
        "margin-dependent envelope. Candidate eligibility requires both "
        "the one-step 0.15-rad position floor and terminal envelope, so a "
        "temporarily safe but dynamically unbrakeable state is rejected. "
        "The wrapper is removed after one action and qpos/qvel are "
        "unchanged by configuration. No action substitution, threshold "
        "change, live dispatch, typed recovery, or task-outcome read "
        "occurs. It is not qualification, task utility, deployment, or "
        "physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3JointVelocityEnvelopeExactH1PilotError(
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
            "joint_velocity_envelope_exact_h1_fallbacks"
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
        "controller_joint_velocity_envelope_exact_h1_contract"
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
                "execution_terminal_envelope_satisfied"
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
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_joint_velocity_envelope_exact_h1_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "velocity_envelope_slopes_per_s": list(
            VELOCITY_ENVELOPE_SLOPES_PER_S
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
        "h3_joint_velocity_envelope_exact_h1_success": method_success,
        "total_fresh_policy_attempt_count": len(attempts),
        "direct_h3_allow_attempt_count": sum(
            attempt["gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "joint_velocity_envelope_exact_h1_screen_count": len(
            fallbacks
        ),
        "joint_velocity_envelope_exact_h1_authorization_count": len(
            authorized
        ),
        "joint_velocity_envelope_exact_h1_execution_count": len(
            executed
        ),
        "joint_velocity_envelope_exact_h1_exact_action_identity_count": sum(
            fallback["exact_action_identity"] is True
            for fallback in executed
        ),
        "selected_velocity_envelope_slopes_per_s": [
            fallback["selected_slope_per_s"] for fallback in executed
        ],
        "candidate_terminal_envelope_satisfied_count": sum(
            candidate["terminal_envelope_satisfied"]
            for candidate in candidates
        ),
        "execution_terminal_envelope_satisfied_count": sum(
            fallback["execution_terminal_envelope_satisfied"] is True
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
        "candidate_envelope_activation_count": sum(
            sample["envelope_activated"]
            for sample in candidate_torque_samples
        ),
        "execution_envelope_activation_count": sum(
            sample["envelope_activated"]
            for sample in execution_torque_samples
        ),
        "candidate_target_joint_torque_clip_count": sum(
            sample["target_joint_torque_clipped"]
            for sample in candidate_torque_samples
        ),
        "execution_target_joint_torque_clip_count": sum(
            sample["target_joint_torque_clipped"]
            for sample in execution_torque_samples
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
        "joint_velocity_envelope_exact_h1_shadow_env_step_count": row[
            "joint_velocity_envelope_exact_h1_shadow_env_step_count"
        ],
        "joint_velocity_envelope_controller_configuration_count": row[
            "joint_velocity_envelope_controller_configuration_count"
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
            "H3 velocity-envelope pilot requires a clean worktree"
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
        raise H3JointVelocityEnvelopeExactH1PilotError(
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
            "running_no_outcome_h3_joint_velocity_envelope_exact_h1"
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
                controller_joint_velocity_envelope_exact_h1_slopes=(
                    VELOCITY_ENVELOPE_SLOPES_PER_S
                ),
                controller_joint_velocity_envelope_target_joint_index=(
                    TARGET_JOINT_INDEX
                ),
                controller_joint_velocity_envelope_target_joint_side=(
                    TARGET_JOINT_SIDE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.25",
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
        raise H3JointVelocityEnvelopeExactH1PilotError(
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
        raise H3JointVelocityEnvelopeExactH1PilotError(
            "velocity-envelope summary recomputation differs"
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
