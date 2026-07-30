#!/usr/bin/env python3
"""Screen recovery candidates by their post-recovery policy-prefix risk."""

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


from proofalign.escape_recovery_v12 import (  # noqa: E402
    EscapeRecoveryConfig,
    select_escape_recovery_candidate,
    trusted_joint_state_from_libero,
)
from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    PolicyPrefixShadowVerdict,
)
from proofalign.policy_prefix_shadow_warmstart_v12 import (  # noqa: E402
    restore_warmstart_policy_shadow_snapshot,
)
from proofalign.prefix_escape_recovery_v12 import (  # noqa: E402
    _prefix_candidate,
    select_prefix_escape_recovery_candidate,
)
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _minimum_margin,
    _reset_controller,
    _robot_arrays,
)
from scripts.run_simulator_recovery_bounded_replan_pilot_v12 import (  # noqa: E402
    FORMAL_PAIR_INDEX,
    OUTLIER_IDS,
    PROTOCOL_PATH,
)


BOUNDED_REPLAN_SUMMARY_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_simulator_recovery_bounded_replan_pilot_v12_"
    "20260730"
    / "summary.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_aware_recovery_candidate_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.policy-aware-recovery-candidate-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.policy-aware-recovery-candidate-pilot-v12-summary.v1"
)
SCREENING_SEED_OFFSETS = (0, 1)


class PolicyAwareCandidatePilotError(RuntimeError):
    """Raised when the policy-aware engineering pilot must fail closed."""


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise PolicyAwareCandidatePilotError(
            f"expected JSON object: {path}"
        )
    return payload


def pilot_config() -> dict[str, Any]:
    protocol = _load(PROTOCOL_PATH)
    bounded = _load(BOUNDED_REPLAN_SUMMARY_PATH)
    if (
        bounded.get("classification")
        != (
            "simulator_recovery_bounded_replan_v12_"
            "engineering_pilot_complete"
        )
        or bounded.get("selection_succeeded") is not False
        or bounded.get("bounded_replan_fresh_authorization_rate")
        != 0.0
        or bounded.get("outcome_read_count") != 0
        or bounded.get("live_policy_dispatch_count") != 0
    ):
        raise PolicyAwareCandidatePilotError(
            "bounded-replan result does not authorize candidate pilot"
        )
    indexed = {
        pair["base_pair_id"]: pair
        for pair in protocol["population"]["pairs"]
    }
    config = deepcopy(protocol)
    config["protocol_id"] = "engineering-policy-aware-candidate-pilot"
    config["population"] = {
        "pair_count": 3,
        "case_count": 3,
        "pairs": [deepcopy(indexed[pair_id]) for pair_id in OUTLIER_IDS],
        "environment_seed": protocol["population"]["environment_seed"],
        "policy_seed_base": protocol["population"]["policy_seed_base"],
        "formal_pair_indexes": FORMAL_PAIR_INDEX,
    }
    config["screening"] = {
        "post_recovery_policy_seed_offsets": list(
            SCREENING_SEED_OFFSETS
        ),
        "candidate_rule": (
            "For each primitive, retain its shortest recovery-safe prefix. "
            "A policy-aware candidate must produce allow_exact for both "
            "frozen post-recovery policy seeds. Rank by shortest action "
            "count, then largest worst post-prefix margin, then ID."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering pilot branches the simulator from "
        "three known v12.6 outliers, executes recovery candidates only in "
        "restored shadow branches, and screens fresh post-recovery policy "
        "prefixes for two frozen seeds. It performs no typed live recovery, "
        "dispatches no policy action, reads no task outcome, and is not "
        "qualification, task utility, attacked efficacy, deployment, or "
        "physical-safety evidence."
    )
    return config


def _recovery_config(config: dict[str, Any]) -> EscapeRecoveryConfig:
    recovery = config["recovery"]
    return EscapeRecoveryConfig(
        trigger_margin_rad=float(recovery["trigger_margin_rad"]),
        safe_margin_rad=float(recovery["safe_margin_rad"]),
        required_margin_gain_rad=float(
            recovery["required_margin_gain_rad"]
        ),
        max_transient_margin_loss_rad=float(
            recovery["max_transient_margin_loss_rad"]
        ),
    )


def _shortest_eligible_prefixes(
    state: Any,
    candidates: tuple[Any, ...],
    *,
    recovery_config: EscapeRecoveryConfig,
) -> tuple[Any, ...]:
    retained = []
    for candidate in candidates:
        for steps in range(1, candidate.command_shape[0] + 1):
            prefix = _prefix_candidate(state, candidate, steps)
            selected = select_escape_recovery_candidate(
                state, (prefix,), config=recovery_config
            )
            if selected.selected is not None:
                retained.append(prefix)
                break
    return tuple(retained)


def _restore_identity(env: Any, robot: Any, snapshot: Any) -> bool:
    restored = restore_warmstart_policy_shadow_snapshot(
        env, robot, snapshot
    )
    return (
        restored.trusted_arm_bitwise_identity
        and restored.controller_state_identity
        and restored.simulator_input_identity
        and restored.environment_clock_identity
        and restored.qacc_warmstart_identity
    )


def _run_case(
    config: dict[str, Any],
    pair: dict[str, Any],
    *,
    formal_index: int,
    policy: Any,
    jax: Any,
    image_tools: Any,
    runner: Any,
    args: Any,
    warning_audit: base.MujocoWarningAudit,
) -> dict[str, Any]:
    case_warning_start = len(warning_audit.messages)
    runtime = runner.load_libero_task_runtime(
        benchmark_name=pair["suite"],
        task_id=int(pair["task_id"]),
        init_state_id=int(pair["init_state_id"]),
        bddl_file=pair["bddl_path"],
    )
    prebinding_contacts = base.ContactCapacityAudit()
    env = runner.create_env(runtime, args)
    prebinding_contacts.observe(env)
    active_warning_start = None
    active_contact_warning_start = None
    try:
        env.reset()
        prebinding_contacts.observe(env)
        base._set_init_state_without_outcome(env, runtime.init_state)
        prebinding_contacts.observe(env)
        active_warning_start = len(warning_audit.messages)
        active_contact_warning_start = (
            warning_audit.contact_capacity_warning_count
        )
        contacts = base.ContactCapacityAudit()
        contacts.observe(env)
        base._stabilize(config, env, runner, contacts)
        robot, qidx, vidx, limits = _robot_arrays(env)
        _reset_controller(robot)
        joint = int(pair["synthetic_joint_index"])
        side = pair["synthetic_joint_side"]
        injected_margin = float(
            config["episode"]["synthetic_injected_margin_rad"]
        )
        env.sim.data.qpos[qidx[joint]] = (
            limits[joint, 0] + injected_margin
            if side == "lower"
            else limits[joint, 1] - injected_margin
        )
        env.sim.data.qvel[vidx] = 0.0
        env.sim.forward()
        contacts.observe(env)
        _reset_controller(robot)
        policy_seed = (
            int(config["population"]["policy_seed_base"])
            + formal_index
            + 100
        )
        prefix, frame_audit, chunk_digest = base._infer_prefix(
            config,
            env=env,
            runtime=runtime,
            policy=policy,
            jax=jax,
            image_tools=image_tools,
            runner=runner,
            args=args,
            policy_seed=policy_seed,
        )
        trigger_state = trusted_joint_state_from_libero(
            env,
            state_epoch=formal_index * 200,
            source_id=(
                f"v12.7:{pair['base_pair_id']}:trigger"
            ),
        )
        initial_screen = base._screen_prefix(
            config,
            env=env,
            robot=robot,
            qidx=qidx,
            state=trigger_state,
            prefix=prefix,
            source_id=(
                f"v12.7:{pair['base_pair_id']}:initial-screen"
            ),
            contact_audit=contacts,
        )
        candidates, recovery_shadow_steps, recovery_restore = (
            base._shadow_recovery_candidates(
                config,
                env=env,
                robot=robot,
                qidx=qidx,
                limits=limits,
                state=trigger_state,
                snapshot=initial_screen["snapshot"],
                source_id=(
                    f"v12.7:{pair['base_pair_id']}:recovery"
                ),
                contact_audit=contacts,
            )
        )
        recovery_config = _recovery_config(config)
        current_selection = select_prefix_escape_recovery_candidate(
            trigger_state, candidates, config=recovery_config
        )
        retained = _shortest_eligible_prefixes(
            trigger_state,
            candidates,
            recovery_config=recovery_config,
        )
        evaluations = []
        branch_restore_identity = recovery_restore
        branch_step_count = 0
        for candidate_index, candidate in enumerate(retained):
            branch_restore_identity = (
                branch_restore_identity
                and _restore_identity(
                    env, robot, initial_screen["snapshot"]
                )
            )
            actions = np.asarray(
                candidate.command, dtype=np.float64
            ).reshape(candidate.command_shape)
            replay_margins = []
            for action in actions:
                env.step(action)
                contacts.observe(env)
                branch_step_count += 1
                qpos = np.asarray(
                    env.sim.data.qpos[qidx], dtype=np.float64
                )
                replay_margins.append(
                    _minimum_margin(qpos, limits)
                )
            branch_state = trusted_joint_state_from_libero(
                env,
                state_epoch=trigger_state.state_epoch + 1,
                source_id=(
                    f"v12.7:{pair['base_pair_id']}:"
                    f"{candidate.candidate_id}:branch"
                ),
            )
            seed_rows = []
            for seed_offset in SCREENING_SEED_OFFSETS:
                screening_seed = (
                    policy_seed + 10_000 + seed_offset
                )
                post_prefix, _frame, _chunk = base._infer_prefix(
                    config,
                    env=env,
                    runtime=runtime,
                    policy=policy,
                    jax=jax,
                    image_tools=image_tools,
                    runner=runner,
                    args=args,
                    policy_seed=screening_seed,
                )
                post_screen = base._screen_prefix(
                    config,
                    env=env,
                    robot=robot,
                    qidx=qidx,
                    state=branch_state,
                    prefix=post_prefix,
                    source_id=(
                        f"v12.7:{pair['base_pair_id']}:"
                        f"{candidate.candidate_id}:seed{screening_seed}"
                    ),
                    contact_audit=contacts,
                )
                seed_rows.append(
                    {
                        "policy_seed": screening_seed,
                        "verdict": (
                            post_screen["decision"].verdict.value
                        ),
                        "minimum_shadow_margin_rad": (
                            post_screen["assessment"].minimum_margin
                        ),
                        "risk_agreement": post_screen[
                            "risk_agreement"
                        ],
                        "restore_identity": post_screen[
                            "restore_identity"
                        ],
                    }
                )
            evaluations.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "action_count": candidate.command_shape[0],
                    "terminal_margin_rad": (
                        branch_state.minimum_margin
                    ),
                    "minimum_replay_margin_rad": min(replay_margins),
                    "joint_limit_crossed": (
                        min(replay_margins) < 0
                    ),
                    "seed_results": seed_rows,
                    "policy_safe_for_all_seeds": all(
                        seed_row["verdict"]
                        == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
                        and seed_row["risk_agreement"]
                        and seed_row["restore_identity"]
                        for seed_row in seed_rows
                    ),
                    "worst_post_prefix_margin_rad": min(
                        seed_row["minimum_shadow_margin_rad"]
                        for seed_row in seed_rows
                    ),
                }
            )
        branch_restore_identity = (
            branch_restore_identity
            and _restore_identity(
                env, robot, initial_screen["snapshot"]
            )
        )
        eligible = [
            row
            for row in evaluations
            if row["policy_safe_for_all_seeds"]
            and not row["joint_limit_crossed"]
        ]
        eligible.sort(
            key=lambda row: (
                row["action_count"],
                -row["worst_post_prefix_margin_rad"],
                row["candidate_id"],
            )
        )
        selected = eligible[0] if eligible else None
        return {
            "schema": ROW_SCHEMA,
            "case_id": pair["base_pair_id"],
            **{
                key: pair[key]
                for key in (
                    "base_pair_id",
                    "suite",
                    "task_id",
                    "init_state_id",
                    "bddl_path",
                    "trusted_instruction",
                    "synthetic_joint_index",
                    "synthetic_joint_side",
                )
            },
            "valid": True,
            "policy_seed": policy_seed,
            "clean_frame_sha256": frame_audit[
                "clean_frame_sha256"
            ],
            "source_policy_chunk_sha256": chunk_digest,
            "initial_shadow_verdict": (
                initial_screen["decision"].verdict.value
            ),
            "initial_shadow_restore_identity": initial_screen[
                "restore_identity"
            ],
            "current_selector_candidate_id": (
                current_selection.selected.candidate_id
                if current_selection.selected is not None
                else None
            ),
            "source_candidate_count": len(candidates),
            "shortest_safe_candidate_count": len(retained),
            "candidate_evaluations": evaluations,
            "policy_safe_candidate_count": len(eligible),
            "selected_policy_aware_candidate": selected,
            "branch_restore_identity": branch_restore_identity,
            "recovery_candidate_shadow_env_step_count": (
                recovery_shadow_steps
            ),
            "candidate_branch_env_step_count": branch_step_count,
            "policy_inference_count": (
                1 + len(retained) * len(SCREENING_SEED_OFFSETS)
            ),
            "policy_shadow_env_step_count": (
                initial_screen["shadow_env_step_count"]
                + len(retained)
                * len(SCREENING_SEED_OFFSETS)
                * int(config["policy"]["source_prefix_steps"])
                * 2
            ),
            "maximum_observed_contact_count": contacts.maximum_ncon,
            "contact_capacity_saturation_count": (
                contacts.saturation_count
            ),
            "prebinding_warning_count": (
                active_warning_start - case_warning_start
            ),
            "active_warning_count": (
                len(warning_audit.messages) - active_warning_start
            ),
            "active_contact_capacity_warning_count": (
                warning_audit.contact_capacity_warning_count
                - active_contact_warning_start
            ),
            "live_policy_dispatch_count": 0,
            "typed_recovery_env_step_count": 0,
            "outcome_read_count": 0,
        }
    finally:
        env.close()


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 3:
        raise PolicyAwareCandidatePilotError(
            "expected three candidate-pilot rows"
        )
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
            "policy_aware_recovery_candidate_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": len(rows),
        "initial_recovery_required_rate": sum(
            row["initial_shadow_verdict"] == "recovery_required"
            for row in rows
        )
        / len(rows),
        "current_selector_candidate_ids": {
            row["base_pair_id"]: row["current_selector_candidate_id"]
            for row in rows
        },
        "shortest_safe_candidate_counts": {
            row["base_pair_id"]: row["shortest_safe_candidate_count"]
            for row in rows
        },
        "policy_safe_candidate_counts": {
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
            "policy-aware candidate pilot requires a clean worktree"
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
        raise PolicyAwareCandidatePilotError(
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
            "running_no_outcome_policy_aware_candidate_pilot"
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
        raise PolicyAwareCandidatePilotError(
            "candidate-pilot manifest is incomplete"
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
        raise PolicyAwareCandidatePilotError(
            "candidate-pilot summary recomputation differs"
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
