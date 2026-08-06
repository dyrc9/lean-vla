#!/usr/bin/env python3
"""Evaluate joint-limit-aware OSC nullspace exact-H1 fallback."""

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
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_h3_two_step_backup_exact_h1_pilot_v12 import (  # noqa: E402
    pilot_config as two_step_config,
)
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
    / "proofalign_h3_two_step_backup_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_nullspace_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-nullspace-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-nullspace-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
TARGET_JOINT_INDEX = 1
TARGET_JOINT_SIDE = "upper"
NULLSPACE_RETREAT_OFFSETS_RAD = (0.05, 0.10, 0.20, 0.30, 0.50)


class H3NullspaceExactH1PilotError(RuntimeError):
    """Raised when the nullspace exact-H1 pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "h3_two_step_backup_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "h3_two_step_backup_exact_h1_success"
        )
        is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or predecessor.get("backup_viability_viable_count") != 0
        or predecessor.get("reserve_search_viable_candidate_counts")
        != [56, 0, 56, 0]
        or predecessor.get("reset_reserve_execution_count") != 2
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3NullspaceExactH1PilotError(
            "two-step backup nonpass does not authorize successor"
        )
    config = deepcopy(two_step_config())
    floor = float(config["recovery"]["safe_margin_rad"])
    config["protocol_id"] = (
        "engineering-h3-nullspace-exact-h1-pilot"
    )
    config["controller_nullspace_exact_h1_contract"] = {
        "type": "joint_limit_aware_osc_nullspace_exact_h1",
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "retreat_offsets_rad": list(
            NULLSPACE_RETREAT_OFFSETS_RAD
        ),
        "selection_rule": (
            "Smallest offset whose exact one-step replay remains at or "
            "above 0.15 rad, then largest terminal margin."
        ),
        "controller_fields_changed": ("initial_joint", "goal_pos", "goal_ori"),
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
            "controller_reset_exact_h1_fallback": False,
            "reset_exact_h1_require_backup_viability": False,
            "reset_backup_require_safe_successor": False,
            "maximum_reset_reserve_bridges_per_cycle": 0,
            "controller_nullspace_exact_h1_offsets_rad": list(
                NULLSPACE_RETREAT_OFFSETS_RAD
            ),
            "controller_nullspace_target_joint_index": (
                TARGET_JOINT_INDEX
            ),
            "controller_nullspace_target_joint_side": (
                TARGET_JOINT_SIDE
            ),
            "fallback_rule": (
                "After H3 block, restore the bound controller snapshot. For "
                "each frozen offset, keep simulator qpos/qvel unchanged, "
                "move only OSC initial_joint[1] from current qpos toward the "
                "lower side, reset the end-effector goal, and replay the "
                "identical first source-policy action. Execute the smallest "
                "offset that keeps the exact action at or above 0.15 rad, "
                "then immediately fresh replan."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates a joint-limit-"
        "aware OSC nullspace fallback after H3 block_replan on the sole "
        "remaining known v12.6 outlier. It changes only controller target "
        "state, not simulator qpos/qvel or source-policy action bytes. The "
        "smallest frozen joint-1 retreat offset with an exact one-step "
        "0.15-rad-safe replay is used before immediate fresh replanning. No "
        "action substitution, recovery-threshold change, live dispatch, "
        "typed recovery, or task-outcome read occurs. It is not "
        "qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3NullspaceExactH1PilotError(
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
        for fallback in cycle["nullspace_exact_h1_fallbacks"]
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
    config = pilot_config()
    contract = config["controller_nullspace_exact_h1_contract"]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_nullspace_exact_h1_v12_engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "nullspace_retreat_offsets_rad": list(
            NULLSPACE_RETREAT_OFFSETS_RAD
        ),
        "minimum_margin_floor_rad": contract[
            "minimum_margin_floor_rad"
        ],
        "action_substitution_authorized": False,
        "recovery_required_margin_gain_rad": config["recovery"][
            "required_margin_gain_rad"
        ],
        "recovery_max_transient_margin_loss_rad": config[
            "recovery"
        ]["max_transient_margin_loss_rad"],
        "lane_count": len(row["lane_results"]),
        "lane_base_seeds": row["lane_base_seeds"],
        "planned_cycle_count_per_lane": RECEDING_CYCLE_COUNT,
        "completed_cycle_counts": {
            str(lane["base_seed"]): lane["completed_cycle_count"]
            for lane in row["lane_results"]
        },
        "safe_lane_count": sum(
            lane["lane_safe"] for lane in row["lane_results"]
        ),
        "h3_nullspace_exact_h1_success": row[
            "receding_horizon_success"
        ],
        "total_fresh_policy_attempt_count": len(attempts),
        "direct_h3_allow_attempt_count": sum(
            attempt["gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "nullspace_exact_h1_screen_count": len(fallbacks),
        "nullspace_exact_h1_authorization_count": len(authorized),
        "nullspace_exact_h1_execution_count": len(executed),
        "nullspace_exact_h1_exact_action_identity_count": sum(
            fallback["exact_action_identity"] is True
            for fallback in executed
        ),
        "selected_nullspace_offsets_rad": [
            fallback["selected_offset_rad"] for fallback in executed
        ],
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
        "candidate_configuration_count": len(candidates),
        "maximum_prediction_execution_margin_error_rad": max(
            (
                fallback[
                    "prediction_execution_margin_error_rad"
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
        "nullspace_exact_h1_shadow_env_step_count": row[
            "nullspace_exact_h1_shadow_env_step_count"
        ],
        "nullspace_controller_configuration_count": row[
            "nullspace_controller_configuration_count"
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
            "H3 nullspace exact-H1 pilot requires a clean worktree"
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
        raise H3NullspaceExactH1PilotError(
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
            "running_no_outcome_h3_nullspace_exact_h1"
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
                controller_nullspace_exact_h1_offsets_rad=(
                    NULLSPACE_RETREAT_OFFSETS_RAD
                ),
                controller_nullspace_target_joint_index=(
                    TARGET_JOINT_INDEX
                ),
                controller_nullspace_target_joint_side=(
                    TARGET_JOINT_SIDE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.23",
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
        raise H3NullspaceExactH1PilotError(
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
        raise H3NullspaceExactH1PilotError(
            "nullspace exact-H1 summary recomputation differs"
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
