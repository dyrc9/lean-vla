#!/usr/bin/env python3
"""Use joint-targeted beam generation for predictive recovery escalation."""

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
from scripts.run_joint_targeted_beam_recovery_pilot_v12 import (  # noqa: E402
    _beam_candidate_builder,
)
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_predictive_recovery_escalation_pilot_v12 import (  # noqa: E402
    MAXIMUM_RECOVERY_ESCALATIONS_PER_CYCLE,
    RECOVERY_ROUND_SEED_STRIDE,
    REPLAN_ATTEMPTS_PER_ROUND,
    pilot_config as escalation_config,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    RECEDING_CYCLE_COUNT,
    TARGET_ID,
    _run_case,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_recovery_escalation_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_adaptive_beam_recovery_escalation_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.adaptive-beam-recovery-escalation-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.adaptive-beam-recovery-escalation-pilot-v12-summary.v1"
)


class AdaptiveBeamEscalationPilotError(RuntimeError):
    """Raised when adaptive beam escalation must fail closed."""


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "predictive_recovery_escalation_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get(
            "predictive_recovery_escalation_success"
        )
        is not False
        or predecessor.get("recovery_escalation_attempt_count") != 2
        or predecessor.get("recovery_escalation_selection_count") != 0
        or predecessor.get("recovery_escalation_execution_count") != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise AdaptiveBeamEscalationPilotError(
            "default escalation nonpass does not authorize beam fallback"
        )
    config = deepcopy(escalation_config())
    config["protocol_id"] = (
        "engineering-adaptive-beam-recovery-escalation-pilot"
    )
    config["receding_horizon"].update(
        {
            "escalation_candidate_generator": (
                "frozen primitives first, joint-targeted beam fallback"
            ),
            "fallback_gate": (
                "The first beam-ranked trajectory must independently pass "
                "the unchanged recovery selector and exact replay before "
                "shadow execution."
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed engineering pilot adds the previously tested "
        "joint-targeted beam generator as a fallback when the frozen "
        "primitive recovery selector cannot serve a predictive escalation "
        "on the sole remaining known v12.6 outlier. A beam trajectory is "
        "executed only after the unchanged recovery selector and exact "
        "replay gates, then followed by a fresh unchanged H1 gate. All "
        "recovery and policy advances remain restored simulator shadow; no "
        "typed live recovery or policy action is dispatched and no task "
        "outcome is read. It is not qualification, task utility, "
        "deployment, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise AdaptiveBeamEscalationPilotError(
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
    escalations = [
        escalation
        for cycle in cycles
        for escalation in cycle["recovery_escalations"]
    ]
    executed = [
        escalation
        for escalation in escalations
        if escalation["executed_in_shadow"]
    ]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "adaptive_beam_recovery_escalation_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "initial_recovery_candidate_id": row[
            "recovery_candidate_id"
        ],
        "lane_count": len(row["lane_results"]),
        "planned_cycle_count_per_lane": RECEDING_CYCLE_COUNT,
        "completed_cycle_counts": {
            str(lane["base_seed"]): lane["completed_cycle_count"]
            for lane in row["lane_results"]
        },
        "safe_lane_count": sum(
            lane["lane_safe"] for lane in row["lane_results"]
        ),
        "adaptive_beam_escalation_success": row[
            "receding_horizon_success"
        ],
        "total_fresh_h1_attempt_count": len(attempts),
        "one_step_allow_attempt_count": sum(
            attempt["one_step_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "full_prefix_allow_attempt_count": sum(
            attempt["full_prefix_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for attempt in attempts
        ),
        "recovery_escalation_attempt_count": len(escalations),
        "beam_fallback_attempt_count": sum(
            escalation["generator_mode"]
            == "joint_targeted_beam_fallback"
            for escalation in escalations
        ),
        "recovery_escalation_selection_count": sum(
            escalation["candidate_selected"]
            for escalation in escalations
        ),
        "recovery_escalation_execution_count": len(executed),
        "recovery_escalation_candidate_ids": [
            escalation["candidate_id"]
            for escalation in escalations
        ],
        "maximum_recovery_escalation_replay_error_rad": (
            max(
                escalation["replay_max_abs_qpos_error_rad"]
                for escalation in executed
            )
            if executed
            else None
        ),
        "attempt_counts_by_lane_cycle": {
            f"{lane['base_seed']}:{cycle['cycle_index']}": (
                cycle["attempt_count"]
            )
            for lane in row["lane_results"]
            for cycle in lane["cycles"]
        },
        "escalation_counts_by_lane_cycle": {
            f"{lane['base_seed']}:{cycle['cycle_index']}": len(
                cycle["recovery_escalations"]
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
        "escalation_candidate_shadow_env_step_count": row[
            "escalation_candidate_shadow_env_step_count"
        ],
        "escalation_execution_shadow_env_step_count": row[
            "escalation_execution_shadow_env_step_count"
        ],
        "full_prefix_shadow_env_step_count": row[
            "full_prefix_shadow_env_step_count"
        ],
        "one_step_gate_shadow_env_step_count": row[
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
            "adaptive-beam escalation requires a clean worktree"
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
        raise AdaptiveBeamEscalationPilotError(
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
            "running_no_outcome_adaptive_beam_escalation"
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
                replan_attempts_per_cycle=(
                    REPLAN_ATTEMPTS_PER_ROUND
                ),
                maximum_recovery_escalations_per_cycle=(
                    MAXIMUM_RECOVERY_ESCALATIONS_PER_CYCLE
                ),
                recovery_round_seed_stride=(
                    RECOVERY_ROUND_SEED_STRIDE
                ),
                escalation_candidate_builder=(
                    _beam_candidate_builder
                ),
                row_schema=ROW_SCHEMA,
                source_version="v12.14",
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
        raise AdaptiveBeamEscalationPilotError(
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
        raise AdaptiveBeamEscalationPilotError(
            "adaptive-beam summary recomputation differs"
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
