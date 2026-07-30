#!/usr/bin/env python3
"""Evaluate a scoped simulator virtual joint-stop beam."""

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


from scripts import run_h3_contact_aware_vertex_schedule_beam_pilot_v12 as predecessor  # noqa: E402
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    RECEDING_CYCLE_COUNT,
    _run_case,
)


base = predecessor.base
vertices = predecessor.vertices
saber_io = predecessor.saber_io
_canonical = predecessor._canonical
_load = predecessor._load

PREDECESSOR_ROOT = predecessor.OUTPUT_ROOT
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_virtual_joint_guard_beam_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-virtual-joint-guard-beam-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-virtual-joint-guard-beam-pilot-v12-summary.v1"
)
BEAM_WIDTH = predecessor.BEAM_WIDTH
MAX_BEAM_HORIZON = predecessor.MAX_BEAM_HORIZON
RETENTION_STRATEGY = predecessor.RETENTION_STRATEGY
VIRTUAL_JOINT_GUARD_MARGINS_RAD = (0.16, 0.18, 0.20, 0.22)
CONTROLLER_MODE_COUNT = len(VIRTUAL_JOINT_GUARD_MARGINS_RAD)


class H3VirtualJointGuardBeamPilotError(RuntimeError):
    """Raised when the simulator virtual joint-stop must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    velocities = prior.get(
        "best_velocity_terminal_toward_velocities_rad_s"
    )
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_schedule_beam_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_contact_aware_vertex_schedule_beam_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("beam_horizons") != [4, 4]
        or prior.get("beam_screen_count") != 2
        or prior.get("beam_configuration_count") != 16_512
        or prior.get("beam_configuration_qpos_identity_count")
        != 16_512
        or prior.get("beam_configuration_qvel_identity_count")
        != 16_512
        or prior.get("beam_controller_scope_restore_count")
        != 16_512
        or prior.get("beam_torque_bound_violation_count") != 0
        or not isinstance(velocities, list)
        or len(velocities) != 6
        or velocities[1] < 4.329
        or velocities[4] < 4.329
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3VirtualJointGuardBeamPilotError(
            "schedule-beam nonpass does not authorize virtual guard"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-virtual-joint-guard-beam-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["type"] = (
        "scoped_simulator_virtual_joint_stop_exact_action_beam"
    )
    contract["controller_mode_type"] = (
        "virtual_joint_guard_margin"
    )
    contract["candidate_vertex_ids"] = []
    contract["candidate_vertex_count"] = 0
    contract["ranked_schedule_vertex_ids"] = []
    contract["blend_fractions"] = []
    contract["vertex_schedules"] = []
    contract["virtual_joint_guard_margins_rad"] = list(
        VIRTUAL_JOINT_GUARD_MARGINS_RAD
    )
    contract["controller_mode_count"] = CONTROLLER_MODE_COUNT
    contract["guard_rule"] = (
        "Only during one exact source-action env step, replace the target "
        "joint model range with the original range tightened inward by "
        "the selected guard margin. Require the state to start inside "
        "that guarded range. Restore the original model range exactly "
        "and forward the simulator before leaving the scope."
    )
    contract["guard_model_configuration_identity_required"] = True
    contract["guard_range_restore_required"] = True
    contract["guard_constraint_audit_required"] = True
    contract["selection_rule"] = (
        "Expand all four virtual-stop margins over every remaining exact "
        "source action under the unchanged 0.15-rad global floor. "
        "Authorize only a complete sequence, execute its first scoped "
        "guard with identical action bytes, then fresh H3 replan."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_candidate_ids": [],
            "contact_aware_vertex_beam_blend_fractions": [],
            "contact_aware_vertex_beam_vertex_schedules": [],
            "contact_aware_vertex_beam_virtual_joint_guard_margins_rad": list(
                VIRTUAL_JOINT_GUARD_MARGINS_RAD
            ),
            "contact_aware_vertex_beam_controller_mode_count": (
                CONTROLLER_MODE_COUNT
            ),
            "fallback_rule": (
                "After H3 blocks, search four scoped simulator "
                "virtual-stop margins through all remaining exact source "
                "actions. Keep the original 0.15-rad floor and execute "
                "only the first guard before fresh inference."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed pilot is explicitly a simulator virtual "
        "joint-stop / safety-brake experiment, not an actuator-only "
        "successor. It preserves exact source action bytes and qpos/qvel "
        "at configuration time, but temporarily changes one MuJoCo joint "
        "range during each guarded action and then restores it exactly. "
        "It audits constraint force/activation, range restoration, "
        "prediction/execution identity, warnings, contact capacity, and "
        "the unchanged 0.15-rad floor. Even a pass is only simulator "
        "engineering/shadow evidence, not task utility, deployment, "
        "actuator authority, qualification, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    inherited.pop(
        "h3_contact_aware_vertex_schedule_beam_success"
    )
    fallbacks = [
        fallback
        for lane in rows[0]["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle[
            "contact_aware_vertex_exact_h1_fallbacks"
        ]
    ]
    beam_results = [
        fallback["beam_search"] for fallback in fallbacks
    ]
    authorized = [
        fallback for fallback in fallbacks if fallback["authorized"]
    ]
    execution_samples = [
        sample
        for fallback in authorized
        for sample in fallback[
            "execution_controller_substep_torque_audit"
        ]
    ]
    completed = inherited["completed_cycle_counts"]
    expected = {
        str(seed): RECEDING_CYCLE_COUNT
        for seed in LANE_BASE_SEEDS
    }
    activation_count = sum(
        sample["guard_constraint_near_or_active"]
        for sample in execution_samples
    )
    configuration_range_restore_count = sum(
        fallback["execution_controller_scope_restored"]
        is True
        for fallback in authorized
    )
    method_success = bool(
        inherited["one_step_receding_floor_success"]
        and completed == expected
        and authorized
        and activation_count > 0
        and configuration_range_restore_count == len(authorized)
        and all(
            fallback["exact_action_identity"] is True
            and fallback[
                "prediction_execution_margin_error_rad"
            ]
            == 0
            and fallback[
                "prediction_execution_target_joint_velocity_error_rad_s"
            ]
            == 0
            and fallback["execution_configuration"][
                "configuration_inside_guard_range"
            ]
            for fallback in authorized
        )
        and all(
            result["mode_count"] == CONTROLLER_MODE_COUNT
            and result["virtual_joint_guard_margins_rad"]
            == list(VIRTUAL_JOINT_GUARD_MARGINS_RAD)
            and result["selected"] is not None
            and len(result["selected"]["sequence"])
            == result["horizon"]
            and result["restore_identity"]
            and result["configuration_count"]
            == result["configuration_qpos_identity_count"]
            == result["configuration_qvel_identity_count"]
            == result["controller_scope_restore_count"]
            and result["torque_bound_violation_count"] == 0
            for result in beam_results
        )
    )
    inherited.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_virtual_joint_guard_beam_v12_"
                "engineering_pilot_complete"
            ),
            "candidate_vertex_ids": [],
            "ranked_candidate_vertex_ids": [],
            "vertex_blend_fractions": [],
            "controller_mode_type": "virtual_joint_guard_margin",
            "controller_mode_count": CONTROLLER_MODE_COUNT,
            "virtual_joint_guard_margins_rad": list(
                VIRTUAL_JOINT_GUARD_MARGINS_RAD
            ),
            "h3_virtual_joint_guard_beam_success": method_success,
            "virtual_joint_guard_authorization_count": len(
                authorized
            ),
            "virtual_joint_guard_activation_sample_count": (
                activation_count
            ),
            "virtual_joint_guard_execution_substep_sample_count": len(
                execution_samples
            ),
            "virtual_joint_guard_range_restore_count": (
                configuration_range_restore_count
            ),
            "maximum_abs_target_dof_constraint_force": (
                max(
                    abs(sample["target_dof_constraint_force"])
                    for sample in execution_samples
                )
                if execution_samples
                else None
            ),
            "selected_virtual_joint_guard_margins_rad": [
                fallback[
                    "selected_virtual_joint_guard_margin_rad"
                ]
                for fallback in authorized
            ],
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return inherited


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
            "virtual joint-guard pilot requires a clean worktree"
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
        raise H3VirtualJointGuardBeamPilotError(
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
            "running_no_outcome_h3_virtual_joint_guard_beam"
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
                gate_horizon_steps=vertices.GATE_HORIZON_STEPS,
                controller_contact_aware_vertex_exact_h1_ids=(),
                controller_contact_aware_vertex_target_joint_index=(
                    vertices.TARGET_JOINT_INDEX
                ),
                controller_contact_aware_vertex_target_joint_side=(
                    vertices.TARGET_JOINT_SIDE
                ),
                contact_aware_vertex_require_terminal_non_toward_velocity=(
                    False
                ),
                contact_aware_vertex_beam_width=BEAM_WIDTH,
                contact_aware_vertex_beam_max_horizon=(
                    MAX_BEAM_HORIZON
                ),
                contact_aware_vertex_beam_virtual_joint_guard_margins_rad=(
                    VIRTUAL_JOINT_GUARD_MARGINS_RAD
                ),
                contact_aware_vertex_beam_retention_strategy=(
                    RETENTION_STRATEGY
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.35",
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
        raise H3VirtualJointGuardBeamPilotError(
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
        raise H3VirtualJointGuardBeamPilotError(
            "virtual-guard summary recomputation differs"
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
