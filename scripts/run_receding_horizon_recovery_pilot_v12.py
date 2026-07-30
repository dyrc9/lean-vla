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
    row_schema: str = ROW_SCHEMA,
    source_version: str = "v12.11",
) -> dict[str, Any]:
    if (
        replan_attempts_per_cycle <= 0
        or seed_attempt_stride <= 0
        or maximum_recovery_escalations_per_cycle < 0
        or recovery_round_seed_stride <= 0
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
        policy_advance_steps = 0
        for lane_index, base_seed in enumerate(LANE_BASE_SEEDS):
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
                selected_prefix = None
                for recovery_round in range(
                    maximum_recovery_escalations_per_cycle + 1
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
                            prefix=prefix[:1],
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
                            "one_step_minimum_margin_rad": (
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
                if advanced_margin <= float(
                    config["episode"]["trigger_margin_rad"]
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
