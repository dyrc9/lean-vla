#!/usr/bin/env python3
"""Search variable primitive sequences targeted at the diagnosed joint."""

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


from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_continuous_blend_recovery_pilot_v12 import (  # noqa: E402
    pilot_config as continuous_config,
)
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
    _restore_identity,
)
from scripts.run_two_stage_policy_aware_recovery_pilot_v12 import (  # noqa: E402
    TARGET_ID,
    _candidate_library,
    _execute_actions,
    _run_case,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_continuous_blend_recovery_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_joint_targeted_beam_recovery_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.joint-targeted-beam-recovery-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.joint-targeted-beam-recovery-pilot-v12-summary.v1"
)
TARGET_JOINT_INDEX = 1
TARGET_JOINT_SIDE = "upper"
BEAM_WIDTH = 24
MAX_DEPTH = 10
MAX_POLICY_CANDIDATES = 96


class JointTargetedBeamPilotError(RuntimeError):
    """Raised when the joint-targeted pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "continuous_blend_recovery_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("selection_succeeded") is not False
        or predecessor.get("raw_candidate_count") != 164
        or predecessor.get("recovery_eligible_candidate_count") != 164
        or predecessor.get("best_seed0_limiting_joint_index")
        != TARGET_JOINT_INDEX
        or predecessor.get("best_seed0_limiting_joint_side")
        != TARGET_JOINT_SIDE
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise JointTargetedBeamPilotError(
            "continuous nonpass does not authorize joint-targeted search"
        )
    config = deepcopy(continuous_config())
    config["protocol_id"] = (
        "engineering-joint-targeted-beam-recovery-pilot"
    )
    config["generator"] = {
        "mode": "result_informed_joint_targeted_beam",
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "action_ids": list(_candidate_library(config)),
        "beam_width": BEAM_WIDTH,
        "maximum_depth": MAX_DEPTH,
        "maximum_policy_candidates": MAX_POLICY_CANDIDATES,
        "transient_gate": (
            "Every retained search sequence must preserve the original "
            "max-transient-margin-loss and no-crossing rules."
        ),
        "beam_rank_rule": (
            "Largest target-joint terminal margin, largest global terminal "
            "margin, largest global minimum margin, then action IDs."
        ),
        "policy_rank_rule": (
            "Largest target-joint terminal margin, shortest sequence, "
            "largest global terminal/minimum margin, then candidate ID."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering pilot uses simulator-shadow beam "
        "search to generate bounded primitive sequences targeted at the "
        "diagnosed joint-1 upper-margin failure on the sole remaining known "
        "v12.6 outlier. Every search node preserves the original transient "
        "and crossing gates, and every policy candidate passes the original "
        "recovery selector. Policy screens remain restored shadow branches; "
        "no typed live recovery or policy action is dispatched and no task "
        "outcome is read. It is not qualification, efficacy, deployment, "
        "or physical-safety evidence."
    )
    return config


def _beam_candidate_builder(
    config: dict[str, Any],
    *,
    env: Any,
    robot: Any,
    qidx: Any,
    limits: Any,
    trigger_state: Any,
    snapshot: Any,
    contacts: base.ContactCapacityAudit,
) -> dict[str, Any]:
    library = _candidate_library(config)
    baseline = float(trigger_state.minimum_margin)
    transient_floor = baseline - float(
        config["recovery"]["max_transient_margin_loss_rad"]
    )
    safe_margin = float(config["recovery"]["safe_margin_rad"])
    terminal_gain = float(
        config["recovery"]["required_margin_gain_rad"]
    )
    beam = [
        {
            "action_ids": (),
            "actions": (),
            "terminal_target_margin_rad": (
                float(limits[TARGET_JOINT_INDEX, 1])
                - float(trigger_state.qpos[TARGET_JOINT_INDEX])
            ),
            "terminal_global_margin_rad": baseline,
            "minimum_global_margin_rad": baseline,
        }
    ]
    collected = []
    depth_rows = []
    shadow_steps = 0
    restore_identity = True
    for depth in range(1, MAX_DEPTH + 1):
        expanded = []
        rejected_transient = 0
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
                if min(margins) < 0 or min(margins) < transient_floor:
                    rejected_transient += 1
                    continue
                target_margin = float(
                    limits[TARGET_JOINT_INDEX, 1]
                    - positions[-1][TARGET_JOINT_INDEX]
                )
                expanded.append(
                    {
                        "action_ids": action_ids,
                        "actions": actions,
                        "terminal_target_margin_rad": target_margin,
                        "terminal_global_margin_rad": margins[-1],
                        "minimum_global_margin_rad": min(margins),
                    }
                )
        expanded.sort(
            key=lambda node: (
                -node["terminal_target_margin_rad"],
                -node["terminal_global_margin_rad"],
                -node["minimum_global_margin_rad"],
                node["action_ids"],
            )
        )
        beam = expanded[:BEAM_WIDTH]
        eligible_at_depth = [
            node
            for node in beam
            if node["terminal_global_margin_rad"] >= safe_margin
            and node["terminal_global_margin_rad"]
            >= baseline + terminal_gain
        ]
        collected.extend(eligible_at_depth)
        depth_rows.append(
            {
                "depth": depth,
                "expanded_transient_safe_count": len(expanded),
                "rejected_transient_count": rejected_transient,
                "retained_count": len(beam),
                "recovery_terminal_eligible_retained_count": len(
                    eligible_at_depth
                ),
                "best_terminal_target_margin_rad": (
                    beam[0]["terminal_target_margin_rad"]
                    if beam
                    else None
                ),
                "best_terminal_global_margin_rad": (
                    max(
                        node["terminal_global_margin_rad"]
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
    collected.sort(
        key=lambda node: (
            -node["terminal_target_margin_rad"],
            len(node["actions"]),
            -node["terminal_global_margin_rad"],
            -node["minimum_global_margin_rad"],
            node["action_ids"],
        )
    )
    selected_nodes = collected[:MAX_POLICY_CANDIDATES]
    specs = []
    for rank, node in enumerate(selected_nodes):
        action_id_text = "-".join(node["action_ids"])
        specs.append(
            {
                "candidate_id": (
                    f"joint1_upper_beam_r{rank:03d}_"
                    f"h{len(node['actions'])}_{action_id_text}"
                ),
                "first_stage_candidate_id": "beam_search",
                "first_stage_action_id": node["action_ids"][0],
                "first_stage_horizon": 1,
                "second_stage_action_id": "variable_sequence",
                "second_stage_horizon": len(node["actions"]) - 1,
                "action_count": len(node["actions"]),
                "action_ids": node["action_ids"],
                "actions": node["actions"],
                "target_joint_index": TARGET_JOINT_INDEX,
                "target_joint_side": TARGET_JOINT_SIDE,
                "search_terminal_target_margin_rad": node[
                    "terminal_target_margin_rad"
                ],
            }
        )
    if not specs:
        raise JointTargetedBeamPilotError(
            "beam search produced no recovery-terminal candidate"
        )
    return {
        "candidate_specs": tuple(specs),
        "shadow_env_step_count": shadow_steps,
        "restore_identity": restore_identity,
        "diagnostics": {
            "depths": depth_rows,
            "recovery_terminal_node_count_before_cap": len(collected),
            "policy_candidate_count_after_cap": len(specs),
            "best_terminal_target_margin_rad": selected_nodes[0][
                "terminal_target_margin_rad"
            ],
        },
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise JointTargetedBeamPilotError(
            "expected exactly the frozen target row"
        )
    row = rows[0]
    selected = row["selected_policy_aware_candidate"]
    screened = [
        item
        for item in row["candidate_evaluations"]
        if item["policy_screened"]
    ]
    best_seed0 = (
        max(
            screened,
            key=lambda item: item["seed_results"][0][
                "minimum_shadow_margin_rad"
            ],
        )
        if screened
        else None
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "joint_targeted_beam_recovery_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "target_joint_index": TARGET_JOINT_INDEX,
        "target_joint_side": TARGET_JOINT_SIDE,
        "raw_candidate_count": row["raw_candidate_count"],
        "recovery_eligible_candidate_count": row[
            "recovery_eligible_candidate_count"
        ],
        "policy_screened_candidate_count": row[
            "policy_screened_candidate_count"
        ],
        "selection_succeeded": selected is not None,
        "selected_policy_aware_candidate": (
            selected["candidate_id"] if selected is not None else None
        ),
        "selected_candidate_detail": selected,
        "best_seed0_candidate": (
            best_seed0["candidate_id"]
            if best_seed0 is not None
            else None
        ),
        "best_seed0_minimum_shadow_margin_rad": (
            best_seed0["seed_results"][0][
                "minimum_shadow_margin_rad"
            ]
            if best_seed0 is not None
            else None
        ),
        "best_generated_terminal_target_margin_rad": row[
            "generator_diagnostics"
        ]["best_terminal_target_margin_rad"],
        "generator_search_shadow_env_step_count": row[
            "generator_search_shadow_env_step_count"
        ],
        "generator_diagnostics": row["generator_diagnostics"],
        "branch_restore_identity_rate": float(
            row["branch_restore_identity"]
        ),
        "joint_limit_crossing_candidate_count": sum(
            item["joint_limit_crossed"]
            for item in row["candidate_evaluations"]
        ),
        "policy_load_count": 1,
        "policy_inference_count": row["policy_inference_count"],
        "policy_shadow_env_step_count": row[
            "policy_shadow_env_step_count"
        ],
        "candidate_generation_shadow_env_step_count": row[
            "candidate_generation_shadow_env_step_count"
        ],
        "candidate_replay_shadow_env_step_count": row[
            "candidate_replay_shadow_env_step_count"
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
        "claim_boundary": pilot_config()["claim_boundary"],
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
            "joint-targeted beam pilot requires a clean worktree"
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
        raise JointTargetedBeamPilotError(
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
            "running_no_outcome_joint_targeted_beam_pilot"
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
                candidate_spec_builder=_beam_candidate_builder,
                candidate_rank_mode="target_joint",
                row_schema=ROW_SCHEMA,
                source_version="v12.10",
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
        raise JointTargetedBeamPilotError(
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
        raise JointTargetedBeamPilotError(
            "joint-targeted summary recomputation differs"
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
        (args.preflight, args.execute, args.validate_results)
    ) != 1:
        parser.error(
            "choose one of --preflight, --execute, or --validate-results"
        )
    if args.validate_results:
        payload = _validate()
    else:
        if args.gpu is None or args.egl_gpu is None:
            parser.error(
                "--preflight/--execute require --gpu and --egl-gpu"
            )
        config = pilot_config()
        if args.preflight:
            payload = _preflight(
                config,
                policy_gpu=args.gpu,
                egl_gpu=args.egl_gpu,
            )
        else:
            payload = _run(
                policy_gpu=args.gpu, egl_gpu=args.egl_gpu
            )
    print(_canonical(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
