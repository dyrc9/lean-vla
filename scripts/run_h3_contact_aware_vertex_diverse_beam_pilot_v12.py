#!/usr/bin/env python3
"""Evaluate a margin/velocity-diverse smooth torque-mode beam."""

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


from scripts import run_h3_contact_aware_vertex_blend_beam_pilot_v12 as predecessor  # noqa: E402
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
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
    / "proofalign_h3_contact_aware_vertex_diverse_beam_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-diverse-beam-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-diverse-beam-pilot-v12-summary.v1"
)
BEAM_WIDTH = predecessor.BEAM_WIDTH
MAX_BEAM_HORIZON = predecessor.MAX_BEAM_HORIZON
CONTACT_VERTEX_IDS = predecessor.CONTACT_VERTEX_IDS
VERTEX_BLEND_FRACTIONS = predecessor.VERTEX_BLEND_FRACTIONS
CONTROLLER_MODE_COUNT = predecessor.CONTROLLER_MODE_COUNT
RETENTION_STRATEGY = "margin_velocity_diverse"
MARGIN_QUOTA = BEAM_WIDTH // 2
VELOCITY_QUOTA = BEAM_WIDTH - MARGIN_QUOTA


class H3ContactAwareVertexDiverseBeamPilotError(RuntimeError):
    """Raised when the diverse smooth-mode beam must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_blend_beam_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_contact_aware_vertex_blend_beam_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("beam_horizons") != [4, 4]
        or prior.get("beam_screen_count") != 2
        or prior.get("selected_beam_mode_sequences") != []
        or prior.get("beam_configuration_count") != 16_512
        or prior.get("beam_configuration_qpos_identity_count")
        != 16_512
        or prior.get("beam_configuration_qvel_identity_count")
        != 16_512
        or prior.get("beam_controller_scope_restore_count")
        != 16_512
        or prior.get("beam_torque_bound_violation_count") != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ContactAwareVertexDiverseBeamPilotError(
            "smooth-beam nonpass does not authorize diverse beam"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-contact-aware-vertex-diverse-beam-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["beam_retention_strategy"] = RETENTION_STRATEGY
    contract["beam_margin_quota"] = MARGIN_QUOTA
    contract["beam_velocity_quota"] = VELOCITY_QUOTA
    contract["beam_retention_rule"] = (
        "At each depth retain the top 32 nodes under the frozen "
        "trajectory-margin ranking and the 32 nodes with smallest "
        "terminal toward-limit velocity. Deduplicate their sequences, "
        "then fill any overlap-created vacancies from the original "
        "trajectory-margin ranking until width 64."
    )
    contract["selection_rule"] = (
        "Use the frozen 64 smooth controller modes and diverse width-64 "
        "frontier at every depth. Authorize only a sequence spanning "
        "every remaining planned cycle. Among complete retained nodes "
        "select by the original trajectory-margin ranking, execute its "
        "first mode with exact source action bytes, then fresh replan."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_beam_retention_strategy": (
                RETENTION_STRATEGY
            ),
            "contact_aware_vertex_beam_margin_quota": MARGIN_QUOTA,
            "contact_aware_vertex_beam_velocity_quota": (
                VELOCITY_QUOTA
            ),
            "fallback_rule": (
                "After H3 blocks, expand the unchanged smooth 64-mode "
                "library. Preserve half the beam for maximum trajectory "
                "margin and half for minimum terminal toward velocity, "
                "under the unchanged 0.15-rad floor. Execute only the "
                "first exact-action mode and then fresh inference."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot changes only beam "
        "retention after the smooth-mode run showed 4096 safe depth-two "
        "nodes but margin pruning retained no depth-three predecessor. "
        "The controller modes, action bytes, width, horizon, 0.15-rad "
        "floor, actuator bounds, first-mode consumption, and fresh H3 "
        "replan are unchanged. No live dispatch, typed recovery, or "
        "task-outcome read occurs. It is engineering/shadow evidence, "
        "not qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    blend_success = inherited.pop(
        "h3_contact_aware_vertex_blend_beam_success"
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
    depth_audits = [
        depth["retention_audit"]
        for result in beam_results
        for depth in result["depth_summaries"]
    ]
    method_success = bool(
        blend_success
        and beam_results
        and depth_audits
        and all(
            result["retention_strategy"] == RETENTION_STRATEGY
            for result in beam_results
        )
        and all(
            audit["strategy"] == RETENTION_STRATEGY
            and audit["margin_quota"] == MARGIN_QUOTA
            and audit["velocity_quota"] == VELOCITY_QUOTA
            for audit in depth_audits
        )
    )
    inherited.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_contact_aware_vertex_diverse_beam_v12_"
                "engineering_pilot_complete"
            ),
            "beam_retention_strategy": RETENTION_STRATEGY,
            "beam_margin_quota": MARGIN_QUOTA,
            "beam_velocity_quota": VELOCITY_QUOTA,
            "h3_contact_aware_vertex_diverse_beam_success": (
                method_success
            ),
            "retained_velocity_top_counts": [
                audit["retained_velocity_top_count"]
                for audit in depth_audits
            ],
            "margin_velocity_top_overlap_counts": [
                audit["margin_velocity_top_overlap_count"]
                for audit in depth_audits
            ],
            "best_velocity_terminal_toward_velocities_rad_s": [
                audit[
                    "best_velocity_terminal_toward_velocity_rad_s"
                ]
                for audit in depth_audits
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
            "contact-aware diverse-beam pilot requires a clean worktree"
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
        raise H3ContactAwareVertexDiverseBeamPilotError(
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
            "running_no_outcome_h3_contact_aware_vertex_diverse_beam"
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
                    CONTACT_VERTEX_IDS
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
                contact_aware_vertex_beam_width=BEAM_WIDTH,
                contact_aware_vertex_beam_max_horizon=(
                    MAX_BEAM_HORIZON
                ),
                contact_aware_vertex_beam_blend_fractions=(
                    VERTEX_BLEND_FRACTIONS
                ),
                contact_aware_vertex_beam_retention_strategy=(
                    RETENTION_STRATEGY
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.33",
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
        raise H3ContactAwareVertexDiverseBeamPilotError(
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
        raise H3ContactAwareVertexDiverseBeamPilotError(
            "diverse-beam summary recomputation differs"
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
