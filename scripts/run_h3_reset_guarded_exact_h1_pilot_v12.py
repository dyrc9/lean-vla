#!/usr/bin/env python3
"""Evaluate H3 with a reset-guarded exact-H1 receding fallback."""

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
from scripts.run_h3_controller_goal_brake_pilot_v12 import (  # noqa: E402
    pilot_config as goal_brake_config,
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
    / "proofalign_h3_controller_goal_brake_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_reset_guarded_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-reset-guarded-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-reset-guarded-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
CONTROLLER_RESET_EXACT_H1_FALLBACK = True


class H3ResetGuardedExactH1PilotError(RuntimeError):
    """Raised when reset-guarded exact H1 must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "h3_controller_goal_brake_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "h3_controller_goal_brake_success"
        )
        is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or predecessor.get(
            "absolute_safe_reset_bridge_candidate_count"
        )
        != 122
        or predecessor.get(
            "post_h3_screened_reset_bridge_candidate_count"
        )
        != 122
        or predecessor.get("safe_bridge_selection_count") != 0
        or predecessor.get(
            "bridge_controller_goal_reset_count"
        )
        != 244
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ResetGuardedExactH1PilotError(
            "controller-goal brake nonpass does not authorize successor"
        )
    config = deepcopy(goal_brake_config())
    floor = float(config["recovery"]["safe_margin_rad"])
    config["protocol_id"] = (
        "engineering-h3-reset-guarded-exact-h1-pilot"
    )
    config["controller_reset_exact_h1_contract"] = {
        "type": "reset_guarded_exact_h1",
        "trigger_gate_horizon_steps": GATE_HORIZON_STEPS,
        "fallback_action_steps": 1,
        "controller_operation": (
            "controller.update(force=True); controller.reset_goal()"
        ),
        "exact_source_policy_action_required": True,
        "action_substitution_authorized": False,
        "simulator_qpos_modified_by_reset": False,
        "simulator_qvel_modified_by_reset": False,
        "minimum_margin_floor_rad": floor,
        "strict_no_crossing": True,
        "fresh_replan_after_each_advance": True,
        "recovery_contract_reused": False,
    }
    config["receding_horizon"].update(
        {
            "gate_horizon_steps": GATE_HORIZON_STEPS,
            "maximum_safe_bridges_per_cycle": 0,
            "controller_goal_reset_before_bridge": False,
            "controller_reset_exact_h1_fallback": True,
            "fallback_rule": (
                "When the exact H3 prefix is block_replan, restore its "
                "bound snapshot, reset only the OSC goal, and shadow the "
                "same prefix's exact first action. Authorize that one action "
                "only if the exact reset replay remains at or above 0.15 "
                "rad with no crossing. Restore again, repeat the reset, "
                "execute identical action bytes, and immediately fresh "
                "replan; no substitute action or unverified tail is used."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates H3 predictive "
        "lookahead with a reset-guarded exact-H1 receding fallback on the "
        "sole remaining known v12.6 outlier. H3 block does not authorize a "
        "different action: only the identical first source-policy action "
        "may advance after an exact controller-reset replay remains above "
        "the frozen 0.15 rad floor with no crossing. Simulator qpos/qvel are "
        "not reset, and fresh inference follows every one-step advance. "
        "Recovery parameters remain unchanged. All work is restored "
        "simulator shadow with zero live dispatch and zero outcome reads. "
        "It is not qualification, task utility, deployment, or physical-"
        "safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3ResetGuardedExactH1PilotError(
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
        for fallback in cycle["reset_exact_h1_fallbacks"]
    ]
    authorized = [
        fallback for fallback in fallbacks if fallback["authorized"]
    ]
    executed = [
        fallback
        for fallback in authorized
        if fallback["executed_in_shadow"]
    ]
    config = pilot_config()
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_reset_guarded_exact_h1_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "fallback_action_steps": 1,
        "minimum_margin_floor_rad": config[
            "controller_reset_exact_h1_contract"
        ]["minimum_margin_floor_rad"],
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
        "h3_reset_guarded_exact_h1_success": row[
            "receding_horizon_success"
        ],
        "total_fresh_policy_attempt_count": len(attempts),
        "direct_h3_allow_attempt_count": sum(
            attempt["gate_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "reset_exact_h1_screen_count": len(fallbacks),
        "reset_exact_h1_authorization_count": len(authorized),
        "reset_exact_h1_execution_count": len(executed),
        "reset_exact_h1_exact_action_identity_count": sum(
            fallback["exact_action_identity"] is True
            for fallback in executed
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
        "reset_exact_h1_controller_goal_reset_count": row[
            "reset_exact_h1_controller_goal_reset_count"
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
        "full_prefix_shadow_env_step_count": row[
            "full_prefix_shadow_env_step_count"
        ],
        "h3_gate_shadow_env_step_count": row[
            "one_step_gate_shadow_env_step_count"
        ],
        "reset_exact_h1_shadow_env_step_count": row[
            "reset_exact_h1_shadow_env_step_count"
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
        "minimum_reset_exact_h1_execution_margin_rad": min(
            (
                fallback["execution_terminal_margin_rad"]
                for fallback in executed
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
            "H3 reset-guarded exact-H1 pilot requires a clean worktree"
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
        raise H3ResetGuardedExactH1PilotError(
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
            "running_no_outcome_h3_reset_guarded_exact_h1"
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
                controller_reset_exact_h1_fallback=(
                    CONTROLLER_RESET_EXACT_H1_FALLBACK
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.20",
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
        raise H3ResetGuardedExactH1PilotError(
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
        raise H3ResetGuardedExactH1PilotError(
            "reset-guarded exact-H1 summary recomputation differs"
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
