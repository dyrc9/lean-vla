#!/usr/bin/env python3
"""Evaluate exact H1 under a two-step reset-backup certificate."""

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


from scripts import run_h3_backup_viable_exact_h1_pilot_v12 as one_step  # noqa: E402
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    TARGET_ID,
    _run_case,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_backup_viable_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_two_step_backup_exact_h1_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-two-step-backup-exact-h1-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-two-step-backup-exact-h1-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
BACKUP_CERTIFICATE_DEPTH = 2
MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE = 2


class H3TwoStepBackupExactH1PilotError(RuntimeError):
    """Raised when the two-step backup pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "h3_backup_viable_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "h3_backup_viable_exact_h1_success"
        )
        is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 2, "10510": 2}
        or predecessor.get("backup_viability_screen_count") != 4
        or predecessor.get("backup_viability_nonempty_count") != 2
        or predecessor.get("reset_reserve_execution_count") != 2
        or predecessor.get("minimum_reserve_execution_margin_rad")
        != 0.15669048862788926
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3TwoStepBackupExactH1PilotError(
            "one-step backup nonpass does not authorize successor"
        )
    config = deepcopy(one_step.pilot_config())
    contract = config["controller_reset_exact_h1_contract"]
    contract.update(
        {
            "type": "two_step_backup_certified_exact_h1",
            "backup_certificate_depth": BACKUP_CERTIFICATE_DEPTH,
            "backup_successor_required": True,
            "reserve_successor_required": True,
        }
    )
    config["protocol_id"] = (
        "engineering-h3-two-step-backup-exact-h1-pilot"
    )
    config["receding_horizon"].update(
        {
            "reset_backup_require_safe_successor": True,
            "backup_viability_rule": (
                "The exact reset-H1 endpoint must have a safe one-step "
                "backup whose own endpoint has at least one safe reset "
                "successor in the frozen 61-action library. A reserve must "
                "satisfy the identical safe-successor test. All intermediate "
                "states remain at or above 0.15 rad; at most two reserves "
                "may occur per policy cycle and never count as policy "
                "advances."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot strengthens reset-guarded "
        "exact H1 with a two-step backup certificate on the sole remaining "
        "known v12.6 outlier. Both an exact policy endpoint and any reserve "
        "must retain a safe reset successor after their first safe backup, "
        "using only the frozen 61-action library and unchanged 0.15 rad "
        "floor. Reserves remain separately logged and never count as exact "
        "policy advances. No qpos/qvel reset, threshold change, live policy "
        "dispatch, typed recovery, or outcome read occurs. It is not "
        "qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = one_step._summarize(rows)
    row = rows[0]
    fallbacks = [
        fallback
        for lane in row["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle["reset_exact_h1_fallbacks"]
    ]
    viability_screened = [
        fallback
        for fallback in fallbacks
        if fallback["backup_viability_candidate_evaluations"]
    ]
    reserves = [
        reserve
        for lane in row["lane_results"]
        for cycle in lane["cycles"]
        for reserve in cycle["reset_reserve_bridges"]
    ]
    old_success = summary.pop(
        "h3_backup_viable_exact_h1_success"
    )
    summary.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_two_step_backup_exact_h1_v12_"
                "engineering_pilot_complete"
            ),
            "backup_certificate_depth": BACKUP_CERTIFICATE_DEPTH,
            "backup_successor_required": True,
            "reserve_successor_required": True,
            "h3_two_step_backup_exact_h1_success": old_success,
            "backup_viability_viable_count": sum(
                fallback[
                    "backup_viability_viable_candidate_count"
                ]
                > 0
                for fallback in viability_screened
            ),
            "minimum_backup_viability_viable_candidate_count": min(
                (
                    fallback[
                        "backup_viability_viable_candidate_count"
                    ]
                    for fallback in viability_screened
                ),
                default=None,
            ),
            "reserve_search_viable_candidate_counts": [
                sum(
                    candidate["viable"]
                    for candidate in reserve[
                        "candidate_evaluations"
                    ]
                )
                for reserve in reserves
            ],
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return summary


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
            "two-step backup pilot requires a clean worktree"
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
        raise H3TwoStepBackupExactH1PilotError(
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
            "running_no_outcome_h3_two_step_backup_exact_h1"
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
                reset_exact_h1_require_backup_viability=True,
                reset_backup_require_safe_successor=True,
                maximum_reset_reserve_bridges_per_cycle=(
                    MAXIMUM_RESET_RESERVE_BRIDGES_PER_CYCLE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.22",
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
        raise H3TwoStepBackupExactH1PilotError(
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
        raise H3TwoStepBackupExactH1PilotError(
            "two-step backup summary recomputation differs"
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
