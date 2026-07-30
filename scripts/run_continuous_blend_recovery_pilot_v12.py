#!/usr/bin/env python3
"""Search a local continuous recovery-action neighborhood on the outlier."""

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
    _canonical,
    _load,
)
from scripts.run_two_stage_policy_aware_recovery_pilot_v12 import (  # noqa: E402
    TARGET_ID,
    _candidate_library,
    _run_case,
    pilot_config as two_stage_config,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_two_stage_policy_aware_recovery_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_continuous_blend_recovery_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.continuous-blend-recovery-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.continuous-blend-recovery-pilot-v12-summary.v1"
)
PARENT_PREFIX_ID = "positive_y@h5"
Z_AMPLITUDES = (0.25, 0.5, 0.75, 1.0)
PERTURBATION_AXES = (
    ("x", 0),
    ("y", 1),
    ("rx", 3),
    ("ry", 4),
    ("rz", 5),
)
PERTURBATION_AMPLITUDES = (
    -1.0,
    -0.75,
    -0.5,
    -0.25,
    0.25,
    0.5,
    0.75,
    1.0,
)


class ContinuousBlendPilotError(RuntimeError):
    """Raised when the local continuous pilot must fail closed."""


def _float_token(value: float) -> str:
    return f"{value:+.2f}".replace("+", "p").replace("-", "m").replace(
        ".", "p"
    )


def local_blend_specs(
    config: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Return the frozen 164-candidate positive-z neighborhood."""

    library = _candidate_library(config)
    first_action = library["positive_y"]
    second_actions = []
    for z_amplitude in Z_AMPLITUDES:
        base_action = [0.0] * 6 + [-1.0]
        base_action[2] = z_amplitude
        second_actions.append(
            (
                f"z{_float_token(z_amplitude)}_none",
                tuple(base_action),
                "none",
                0.0,
                z_amplitude,
            )
        )
        for axis_name, axis_index in PERTURBATION_AXES:
            for perturbation in PERTURBATION_AMPLITUDES:
                action = list(base_action)
                action[axis_index] = perturbation
                second_actions.append(
                    (
                        (
                            f"z{_float_token(z_amplitude)}_"
                            f"{axis_name}{_float_token(perturbation)}"
                        ),
                        tuple(action),
                        axis_name,
                        perturbation,
                        z_amplitude,
                    )
                )
    specs = []
    for (
        action_id,
        second_action,
        axis_name,
        perturbation,
        z_amplitude,
    ) in second_actions:
        actions = (first_action,) * 5 + (second_action,)
        specs.append(
            {
                "candidate_id": (
                    f"{PARENT_PREFIX_ID}+blend_{action_id}@h1"
                ),
                "first_stage_candidate_id": PARENT_PREFIX_ID,
                "first_stage_action_id": "positive_y",
                "first_stage_horizon": 5,
                "second_stage_action_id": f"blend_{action_id}",
                "second_stage_horizon": 1,
                "second_stage_action": second_action,
                "z_amplitude": z_amplitude,
                "perturbation_axis": axis_name,
                "perturbation_amplitude": perturbation,
                "action_count": 6,
                "actions": actions,
            }
        )
    return tuple(specs)


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "two_stage_policy_aware_recovery_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("selection_succeeded") is not False
        or predecessor.get("raw_candidate_count") != 156
        or predecessor.get("recovery_eligible_candidate_count") != 65
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise ContinuousBlendPilotError(
            "two-stage nonpass does not authorize local blend search"
        )
    config = deepcopy(two_stage_config())
    config["protocol_id"] = (
        "engineering-continuous-blend-recovery-pilot"
    )
    specs = local_blend_specs(config)
    config["generator"] = {
        "mode": "result_informed_local_continuous_blend",
        "parent_prefix_id": PARENT_PREFIX_ID,
        "base_direction": "positive_z",
        "z_amplitudes": list(Z_AMPLITUDES),
        "perturbation_axes": [
            name for name, _index in PERTURBATION_AXES
        ],
        "perturbation_amplitudes": list(
            PERTURBATION_AMPLITUDES
        ),
        "second_stage_horizon": 1,
        "raw_candidate_count": len(specs),
        "candidate_rank_rule": (
            "Largest terminal recovery margin, largest minimum recovery "
            "margin, then candidate ID; all candidates have six actions."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering pilot searches a frozen local "
        "continuous-action neighborhood around the best bounded two-stage "
        "trajectory on the sole remaining known v12.6 outlier. Candidate "
        "execution and policy screens occur only in restored shadow "
        "branches. Recovery thresholds and policy gates are unchanged; no "
        "typed live recovery or policy action is dispatched and no task "
        "outcome is read. It is not qualification, efficacy, deployment, "
        "or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise ContinuousBlendPilotError(
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
            "continuous_blend_recovery_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
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
        "best_seed0_limiting_joint_index": (
            best_seed0["seed_results"][0][
                "minimum_margin_joint_index"
            ]
            if best_seed0 is not None
            else None
        ),
        "best_seed0_limiting_joint_side": (
            best_seed0["seed_results"][0][
                "minimum_margin_joint_side"
            ]
            if best_seed0 is not None
            else None
        ),
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
            "continuous-blend pilot requires a clean worktree"
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
        raise ContinuousBlendPilotError(
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
            "running_no_outcome_continuous_blend_pilot"
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
                candidate_specs=local_blend_specs(config),
                row_schema=ROW_SCHEMA,
                source_version="v12.9",
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
        raise ContinuousBlendPilotError("pilot manifest is incomplete")
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
        raise ContinuousBlendPilotError(
            "continuous-blend summary recomputation differs"
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
