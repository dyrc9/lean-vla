#!/usr/bin/env python3
"""Evaluate successor-viable contact-aware exact-H1 vertices."""

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


from scripts import run_h3_contact_aware_vertex_receding_floor_pilot_v12 as predecessor  # noqa: E402
from scripts import run_h3_contact_aware_vertex_exact_h1_pilot_v12 as vertices  # noqa: E402
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
    / "proofalign_h3_contact_aware_vertex_receding_floor_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_contact_aware_vertex_successor_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-successor-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-successor-pilot-v12-summary.v1"
)


class H3ContactAwareVertexSuccessorPilotError(RuntimeError):
    """Raised when the successor-viable pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_receding_floor_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_contact_aware_vertex_receding_floor_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 3, "10510": 3}
        or prior.get("safe_contact_aware_vertex_counts")
        != [64, 64, 0, 64, 64, 0]
        or prior.get("selected_contact_aware_vertex_ids")
        != [25, 9, 25, 9]
        or prior.get("minimum_advanced_state_margin_rad", 0) < 0.20
        or prior.get("candidate_configuration_count") != 384
        or prior.get("candidate_configuration_qpos_identity_count")
        != 384
        or prior.get("candidate_configuration_qvel_identity_count")
        != 384
        or prior.get("candidate_controller_scope_restore_count")
        != 384
        or prior.get(
            "contact_aware_vertex_exact_h1_exact_action_identity_count"
        )
        != 4
        or prior.get("maximum_prediction_execution_margin_error_rad")
        != 0.0
        or prior.get(
            "maximum_prediction_execution_target_joint_velocity_error_rad_s"
        )
        != 0.0
        or prior.get("torque_bound_violation_count") != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ContactAwareVertexSuccessorPilotError(
            "greedy vertex nonpass does not authorize successor"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-contact-aware-vertex-successor-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["safe_successor_required"] = True
    contract["successor_action"] = (
        "second exact source-policy action from the same frozen chunk"
    )
    contract["successor_population"] = (
        "same frozen 64 contact-aware actuator vertices"
    )
    contract["successor_consumed"] = False
    contract["selection_rule"] = (
        "A first vertex must satisfy the 0.15-rad one-step floor and "
        "have at least one second-action vertex successor satisfying the "
        "same floor. Rank by largest safe-successor count, then largest "
        "first-step target and global margin, then lowest vertex ID. "
        "Execute only the first action and immediately fresh replan."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_require_safe_successor": True,
            "fallback_rule": (
                "After H3 block, screen each first-action vertex. At its "
                "restored endpoint, screen all 64 vertices with the second "
                "exact action from the same policy chunk. Authorize only "
                "first vertices with a nonempty 0.15-safe successor set, "
                "rank by successor count and margin, execute only the "
                "first exact action, then fresh inference and H3."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot adds a bounded two-step "
        "viability gate to the frozen 64-vertex contact-aware method. The "
        "first and successor screens use exact source-policy actions from "
        "the same chunk, restored real contact dynamics, unchanged "
        "0.15-rad floor, and actuator bounds. The successor is not "
        "consumed; actual execution advances one exact action and then "
        "fresh replans. Terminal velocity remains audited but is not a "
        "hard proxy gate. No action substitution, threshold change, live "
        "dispatch, typed recovery, or task-outcome read occurs. It is not "
        "qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = predecessor._summarize(rows)
    base_success = summary.pop(
        "h3_contact_aware_vertex_receding_floor_success"
    )
    fallbacks = [
        fallback
        for lane in rows[0]["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle[
            "contact_aware_vertex_exact_h1_fallbacks"
        ]
    ]
    candidates = [
        candidate
        for fallback in fallbacks
        for candidate in fallback["candidate_evaluations"]
    ]
    successor_rows = [
        successor
        for candidate in candidates
        for successor in candidate["successor_evaluations"]
    ]
    completed = summary["completed_cycle_counts"]
    expected = {
        str(seed): RECEDING_CYCLE_COUNT
        for seed in LANE_BASE_SEEDS
    }
    method_success = bool(
        base_success
        and completed == expected
        and all(
            fallback["safe_successor_required"]
            for fallback in fallbacks
        )
        and all(
            candidate["safe_successor_count"] > 0
            for candidate in candidates
            if candidate["selected"]
        )
        and all(
            successor["configuration"][
                "configuration_qpos_identity"
            ]
            and successor["configuration"][
                "configuration_qvel_identity"
            ]
            and successor["controller_scope_restored"]
            and successor["torque_bound_violation_count"] == 0
            for successor in successor_rows
        )
    )
    summary.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_contact_aware_vertex_successor_v12_"
                "engineering_pilot_complete"
            ),
            "one_step_receding_floor_success": base_success,
            "safe_successor_required": True,
            "successor_consumed": False,
            "h3_contact_aware_vertex_successor_success": (
                method_success
            ),
            "selected_safe_successor_counts": [
                candidate["safe_successor_count"]
                for candidate in candidates
                if candidate["selected"]
            ],
            "successor_candidate_count": len(successor_rows),
            "successor_safe_candidate_count": sum(
                successor["safe"]
                for successor in successor_rows
            ),
            "successor_configuration_qpos_identity_count": sum(
                successor["configuration"][
                    "configuration_qpos_identity"
                ]
                for successor in successor_rows
            ),
            "successor_configuration_qvel_identity_count": sum(
                successor["configuration"][
                    "configuration_qvel_identity"
                ]
                for successor in successor_rows
            ),
            "successor_controller_scope_restore_count": sum(
                successor["controller_scope_restored"]
                for successor in successor_rows
            ),
            "successor_torque_bound_violation_count": sum(
                successor["torque_bound_violation_count"]
                for successor in successor_rows
            ),
            "contact_aware_vertex_successor_shadow_env_step_count": (
                rows[0][
                    "contact_aware_vertex_successor_shadow_env_step_count"
                ]
            ),
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
            "successor-viable vertex pilot requires a clean worktree"
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
        raise H3ContactAwareVertexSuccessorPilotError(
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
            "running_no_outcome_h3_contact_aware_vertex_successor"
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
                controller_contact_aware_vertex_exact_h1_ids=(
                    vertices.CONTACT_AWARE_VERTEX_IDS
                ),
                controller_contact_aware_vertex_target_joint_index=(
                    vertices.TARGET_JOINT_INDEX
                ),
                controller_contact_aware_vertex_target_joint_side=(
                    vertices.TARGET_JOINT_SIDE
                ),
                contact_aware_vertex_require_terminal_non_toward_velocity=(
                    False
                ),
                contact_aware_vertex_require_safe_successor=True,
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.30",
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
        raise H3ContactAwareVertexSuccessorPilotError(
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
        raise H3ContactAwareVertexSuccessorPilotError(
            "successor summary recomputation differs"
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
