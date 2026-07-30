#!/usr/bin/env python3
"""Screen every recovery-safe primitive prefix on the remaining outliers."""

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
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    PROTOCOL_PATH,
    _canonical,
    _load,
    _run_case,
)
from scripts.run_simulator_recovery_bounded_replan_pilot_v12 import (  # noqa: E402
    FORMAL_PAIR_INDEX,
)


PREDECESSOR_SUMMARY_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_aware_recovery_candidate_pilot_v12_"
    "20260730"
    / "summary.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_aware_recovery_all_prefix_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.policy-aware-recovery-all-prefix-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.policy-aware-recovery-all-prefix-pilot-v12-summary.v1"
)
TARGET_IDS = (
    "human_safety_task13_init22",
    "obstacle_avoidance_human_task14_init46",
)
SCREENING_SEED_OFFSETS = (0, 1)


class AllPrefixPilotError(RuntimeError):
    """Raised when the all-prefix engineering pilot must fail closed."""


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_SUMMARY_PATH)
    if (
        predecessor.get("classification")
        != (
            "policy_aware_recovery_candidate_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("policy_safe_candidate_coverage_rate")
        != 1 / 3
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
    ):
        raise AllPrefixPilotError(
            "shortest-prefix pilot does not authorize all-prefix pilot"
        )
    protocol = _load(PROTOCOL_PATH)
    indexed = {
        pair["base_pair_id"]: pair
        for pair in protocol["population"]["pairs"]
    }
    config = deepcopy(protocol)
    config["protocol_id"] = "engineering-policy-aware-all-prefix-pilot"
    config["population"] = {
        "pair_count": 2,
        "case_count": 2,
        "pairs": [deepcopy(indexed[pair_id]) for pair_id in TARGET_IDS],
        "environment_seed": protocol["population"]["environment_seed"],
        "policy_seed_base": protocol["population"]["policy_seed_base"],
        "formal_pair_indexes": FORMAL_PAIR_INDEX,
    }
    config["screening"] = {
        "candidate_prefix_mode": "all_recovery_safe_prefixes",
        "post_recovery_policy_seed_offsets": list(
            SCREENING_SEED_OFFSETS
        ),
        "candidate_rule": (
            "Evaluate every recovery-safe H=1..10 prefix of every frozen "
            "primitive. Require allow_exact under both frozen post-recovery "
            "policy seeds; rank by shortest prefix, largest worst post-"
            "prefix margin, then candidate ID."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering pilot expands two unresolved "
        "v12.6 outliers from shortest-safe prefixes to every recovery-safe "
        "prefix in the frozen H=10 primitive trajectories. All candidate "
        "execution and post-policy screens remain restored shadow branches; "
        "no policy action or typed recovery is dispatched and no task "
        "outcome is read. It is not qualification, efficacy, deployment, "
        "or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 2:
        raise AllPrefixPilotError("expected two all-prefix rows")
    selected = {
        row["base_pair_id"]: (
            row["selected_policy_aware_candidate"]["candidate_id"]
            if row["selected_policy_aware_candidate"] is not None
            else None
        )
        for row in rows
    }
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "policy_aware_recovery_all_prefix_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": len(rows),
        "eligible_candidate_prefix_counts": {
            row["base_pair_id"]: row[
                "eligible_candidate_prefix_count"
            ]
            for row in rows
        },
        "policy_safe_candidate_prefix_counts": {
            row["base_pair_id"]: row["policy_safe_candidate_count"]
            for row in rows
        },
        "selected_policy_aware_candidates": selected,
        "policy_safe_candidate_coverage_rate": sum(
            value is not None for value in selected.values()
        )
        / len(rows),
        "branch_restore_identity_rate": sum(
            row["branch_restore_identity"] for row in rows
        )
        / len(rows),
        "joint_limit_crossing_candidate_count": sum(
            evaluation["joint_limit_crossed"]
            for row in rows
            for evaluation in row["candidate_evaluations"]
        ),
        "policy_load_count": 1,
        "policy_inference_count": sum(
            row["policy_inference_count"] for row in rows
        ),
        "policy_shadow_env_step_count": sum(
            row["policy_shadow_env_step_count"] for row in rows
        ),
        "recovery_candidate_shadow_env_step_count": sum(
            row["recovery_candidate_shadow_env_step_count"]
            for row in rows
        ),
        "candidate_branch_env_step_count": sum(
            row["candidate_branch_env_step_count"] for row in rows
        ),
        "active_warning_count": sum(
            row["active_warning_count"] for row in rows
        ),
        "active_contact_capacity_warning_count": sum(
            row["active_contact_capacity_warning_count"]
            for row in rows
        ),
        "contact_capacity_saturation_count": sum(
            row["contact_capacity_saturation_count"] for row in rows
        ),
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
            "all-prefix pilot requires a clean worktree"
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
        raise AllPrefixPilotError(
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
            "running_no_outcome_policy_aware_all_prefix_pilot"
        )
        saber_io.atomic_json(manifest_path, manifest)
        rows = []
        try:
            for pair in config["population"]["pairs"]:
                row = _run_case(
                    config,
                    pair,
                    formal_index=FORMAL_PAIR_INDEX[
                        pair["base_pair_id"]
                    ],
                    policy=policy,
                    jax=jax,
                    image_tools=image_tools,
                    runner=runner,
                    args=args,
                    warning_audit=warning_audit,
                    all_safe_prefixes=True,
                    screening_seed_offsets=SCREENING_SEED_OFFSETS,
                    row_schema=ROW_SCHEMA,
                )
                rows.append(row)
                saber_io.append_ledger(ledger_path, row)
        finally:
            mujoco.set_mju_user_warning(previous_warning_callback)
        summary = _summarize(rows)
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
        raise AllPrefixPilotError("pilot manifest is incomplete")
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
        raise AllPrefixPilotError(
            "pilot summary recomputation differs"
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
