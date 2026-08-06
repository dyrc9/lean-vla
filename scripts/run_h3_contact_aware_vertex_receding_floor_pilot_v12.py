#!/usr/bin/env python3
"""Re-evaluate contact-aware vertices with the actual receding floor."""

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


from scripts import run_h3_contact_aware_vertex_exact_h1_pilot_v12 as source  # noqa: E402
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    RECEDING_CYCLE_COUNT,
    _run_case,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_contact_aware_vertex_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_contact_aware_vertex_receding_floor_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-receding-floor-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-receding-floor-pilot-v12-summary.v1"
)


class H3ContactAwareVertexRecedingFloorPilotError(RuntimeError):
    """Raised when the receding-floor replay must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_exact_h1_v12_"
            "engineering_pilot_complete"
        )
        or prior.get("h3_contact_aware_vertex_exact_h1_success")
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("candidate_configuration_count") != 128
        or prior.get("candidate_configuration_qpos_identity_count")
        != 128
        or prior.get("candidate_configuration_qvel_identity_count")
        != 128
        or prior.get("candidate_controller_scope_restore_count")
        != 128
        or prior.get("candidate_terminal_non_toward_velocity_count")
        != 0
        or prior.get("safe_contact_aware_vertex_counts") != [0, 0]
        or prior.get("torque_bound_violation_count") != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ContactAwareVertexRecedingFloorPilotError(
            "strict-terminal vertex result does not authorize successor"
        )
    config = deepcopy(source.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-contact-aware-vertex-receding-floor-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["terminal_non_toward_velocity_required"] = False
    contract["selection_rule"] = (
        "Among vertices whose exact one-step replay stays at or above "
        "0.15 rad and remains within actuator bounds, select largest "
        "terminal target-joint margin, then largest global margin, then "
        "lowest vertex ID. Terminal velocity remains audited but is not an "
        "extra gate; the next fresh H3 plus real vertex screen determines "
        "successor viability."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_require_terminal_non_toward_velocity": (
                False
            ),
            "fallback_rule": (
                "After H3 block, restore and screen the same frozen 64 "
                "contact-aware vertices using the exact source action. "
                "Authorize only the unchanged 0.15-rad one-step floor and "
                "actuator bounds, rank by terminal target and global "
                "margin, audit terminal velocity, execute one action, and "
                "immediately run a fresh H3 and vertex screen."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot reuses the exact frozen "
        "64-vertex contact-aware population, action bytes, seeds, 0.15-rad "
        "floor, actuator bounds, and fresh H3 loop. It removes only the "
        "previous terminal nonpositive-velocity proxy, which was a "
        "sufficient but not required condition for the stated five-step "
        "receding safety objective. Terminal velocity remains fully "
        "audited, and every next advance requires a new real contact-aware "
        "one-step shadow. No action substitution, threshold change, live "
        "dispatch, typed recovery, or task-outcome read occurs. It is not "
        "qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict = source._summarize(rows)
    strict_proxy_success = strict.pop(
        "h3_contact_aware_vertex_exact_h1_success"
    )
    completed = strict["completed_cycle_counts"]
    expected = {
        str(seed): RECEDING_CYCLE_COUNT
        for seed in LANE_BASE_SEEDS
    }
    receding_floor_success = bool(
        rows[0]["receding_horizon_success"]
        and completed == expected
        and strict[
            "contact_aware_vertex_exact_h1_exact_action_identity_count"
        ]
        == strict["contact_aware_vertex_exact_h1_execution_count"]
        and strict["candidate_configuration_qpos_identity_count"]
        == strict["candidate_configuration_count"]
        and strict["candidate_configuration_qvel_identity_count"]
        == strict["candidate_configuration_count"]
        and strict["candidate_controller_scope_restore_count"]
        == strict["candidate_configuration_count"]
        and strict["execution_controller_scope_restore_count"]
        == strict["contact_aware_vertex_exact_h1_execution_count"]
        and strict["torque_bound_violation_count"] == 0
    )
    strict.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_contact_aware_vertex_receding_floor_v12_"
                "engineering_pilot_complete"
            ),
            "strict_terminal_proxy_success": strict_proxy_success,
            "terminal_non_toward_velocity_required": False,
            "h3_contact_aware_vertex_receding_floor_success": (
                receding_floor_success
            ),
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return strict


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
            "receding-floor vertex pilot requires a clean worktree"
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
        raise H3ContactAwareVertexRecedingFloorPilotError(
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
            "running_no_outcome_h3_contact_aware_vertex_receding_floor"
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
                gate_horizon_steps=source.GATE_HORIZON_STEPS,
                controller_contact_aware_vertex_exact_h1_ids=(
                    source.CONTACT_AWARE_VERTEX_IDS
                ),
                controller_contact_aware_vertex_target_joint_index=(
                    source.TARGET_JOINT_INDEX
                ),
                controller_contact_aware_vertex_target_joint_side=(
                    source.TARGET_JOINT_SIDE
                ),
                contact_aware_vertex_require_terminal_non_toward_velocity=(
                    False
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.29",
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
        raise H3ContactAwareVertexRecedingFloorPilotError(
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
        raise H3ContactAwareVertexRecedingFloorPilotError(
            "receding-floor summary recomputation differs"
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
