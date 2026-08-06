#!/usr/bin/env python3
"""Evaluate H2-screen/H1-advance receding control with scaled bridges."""

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
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    RECEDING_CYCLE_COUNT,
    TARGET_ID,
    _run_case,
)
from scripts.run_safe_bridge_receding_horizon_pilot_v12 import (  # noqa: E402
    pilot_config as bridge_config,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_safe_bridge_receding_horizon_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h2_scaled_bridge_receding_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h2-scaled-bridge-receding-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h2-scaled-bridge-receding-pilot-v12-summary.v1"
)
GATE_HORIZON_STEPS = 2
BRIDGE_SCALES = (0.1, 0.25, 0.5, 0.75, 1.0)
MAXIMUM_SAFE_BRIDGES_PER_CYCLE = 2
SAFE_BRIDGE_SEED_STRIDE = 2_000


class H2ScaledBridgePilotError(RuntimeError):
    """Raised when the H2 scaled-bridge pilot must fail closed."""


def _scale_token(value: float) -> str:
    return f"{value:.2f}".replace(".", "p")


def _scaled_bridge_library(
    source: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded = []
    for spec in source:
        action_id = str(spec["candidate_id"])
        action = tuple(float(value) for value in spec["action"])
        if action_id == "hold":
            expanded.append(deepcopy(spec))
            continue
        for scale in BRIDGE_SCALES:
            candidate_id = (
                action_id
                if scale == 1.0
                else f"{action_id}_scale{_scale_token(scale)}"
            )
            expanded.append(
                {
                    "candidate_id": candidate_id,
                    "action": [
                        *(value * scale for value in action[:6]),
                        action[6],
                    ],
                }
            )
    return expanded


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "safe_bridge_receding_horizon_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "safe_bridge_receding_horizon_success"
        )
        is not False
        or predecessor.get("safe_bridge_search_count") != 2
        or predecessor.get("safe_bridge_selection_count") != 0
        or predecessor.get("bridge_post_h1_shadow_env_step_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
    ):
        raise H2ScaledBridgePilotError(
            "full-scale bridge nonpass does not authorize H2 successor"
        )
    config = deepcopy(bridge_config())
    config["protocol_id"] = (
        "engineering-h2-scaled-bridge-receding-pilot"
    )
    config["recovery"]["candidate_library"] = (
        _scaled_bridge_library(
            config["recovery"]["candidate_library"]
        )
    )
    config["receding_horizon"].update(
        {
            "gate_horizon_steps": GATE_HORIZON_STEPS,
            "advanced_policy_action_steps_per_cycle": 1,
            "maximum_safe_bridges_per_cycle": (
                MAXIMUM_SAFE_BRIDGES_PER_CYCLE
            ),
            "safe_bridge_seed_stride": SAFE_BRIDGE_SEED_STRIDE,
            "safe_bridge_action_ids": [
                spec["candidate_id"]
                for spec in config["recovery"]["candidate_library"]
            ],
            "safe_bridge_scales": list(BRIDGE_SCALES),
            "gate_rule": (
                "The exact first two policy actions must pass the unchanged "
                "predictive threshold before only the first action advances."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates H2 predictive "
        "screening with H1 shadow advancement and bounded scaled one-step "
        "bridges on the sole remaining known v12.6 outlier. The predictive "
        "threshold, transient floor, no-crossing rule, and recovery contract "
        "are unchanged. A bridge uses a frozen primitive direction scaled "
        "within [0.1,1.0], remains a separately typed non-recovery action, "
        "and must produce a fresh post-bridge H2 allow before execution. "
        "All advances occur only in restored simulator shadow; no live "
        "policy action is dispatched and no task outcome is read. It is not "
        "qualification, task utility, deployment, or physical-safety "
        "evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise H2ScaledBridgePilotError(
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
    executed = [
        bridge for bridge in bridges if bridge["executed_in_shadow"]
    ]
    bridge_evaluations = [
        evaluation
        for bridge in bridges
        for evaluation in bridge["candidate_evaluations"]
    ]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "h2_scaled_bridge_receding_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "gate_horizon_steps": GATE_HORIZON_STEPS,
        "advanced_policy_action_steps_per_cycle": 1,
        "scaled_bridge_candidate_count": len(
            pilot_config()["recovery"]["candidate_library"]
        ),
        "lane_count": len(row["lane_results"]),
        "planned_cycle_count_per_lane": RECEDING_CYCLE_COUNT,
        "completed_cycle_counts": {
            str(lane["base_seed"]): lane["completed_cycle_count"]
            for lane in row["lane_results"]
        },
        "safe_lane_count": sum(
            lane["lane_safe"] for lane in row["lane_results"]
        ),
        "h2_scaled_bridge_success": row[
            "receding_horizon_success"
        ],
        "total_fresh_policy_attempt_count": len(attempts),
        "h2_allow_attempt_count": sum(
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
        "transient_safe_bridge_candidate_count": sum(
            evaluation["transient_safe"]
            for evaluation in bridge_evaluations
        ),
        "post_h2_screened_bridge_candidate_count": sum(
            evaluation["policy_screened"]
            for evaluation in bridge_evaluations
        ),
        "safe_bridge_selection_count": sum(
            bridge["selected_action_id"] is not None
            for bridge in bridges
        ),
        "safe_bridge_execution_count": len(executed),
        "safe_bridge_selected_action_ids": [
            bridge["selected_action_id"] for bridge in bridges
        ],
        "attempt_counts_by_lane_cycle": {
            f"{lane['base_seed']}:{cycle['cycle_index']}": (
                cycle["attempt_count"]
            )
            for lane in row["lane_results"]
            for cycle in lane["cycles"]
        },
        "bridge_counts_by_lane_cycle": {
            f"{lane['base_seed']}:{cycle['cycle_index']}": len(
                cycle["safe_bridges"]
            )
            for lane in row["lane_results"]
            for cycle in lane["cycles"]
        },
        "branch_restore_identity_rate": float(
            row["branch_restore_identity"]
        ),
        "policy_load_count": 1,
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
        "bridge_post_h2_shadow_env_step_count": row[
            "bridge_post_h1_shadow_env_step_count"
        ],
        "bridge_execution_shadow_env_step_count": row[
            "bridge_execution_shadow_env_step_count"
        ],
        "full_prefix_shadow_env_step_count": row[
            "full_prefix_shadow_env_step_count"
        ],
        "h2_gate_shadow_env_step_count": row[
            "one_step_gate_shadow_env_step_count"
        ],
        "policy_conditioned_shadow_advance_env_step_count": row[
            "policy_conditioned_shadow_advance_env_step_count"
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
            "H2 scaled-bridge pilot requires a clean worktree"
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
        raise H2ScaledBridgePilotError(
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
            "running_no_outcome_h2_scaled_bridge_receding"
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
                row_schema=ROW_SCHEMA,
                source_version="v12.16",
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
        raise H2ScaledBridgePilotError(
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
        raise H2ScaledBridgePilotError(
            "H2 scaled-bridge summary recomputation differs"
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
