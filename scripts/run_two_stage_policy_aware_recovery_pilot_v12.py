#!/usr/bin/env python3
"""Search bounded two-stage recovery trajectories on the remaining outlier."""

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
    select_escape_recovery_candidate,
    trusted_joint_state_from_libero,
)
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    PolicyPrefixShadowVerdict,
)
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    ShadowJointTrajectory,
)
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _minimum_margin,
    _reset_controller,
    _robot_arrays,
)
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    PROTOCOL_PATH,
    _canonical,
    _load,
    _recovery_config,
    _restore_identity,
)
from scripts.run_simulator_recovery_bounded_replan_pilot_v12 import (  # noqa: E402
    FORMAL_PAIR_INDEX,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_policy_aware_recovery_all_prefix_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_two_stage_policy_aware_recovery_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.two-stage-policy-aware-recovery-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.two-stage-policy-aware-recovery-pilot-v12-summary.v1"
)
TARGET_ID = "obstacle_avoidance_human_task14_init46"
PARENT_PREFIX_IDS = (
    "positive_y@h5",
    "hold@h5",
    "positive_x@h6",
    "negative_ry@h3",
)
SECOND_STAGE_HORIZONS = (1, 2, 3)
SCREENING_SEED_OFFSETS = (0, 1)


class TwoStagePilotError(RuntimeError):
    """Raised when the bounded two-stage pilot must fail closed."""


def _predecessor_row() -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in (
            PREDECESSOR_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    matches = [
        row for row in rows if row.get("base_pair_id") == TARGET_ID
    ]
    if len(matches) != 1:
        raise TwoStagePilotError(
            "all-prefix ledger does not contain exactly one target row"
        )
    return matches[0]


def _validate_parent_evidence(row: dict[str, Any]) -> None:
    evaluations = {
        item["candidate_id"]: item
        for item in row.get("candidate_evaluations", ())
    }
    if any(parent not in evaluations for parent in PARENT_PREFIX_IDS):
        raise TwoStagePilotError(
            "frozen first-stage parent is absent from predecessor ledger"
        )
    if any(
        evaluations[parent]["policy_safe_for_all_seeds"]
        for parent in PARENT_PREFIX_IDS
    ):
        raise TwoStagePilotError(
            "two-stage search is not authorized for an already-safe parent"
        )
    ranked = sorted(
        evaluations.values(),
        key=lambda item: (
            -float(item["worst_post_prefix_margin_rad"]),
            item["candidate_id"],
        ),
    )
    if tuple(item["candidate_id"] for item in ranked[:4]) != (
        PARENT_PREFIX_IDS
    ):
        raise TwoStagePilotError(
            "frozen parents no longer match top predecessor evidence"
        )


def _candidate_library(
    config: dict[str, Any],
) -> dict[str, tuple[float, ...]]:
    return {
        str(spec["candidate_id"]): tuple(
            float(value) for value in spec["action"]
        )
        for spec in config["recovery"]["candidate_library"]
    }


def _parse_parent_id(parent_id: str) -> tuple[str, int]:
    action_id, horizon_text = parent_id.rsplit("@h", 1)
    horizon = int(horizon_text)
    if not action_id or horizon <= 0:
        raise TwoStagePilotError(
            f"invalid frozen parent prefix: {parent_id}"
        )
    return action_id, horizon


def composite_specs(config: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return the frozen 4 x 13 x 3 deterministic candidate space."""

    library = _candidate_library(config)
    specs = []
    for parent_id in PARENT_PREFIX_IDS:
        first_action_id, first_horizon = _parse_parent_id(parent_id)
        first_action = library[first_action_id]
        for second_action_id, second_action in library.items():
            for second_horizon in SECOND_STAGE_HORIZONS:
                actions = (
                    (first_action,) * first_horizon
                    + (second_action,) * second_horizon
                )
                specs.append(
                    {
                        "candidate_id": (
                            f"{parent_id}+{second_action_id}"
                            f"@h{second_horizon}"
                        ),
                        "first_stage_candidate_id": parent_id,
                        "first_stage_action_id": first_action_id,
                        "first_stage_horizon": first_horizon,
                        "second_stage_action_id": second_action_id,
                        "second_stage_horizon": second_horizon,
                        "action_count": len(actions),
                        "actions": actions,
                    }
                )
    return tuple(specs)


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "policy_aware_recovery_all_prefix_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("selected_policy_aware_candidates", {}).get(
            TARGET_ID
        )
        is not None
        or predecessor.get(
            "policy_safe_candidate_prefix_counts", {}
        ).get(TARGET_ID)
        != 0
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise TwoStagePilotError(
            "all-prefix result does not authorize two-stage search"
        )
    _validate_parent_evidence(_predecessor_row())
    protocol = _load(PROTOCOL_PATH)
    indexed = {
        pair["base_pair_id"]: pair
        for pair in protocol["population"]["pairs"]
    }
    config = deepcopy(protocol)
    config["protocol_id"] = (
        "engineering-two-stage-policy-aware-recovery-pilot"
    )
    config["population"] = {
        "pair_count": 1,
        "case_count": 1,
        "pairs": [deepcopy(indexed[TARGET_ID])],
        "environment_seed": protocol["population"]["environment_seed"],
        "policy_seed_base": protocol["population"]["policy_seed_base"],
        "formal_pair_indexes": FORMAL_PAIR_INDEX,
    }
    config["generator"] = {
        "mode": "result_informed_bounded_two_stage",
        "first_stage_parent_prefix_ids": list(PARENT_PREFIX_IDS),
        "second_stage_action_ids": list(
            _candidate_library(config)
        ),
        "second_stage_horizons": list(SECOND_STAGE_HORIZONS),
        "raw_candidate_count": len(composite_specs(config)),
        "candidate_rank_rule": (
            "Shortest total action count, largest terminal recovery "
            "margin, largest minimum recovery margin, then candidate ID."
        ),
    }
    config["screening"] = {
        "post_recovery_policy_seed_offsets": list(
            SCREENING_SEED_OFFSETS
        ),
        "early_rejection": (
            "Reject after the first non-allow_exact, risk-disagreement, "
            "or restore-identity failure; otherwise require both seeds."
        ),
    }
    config["execution_boundary"][
        "typed_recovery_env_step_authorized"
    ] = False
    config["claim_boundary"] = (
        "This result-informed engineering pilot searches a frozen bounded "
        "two-stage recovery space on the sole remaining known v12.6 "
        "outlier. Candidate execution and policy screens occur only in "
        "restored shadow branches. The original recovery thresholds and "
        "policy gate are unchanged; no typed live recovery or policy "
        "action is dispatched and no task outcome is read. It is not "
        "qualification, efficacy, deployment, or physical-safety evidence."
    )
    return config


def _execute_actions(
    env: Any,
    *,
    actions: tuple[tuple[float, ...], ...],
    qidx: np.ndarray,
    limits: np.ndarray,
    contacts: base.ContactCapacityAudit,
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]:
    positions = []
    margins = []
    for action in actions:
        # The transition tuple, including any outcome field, is discarded.
        env.step(np.asarray(action, dtype=np.float64))
        contacts.observe(env)
        qpos = np.asarray(env.sim.data.qpos[qidx], dtype=np.float64)
        positions.append(tuple(float(value) for value in qpos))
        margins.append(_minimum_margin(qpos, limits))
    return tuple(positions), tuple(margins)


def _make_candidate(
    spec: dict[str, Any],
    *,
    trigger_state: Any,
    positions: tuple[tuple[float, ...], ...],
    margins: tuple[float, ...],
    source_id: str,
) -> RecoveryCandidate:
    command = tuple(
        value for action in spec["actions"] for value in action
    )
    return RecoveryCandidate(
        candidate_id=spec["candidate_id"],
        command=command,
        command_shape=(spec["action_count"], 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=trigger_state.state_digest,
            action_block_digest=command_digest(command),
            positions=positions,
            predictor_id=f"{source_id}:{spec['candidate_id']}",
        ),
        hard_violation_atoms=(
            ("joint_limit_crossed",) if min(margins) < 0 else ()
        ),
    )


def _run_case(
    config: dict[str, Any],
    pair: dict[str, Any],
    *,
    policy: Any,
    jax: Any,
    image_tools: Any,
    runner: Any,
    args: Any,
    warning_audit: base.MujocoWarningAudit,
) -> dict[str, Any]:
    formal_index = FORMAL_PAIR_INDEX[TARGET_ID]
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
            state_epoch=formal_index * 300,
            source_id=f"v12.8:{TARGET_ID}:trigger",
        )
        initial_screen = base._screen_prefix(
            config,
            env=env,
            robot=robot,
            qidx=qidx,
            state=trigger_state,
            prefix=prefix,
            source_id=f"v12.8:{TARGET_ID}:initial-screen",
            contact_audit=contacts,
        )
        if (
            initial_screen["decision"].verdict.value
            != PolicyPrefixShadowVerdict.RECOVERY_REQUIRED.value
        ):
            raise TwoStagePilotError(
                "target no longer reproduces recovery_required"
            )
        recovery_config = _recovery_config(config)
        branch_restore_identity = initial_screen["restore_identity"]
        physical_rows = []
        candidates: dict[str, RecoveryCandidate] = {}
        specs_by_id = {}
        generation_step_count = 0
        for spec in composite_specs(config):
            branch_restore_identity = (
                branch_restore_identity
                and _restore_identity(
                    env, robot, initial_screen["snapshot"]
                )
            )
            positions, margins = _execute_actions(
                env,
                actions=spec["actions"],
                qidx=qidx,
                limits=limits,
                contacts=contacts,
            )
            generation_step_count += spec["action_count"]
            candidate = _make_candidate(
                spec,
                trigger_state=trigger_state,
                positions=positions,
                margins=margins,
                source_id=f"v12.8:{TARGET_ID}:two-stage",
            )
            selection = select_escape_recovery_candidate(
                trigger_state,
                (candidate,),
                config=recovery_config,
            )
            evaluation = selection.evaluations[0]
            candidates[candidate.candidate_id] = candidate
            specs_by_id[candidate.candidate_id] = spec
            physical_rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "first_stage_candidate_id": spec[
                        "first_stage_candidate_id"
                    ],
                    "second_stage_action_id": spec[
                        "second_stage_action_id"
                    ],
                    "second_stage_horizon": spec[
                        "second_stage_horizon"
                    ],
                    "action_count": spec["action_count"],
                    "eligible": evaluation.eligible,
                    "rejection_reasons": list(evaluation.reasons),
                    "minimum_recovery_margin_rad": min(margins),
                    "terminal_recovery_margin_rad": margins[-1],
                    "joint_limit_crossed": min(margins) < 0,
                    "replay_max_abs_qpos_error_rad": None,
                    "replay_within_tolerance": None,
                    "policy_screened": False,
                    "seed_results": [],
                    "policy_safe_for_all_seeds": False,
                }
            )
        ranked = [row for row in physical_rows if row["eligible"]]
        ranked.sort(
            key=lambda row: (
                row["action_count"],
                -row["terminal_recovery_margin_rad"],
                -row["minimum_recovery_margin_rad"],
                row["candidate_id"],
            )
        )
        inference_count = 1
        post_shadow_steps = 0
        replay_step_count = 0
        selected = None
        for row in ranked:
            candidate = candidates[row["candidate_id"]]
            spec = specs_by_id[row["candidate_id"]]
            branch_restore_identity = (
                branch_restore_identity
                and _restore_identity(
                    env, robot, initial_screen["snapshot"]
                )
            )
            replay_positions, replay_margins = _execute_actions(
                env,
                actions=spec["actions"],
                qidx=qidx,
                limits=limits,
                contacts=contacts,
            )
            replay_step_count += spec["action_count"]
            replay_error = float(
                np.max(
                    np.abs(
                        np.asarray(replay_positions, dtype=np.float64)
                        - np.asarray(
                            candidate.trajectory.positions,
                            dtype=np.float64,
                        )
                    )
                )
            )
            replay_tolerance = float(
                config["recovery"][
                    "shadow_replay_abs_qpos_tolerance_rad"
                ]
            )
            row["minimum_replay_margin_rad"] = min(replay_margins)
            row["replay_max_abs_qpos_error_rad"] = replay_error
            row["replay_within_tolerance"] = (
                replay_error <= replay_tolerance
            )
            if not row["replay_within_tolerance"]:
                continue
            branch_state = trusted_joint_state_from_libero(
                env,
                state_epoch=trigger_state.state_epoch + 1,
                source_id=(
                    f"v12.8:{TARGET_ID}:"
                    f"{candidate.candidate_id}:branch"
                ),
            )
            row["policy_screened"] = True
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
                inference_count += 1
                post_screen = base._screen_prefix(
                    config,
                    env=env,
                    robot=robot,
                    qidx=qidx,
                    state=branch_state,
                    prefix=post_prefix,
                    source_id=(
                        f"v12.8:{TARGET_ID}:"
                        f"{candidate.candidate_id}:"
                        f"seed{screening_seed}"
                    ),
                    contact_audit=contacts,
                )
                post_shadow_steps += post_screen[
                    "shadow_env_step_count"
                ]
                seed_row = {
                    "policy_seed": screening_seed,
                    "verdict": post_screen[
                        "decision"
                    ].verdict.value,
                    "minimum_shadow_margin_rad": post_screen[
                        "assessment"
                    ].minimum_margin,
                    "risk_agreement": post_screen[
                        "risk_agreement"
                    ],
                    "restore_identity": post_screen[
                        "restore_identity"
                    ],
                }
                seed_rows.append(seed_row)
                if not (
                    seed_row["verdict"]
                    == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
                    and seed_row["risk_agreement"]
                    and seed_row["restore_identity"]
                ):
                    break
            row["seed_results"] = seed_rows
            row["policy_safe_for_all_seeds"] = (
                len(seed_rows) == len(SCREENING_SEED_OFFSETS)
                and all(
                    seed_row["verdict"]
                    == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
                    and seed_row["risk_agreement"]
                    and seed_row["restore_identity"]
                    for seed_row in seed_rows
                )
            )
            if row["policy_safe_for_all_seeds"]:
                selected = deepcopy(row)
                break
        branch_restore_identity = (
            branch_restore_identity
            and _restore_identity(
                env, robot, initial_screen["snapshot"]
            )
        )
        if not branch_restore_identity:
            raise TwoStagePilotError(
                "candidate branch restore identity failed"
            )
        return {
            "schema": ROW_SCHEMA,
            "case_id": TARGET_ID,
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
            "screening_policy_seeds": [
                policy_seed + 10_000 + offset
                for offset in SCREENING_SEED_OFFSETS
            ],
            "clean_frame_sha256": frame_audit[
                "clean_frame_sha256"
            ],
            "source_policy_chunk_sha256": chunk_digest,
            "initial_shadow_verdict": initial_screen[
                "decision"
            ].verdict.value,
            "initial_shadow_restore_identity": initial_screen[
                "restore_identity"
            ],
            "raw_candidate_count": len(physical_rows),
            "recovery_eligible_candidate_count": len(ranked),
            "policy_screened_candidate_count": sum(
                row["policy_screened"] for row in physical_rows
            ),
            "candidate_evaluations": physical_rows,
            "selected_policy_aware_candidate": selected,
            "branch_restore_identity": branch_restore_identity,
            "candidate_generation_shadow_env_step_count": (
                generation_step_count
            ),
            "candidate_replay_shadow_env_step_count": (
                replay_step_count
            ),
            "policy_inference_count": inference_count,
            "policy_shadow_env_step_count": (
                initial_screen["shadow_env_step_count"]
                + post_shadow_steps
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
    if len(rows) != 1 or rows[0].get("base_pair_id") != TARGET_ID:
        raise TwoStagePilotError("expected exactly the frozen target row")
    row = rows[0]
    selected = row["selected_policy_aware_candidate"]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "two_stage_policy_aware_recovery_v12_"
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
            "two-stage pilot requires a clean worktree"
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
        raise TwoStagePilotError(
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
            "running_no_outcome_two_stage_policy_aware_pilot"
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
        raise TwoStagePilotError("pilot manifest is incomplete")
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
        raise TwoStagePilotError(
            "two-stage pilot summary recomputation differs"
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
