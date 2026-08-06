#!/usr/bin/env python3
"""Evaluate two-phase contact-aware vertex schedules for exact actions."""

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


from scripts import run_h3_contact_aware_vertex_diverse_beam_pilot_v12 as predecessor  # noqa: E402
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
    / "proofalign_h3_contact_aware_vertex_schedule_beam_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-schedule-beam-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-contact-aware-vertex-schedule-beam-pilot-v12-summary.v1"
)
BEAM_WIDTH = predecessor.BEAM_WIDTH
MAX_BEAM_HORIZON = predecessor.MAX_BEAM_HORIZON
RETENTION_STRATEGY = predecessor.RETENTION_STRATEGY
RANKED_SCHEDULE_VERTEX_IDS = (
    25,
    9,
    29,
    13,
    57,
    41,
    27,
    11,
)
SCHEDULE_VERTEX_IDS = tuple(sorted(RANKED_SCHEDULE_VERTEX_IDS))
VERTEX_SCHEDULES = tuple(
    (first_vertex_id, second_vertex_id)
    for first_vertex_id in RANKED_SCHEDULE_VERTEX_IDS
    for second_vertex_id in RANKED_SCHEDULE_VERTEX_IDS
)
SCHEDULE_SWITCH_SUBSTEP_INDEX = 12
CONTROLLER_MODE_COUNT = len(VERTEX_SCHEDULES)


class H3ContactAwareVertexScheduleBeamPilotError(RuntimeError):
    """Raised when the two-phase schedule beam must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_contact_aware_vertex_diverse_beam_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_contact_aware_vertex_diverse_beam_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("beam_horizons") != [4, 4]
        or prior.get("beam_screen_count") != 2
        or prior.get("beam_retention_strategy")
        != RETENTION_STRATEGY
        or prior.get("beam_configuration_count") != 16_512
        or prior.get("beam_configuration_qpos_identity_count")
        != 16_512
        or prior.get("beam_configuration_qvel_identity_count")
        != 16_512
        or prior.get("beam_controller_scope_restore_count")
        != 16_512
        or prior.get("beam_torque_bound_violation_count") != 0
        or prior.get(
            "best_velocity_terminal_toward_velocities_rad_s"
        )[1]
        < 4.329
        or prior.get(
            "best_velocity_terminal_toward_velocities_rad_s"
        )[4]
        < 4.329
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3ContactAwareVertexScheduleBeamPilotError(
            "diverse-beam nonpass does not authorize schedule beam"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-contact-aware-vertex-schedule-beam-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["controller_mode_type"] = (
        "two_phase_contact_aware_vertex_schedule"
    )
    contract["candidate_vertex_ids"] = list(SCHEDULE_VERTEX_IDS)
    contract["candidate_vertex_count"] = len(SCHEDULE_VERTEX_IDS)
    contract["ranked_schedule_vertex_ids"] = list(
        RANKED_SCHEDULE_VERTEX_IDS
    )
    contract["blend_fractions"] = []
    contract["vertex_schedules"] = [
        list(schedule) for schedule in VERTEX_SCHEDULES
    ]
    contract["schedule_switch_substep_index"] = (
        SCHEDULE_SWITCH_SUBSTEP_INDEX
    )
    contract["controller_mode_count"] = CONTROLLER_MODE_COUNT
    contract["schedule_rule"] = (
        "For each exact action, use schedule vertex A for controller "
        "substeps 0 through 11 and vertex B from substep 12 onward. "
        "Enumerate all ordered pairs from the frozen top-eight contact "
        "patterns. Joint 1 remains at its away-limit actuator bound in "
        "both phases."
    )
    contract["selection_rule"] = (
        "Expand the 64 frozen ordered two-phase schedules with the "
        "unchanged diverse width-64 frontier. Authorize only a sequence "
        "spanning every remaining planned cycle. Execute its first "
        "schedule with exact source action bytes, then fresh replan."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_candidate_ids": list(
                SCHEDULE_VERTEX_IDS
            ),
            "contact_aware_vertex_beam_blend_fractions": [],
            "contact_aware_vertex_beam_vertex_schedules": [
                list(schedule) for schedule in VERTEX_SCHEDULES
            ],
            "contact_aware_vertex_beam_schedule_switch_substep_index": (
                SCHEDULE_SWITCH_SUBSTEP_INDEX
            ),
            "contact_aware_vertex_beam_controller_mode_count": (
                CONTROLLER_MODE_COUNT
            ),
            "fallback_rule": (
                "After H3 blocks, search all 8x8 frozen two-phase "
                "contact-aware schedules under the unchanged diverse "
                "width-64 beam and 0.15-rad floor. Execute only the first "
                "exact-action schedule, then fresh inference."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot changes only the "
        "within-action torque parameterization after every fixed mode "
        "ended the second exact action above 4.329 rad/s toward the "
        "joint limit. It enumerates 64 frozen two-phase schedules while "
        "keeping exact source action bytes, target-joint away torque, "
        "actuator bounds, beam width/horizon/retention, the 0.15-rad "
        "floor, and fresh H3 replanning unchanged. No live dispatch, "
        "typed recovery, or task-outcome read occurs. It is engineering/"
        "shadow evidence, not qualification, task utility, deployment, "
        "or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    inherited.pop(
        "h3_contact_aware_vertex_diverse_beam_success"
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
    completed = inherited["completed_cycle_counts"]
    expected = {
        str(seed): RECEDING_CYCLE_COUNT
        for seed in LANE_BASE_SEEDS
    }
    method_success = bool(
        inherited["one_step_receding_floor_success"]
        and completed == expected
        and beam_results
        and len(beam_results) == len(fallbacks)
        and all(
            result["mode_count"] == CONTROLLER_MODE_COUNT
            and result["blend_fractions"] == []
            and result["vertex_schedules"]
            == [list(schedule) for schedule in VERTEX_SCHEDULES]
            and result["schedule_switch_substep_index"]
            == SCHEDULE_SWITCH_SUBSTEP_INDEX
            and result["retention_strategy"] == RETENTION_STRATEGY
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
                "h3_contact_aware_vertex_schedule_beam_v12_"
                "engineering_pilot_complete"
            ),
            "candidate_vertex_ids": list(SCHEDULE_VERTEX_IDS),
            "ranked_candidate_vertex_ids": list(
                RANKED_SCHEDULE_VERTEX_IDS
            ),
            "vertex_blend_fractions": [],
            "controller_mode_type": (
                "two_phase_contact_aware_vertex_schedule"
            ),
            "controller_mode_count": CONTROLLER_MODE_COUNT,
            "schedule_switch_substep_index": (
                SCHEDULE_SWITCH_SUBSTEP_INDEX
            ),
            "h3_contact_aware_vertex_schedule_beam_success": (
                method_success
            ),
            "selected_first_vertex_schedules": [
                fallback["selected_schedule_vertex_ids"]
                for fallback in fallbacks
                if fallback["authorized"]
            ],
            "selected_schedule_switch_substep_indices": [
                fallback[
                    "selected_schedule_switch_substep_index"
                ]
                for fallback in fallbacks
                if fallback["authorized"]
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
            "contact-aware schedule-beam pilot requires a clean worktree"
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
        raise H3ContactAwareVertexScheduleBeamPilotError(
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
            "running_no_outcome_h3_contact_aware_vertex_schedule_beam"
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
                    SCHEDULE_VERTEX_IDS
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
                contact_aware_vertex_beam_vertex_schedules=(
                    VERTEX_SCHEDULES
                ),
                contact_aware_vertex_beam_schedule_switch_substep_index=(
                    SCHEDULE_SWITCH_SUBSTEP_INDEX
                ),
                contact_aware_vertex_beam_retention_strategy=(
                    RETENTION_STRATEGY
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.34",
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
        raise H3ContactAwareVertexScheduleBeamPilotError(
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
        raise H3ContactAwareVertexScheduleBeamPilotError(
            "schedule-beam summary recomputation differs"
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
