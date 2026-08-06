#!/usr/bin/env python3
"""Evaluate full-remaining-horizon contact-aware vertex beam search."""

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


from scripts import run_h3_contact_aware_vertex_successor_pilot_v12 as predecessor  # noqa: E402
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
    / "proofalign_h3_contact_aware_vertex_successor_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_contact_aware_vertex_beam_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-beam-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-beam-pilot-v12-summary.v1"
)
BEAM_WIDTH = 64
MAX_BEAM_HORIZON = 4


class H3ContactAwareVertexBeamPilotError(RuntimeError):
    """Raised when the contact-aware beam pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_successor_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_contact_aware_vertex_successor_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 2, "10510": 2}
        or prior.get("selected_contact_aware_vertex_ids")
        != [25, 25]
        or prior.get("selected_safe_successor_counts") != [64, 64]
        or prior.get("successor_candidate_count") != 16_384
        or prior.get("successor_configuration_qpos_identity_count")
        != 16_384
        or prior.get("successor_configuration_qvel_identity_count")
        != 16_384
        or prior.get("successor_controller_scope_restore_count")
        != 16_384
        or prior.get("successor_torque_bound_violation_count") != 0
        or prior.get("minimum_advanced_state_margin_rad", 0) < 0.275
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ContactAwareVertexBeamPilotError(
            "two-step successor nonpass does not authorize beam"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-contact-aware-vertex-beam-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["safe_successor_required"] = False
    contract["beam_width"] = BEAM_WIDTH
    contract["maximum_beam_horizon"] = MAX_BEAM_HORIZON
    contract["beam_horizon_rule"] = (
        "min(maximum_beam_horizon, remaining planned cycles)"
    )
    contract["beam_actions"] = (
        "consecutive exact source-policy actions from the current chunk"
    )
    contract["beam_tail_consumed"] = False
    contract["selection_rule"] = (
        "Expand all 64 vertices per retained state and keep the best 64 "
        "safe sequences by largest trajectory minimum margin, largest "
        "terminal target margin, smallest terminal toward velocity, then "
        "lexicographic sequence. Authorize only a sequence spanning every "
        "remaining planned cycle. Execute its first vertex only and fresh "
        "replan."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_require_safe_successor": False,
            "contact_aware_vertex_beam_width": BEAM_WIDTH,
            "contact_aware_vertex_beam_max_horizon": (
                MAX_BEAM_HORIZON
            ),
            "fallback_rule": (
                "After H3 block, expand the frozen 64 contact-aware "
                "vertices through exact policy actions for all remaining "
                "cycles up to depth four. Retain a width-64 beam using the "
                "0.15-rad floor and trajectory-margin ranking. Authorize "
                "only a full-horizon sequence, execute its first exact "
                "action, then fresh inference and H3."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot replaces the insufficient "
        "two-step successor gate with a width-64 contact-aware beam that "
        "covers every remaining one-action receding cycle up to depth "
        "four. All beam edges use consecutive exact source-policy actions, "
        "restored real contact dynamics, the unchanged 0.15-rad floor, "
        "and actuator bounds. Only the first vertex is consumed before "
        "fresh inference and H3. No action substitution, threshold change, "
        "live dispatch, typed recovery, or task-outcome read occurs. It is "
        "not qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    inherited.pop(
        "h3_contact_aware_vertex_successor_success"
    )
    one_step_success = inherited[
        "one_step_receding_floor_success"
    ]
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
    selected_beams = [
        result["selected"]
        for result in beam_results
        if result["selected"] is not None
    ]
    completed = inherited["completed_cycle_counts"]
    expected = {
        str(seed): RECEDING_CYCLE_COUNT
        for seed in LANE_BASE_SEEDS
    }
    method_success = bool(
        one_step_success
        and completed == expected
        and len(selected_beams) == len(fallbacks)
        and all(
            len(result["selected"]["sequence"])
            == result["horizon"]
            for result in beam_results
        )
        and all(
            result["restore_identity"]
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
                "h3_contact_aware_vertex_beam_v12_"
                "engineering_pilot_complete"
            ),
            "safe_successor_required": False,
            "beam_width": BEAM_WIDTH,
            "maximum_beam_horizon": MAX_BEAM_HORIZON,
            "beam_tail_consumed": False,
            "h3_contact_aware_vertex_beam_success": method_success,
            "beam_screen_count": len(beam_results),
            "beam_horizons": [
                result["horizon"] for result in beam_results
            ],
            "selected_beam_sequences": [
                result["selected"]["sequence"]
                for result in beam_results
                if result["selected"] is not None
            ],
            "selected_beam_trajectory_minimum_margins_rad": [
                result["selected"][
                    "trajectory_minimum_margin_rad"
                ]
                for result in beam_results
                if result["selected"] is not None
            ],
            "beam_configuration_count": sum(
                result["configuration_count"]
                for result in beam_results
            ),
            "beam_configuration_qpos_identity_count": sum(
                result["configuration_qpos_identity_count"]
                for result in beam_results
            ),
            "beam_configuration_qvel_identity_count": sum(
                result["configuration_qvel_identity_count"]
                for result in beam_results
            ),
            "beam_controller_scope_restore_count": sum(
                result["controller_scope_restore_count"]
                for result in beam_results
            ),
            "beam_torque_bound_violation_count": sum(
                result["torque_bound_violation_count"]
                for result in beam_results
            ),
            "contact_aware_vertex_beam_shadow_env_step_count": (
                rows[0][
                    "contact_aware_vertex_beam_shadow_env_step_count"
                ]
            ),
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
            "contact-aware beam pilot requires a clean worktree"
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
        raise H3ContactAwareVertexBeamPilotError(
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
            "running_no_outcome_h3_contact_aware_vertex_beam"
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
                contact_aware_vertex_beam_width=BEAM_WIDTH,
                contact_aware_vertex_beam_max_horizon=(
                    MAX_BEAM_HORIZON
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.31",
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
        raise H3ContactAwareVertexBeamPilotError(
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
        raise H3ContactAwareVertexBeamPilotError(
            "beam summary recomputation differs"
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
