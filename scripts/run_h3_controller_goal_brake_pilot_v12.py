#!/usr/bin/env python3
"""Evaluate an H3 controller-goal-reset brake before a one-step bridge."""

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
from scripts.run_absolute_safe_h2_bridge_pilot_v12 import (  # noqa: E402
    BRIDGE_FLOOR_MODE,
    CONSUME_BRIDGE_AUTHORIZED_PREFIX,
)
from scripts.run_h3_sequence_bridge_pilot_v12 import (  # noqa: E402
    pilot_config as sequence_config,
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
    / "proofalign_h3_sequence_bridge_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_controller_goal_brake_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-controller-goal-brake-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-controller-goal-brake-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
MAXIMUM_SAFE_BRIDGES_PER_CYCLE = 1
SAFE_BRIDGE_SEED_STRIDE = 2_000
CONTROLLER_GOAL_RESET_BEFORE_BRIDGE = True


class H3ControllerGoalBrakePilotError(RuntimeError):
    """Raised when the H3 controller-goal brake pilot fails closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    diagnostics = predecessor.get("builder_diagnostics", ())
    if (
        predecessor.get("classification")
        != "h3_sequence_bridge_v12_engineering_pilot_complete"
        or predecessor.get("h3_sequence_bridge_success") is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or predecessor.get("generated_sequence_candidate_count")
        != 256
        or predecessor.get("safe_bridge_selection_count") != 0
        or len(diagnostics) != 2
        or any(
            item["depths"][-1][
                "expanded_absolute_safe_count"
            ]
            != 0
            for item in diagnostics
        )
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ControllerGoalBrakePilotError(
            "H3 sequence nonpass does not authorize reset-brake successor"
        )
    config = deepcopy(sequence_config())
    floor = float(config["recovery"]["safe_margin_rad"])
    config["protocol_id"] = (
        "engineering-h3-controller-goal-reset-brake-pilot"
    )
    config["bridge_contract"] = {
        "type": "controller_goal_reset_brake",
        "controller_operation": (
            "controller.update(force=True); controller.reset_goal()"
        ),
        "controller_goal_rebound_to_current_pose": True,
        "simulator_qpos_modified_by_reset": False,
        "simulator_qvel_modified_by_reset": False,
        "floor_mode": BRIDGE_FLOOR_MODE,
        "terminal_margin_floor_rad": floor,
        "strict_no_crossing": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "advance_policy_action_steps": 1,
        "consume_same_authorized_prefix": (
            CONSUME_BRIDGE_AUTHORIZED_PREFIX
        ),
        "recovery_contract_reused": False,
        "bridge_action_library_count": len(
            config["recovery"]["candidate_library"]
        ),
        "bridge_action_count": 1,
    }
    config["receding_horizon"].update(
        {
            "gate_horizon_steps": GATE_HORIZON_STEPS,
            "maximum_safe_bridges_per_cycle": (
                MAXIMUM_SAFE_BRIDGES_PER_CYCLE
            ),
            "safe_bridge_seed_stride": SAFE_BRIDGE_SEED_STRIDE,
            "controller_goal_reset_before_bridge": (
                CONTROLLER_GOAL_RESET_BEFORE_BRIDGE
            ),
            "safe_bridge_gate": (
                "After H3 block_replan, restore the exact branch and reset "
                "only the OSC goal to the current end-effector pose before "
                "one frozen scaled bridge action. The reset may not modify "
                "simulator qpos or qvel. The resulting step must remain at "
                "or above 0.15 rad with no crossing, produce fresh H3 "
                "allow_exact, and reconfirm the same prefix after exact "
                "reset-plus-action replay before H1 advancement."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates an explicit OSC "
        "controller-goal reset brake after H3 block_replan on the sole "
        "remaining known v12.6 outlier. The reset rebinds only the internal "
        "goal to the current end-effector pose; it does not clear simulator "
        "qpos or qvel. The following one-step bridge must preserve the "
        "frozen 0.15 rad floor and strict no-crossing, then pass fresh and "
        "post-replay H3 exact gates. It is not recovery, and recovery "
        "parameters remain unchanged. All actions remain restored simulator "
        "shadow with zero live dispatch and zero task-outcome reads. It is "
        "not qualification, utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3ControllerGoalBrakePilotError(
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
    bridges = [
        bridge
        for cycle in cycles
        for bridge in cycle["safe_bridges"]
    ]
    evaluations = [
        evaluation
        for bridge in bridges
        for evaluation in bridge["candidate_evaluations"]
    ]
    selected = [
        bridge
        for bridge in bridges
        if bridge["selected_action_id"] is not None
    ]
    executed = [
        bridge for bridge in bridges if bridge["executed_in_shadow"]
    ]
    confirmed = [
        bridge
        for bridge in executed
        if bridge["post_execution_gate_verdict"] is not None
    ]
    config = pilot_config()
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_controller_goal_brake_v12_engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "advanced_policy_action_steps_per_cycle": 1,
        "controller_goal_reset_before_bridge": True,
        "controller_operation": config["bridge_contract"][
            "controller_operation"
        ],
        "bridge_floor_mode": BRIDGE_FLOOR_MODE,
        "bridge_terminal_margin_floor_rad": config[
            "bridge_contract"
        ]["terminal_margin_floor_rad"],
        "bridge_action_library_count": config["bridge_contract"][
            "bridge_action_library_count"
        ],
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
        "h3_controller_goal_brake_success": row[
            "receding_horizon_success"
        ],
        "total_fresh_policy_attempt_count": len(attempts),
        "h3_allow_attempt_count": sum(
            attempt["gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "full_prefix_allow_attempt_count": sum(
            attempt["full_prefix_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "safe_bridge_search_count": len(bridges),
        "generated_reset_bridge_candidate_count": len(evaluations),
        "absolute_safe_reset_bridge_candidate_count": sum(
            evaluation["bridge_safe"] for evaluation in evaluations
        ),
        "post_h3_screened_reset_bridge_candidate_count": sum(
            evaluation["policy_screened"] for evaluation in evaluations
        ),
        "safe_bridge_selection_count": len(selected),
        "safe_bridge_execution_count": len(executed),
        "post_execution_h3_confirmation_count": len(confirmed),
        "post_execution_h3_allow_count": sum(
            bridge["post_execution_gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for bridge in confirmed
        ),
        "authorized_prefix_consumption_count": sum(
            bridge["authorized_prefix_consumed"]
            for bridge in confirmed
        ),
        "selected_bridge_action_ids": [
            bridge["selected_action_id"] for bridge in selected
        ],
        "bridge_controller_goal_reset_count": row[
            "bridge_controller_goal_reset_count"
        ],
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
        "bridge_candidate_shadow_env_step_count": row[
            "bridge_candidate_shadow_env_step_count"
        ],
        "bridge_post_h3_shadow_env_step_count": row[
            "bridge_post_h1_shadow_env_step_count"
        ],
        "bridge_execution_shadow_env_step_count": row[
            "bridge_execution_shadow_env_step_count"
        ],
        "full_prefix_shadow_env_step_count": row[
            "full_prefix_shadow_env_step_count"
        ],
        "h3_gate_shadow_env_step_count": row[
            "one_step_gate_shadow_env_step_count"
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
        "minimum_executed_bridge_margin_rad": min(
            (
                bridge["execution_minimum_margin_rad"]
                for bridge in executed
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
            "H3 controller-goal brake requires a clean worktree"
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
        raise H3ControllerGoalBrakePilotError(
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
            "running_no_outcome_h3_controller_goal_brake"
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
                maximum_safe_bridges_per_cycle=(
                    MAXIMUM_SAFE_BRIDGES_PER_CYCLE
                ),
                safe_bridge_seed_stride=SAFE_BRIDGE_SEED_STRIDE,
                gate_horizon_steps=GATE_HORIZON_STEPS,
                bridge_floor_mode=BRIDGE_FLOOR_MODE,
                consume_bridge_authorized_prefix=(
                    CONSUME_BRIDGE_AUTHORIZED_PREFIX
                ),
                controller_goal_reset_before_bridge=(
                    CONTROLLER_GOAL_RESET_BEFORE_BRIDGE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.19",
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
        raise H3ControllerGoalBrakePilotError(
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
        raise H3ControllerGoalBrakePilotError(
            "controller-goal brake summary recomputation differs"
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
