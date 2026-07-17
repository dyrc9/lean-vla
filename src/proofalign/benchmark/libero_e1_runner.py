"""E1-specific unguarded LIBERO baseline execution.

The generic online wrapper predates CTDA and still runs its legacy intent and
effect checker when ``ctda`` is disabled.  E1's VLA-only arm must not inherit
that gate.  This module keeps the same environment, policy, observer, trace,
and result serialization as the CTDA runner while replacing only the checker
with a recorder that always permits the policy action.
"""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any

from proofalign.benchmark.libero_online_runner import (
    _check_task_success,
    _execution_config_digest,
    _write_result,
    build_action_abstractor,
    build_policy,
    build_safety_spec,
    create_initialized_env,
    load_libero_task_runtime,
)
from proofalign.benchmark.libero_online_wrapper import ProofAlignLiberoWrapper
from proofalign.models import CheckResult, Decision, ExecutionDecision, ExecutionStep


class UnguardedObservationChecker:
    """Record wrapper state without authorizing, rejecting, or stopping actions."""

    @staticmethod
    def _allow(layer: str) -> CheckResult:
        return CheckResult(
            passed=True,
            layer=layer,
            explanation="E1 VLA-only arm: observational wrapper, no ProofAlign gate",
            suggested_decision=Decision.ALLOW,
            lean_mode="disabled-vla-only",
        )

    def check_intent_alignment(self, *_args: Any, **_kwargs: Any) -> CheckResult:
        return self._allow("e1_vla_only_intent_observation")

    def check_effect_alignment(self, *_args: Any, **_kwargs: Any) -> CheckResult:
        return self._allow("e1_vla_only_effect_observation")

    def check_chunk_effect_alignment(self, *_args: Any, **_kwargs: Any) -> CheckResult:
        return self._allow("e1_vla_only_chunk_observation")


def run_vla_only_episode_with_plugins(
    args: Any,
    *,
    policy: Any | None = None,
    action_abstractor: Any | None = None,
) -> tuple[ExecutionDecision, dict[str, Any]]:
    """Run one genuinely unguarded VLA-only E1 episode.

    The selected registered init state is required and no warmup action is
    allowed.  These constraints make its initial observation directly
    comparable with the Full CTDA arm.
    """

    if bool(getattr(args, "ctda", False)):
        raise ValueError("the E1 VLA-only runner cannot enable CTDA")
    if int(getattr(args, "warmup_steps", 0)) != 0:
        raise ValueError("the E1 VLA-only runner requires warmup_steps=0")

    episode_start = perf_counter()
    runtime = load_libero_task_runtime(
        benchmark_name=args.benchmark,
        task_id=args.task_id,
        init_state_id=args.init_state_id,
        bddl_file=args.bddl_file,
    )
    runtime = replace(
        runtime,
        metadata={
            **runtime.metadata,
            "method_name": getattr(args, "method_name", None),
            "execution_config_digest": _execution_config_digest(args),
            "e1_vla_only_gate": "disabled_observational_wrapper_only",
        },
    )
    env = create_initialized_env(runtime, args)
    try:
        if policy is None:
            policy = build_policy(args)
        else:
            reset_episode = getattr(policy, "reset_episode", None)
            if callable(reset_episode):
                reset_episode()
        if action_abstractor is None:
            action_abstractor = build_action_abstractor(args)

        wrapper = ProofAlignLiberoWrapper(
            env,
            runtime.instruction,
            build_safety_spec(args),
            checker=UnguardedObservationChecker(),
            action_abstractor=action_abstractor,
            max_chunk_steps=int(args.max_chunk_steps),
        )
        selected_init_state_applied = bool(
            getattr(env, "_proofalign_selected_init_state_applied", False)
        )
        initialized_observation_source = getattr(
            env, "_proofalign_initialized_observation_source", "unknown"
        )
        wrapper.current_observation = getattr(
            env, "_proofalign_initialized_observation", None
        )
        if wrapper.current_observation is None:
            raise RuntimeError(
                "E1 VLA-only requires the observation returned by set_init_state"
            )
        wrapper.current_state = wrapper.state_observer.observe(
            env, wrapper.current_observation
        )
        valid_for_registered_init = bool(
            runtime.init_state is not None
            and selected_init_state_applied
            and initialized_observation_source == "set_init_state"
        )
        if not valid_for_registered_init:
            raise RuntimeError(
                "E1 VLA-only registered-init gate requires set_init_state output"
            )
        from proofalign.ctda import digest_legacy_state

        runtime.metadata["environment_initialization"] = {
            "selected_init_state_present": True,
            "selected_init_state_applied": selected_init_state_applied,
            "initialized_observation_source": initialized_observation_source,
            "online_reset_performed": False,
            "valid_for_registered_init": True,
            "benchmark_init_observed_state_digest": digest_legacy_state(
                wrapper.current_state
            ),
        }

        decision = wrapper.run_episode(policy, max_steps=int(args.max_steps))
        episode_metadata = {
            "task_success": _check_task_success(env),
            "episode_wall_time_seconds": perf_counter() - episode_start,
        }
        _write_result(args.output, runtime, decision, episode_metadata)
        return decision, episode_metadata
    finally:
        if hasattr(env, "close"):
            env.close()


def executed_raw_step_count(payload: dict[str, Any]) -> int:
    """Count recorded simulator actions without using runtime timing fields."""

    total = 0
    for step in payload.get("trace", []):
        summary = step.get("summary") or {}
        count = summary.get("num_raw_steps")
        if type(count) is int and count >= 0:
            total += count
    return total


def first_policy_chunk(payload: dict[str, Any]) -> list[Any] | None:
    for step in payload.get("trace", []):
        chunk = step.get("proposed_action_chunk")
        if isinstance(chunk, list):
            return chunk
    return None


def policy_call_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for step in payload.get("trace", [])
        if isinstance(step.get("policy_call_id"), str)
    )

