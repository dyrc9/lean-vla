#!/usr/bin/env python3
"""Evaluate one-step receding-horizon policy shadow after recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from types import MethodType
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
        "prior_initial_joint": initial_joint.tolist(),
        "retreat_initial_joint": target.tolist(),
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


def _configure_joint_velocity_damping(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    joint_index: int,
    gain: float,
) -> dict[str, Any]:
    if (
        joint_index < 0
        or joint_index >= len(qidx)
        or len(qidx) != len(vidx)
        or not np.isfinite(gain)
        or gain <= 0
    ):
        raise RecedingHorizonPilotError(
            "invalid joint-velocity damping configuration"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    controller = robot.controller
    controller.update(force=True)
    controller.reset_goal()
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    if (
        actuator_min.shape != (len(qidx),)
        or actuator_max.shape != (len(qidx),)
    ):
        raise RecedingHorizonPilotError(
            "unexpected controller actuator-limit shape"
        )
    return {
        "target_joint_index": joint_index,
        "gain": float(gain),
        "controller_goal_reset": True,
        "target_actuator_min": float(actuator_min[joint_index]),
        "target_actuator_max": float(actuator_max[joint_index]),
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_joint_velocity_damping(
    robot: Any,
    *,
    joint_index: int,
    gain: float,
) -> Any:
    controller = robot.controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    if (
        joint_index < 0
        or joint_index >= len(actuator_min)
        or actuator_min.shape != actuator_max.shape
        or not np.isfinite(gain)
        or gain <= 0
    ):
        raise RecedingHorizonPilotError(
            "invalid scoped joint-velocity damping"
        )
    if "run_controller" in controller.__dict__:
        raise RecedingHorizonPilotError(
            "controller already has a run_controller override"
        )
    original_run_controller = controller.run_controller
    torque_audit: list[dict[str, Any]] = []

    def damped_run_controller(controller_self: Any) -> np.ndarray:
        nominal = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[joint_index]
        )
        requested_damping = -float(gain) * joint_velocity
        unclipped = nominal.copy()
        unclipped[joint_index] += requested_damping
        applied = np.asarray(
            controller_self.clip_torques(unclipped),
            dtype=np.float64,
        ).copy()
        controller_self.torques = applied
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_velocity_rad_s": joint_velocity,
                "nominal_torque": float(nominal[joint_index]),
                "requested_damping_torque": requested_damping,
                "unclipped_torque": float(unclipped[joint_index]),
                "applied_torque": float(applied[joint_index]),
                "actuator_min": float(actuator_min[joint_index]),
                "actuator_max": float(actuator_max[joint_index]),
                "torque_clipped": bool(
                    not np.array_equal(unclipped, applied)
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        damped_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _configure_joint_limit_velocity_envelope(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    joint_index: int,
    joint_side: str,
    margin_floor: float,
    slope: float,
) -> dict[str, Any]:
    if (
        joint_index < 0
        or joint_index >= len(qidx)
        or len(qidx) != len(vidx)
        or limits.shape != (len(qidx), 2)
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(margin_floor)
        or margin_floor < 0
        or not np.isfinite(slope)
        or slope < 0
    ):
        raise RecedingHorizonPilotError(
            "invalid joint-limit velocity-envelope configuration"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    controller = robot.controller
    controller.update(force=True)
    controller.reset_goal()
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    limit = float(
        limits[
            joint_index,
            1 if joint_side == "upper" else 0,
        ]
    )
    return {
        "target_joint_index": joint_index,
        "target_joint_side": joint_side,
        "target_joint_limit_rad": limit,
        "minimum_margin_floor_rad": float(margin_floor),
        "slope_per_s": float(slope),
        "controller_goal_reset": True,
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_joint_limit_velocity_envelope(
    robot: Any,
    *,
    joint_index: int,
    joint_side: str,
    joint_limit: float,
    margin_floor: float,
    slope: float,
) -> Any:
    controller = robot.controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    if (
        joint_index < 0
        or joint_index >= len(actuator_min)
        or actuator_min.shape != actuator_max.shape
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(joint_limit)
        or not np.isfinite(margin_floor)
        or margin_floor < 0
        or not np.isfinite(slope)
        or slope < 0
    ):
        raise RecedingHorizonPilotError(
            "invalid scoped joint-limit velocity envelope"
        )
    if "run_controller" in controller.__dict__:
        raise RecedingHorizonPilotError(
            "controller already has a run_controller override"
        )
    original_run_controller = controller.run_controller
    torque_audit: list[dict[str, Any]] = []

    def enveloped_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        joint_position = float(
            np.asarray(
                controller_self.joint_pos, dtype=np.float64
            )[joint_index]
        )
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[joint_index]
        )
        if joint_side == "upper":
            margin = float(joint_limit) - joint_position
            toward_limit_velocity = joint_velocity
            brake_torque = float(actuator_min[joint_index])
        else:
            margin = joint_position - float(joint_limit)
            toward_limit_velocity = -joint_velocity
            brake_torque = float(actuator_max[joint_index])
        allowed_toward_limit_velocity = float(slope) * max(
            margin - float(margin_floor), 0.0
        )
        activated = (
            toward_limit_velocity > allowed_toward_limit_velocity
        )
        unclipped = nominal.copy()
        if activated:
            unclipped[joint_index] = brake_torque
        applied = np.asarray(
            controller_self.clip_torques(unclipped),
            dtype=np.float64,
        ).copy()
        controller_self.torques = applied
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_position_rad": joint_position,
                "joint_velocity_rad_s": joint_velocity,
                "joint_margin_rad": margin,
                "toward_limit_velocity_rad_s": (
                    toward_limit_velocity
                ),
                "allowed_toward_limit_velocity_rad_s": (
                    allowed_toward_limit_velocity
                ),
                "envelope_activated": activated,
                "nominal_torque": float(nominal[joint_index]),
                "unclipped_torque": float(unclipped[joint_index]),
                "applied_torque": float(applied[joint_index]),
                "actuator_min": float(actuator_min[joint_index]),
                "actuator_max": float(actuator_max[joint_index]),
                "target_joint_torque_clipped": bool(
                    unclipped[joint_index] != applied[joint_index]
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        enveloped_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _configure_joint_limit_anticipatory_brake(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    joint_index: int,
    joint_side: str,
    actuator_bound_fraction: float,
) -> dict[str, Any]:
    if (
        joint_index < 0
        or joint_index >= len(qidx)
        or len(qidx) != len(vidx)
        or limits.shape != (len(qidx), 2)
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(actuator_bound_fraction)
        or actuator_bound_fraction <= 0
        or actuator_bound_fraction > 1
    ):
        raise RecedingHorizonPilotError(
            "invalid anticipatory-brake configuration"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    controller = robot.controller
    controller.update(force=True)
    controller.reset_goal()
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    return {
        "target_joint_index": joint_index,
        "target_joint_side": joint_side,
        "actuator_bound_fraction": float(
            actuator_bound_fraction
        ),
        "controller_goal_reset": True,
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_joint_limit_anticipatory_brake(
    robot: Any,
    *,
    joint_index: int,
    joint_side: str,
    actuator_bound_fraction: float,
) -> Any:
    controller = robot.controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    if (
        joint_index < 0
        or joint_index >= len(actuator_min)
        or actuator_min.shape != actuator_max.shape
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(actuator_bound_fraction)
        or actuator_bound_fraction <= 0
        or actuator_bound_fraction > 1
    ):
        raise RecedingHorizonPilotError(
            "invalid scoped anticipatory brake"
        )
    if "run_controller" in controller.__dict__:
        raise RecedingHorizonPilotError(
            "controller already has a run_controller override"
        )
    original_run_controller = controller.run_controller
    torque_audit: list[dict[str, Any]] = []
    away_limit_bound = float(
        actuator_min[joint_index]
        if joint_side == "upper"
        else actuator_max[joint_index]
    )
    requested_brake_torque = (
        float(actuator_bound_fraction) * away_limit_bound
    )

    def braked_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        joint_position = float(
            np.asarray(
                controller_self.joint_pos, dtype=np.float64
            )[joint_index]
        )
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[joint_index]
        )
        unclipped = nominal.copy()
        unclipped[joint_index] = requested_brake_torque
        applied = np.asarray(
            controller_self.clip_torques(unclipped),
            dtype=np.float64,
        ).copy()
        controller_self.torques = applied
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_position_rad": joint_position,
                "joint_velocity_rad_s": joint_velocity,
                "nominal_torque": float(nominal[joint_index]),
                "requested_brake_torque": requested_brake_torque,
                "applied_torque": float(applied[joint_index]),
                "actuator_min": float(actuator_min[joint_index]),
                "actuator_max": float(actuator_max[joint_index]),
                "target_joint_torque_clipped": bool(
                    requested_brake_torque
                    != applied[joint_index]
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        braked_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _configure_coupled_inverse_mass_brake(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    joint_index: int,
    joint_side: str,
    blend_fraction: float,
) -> dict[str, Any]:
    if (
        joint_index < 0
        or joint_index >= len(qidx)
        or len(qidx) != len(vidx)
        or limits.shape != (len(qidx), 2)
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(blend_fraction)
        or blend_fraction <= 0
        or blend_fraction > 1
    ):
        raise RecedingHorizonPilotError(
            "invalid coupled inverse-mass brake configuration"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    controller = robot.controller
    controller.update(force=True)
    controller.reset_goal()
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    return {
        "target_joint_index": joint_index,
        "target_joint_side": joint_side,
        "blend_fraction": float(blend_fraction),
        "controller_goal_reset": True,
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_coupled_inverse_mass_brake(
    robot: Any,
    *,
    joint_index: int,
    joint_side: str,
    blend_fraction: float,
) -> Any:
    controller = robot.controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    if (
        joint_index < 0
        or joint_index >= len(actuator_min)
        or actuator_min.shape != actuator_max.shape
        or joint_side not in {"lower", "upper"}
        or not np.isfinite(blend_fraction)
        or blend_fraction <= 0
        or blend_fraction > 1
    ):
        raise RecedingHorizonPilotError(
            "invalid scoped coupled inverse-mass brake"
        )
    if "run_controller" in controller.__dict__:
        raise RecedingHorizonPilotError(
            "controller already has a run_controller override"
        )
    original_run_controller = controller.run_controller
    torque_audit: list[dict[str, Any]] = []

    def coupled_brake_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal_raw = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        nominal = np.asarray(
            controller_self.clip_torques(nominal_raw),
            dtype=np.float64,
        ).copy()
        mass_matrix = np.asarray(
            controller_self.mass_matrix, dtype=np.float64
        )
        if mass_matrix.shape != (
            len(actuator_min),
            len(actuator_min),
        ):
            raise RecedingHorizonPilotError(
                "unexpected controller mass-matrix shape"
            )
        basis = np.zeros(len(actuator_min), dtype=np.float64)
        basis[joint_index] = 1.0
        inverse_mass_row = np.linalg.solve(mass_matrix, basis)
        toward_acceleration_row = (
            inverse_mass_row
            if joint_side == "upper"
            else -inverse_mass_row
        )
        maximum_away_vertex = np.where(
            toward_acceleration_row > 0,
            actuator_min,
            np.where(
                toward_acceleration_row < 0,
                actuator_max,
                nominal,
            ),
        )
        blended = nominal + float(blend_fraction) * (
            maximum_away_vertex - nominal
        )
        applied = np.asarray(
            controller_self.clip_torques(blended),
            dtype=np.float64,
        ).copy()
        controller_self.torques = applied
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[joint_index]
        )
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_velocity_rad_s": joint_velocity,
                "inverse_mass_row": inverse_mass_row.tolist(),
                "mass_solve_max_abs_residual": float(
                    np.max(
                        np.abs(
                            mass_matrix @ inverse_mass_row - basis
                        )
                    )
                ),
                "nominal_clipped_torque": nominal.tolist(),
                "maximum_away_vertex_torque": (
                    maximum_away_vertex.tolist()
                ),
                "applied_torque": applied.tolist(),
                "nominal_toward_acceleration_term": float(
                    toward_acceleration_row @ nominal
                ),
                "vertex_toward_acceleration_term": float(
                    toward_acceleration_row
                    @ maximum_away_vertex
                ),
                "applied_toward_acceleration_term": float(
                    toward_acceleration_row @ applied
                ),
                "torque_bound_violation": bool(
                    np.any(applied < actuator_min)
                    or np.any(applied > actuator_max)
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        coupled_brake_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _contact_aware_actuator_vertex(
    controller: Any,
    *,
    target_joint_index: int,
    target_joint_side: str,
    vertex_id: int,
) -> np.ndarray:
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    other_joints = [
        index
        for index in range(len(actuator_min))
        if index != target_joint_index
    ]
    if (
        target_joint_index < 0
        or target_joint_index >= len(actuator_min)
        or actuator_min.shape != actuator_max.shape
        or len(other_joints) != 6
        or target_joint_side not in {"lower", "upper"}
        or vertex_id < 0
        or vertex_id >= 2 ** len(other_joints)
    ):
        raise RecedingHorizonPilotError(
            "invalid contact-aware actuator vertex"
        )
    vertex = np.empty_like(actuator_min)
    vertex[target_joint_index] = (
        actuator_min[target_joint_index]
        if target_joint_side == "upper"
        else actuator_max[target_joint_index]
    )
    for bit_index, joint_index in enumerate(other_joints):
        vertex[joint_index] = (
            actuator_max[joint_index]
            if vertex_id & (1 << bit_index)
            else actuator_min[joint_index]
        )
    return vertex


def _configure_contact_aware_actuator_vertex(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    target_joint_index: int,
    target_joint_side: str,
    vertex_id: int,
) -> dict[str, Any]:
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    controller = robot.controller
    controller.update(force=True)
    controller.reset_goal()
    vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=target_joint_index,
        target_joint_side=target_joint_side,
        vertex_id=vertex_id,
    )
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    return {
        "target_joint_index": target_joint_index,
        "target_joint_side": target_joint_side,
        "vertex_id": vertex_id,
        "vertex_torque": vertex.tolist(),
        "controller_goal_reset": True,
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_contact_aware_actuator_vertex(
    robot: Any,
    *,
    target_joint_index: int,
    target_joint_side: str,
    vertex_id: int,
) -> Any:
    controller = robot.controller
    if "run_controller" in controller.__dict__:
        raise RecedingHorizonPilotError(
            "controller already has a run_controller override"
        )
    original_run_controller = controller.run_controller
    vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=target_joint_index,
        target_joint_side=target_joint_side,
        vertex_id=vertex_id,
    )
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    torque_audit: list[dict[str, Any]] = []

    def vertex_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        applied = vertex.copy()
        controller_self.torques = applied
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[target_joint_index]
        )
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_velocity_rad_s": joint_velocity,
                "nominal_torque": nominal.tolist(),
                "applied_vertex_torque": applied.tolist(),
                "torque_bound_violation": bool(
                    np.any(applied < actuator_min)
                    or np.any(applied > actuator_max)
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        vertex_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


@contextmanager
def _scoped_contact_aware_actuator_vertex_blend(
    robot: Any,
    *,
    target_joint_index: int,
    target_joint_side: str,
    vertex_id: int,
    blend_fraction: float,
) -> Any:
    controller = robot.controller
    if (
        "run_controller" in controller.__dict__
        or not np.isfinite(blend_fraction)
        or blend_fraction <= 0
        or blend_fraction > 1
    ):
        raise RecedingHorizonPilotError(
            "invalid contact-aware actuator vertex blend"
        )
    original_run_controller = controller.run_controller
    vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=target_joint_index,
        target_joint_side=target_joint_side,
        vertex_id=vertex_id,
    )
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    torque_audit: list[dict[str, Any]] = []

    def blended_vertex_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal_raw = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        nominal = np.asarray(
            controller_self.clip_torques(nominal_raw),
            dtype=np.float64,
        ).copy()
        applied = nominal + float(blend_fraction) * (
            vertex - nominal
        )
        applied = np.asarray(
            controller_self.clip_torques(applied),
            dtype=np.float64,
        ).copy()
        controller_self.torques = applied
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[target_joint_index]
        )
        torque_audit.append(
            {
                "controller_substep_index": len(torque_audit),
                "joint_velocity_rad_s": joint_velocity,
                "blend_fraction": float(blend_fraction),
                "nominal_clipped_torque": nominal.tolist(),
                "vertex_torque": vertex.tolist(),
                "applied_torque": applied.tolist(),
                "torque_bound_violation": bool(
                    np.any(applied < actuator_min)
                    or np.any(applied > actuator_max)
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        blended_vertex_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _configure_contact_aware_actuator_vertex_schedule(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    target_joint_index: int,
    target_joint_side: str,
    first_vertex_id: int,
    second_vertex_id: int,
    switch_substep_index: int,
) -> dict[str, Any]:
    configuration = _configure_contact_aware_actuator_vertex(
        env=env,
        robot=robot,
        qidx=qidx,
        vidx=vidx,
        target_joint_index=target_joint_index,
        target_joint_side=target_joint_side,
        vertex_id=first_vertex_id,
    )
    controller = robot.controller
    second_vertex = _contact_aware_actuator_vertex(
        controller,
        target_joint_index=target_joint_index,
        target_joint_side=target_joint_side,
        vertex_id=second_vertex_id,
    )
    configuration.update(
        {
            "vertex_id": first_vertex_id,
            "schedule_vertex_ids": [
                first_vertex_id,
                second_vertex_id,
            ],
            "switch_substep_index": switch_substep_index,
            "second_vertex_torque": second_vertex.tolist(),
        }
    )
    return configuration


@contextmanager
def _scoped_contact_aware_actuator_vertex_schedule(
    robot: Any,
    *,
    target_joint_index: int,
    target_joint_side: str,
    first_vertex_id: int,
    second_vertex_id: int,
    switch_substep_index: int,
) -> Any:
    controller = robot.controller
    if (
        "run_controller" in controller.__dict__
        or switch_substep_index <= 0
    ):
        raise RecedingHorizonPilotError(
            "invalid contact-aware actuator vertex schedule"
        )
    original_run_controller = controller.run_controller
    vertices = (
        _contact_aware_actuator_vertex(
            controller,
            target_joint_index=target_joint_index,
            target_joint_side=target_joint_side,
            vertex_id=first_vertex_id,
        ),
        _contact_aware_actuator_vertex(
            controller,
            target_joint_index=target_joint_index,
            target_joint_side=target_joint_side,
            vertex_id=second_vertex_id,
        ),
    )
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    torque_audit: list[dict[str, Any]] = []

    def scheduled_vertex_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        nominal = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        substep_index = len(torque_audit)
        phase_index = int(
            substep_index >= switch_substep_index
        )
        applied = vertices[phase_index].copy()
        controller_self.torques = applied
        joint_velocity = float(
            np.asarray(
                controller_self.joint_vel, dtype=np.float64
            )[target_joint_index]
        )
        torque_audit.append(
            {
                "controller_substep_index": substep_index,
                "schedule_phase_index": phase_index,
                "applied_vertex_id": (
                    first_vertex_id
                    if phase_index == 0
                    else second_vertex_id
                ),
                "switch_substep_index": switch_substep_index,
                "joint_velocity_rad_s": joint_velocity,
                "nominal_torque": nominal.tolist(),
                "applied_vertex_torque": applied.tolist(),
                "torque_bound_violation": bool(
                    np.any(applied < actuator_min)
                    or np.any(applied > actuator_max)
                ),
            }
        )
        return applied

    controller.run_controller = MethodType(
        scheduled_vertex_run_controller, controller
    )
    try:
        yield torque_audit
    finally:
        del controller.run_controller


def _configure_virtual_joint_guard(
    *,
    env: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    target_joint_index: int,
    target_joint_side: str,
    guard_margin_rad: float,
    guard_solref: tuple[float, float] | None = None,
    guard_solimp: tuple[
        float, float, float, float, float
    ]
    | None = None,
) -> dict[str, Any]:
    model = env.sim.model
    qpos_address = int(qidx[target_joint_index])
    joint_ids = np.flatnonzero(
        np.asarray(model.jnt_qposadr) == qpos_address
    )
    if (
        len(joint_ids) != 1
        or not np.isfinite(guard_margin_rad)
        or guard_margin_rad <= 0
        or (guard_solref is None) != (guard_solimp is None)
        or (
            guard_solref is not None
            and (
                len(guard_solref) != 2
                or len(guard_solimp) != 5
                or any(
                    not np.isfinite(value)
                    for value in (*guard_solref, *guard_solimp)
                )
            )
        )
    ):
        raise RecedingHorizonPilotError(
            "invalid virtual joint guard configuration"
        )
    model_joint_id = int(joint_ids[0])
    original_range = np.asarray(
        model.jnt_range[model_joint_id], dtype=np.float64
    ).copy()
    original_solref = np.asarray(
        model.jnt_solref[model_joint_id], dtype=np.float64
    ).copy()
    original_solimp = np.asarray(
        model.jnt_solimp[model_joint_id], dtype=np.float64
    ).copy()
    guarded_range = original_range.copy()
    if target_joint_side == "upper":
        guarded_range[1] = (
            original_range[1] - guard_margin_rad
        )
    elif target_joint_side == "lower":
        guarded_range[0] = (
            original_range[0] + guard_margin_rad
        )
    else:
        raise RecedingHorizonPilotError(
            "invalid virtual joint guard side"
        )
    before_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    ).copy()
    before_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    ).copy()
    target_position = float(before_qpos[target_joint_index])
    inside_guard_range = bool(
        target_position <= guarded_range[1]
        if target_joint_side == "upper"
        else target_position >= guarded_range[0]
    )
    after_qpos = np.asarray(
        env.sim.data.qpos[qidx], dtype=np.float64
    )
    after_qvel = np.asarray(
        env.sim.data.qvel[vidx], dtype=np.float64
    )
    return {
        "target_joint_index": target_joint_index,
        "target_joint_side": target_joint_side,
        "model_joint_id": model_joint_id,
        "qpos_address": qpos_address,
        "dof_address": int(vidx[target_joint_index]),
        "guard_margin_rad": float(guard_margin_rad),
        "original_joint_range": original_range.tolist(),
        "guarded_joint_range": guarded_range.tolist(),
        "original_joint_solref": original_solref.tolist(),
        "original_joint_solimp": original_solimp.tolist(),
        "guarded_joint_solref": (
            list(guard_solref)
            if guard_solref is not None
            else None
        ),
        "guarded_joint_solimp": (
            list(guard_solimp)
            if guard_solimp is not None
            else None
        ),
        "configuration_inside_guard_range": inside_guard_range,
        "configuration_qpos_identity": bool(
            np.array_equal(before_qpos, after_qpos)
        ),
        "configuration_qvel_identity": bool(
            np.array_equal(before_qvel, after_qvel)
        ),
    }


@contextmanager
def _scoped_virtual_joint_guard(
    env: Any,
    robot: Any,
    *,
    configuration: dict[str, Any],
) -> Any:
    controller = robot.controller
    model = env.sim.model
    model_joint_id = int(configuration["model_joint_id"])
    dof_address = int(configuration["dof_address"])
    target_joint_index = int(
        configuration["target_joint_index"]
    )
    target_joint_side = str(configuration["target_joint_side"])
    original_range = np.asarray(
        configuration["original_joint_range"],
        dtype=np.float64,
    )
    guarded_range = np.asarray(
        configuration["guarded_joint_range"],
        dtype=np.float64,
    )
    original_solref = np.asarray(
        configuration["original_joint_solref"],
        dtype=np.float64,
    )
    original_solimp = np.asarray(
        configuration["original_joint_solimp"],
        dtype=np.float64,
    )
    guarded_solref = (
        np.asarray(
            configuration["guarded_joint_solref"],
            dtype=np.float64,
        )
        if configuration["guarded_joint_solref"] is not None
        else None
    )
    guarded_solimp = (
        np.asarray(
            configuration["guarded_joint_solimp"],
            dtype=np.float64,
        )
        if configuration["guarded_joint_solimp"] is not None
        else None
    )
    if (
        "run_controller" in controller.__dict__
        or not np.array_equal(
            np.asarray(model.jnt_range[model_joint_id]),
            original_range,
        )
        or not np.array_equal(
            np.asarray(model.jnt_solref[model_joint_id]),
            original_solref,
        )
        or not np.array_equal(
            np.asarray(model.jnt_solimp[model_joint_id]),
            original_solimp,
        )
    ):
        raise RecedingHorizonPilotError(
            "invalid virtual joint guard scope"
        )
    original_run_controller = controller.run_controller
    actuator_min = np.asarray(
        controller.actuator_min, dtype=np.float64
    )
    actuator_max = np.asarray(
        controller.actuator_max, dtype=np.float64
    )
    guard_audit: list[dict[str, Any]] = []

    def guarded_run_controller(
        controller_self: Any,
    ) -> np.ndarray:
        raw = np.asarray(
            original_run_controller(), dtype=np.float64
        ).copy()
        downstream_clipped = np.asarray(
            controller_self.clip_torques(raw),
            dtype=np.float64,
        ).copy()
        position = float(
            env.sim.data.qpos[
                int(configuration["qpos_address"])
            ]
        )
        velocity = float(
            env.sim.data.qvel[dof_address]
        )
        guarded_limit = float(
            guarded_range[
                1 if target_joint_side == "upper" else 0
            ]
        )
        guard_distance = (
            guarded_limit - position
            if target_joint_side == "upper"
            else position - guarded_limit
        )
        guard_audit.append(
            {
                "controller_substep_index": len(guard_audit),
                "target_joint_index": target_joint_index,
                "target_joint_position_rad": position,
                "target_joint_velocity_rad_s": velocity,
                "guard_distance_rad": guard_distance,
                "guard_constraint_near_or_active": bool(
                    guard_distance <= 1e-5
                ),
                "target_dof_constraint_force": float(
                    env.sim.data.qfrc_constraint[dof_address]
                ),
                "raw_controller_torque": raw.tolist(),
                "downstream_clipped_controller_torque": (
                    downstream_clipped.tolist()
                ),
                "downstream_clipping_required": bool(
                    not np.array_equal(raw, downstream_clipped)
                ),
                "torque_bound_violation": bool(
                    np.any(downstream_clipped < actuator_min)
                    or np.any(downstream_clipped > actuator_max)
                ),
            }
        )
        return raw

    model.jnt_range[model_joint_id] = guarded_range
    if guarded_solref is not None:
        model.jnt_solref[model_joint_id] = guarded_solref
        model.jnt_solimp[model_joint_id] = guarded_solimp
    env.sim.forward()
    controller.run_controller = MethodType(
        guarded_run_controller, controller
    )
    try:
        yield guard_audit
    finally:
        del controller.run_controller
        model.jnt_range[model_joint_id] = original_range
        model.jnt_solref[model_joint_id] = original_solref
        model.jnt_solimp[model_joint_id] = original_solimp
        env.sim.forward()


def _retain_contact_aware_beam(
    expansions: list[dict[str, Any]],
    *,
    beam_width: int,
    strategy: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if beam_width <= 0 or strategy not in {
        "trajectory_margin",
        "margin_velocity_diverse",
    }:
        raise RecedingHorizonPilotError(
            "invalid contact-aware beam retention"
        )
    margin_ranked = sorted(
        expansions,
        key=lambda node: (
            -node["trajectory_minimum_margin_rad"],
            -node["terminal_target_joint_margin_rad"],
            node["terminal_toward_limit_velocity_rad_s"],
            node["sequence"],
        ),
    )
    velocity_ranked = sorted(
        expansions,
        key=lambda node: (
            node["terminal_toward_limit_velocity_rad_s"],
            -node["trajectory_minimum_margin_rad"],
            -node["terminal_target_joint_margin_rad"],
            node["sequence"],
        ),
    )
    margin_quota = (
        beam_width
        if strategy == "trajectory_margin"
        else beam_width // 2
    )
    velocity_quota = (
        0
        if strategy == "trajectory_margin"
        else beam_width - margin_quota
    )
    retained_sequences: set[tuple[int, ...]] = set()
    for node in margin_ranked[:margin_quota]:
        retained_sequences.add(tuple(node["sequence"]))
    for node in velocity_ranked[:velocity_quota]:
        retained_sequences.add(tuple(node["sequence"]))
    for node in margin_ranked:
        if len(retained_sequences) >= min(
            len(expansions), beam_width
        ):
            break
        retained_sequences.add(tuple(node["sequence"]))
    retained = [
        node
        for node in margin_ranked
        if tuple(node["sequence"]) in retained_sequences
    ][:beam_width]
    margin_top = {
        tuple(node["sequence"])
        for node in margin_ranked[:margin_quota]
    }
    velocity_top = {
        tuple(node["sequence"])
        for node in velocity_ranked[:velocity_quota]
    }
    audit = {
        "strategy": strategy,
        "margin_quota": margin_quota,
        "velocity_quota": velocity_quota,
        "margin_velocity_top_overlap_count": len(
            margin_top & velocity_top
        ),
        "retained_margin_top_count": sum(
            tuple(node["sequence"]) in margin_top
            for node in retained
        ),
        "retained_velocity_top_count": sum(
            tuple(node["sequence"]) in velocity_top
            for node in retained
        ),
        "all_terminal_toward_velocity_min_rad_s": (
            velocity_ranked[0][
                "terminal_toward_limit_velocity_rad_s"
            ]
            if velocity_ranked
            else None
        ),
        "all_terminal_toward_velocity_max_rad_s": (
            velocity_ranked[-1][
                "terminal_toward_limit_velocity_rad_s"
            ]
            if velocity_ranked
            else None
        ),
        "retained_terminal_toward_velocity_min_rad_s": (
            min(
                node[
                    "terminal_toward_limit_velocity_rad_s"
                ]
                for node in retained
            )
            if retained
            else None
        ),
        "retained_terminal_toward_velocity_max_rad_s": (
            max(
                node[
                    "terminal_toward_limit_velocity_rad_s"
                ]
                for node in retained
            )
            if retained
            else None
        ),
        "best_velocity_sequence": (
            list(velocity_ranked[0]["sequence"])
            if velocity_ranked
            else None
        ),
        "best_velocity_terminal_toward_velocity_rad_s": (
            velocity_ranked[0][
                "terminal_toward_limit_velocity_rad_s"
            ]
            if velocity_ranked
            else None
        ),
        "best_velocity_trajectory_minimum_margin_rad": (
            velocity_ranked[0][
                "trajectory_minimum_margin_rad"
            ]
            if velocity_ranked
            else None
        ),
    }
    return retained, audit


def _screen_contact_aware_vertex_beam(
    *,
    env: Any,
    robot: Any,
    qidx: np.ndarray,
    vidx: np.ndarray,
    limits: np.ndarray,
    snapshot: Any,
    contacts: base.ContactCapacityAudit,
    actions: tuple[tuple[float, ...], ...],
    vertex_ids: tuple[int, ...],
    blend_fractions: tuple[float, ...] = (),
    vertex_schedules: tuple[tuple[int, int], ...] = (),
    schedule_switch_substep_index: int = 12,
    virtual_joint_guard_margins_rad: tuple[float, ...] = (),
    virtual_joint_guard_solref: tuple[float, float] | None = None,
    virtual_joint_guard_solimp: tuple[
        float, float, float, float, float
    ]
    | None = None,
    target_joint_index: int,
    target_joint_side: str,
    minimum_margin_floor_rad: float,
    beam_width: int,
    retention_strategy: str = "trajectory_margin",
    source_id: str,
) -> dict[str, Any]:
    if (
        not actions
        or (
            not vertex_ids
            and not virtual_joint_guard_margins_rad
        )
        or beam_width <= 0
        or minimum_margin_floor_rad < 0
        or retention_strategy
        not in {
            "trajectory_margin",
            "margin_velocity_diverse",
        }
        or sum(
            bool(modes)
            for modes in (
                blend_fractions,
                vertex_schedules,
                virtual_joint_guard_margins_rad,
            )
        )
        > 1
        or schedule_switch_substep_index <= 0
        or any(
            len(schedule) != 2
            or any(
                not isinstance(vertex_id, int)
                or vertex_id < 0
                or vertex_id >= 64
                for vertex_id in schedule
            )
            for schedule in vertex_schedules
        )
        or any(
            not np.isfinite(fraction)
            or fraction <= 0
            or fraction > 1
            for fraction in blend_fractions
        )
        or any(
            not np.isfinite(margin)
            or margin < minimum_margin_floor_rad
            for margin in virtual_joint_guard_margins_rad
        )
        or (virtual_joint_guard_solref is None)
        != (virtual_joint_guard_solimp is None)
    ):
        raise RecedingHorizonPilotError(
            "invalid contact-aware beam configuration"
        )
    target_limit = float(
        limits[
            target_joint_index,
            1 if target_joint_side == "upper" else 0,
        ]
    )
    modes = (
        tuple(
            (
                mode_id,
                vertex_id,
                float(fraction),
                None,
                None,
            )
            for mode_id, (vertex_id, fraction) in enumerate(
                (
                    (vertex_id, fraction)
                    for vertex_id in vertex_ids
                    for fraction in blend_fractions
                )
            )
        )
        if blend_fractions
        else (
            tuple(
                (
                    mode_id,
                    first_vertex_id,
                    None,
                    second_vertex_id,
                    None,
                )
                for mode_id, (
                    first_vertex_id,
                    second_vertex_id,
                ) in enumerate(vertex_schedules)
            )
            if vertex_schedules
            else (
                tuple(
                    (
                        mode_id,
                        None,
                        None,
                        None,
                        float(guard_margin),
                    )
                    for mode_id, guard_margin in enumerate(
                        virtual_joint_guard_margins_rad
                    )
                )
                if virtual_joint_guard_margins_rad
                else tuple(
                    (
                        vertex_id,
                        vertex_id,
                        None,
                        None,
                        None,
                    )
                    for vertex_id in vertex_ids
                )
            )
        )
    )
    restore_identity = _restore_identity(
        env, robot, snapshot
    )
    beam = [
        {
            "snapshot": snapshot,
            "sequence": (),
            "trajectory_minimum_margin_rad": float("inf"),
        }
    ]
    depth_summaries = []
    configuration_count = 0
    shadow_steps = 0
    qpos_identity_count = 0
    qvel_identity_count = 0
    scope_restore_count = 0
    torque_bound_violation_count = 0
    for depth, action in enumerate(actions):
        parent_count = len(beam)
        expansions = []
        for parent_index, parent in enumerate(beam):
            for (
                mode_id,
                vertex_id,
                blend_fraction,
                second_vertex_id,
                virtual_joint_guard_margin,
            ) in modes:
                restore_identity = (
                    restore_identity
                    and _restore_identity(
                        env,
                        robot,
                        parent["snapshot"],
                    )
                )
                configuration = (
                    _configure_virtual_joint_guard(
                        env=env,
                        qidx=qidx,
                        vidx=vidx,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        guard_margin_rad=(
                            virtual_joint_guard_margin
                        ),
                        guard_solref=virtual_joint_guard_solref,
                        guard_solimp=virtual_joint_guard_solimp,
                    )
                    if virtual_joint_guard_margin is not None
                    else _configure_contact_aware_actuator_vertex_schedule(
                        env=env,
                        robot=robot,
                        qidx=qidx,
                        vidx=vidx,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        first_vertex_id=vertex_id,
                        second_vertex_id=second_vertex_id,
                        switch_substep_index=(
                            schedule_switch_substep_index
                        ),
                    )
                    if second_vertex_id is not None
                    else _configure_contact_aware_actuator_vertex(
                        env=env,
                        robot=robot,
                        qidx=qidx,
                        vidx=vidx,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        vertex_id=vertex_id,
                    )
                )
                if (
                    virtual_joint_guard_margin is not None
                    and not configuration[
                        "configuration_inside_guard_range"
                    ]
                ):
                    continue
                configuration_count += 1
                qpos_identity_count += int(
                    configuration["configuration_qpos_identity"]
                )
                qvel_identity_count += int(
                    configuration["configuration_qvel_identity"]
                )
                scope = (
                    _scoped_virtual_joint_guard(
                        env,
                        robot,
                        configuration=configuration,
                    )
                    if virtual_joint_guard_margin is not None
                    else _scoped_contact_aware_actuator_vertex_schedule(
                        robot,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        first_vertex_id=vertex_id,
                        second_vertex_id=second_vertex_id,
                        switch_substep_index=(
                            schedule_switch_substep_index
                        ),
                    )
                    if second_vertex_id is not None
                    else _scoped_contact_aware_actuator_vertex_blend(
                        robot,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        vertex_id=vertex_id,
                        blend_fraction=blend_fraction,
                    )
                    if blend_fraction is not None
                    else _scoped_contact_aware_actuator_vertex(
                        robot,
                        target_joint_index=target_joint_index,
                        target_joint_side=target_joint_side,
                        vertex_id=vertex_id,
                    )
                )
                with scope as torque_audit:
                    (
                        _positions,
                        margins,
                    ) = _execute_actions(
                        env,
                        actions=(action,),
                        qidx=qidx,
                        limits=limits,
                        contacts=contacts,
                    )
                shadow_steps += 1
                scope_restored = (
                    "run_controller"
                    not in robot.controller.__dict__
                    and (
                        virtual_joint_guard_margin is None
                        or np.array_equal(
                            np.asarray(
                                env.sim.model.jnt_range[
                                    configuration["model_joint_id"]
                                ]
                            ),
                            np.asarray(
                                configuration[
                                    "original_joint_range"
                                ]
                            ),
                        )
                    )
                    and (
                        virtual_joint_guard_margin is None
                        or (
                            np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solref[
                                        configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    configuration[
                                        "original_joint_solref"
                                    ]
                                ),
                            )
                            and np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solimp[
                                        configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    configuration[
                                        "original_joint_solimp"
                                    ]
                                ),
                            )
                        )
                    )
                )
                scope_restore_count += int(scope_restored)
                candidate_bound_violations = sum(
                    sample["torque_bound_violation"]
                    for sample in torque_audit
                )
                torque_bound_violation_count += (
                    candidate_bound_violations
                )
                local_minimum_margin = min(margins)
                safe = bool(
                    configuration["configuration_qpos_identity"]
                    and configuration["configuration_qvel_identity"]
                    and scope_restored
                    and candidate_bound_violations == 0
                    and local_minimum_margin
                    >= minimum_margin_floor_rad
                    and local_minimum_margin >= 0
                )
                if not safe:
                    continue
                terminal_position = float(
                    env.sim.data.qpos[qidx[target_joint_index]]
                )
                terminal_velocity = float(
                    env.sim.data.qvel[vidx[target_joint_index]]
                )
                terminal_target_margin = (
                    target_limit - terminal_position
                    if target_joint_side == "upper"
                    else terminal_position - target_limit
                )
                terminal_toward_velocity = (
                    terminal_velocity
                    if target_joint_side == "upper"
                    else -terminal_velocity
                )
                endpoint_snapshot = (
                    base.capture_warmstart_policy_shadow_snapshot(
                        env,
                        robot,
                        source_id=(
                            f"{source_id}:depth{depth}:"
                            f"parent{parent_index}:mode{mode_id}"
                        ),
                    )
                )
                first_step = (
                    {
                        "vertex_id": vertex_id,
                        "mode_id": mode_id,
                        "blend_fraction": blend_fraction,
                        "schedule_vertex_ids": (
                            [vertex_id, second_vertex_id]
                            if second_vertex_id is not None
                            else None
                        ),
                        "schedule_switch_substep_index": (
                            schedule_switch_substep_index
                            if second_vertex_id is not None
                            else None
                        ),
                        "virtual_joint_guard_margin_rad": (
                            virtual_joint_guard_margin
                        ),
                        "configuration": configuration,
                        "controller_substep_torque_audit": (
                            torque_audit
                        ),
                        "minimum_margin_rad": (
                            local_minimum_margin
                        ),
                        "terminal_margin_rad": margins[-1],
                        "terminal_target_joint_margin_rad": (
                            terminal_target_margin
                        ),
                        "terminal_target_joint_velocity_rad_s": (
                            terminal_velocity
                        ),
                        "terminal_toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                    }
                    if depth == 0
                    else parent["first_step"]
                )
                expansions.append(
                    {
                        "snapshot": endpoint_snapshot,
                        "sequence": (
                            parent["sequence"] + (mode_id,)
                        ),
                        "trajectory_minimum_margin_rad": min(
                            parent[
                                "trajectory_minimum_margin_rad"
                            ],
                            local_minimum_margin,
                        ),
                        "terminal_margin_rad": margins[-1],
                        "terminal_target_joint_margin_rad": (
                            terminal_target_margin
                        ),
                        "terminal_target_joint_velocity_rad_s": (
                            terminal_velocity
                        ),
                        "terminal_toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                        "first_step": first_step,
                    }
                )
        beam, retention_audit = _retain_contact_aware_beam(
            expansions,
            beam_width=beam_width,
            strategy=retention_strategy,
        )
        retained_count = len(beam)
        margin_ranked = sorted(
            expansions,
            key=lambda node: (
                -node["trajectory_minimum_margin_rad"],
                -node["terminal_target_joint_margin_rad"],
                node[
                    "terminal_toward_limit_velocity_rad_s"
                ],
                node["sequence"],
            ),
        )
        depth_summaries.append(
            {
                "depth": depth + 1,
                "action": action,
                "parent_count": parent_count,
                "expansion_count": parent_count * len(modes),
                "safe_expansion_count": len(expansions),
                "retained_count": retained_count,
                "best_trajectory_minimum_margin_rad": (
                    margin_ranked[0][
                        "trajectory_minimum_margin_rad"
                    ]
                    if margin_ranked
                    else None
                ),
                "best_sequence": (
                    list(margin_ranked[0]["sequence"])
                    if margin_ranked
                    else None
                ),
                "retention_audit": retention_audit,
            }
        )
        if not beam:
            break
    restore_identity = (
        restore_identity
        and _restore_identity(env, robot, snapshot)
    )
    selected = beam[0] if len(beam) > 0 else None
    completed_horizon = (
        len(selected["sequence"]) if selected is not None else 0
    )
    selected_payload = None
    if selected is not None and completed_horizon == len(actions):
        selected_payload = {
            "sequence": list(selected["sequence"]),
            "trajectory_minimum_margin_rad": selected[
                "trajectory_minimum_margin_rad"
            ],
            "terminal_margin_rad": selected[
                "terminal_margin_rad"
            ],
            "terminal_target_joint_margin_rad": selected[
                "terminal_target_joint_margin_rad"
            ],
            "terminal_target_joint_velocity_rad_s": selected[
                "terminal_target_joint_velocity_rad_s"
            ],
            "terminal_toward_limit_velocity_rad_s": selected[
                "terminal_toward_limit_velocity_rad_s"
            ],
            "first_step": selected["first_step"],
        }
    return {
        "horizon": len(actions),
        "beam_width": beam_width,
        "retention_strategy": retention_strategy,
        "mode_count": len(modes),
        "blend_fractions": list(blend_fractions),
        "vertex_schedules": [
            list(schedule) for schedule in vertex_schedules
        ],
        "schedule_switch_substep_index": (
            schedule_switch_substep_index
            if vertex_schedules
            else None
        ),
        "virtual_joint_guard_margins_rad": list(
            virtual_joint_guard_margins_rad
        ),
        "virtual_joint_guard_solref": (
            list(virtual_joint_guard_solref)
            if virtual_joint_guard_solref is not None
            else None
        ),
        "virtual_joint_guard_solimp": (
            list(virtual_joint_guard_solimp)
            if virtual_joint_guard_solimp is not None
            else None
        ),
        "depth_summaries": depth_summaries,
        "selected": selected_payload,
        "restore_identity": restore_identity,
        "configuration_count": configuration_count,
        "shadow_env_step_count": shadow_steps,
        "configuration_qpos_identity_count": (
            qpos_identity_count
        ),
        "configuration_qvel_identity_count": (
            qvel_identity_count
        ),
        "controller_scope_restore_count": scope_restore_count,
        "torque_bound_violation_count": (
            torque_bound_violation_count
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
    controller_joint_damping_exact_h1_gains: tuple[
        float, ...
    ] = (),
    controller_joint_damping_target_joint_index: int = 1,
    controller_joint_velocity_envelope_exact_h1_slopes: tuple[
        float, ...
    ] = (),
    controller_joint_velocity_envelope_target_joint_index: int = 1,
    controller_joint_velocity_envelope_target_joint_side: str = "upper",
    controller_joint_anticipatory_brake_exact_h1_fractions: tuple[
        float, ...
    ] = (),
    controller_joint_anticipatory_brake_target_joint_index: int = 1,
    controller_joint_anticipatory_brake_target_joint_side: str = "upper",
    controller_coupled_inverse_mass_brake_exact_h1_fractions: tuple[
        float, ...
    ] = (),
    controller_coupled_inverse_mass_brake_target_joint_index: int = 1,
    controller_coupled_inverse_mass_brake_target_joint_side: str = "upper",
    controller_contact_aware_vertex_exact_h1_ids: tuple[
        int, ...
    ] = (),
    controller_contact_aware_vertex_target_joint_index: int = 1,
    controller_contact_aware_vertex_target_joint_side: str = "upper",
    contact_aware_vertex_require_terminal_non_toward_velocity: bool = True,
    contact_aware_vertex_require_safe_successor: bool = False,
    contact_aware_vertex_beam_width: int = 0,
    contact_aware_vertex_beam_max_horizon: int = 0,
    contact_aware_vertex_beam_blend_fractions: tuple[
        float, ...
    ] = (),
    contact_aware_vertex_beam_vertex_schedules: tuple[
        tuple[int, int], ...
    ] = (),
    contact_aware_vertex_beam_schedule_switch_substep_index: int = 12,
    contact_aware_vertex_beam_virtual_joint_guard_margins_rad: tuple[
        float, ...
    ] = (),
    contact_aware_vertex_beam_virtual_joint_guard_solref: tuple[
        float, float
    ]
    | None = None,
    contact_aware_vertex_beam_virtual_joint_guard_solimp: tuple[
        float, float, float, float, float
    ]
    | None = None,
    contact_aware_vertex_beam_retention_strategy: str = (
        "trajectory_margin"
    ),
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
        or any(
            not np.isfinite(gain) or gain <= 0
            for gain in controller_joint_damping_exact_h1_gains
        )
        or tuple(controller_joint_damping_exact_h1_gains)
        != tuple(
            sorted(set(controller_joint_damping_exact_h1_gains))
        )
        or controller_joint_damping_target_joint_index < 0
        or controller_joint_damping_target_joint_index >= 7
        or any(
            not np.isfinite(slope) or slope < 0
            for slope in (
                controller_joint_velocity_envelope_exact_h1_slopes
            )
        )
        or tuple(
            controller_joint_velocity_envelope_exact_h1_slopes
        )
        != tuple(
            sorted(
                set(
                    controller_joint_velocity_envelope_exact_h1_slopes
                )
            )
        )
        or controller_joint_velocity_envelope_target_joint_index < 0
        or controller_joint_velocity_envelope_target_joint_index >= 7
        or controller_joint_velocity_envelope_target_joint_side
        not in {"lower", "upper"}
        or any(
            not np.isfinite(fraction)
            or fraction <= 0
            or fraction > 1
            for fraction in (
                controller_joint_anticipatory_brake_exact_h1_fractions
            )
        )
        or tuple(
            controller_joint_anticipatory_brake_exact_h1_fractions
        )
        != tuple(
            sorted(
                set(
                    controller_joint_anticipatory_brake_exact_h1_fractions
                )
            )
        )
        or controller_joint_anticipatory_brake_target_joint_index < 0
        or controller_joint_anticipatory_brake_target_joint_index >= 7
        or controller_joint_anticipatory_brake_target_joint_side
        not in {"lower", "upper"}
        or any(
            not np.isfinite(fraction)
            or fraction <= 0
            or fraction > 1
            for fraction in (
                controller_coupled_inverse_mass_brake_exact_h1_fractions
            )
        )
        or tuple(
            controller_coupled_inverse_mass_brake_exact_h1_fractions
        )
        != tuple(
            sorted(
                set(
                    controller_coupled_inverse_mass_brake_exact_h1_fractions
                )
            )
        )
        or controller_coupled_inverse_mass_brake_target_joint_index < 0
        or controller_coupled_inverse_mass_brake_target_joint_index >= 7
        or controller_coupled_inverse_mass_brake_target_joint_side
        not in {"lower", "upper"}
        or any(
            not isinstance(vertex_id, int)
            or vertex_id < 0
            or vertex_id >= 64
            for vertex_id in controller_contact_aware_vertex_exact_h1_ids
        )
        or tuple(controller_contact_aware_vertex_exact_h1_ids)
        != tuple(
            sorted(set(controller_contact_aware_vertex_exact_h1_ids))
        )
        or controller_contact_aware_vertex_target_joint_index < 0
        or controller_contact_aware_vertex_target_joint_index >= 7
        or controller_contact_aware_vertex_target_joint_side
        not in {"lower", "upper"}
        or not isinstance(
            contact_aware_vertex_require_terminal_non_toward_velocity,
            bool,
        )
        or not isinstance(
            contact_aware_vertex_require_safe_successor,
            bool,
        )
        or contact_aware_vertex_beam_width < 0
        or contact_aware_vertex_beam_max_horizon < 0
        or (
            (contact_aware_vertex_beam_width == 0)
            != (contact_aware_vertex_beam_max_horizon == 0)
        )
        or contact_aware_vertex_beam_max_horizon
        > int(config["policy"]["source_prefix_steps"])
        or any(
            not np.isfinite(fraction)
            or fraction <= 0
            or fraction > 1
            for fraction in (
                contact_aware_vertex_beam_blend_fractions
            )
        )
        or tuple(contact_aware_vertex_beam_blend_fractions)
        != tuple(
            sorted(
                set(contact_aware_vertex_beam_blend_fractions)
            )
        )
        or (
            contact_aware_vertex_beam_blend_fractions
            and contact_aware_vertex_beam_vertex_schedules
        )
        or sum(
            bool(modes)
            for modes in (
                contact_aware_vertex_beam_blend_fractions,
                contact_aware_vertex_beam_vertex_schedules,
                contact_aware_vertex_beam_virtual_joint_guard_margins_rad,
            )
        )
        > 1
        or any(
            len(schedule) != 2
            or any(
                not isinstance(vertex_id, int)
                or vertex_id < 0
                or vertex_id >= 64
                for vertex_id in schedule
            )
            for schedule in (
                contact_aware_vertex_beam_vertex_schedules
            )
        )
        or len(
            set(contact_aware_vertex_beam_vertex_schedules)
        )
        != len(contact_aware_vertex_beam_vertex_schedules)
        or contact_aware_vertex_beam_schedule_switch_substep_index
        <= 0
        or any(
            not np.isfinite(margin)
            or margin
            < float(config["recovery"]["safe_margin_rad"])
            for margin in (
                contact_aware_vertex_beam_virtual_joint_guard_margins_rad
            )
        )
        or tuple(
            contact_aware_vertex_beam_virtual_joint_guard_margins_rad
        )
        != tuple(
            sorted(
                set(
                    contact_aware_vertex_beam_virtual_joint_guard_margins_rad
                )
            )
        )
        or (
            contact_aware_vertex_beam_virtual_joint_guard_solref
            is None
        )
        != (
            contact_aware_vertex_beam_virtual_joint_guard_solimp
            is None
        )
        or (
            contact_aware_vertex_beam_virtual_joint_guard_solref
            is not None
            and (
                len(
                    contact_aware_vertex_beam_virtual_joint_guard_solref
                )
                != 2
                or len(
                    contact_aware_vertex_beam_virtual_joint_guard_solimp
                )
                != 5
                or any(
                    not np.isfinite(value)
                    for value in (
                        *contact_aware_vertex_beam_virtual_joint_guard_solref,
                        *contact_aware_vertex_beam_virtual_joint_guard_solimp,
                    )
                )
            )
        )
        or contact_aware_vertex_beam_retention_strategy
        not in {
            "trajectory_margin",
            "margin_velocity_diverse",
        }
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
        joint_damping_exact_h1_shadow_steps = 0
        joint_damping_controller_configuration_count = 0
        joint_velocity_envelope_exact_h1_shadow_steps = 0
        joint_velocity_envelope_controller_configuration_count = 0
        joint_anticipatory_brake_exact_h1_shadow_steps = 0
        joint_anticipatory_brake_controller_configuration_count = 0
        coupled_inverse_mass_brake_exact_h1_shadow_steps = 0
        coupled_inverse_mass_brake_controller_configuration_count = 0
        contact_aware_vertex_exact_h1_shadow_steps = 0
        contact_aware_vertex_controller_configuration_count = 0
        contact_aware_vertex_successor_shadow_steps = 0
        contact_aware_vertex_beam_shadow_steps = 0
        contact_aware_vertex_beam_screen_count = 0
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
                joint_damping_exact_h1_fallbacks = []
                joint_velocity_envelope_exact_h1_fallbacks = []
                joint_anticipatory_brake_exact_h1_fallbacks = []
                coupled_inverse_mass_brake_exact_h1_fallbacks = []
                contact_aware_vertex_exact_h1_fallbacks = []
                selected_prefix = None
                selected_advance_controller_goal_reset = False
                selected_advance_nullspace_offset = None
                selected_advance_joint_damping_gain = None
                selected_advance_joint_velocity_envelope_slope = None
                selected_advance_joint_anticipatory_brake_fraction = None
                selected_advance_coupled_inverse_mass_brake_fraction = None
                selected_advance_contact_aware_vertex_id = None
                selected_advance_contact_aware_vertex_blend_fraction = None
                selected_advance_contact_aware_vertex_schedule_second_id = (
                    None
                )
                selected_advance_contact_aware_vertex_schedule_switch_substep_index = (
                    None
                )
                selected_advance_virtual_joint_guard_margin_rad = None
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
                    if controller_joint_damping_exact_h1_gains:
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for damping fallback"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        for gain in (
                            controller_joint_damping_exact_h1_gains
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
                                _configure_joint_velocity_damping(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    joint_index=(
                                        controller_joint_damping_target_joint_index
                                    ),
                                    gain=float(gain),
                                )
                            )
                            joint_damping_controller_configuration_count += (
                                1
                            )
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "damping configuration changed qpos/qvel"
                                )
                            with _scoped_joint_velocity_damping(
                                robot,
                                joint_index=(
                                    controller_joint_damping_target_joint_index
                                ),
                                gain=float(gain),
                            ) as torque_audit:
                                (
                                    _damped_positions,
                                    damped_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(exact_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            joint_damping_exact_h1_shadow_steps += 1
                            candidate_rows.append(
                                {
                                    "gain": float(gain),
                                    "configuration": configuration,
                                    "controller_substep_torque_audit": (
                                        torque_audit
                                    ),
                                    "controller_scope_restored": (
                                        "run_controller"
                                        not in robot.controller.__dict__
                                    ),
                                    "predicted_minimum_margin_rad": min(
                                        damped_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        damped_margins[-1]
                                    ),
                                    "safe": (
                                        min(damped_margins)
                                        >= fallback_floor
                                        and min(damped_margins) >= 0
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
                                candidate["gain"],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                            )
                        )
                        selected_damping = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_damping is not None:
                            selected_damping["selected"] = True
                        damping_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "target_joint_index": (
                                controller_joint_damping_target_joint_index
                            ),
                            "minimum_margin_floor_rad": fallback_floor,
                            "candidate_evaluations": candidate_rows,
                            "selected_gain": (
                                selected_damping["gain"]
                                if selected_damping is not None
                                else None
                            ),
                            "authorized": (
                                selected_damping is not None
                            ),
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_configuration": None,
                            "execution_controller_substep_torque_audit": [],
                            "execution_controller_scope_restored": None,
                            "execution_terminal_margin_rad": None,
                            "prediction_execution_margin_error_rad": None,
                        }
                        joint_damping_exact_h1_fallbacks.append(
                            damping_row
                        )
                        if selected_damping is not None:
                            selected_prefix = prefix
                            selected_advance_joint_damping_gain = (
                                selected_damping["gain"]
                            )
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                    if (
                        controller_joint_velocity_envelope_exact_h1_slopes
                    ):
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for velocity envelope"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        target_joint = (
                            controller_joint_velocity_envelope_target_joint_index
                        )
                        target_side = (
                            controller_joint_velocity_envelope_target_joint_side
                        )
                        target_limit = float(
                            limits[
                                target_joint,
                                1 if target_side == "upper" else 0,
                            ]
                        )
                        for slope in (
                            controller_joint_velocity_envelope_exact_h1_slopes
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
                                _configure_joint_limit_velocity_envelope(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    limits=limits,
                                    joint_index=target_joint,
                                    joint_side=target_side,
                                    margin_floor=fallback_floor,
                                    slope=float(slope),
                                )
                            )
                            joint_velocity_envelope_controller_configuration_count += (
                                1
                            )
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "velocity-envelope config changed qpos/qvel"
                                )
                            with _scoped_joint_limit_velocity_envelope(
                                robot,
                                joint_index=target_joint,
                                joint_side=target_side,
                                joint_limit=target_limit,
                                margin_floor=fallback_floor,
                                slope=float(slope),
                            ) as torque_audit:
                                (
                                    _enveloped_positions,
                                    enveloped_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(exact_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            joint_velocity_envelope_exact_h1_shadow_steps += (
                                1
                            )
                            terminal_joint_position = float(
                                env.sim.data.qpos[qidx[target_joint]]
                            )
                            terminal_joint_velocity = float(
                                env.sim.data.qvel[vidx[target_joint]]
                            )
                            if target_side == "upper":
                                terminal_target_margin = (
                                    target_limit
                                    - terminal_joint_position
                                )
                                terminal_toward_velocity = (
                                    terminal_joint_velocity
                                )
                            else:
                                terminal_target_margin = (
                                    terminal_joint_position
                                    - target_limit
                                )
                                terminal_toward_velocity = (
                                    -terminal_joint_velocity
                                )
                            terminal_allowed_velocity = float(
                                slope
                            ) * max(
                                terminal_target_margin
                                - fallback_floor,
                                0.0,
                            )
                            terminal_envelope_satisfied = (
                                terminal_toward_velocity
                                <= terminal_allowed_velocity + 1e-9
                            )
                            candidate_rows.append(
                                {
                                    "slope_per_s": float(slope),
                                    "configuration": configuration,
                                    "controller_substep_torque_audit": (
                                        torque_audit
                                    ),
                                    "controller_scope_restored": (
                                        "run_controller"
                                        not in robot.controller.__dict__
                                    ),
                                    "predicted_minimum_margin_rad": min(
                                        enveloped_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        enveloped_margins[-1]
                                    ),
                                    "predicted_terminal_target_joint_margin_rad": (
                                        terminal_target_margin
                                    ),
                                    "predicted_terminal_target_joint_velocity_rad_s": (
                                        terminal_joint_velocity
                                    ),
                                    "predicted_terminal_toward_limit_velocity_rad_s": (
                                        terminal_toward_velocity
                                    ),
                                    "predicted_terminal_allowed_toward_limit_velocity_rad_s": (
                                        terminal_allowed_velocity
                                    ),
                                    "terminal_envelope_satisfied": (
                                        terminal_envelope_satisfied
                                    ),
                                    "safe": (
                                        min(enveloped_margins)
                                        >= fallback_floor
                                        and min(enveloped_margins) >= 0
                                        and terminal_envelope_satisfied
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
                                -candidate["slope_per_s"],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                            )
                        )
                        selected_envelope = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_envelope is not None:
                            selected_envelope["selected"] = True
                        envelope_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "target_joint_index": target_joint,
                            "target_joint_side": target_side,
                            "minimum_margin_floor_rad": fallback_floor,
                            "candidate_evaluations": candidate_rows,
                            "selected_slope_per_s": (
                                selected_envelope["slope_per_s"]
                                if selected_envelope is not None
                                else None
                            ),
                            "authorized": (
                                selected_envelope is not None
                            ),
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_configuration": None,
                            "execution_controller_substep_torque_audit": [],
                            "execution_controller_scope_restored": None,
                            "execution_terminal_margin_rad": None,
                            "execution_terminal_target_joint_margin_rad": None,
                            "execution_terminal_target_joint_velocity_rad_s": None,
                            "execution_terminal_toward_limit_velocity_rad_s": None,
                            "execution_terminal_allowed_toward_limit_velocity_rad_s": None,
                            "execution_terminal_envelope_satisfied": None,
                            "prediction_execution_margin_error_rad": None,
                            "prediction_execution_target_joint_velocity_error_rad_s": None,
                        }
                        joint_velocity_envelope_exact_h1_fallbacks.append(
                            envelope_row
                        )
                        if selected_envelope is not None:
                            selected_prefix = prefix
                            selected_advance_joint_velocity_envelope_slope = (
                                selected_envelope["slope_per_s"]
                            )
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                    if (
                        controller_joint_anticipatory_brake_exact_h1_fractions
                    ):
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for anticipatory brake"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        target_joint = (
                            controller_joint_anticipatory_brake_target_joint_index
                        )
                        target_side = (
                            controller_joint_anticipatory_brake_target_joint_side
                        )
                        for fraction in (
                            controller_joint_anticipatory_brake_exact_h1_fractions
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
                                _configure_joint_limit_anticipatory_brake(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    limits=limits,
                                    joint_index=target_joint,
                                    joint_side=target_side,
                                    actuator_bound_fraction=float(
                                        fraction
                                    ),
                                )
                            )
                            joint_anticipatory_brake_controller_configuration_count += (
                                1
                            )
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "anticipatory-brake config changed qpos/qvel"
                                )
                            with _scoped_joint_limit_anticipatory_brake(
                                robot,
                                joint_index=target_joint,
                                joint_side=target_side,
                                actuator_bound_fraction=float(
                                    fraction
                                ),
                            ) as torque_audit:
                                (
                                    _braked_positions,
                                    braked_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(exact_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            joint_anticipatory_brake_exact_h1_shadow_steps += (
                                1
                            )
                            terminal_joint_velocity = float(
                                env.sim.data.qvel[vidx[target_joint]]
                            )
                            terminal_toward_velocity = (
                                terminal_joint_velocity
                                if target_side == "upper"
                                else -terminal_joint_velocity
                            )
                            candidate_rows.append(
                                {
                                    "actuator_bound_fraction": float(
                                        fraction
                                    ),
                                    "configuration": configuration,
                                    "controller_substep_torque_audit": (
                                        torque_audit
                                    ),
                                    "controller_scope_restored": (
                                        "run_controller"
                                        not in robot.controller.__dict__
                                    ),
                                    "predicted_minimum_margin_rad": min(
                                        braked_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        braked_margins[-1]
                                    ),
                                    "predicted_terminal_target_joint_velocity_rad_s": (
                                        terminal_joint_velocity
                                    ),
                                    "predicted_terminal_toward_limit_velocity_rad_s": (
                                        terminal_toward_velocity
                                    ),
                                    "terminal_non_toward_velocity": (
                                        terminal_toward_velocity <= 1e-9
                                    ),
                                    "safe": (
                                        min(braked_margins)
                                        >= fallback_floor
                                        and min(braked_margins) >= 0
                                        and terminal_toward_velocity
                                        <= 1e-9
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
                                candidate[
                                    "actuator_bound_fraction"
                                ],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                            )
                        )
                        selected_brake = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_brake is not None:
                            selected_brake["selected"] = True
                        brake_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "target_joint_index": target_joint,
                            "target_joint_side": target_side,
                            "minimum_margin_floor_rad": fallback_floor,
                            "candidate_evaluations": candidate_rows,
                            "selected_actuator_bound_fraction": (
                                selected_brake[
                                    "actuator_bound_fraction"
                                ]
                                if selected_brake is not None
                                else None
                            ),
                            "authorized": selected_brake is not None,
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_configuration": None,
                            "execution_controller_substep_torque_audit": [],
                            "execution_controller_scope_restored": None,
                            "execution_terminal_margin_rad": None,
                            "execution_terminal_target_joint_velocity_rad_s": None,
                            "execution_terminal_toward_limit_velocity_rad_s": None,
                            "execution_terminal_non_toward_velocity": None,
                            "prediction_execution_margin_error_rad": None,
                            "prediction_execution_target_joint_velocity_error_rad_s": None,
                        }
                        joint_anticipatory_brake_exact_h1_fallbacks.append(
                            brake_row
                        )
                        if selected_brake is not None:
                            selected_prefix = prefix
                            selected_advance_joint_anticipatory_brake_fraction = (
                                selected_brake[
                                    "actuator_bound_fraction"
                                ]
                            )
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                    if (
                        controller_coupled_inverse_mass_brake_exact_h1_fractions
                    ):
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for coupled brake"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        target_joint = (
                            controller_coupled_inverse_mass_brake_target_joint_index
                        )
                        target_side = (
                            controller_coupled_inverse_mass_brake_target_joint_side
                        )
                        for fraction in (
                            controller_coupled_inverse_mass_brake_exact_h1_fractions
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
                                _configure_coupled_inverse_mass_brake(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    limits=limits,
                                    joint_index=target_joint,
                                    joint_side=target_side,
                                    blend_fraction=float(fraction),
                                )
                            )
                            coupled_inverse_mass_brake_controller_configuration_count += (
                                1
                            )
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "coupled-brake config changed qpos/qvel"
                                )
                            with _scoped_coupled_inverse_mass_brake(
                                robot,
                                joint_index=target_joint,
                                joint_side=target_side,
                                blend_fraction=float(fraction),
                            ) as torque_audit:
                                (
                                    _coupled_positions,
                                    coupled_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(exact_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            coupled_inverse_mass_brake_exact_h1_shadow_steps += (
                                1
                            )
                            terminal_joint_velocity = float(
                                env.sim.data.qvel[vidx[target_joint]]
                            )
                            terminal_toward_velocity = (
                                terminal_joint_velocity
                                if target_side == "upper"
                                else -terminal_joint_velocity
                            )
                            candidate_rows.append(
                                {
                                    "blend_fraction": float(
                                        fraction
                                    ),
                                    "configuration": configuration,
                                    "controller_substep_torque_audit": (
                                        torque_audit
                                    ),
                                    "controller_scope_restored": (
                                        "run_controller"
                                        not in robot.controller.__dict__
                                    ),
                                    "predicted_minimum_margin_rad": min(
                                        coupled_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        coupled_margins[-1]
                                    ),
                                    "predicted_terminal_target_joint_velocity_rad_s": (
                                        terminal_joint_velocity
                                    ),
                                    "predicted_terminal_toward_limit_velocity_rad_s": (
                                        terminal_toward_velocity
                                    ),
                                    "terminal_non_toward_velocity": (
                                        terminal_toward_velocity <= 1e-9
                                    ),
                                    "safe": (
                                        min(coupled_margins)
                                        >= fallback_floor
                                        and min(coupled_margins) >= 0
                                        and terminal_toward_velocity
                                        <= 1e-9
                                        and all(
                                            not sample[
                                                "torque_bound_violation"
                                            ]
                                            for sample in torque_audit
                                        )
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
                                candidate["blend_fraction"],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                            )
                        )
                        selected_coupled_brake = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_coupled_brake is not None:
                            selected_coupled_brake["selected"] = True
                        coupled_brake_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "target_joint_index": target_joint,
                            "target_joint_side": target_side,
                            "minimum_margin_floor_rad": fallback_floor,
                            "candidate_evaluations": candidate_rows,
                            "selected_blend_fraction": (
                                selected_coupled_brake[
                                    "blend_fraction"
                                ]
                                if selected_coupled_brake is not None
                                else None
                            ),
                            "authorized": (
                                selected_coupled_brake is not None
                            ),
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_configuration": None,
                            "execution_controller_substep_torque_audit": [],
                            "execution_controller_scope_restored": None,
                            "execution_terminal_margin_rad": None,
                            "execution_terminal_target_joint_velocity_rad_s": None,
                            "execution_terminal_toward_limit_velocity_rad_s": None,
                            "execution_terminal_non_toward_velocity": None,
                            "prediction_execution_margin_error_rad": None,
                            "prediction_execution_target_joint_velocity_error_rad_s": None,
                        }
                        coupled_inverse_mass_brake_exact_h1_fallbacks.append(
                            coupled_brake_row
                        )
                        if selected_coupled_brake is not None:
                            selected_prefix = prefix
                            selected_advance_coupled_inverse_mass_brake_fraction = (
                                selected_coupled_brake[
                                    "blend_fraction"
                                ]
                            )
                            selected_advance_minimum_margin_floor = (
                                fallback_floor
                            )
                            break
                    if (
                        controller_contact_aware_vertex_exact_h1_ids
                        or contact_aware_vertex_beam_virtual_joint_guard_margins_rad
                    ):
                        if one_step_screen is None:
                            raise RecedingHorizonPilotError(
                                "missing failed gate for contact-aware vertex"
                            )
                        exact_action = tuple(
                            float(value) for value in prefix[0]
                        )
                        successor_exact_action = (
                            tuple(
                                float(value)
                                for value in prefix[1]
                            )
                            if contact_aware_vertex_require_safe_successor
                            else None
                        )
                        candidate_rows = []
                        fallback_floor = float(
                            config["recovery"]["safe_margin_rad"]
                        )
                        target_joint = (
                            controller_contact_aware_vertex_target_joint_index
                        )
                        target_side = (
                            controller_contact_aware_vertex_target_joint_side
                        )
                        target_limit = float(
                            limits[
                                target_joint,
                                1 if target_side == "upper" else 0,
                            ]
                        )
                        if contact_aware_vertex_beam_width > 0:
                            beam_horizon = min(
                                contact_aware_vertex_beam_max_horizon,
                                RECEDING_CYCLE_COUNT - cycle_index,
                                len(prefix),
                            )
                            beam_actions = tuple(
                                tuple(
                                    float(value)
                                    for value in prefix[action_index]
                                )
                                for action_index in range(beam_horizon)
                            )
                            beam_result = (
                                _screen_contact_aware_vertex_beam(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    limits=limits,
                                    snapshot=one_step_screen[
                                        "snapshot"
                                    ],
                                    contacts=contacts,
                                    actions=beam_actions,
                                    vertex_ids=(
                                        controller_contact_aware_vertex_exact_h1_ids
                                    ),
                                    blend_fractions=(
                                        contact_aware_vertex_beam_blend_fractions
                                    ),
                                    vertex_schedules=(
                                        contact_aware_vertex_beam_vertex_schedules
                                    ),
                                    schedule_switch_substep_index=(
                                        contact_aware_vertex_beam_schedule_switch_substep_index
                                    ),
                                    virtual_joint_guard_margins_rad=(
                                        contact_aware_vertex_beam_virtual_joint_guard_margins_rad
                                    ),
                                    virtual_joint_guard_solref=(
                                        contact_aware_vertex_beam_virtual_joint_guard_solref
                                    ),
                                    virtual_joint_guard_solimp=(
                                        contact_aware_vertex_beam_virtual_joint_guard_solimp
                                    ),
                                    target_joint_index=target_joint,
                                    target_joint_side=target_side,
                                    minimum_margin_floor_rad=(
                                        fallback_floor
                                    ),
                                    beam_width=(
                                        contact_aware_vertex_beam_width
                                    ),
                                    retention_strategy=(
                                        contact_aware_vertex_beam_retention_strategy
                                    ),
                                    source_id=(
                                        f"{source_version}:{TARGET_ID}:"
                                        f"lane{lane_index}:"
                                        f"cycle{cycle_index}:"
                                        f"round{recovery_round}:beam"
                                    ),
                                )
                            )
                            contact_aware_vertex_beam_screen_count += 1
                            contact_aware_vertex_beam_shadow_steps += (
                                beam_result["shadow_env_step_count"]
                            )
                            contact_aware_vertex_exact_h1_shadow_steps += (
                                beam_result["shadow_env_step_count"]
                            )
                            contact_aware_vertex_controller_configuration_count += (
                                beam_result["configuration_count"]
                            )
                            restore_identity = (
                                restore_identity
                                and beam_result["restore_identity"]
                            )
                            selected_beam = beam_result["selected"]
                            beam_candidates = []
                            if selected_beam is not None:
                                first_step = selected_beam[
                                    "first_step"
                                ]
                                beam_candidates.append(
                                    {
                                        "vertex_id": first_step[
                                            "vertex_id"
                                        ],
                                        "mode_id": first_step[
                                            "mode_id"
                                        ],
                                        "blend_fraction": first_step[
                                            "blend_fraction"
                                        ],
                                        "schedule_vertex_ids": first_step[
                                            "schedule_vertex_ids"
                                        ],
                                        "schedule_switch_substep_index": first_step[
                                            "schedule_switch_substep_index"
                                        ],
                                        "virtual_joint_guard_margin_rad": first_step[
                                            "virtual_joint_guard_margin_rad"
                                        ],
                                        "configuration": first_step[
                                            "configuration"
                                        ],
                                        "controller_substep_torque_audit": (
                                            first_step[
                                                "controller_substep_torque_audit"
                                            ]
                                        ),
                                        "controller_scope_restored": True,
                                        "predicted_minimum_margin_rad": (
                                            first_step[
                                                "minimum_margin_rad"
                                            ]
                                        ),
                                        "predicted_terminal_margin_rad": (
                                            first_step[
                                                "terminal_margin_rad"
                                            ]
                                        ),
                                        "predicted_terminal_target_joint_margin_rad": (
                                            first_step[
                                                "terminal_target_joint_margin_rad"
                                            ]
                                        ),
                                        "predicted_terminal_target_joint_velocity_rad_s": (
                                            first_step[
                                                "terminal_target_joint_velocity_rad_s"
                                            ]
                                        ),
                                        "predicted_terminal_toward_limit_velocity_rad_s": (
                                            first_step[
                                                "terminal_toward_limit_velocity_rad_s"
                                            ]
                                        ),
                                        "terminal_non_toward_velocity": (
                                            first_step[
                                                "terminal_toward_limit_velocity_rad_s"
                                            ]
                                            <= 1e-9
                                        ),
                                        "terminal_non_toward_velocity_required": False,
                                        "one_step_safe": True,
                                        "safe_successor_required": False,
                                        "successor_exact_action": None,
                                        "successor_evaluations": [],
                                        "safe_successor_count": None,
                                        "successor_restore_identity": None,
                                        "safe": True,
                                        "selected": True,
                                    }
                                )
                            vertex_row = {
                                "recovery_round": recovery_round,
                                "policy_seed": attempts[-1][
                                    "policy_seed"
                                ],
                                "policy_chunk_sha256": attempts[-1][
                                    "policy_chunk_sha256"
                                ],
                                "exact_first_action": exact_action,
                                "target_joint_index": target_joint,
                                "target_joint_side": target_side,
                                "minimum_margin_floor_rad": fallback_floor,
                                "terminal_non_toward_velocity_required": False,
                                "safe_successor_required": False,
                                "successor_exact_action": None,
                                "beam_search": beam_result,
                                "candidate_evaluations": beam_candidates,
                                "selected_vertex_id": (
                                    selected_beam["first_step"][
                                        "vertex_id"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "selected_mode_id": (
                                    selected_beam["first_step"][
                                        "mode_id"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "selected_blend_fraction": (
                                    selected_beam["first_step"][
                                        "blend_fraction"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "selected_schedule_vertex_ids": (
                                    selected_beam["first_step"][
                                        "schedule_vertex_ids"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "selected_schedule_switch_substep_index": (
                                    selected_beam["first_step"][
                                        "schedule_switch_substep_index"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "selected_virtual_joint_guard_margin_rad": (
                                    selected_beam["first_step"][
                                        "virtual_joint_guard_margin_rad"
                                    ]
                                    if selected_beam is not None
                                    else None
                                ),
                                "authorized": (
                                    selected_beam is not None
                                ),
                                "executed_in_shadow": False,
                                "exact_action_identity": None,
                                "execution_configuration": None,
                                "execution_controller_substep_torque_audit": [],
                                "execution_controller_scope_restored": None,
                                "execution_terminal_margin_rad": None,
                                "execution_terminal_target_joint_margin_rad": None,
                                "execution_terminal_target_joint_velocity_rad_s": None,
                                "execution_terminal_toward_limit_velocity_rad_s": None,
                                "execution_terminal_non_toward_velocity": None,
                                "prediction_execution_margin_error_rad": None,
                                "prediction_execution_target_joint_velocity_error_rad_s": None,
                            }
                            contact_aware_vertex_exact_h1_fallbacks.append(
                                vertex_row
                            )
                            if selected_beam is not None:
                                selected_prefix = prefix
                                selected_advance_contact_aware_vertex_id = (
                                    selected_beam["first_step"][
                                        "vertex_id"
                                    ]
                                )
                                selected_advance_contact_aware_vertex_blend_fraction = (
                                    selected_beam["first_step"][
                                        "blend_fraction"
                                    ]
                                )
                                selected_schedule = selected_beam[
                                    "first_step"
                                ]["schedule_vertex_ids"]
                                if selected_schedule is not None:
                                    selected_advance_contact_aware_vertex_schedule_second_id = (
                                        selected_schedule[1]
                                    )
                                    selected_advance_contact_aware_vertex_schedule_switch_substep_index = (
                                        selected_beam["first_step"][
                                            "schedule_switch_substep_index"
                                        ]
                                    )
                                selected_advance_virtual_joint_guard_margin_rad = (
                                    selected_beam["first_step"][
                                        "virtual_joint_guard_margin_rad"
                                    ]
                                )
                                selected_advance_minimum_margin_floor = (
                                    fallback_floor
                                )
                                break
                            continue
                        for vertex_id in (
                            controller_contact_aware_vertex_exact_h1_ids
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
                                _configure_contact_aware_actuator_vertex(
                                    env=env,
                                    robot=robot,
                                    qidx=qidx,
                                    vidx=vidx,
                                    target_joint_index=target_joint,
                                    target_joint_side=target_side,
                                    vertex_id=vertex_id,
                                )
                            )
                            contact_aware_vertex_controller_configuration_count += (
                                1
                            )
                            if (
                                not configuration[
                                    "configuration_qpos_identity"
                                ]
                                or not configuration[
                                    "configuration_qvel_identity"
                                ]
                            ):
                                raise RecedingHorizonPilotError(
                                    "contact-aware vertex config changed qpos/qvel"
                                )
                            with _scoped_contact_aware_actuator_vertex(
                                robot,
                                target_joint_index=target_joint,
                                target_joint_side=target_side,
                                vertex_id=vertex_id,
                            ) as torque_audit:
                                (
                                    _vertex_positions,
                                    vertex_margins,
                                ) = _execute_actions(
                                    env,
                                    actions=(exact_action,),
                                    qidx=qidx,
                                    limits=limits,
                                    contacts=contacts,
                                )
                            contact_aware_vertex_exact_h1_shadow_steps += 1
                            terminal_joint_position = float(
                                env.sim.data.qpos[qidx[target_joint]]
                            )
                            terminal_joint_velocity = float(
                                env.sim.data.qvel[vidx[target_joint]]
                            )
                            if target_side == "upper":
                                terminal_target_margin = (
                                    target_limit
                                    - terminal_joint_position
                                )
                                terminal_toward_velocity = (
                                    terminal_joint_velocity
                                )
                            else:
                                terminal_target_margin = (
                                    terminal_joint_position
                                    - target_limit
                                )
                                terminal_toward_velocity = (
                                    -terminal_joint_velocity
                                )
                            candidate_rows.append(
                                {
                                    "vertex_id": vertex_id,
                                    "configuration": configuration,
                                    "controller_substep_torque_audit": (
                                        torque_audit
                                    ),
                                    "controller_scope_restored": (
                                        "run_controller"
                                        not in robot.controller.__dict__
                                    ),
                                    "predicted_minimum_margin_rad": min(
                                        vertex_margins
                                    ),
                                    "predicted_terminal_margin_rad": (
                                        vertex_margins[-1]
                                    ),
                                    "predicted_terminal_target_joint_margin_rad": (
                                        terminal_target_margin
                                    ),
                                    "predicted_terminal_target_joint_velocity_rad_s": (
                                        terminal_joint_velocity
                                    ),
                                    "predicted_terminal_toward_limit_velocity_rad_s": (
                                        terminal_toward_velocity
                                    ),
                                    "terminal_non_toward_velocity": (
                                        terminal_toward_velocity <= 1e-9
                                    ),
                                    "terminal_non_toward_velocity_required": (
                                        contact_aware_vertex_require_terminal_non_toward_velocity
                                    ),
                                    "one_step_safe": (
                                        min(vertex_margins)
                                        >= fallback_floor
                                        and min(vertex_margins) >= 0
                                        and (
                                            not contact_aware_vertex_require_terminal_non_toward_velocity
                                            or terminal_toward_velocity
                                            <= 1e-9
                                        )
                                        and all(
                                            not sample[
                                                "torque_bound_violation"
                                            ]
                                            for sample in torque_audit
                                        )
                                    ),
                                    "safe_successor_required": (
                                        contact_aware_vertex_require_safe_successor
                                    ),
                                    "successor_exact_action": (
                                        successor_exact_action
                                    ),
                                    "successor_evaluations": [],
                                    "safe_successor_count": None,
                                    "successor_restore_identity": None,
                                    "safe": False,
                                    "selected": False,
                                }
                            )
                            candidate_row = candidate_rows[-1]
                            if (
                                candidate_row["one_step_safe"]
                                and contact_aware_vertex_require_safe_successor
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
                                            f"vertex{vertex_id}:endpoint"
                                        ),
                                    )
                                )
                                successor_rows = []
                                successor_restore_identity = True
                                for successor_vertex_id in (
                                    controller_contact_aware_vertex_exact_h1_ids
                                ):
                                    successor_restore_identity = (
                                        successor_restore_identity
                                        and _restore_identity(
                                            env,
                                            robot,
                                            endpoint_snapshot,
                                        )
                                    )
                                    successor_configuration = (
                                        _configure_contact_aware_actuator_vertex(
                                            env=env,
                                            robot=robot,
                                            qidx=qidx,
                                            vidx=vidx,
                                            target_joint_index=target_joint,
                                            target_joint_side=target_side,
                                            vertex_id=(
                                                successor_vertex_id
                                            ),
                                        )
                                    )
                                    contact_aware_vertex_controller_configuration_count += (
                                        1
                                    )
                                    with _scoped_contact_aware_actuator_vertex(
                                        robot,
                                        target_joint_index=target_joint,
                                        target_joint_side=target_side,
                                        vertex_id=successor_vertex_id,
                                    ) as successor_torque_audit:
                                        (
                                            _successor_positions,
                                            successor_margins,
                                        ) = _execute_actions(
                                            env,
                                            actions=(
                                                successor_exact_action,
                                            ),
                                            qidx=qidx,
                                            limits=limits,
                                            contacts=contacts,
                                        )
                                    contact_aware_vertex_successor_shadow_steps += (
                                        1
                                    )
                                    successor_terminal_velocity = float(
                                        env.sim.data.qvel[
                                            vidx[target_joint]
                                        ]
                                    )
                                    successor_safe = bool(
                                        successor_configuration[
                                            "configuration_qpos_identity"
                                        ]
                                        and successor_configuration[
                                            "configuration_qvel_identity"
                                        ]
                                        and (
                                            "run_controller"
                                            not in robot.controller.__dict__
                                        )
                                        and min(successor_margins)
                                        >= fallback_floor
                                        and min(successor_margins) >= 0
                                        and all(
                                            not sample[
                                                "torque_bound_violation"
                                            ]
                                            for sample in (
                                                successor_torque_audit
                                            )
                                        )
                                    )
                                    successor_rows.append(
                                        {
                                            "vertex_id": (
                                                successor_vertex_id
                                            ),
                                            "configuration": (
                                                successor_configuration
                                            ),
                                            "controller_scope_restored": (
                                                "run_controller"
                                                not in robot.controller.__dict__
                                            ),
                                            "controller_substep_count": len(
                                                successor_torque_audit
                                            ),
                                            "torque_bound_violation_count": sum(
                                                sample[
                                                    "torque_bound_violation"
                                                ]
                                                for sample in (
                                                    successor_torque_audit
                                                )
                                            ),
                                            "minimum_margin_rad": min(
                                                successor_margins
                                            ),
                                            "terminal_margin_rad": (
                                                successor_margins[-1]
                                            ),
                                            "terminal_target_joint_velocity_rad_s": (
                                                successor_terminal_velocity
                                            ),
                                            "safe": successor_safe,
                                        }
                                    )
                                successor_restore_identity = (
                                    successor_restore_identity
                                    and _restore_identity(
                                        env,
                                        robot,
                                        endpoint_snapshot,
                                    )
                                )
                                restore_identity = (
                                    restore_identity
                                    and successor_restore_identity
                                )
                                candidate_row[
                                    "successor_evaluations"
                                ] = successor_rows
                                candidate_row[
                                    "safe_successor_count"
                                ] = sum(
                                    row["safe"]
                                    for row in successor_rows
                                )
                                candidate_row[
                                    "successor_restore_identity"
                                ] = successor_restore_identity
                            elif candidate_row["one_step_safe"]:
                                candidate_row[
                                    "safe_successor_count"
                                ] = None
                            else:
                                candidate_row[
                                    "safe_successor_count"
                                ] = 0
                            candidate_row["safe"] = bool(
                                candidate_row["one_step_safe"]
                                and (
                                    not contact_aware_vertex_require_safe_successor
                                    or candidate_row[
                                        "safe_successor_count"
                                    ]
                                    > 0
                                )
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
                                -(
                                    candidate[
                                        "safe_successor_count"
                                    ]
                                    or 0
                                ),
                                -candidate[
                                    "predicted_terminal_target_joint_margin_rad"
                                ],
                                -candidate[
                                    "predicted_terminal_margin_rad"
                                ],
                                candidate["vertex_id"],
                            )
                        )
                        selected_vertex = (
                            safe_candidates[0]
                            if safe_candidates
                            else None
                        )
                        if selected_vertex is not None:
                            selected_vertex["selected"] = True
                        vertex_row = {
                            "recovery_round": recovery_round,
                            "policy_seed": attempts[-1][
                                "policy_seed"
                            ],
                            "policy_chunk_sha256": attempts[-1][
                                "policy_chunk_sha256"
                            ],
                            "exact_first_action": exact_action,
                            "target_joint_index": target_joint,
                            "target_joint_side": target_side,
                            "minimum_margin_floor_rad": fallback_floor,
                            "terminal_non_toward_velocity_required": (
                                contact_aware_vertex_require_terminal_non_toward_velocity
                            ),
                            "safe_successor_required": (
                                contact_aware_vertex_require_safe_successor
                            ),
                            "successor_exact_action": (
                                successor_exact_action
                            ),
                            "candidate_evaluations": candidate_rows,
                            "selected_vertex_id": (
                                selected_vertex["vertex_id"]
                                if selected_vertex is not None
                                else None
                            ),
                            "authorized": selected_vertex is not None,
                            "executed_in_shadow": False,
                            "exact_action_identity": None,
                            "execution_configuration": None,
                            "execution_controller_substep_torque_audit": [],
                            "execution_controller_scope_restored": None,
                            "execution_terminal_margin_rad": None,
                            "execution_terminal_target_joint_margin_rad": None,
                            "execution_terminal_target_joint_velocity_rad_s": None,
                            "execution_terminal_toward_limit_velocity_rad_s": None,
                            "execution_terminal_non_toward_velocity": None,
                            "prediction_execution_margin_error_rad": None,
                            "prediction_execution_target_joint_velocity_error_rad_s": None,
                        }
                        contact_aware_vertex_exact_h1_fallbacks.append(
                            vertex_row
                        )
                        if selected_vertex is not None:
                            selected_prefix = prefix
                            selected_advance_contact_aware_vertex_id = (
                                selected_vertex["vertex_id"]
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
                    "joint_damping_exact_h1_fallbacks": (
                        joint_damping_exact_h1_fallbacks
                    ),
                    "joint_velocity_envelope_exact_h1_fallbacks": (
                        joint_velocity_envelope_exact_h1_fallbacks
                    ),
                    "joint_anticipatory_brake_exact_h1_fallbacks": (
                        joint_anticipatory_brake_exact_h1_fallbacks
                    ),
                    "coupled_inverse_mass_brake_exact_h1_fallbacks": (
                        coupled_inverse_mass_brake_exact_h1_fallbacks
                    ),
                    "contact_aware_vertex_exact_h1_fallbacks": (
                        contact_aware_vertex_exact_h1_fallbacks
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
                executed_configuration = None
                execution_torque_audit: list[dict[str, Any]] = []
                execution_envelope_state = None
                execution_brake_state = None
                execution_coupled_brake_state = None
                execution_vertex_state = None
                if (
                    selected_advance_contact_aware_vertex_id is not None
                    or selected_advance_virtual_joint_guard_margin_rad
                    is not None
                ):
                    target_joint = (
                        controller_contact_aware_vertex_target_joint_index
                    )
                    target_side = (
                        controller_contact_aware_vertex_target_joint_side
                    )
                    target_limit = float(
                        limits[
                            target_joint,
                            1 if target_side == "upper" else 0,
                        ]
                    )
                    executed_configuration = (
                        _configure_virtual_joint_guard(
                            env=env,
                            qidx=qidx,
                            vidx=vidx,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            guard_margin_rad=(
                                selected_advance_virtual_joint_guard_margin_rad
                            ),
                            guard_solref=(
                                contact_aware_vertex_beam_virtual_joint_guard_solref
                            ),
                            guard_solimp=(
                                contact_aware_vertex_beam_virtual_joint_guard_solimp
                            ),
                        )
                        if (
                            selected_advance_virtual_joint_guard_margin_rad
                            is not None
                        )
                        else _configure_contact_aware_actuator_vertex_schedule(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            first_vertex_id=(
                                selected_advance_contact_aware_vertex_id
                            ),
                            second_vertex_id=(
                                selected_advance_contact_aware_vertex_schedule_second_id
                            ),
                            switch_substep_index=(
                                selected_advance_contact_aware_vertex_schedule_switch_substep_index
                            ),
                        )
                        if (
                            selected_advance_contact_aware_vertex_schedule_second_id
                            is not None
                        )
                        else _configure_contact_aware_actuator_vertex(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            vertex_id=(
                                selected_advance_contact_aware_vertex_id
                            ),
                        )
                    )
                    contact_aware_vertex_controller_configuration_count += (
                        1
                    )
                    if (
                        selected_advance_contact_aware_vertex_blend_fraction
                        is not None
                    ):
                        executed_configuration["blend_fraction"] = float(
                            selected_advance_contact_aware_vertex_blend_fraction
                        )
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                        or (
                            selected_advance_virtual_joint_guard_margin_rad
                            is not None
                            and not executed_configuration[
                                "configuration_inside_guard_range"
                            ]
                        )
                    ):
                        raise RecedingHorizonPilotError(
                            "executed contact-aware vertex config changed qpos/qvel"
                        )
                    vertex_scope = (
                        _scoped_virtual_joint_guard(
                            env,
                            robot,
                            configuration=executed_configuration,
                        )
                        if (
                            selected_advance_virtual_joint_guard_margin_rad
                            is not None
                        )
                        else _scoped_contact_aware_actuator_vertex_schedule(
                            robot,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            first_vertex_id=(
                                selected_advance_contact_aware_vertex_id
                            ),
                            second_vertex_id=(
                                selected_advance_contact_aware_vertex_schedule_second_id
                            ),
                            switch_substep_index=(
                                selected_advance_contact_aware_vertex_schedule_switch_substep_index
                            ),
                        )
                        if (
                            selected_advance_contact_aware_vertex_schedule_second_id
                            is not None
                        )
                        else _scoped_contact_aware_actuator_vertex_blend(
                            robot,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            vertex_id=(
                                selected_advance_contact_aware_vertex_id
                            ),
                            blend_fraction=(
                                selected_advance_contact_aware_vertex_blend_fraction
                            ),
                        )
                        if (
                            selected_advance_contact_aware_vertex_blend_fraction
                            is not None
                        )
                        else _scoped_contact_aware_actuator_vertex(
                            robot,
                            target_joint_index=target_joint,
                            target_joint_side=target_side,
                            vertex_id=(
                                selected_advance_contact_aware_vertex_id
                            ),
                        )
                    )
                    with vertex_scope as execution_torque_audit:
                        env.step(
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            )
                        )
                    if (
                        selected_advance_virtual_joint_guard_margin_rad
                        is not None
                        and not np.array_equal(
                            np.asarray(
                                env.sim.model.jnt_range[
                                    executed_configuration[
                                        "model_joint_id"
                                    ]
                                ]
                            ),
                            np.asarray(
                                executed_configuration[
                                    "original_joint_range"
                                ]
                            ),
                        )
                    ):
                        raise RecedingHorizonPilotError(
                            "executed virtual joint guard range not restored"
                        )
                    if (
                        selected_advance_virtual_joint_guard_margin_rad
                        is not None
                        and (
                            not np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solref[
                                        executed_configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    executed_configuration[
                                        "original_joint_solref"
                                    ]
                                ),
                            )
                            or not np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solimp[
                                        executed_configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    executed_configuration[
                                        "original_joint_solimp"
                                    ]
                                ),
                            )
                        )
                    ):
                        raise RecedingHorizonPilotError(
                            "executed virtual joint guard profile not restored"
                        )
                    terminal_joint_position = float(
                        env.sim.data.qpos[qidx[target_joint]]
                    )
                    terminal_joint_velocity = float(
                        env.sim.data.qvel[vidx[target_joint]]
                    )
                    if target_side == "upper":
                        terminal_target_margin = (
                            target_limit - terminal_joint_position
                        )
                        terminal_toward_velocity = (
                            terminal_joint_velocity
                        )
                    else:
                        terminal_target_margin = (
                            terminal_joint_position - target_limit
                        )
                        terminal_toward_velocity = (
                            -terminal_joint_velocity
                        )
                    execution_vertex_state = {
                        "target_joint_margin_rad": (
                            terminal_target_margin
                        ),
                        "target_joint_velocity_rad_s": (
                            terminal_joint_velocity
                        ),
                        "toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                        "terminal_non_toward_velocity": bool(
                            terminal_toward_velocity <= 1e-9
                        ),
                    }
                elif (
                    selected_advance_coupled_inverse_mass_brake_fraction
                    is not None
                ):
                    target_joint = (
                        controller_coupled_inverse_mass_brake_target_joint_index
                    )
                    target_side = (
                        controller_coupled_inverse_mass_brake_target_joint_side
                    )
                    executed_configuration = (
                        _configure_coupled_inverse_mass_brake(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            limits=limits,
                            joint_index=target_joint,
                            joint_side=target_side,
                            blend_fraction=(
                                selected_advance_coupled_inverse_mass_brake_fraction
                            ),
                        )
                    )
                    coupled_inverse_mass_brake_controller_configuration_count += (
                        1
                    )
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                    ):
                        raise RecedingHorizonPilotError(
                            "executed coupled-brake config changed qpos/qvel"
                        )
                    with _scoped_coupled_inverse_mass_brake(
                        robot,
                        joint_index=target_joint,
                        joint_side=target_side,
                        blend_fraction=(
                            selected_advance_coupled_inverse_mass_brake_fraction
                        ),
                    ) as execution_torque_audit:
                        env.step(
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            )
                        )
                    terminal_joint_velocity = float(
                        env.sim.data.qvel[vidx[target_joint]]
                    )
                    terminal_toward_velocity = (
                        terminal_joint_velocity
                        if target_side == "upper"
                        else -terminal_joint_velocity
                    )
                    execution_coupled_brake_state = {
                        "target_joint_velocity_rad_s": (
                            terminal_joint_velocity
                        ),
                        "toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                        "terminal_non_toward_velocity": bool(
                            terminal_toward_velocity <= 1e-9
                        ),
                    }
                elif (
                    selected_advance_joint_anticipatory_brake_fraction
                    is not None
                ):
                    target_joint = (
                        controller_joint_anticipatory_brake_target_joint_index
                    )
                    target_side = (
                        controller_joint_anticipatory_brake_target_joint_side
                    )
                    executed_configuration = (
                        _configure_joint_limit_anticipatory_brake(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            limits=limits,
                            joint_index=target_joint,
                            joint_side=target_side,
                            actuator_bound_fraction=(
                                selected_advance_joint_anticipatory_brake_fraction
                            ),
                        )
                    )
                    joint_anticipatory_brake_controller_configuration_count += (
                        1
                    )
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                    ):
                        raise RecedingHorizonPilotError(
                            "executed anticipatory-brake config changed qpos/qvel"
                        )
                    with _scoped_joint_limit_anticipatory_brake(
                        robot,
                        joint_index=target_joint,
                        joint_side=target_side,
                        actuator_bound_fraction=(
                            selected_advance_joint_anticipatory_brake_fraction
                        ),
                    ) as execution_torque_audit:
                        env.step(
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            )
                        )
                    terminal_joint_velocity = float(
                        env.sim.data.qvel[vidx[target_joint]]
                    )
                    terminal_toward_velocity = (
                        terminal_joint_velocity
                        if target_side == "upper"
                        else -terminal_joint_velocity
                    )
                    execution_brake_state = {
                        "target_joint_velocity_rad_s": (
                            terminal_joint_velocity
                        ),
                        "toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                        "terminal_non_toward_velocity": bool(
                            terminal_toward_velocity <= 1e-9
                        ),
                    }
                elif (
                    selected_advance_joint_velocity_envelope_slope
                    is not None
                ):
                    target_joint = (
                        controller_joint_velocity_envelope_target_joint_index
                    )
                    target_side = (
                        controller_joint_velocity_envelope_target_joint_side
                    )
                    target_limit = float(
                        limits[
                            target_joint,
                            1 if target_side == "upper" else 0,
                        ]
                    )
                    executed_configuration = (
                        _configure_joint_limit_velocity_envelope(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            limits=limits,
                            joint_index=target_joint,
                            joint_side=target_side,
                            margin_floor=(
                                selected_advance_minimum_margin_floor
                            ),
                            slope=(
                                selected_advance_joint_velocity_envelope_slope
                            ),
                        )
                    )
                    joint_velocity_envelope_controller_configuration_count += (
                        1
                    )
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                    ):
                        raise RecedingHorizonPilotError(
                            "executed velocity-envelope config changed qpos/qvel"
                        )
                    with _scoped_joint_limit_velocity_envelope(
                        robot,
                        joint_index=target_joint,
                        joint_side=target_side,
                        joint_limit=target_limit,
                        margin_floor=(
                            selected_advance_minimum_margin_floor
                        ),
                        slope=(
                            selected_advance_joint_velocity_envelope_slope
                        ),
                    ) as execution_torque_audit:
                        env.step(
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            )
                        )
                    terminal_joint_position = float(
                        env.sim.data.qpos[qidx[target_joint]]
                    )
                    terminal_joint_velocity = float(
                        env.sim.data.qvel[vidx[target_joint]]
                    )
                    if target_side == "upper":
                        terminal_target_margin = (
                            target_limit - terminal_joint_position
                        )
                        terminal_toward_velocity = (
                            terminal_joint_velocity
                        )
                    else:
                        terminal_target_margin = (
                            terminal_joint_position - target_limit
                        )
                        terminal_toward_velocity = (
                            -terminal_joint_velocity
                        )
                    terminal_allowed_velocity = (
                        selected_advance_joint_velocity_envelope_slope
                        * max(
                            terminal_target_margin
                            - selected_advance_minimum_margin_floor,
                            0.0,
                        )
                    )
                    execution_envelope_state = {
                        "target_joint_margin_rad": (
                            terminal_target_margin
                        ),
                        "target_joint_velocity_rad_s": (
                            terminal_joint_velocity
                        ),
                        "toward_limit_velocity_rad_s": (
                            terminal_toward_velocity
                        ),
                        "allowed_toward_limit_velocity_rad_s": (
                            terminal_allowed_velocity
                        ),
                        "terminal_envelope_satisfied": bool(
                            terminal_toward_velocity
                            <= terminal_allowed_velocity + 1e-9
                        ),
                    }
                elif selected_advance_joint_damping_gain is not None:
                    executed_configuration = (
                        _configure_joint_velocity_damping(
                            env=env,
                            robot=robot,
                            qidx=qidx,
                            vidx=vidx,
                            joint_index=(
                                controller_joint_damping_target_joint_index
                            ),
                            gain=selected_advance_joint_damping_gain,
                        )
                    )
                    joint_damping_controller_configuration_count += 1
                    if (
                        not executed_configuration[
                            "configuration_qpos_identity"
                        ]
                        or not executed_configuration[
                            "configuration_qvel_identity"
                        ]
                    ):
                        raise RecedingHorizonPilotError(
                            "executed damping config changed qpos/qvel"
                        )
                    with _scoped_joint_velocity_damping(
                        robot,
                        joint_index=(
                            controller_joint_damping_target_joint_index
                        ),
                        gain=selected_advance_joint_damping_gain,
                    ) as execution_torque_audit:
                        env.step(
                            np.asarray(
                                selected_prefix[0],
                                dtype=np.float64,
                            )
                        )
                elif selected_advance_nullspace_offset is not None:
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
                    env.step(
                        np.asarray(
                            selected_prefix[0], dtype=np.float64
                        )
                    )
                elif selected_advance_controller_goal_reset:
                    _reset_controller(robot)
                    reset_exact_h1_controller_goal_reset_count += 1
                    env.step(
                        np.asarray(
                            selected_prefix[0], dtype=np.float64
                        )
                    )
                else:
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
                if joint_damping_exact_h1_fallbacks:
                    executed_damping = (
                        joint_damping_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_damping[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_damping["executed_in_shadow"] = True
                    executed_damping[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_damping[
                        "execution_controller_substep_torque_audit"
                    ] = execution_torque_audit
                    executed_damping[
                        "execution_controller_scope_restored"
                    ] = (
                        "run_controller"
                        not in robot.controller.__dict__
                    )
                    executed_damping["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_damping[
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
                    executed_damping[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_damping[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                if joint_velocity_envelope_exact_h1_fallbacks:
                    executed_envelope = (
                        joint_velocity_envelope_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_envelope[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_envelope["executed_in_shadow"] = True
                    executed_envelope[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_envelope[
                        "execution_controller_substep_torque_audit"
                    ] = execution_torque_audit
                    executed_envelope[
                        "execution_controller_scope_restored"
                    ] = (
                        "run_controller"
                        not in robot.controller.__dict__
                    )
                    executed_envelope["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_envelope[
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
                    executed_envelope[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_envelope[
                        "execution_terminal_target_joint_margin_rad"
                    ] = execution_envelope_state[
                        "target_joint_margin_rad"
                    ]
                    executed_envelope[
                        "execution_terminal_target_joint_velocity_rad_s"
                    ] = execution_envelope_state[
                        "target_joint_velocity_rad_s"
                    ]
                    executed_envelope[
                        "execution_terminal_toward_limit_velocity_rad_s"
                    ] = execution_envelope_state[
                        "toward_limit_velocity_rad_s"
                    ]
                    executed_envelope[
                        "execution_terminal_allowed_toward_limit_velocity_rad_s"
                    ] = execution_envelope_state[
                        "allowed_toward_limit_velocity_rad_s"
                    ]
                    executed_envelope[
                        "execution_terminal_envelope_satisfied"
                    ] = execution_envelope_state[
                        "terminal_envelope_satisfied"
                    ]
                    executed_envelope[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                    executed_envelope[
                        "prediction_execution_target_joint_velocity_error_rad_s"
                    ] = abs(
                        execution_envelope_state[
                            "target_joint_velocity_rad_s"
                        ]
                        - executed_candidate[
                            "predicted_terminal_target_joint_velocity_rad_s"
                        ]
                    )
                if joint_anticipatory_brake_exact_h1_fallbacks:
                    executed_brake = (
                        joint_anticipatory_brake_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_brake[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_brake["executed_in_shadow"] = True
                    executed_brake[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_brake[
                        "execution_controller_substep_torque_audit"
                    ] = execution_torque_audit
                    executed_brake[
                        "execution_controller_scope_restored"
                    ] = (
                        "run_controller"
                        not in robot.controller.__dict__
                    )
                    executed_brake["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_brake[
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
                    executed_brake[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_brake[
                        "execution_terminal_target_joint_velocity_rad_s"
                    ] = execution_brake_state[
                        "target_joint_velocity_rad_s"
                    ]
                    executed_brake[
                        "execution_terminal_toward_limit_velocity_rad_s"
                    ] = execution_brake_state[
                        "toward_limit_velocity_rad_s"
                    ]
                    executed_brake[
                        "execution_terminal_non_toward_velocity"
                    ] = execution_brake_state[
                        "terminal_non_toward_velocity"
                    ]
                    executed_brake[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                    executed_brake[
                        "prediction_execution_target_joint_velocity_error_rad_s"
                    ] = abs(
                        execution_brake_state[
                            "target_joint_velocity_rad_s"
                        ]
                        - executed_candidate[
                            "predicted_terminal_target_joint_velocity_rad_s"
                        ]
                    )
                if coupled_inverse_mass_brake_exact_h1_fallbacks:
                    executed_coupled_brake = (
                        coupled_inverse_mass_brake_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_coupled_brake[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_coupled_brake["executed_in_shadow"] = True
                    executed_coupled_brake[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_coupled_brake[
                        "execution_controller_substep_torque_audit"
                    ] = execution_torque_audit
                    executed_coupled_brake[
                        "execution_controller_scope_restored"
                    ] = (
                        "run_controller"
                        not in robot.controller.__dict__
                    )
                    executed_coupled_brake[
                        "exact_action_identity"
                    ] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_coupled_brake[
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
                    executed_coupled_brake[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_coupled_brake[
                        "execution_terminal_target_joint_velocity_rad_s"
                    ] = execution_coupled_brake_state[
                        "target_joint_velocity_rad_s"
                    ]
                    executed_coupled_brake[
                        "execution_terminal_toward_limit_velocity_rad_s"
                    ] = execution_coupled_brake_state[
                        "toward_limit_velocity_rad_s"
                    ]
                    executed_coupled_brake[
                        "execution_terminal_non_toward_velocity"
                    ] = execution_coupled_brake_state[
                        "terminal_non_toward_velocity"
                    ]
                    executed_coupled_brake[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                    executed_coupled_brake[
                        "prediction_execution_target_joint_velocity_error_rad_s"
                    ] = abs(
                        execution_coupled_brake_state[
                            "target_joint_velocity_rad_s"
                        ]
                        - executed_candidate[
                            "predicted_terminal_target_joint_velocity_rad_s"
                        ]
                    )
                if contact_aware_vertex_exact_h1_fallbacks:
                    executed_vertex = (
                        contact_aware_vertex_exact_h1_fallbacks[-1]
                    )
                    executed_candidate = next(
                        candidate
                        for candidate in executed_vertex[
                            "candidate_evaluations"
                        ]
                        if candidate["selected"]
                    )
                    executed_vertex["executed_in_shadow"] = True
                    executed_vertex[
                        "execution_configuration"
                    ] = executed_configuration
                    executed_vertex[
                        "execution_controller_substep_torque_audit"
                    ] = execution_torque_audit
                    executed_vertex[
                        "execution_controller_scope_restored"
                    ] = (
                        "run_controller"
                        not in robot.controller.__dict__
                        and (
                            "model_joint_id"
                            not in executed_configuration
                            or np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_range[
                                        executed_configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    executed_configuration[
                                        "original_joint_range"
                                    ]
                                ),
                            )
                            and np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solref[
                                        executed_configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    executed_configuration[
                                        "original_joint_solref"
                                    ]
                                ),
                            )
                            and np.array_equal(
                                np.asarray(
                                    env.sim.model.jnt_solimp[
                                        executed_configuration[
                                            "model_joint_id"
                                        ]
                                    ]
                                ),
                                np.asarray(
                                    executed_configuration[
                                        "original_joint_solimp"
                                    ]
                                ),
                            )
                        )
                    )
                    executed_vertex["exact_action_identity"] = bool(
                        np.array_equal(
                            np.asarray(
                                executed_vertex[
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
                    executed_vertex[
                        "execution_terminal_margin_rad"
                    ] = advanced_margin
                    executed_vertex[
                        "execution_terminal_target_joint_margin_rad"
                    ] = execution_vertex_state[
                        "target_joint_margin_rad"
                    ]
                    executed_vertex[
                        "execution_terminal_target_joint_velocity_rad_s"
                    ] = execution_vertex_state[
                        "target_joint_velocity_rad_s"
                    ]
                    executed_vertex[
                        "execution_terminal_toward_limit_velocity_rad_s"
                    ] = execution_vertex_state[
                        "toward_limit_velocity_rad_s"
                    ]
                    executed_vertex[
                        "execution_terminal_non_toward_velocity"
                    ] = execution_vertex_state[
                        "terminal_non_toward_velocity"
                    ]
                    executed_vertex[
                        "prediction_execution_margin_error_rad"
                    ] = abs(
                        advanced_margin
                        - executed_candidate[
                            "predicted_terminal_margin_rad"
                        ]
                    )
                    executed_vertex[
                        "prediction_execution_target_joint_velocity_error_rad_s"
                    ] = abs(
                        execution_vertex_state[
                            "target_joint_velocity_rad_s"
                        ]
                        - executed_candidate[
                            "predicted_terminal_target_joint_velocity_rad_s"
                        ]
                    )
                if advanced_margin < (
                    selected_advance_minimum_margin_floor
                ) or (
                    execution_envelope_state is not None
                    and not execution_envelope_state[
                        "terminal_envelope_satisfied"
                    ]
                ) or (
                    execution_brake_state is not None
                    and not execution_brake_state[
                        "terminal_non_toward_velocity"
                    ]
                ) or (
                    execution_coupled_brake_state is not None
                    and not execution_coupled_brake_state[
                        "terminal_non_toward_velocity"
                    ]
                ) or (
                    execution_vertex_state is not None
                    and contact_aware_vertex_require_terminal_non_toward_velocity
                    and not execution_vertex_state[
                        "terminal_non_toward_velocity"
                    ]
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
            "controller_joint_damping_exact_h1_gains": list(
                controller_joint_damping_exact_h1_gains
            ),
            "controller_joint_damping_target_joint_index": (
                controller_joint_damping_target_joint_index
            ),
            "controller_joint_velocity_envelope_exact_h1_slopes": list(
                controller_joint_velocity_envelope_exact_h1_slopes
            ),
            "controller_joint_velocity_envelope_target_joint_index": (
                controller_joint_velocity_envelope_target_joint_index
            ),
            "controller_joint_velocity_envelope_target_joint_side": (
                controller_joint_velocity_envelope_target_joint_side
            ),
            "controller_joint_anticipatory_brake_exact_h1_fractions": list(
                controller_joint_anticipatory_brake_exact_h1_fractions
            ),
            "controller_joint_anticipatory_brake_target_joint_index": (
                controller_joint_anticipatory_brake_target_joint_index
            ),
            "controller_joint_anticipatory_brake_target_joint_side": (
                controller_joint_anticipatory_brake_target_joint_side
            ),
            "controller_coupled_inverse_mass_brake_exact_h1_fractions": list(
                controller_coupled_inverse_mass_brake_exact_h1_fractions
            ),
            "controller_coupled_inverse_mass_brake_target_joint_index": (
                controller_coupled_inverse_mass_brake_target_joint_index
            ),
            "controller_coupled_inverse_mass_brake_target_joint_side": (
                controller_coupled_inverse_mass_brake_target_joint_side
            ),
            "controller_contact_aware_vertex_exact_h1_ids": list(
                controller_contact_aware_vertex_exact_h1_ids
            ),
            "controller_contact_aware_vertex_target_joint_index": (
                controller_contact_aware_vertex_target_joint_index
            ),
            "controller_contact_aware_vertex_target_joint_side": (
                controller_contact_aware_vertex_target_joint_side
            ),
            "contact_aware_vertex_require_terminal_non_toward_velocity": (
                contact_aware_vertex_require_terminal_non_toward_velocity
            ),
            "contact_aware_vertex_require_safe_successor": (
                contact_aware_vertex_require_safe_successor
            ),
            "contact_aware_vertex_beam_width": (
                contact_aware_vertex_beam_width
            ),
            "contact_aware_vertex_beam_max_horizon": (
                contact_aware_vertex_beam_max_horizon
            ),
            "contact_aware_vertex_beam_blend_fractions": list(
                contact_aware_vertex_beam_blend_fractions
            ),
            "contact_aware_vertex_beam_vertex_schedules": [
                list(schedule)
                for schedule in (
                    contact_aware_vertex_beam_vertex_schedules
                )
            ],
            "contact_aware_vertex_beam_schedule_switch_substep_index": (
                contact_aware_vertex_beam_schedule_switch_substep_index
                if contact_aware_vertex_beam_vertex_schedules
                else None
            ),
            "contact_aware_vertex_beam_virtual_joint_guard_margins_rad": list(
                contact_aware_vertex_beam_virtual_joint_guard_margins_rad
            ),
            "contact_aware_vertex_beam_virtual_joint_guard_solref": (
                list(
                    contact_aware_vertex_beam_virtual_joint_guard_solref
                )
                if contact_aware_vertex_beam_virtual_joint_guard_solref
                is not None
                else None
            ),
            "contact_aware_vertex_beam_virtual_joint_guard_solimp": (
                list(
                    contact_aware_vertex_beam_virtual_joint_guard_solimp
                )
                if contact_aware_vertex_beam_virtual_joint_guard_solimp
                is not None
                else None
            ),
            "contact_aware_vertex_beam_retention_strategy": (
                contact_aware_vertex_beam_retention_strategy
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
            "joint_damping_exact_h1_shadow_env_step_count": (
                joint_damping_exact_h1_shadow_steps
            ),
            "joint_damping_controller_configuration_count": (
                joint_damping_controller_configuration_count
            ),
            "joint_velocity_envelope_exact_h1_shadow_env_step_count": (
                joint_velocity_envelope_exact_h1_shadow_steps
            ),
            "joint_velocity_envelope_controller_configuration_count": (
                joint_velocity_envelope_controller_configuration_count
            ),
            "joint_anticipatory_brake_exact_h1_shadow_env_step_count": (
                joint_anticipatory_brake_exact_h1_shadow_steps
            ),
            "joint_anticipatory_brake_controller_configuration_count": (
                joint_anticipatory_brake_controller_configuration_count
            ),
            "coupled_inverse_mass_brake_exact_h1_shadow_env_step_count": (
                coupled_inverse_mass_brake_exact_h1_shadow_steps
            ),
            "coupled_inverse_mass_brake_controller_configuration_count": (
                coupled_inverse_mass_brake_controller_configuration_count
            ),
            "contact_aware_vertex_exact_h1_shadow_env_step_count": (
                contact_aware_vertex_exact_h1_shadow_steps
            ),
            "contact_aware_vertex_controller_configuration_count": (
                contact_aware_vertex_controller_configuration_count
            ),
            "contact_aware_vertex_successor_shadow_env_step_count": (
                contact_aware_vertex_successor_shadow_steps
            ),
            "contact_aware_vertex_beam_shadow_env_step_count": (
                contact_aware_vertex_beam_shadow_steps
            ),
            "contact_aware_vertex_beam_screen_count": (
                contact_aware_vertex_beam_screen_count
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
