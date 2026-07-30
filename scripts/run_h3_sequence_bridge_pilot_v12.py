#!/usr/bin/env python3
"""Evaluate H3/H1 control with bounded controller-aware bridge sequences."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np


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
    pilot_config as absolute_bridge_config,
)
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
    _restore_identity,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    RECEDING_CYCLE_COUNT,
    TARGET_ID,
    _run_case,
)
from scripts.run_two_stage_policy_aware_recovery_pilot_v12 import (  # noqa: E402
    _candidate_library,
    _execute_actions,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_absolute_safe_h2_bridge_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_sequence_bridge_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-sequence-bridge-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-sequence-bridge-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 3
MAXIMUM_SAFE_BRIDGES_PER_CYCLE = 1
SAFE_BRIDGE_SEED_STRIDE = 2_000
BRIDGE_BEAM_WIDTH = 96
BRIDGE_MAXIMUM_DEPTH = 3
MAXIMUM_POLICY_CANDIDATES = 192
POLICY_CANDIDATES_PER_DEPTH = 64
TARGET_JOINT_INDEX = 1
ANTI_POLICY_SCALES = (0.25, 0.5, 0.75, 1.0)


class H3SequenceBridgePilotError(RuntimeError):
    """Raised when the H3 sequence-bridge pilot must fail closed."""


def _scale_token(value: float) -> str:
    return f"{value:.2f}".replace(".", "p")


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "absolute_safe_h2_bridge_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("absolute_safe_h2_bridge_success") is not False
        or predecessor.get("completed_cycle_counts")
        != {"10509": 2, "10510": 2}
        or predecessor.get("absolute_safe_bridge_candidate_count")
        != 122
        or predecessor.get(
            "post_h2_screened_bridge_candidate_count"
        )
        != 122
        or predecessor.get("safe_bridge_selection_count") != 0
        or predecessor.get("active_warning_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise H3SequenceBridgePilotError(
            "absolute-safe H2 nonpass does not authorize successor"
        )
    config = deepcopy(absolute_bridge_config())
    config["protocol_id"] = (
        "engineering-h3-controller-aware-sequence-bridge-pilot"
    )
    config["bridge_contract"].update(
        {
            "type": "controller_aware_sequence_bridge",
            "gate_horizon_steps": GATE_HORIZON_STEPS,
            "maximum_sequence_depth": BRIDGE_MAXIMUM_DEPTH,
            "beam_width": BRIDGE_BEAM_WIDTH,
            "maximum_policy_candidates": (
                MAXIMUM_POLICY_CANDIDATES
            ),
            "policy_candidates_per_depth": (
                POLICY_CANDIDATES_PER_DEPTH
            ),
            "target_joint_index": TARGET_JOINT_INDEX,
            "anti_policy_scales": list(ANTI_POLICY_SCALES),
        }
    )
    config["receding_horizon"].update(
        {
            "gate_horizon_steps": GATE_HORIZON_STEPS,
            "maximum_safe_bridges_per_cycle": (
                MAXIMUM_SAFE_BRIDGES_PER_CYCLE
            ),
            "safe_bridge_seed_stride": SAFE_BRIDGE_SEED_STRIDE,
            "bridge_sequence_maximum_depth": (
                BRIDGE_MAXIMUM_DEPTH
            ),
            "bridge_beam_width": BRIDGE_BEAM_WIDTH,
            "bridge_maximum_policy_candidates": (
                MAXIMUM_POLICY_CANDIDATES
            ),
            "safe_bridge_gate": (
                "H3 stops one controller cycle earlier than H2. A bounded "
                "bridge sequence may contain at most three actions; every "
                "intermediate replay state must remain at or above the "
                "frozen 0.15 rad absolute-safe floor with no crossing. The "
                "endpoint must produce a fresh H3 allow_exact, and the same "
                "prefix must pass H3 again after exact sequence replay "
                "before only its first policy action advances."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates H3 predictive "
        "screening, H1 policy advancement, and bounded controller-aware "
        "bridge sequences on the sole remaining known v12.6 outlier. Every "
        "bridge intermediate state preserves the frozen 0.15 rad absolute "
        "safe-state floor and strict no-crossing. The bridge is not "
        "recovery; recovery gain and transient-loss parameters remain "
        "unchanged. Endpoint H3 authorization is reconfirmed after exact "
        "sequence replay. All actions remain inside restored simulator "
        "shadow; no live policy dispatch or task outcome read occurs. It is "
        "not qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _controller_aware_sequence_builder(
    config: dict[str, Any],
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    branch_state: Any,
    snapshot: Any,
    contacts: base.ContactCapacityAudit,
    blocked_prefix: np.ndarray | None,
) -> dict[str, Any]:
    if blocked_prefix is None or len(blocked_prefix) < GATE_HORIZON_STEPS:
        raise H3SequenceBridgePilotError(
            "sequence bridge requires the blocked H3 prefix"
        )
    library = dict(_candidate_library(config))
    prefix_array = np.asarray(blocked_prefix, dtype=np.float64)
    policy_sources = {
        "first": prefix_array[0],
        "mean_h3": np.mean(
            prefix_array[:GATE_HORIZON_STEPS], axis=0
        ),
    }
    anti_policy_ids = []
    for source_id, source_action in policy_sources.items():
        for scale in ANTI_POLICY_SCALES:
            action_id = (
                f"anti_policy_{source_id}_scale{_scale_token(scale)}"
            )
            action = np.asarray(source_action, dtype=np.float64).copy()
            action[:6] = np.clip(-scale * action[:6], -1.0, 1.0)
            action[6] = source_action[6]
            library[action_id] = tuple(float(value) for value in action)
            anti_policy_ids.append(action_id)
    floor = float(config["recovery"]["safe_margin_rad"])
    trigger = float(config["episode"]["trigger_margin_rad"])
    initial_target_margin = float(
        limits[TARGET_JOINT_INDEX, 1]
        - branch_state.qpos[TARGET_JOINT_INDEX]
    )
    beam = [
        {
            "action_ids": (),
            "actions": (),
            "target_terminal_margin_rad": initial_target_margin,
            "global_terminal_margin_rad": (
                branch_state.minimum_margin
            ),
            "global_minimum_margin_rad": (
                branch_state.minimum_margin
            ),
        }
    ]
    retained_by_depth = []
    depth_rows = []
    shadow_steps = 0
    restore_identity = True
    for depth in range(1, BRIDGE_MAXIMUM_DEPTH + 1):
        expanded = []
        rejected_floor = 0
        for node in beam:
            for action_id, action in library.items():
                restored = _restore_identity(env, robot, snapshot)
                restore_identity = restore_identity and restored
                action_ids = node["action_ids"] + (action_id,)
                actions = node["actions"] + (action,)
                positions, margins = _execute_actions(
                    env,
                    actions=actions,
                    qidx=qidx,
                    limits=limits,
                    contacts=contacts,
                )
                shadow_steps += len(actions)
                minimum_margin = min(margins)
                if minimum_margin < floor or minimum_margin < trigger:
                    rejected_floor += 1
                    continue
                target_margin = float(
                    limits[TARGET_JOINT_INDEX, 1]
                    - positions[-1][TARGET_JOINT_INDEX]
                )
                expanded.append(
                    {
                        "action_ids": action_ids,
                        "actions": actions,
                        "target_terminal_margin_rad": target_margin,
                        "global_terminal_margin_rad": margins[-1],
                        "global_minimum_margin_rad": minimum_margin,
                    }
                )
        expanded.sort(
            key=lambda node: (
                -node["target_terminal_margin_rad"],
                -node["global_terminal_margin_rad"],
                -node["global_minimum_margin_rad"],
                node["action_ids"],
            )
        )
        beam = expanded[:BRIDGE_BEAM_WIDTH]
        retained_by_depth.append(tuple(beam))
        depth_rows.append(
            {
                "depth": depth,
                "expanded_absolute_safe_count": len(expanded),
                "rejected_absolute_floor_count": rejected_floor,
                "retained_count": len(beam),
                "best_target_terminal_margin_rad": (
                    beam[0]["target_terminal_margin_rad"]
                    if beam
                    else None
                ),
                "best_global_terminal_margin_rad": (
                    max(
                        node["global_terminal_margin_rad"]
                        for node in beam
                    )
                    if beam
                    else None
                ),
            }
        )
        if not beam:
            break
    restore_identity = (
        restore_identity
        and _restore_identity(env, robot, snapshot)
    )
    selected_nodes = []
    for depth_index in reversed(range(len(retained_by_depth))):
        depth = depth_index + 1
        for rank, node in enumerate(
            retained_by_depth[depth_index][
                :POLICY_CANDIDATES_PER_DEPTH
            ]
        ):
            selected_nodes.append((depth, rank, node))
    selected_nodes = selected_nodes[:MAXIMUM_POLICY_CANDIDATES]
    candidate_specs = []
    for policy_rank, (depth, rank, node) in enumerate(selected_nodes):
        candidate_specs.append(
            {
                "candidate_id": (
                    f"h{depth}_r{rank:03d}_"
                    + "-".join(node["action_ids"])
                ),
                "action_ids": node["action_ids"],
                "actions": node["actions"],
                "policy_rank": policy_rank,
                "search_target_terminal_margin_rad": node[
                    "target_terminal_margin_rad"
                ],
            }
        )
    return {
        "candidate_specs": tuple(candidate_specs),
        "shadow_env_step_count": shadow_steps,
        "restore_identity": restore_identity,
        "diagnostics": {
            "base_library_count": (
                len(library) - len(anti_policy_ids)
            ),
            "anti_policy_action_ids": anti_policy_ids,
            "total_action_library_count": len(library),
            "absolute_safe_floor_rad": floor,
            "beam_width": BRIDGE_BEAM_WIDTH,
            "maximum_depth": BRIDGE_MAXIMUM_DEPTH,
            "maximum_policy_candidates": (
                MAXIMUM_POLICY_CANDIDATES
            ),
            "depths": depth_rows,
            "policy_candidate_count": len(candidate_specs),
        },
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H3SequenceBridgePilotError(
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
            "h3_sequence_bridge_v12_engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "result_informed": True,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "advanced_policy_action_steps_per_cycle": 1,
        "bridge_floor_mode": BRIDGE_FLOOR_MODE,
        "bridge_terminal_margin_floor_rad": config[
            "bridge_contract"
        ]["terminal_margin_floor_rad"],
        "bridge_maximum_depth": BRIDGE_MAXIMUM_DEPTH,
        "bridge_beam_width": BRIDGE_BEAM_WIDTH,
        "maximum_policy_candidates": MAXIMUM_POLICY_CANDIDATES,
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
        "h3_sequence_bridge_success": row[
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
        "generated_sequence_candidate_count": len(evaluations),
        "absolute_safe_sequence_candidate_count": sum(
            evaluation["bridge_safe"] for evaluation in evaluations
        ),
        "post_h3_screened_sequence_candidate_count": sum(
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
        "selected_bridge_sequence_ids": [
            bridge["selected_action_id"] for bridge in selected
        ],
        "selected_bridge_action_counts": [
            bridge["selected_action_count"] for bridge in selected
        ],
        "builder_diagnostics": [
            bridge["candidate_builder_diagnostics"]
            for bridge in bridges
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
            "H3 sequence-bridge pilot requires a clean worktree"
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
        raise H3SequenceBridgePilotError(
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
            "running_no_outcome_h3_sequence_bridge"
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
                bridge_candidate_builder=(
                    _controller_aware_sequence_builder
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.18",
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
        raise H3SequenceBridgePilotError(
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
        raise H3SequenceBridgePilotError(
            "H3 sequence-bridge summary recomputation differs"
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
