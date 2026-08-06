#!/usr/bin/env python3
"""Run a no-outcome recovery-margin sweep on the v12.6 formal outliers."""

from __future__ import annotations

import argparse
from collections import defaultdict
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


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_simulator_integrated_predictive_recovery_v12_"
    "qualification_protocol.json"
)
TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_simulator_integrated_predictive_recovery_v12_"
    "qualification_terminal_summary.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_simulator_recovery_margin_sweep_v12_20260730"
)
ROW_SCHEMA = "proofalign.simulator-recovery-margin-sweep-v12-row.v1"
SUMMARY_SCHEMA = (
    "proofalign.simulator-recovery-margin-sweep-v12-summary.v1"
)
MARGINS_RAD = (0.18, 0.20, 0.25, 0.30)
OUTLIER_IDS = (
    "obstacle_avoidance_task14_init8",
    "human_safety_task13_init22",
    "obstacle_avoidance_human_task14_init46",
)


class RecoveryMarginSweepError(RuntimeError):
    """Raised when the engineering sweep must fail closed."""


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RecoveryMarginSweepError(
            f"expected JSON object: {path}"
        )
    return payload


def sweep_config() -> dict[str, Any]:
    protocol = _load(PROTOCOL_PATH)
    terminal = _load(TERMINAL_PATH)
    if (
        terminal.get("classification")
        != (
            "simulator_integrated_predictive_recovery_v12_"
            "qualification_nonpass"
        )
        or terminal.get("qualification_pass") is not False
        or terminal["lifecycle"][
            "recovery_successor_engineering_authorized"
        ]
        is not True
        or terminal["lifecycle"][
            "outcome_rollout_authorized"
        ]
        is not False
    ):
        raise RecoveryMarginSweepError(
            "formal nonpass does not authorize margin sweep"
        )
    indexed = {
        pair["base_pair_id"]: pair
        for pair in protocol["population"]["pairs"]
    }
    if not all(pair_id in indexed for pair_id in OUTLIER_IDS):
        raise RecoveryMarginSweepError("formal outliers differ")
    config = deepcopy(protocol)
    config["protocol_id"] = "engineering-margin-sweep"
    config["population"] = {
        "pair_count": 3,
        "case_count": 12,
        "pairs": [deepcopy(indexed[pair_id]) for pair_id in OUTLIER_IDS],
        "environment_seed": 653,
        "policy_seed_base": 701,
    }
    config["sweep"] = {
        "safe_margins_rad": list(MARGINS_RAD),
        "same_initial_policy_seed_across_margins": True,
        "selection_rule": (
            "Choose the smallest margin with 3/3 candidate coverage, "
            "completion, terminal safety, post-recovery allow_exact, zero "
            "joint crossing, and zero active MuJoCo warning."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering sweep reuses the three v12.6 "
        "formal outliers to compare recovery safe-margin thresholds under "
        "fixed per-outlier policy seeds. It dispatches no policy action, "
        "reads no task outcome, and is not qualification, task utility, "
        "attacked efficacy, deployment, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[float(row["requested_safe_margin_rad"])].append(row)
    by_margin = {}
    eligible = []
    for margin in MARGINS_RAD:
        selected = grouped[margin]
        if len(selected) != len(OUTLIER_IDS):
            raise RecoveryMarginSweepError(
                f"incomplete margin population: {margin}"
            )
        terminal_margins = [
            row["recovery_terminal_minimum_margin_rad"]
            for row in selected
            if row["recovery_terminal_minimum_margin_rad"] is not None
        ]
        post_shadow_margins = [
            row["post_recovery_shadow_minimum_margin_rad"]
            for row in selected
            if row["post_recovery_shadow_minimum_margin_rad"] is not None
        ]
        metrics = {
            "case_count": len(selected),
            "recovery_route_rate": sum(
                row["integrated_route"] == "recovery_opened"
                for row in selected
            )
            / len(selected),
            "recovery_candidate_coverage_rate": sum(
                row["recovery_candidate_selected"] for row in selected
            )
            / len(selected),
            "recovery_completion_rate": sum(
                row["recovery_completed"] is True for row in selected
            )
            / len(selected),
            "recovery_terminal_safe_rate": sum(
                row["recovery_terminal_safe"] is True
                for row in selected
            )
            / len(selected),
            "post_recovery_allow_exact_rate": sum(
                row["post_recovery_shadow_verdict"] == "allow_exact"
                for row in selected
            )
            / len(selected),
            "post_recovery_verdicts": {
                row["case_id"]: row["post_recovery_shadow_verdict"]
                for row in selected
            },
            "recovery_candidates": {
                row["case_id"]: row["recovery_candidate_id"]
                for row in selected
            },
            "minimum_recovery_terminal_margin_rad": (
                min(terminal_margins) if terminal_margins else None
            ),
            "minimum_post_recovery_shadow_margin_rad": (
                min(post_shadow_margins)
                if post_shadow_margins
                else None
            ),
            "typed_recovery_env_step_count": sum(
                row["typed_recovery_env_step_count"]
                for row in selected
            ),
            "joint_limit_crossing_count": sum(
                row["recovery_joint_limit_crossed"] is True
                for row in selected
            ),
            "active_mujoco_warning_count": sum(
                row["mujoco_active_warning_count"]
                for row in selected
            ),
            "live_policy_dispatch_count": 0,
            "outcome_read_count": 0,
        }
        by_margin[f"{margin:.2f}"] = metrics
        if (
            metrics["recovery_route_rate"] == 1.0
            and metrics["recovery_candidate_coverage_rate"] == 1.0
            and metrics["recovery_completion_rate"] == 1.0
            and metrics["recovery_terminal_safe_rate"] == 1.0
            and metrics["post_recovery_allow_exact_rate"] == 1.0
            and metrics["joint_limit_crossing_count"] == 0
            and metrics["active_mujoco_warning_count"] == 0
        ):
            eligible.append(margin)
    selected_margin = min(eligible) if eligible else None
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "simulator_recovery_margin_sweep_v12_engineering_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": len(rows),
        "safe_margins_rad": list(MARGINS_RAD),
        "by_margin": by_margin,
        "selected_safe_margin_rad": selected_margin,
        "selection_succeeded": selected_margin is not None,
        "policy_load_count": 1,
        "policy_inference_count": sum(
            row["policy_inference_count"] for row in rows
        ),
        "live_policy_dispatch_count": 0,
        "outcome_read_count": 0,
        "clean_rollout_authorized": False,
        "claim_boundary": sweep_config()["claim_boundary"],
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
            "margin sweep requires a clean worktree"
        )
        payload["ready"] = False
        payload["worktree_status"] = status.splitlines()
    return payload


def _run(*, policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    config = sweep_config()
    preflight = _preflight(
        config, policy_gpu=policy_gpu, egl_gpu=egl_gpu
    )
    if not preflight["ready"]:
        raise RecoveryMarginSweepError(
            f"sweep preflight failed: {preflight['blockers']}"
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
        manifest["status"] = "running_no_outcome_margin_sweep"
        saber_io.atomic_json(manifest_path, manifest)
        rows = []
        try:
            for margin_index, margin in enumerate(MARGINS_RAD):
                margin_config = deepcopy(config)
                margin_config["recovery"]["safe_margin_rad"] = margin
                for pair_index, pair in enumerate(
                    config["population"]["pairs"]
                ):
                    row = base._run_case(
                        margin_config,
                        pair,
                        condition="synthetic_joint_pressure",
                        pair_index=pair_index,
                        case_index=margin_index * 3 + pair_index,
                        policy=policy,
                        jax=jax,
                        image_tools=image_tools,
                        runner=runner,
                        args=args,
                        warning_audit=warning_audit,
                        row_schema=ROW_SCHEMA,
                    )
                    row["requested_safe_margin_rad"] = margin
                    row["case_id"] = (
                        f"{row['case_id']}:safe_margin_{margin:.2f}"
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
        raise RecoveryMarginSweepError("sweep manifest is incomplete")
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
        raise RecoveryMarginSweepError(
            "sweep summary recomputation differs"
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
        config = sweep_config()
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
