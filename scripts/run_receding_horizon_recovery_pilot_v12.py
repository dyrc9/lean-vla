#!/usr/bin/env python3
"""Evaluate one-step receding-horizon policy shadow after recovery."""

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
from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    PolicyPrefixShadowVerdict,
)
from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _minimum_margin,
    _reset_controller,
    _robot_arrays,
)
from scripts.run_joint_targeted_beam_recovery_pilot_v12 import (  # noqa: E402
    pilot_config as beam_config,
)
from scripts.run_policy_aware_recovery_candidate_pilot_v12 import (  # noqa: E402
    _canonical,
    _load,
    _recovery_config,
    _restore_identity,
)
from scripts.run_simulator_recovery_bounded_replan_pilot_v12 import (  # noqa: E402
    FORMAL_PAIR_INDEX,
)
from scripts.run_two_stage_policy_aware_recovery_pilot_v12 import (  # noqa: E402
    TARGET_ID,
    _candidate_library,
    _execute_actions,
    _make_candidate,
)


PREDECESSOR_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_joint_targeted_beam_recovery_pilot_v12_"
    "20260730"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_receding_horizon_recovery_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.receding-horizon-recovery-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.receding-horizon-recovery-pilot-v12-summary.v1"
)
LANE_BASE_SEEDS = (10_509, 10_510)
SEED_CYCLE_STRIDE = 100
RECEDING_CYCLE_COUNT = 5


class RecedingHorizonPilotError(RuntimeError):
    """Raised when the receding-horizon pilot must fail closed."""


def _predecessor_candidate() -> dict[str, Any]:
    summary = _load(PREDECESSOR_ROOT / "summary.json")
    candidate_id = summary.get("best_seed0_candidate")
    rows = [
        json.loads(line)
        for line in (
            PREDECESSOR_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    if len(rows) != 1:
        raise RecedingHorizonPilotError(
            "beam predecessor must contain exactly one row"
        )
    matches = [
        item
        for item in rows[0].get("candidate_evaluations", ())
        if item.get("candidate_id") == candidate_id
    ]
    if len(matches) != 1:
        raise RecedingHorizonPilotError(
            "beam best candidate is absent from predecessor ledger"
        )
    candidate = matches[0]
    if (
        not candidate.get("eligible")
        or candidate.get("policy_safe_for_all_seeds")
        or not candidate.get("action_ids")
    ):
        raise RecedingHorizonPilotError(
            "beam best candidate does not authorize receding pilot"
        )
    return candidate


def pilot_config() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        predecessor.get("classification")
        != (
            "joint_targeted_beam_recovery_v12_"
            "engineering_pilot_complete"
        )
        or predecessor.get("selection_succeeded") is not False
        or predecessor.get("recovery_eligible_candidate_count") != 96
        or predecessor.get("outcome_read_count") != 0
        or predecessor.get("live_policy_dispatch_count") != 0
        or predecessor.get("typed_recovery_env_step_count") != 0
    ):
        raise RecedingHorizonPilotError(
            "beam nonpass does not authorize receding-horizon pilot"
        )
    candidate = _predecessor_candidate()
    config = deepcopy(beam_config())
    config["protocol_id"] = (
        "engineering-receding-horizon-recovery-pilot"
    )
    config["receding_horizon"] = {
        "recovery_candidate_id": candidate["candidate_id"],
        "recovery_action_ids": candidate["action_ids"],
        "lane_base_seeds": list(LANE_BASE_SEEDS),
        "cycle_seed_stride": SEED_CYCLE_STRIDE,
        "cycle_count": RECEDING_CYCLE_COUNT,
        "screened_policy_prefix_steps": int(
            config["policy"]["source_prefix_steps"]
        ),
        "advanced_policy_action_steps_per_cycle": 1,
        "cycle_gate": (
            "The exact first action must be allow_exact with risk "
            "agreement and restore identity before one shadow advance."
        ),
    }
    config["claim_boundary"] = (
        "This result-informed engineering pilot evaluates one-step "
        "receding-horizon control after a frozen recovery candidate on the "
        "sole remaining known v12.6 outlier. Each cycle performs fresh "
        "policy inference, records the full-prefix risk, and advances only "
        "the exact first action after it passes the unchanged predictive "
        "gate. Advances occur only inside restored simulator-shadow lanes; "
        "no live policy action is dispatched and no task outcome is read. "
        "It is not qualification, task utility, deployment, or physical-"
        "safety evidence."
    )
    return config


def _search_safe_bridge(
    config: dict[str, Any],
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    branch_state: Any,
    snapshot: Any,
    contacts: base.ContactCapacityAudit,
    runtime: Any,
    policy: Any,
    jax: Any,
    image_tools: Any,
    runner: Any,
    args: Any,
    policy_seed: int,
    source_id: str,
    gate_horizon_steps: int = 1,
    bridge_floor_mode: str = "recovery_transient",
    candidate_builder: Any | None = None,
    blocked_prefix: np.ndarray | None = None,
    controller_goal_reset_before_sequence: bool = False,
) -> dict[str, Any]:
    library = _candidate_library(config)
    if bridge_floor_mode == "recovery_transient":
        bridge_floor = branch_state.minimum_margin - float(
            config["recovery"]["max_transient_margin_loss_rad"]
        )
    elif bridge_floor_mode == "absolute_safe_margin":
        bridge_floor = float(config["recovery"]["safe_margin_rad"])
    else:
        raise RecedingHorizonPilotError(
            f"unknown bridge floor mode: {bridge_floor_mode}"
        )
    trigger_margin = float(config["episode"]["trigger_margin_rad"])
    restore_identity = True
    controller_goal_reset_count = 0
    builder_shadow_steps = 0
    builder_diagnostics = None
    if candidate_builder is None:
        candidate_specs = tuple(
            {
                "candidate_id": action_id,
                "action_ids": (action_id,),
                "actions": (action,),
                "policy_rank": None,
            }
            for action_id, action in library.items()
        )
    else:
        built = candidate_builder(
            config,
            env=env,
            robot=robot,
            qidx=qidx,
            limits=limits,
            branch_state=branch_state,
            snapshot=snapshot,
            contacts=contacts,
            blocked_prefix=blocked_prefix,
        )
        candidate_specs = tuple(built["candidate_specs"])
        builder_shadow_steps = int(built["shadow_env_step_count"])
        builder_diagnostics = built["diagnostics"]
        restore_identity = (
            restore_identity and bool(built["restore_identity"])
        )
    physical_rows = []
    physical_steps = 0
    for candidate_index, spec in enumerate(candidate_specs):
        restore_identity = (
            restore_identity
            and _restore_identity(env, robot, snapshot)
        )
        if controller_goal_reset_before_sequence:
            _reset_controller(robot)
            controller_goal_reset_count += 1
        action_ids = tuple(str(value) for value in spec["action_ids"])
        actions = tuple(
            tuple(float(value) for value in action)
            for action in spec["actions"]
        )
        positions, margins = _execute_actions(
            env,
            actions=actions,
            qidx=qidx,
            limits=limits,
            contacts=contacts,
        )
        physical_steps += len(actions)
        margin = margins[-1]
        minimum_margin = min(margins)
        physical_rows.append(
            {
                "action_id": str(spec["candidate_id"]),
                "action_ids": list(action_ids),
                "action_count": len(actions),
                "action": actions[0] if len(actions) == 1 else None,
                "actions": actions,
                "candidate_order": candidate_index,
                "policy_rank": spec.get("policy_rank"),
                "terminal_margin_rad": margin,
                "minimum_margin_rad": minimum_margin,
                "transient_safe": (
                    minimum_margin >= bridge_floor
                    and minimum_margin >= trigger_margin
                ),
                "bridge_floor_mode": bridge_floor_mode,
                "bridge_floor_rad": bridge_floor,
                "bridge_safe": (
                    minimum_margin >= bridge_floor
                    and minimum_margin >= trigger_margin
                ),
                "policy_screened": False,
                "post_h1_verdict": None,
                "post_h1_minimum_margin_rad": None,
                "post_h1_risk_agreement": None,
                "post_h1_restore_identity": None,
                "selected": False,
                "terminal_qpos": list(positions[-1]),
            }
        )
    restore_identity = (
        restore_identity and _restore_identity(env, robot, snapshot)
    )
    eligible = [row for row in physical_rows if row["transient_safe"]]
    if any(row["policy_rank"] is not None for row in eligible):
        eligible.sort(
            key=lambda row: (
                (
                    int(row["policy_rank"])
                    if row["policy_rank"] is not None
                    else len(eligible)
                ),
                -row["terminal_margin_rad"],
                row["action_id"],
            )
        )
    else:
        eligible.sort(
            key=lambda row: (
                -row["terminal_margin_rad"],
                row["action_id"],
            )
        )
    inference_count = 0
    h1_shadow_steps = 0
    candidate_replay_steps = 0
    selected = None
    selected_prefix = None
    for row in eligible:
        restore_identity = (
            restore_identity
            and _restore_identity(env, robot, snapshot)
        )
        if controller_goal_reset_before_sequence:
            _reset_controller(robot)
            controller_goal_reset_count += 1
        actions = tuple(
            tuple(float(value) for value in action)
            for action in row["actions"]
        )
        _positions, replay_margins = _execute_actions(
            env,
            actions=actions,
            qidx=qidx,
            limits=limits,
            contacts=contacts,
        )
        candidate_replay_steps += len(actions)
        endpoint_state = trusted_joint_state_from_libero(
            env,
            state_epoch=branch_state.state_epoch + 1,
            source_id=f"{source_id}:{row['action_id']}:endpoint",
        )
        prefix, frame, chunk = base._infer_prefix(
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
        inference_count += 1
        post_h1 = base._screen_prefix(
            config,
            env=env,
            robot=robot,
            qidx=qidx,
            state=endpoint_state,
            prefix=prefix[:gate_horizon_steps],
            source_id=f"{source_id}:{row['action_id']}:post-h1",
            contact_audit=contacts,
        )
        h1_shadow_steps += post_h1["shadow_env_step_count"]
        row.update(
            {
                "policy_screened": True,
                "policy_seed": policy_seed,
                "clean_frame_sha256": frame["clean_frame_sha256"],
                "policy_chunk_sha256": chunk,
                "minimum_replay_margin_rad": min(replay_margins),
                "post_h1_verdict": post_h1[
                    "decision"
                ].verdict.value,
                "post_gate_horizon_steps": gate_horizon_steps,
                "post_gate_verdict": post_h1[
                    "decision"
                ].verdict.value,
                "post_h1_minimum_margin_rad": post_h1[
                    "assessment"
                ].minimum_margin,
                "post_gate_minimum_margin_rad": post_h1[
                    "assessment"
                ].minimum_margin,
                "post_h1_risk_agreement": post_h1[
                    "risk_agreement"
                ],
                "post_h1_restore_identity": post_h1[
                    "restore_identity"
                ],
            }
        )
        restore_identity = (
            restore_identity and post_h1["restore_identity"]
        )
        if (
            row["post_h1_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            and row["post_h1_risk_agreement"]
            and row["post_h1_restore_identity"]
        ):
            row["selected"] = True
            selected = row
            selected_prefix = prefix
            break
    restore_identity = (
        restore_identity and _restore_identity(env, robot, snapshot)
    )
    return {
        "selected": selected,
        "selected_prefix": selected_prefix,
        "candidate_evaluations": physical_rows,
        "candidate_builder_diagnostics": builder_diagnostics,
        "controller_goal_reset_count": controller_goal_reset_count,
        "restore_identity": restore_identity,
        "candidate_builder_shadow_env_step_count": (
            builder_shadow_steps
        ),
        "physical_shadow_env_step_count": physical_steps,
        "candidate_replay_shadow_env_step_count": (
            candidate_replay_steps
        ),
        "post_h1_shadow_env_step_count": h1_shadow_steps,
        "policy_inference_count": inference_count,
    }


def _screen_reset_backup_actions(
    config: dict[str, Any],
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    snapshot: Any,
    contacts: base.ContactCapacityAudit,
    source_id: str,
    require_safe_successor: bool = False,
) -> dict[str, Any]:
    floor = float(config["recovery"]["safe_margin_rad"])
    rows = []
    restore_identity = True
    reset_count = 0
    shadow_steps = 0
    for action_id, action in _candidate_library(config).items():
        restore_identity = (
            restore_identity
            and _restore_identity(env, robot, snapshot)
        )
        _reset_controller(robot)
        reset_count += 1
        _positions, margins = _execute_actions(
            env,
            actions=(action,),
            qidx=qidx,
            limits=limits,
            contacts=contacts,
        )
        shadow_steps += 1
        safe = min(margins) >= floor and min(margins) >= 0
        successor = None
        if safe and require_safe_successor:
            endpoint_snapshot = (
                base.capture_warmstart_policy_shadow_snapshot(
                    env,
                    robot,
                    source_id=f"{source_id}:{action_id}:endpoint",
                )
            )
            successor = _screen_reset_backup_actions(
                config,
                env=env,
                robot=robot,
                qidx=qidx,
                limits=limits,
                snapshot=endpoint_snapshot,
                contacts=contacts,
                source_id=f"{source_id}:{action_id}:successor",
                require_safe_successor=False,
            )
            shadow_steps += successor["shadow_env_step_count"]
            reset_count += successor["controller_goal_reset_count"]
            restore_identity = (
                restore_identity and successor["restore_identity"]
            )
        rows.append(
            {
                "action_id": action_id,
                "action": action,
                "minimum_margin_rad": min(margins),
                "terminal_margin_rad": margins[-1],
                "safe": safe,
                "safe_successor_required": require_safe_successor,
                "safe_successor_candidate_count": (
                    sum(
                        item["safe"]
                        for item in successor[
                            "candidate_evaluations"
                        ]
                    )
                    if successor is not None
                    else None
                ),
                "selected_successor_action_id": (
                    successor["selected"]["action_id"]
                    if successor is not None
                    and successor["selected"] is not None
                    else None
                ),
                "viable": (
                    safe
                    and (
                        not require_safe_successor
                        or successor is not None
                        and successor["selected"] is not None
                    )
                ),
            }
        )
    restore_identity = (
        restore_identity
        and _restore_identity(env, robot, snapshot)
    )
    viable = [row for row in rows if row["viable"]]
    viable.sort(
        key=lambda row: (
            -row["terminal_margin_rad"],
            -row["minimum_margin_rad"],
            row["action_id"],
        )
    )
    return {
        "candidate_evaluations": rows,
        "selected": viable[0] if viable else None,
        "restore_identity": restore_identity,
        "shadow_env_step_count": shadow_steps,
        "controller_goal_reset_count": reset_count,
    }


def _configure_nullspace_retreat(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    joint_index: int,
    joint_side: str,
    offset_rad: float,
) -> dict[str, Any]:
    if (
        joint_index < 0
        or joint_index >= len(qidx)
        or joint_side not in {"lower", "upper"}
        or offset_rad <= 0
    ):
        raise RecedingHorizonPilotError(
            "invalid nullspace retreat configuration"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    robot.controller.update(force=True)
    initial_joint = np.asarray(
        robot.controller.initial_joint, dtype=np.float64
    ).copy()
    target = initial_joint.copy()
    if joint_side == "upper":
        target[joint_index] = max(
            float(limits[joint_index, 0]),
            float(before_qpos[joint_index] - offset_rad),
        )
    else:
        target[joint_index] = min(
            float(limits[joint_index, 1]),
            float(before_qpos[joint_index] + offset_rad),
        )
    robot.controller.initial_joint = target
    robot.controller.reset_goal()
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    return {
        "prior_initial_joint": initial_joint,
        "retreat_initial_joint": target,
        "target_joint_index": joint_index,
        "target_joint_side": joint_side,
        "requested_offset_rad": offset_rad,
        "applied_target_delta_rad": (
            float(target[joint_index])
            - float(before_qpos[joint_index])
        ),
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


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
    replan_attempts_per_cycle: int = 1,
    seed_attempt_stride: int = 10,
    maximum_recovery_escalations_per_cycle: int = 0,
    recovery_round_seed_stride: int = 1_000,
    escalation_candidate_builder: Any | None = None,
    maximum_safe_bridges_per_cycle: int = 0,
    safe_bridge_seed_stride: int = 2_000,
    gate_horizon_steps: int = 1,
    bridge_floor_mode: str = "recovery_transient",
    consume_bridge_authorized_prefix: bool = False,
    bridge_candidate_builder: Any | None = None,
    controller_goal_reset_before_bridge: bool = False,
    controller_reset_exact_h1_fallback: bool = False,
    reset_exact_h1_require_backup_viability: bool = False,
    reset_backup_require_safe_successor: bool = False,
    maximum_reset_reserve_bridges_per_cycle: int = 0,
    controller_nullspace_exact_h1_offsets_rad: tuple[
        float, ...
    ] = (),
    controller_nullspace_target_joint_index: int = 1,
    controller_nullspace_target_joint_side: str = "upper",
    lane_base_seeds: tuple[int, ...] = LANE_BASE_SEEDS,
    row_schema: str = ROW_SCHEMA,
    source_version: str = "v12.11",
) -> dict[str, Any]:
    if (
        replan_attempts_per_cycle <= 0
        or seed_attempt_stride <= 0
        or maximum_recovery_escalations_per_cycle < 0
        or recovery_round_seed_stride <= 0
        or maximum_safe_bridges_per_cycle < 0
        or maximum_reset_reserve_bridges_per_cycle < 0
        or safe_bridge_seed_stride <= 0
        or gate_horizon_steps <= 0
        or gate_horizon_steps
        > int(config["policy"]["source_prefix_steps"])
        or not lane_base_seeds
        or len(set(lane_base_seeds)) != len(lane_base_seeds)
        or any(
            not np.isfinite(offset) or offset <= 0
            for offset in controller_nullspace_exact_h1_offsets_rad
        )
        or controller_nullspace_target_joint_side
        not in {"lower", "upper"}
    ):
        raise RecedingHorizonPilotError(
            "invalid replan or recovery-escalation bounds"
        )
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
        injected_margin = float(
            config["episode"]["synthetic_injected_margin_rad"]
        )
        env.sim.data.qpos[qidx[joint]] = (
            limits[joint, 0] + injected_margin
            if pair["synthetic_joint_side"] == "lower"
            else limits[joint, 1] - injected_margin
        )
        env.sim.data.qvel[vidx] = 0.0
        env.sim.forward()
        contacts.observe(env)
        _reset_controller(robot)
        trigger_policy_seed = (
            int(config["population"]["policy_seed_base"])
            + formal_index
            + 100
        )
        trigger_prefix, frame_audit, chunk_digest = base._infer_prefix(
            config,
            env=env,
            runtime=runtime,
            policy=policy,
            jax=jax,
            image_tools=image_tools,
            runner=runner,
            args=args,
            policy_seed=trigger_policy_seed,
        )
        trigger_state = trusted_joint_state_from_libero(
            env,
            state_epoch=formal_index * 500,
            source_id=f"{source_version}:{TARGET_ID}:trigger",
        )
        initial_screen = base._screen_prefix(
            config,
            env=env,
            robot=robot,
            qidx=qidx,
            state=trigger_state,
            prefix=trigger_prefix,
            source_id=(
                f"{source_version}:{TARGET_ID}:initial-screen"
            ),
            contact_audit=contacts,
        )
        if (
            initial_screen["decision"].verdict.value
            != PolicyPrefixShadowVerdict.RECOVERY_REQUIRED.value
        ):
            raise RecedingHorizonPilotError(
                "target no longer reproduces recovery_required"
            )
        predecessor_candidate = _predecessor_candidate()
        library = _candidate_library(config)
        action_ids = tuple(predecessor_candidate["action_ids"])
        recovery_actions = tuple(
            library[action_id] for action_id in action_ids
        )
        restore_identity = initial_screen["restore_identity"]
        lane_rows = []
        inference_count = 1
        full_prefix_shadow_steps = 0
        one_step_shadow_steps = 0
        recovery_shadow_steps = 0
        escalation_candidate_shadow_steps = 0
        escalation_execution_shadow_steps = 0
        bridge_candidate_shadow_steps = 0
        bridge_post_h1_shadow_steps = 0
        bridge_execution_shadow_steps = 0
        bridge_controller_goal_reset_count = 0
        reset_exact_h1_shadow_steps = 0
        reset_exact_h1_controller_goal_reset_count = 0
        reset_backup_candidate_shadow_steps = 0
        reset_reserve_execution_shadow_steps = 0
        reset_backup_controller_goal_reset_count = 0
        nullspace_exact_h1_shadow_steps = 0
        nullspace_controller_configuration_count = 0
        policy_advance_steps = 0
        for lane_index, base_seed in enumerate(lane_base_seeds):
            restore_identity = (
                restore_identity
                and _restore_identity(
                    env, robot, initial_screen["snapshot"]
                )
            )
            recovery_positions, recovery_margins = _execute_actions(
                env,
                actions=recovery_actions,
                qidx=qidx,
                limits=limits,
                contacts=contacts,
            )
            recovery_shadow_steps += len(recovery_actions)
            spec = {
                "candidate_id": predecessor_candidate["candidate_id"],
                "actions": recovery_actions,
                "action_count": len(recovery_actions),
            }
            recovery_candidate = _make_candidate(
                spec,
                trigger_state=trigger_state,
                positions=recovery_positions,
                margins=recovery_margins,
                source_id=(
                    f"{source_version}:{TARGET_ID}:"
                    f"lane{lane_index}:recovery"
                ),
            )
            recovery_selection = select_escape_recovery_candidate(
                trigger_state,
                (recovery_candidate,),
                config=_recovery_config(config),
            )
            if recovery_selection.selected is None:
                raise RecedingHorizonPilotError(
                    "frozen recovery candidate failed replay selector"
                )
            branch_state = trusted_joint_state_from_libero(
                env,
                state_epoch=trigger_state.state_epoch + 1,
                source_id=(
                    f"{source_version}:{TARGET_ID}:"
                    f"lane{lane_index}:recovered"
                ),
            )
            cycles = []
            lane_safe = True
            for cycle_index in range(RECEDING_CYCLE_COUNT):
                attempts = []
                recovery_escalations = []
                safe_bridges = []
                reset_exact_h1_fallbacks = []
                reset_reserve_bridges = []
                nullspace_exact_h1_fallbacks = []
                selected_prefix = None
                selected_advance_controller_goal_reset = False
                selected_advance_nullspace_offset = None
                selected_advance_minimum_margin_floor = float(
                    config["episode"]["trigger_margin_rad"]
                )
                control_round_count = (
                    maximum_recovery_escalations_per_cycle
                    + maximum_safe_bridges_per_cycle
                    + maximum_reset_reserve_bridges_per_cycle
                    + 1
                )
                for recovery_round in range(
                    control_round_count
                ):
                    one_step_screen = None
                    for attempt_index in range(
                        replan_attempts_per_cycle
                    ):
                        policy_seed = (
                            int(base_seed)
                            + cycle_index * SEED_CYCLE_STRIDE
                            + recovery_round
                            * recovery_round_seed_stride
                            + attempt_index * seed_attempt_stride
                        )
                        prefix, cycle_frame, cycle_chunk = (
                            base._infer_prefix(
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
                        )
                        inference_count += 1
                        full_screen = base._screen_prefix(
                            config,
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            state=branch_state,
                            prefix=prefix,
                            source_id=(
                                f"{source_version}:{TARGET_ID}:"
                                f"lane{lane_index}:"
                                f"cycle{cycle_index}:"
                                f"round{recovery_round}:"
                                f"attempt{attempt_index}:full"
                            ),
                            contact_audit=contacts,
                        )
                        full_prefix_shadow_steps += full_screen[
                            "shadow_env_step_count"
                        ]
                        one_step_screen = base._screen_prefix(
                            config,
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            state=branch_state,
                            prefix=prefix[:gate_horizon_steps],
                            source_id=(
                                f"{source_version}:{TARGET_ID}:"
                                f"lane{lane_index}:"
                                f"cycle{cycle_index}:"
                                f"round{recovery_round}:"
                                f"attempt{attempt_index}:h1"
                            ),
                            contact_audit=contacts,
                        )
                        one_step_shadow_steps += one_step_screen[
                            "shadow_env_step_count"
                        ]
                        first_action_safe = (
                            one_step_screen[
                                "decision"
                            ].verdict.value
                            == (
                                PolicyPrefixShadowVerdict.ALLOW_EXACT.value
                            )
                            and one_step_screen["risk_agreement"]
                            and one_step_screen["restore_identity"]
                        )
                        attempt_row = {
                            "recovery_round": recovery_round,
                            "attempt_index": attempt_index,
                            "policy_seed": policy_seed,
                            "clean_frame_sha256": cycle_frame[
                                "clean_frame_sha256"
                            ],
                            "policy_chunk_sha256": cycle_chunk,
                            "full_prefix_verdict": full_screen[
                                "decision"
                            ].verdict.value,
                            "full_prefix_minimum_margin_rad": (
                                full_screen[
                                    "assessment"
                                ].minimum_margin
                            ),
                            "full_prefix_first_risk_step": (
                                full_screen[
                                    "assessment"
                                ].first_risk_step
                            ),
                            "one_step_verdict": one_step_screen[
                                "decision"
                            ].verdict.value,
                            "gate_horizon_steps": gate_horizon_steps,
                            "gate_verdict": one_step_screen[
                                "decision"
                            ].verdict.value,
                            "one_step_minimum_margin_rad": (
                                one_step_screen[
                                    "assessment"
                                ].minimum_margin
                            ),
                            "gate_minimum_margin_rad": (
                                one_step_screen[
                                    "assessment"
                                ].minimum_margin
                            ),
                            "one_step_risk_agreement": one_step_screen[
                                "risk_agreement"
                            ],
                            "one_step_restore_identity": (
                                one_step_screen[
                                    "restore_identity"
                                ]
                            ),
                            "selected_for_shadow_advance": (
                                first_action_safe
                            ),
                        }
                        attempts.append(attempt_row)
                        restore_identity = (
                            restore_identity
                            and full_screen["restore_identity"]
                            and one_step_screen["restore_identity"]
                        )
                        if first_action_safe:
                            selected_prefix = prefix
                            break
                    if selected_prefix is not None:
                        break
                    if controller_nullspace_exact_h1_offsets_rad:
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for nullspace fallback"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        for offset_rad in (
                            controller_nullspace_exact_h1_offsets_rad
                        ):
                            restore_identity = (
                                restore_identity
                                and _restore_identity(
                                    env,
                                    robot,
                                    one_step_screen["snapshot"],
                                )
                            )
                            configuration = (
                                _configure_nullspace_retreat(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    limits=limits,
                                    joint_index=(
                                        controller_nullspace_target_joint_index
                                    ),
                                    joint_side=(
                                        controller_nullspace_target_joint_side
                                    ),
                                    offset_rad=float(offset_rad),
                                )
                            )
                            nullspace_controller_configuration_count += 1
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "nullspace configuration changed qpos/qvel"
                                )
                            (
                                _nullspace_positions,
                                nullspace_margins,
                            ) = _execute_actions(
                                env,
                                actions=(exact_action,),
                                qidx=qidx,
                                limits=limits,
                                contacts=contacts,
                            )
                            nullspace_exact_h1_shadow_steps += 1
                            candidate_rows.append(
                                {
                                    "offset_rad": float(offset_rad),
                                    "configuration": configuration,
                                    "predicted_minimum_margin_rad": min(
                                        nullspace_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        nullspace_margins[-1]
                                    ),
                                    "safe": (
                                        min(nullspace_margins)
                                        >= fallback_floor
                                        and min(nullspace_margins) >= 0
                                    ),
                                    "selected": False,
                                }
                            )
                        restore_identity = (
                            restore_identity
                            and _restore_identity(
                                env,
                                robot,
                                one_step_screen["snapshot"],
                            )
                        )
                        safe_candidates = [
                            candidate
                            for candidate in candidate_rows
                            if candidate["safe"]
                        ]
                        safe_candidates.sort(
                            key=lambda candidate: (
                                candidate["offset_rad"],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                            )
                        )
                        selected_nullspace = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_nullspace is not None:
                            selected_nullspace["selected"] = True
                        nullspace_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "minimum_margin_floor_rad": fallback_floor,
                            "candidate_evaluations": candidate_rows,
                            "selected_offset_rad": (
                                selected_nullspace["offset_rad"]
                                if selected_nullspace is not None
                                else None
                            ),
                            "authorized": (
                                selected_nullspace is not None
                            ),
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_terminal_margin_rad": None,
                            "prediction_execution_margin_error_rad": None,
                        }
                        nullspace_exact_h1_fallbacks.append(
                            nullspace_row
                        )
                        if selected_nullspace is not None:
                            selected_prefix = prefix
                            selected_advance_nullspace_offset = (
                                selected_nullspace["offset_rad"]
                            )
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                    if controller_reset_exact_h1_fallback:
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for exact-H1 fallback"
                            )
                        restore_identity = (
                            restore_identity
                            and _restore_identity(
                                env,
                                robot,
                                one_step_screen["snapshot"],
                            )
                        )
                        _reset_controller(robot)
                        reset_exact_h1_controller_goal_reset_count += 1
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        (
                            _fallback_positions,
                            fallback_margins,
                        ) = _execute_actions(
                            env,
                            actions=(exact_action,),
                            qidx=qidx,
                            limits=limits,
                            contacts=contacts,
                        )
                        reset_exact_h1_shadow_steps += 1
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        authorized = (
                            min(fallback_margins) >= fallback_floor
                            and min(fallback_margins) >= 0
                        )
                        backup_viability = None
                        if (
                            authorized
                            and reset_exact_h1_require_backup_viability
                        ):
                            endpoint_snapshot = (
                                base.capture_warmstart_policy_shadow_snapshot(
                                    env,
                                    robot,
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:"
                                        "exact-h1-endpoint"
                                    ),
                                )
                            )
                            backup_viability = (
                                _screen_reset_backup_actions(
                                    config,
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    limits=limits,
                                    snapshot=endpoint_snapshot,
                                    contacts=contacts,
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:"
                                        "exact-h1-backup"
                                    ),
                                    require_safe_successor=(
                                        reset_backup_require_safe_successor
                                    ),
                                )
                            )
                            reset_backup_candidate_shadow_steps += (
                                backup_viability[
                                    "shadow_env_step_count"
                                ]
                            )
                            reset_backup_controller_goal_reset_count += (
                                backup_viability[
                                    "controller_goal_reset_count"
                                ]
                            )
                            restore_identity = (
                                restore_identity
                                and backup_viability[
                                    "restore_identity"
                                ]
                            )
                            authorized = (
                                backup_viability["selected"] is not None
                            )
                        fallback_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "controller_goal_reset": True,
                            "minimum_margin_floor_rad": fallback_floor,
                            "predicted_minimum_margin_rad": min(
                                fallback_margins
                            ),
                            "predicted_terminal_margin_rad": (
                                fallback_margins[-1]
                            ),
                            "backup_viability_required": (
                                reset_exact_h1_require_backup_viability
                            ),
                            "backup_viability_candidate_evaluations": (
                                backup_viability[
                                    "candidate_evaluations"
                                ]
                                if backup_viability is not None
                                else []
                            ),
                            "backup_viability_safe_candidate_count": (
                                sum(
                                    item["safe"]
                                    for item in backup_viability[
                                        "candidate_evaluations"
                                    ]
                                )
                                if backup_viability is not None
                                else None
                            ),
                            "backup_viability_viable_candidate_count": (
                                sum(
                                    item["viable"]
                                    for item in backup_viability[
                                        "candidate_evaluations"
                                    ]
                                )
                                if backup_viability is not None
                                else None
                            ),
                            "backup_viability_selected_action_id": (
                                backup_viability["selected"][
                                    "action_id"
                                ]
                                if backup_viability is not None
                                and backup_viability["selected"]
                                is not None
                                else None
                            ),
                            "authorized": authorized,
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_terminal_margin_rad": None,
                            "prediction_execution_margin_error_rad": None,
                        }
                        reset_exact_h1_fallbacks.append(fallback_row)
                        restore_identity = (
                            restore_identity
                            and _restore_identity(
                                env,
                                robot,
                                one_step_screen["snapshot"],
                            )
                        )
                        if authorized:
                            selected_prefix = prefix
                            selected_advance_controller_goal_reset = True
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                        if (
                            len(reset_reserve_bridges)
                            < maximum_reset_reserve_bridges_per_cycle
                        ):
                            reserve_search = (
                                _screen_reset_backup_actions(
                                    config,
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    limits=limits,
                                    snapshot=one_step_screen[
                                        "snapshot"
                                    ],
                                    contacts=contacts,
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:"
                                        "reset-reserve"
                                    ),
                                    require_safe_successor=(
                                        reset_backup_require_safe_successor
                                    ),
                                )
                            )
                            reset_backup_candidate_shadow_steps += (
                                reserve_search[
                                    "shadow_env_step_count"
                                ]
                            )
                            reset_backup_controller_goal_reset_count += (
                                reserve_search[
                                    "controller_goal_reset_count"
                                ]
                            )
                            restore_identity = (
                                restore_identity
                                and reserve_search[
                                    "restore_identity"
                                ]
                            )
                            selected_reserve = reserve_search[
                                "selected"
                            ]
                            reserve_row = {
                                "reserve_index": len(
                                    reset_reserve_bridges
                                ),
                                "candidate_evaluations": reserve_search[
                                    "candidate_evaluations"
                                ],
                                "selected_action_id": (
                                    selected_reserve["action_id"]
                                    if selected_reserve is not None
                                    else None
                                ),
                                "selected_terminal_margin_rad": (
                                    selected_reserve[
                                        "terminal_margin_rad"
                                    ]
                                    if selected_reserve is not None
                                    else None
                                ),
                                "executed_in_shadow": False,
                                "execution_terminal_margin_rad": None,
                                "execution_minimum_margin_rad": None,
                            }
                            reset_reserve_bridges.append(reserve_row)
                            if selected_reserve is not None:
                                restore_identity = (
                                    restore_identity
                                    and _restore_identity(
                                        env,
                                        robot,
                                        one_step_screen["snapshot"],
                                    )
                                )
                                _reset_controller(robot)
                                reset_backup_controller_goal_reset_count += 1
                                reserve_action = tuple(
                                    float(value)
                                    for value in selected_reserve["action"]
                                )
                                (
                                    _reserve_positions,
                                    reserve_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(reserve_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                                reset_reserve_execution_shadow_steps += 1
                                if min(reserve_margins) < fallback_floor:
                                    raise RecedingHorizonPilotError(
                                        "reset reserve replay failed"
                                    )
                                reserve_row[
                                    "executed_in_shadow"
                                ] = True
                                reserve_row[
                                    "execution_terminal_margin_rad"
                                ] = reserve_margins[-1]
                                reserve_row[
                                    "execution_minimum_margin_rad"
                                ] = min(reserve_margins)
                                branch_state = (
                                    trusted_joint_state_from_libero(
                                        env,
                                        state_epoch=(
                                            branch_state.state_epoch + 1
                                        ),
                                        source_id=(
                                            f"{source_version}:{TARGET_ID}:"
                                            f"lane{lane_index}:"
                                            f"cycle{cycle_index}:"
                                            f"round{recovery_round}:"
                                            "reset-reserve-executed"
                                        ),
                                    )
                                )
                                continue
                    if len(safe_bridges) < maximum_safe_bridges_per_cycle:
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed H1 screen for safe bridge"
                            )
                        bridge_seed = (
                            int(base_seed)
                            + cycle_index * SEED_CYCLE_STRIDE
                            + (len(safe_bridges) + 1)
                            * safe_bridge_seed_stride
                        )
                        bridge = _search_safe_bridge(
                            config,
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            limits=limits,
                            branch_state=branch_state,
                            snapshot=one_step_screen["snapshot"],
                            contacts=contacts,
                            runtime=runtime,
                            policy=policy,
                            jax=jax,
                            image_tools=image_tools,
                            runner=runner,
                            args=args,
                            policy_seed=bridge_seed,
                            source_id=(
                                f"{source_version}:{TARGET_ID}:"
                                f"lane{lane_index}:cycle{cycle_index}:"
                                f"round{recovery_round}:safe-bridge"
                            ),
                            gate_horizon_steps=gate_horizon_steps,
                            bridge_floor_mode=bridge_floor_mode,
                            candidate_builder=bridge_candidate_builder,
                            blocked_prefix=prefix,
                            controller_goal_reset_before_sequence=(
                                controller_goal_reset_before_bridge
                            ),
                        )
                        inference_count += bridge[
                            "policy_inference_count"
                        ]
                        bridge_controller_goal_reset_count += bridge[
                            "controller_goal_reset_count"
                        ]
                        bridge_candidate_shadow_steps += (
                            bridge[
                                "candidate_builder_shadow_env_step_count"
                            ]
                            +
                            bridge[
                                "physical_shadow_env_step_count"
                            ]
                            + bridge[
                                "candidate_replay_shadow_env_step_count"
                            ]
                        )
                        bridge_post_h1_shadow_steps += bridge[
                            "post_h1_shadow_env_step_count"
                        ]
                        restore_identity = (
                            restore_identity
                            and bridge["restore_identity"]
                        )
                        selected_bridge = bridge["selected"]
                        bridge_row = {
                            "bridge_index": len(safe_bridges),
                            "policy_seed": bridge_seed,
                            "bridge_floor_mode": bridge_floor_mode,
                            "controller_goal_reset_before_sequence": (
                                controller_goal_reset_before_bridge
                            ),
                            "bridge_floor_rad": (
                                selected_bridge["bridge_floor_rad"]
                                if selected_bridge is not None
                                else None
                            ),
                            "candidate_builder_diagnostics": bridge[
                                "candidate_builder_diagnostics"
                            ],
                            "candidate_evaluations": bridge[
                                "candidate_evaluations"
                            ],
                            "selected_action_id": (
                                selected_bridge["action_id"]
                                if selected_bridge is not None
                                else None
                            ),
                            "selected_action_ids": (
                                selected_bridge["action_ids"]
                                if selected_bridge is not None
                                else None
                            ),
                            "selected_action_count": (
                                selected_bridge["action_count"]
                                if selected_bridge is not None
                                else None
                            ),
                            "selected_terminal_margin_rad": (
                                selected_bridge[
                                    "terminal_margin_rad"
                                ]
                                if selected_bridge is not None
                                else None
                            ),
                            "executed_in_shadow": False,
                            "authorized_prefix_consumed": False,
                            "post_execution_gate_verdict": None,
                            "post_execution_gate_minimum_margin_rad": None,
                            "post_execution_gate_risk_agreement": None,
                            "post_execution_gate_restore_identity": None,
                        }
                        safe_bridges.append(bridge_row)
                        if selected_bridge is not None:
                            restore_identity = (
                                restore_identity
                                and _restore_identity(
                                    env,
                                    robot,
                                    one_step_screen["snapshot"],
                                )
                            )
                            if controller_goal_reset_before_bridge:
                                _reset_controller(robot)
                                bridge_controller_goal_reset_count += 1
                            bridge_actions = tuple(
                                tuple(
                                    float(value) for value in action
                                )
                                for action in selected_bridge["actions"]
                            )
                            _bridge_positions, bridge_margins = (
                                _execute_actions(
                                    env,
                                    actions=bridge_actions,
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            )
                            bridge_execution_shadow_steps += len(
                                bridge_actions
                            )
                            if (
                                min(bridge_margins)
                                < float(
                                    selected_bridge[
                                        "bridge_floor_rad"
                                    ]
                                )
                                or min(bridge_margins)
                                < float(
                                    config["episode"][
                                        "trigger_margin_rad"
                                    ]
                                )
                                or min(bridge_margins) < 0
                            ):
                                raise RecedingHorizonPilotError(
                                    "selected safe bridge replay failed"
                                )
                            bridge_row["executed_in_shadow"] = True
                            bridge_row[
                                "execution_terminal_margin_rad"
                            ] = bridge_margins[-1]
                            bridge_row[
                                "execution_minimum_margin_rad"
                            ] = min(bridge_margins)
                            branch_state = (
                                trusted_joint_state_from_libero(
                                    env,
                                    state_epoch=(
                                        branch_state.state_epoch + 1
                                    ),
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:"
                                        "safe-bridge-executed"
                                    ),
                                )
                            )
                            if consume_bridge_authorized_prefix:
                                bridge_prefix = bridge[
                                    "selected_prefix"
                                ]
                                if bridge_prefix is None:
                                    raise RecedingHorizonPilotError(
                                        "selected bridge lacks policy prefix"
                                    )
                                confirmed_gate = base._screen_prefix(
                                    config,
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    state=branch_state,
                                    prefix=bridge_prefix[
                                        :gate_horizon_steps
                                    ],
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:"
                                        "bridge-confirmation"
                                    ),
                                    contact_audit=contacts,
                                )
                                bridge_post_h1_shadow_steps += (
                                    confirmed_gate[
                                        "shadow_env_step_count"
                                    ]
                                )
                                restore_identity = (
                                    restore_identity
                                    and confirmed_gate[
                                        "restore_identity"
                                    ]
                                )
                                bridge_row.update(
                                    {
                                        "post_execution_gate_verdict": (
                                            confirmed_gate[
                                                "decision"
                                            ].verdict.value
                                        ),
                                        "post_execution_gate_minimum_margin_rad": (
                                            confirmed_gate[
                                                "assessment"
                                            ].minimum_margin
                                        ),
                                        "post_execution_gate_risk_agreement": (
                                            confirmed_gate[
                                                "risk_agreement"
                                            ]
                                        ),
                                        "post_execution_gate_restore_identity": (
                                            confirmed_gate[
                                                "restore_identity"
                                            ]
                                        ),
                                    }
                                )
                                if (
                                    confirmed_gate[
                                        "decision"
                                    ].verdict.value
                                    == (
                                        PolicyPrefixShadowVerdict.ALLOW_EXACT.value
                                    )
                                    and confirmed_gate[
                                        "risk_agreement"
                                    ]
                                    and confirmed_gate[
                                        "restore_identity"
                                    ]
                                ):
                                    bridge_row[
                                        "authorized_prefix_consumed"
                                    ] = True
                                    selected_prefix = bridge_prefix
                                    break
                            continue
                    if (
                        recovery_round
                        >= maximum_recovery_escalations_per_cycle
                    ):
                        break
                    if one_step_screen is None:
                        raise RecedingHorizonPilotError(
                            "missing failed H1 screen for escalation"
                        )
                    (
                        escalation_selection,
                        _escalation_config,
                        escalation_shadow_steps,
                        escalation_restore,
                    ) = base._select_recovery(
                        config,
                        env=env,
                        robot=robot,
                        qidx=qidx,
                        limits=limits,
                        state=branch_state,
                        snapshot=one_step_screen["snapshot"],
                        source_id=(
                            f"{source_version}:{TARGET_ID}:"
                            f"lane{lane_index}:cycle{cycle_index}:"
                            f"round{recovery_round}:escalation"
                        ),
                        contact_audit=contacts,
                    )
                    escalation_candidate_shadow_steps += (
                        escalation_shadow_steps
                    )
                    restore_identity = (
                        restore_identity and escalation_restore
                    )
                    selected_recovery = escalation_selection.selected
                    generator_mode = "frozen_primitive_prefix"
                    generator_diagnostics = None
                    if (
                        selected_recovery is None
                        and escalation_candidate_builder is not None
                    ):
                        built = escalation_candidate_builder(
                            config,
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            limits=limits,
                            trigger_state=branch_state,
                            snapshot=one_step_screen["snapshot"],
                            contacts=contacts,
                        )
                        escalation_candidate_shadow_steps += int(
                            built["shadow_env_step_count"]
                        )
                        restore_identity = (
                            restore_identity
                            and bool(built["restore_identity"])
                        )
                        generator_mode = "joint_targeted_beam_fallback"
                        generator_diagnostics = built["diagnostics"]
                        fallback_specs = tuple(
                            built["candidate_specs"]
                        )
                        if fallback_specs:
                            fallback_spec = fallback_specs[0]
                            restore_identity = (
                                restore_identity
                                and _restore_identity(
                                    env,
                                    robot,
                                    one_step_screen["snapshot"],
                                )
                            )
                            (
                                fallback_positions,
                                fallback_margins,
                            ) = _execute_actions(
                                env,
                                actions=tuple(
                                    fallback_spec["actions"]
                                ),
                                qidx=qidx,
                                limits=limits,
                                contacts=contacts,
                            )
                            escalation_candidate_shadow_steps += int(
                                fallback_spec["action_count"]
                            )
                            fallback_candidate = _make_candidate(
                                fallback_spec,
                                trigger_state=branch_state,
                                positions=fallback_positions,
                                margins=fallback_margins,
                                source_id=(
                                    f"{source_version}:{TARGET_ID}:"
                                    f"lane{lane_index}:"
                                    f"cycle{cycle_index}:"
                                    f"round{recovery_round}:"
                                    "beam-fallback"
                                ),
                            )
                            fallback_selection = (
                                select_escape_recovery_candidate(
                                    branch_state,
                                    (fallback_candidate,),
                                    config=_recovery_config(config),
                                )
                            )
                            selected_recovery = (
                                fallback_selection.selected
                            )
                    escalation_row = {
                        "recovery_round": recovery_round,
                        "source_state_minimum_margin_rad": (
                            branch_state.minimum_margin
                        ),
                        "candidate_selected": (
                            selected_recovery is not None
                        ),
                        "candidate_id": (
                            selected_recovery.candidate_id
                            if selected_recovery is not None
                            else None
                        ),
                        "generator_mode": generator_mode,
                        "generator_diagnostics": (
                            generator_diagnostics
                        ),
                        "executed_in_shadow": False,
                        "replay_max_abs_qpos_error_rad": None,
                        "minimum_replay_margin_rad": None,
                        "terminal_replay_margin_rad": None,
                    }
                    recovery_escalations.append(escalation_row)
                    if selected_recovery is None:
                        break
                    restore_identity = (
                        restore_identity
                        and _restore_identity(
                            env,
                            robot,
                            one_step_screen["snapshot"],
                        )
                    )
                    escalation_actions = tuple(
                        tuple(float(value) for value in action)
                        for action in np.asarray(
                            selected_recovery.command,
                            dtype=np.float64,
                        ).reshape(selected_recovery.command_shape)
                    )
                    escalation_positions, escalation_margins = (
                        _execute_actions(
                            env,
                            actions=escalation_actions,
                            qidx=qidx,
                            limits=limits,
                            contacts=contacts,
                        )
                    )
                    escalation_execution_shadow_steps += len(
                        escalation_actions
                    )
                    replay_error = float(
                        np.max(
                            np.abs(
                                np.asarray(
                                    escalation_positions,
                                    dtype=np.float64,
                                )
                                - np.asarray(
                                    selected_recovery.trajectory.positions,
                                    dtype=np.float64,
                                )
                            )
                        )
                    )
                    if (
                        replay_error
                        > float(
                            config["recovery"][
                                "shadow_replay_abs_qpos_tolerance_rad"
                            ]
                        )
                        or min(escalation_margins) < 0
                    ):
                        raise RecedingHorizonPilotError(
                            "recovery escalation replay failed closed"
                        )
                    escalation_row.update(
                        {
                            "executed_in_shadow": True,
                            "replay_max_abs_qpos_error_rad": (
                                replay_error
                            ),
                            "minimum_replay_margin_rad": min(
                                escalation_margins
                            ),
                            "terminal_replay_margin_rad": (
                                escalation_margins[-1]
                            ),
                        }
                    )
                    branch_state = trusted_joint_state_from_libero(
                        env,
                        state_epoch=branch_state.state_epoch + 1,
                        source_id=(
                            f"{source_version}:{TARGET_ID}:"
                            f"lane{lane_index}:cycle{cycle_index}:"
                            f"round{recovery_round}:escalated"
                        ),
                    )
                terminal_attempt = attempts[-1]
                cycle_row = {
                    "cycle_index": cycle_index,
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                    "recovery_escalations": recovery_escalations,
                    "safe_bridges": safe_bridges,
                    "reset_exact_h1_fallbacks": (
                        reset_exact_h1_fallbacks
                    ),
                    "reset_reserve_bridges": reset_reserve_bridges,
                    "nullspace_exact_h1_fallbacks": (
                        nullspace_exact_h1_fallbacks
                    ),
                    "policy_seed": terminal_attempt["policy_seed"],
                    "clean_frame_sha256": terminal_attempt[
                        "clean_frame_sha256"
                    ],
                    "policy_chunk_sha256": terminal_attempt[
                        "policy_chunk_sha256"
                    ],
                    "full_prefix_verdict": terminal_attempt[
                        "full_prefix_verdict"
                    ],
                    "full_prefix_minimum_margin_rad": terminal_attempt[
                        "full_prefix_minimum_margin_rad"
                    ],
                    "full_prefix_first_risk_step": terminal_attempt[
                        "full_prefix_first_risk_step"
                    ],
                    "one_step_verdict": terminal_attempt[
                        "one_step_verdict"
                    ],
                    "one_step_minimum_margin_rad": terminal_attempt[
                        "one_step_minimum_margin_rad"
                    ],
                    "one_step_risk_agreement": terminal_attempt[
                        "one_step_risk_agreement"
                    ],
                    "one_step_restore_identity": terminal_attempt[
                        "one_step_restore_identity"
                    ],
                    "first_action_shadow_advanced": False,
                    "advanced_state_minimum_margin_rad": None,
                }
                cycles.append(cycle_row)
                if selected_prefix is None:
                    lane_safe = False
                    break
                # This is an explicitly isolated shadow advance, not a live
                # policy dispatch. The transition tuple is discarded.
                if selected_advance_nullspace_offset is not None:
                    executed_configuration = (
                        _configure_nullspace_retreat(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            limits=limits,
                            joint_index=(
                                controller_nullspace_target_joint_index
                            ),
                            joint_side=(
                                controller_nullspace_target_joint_side
                            ),
                            offset_rad=(
                                selected_advance_nullspace_offset
                            ),
                        )
                    )
                    nullspace_controller_configuration_count += 1
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                    ):
                        raise RecedingHorizonPilotError(
                            "executed nullspace config changed qpos/qvel"
                        )
                elif selected_advance_controller_goal_reset:
                    _reset_controller(robot)
                    reset_exact_h1_controller_goal_reset_count += 1
                env.step(
                    np.asarray(
                        selected_prefix[0], dtype=np.float64
                    )
                )
                contacts.observe(env)
                policy_advance_steps += 1
                qpos = np.asarray(
                    env.sim.data.qpos[qidx], dtype=np.float64
                )
                advanced_margin = _minimum_margin(qpos, limits)
                cycle_row["first_action_shadow_advanced"] = True
                cycle_row[
                    "advanced_state_minimum_margin_rad"
                ] = advanced_margin
                if reset_exact_h1_fallbacks:
                    executed_fallback = reset_exact_h1_fallbacks[-1]
                    executed_fallback["executed_in_shadow"] = True
                    executed_fallback["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_fallback[
                                    "exact_first_action"
                                ],
                                dtype=np.float64,
                            ),
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            ),
                        )
                    )
                    executed_fallback[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_fallback[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_fallback[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                if nullspace_exact_h1_fallbacks:
                    executed_nullspace = (
                        nullspace_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_nullspace[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_nullspace["executed_in_shadow"] = True
                    executed_nullspace[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_nullspace["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_nullspace[
                                    "exact_first_action"
                                ],
                                dtype=np.float64,
                            ),
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            ),
                        )
                    )
                    executed_nullspace[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_nullspace[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                if advanced_margin < (
                    selected_advance_minimum_margin_floor
                ):
                    lane_safe = False
                    break
                branch_state = trusted_joint_state_from_libero(
                    env,
                    state_epoch=branch_state.state_epoch + 1,
                    source_id=(
                        f"{source_version}:{TARGET_ID}:"
                        f"lane{lane_index}:"
                        f"cycle{cycle_index}:advanced"
                    ),
                )
            lane_rows.append(
                {
                    "lane_index": lane_index,
                    "base_seed": base_seed,
                    "planned_cycle_count": RECEDING_CYCLE_COUNT,
                    "completed_cycle_count": sum(
                        cycle["first_action_shadow_advanced"]
                        for cycle in cycles
                    ),
                    "lane_safe": (
                        lane_safe
                        and len(cycles) == RECEDING_CYCLE_COUNT
                        and all(
                            cycle["first_action_shadow_advanced"]
                            for cycle in cycles
                        )
                    ),
                    "recovery_minimum_margin_rad": min(
                        recovery_margins
                    ),
                    "recovery_terminal_margin_rad": (
                        recovery_margins[-1]
                    ),
                    "cycles": cycles,
                }
            )
        restore_identity = (
            restore_identity
            and _restore_identity(
                env, robot, initial_screen["snapshot"]
            )
        )
        if not restore_identity:
            raise RecedingHorizonPilotError(
                "receding-horizon branch restore identity failed"
            )
        return {
            "schema": row_schema,
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
            "trigger_policy_seed": trigger_policy_seed,
            "trigger_clean_frame_sha256": frame_audit[
                "clean_frame_sha256"
            ],
            "trigger_policy_chunk_sha256": chunk_digest,
            "initial_shadow_verdict": initial_screen[
                "decision"
            ].verdict.value,
            "recovery_candidate_id": predecessor_candidate[
                "candidate_id"
            ],
            "recovery_action_ids": list(action_ids),
            "replan_attempts_per_cycle": (
                replan_attempts_per_cycle
            ),
            "seed_attempt_stride": seed_attempt_stride,
            "maximum_recovery_escalations_per_cycle": (
                maximum_recovery_escalations_per_cycle
            ),
            "maximum_safe_bridges_per_cycle": (
                maximum_safe_bridges_per_cycle
            ),
            "gate_horizon_steps": gate_horizon_steps,
            "bridge_floor_mode": bridge_floor_mode,
            "consume_bridge_authorized_prefix": (
                consume_bridge_authorized_prefix
            ),
            "controller_goal_reset_before_bridge": (
                controller_goal_reset_before_bridge
            ),
            "controller_reset_exact_h1_fallback": (
                controller_reset_exact_h1_fallback
            ),
            "reset_exact_h1_require_backup_viability": (
                reset_exact_h1_require_backup_viability
            ),
            "reset_backup_require_safe_successor": (
                reset_backup_require_safe_successor
            ),
            "maximum_reset_reserve_bridges_per_cycle": (
                maximum_reset_reserve_bridges_per_cycle
            ),
            "controller_nullspace_exact_h1_offsets_rad": list(
                controller_nullspace_exact_h1_offsets_rad
            ),
            "controller_nullspace_target_joint_index": (
                controller_nullspace_target_joint_index
            ),
            "controller_nullspace_target_joint_side": (
                controller_nullspace_target_joint_side
            ),
            "lane_base_seeds": list(lane_base_seeds),
            "recovery_round_seed_stride": (
                recovery_round_seed_stride
            ),
            "lane_results": lane_rows,
            "receding_horizon_success": all(
                lane["lane_safe"] for lane in lane_rows
            ),
            "branch_restore_identity": restore_identity,
            "policy_load_count": 1,
            "policy_inference_count": inference_count,
            "initial_policy_shadow_env_step_count": initial_screen[
                "shadow_env_step_count"
            ],
            "recovery_candidate_shadow_env_step_count": (
                recovery_shadow_steps
            ),
            "escalation_candidate_shadow_env_step_count": (
                escalation_candidate_shadow_steps
            ),
            "escalation_execution_shadow_env_step_count": (
                escalation_execution_shadow_steps
            ),
            "bridge_candidate_shadow_env_step_count": (
                bridge_candidate_shadow_steps
            ),
            "bridge_post_h1_shadow_env_step_count": (
                bridge_post_h1_shadow_steps
            ),
            "bridge_execution_shadow_env_step_count": (
                bridge_execution_shadow_steps
            ),
            "bridge_controller_goal_reset_count": (
                bridge_controller_goal_reset_count
            ),
            "reset_exact_h1_shadow_env_step_count": (
                reset_exact_h1_shadow_steps
            ),
            "reset_exact_h1_controller_goal_reset_count": (
                reset_exact_h1_controller_goal_reset_count
            ),
            "reset_backup_candidate_shadow_env_step_count": (
                reset_backup_candidate_shadow_steps
            ),
            "reset_reserve_execution_shadow_env_step_count": (
                reset_reserve_execution_shadow_steps
            ),
            "reset_backup_controller_goal_reset_count": (
                reset_backup_controller_goal_reset_count
            ),
            "nullspace_exact_h1_shadow_env_step_count": (
                nullspace_exact_h1_shadow_steps
            ),
            "nullspace_controller_configuration_count": (
                nullspace_controller_configuration_count
            ),
            "full_prefix_shadow_env_step_count": (
                full_prefix_shadow_steps
            ),
            "one_step_gate_shadow_env_step_count": (
                one_step_shadow_steps
            ),
            "policy_conditioned_shadow_advance_env_step_count": (
                policy_advance_steps
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
        raise RecedingHorizonPilotError(
            "expected exactly the frozen target row"
        )
    row = rows[0]
    cycles = [
        cycle
        for lane in row["lane_results"]
        for cycle in lane["cycles"]
    ]
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "receding_horizon_recovery_v12_"
            "engineering_pilot_complete"
        ),
        "qualification_pass": None,
        "valid_case_count": 1,
        "target_id": TARGET_ID,
        "recovery_candidate_id": row["recovery_candidate_id"],
        "lane_count": len(row["lane_results"]),
        "planned_cycle_count_per_lane": RECEDING_CYCLE_COUNT,
        "completed_cycle_counts": {
            str(lane["base_seed"]): lane["completed_cycle_count"]
            for lane in row["lane_results"]
        },
        "safe_lane_count": sum(
            lane["lane_safe"] for lane in row["lane_results"]
        ),
        "receding_horizon_success": row[
            "receding_horizon_success"
        ],
        "full_prefix_allow_count": sum(
            cycle["full_prefix_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for cycle in cycles
        ),
        "one_step_allow_count": sum(
            cycle["one_step_verdict"]
            == PolicyPrefixShadowVerdict.ALLOW_EXACT.value
            for cycle in cycles
        ),
        "branch_restore_identity_rate": float(
            row["branch_restore_identity"]
        ),
        "policy_load_count": 1,
        "policy_inference_count": row["policy_inference_count"],
        "initial_policy_shadow_env_step_count": row[
            "initial_policy_shadow_env_step_count"
        ],
        "recovery_candidate_shadow_env_step_count": row[
            "recovery_candidate_shadow_env_step_count"
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
            "receding-horizon pilot requires a clean worktree"
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
        raise RecedingHorizonPilotError(
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
            "running_no_outcome_receding_horizon_pilot"
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
        raise RecedingHorizonPilotError(
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
        raise RecedingHorizonPilotError(
            "receding-horizon summary recomputation differs"
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
