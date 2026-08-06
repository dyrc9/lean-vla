#!/usr/bin/env python3
"""Replay the frozen nullspace pilot after an audit serialization fix."""

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


from scripts import run_h3_nullspace_exact_h1_pilot_v12 as source  # noqa: E402
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
)
from scripts.run_receding_horizon_recovery_pilot_v12 import (  # noqa: E402
    LANE_BASE_SEEDS,
    _run_case,
)


FAILED_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_nullspace_exact_h1_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_nullspace_exact_h1_replayfix_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-nullspace-exact-h1-replayfix-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-nullspace-exact-h1-replayfix-v12-summary.v1"
)


class H3NullspaceReplayFixError(RuntimeError):
    """Raised when the serialization-only replay must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(FAILED_ROOT)
    failed = _load(FAILED_ROOT / "run_manifest.json")
    ledger_path = FAILED_ROOT / "qualification_ledger.jsonl"
    if (
        failed.get("status") != "terminal_failed_closed"
        or failed.get("error")
        != "TypeError: Object of type ndarray is not JSON serializable"
        or failed.get("outcomes_observed") is not False
        or failed.get("preflight", {}).get("ready") is not True
        or not ledger_path.is_file()
        or ledger_path.stat().st_size != 0
    ):
        raise H3NullspaceReplayFixError(
            "serialization failure does not authorize mechanical replay"
        )
    config = deepcopy(source.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-nullspace-exact-h1-replayfix"
    )
    config["mechanical_replay"] = {
        "failed_root": str(FAILED_ROOT.relative_to(REPO_ROOT)),
        "only_change": (
            "controller target audit ndarray values serialize as JSON lists"
        ),
        "method_parameters_changed": False,
        "population_changed": False,
        "success_gate_changed": False,
    }
    config["claim_boundary"] = (
        source.pilot_config()["claim_boundary"]
        + " This fresh-root run is a mechanical replay after converting "
        "controller-target audit arrays to JSON lists; method parameters, "
        "population, and success gates are identical to the retained "
        "terminal serialization failure."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = source._summarize(rows)
    old_success = summary.pop("h3_nullspace_exact_h1_success")
    summary.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_nullspace_exact_h1_replayfix_v12_"
                "engineering_pilot_complete"
            ),
            "mechanical_replay_after_serialization_failure": True,
            "method_parameters_changed": False,
            "h3_nullspace_exact_h1_replayfix_success": old_success,
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
            "nullspace replayfix requires a clean worktree"
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
        raise H3NullspaceReplayFixError(
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
            "running_no_outcome_h3_nullspace_replayfix"
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
                controller_nullspace_exact_h1_offsets_rad=(
                    source.NULLSPACE_RETREAT_OFFSETS_RAD
                ),
                controller_nullspace_target_joint_index=(
                    source.TARGET_JOINT_INDEX
                ),
                controller_nullspace_target_joint_side=(
                    source.TARGET_JOINT_SIDE
                ),
                lane_base_seeds=LANE_BASE_SEEDS,
                row_schema=ROW_SCHEMA,
                source_version="v12.23-replayfix",
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
        raise H3NullspaceReplayFixError(
            "replayfix manifest is incomplete"
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
        raise H3NullspaceReplayFixError(
            "replayfix summary recomputation differs"
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
