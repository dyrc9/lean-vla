#!/usr/bin/env python3
"""Successor runner for source-grounded L2 execution-attack experiments.

The frozen OpenPI/LIBERO runner is imported rather than edited so historical
source bindings and the active M2 path remain byte-identical.  This successor
injects an attack at the v4 dispatch boundary (semantic runtime) or at an
environment proxy (VLA-only), then appends a separate privileged attack audit
to each episode artifact.
"""

from __future__ import annotations

import argparse
import collections
from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter, time_ns
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.execution_attack_relay import (  # noqa: E402
    AttackPlacement,
    PostBoundaryAffineAttackSink,
    PublishedAffineFamily,
    PublishedAffineRelay,
    build_published_affine_relay,
)
from proofalign.benchmark.l2_online_arm_runtime import (  # noqa: E402
    ExecutionOnlyPrefixAuthorization,
    ExecutionOnlyPrefixDispatchBoundary,
    ExecutionOnlyPrefixSession,
    ExecutionOnlyStepReceipt,
    L2DisabledPrefixDispatchBoundary,
    execution_only_authorization_audit,
    execution_only_receipt_audit,
)
from proofalign.integrity_v4_runtime import (  # noqa: E402
    SingleUsePrefixDispatchBoundary,
    TransactionVerdict,
)
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402


_BASE_RUN_EPISODE = base.run_episode
_BASE_PARSE_ARGS = base.parse_args
_BASE_COPY_SELF = base.copy_self


class _AttackedEnvironmentProxy:
    """Apply the attack after the base runner's common action clipping."""

    def __init__(
        self,
        env: Any,
        relay: PublishedAffineRelay,
        *,
        wait_steps: int,
    ) -> None:
        self._env = env
        self._relay = relay
        self._wait_steps = wait_steps
        self._call_index = 0

    def step(self, action: list[float]) -> Any:
        runner_step_id = self._call_index
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return self._env.step(action)
        env_input = self._relay.transform(
            action,
            runner_step_id=runner_step_id,
        )
        transition = self._env.step(list(env_input))
        reported = (
            action
            if self._relay.placement
            is AttackPlacement.POST_BOUNDARY_FORGED
            else env_input
        )
        self._relay.mark_dispatch_result(
            env_step_reached=True,
            reported_action=reported,
        )
        return transition

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)


def _attack_boundary_class(
    relay: PublishedAffineRelay,
    *,
    first_policy_step_id: int,
    boundary_class: type = SingleUsePrefixDispatchBoundary,
) -> type:
    """Create an episode-local boundary without mutating the frozen source."""

    class L2AttackDispatchBoundary(boundary_class):
        def __init__(self, sink: Any) -> None:
            if relay.placement is not AttackPlacement.PRE_BOUNDARY:
                sink = PostBoundaryAffineAttackSink(
                    inner=sink,
                    relay=relay,
                    report_forged_nominal=(
                        relay.placement
                        is AttackPlacement.POST_BOUNDARY_FORGED
                    ),
                )
            super().__init__(sink)

        def dispatch_next(
            self,
            session: Any,
            action: tuple[float, ...],
            *,
            now_ns: int,
        ) -> Any:
            if relay.placement is not AttackPlacement.PRE_BOUNDARY:
                relay.bind_runner_step(
                    first_policy_step_id + len(relay.records)
                )
                return super().dispatch_next(
                    session,
                    action,
                    now_ns=now_ns,
                )
            attacked = relay.transform(
                action,
                runner_step_id=(
                    first_policy_step_id + len(relay.records)
                ),
            )
            result = super().dispatch_next(
                session,
                attacked,
                now_ns=now_ns,
            )
            relay.mark_dispatch_result(
                env_step_reached=result.transition is not None,
                reported_action=(
                    None
                    if result.receipt is None
                    else result.receipt.applied_action
                ),
            )
            return result

    return L2AttackDispatchBoundary


def _annotate_payload(
    payload: dict[str, Any],
    relay: PublishedAffineRelay | None,
    *,
    l1_enabled: bool,
    l2_enabled: bool,
) -> dict[str, Any]:
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": "proofalign_l2_execution_attack_successor_v1",
            "frozen_base_runner_modified": False,
            "execution_attack_family": (
                PublishedAffineFamily.NONE.value
                if relay is None
                else relay.scenario.family.value
            ),
            "execution_attack_placement": (
                None if relay is None else relay.placement.value
            ),
            "execution_attack_fidelity": (
                None
                if relay is None
                else "source_command_operator_transfer"
            ),
            "perfect_undetectability_claim_eligible": False,
            "measured_execution_value": "env.step input",
            "l1_semantic_alignment": l1_enabled,
            "l2_execution_integrity": l2_enabled,
            "four_arm_label": (
                "dual"
                if l1_enabled and l2_enabled
                else "semantic_only"
                if l1_enabled
                else "execution_only"
                if l2_enabled
                else "vla_only"
            ),
        }
    )
    payload["metadata"] = metadata
    payload["execution_attack_audit"] = (
        None if relay is None else relay.audit_payload()
    )

    if relay is not None:
        records_by_step = {
            record["runner_step_id"]: record
            for record in relay.records
            if record["env_step_reached"]
        }
        for row in payload.get("trace", []):
            record = records_by_step.get(row.get("step_id"))
            if record is not None:
                row["execution_attack"] = record

        if (
            relay.placement
            is AttackPlacement.POST_BOUNDARY_TRUTHFUL
            and payload.get("decision") == "env_done"
            and any(
                transaction.get("dispatch_status") == "rejected"
                for frame in payload.get(
                    "observation_frame_audits", ()
                )
                for transaction in (
                    frame.get("semantic_transaction") or {},
                )
            )
        ):
            # The frozen base runner gives terminal ``done`` precedence over a
            # same-step execution rejection.  The successor security decision
            # must preserve the rejection without rewriting historical code.
            payload["decision"] = "semantic_execution_rejected"
            payload["success_by_done"] = False
    return payload


@dataclass
class _ExecutionOnlyTransaction:
    authorization: ExecutionOnlyPrefixAuthorization
    boundary: ExecutionOnlyPrefixDispatchBoundary
    session: ExecutionOnlyPrefixSession
    frame_audit_index: int
    initial_observation_digest: str
    observation_digests: list[str] = field(default_factory=list)
    violation_atoms: list[str] = field(default_factory=list)


def _update_execution_only_transaction_audit(
    frame_audits: list[dict[str, Any]],
    transaction: _ExecutionOnlyTransaction,
    *,
    dispatch_status: str,
    integrity_verdict: TransactionVerdict | None = None,
    issues: tuple[str, ...] = (),
) -> None:
    frame = frame_audits[transaction.frame_audit_index]
    frame_audits[transaction.frame_audit_index] = {
        **frame,
        "execution_only_transaction": {
            "authorization": execution_only_authorization_audit(
                transaction.authorization
            ),
            "dispatch_status": dispatch_status,
            "dispatch_issues": issues,
            "step_receipts": [
                execution_only_receipt_audit(receipt)
                for receipt in transaction.session.receipts
            ],
            "prefix_complete": transaction.session.complete,
            "initial_observation_digest": (
                transaction.initial_observation_digest
            ),
            "observation_digests": tuple(
                transaction.observation_digests
            ),
            "observed_violation_atoms": tuple(
                dict.fromkeys(transaction.violation_atoms)
            ),
            "integrity_verdict": (
                None
                if integrity_verdict is None
                else integrity_verdict.value
            ),
            "integrity_issues": issues,
            "observer_scope": (
                "exact_raw_policy_prefix_and_generic_libero_violations"
            ),
            "semantic_effect_claim": None,
        },
    }


def _finalize_execution_only_transaction(
    frame_audits: list[dict[str, Any]],
    transaction: _ExecutionOnlyTransaction,
    *,
    dispatch_issues: tuple[str, ...] = (),
) -> tuple[TransactionVerdict, tuple[str, ...]]:
    if dispatch_issues:
        verdict = TransactionVerdict.REJECT
        issues = dispatch_issues
        status = "rejected"
    else:
        evaluation = transaction.boundary.seal(
            transaction.session,
            effects_known=True,
            observed_violation_atoms=transaction.violation_atoms,
        )
        verdict = evaluation.verdict
        issues = evaluation.issues
        status = (
            "complete"
            if verdict is TransactionVerdict.ALLOW
            else "rejected"
        )
    _update_execution_only_transaction_audit(
        frame_audits,
        transaction,
        dispatch_status=status,
        integrity_verdict=verdict,
        issues=issues,
    )
    return verdict, issues


def _run_execution_only_episode(
    *,
    relay: PublishedAffineRelay | None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run L2 over a raw policy ActionBlock without making an L1 claim."""

    args = kwargs["args"]
    policy = kwargs["policy"]
    jax = kwargs["jax"]
    policy_seed = int(kwargs["policy_seed"])
    image_tools = kwargs["image_tools"]
    suite = kwargs["suite"]
    task_id = int(kwargs["task_id"])
    init_state_id = int(kwargs["init_state_id"])
    attack_records = kwargs["attack_records"]
    output_dir = kwargs["output_dir"]
    observation_transform = kwargs.get("observation_transform")
    wrist_observation_transform = kwargs.get(
        "wrist_observation_transform"
    )
    constraint_signal_extractor = kwargs.get(
        "constraint_signal_extractor"
    )

    base.set_policy_seed(policy, jax, policy_seed)
    trusted_runtime = base.load_libero_task_runtime(
        benchmark_name=suite,
        task_id=task_id,
        init_state_id=init_state_id,
        bddl_file=None,
    )
    runtime = base.apply_attack_record(
        trusted_runtime,
        base.get_attack_record(
            attack_records,
            suite=suite,
            task_id=task_id,
            init_state_id=init_state_id,
        ),
    )
    env = base.create_env(runtime, args)
    trace: list[dict[str, Any]] = []
    replay_images: list[np.ndarray] = []
    frame_audits: list[dict[str, Any]] = []
    action_plan: collections.deque[Any] = collections.deque()
    active_transaction: _ExecutionOnlyTransaction | None = None
    episode_start = perf_counter()
    success_by_done = False
    stop_reason = "max_steps"
    obs = None
    execution_sink: Any = base.AuthorizedLiberoActionSink(env)
    if (
        relay is not None
        and relay.placement is not AttackPlacement.PRE_BOUNDARY
    ):
        execution_sink = PostBoundaryAffineAttackSink(
            inner=execution_sink,
            relay=relay,
            report_forged_nominal=(
                relay.placement
                is AttackPlacement.POST_BOUNDARY_FORGED
            ),
        )
    execution_boundary = ExecutionOnlyPrefixDispatchBoundary(
        execution_sink
    )

    try:
        env.reset()
        if runtime.init_state is not None and hasattr(
            env, "set_init_state"
        ):
            obs = env.set_init_state(runtime.init_state)
        if obs is None:
            obs = base.get_observation(env)

        np.random.seed(args.seed)
        for step_id in range(args.max_steps + args.num_steps_wait):
            if step_id < args.num_steps_wait:
                env_start = perf_counter()
                obs, reward, done, info = base.normalize_env_step(
                    env.step(base.LIBERO_DUMMY_ACTION)
                )
                env_time = perf_counter() - env_start
                trace.append(
                    base.make_trace_record(
                        step_id,
                        "wait",
                        base.LIBERO_DUMMY_ACTION,
                        reward,
                        done,
                        info,
                        0.0,
                        env_time,
                    )
                )
                if done:
                    success_by_done = True
                    stop_reason = "done_during_wait"
                    break
                continue

            started_policy_call = not action_plan
            if started_policy_call:
                proposal_index = len(frame_audits)
                element, replay_image, frame_audit = (
                    base.prepare_openpi_element(
                        obs,
                        runtime.instruction,
                        image_tools,
                        args.resize_size,
                        observation_transform=observation_transform,
                        wrist_observation_transform=(
                            wrist_observation_transform
                        ),
                    )
                )
                replay_images.append(replay_image)
                frame_audit = {
                    **frame_audit,
                    "policy_call_index": proposal_index,
                    "exact_policy_prompt_digest": base.digest_text(
                        runtime.instruction
                    ),
                }
                frame_audits.append(frame_audit)
                policy_start = perf_counter()
                action_chunk = np.asarray(
                    policy.infer(element)["actions"]
                )
                policy_time = perf_counter() - policy_start
                if len(action_chunk) < args.replan_steps:
                    raise RuntimeError(
                        f"Policy returned {len(action_chunk)} actions, "
                        "fewer than "
                        f"replan_steps={args.replan_steps}."
                    )
                if action_chunk.ndim != 2:
                    raise RuntimeError(
                        "Execution-only L2 requires a rank-2 ActionBlock"
                    )
                chunk_digest = base.array_digest(action_chunk)
                if chunk_digest is None:  # pragma: no cover
                    raise RuntimeError(
                        "Policy action chunk lacks a digest"
                    )
                frame_audits[-1] = {
                    **frame_audits[-1],
                    "policy_action_chunk_sha256": chunk_digest,
                    "policy_action_chunk_shape": list(
                        action_chunk.shape
                    ),
                    "policy_action_chunk_dtype": str(action_chunk.dtype),
                }
                executable_chunk = action_chunk[: args.replan_steps]
                clipped_chunk = np.clip(
                    executable_chunk, -1.0, 1.0
                ).astype(np.float64)
                issued_at_ns = time_ns()
                authorization = ExecutionOnlyPrefixAuthorization(
                    episode_nonce=(
                        f"{suite}:task{task_id}:init{init_state_id}:"
                        f"pseed{policy_seed}"
                    ),
                    proposal_index=proposal_index,
                    source_policy_chunk_digest=chunk_digest,
                    policy_observation_digest=(
                        base.openpi_policy_observation_digest(element)
                    ),
                    actions=tuple(
                        tuple(float(value) for value in action)
                        for action in clipped_chunk
                    ),
                    issued_at_ns=issued_at_ns,
                    valid_until_ns=(
                        issued_at_ns
                        + int(
                            getattr(
                                args,
                                "semantic_authorization_ttl_ns",
                                60_000_000_000,
                            )
                        )
                    ),
                )
                opened = execution_boundary.open(
                    authorization,
                    now_ns=issued_at_ns,
                )
                if (
                    opened.verdict is not TransactionVerdict.ALLOW
                    or opened.session is None
                ):
                    frame_audits[-1] = {
                        **frame_audits[-1],
                        "execution_only_transaction": {
                            "authorization": (
                                execution_only_authorization_audit(
                                    authorization
                                )
                            ),
                            "dispatch_status": "authorization_rejected",
                            "dispatch_issues": opened.issues,
                            "step_receipts": [],
                            "integrity_verdict": (
                                TransactionVerdict.REJECT.value
                            ),
                        },
                    }
                    stop_reason = "execution_authorization_rejected"
                    break
                active_transaction = _ExecutionOnlyTransaction(
                    authorization=authorization,
                    boundary=execution_boundary,
                    session=opened.session,
                    frame_audit_index=proposal_index,
                    initial_observation_digest=(
                        base.libero_execution_observation_digest(obs)
                    ),
                )
                _update_execution_only_transaction_audit(
                    frame_audits,
                    active_transaction,
                    dispatch_status="open",
                )
                action_plan.extend(executable_chunk)
            else:
                policy_time = 0.0

            assert active_transaction is not None
            raw_action = np.asarray(
                action_plan.popleft(), dtype=np.float64
            )
            nominal_action = tuple(
                float(value)
                for value in np.clip(raw_action, -1.0, 1.0)
            )
            candidate_action = nominal_action
            if (
                relay is not None
                and relay.placement is AttackPlacement.PRE_BOUNDARY
            ):
                candidate_action = relay.transform(
                    nominal_action,
                    runner_step_id=step_id,
                )
            elif relay is not None:
                relay.bind_runner_step(step_id)

            env_start = perf_counter()
            dispatched = active_transaction.boundary.dispatch_next(
                active_transaction.session,
                candidate_action,
                now_ns=time_ns(),
            )
            env_time = perf_counter() - env_start
            if (
                relay is not None
                and relay.placement is AttackPlacement.PRE_BOUNDARY
            ):
                relay.mark_dispatch_result(
                    env_step_reached=dispatched.transition is not None,
                    reported_action=(
                        None
                        if dispatched.receipt is None
                        else dispatched.receipt.reported_action
                    ),
                )
            if dispatched.transition is None:
                _finalize_execution_only_transaction(
                    frame_audits,
                    active_transaction,
                    dispatch_issues=dispatched.issues,
                )
                active_transaction = None
                action_plan.clear()
                stop_reason = "execution_dispatch_rejected"
                break

            obs, reward, done, info = dispatched.transition
            receipt: ExecutionOnlyStepReceipt | None = (
                dispatched.receipt
            )
            if receipt is None:  # pragma: no cover - sink contract.
                raise RuntimeError(
                    "Execution-only dispatch reached env without a receipt"
                )
            action = np.asarray(
                receipt.reported_action, dtype=np.float64
            )
            constraint_signals = (
                constraint_signal_extractor(env, raw_action, action)
                if constraint_signal_extractor is not None
                else None
            )
            trace_record = base.make_trace_record(
                step_id,
                "policy",
                action,
                reward,
                done,
                info,
                policy_time,
                env_time,
                policy_call=(
                    frame_audits[-1]
                    if started_policy_call
                    else None
                ),
                raw_action=raw_action,
                constraint_signals=constraint_signals,
            )
            trace_record["execution_dispatch_receipt"] = (
                execution_only_receipt_audit(receipt)
            )
            trace.append(trace_record)
            active_transaction.observation_digests.append(
                base.libero_execution_observation_digest(obs)
            )
            active_transaction.violation_atoms.extend(
                base.libero_violation_atoms(info)
            )
            constraint_violation = base.has_cost_or_collision(
                [trace[-1]]
            )
            evaluation = None
            if (
                active_transaction.session.complete
                or done
                or constraint_violation
                or dispatched.verdict
                is not TransactionVerdict.ALLOW
            ):
                evaluation = _finalize_execution_only_transaction(
                    frame_audits,
                    active_transaction,
                    dispatch_issues=(
                        dispatched.issues
                        if dispatched.verdict
                        is not TransactionVerdict.ALLOW
                        else ()
                    ),
                )
                if not active_transaction.session.complete:
                    action_plan.clear()
                active_transaction = None

            if dispatched.verdict is not TransactionVerdict.ALLOW:
                stop_reason = "execution_dispatch_rejected"
                break
            if (
                evaluation is not None
                and evaluation[0] is not TransactionVerdict.ALLOW
            ):
                stop_reason = (
                    "execution_integrity_unknown"
                    if evaluation[0] is TransactionVerdict.UNKNOWN
                    else "execution_integrity_rejected"
                )
                break
            if done:
                success_by_done = True
                stop_reason = "env_done"
                break
            if constraint_violation:
                stop_reason = "constraint_violation"
                break

        if active_transaction is not None:
            incomplete = _finalize_execution_only_transaction(
                frame_audits,
                active_transaction,
            )
            active_transaction = None
            action_plan.clear()
            if stop_reason == "max_steps":
                stop_reason = (
                    "execution_prefix_incomplete"
                    if incomplete[0] is TransactionVerdict.REJECT
                    else "execution_integrity_unknown"
                )

        task_success = base.check_task_success(env)
        unsafe = base.has_cost_or_collision(trace)
        strict_success = bool(task_success) and not unsafe
        payload = {
            "metadata": {
                **runtime.metadata,
                "method": "pi05_openpi",
                "checkpoint": str(args.checkpoint_dir),
                "openpi_config": args.openpi_config,
                "max_steps": args.max_steps,
                "num_steps_wait": args.num_steps_wait,
                "env_img_res": args.env_img_res,
                "resize_size": args.resize_size,
                "replan_steps": args.replan_steps,
                "sample_steps": args.sample_steps,
                "seed": args.seed,
                "policy_seed": policy_seed,
                "paper_track": (
                    "Embodied Physical Safety Track"
                    if suite in base.PHYSICAL_SUITES
                    else "Semantic/extra suite rollout"
                ),
                "initial_state_sha256": base.array_digest(
                    runtime.init_state
                ),
                "observation_attack_type": "none",
                "observation_attack_strength": None,
                "semantic_runtime_enabled": False,
                "semantic_policy_mode": None,
                "semantic_geometry_source": None,
                "semantic_deployment_attestation": False,
                "execution_authorization_basis": (
                    "raw_policy_source_action_chunk"
                ),
            },
            "task_success": bool(task_success),
            "strict_success_no_cost": strict_success,
            "success_by_done": success_by_done,
            "unsafe_cost_or_collision": unsafe,
            "decision": stop_reason,
            "trace": trace,
            "observation_frame_audits": frame_audits,
            "semantic_events": [],
            "execution_only_transactions": [
                frame["execution_only_transaction"]
                for frame in frame_audits
                if "execution_only_transaction" in frame
            ],
            "runtime": {
                "episode_wall_time_seconds": (
                    perf_counter() - episode_start
                )
            },
        }
        seed_suffix = (
            f"_pseed{policy_seed}"
            if getattr(args, "_multiple_policy_seeds", False)
            else ""
        )
        episode_path = (
            output_dir
            / "episodes"
            / (
                f"{suite}_task{task_id}_init{init_state_id}"
                f"{seed_suffix}.json"
            )
        )
        if args.save_video and replay_images:
            base.save_video(
                output_dir,
                runtime,
                task_id,
                init_state_id,
                strict_success,
                replay_images,
            )
        return {**payload, "_path": str(episode_path)}
    finally:
        if hasattr(env, "close"):
            env.close()


def _persist_annotated_episode(payload: dict[str, Any]) -> None:
    path_text = payload.get("_path")
    if not path_text:
        return
    serializable = {
        key: value for key, value in payload.items() if key != "_path"
    }
    Path(path_text).write_text(
        json.dumps(serializable, indent=2, default=base.json_default),
        encoding="utf-8",
    )


def _arm_switches(args: argparse.Namespace) -> tuple[bool, bool]:
    has_l1 = hasattr(args, "l1_semantic_alignment")
    has_l2 = hasattr(args, "l2_execution_integrity")
    if has_l1 != has_l2:
        raise ValueError(
            "L1 and L2 arm switches must be supplied together"
        )
    if not has_l1:
        enabled = bool(getattr(args, "semantic_runtime", False))
        return enabled, enabled
    l1_value = args.l1_semantic_alignment
    l2_value = args.l2_execution_integrity
    if l1_value not in {"on", "off"} or l2_value not in {
        "on",
        "off",
    }:
        raise ValueError("L1 and L2 arm switches must be on or off")
    l1_enabled = l1_value == "on"
    if bool(getattr(args, "semantic_runtime", False)) != l1_enabled:
        raise ValueError(
            "semantic_runtime must equal the L1 semantic-alignment switch"
        )
    return l1_enabled, l2_value == "on"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one base episode through an episode-local L2 attack boundary."""

    args = kwargs["args"]
    l1_enabled, l2_enabled = _arm_switches(args)
    relay = build_published_affine_relay(
        family=getattr(
            args,
            "execution_attack_family",
            PublishedAffineFamily.NONE.value,
        ),
        placement=getattr(
            args,
            "execution_attack_placement",
            AttackPlacement.PRE_BOUNDARY.value,
        ),
    )
    if not l1_enabled and l2_enabled:
        payload = _run_execution_only_episode(
            relay=relay,
            **kwargs,
        )
        _annotate_payload(
            payload,
            relay,
            l1_enabled=l1_enabled,
            l2_enabled=l2_enabled,
        )
        _persist_annotated_episode(payload)
        return payload

    original_boundary = base.SingleUsePrefixDispatchBoundary
    original_create_env = base.create_env
    if l1_enabled:
        boundary_class = (
            SingleUsePrefixDispatchBoundary
            if l2_enabled
            else L2DisabledPrefixDispatchBoundary
        )
        base.SingleUsePrefixDispatchBoundary = (
            boundary_class
            if relay is None
            else _attack_boundary_class(
                relay,
                first_policy_step_id=int(args.num_steps_wait),
                boundary_class=boundary_class,
            )
        )
    elif relay is not None:
        def attacked_create_env(*create_args: Any, **create_kwargs: Any) -> Any:
            return _AttackedEnvironmentProxy(
                original_create_env(*create_args, **create_kwargs),
                relay,
                wait_steps=int(args.num_steps_wait),
            )

        base.create_env = attacked_create_env
    try:
        payload = _BASE_RUN_EPISODE(**kwargs)
    finally:
        base.SingleUsePrefixDispatchBoundary = original_boundary
        base.create_env = original_create_env

    _annotate_payload(
        payload,
        relay,
        l1_enabled=l1_enabled,
        l2_enabled=l2_enabled,
    )
    _persist_annotated_episode(payload)
    return payload


def parse_args() -> argparse.Namespace:
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(
            "L2 successor options:\n"
            "  --execution-attack-family "
            "{none,ueda_blevins_scaling,ueda_blevins_reflection,"
            "ueda_blevins_shear}\n"
            "  --execution-attack-placement "
            "{pre_boundary,post_boundary_truthful,"
            "post_boundary_forged}\n"
            "  --l1-semantic-alignment {on,off}\n"
            "  --l2-execution-integrity {on,off}\n"
        )
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--execution-attack-family",
        choices=[family.value for family in PublishedAffineFamily],
        default=PublishedAffineFamily.NONE.value,
    )
    parser.add_argument(
        "--execution-attack-placement",
        choices=[placement.value for placement in AttackPlacement],
        default=AttackPlacement.PRE_BOUNDARY.value,
    )
    parser.add_argument(
        "--l1-semantic-alignment",
        choices=("on", "off"),
        default=None,
    )
    parser.add_argument(
        "--l2-execution-integrity",
        choices=("on", "off"),
        default=None,
    )
    l2_args, remaining = parser.parse_known_args()
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *remaining]
        args = _BASE_PARSE_ARGS()
    finally:
        sys.argv = original_argv
    args.execution_attack_family = l2_args.execution_attack_family
    args.execution_attack_placement = l2_args.execution_attack_placement
    switches = (
        l2_args.l1_semantic_alignment,
        l2_args.l2_execution_integrity,
    )
    if (switches[0] is None) != (switches[1] is None):
        parser.error(
            "both --l1-semantic-alignment and "
            "--l2-execution-integrity are required together"
        )
    if switches[0] is None:
        enabled = bool(args.semantic_runtime)
        args.l1_semantic_alignment = "on" if enabled else "off"
        args.l2_execution_integrity = "on" if enabled else "off"
        return args
    requested_semantic_runtime = switches[0] == "on"
    if bool(args.semantic_runtime) and not requested_semantic_runtime:
        parser.error(
            "--semantic-runtime conflicts with explicit L1-off switches"
        )
    args.semantic_runtime = requested_semantic_runtime
    args.l1_semantic_alignment = switches[0]
    args.l2_execution_integrity = switches[1]
    return args


def copy_self(output_dir: Path) -> None:
    _BASE_COPY_SELF(output_dir)
    shutil.copy2(Path(__file__), output_dir / Path(__file__).name)
    adapter = (
        REPO_ROOT
        / "src"
        / "proofalign"
        / "benchmark"
        / "l2_online_arm_runtime.py"
    )
    shutil.copy2(adapter, output_dir / adapter.name)


def main() -> None:
    original_parse_args = base.parse_args
    original_run_episode = base.run_episode
    original_copy_self = base.copy_self
    base.parse_args = parse_args
    base.run_episode = run_episode
    base.copy_self = copy_self
    try:
        base.main()
    finally:
        base.parse_args = original_parse_args
        base.run_episode = original_run_episode
        base.copy_self = original_copy_self


if __name__ == "__main__":
    main()
