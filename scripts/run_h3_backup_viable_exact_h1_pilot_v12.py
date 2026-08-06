#!/usr/bin/env python3
"""Evaluate backup-viable reset-guarded exact H1 control."""

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
from scripts.run_h3_reset_guarded_exact_h1_pilot_v12 import (  # noqa: E402
    pilot_config as exact_h1_config,
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
    / "proofalign_h3_reset_guarded_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_backup_viable_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-backup-viable-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-backup-viable-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
RESET_EXACT_H1_REQUIRE_BACKUP_VIABILITY = True
MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE = 2


class H3BackupViableExactH1PilotError(RuntimeError):
    """Raised when backup-viable exact H1 must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "h3_reset_guarded_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "h3_reset_guarded_exact_h1_success"
        )
        is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 3, "10510": 3}
        or predecessor.get("reset_exact_h1_screen_count") != 6
        or predecessor.get(
            "reset_exact_h1_authorization_count"
        )
        != 4
        or predecessor.get("reset_exact_h1_execution_count") != 4
        or predecessor.get(
            "reset_exact_h1_exact_action_identity_count"
        )
        != 4
        or predecessor.get(
            "maximum_prediction_execution_margin_error_rad"
        )
        != 0.0
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3BackupViableExactH1PilotError(
            "reset-guarded exact-H1 nonpass does not authorize successor"
        )
    config = deepcopy(exact_h1_config())
    contract = config["controller_reset_exact_h1_contract"]
    contract.update(
        {
            "type": "backup_viable_reset_guarded_exact_h1",
            "backup_viability_required": True,
            "backup_action_library_count": len(
                config["recovery"]["candidate_library"]
            ),
            "backup_action_steps": 1,
            "maximum_reset_reserve_bridges_per_cycle": (
                MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE
            ),
            "reserve_selection_rule": (
                "Largest terminal global joint margin, then largest "
                "minimum margin, then action ID."
            ),
            "reserve_counts_as_policy_advance": False,
        }
    )
    config["protocol_id"] = (
        "engineering-h3-backup-viable-exact-h1-pilot"
    )
    config["receding_horizon"].update(
        {
            "reset_exact_h1_require_backup_viability": True,
            "maximum_reset_reserve_bridges_per_cycle": (
                MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE
            ),
            "backup_viability_rule": (
                "After the reset-plus-exact first policy action, restore its "
                "endpoint and require at least one reset-plus-one-step "
                "backup from the frozen 61-action library to remain at or "
                "above 0.15 rad. If none exists, do not execute the policy "
                "action; instead execute the highest-terminal-margin safe "
                "reset reserve from the original snapshot and fresh replan. "
                "At most two reserves are allowed per policy cycle and "
                "reserves never count as policy advances."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot augments reset-guarded exact "
        "H1 with one-step backup viability on the sole remaining known "
        "v12.6 outlier. An exact source-policy action may advance only if "
        "its reset endpoint remains inside a frozen 61-action backup set at "
        "the unchanged 0.15 rad floor. When viability is empty, a separately "
        "logged reset reserve action may execute before fresh replanning; it "
        "does not count as a policy advance. No action substitution is "
        "reported as exact policy success, qpos/qvel are not reset, and "
        "recovery thresholds remain unchanged. Everything occurs in "
        "restored simulator shadow with zero live dispatch and zero outcome "
        "reads. It is not qualification, utility, deployment, or physical-"
        "safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3BackupViableExactH1PilotError(
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
    exact_executed = [
        fallback
        for fallback in authorized
        if fallback["executed_in_shadow"]
    ]
    viability_screened = [
        fallback
        for fallback in fallbacks
        if fallback["backup_viability_candidate_evaluations"]
    ]
    reserves = [
        reserve
        for cycle in cycles
        for reserve in cycle["reset_reserve_bridges"]
    ]
    reserve_executed = [
        reserve
        for reserve in reserves
        if reserve["executed_in_shadow"]
    ]
    config = pilot_config()
    contract = config["controller_reset_exact_h1_contract"]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h3_backup_viable_exact_h1_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "minimum_margin_floor_rad": contract[
            "minimum_margin_floor_rad"
        ],
        "backup_action_library_count": contract[
            "backup_action_library_count"
        ],
        "maximum_reset_reserve_bridges_per_cycle": (
            MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE
        ),
        "action_substitution_authorized": False,
        "reserve_counts_as_policy_advance": False,
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
        "h3_backup_viable_exact_h1_success": row[
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
        "reset_exact_h1_execution_count": len(exact_executed),
        "reset_exact_h1_exact_action_identity_count": sum(
            fallback["exact_action_identity"] is True
            for fallback in exact_executed
        ),
        "backup_viability_screen_count": len(viability_screened),
        "backup_viability_nonempty_count": sum(
            fallback["backup_viability_safe_candidate_count"] > 0
            for fallback in viability_screened
        ),
        "minimum_backup_viability_safe_candidate_count": min(
            (
                fallback[
                    "backup_viability_safe_candidate_count"
                ]
                for fallback in viability_screened
            ),
            default=None,
        ),
        "reset_reserve_search_count": len(reserves),
        "reset_reserve_execution_count": len(reserve_executed),
        "reset_reserve_selected_action_ids": [
            reserve["selected_action_id"] for reserve in reserves
        ],
        "maximum_prediction_execution_margin_error_rad": max(
            (
                fallback[
                    "prediction_execution_margin_error_rad"
                ]
                for fallback in exact_executed
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
        "reset_exact_h1_shadow_env_step_count": row[
            "reset_exact_h1_shadow_env_step_count"
        ],
        "reset_backup_candidate_shadow_env_step_count": row[
            "reset_backup_candidate_shadow_env_step_count"
        ],
        "reset_reserve_execution_shadow_env_step_count": row[
            "reset_reserve_execution_shadow_env_step_count"
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
        "minimum_reserve_execution_margin_rad": min(
            (
                reserve["execution_minimum_margin_rad"]
                for reserve in reserve_executed
            ),
            default=None,
        ),
        "reset_exact_h1_controller_goal_reset_count": row[
            "reset_exact_h1_controller_goal_reset_count"
        ],
        "reset_backup_controller_goal_reset_count": row[
            "reset_backup_controller_goal_reset_count"
        ],
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
            "backup-viable exact-H1 pilot requires a clean worktree"
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
        raise H3BackupViableExactH1PilotError(
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
            "running_no_outcome_h3_backup_viable_exact_h1"
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
                controller_reset_exact_h1_fallback=True,
                reset_exact_h1_require_backup_viability=(
                    RESET_EXACT_H1_REQUIRE_BACKUP_VIABILITY
                ),
                maximum_reset_reserve_bridges_per_cycle=(
                    MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.21",
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
        raise H3BackupViableExactH1PilotError(
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
        raise H3BackupViableExactH1PilotError(
            "backup-viable exact-H1 summary recomputation differs"
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
