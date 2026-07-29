#!/usr/bin/env python3
"""Outcome-informed L2 joint-limit containment successor over frozen v10."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.joint_limit_containment import (  # noqa: E402
    JOINT_LIMIT_CONTAINMENT_SCHEMA,
    JOINT_LIMIT_CONTAINMENT_VERSION,
    JOINT_LIMIT_VIOLATION_ATOM,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v10 as v10  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_joint_limit_containment_successor_v11"
)
CONTAINMENT_INFO_KEY = "proofalign_joint_limit_containment"


@dataclass(frozen=True)
class JointLimitObservation:
    runner_step_id: int
    joint_limit_violation: bool
    environment_done_before_containment: bool


class JointLimitContainmentEnvironment:
    """Stop after the first model-defined post-step joint-limit signal."""

    def __init__(self, env: Any, *, wait_steps: int) -> None:
        if type(wait_steps) is not int or wait_steps < 0:
            raise ValueError("wait_steps must be a non-negative integer")
        self._env = env
        self._wait_steps = wait_steps
        self._call_index = 0
        self.observations: list[JointLimitObservation] = []

    def step(self, action: Any) -> Any:
        result = self._env.step(action)
        runner_step_id = self._call_index
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return result

        violated = _model_joint_limit_violation(self._env)
        normalized = _normalize_step_result(result)
        self.observations.append(
            JointLimitObservation(
                runner_step_id=runner_step_id,
                joint_limit_violation=violated,
                environment_done_before_containment=(
                    normalized["done"]
                ),
            )
        )
        if not violated:
            return result

        info = dict(normalized["info"])
        info[CONTAINMENT_INFO_KEY] = True
        if normalized["tuple_length"] == 4:
            return (
                normalized["observation"],
                normalized["reward"],
                True,
                info,
            )
        return (
            normalized["observation"],
            normalized["reward"],
            True,
            normalized["truncated"],
            info,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)


def _normalize_step_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, tuple) or len(result) not in (4, 5):
        raise RuntimeError(
            "joint-limit containment requires a 4- or 5-value env step"
        )
    if len(result) == 4:
        observation, reward, done, info = result
        return {
            "tuple_length": 4,
            "observation": observation,
            "reward": reward,
            "done": bool(done),
            "truncated": False,
            "info": dict(info or {}),
        }
    observation, reward, terminated, truncated, info = result
    return {
        "tuple_length": 5,
        "observation": observation,
        "reward": reward,
        "done": bool(terminated or truncated),
        "truncated": bool(truncated),
        "info": dict(info or {}),
    }


def _model_joint_limit_violation(env: Any) -> bool:
    """Use the same robosuite model-range predicate as SABER."""

    robots = getattr(env, "robots", None)
    if not isinstance(robots, (list, tuple)) or not robots:
        raise RuntimeError(
            "joint-limit observer cannot access the trusted robot list"
        )
    flags = []
    for robot in robots:
        check = getattr(robot, "check_q_limits", None)
        if not callable(check):
            raise RuntimeError(
                "joint-limit observer cannot access check_q_limits"
            )
        value = check()
        if not isinstance(value, (bool, np.bool_)):
            raise RuntimeError(
                "check_q_limits returned a non-boolean value"
            )
        flags.append(bool(value))
    return any(flags)


def _run_with_containment(kwargs: dict[str, Any]) -> dict[str, Any]:
    if kwargs.get("constraint_signal_extractor") is None:
        raise RuntimeError(
            "v11 requires the independent constraint-signal extractor"
        )

    original_create_env = base.create_env
    original_violation_atoms = base.libero_violation_atoms
    wrapped_envs: list[JointLimitContainmentEnvironment] = []

    def create_contained_env(
        *args: Any, **create_kwargs: Any
    ) -> JointLimitContainmentEnvironment:
        wrapped = JointLimitContainmentEnvironment(
            original_create_env(*args, **create_kwargs),
            wait_steps=int(kwargs["args"].num_steps_wait),
        )
        wrapped_envs.append(wrapped)
        return wrapped

    def violation_atoms(info: dict[str, Any]) -> tuple[str, ...]:
        inherited = original_violation_atoms(info)
        if not bool(info.get(CONTAINMENT_INFO_KEY)):
            return inherited
        return tuple(
            dict.fromkeys(
                (*inherited, JOINT_LIMIT_VIOLATION_ATOM)
            )
        )

    base.create_env = create_contained_env
    base.libero_violation_atoms = violation_atoms
    try:
        payload = v10.run_episode(**kwargs)
    finally:
        base.create_env = original_create_env
        base.libero_violation_atoms = original_violation_atoms

    if len(wrapped_envs) != 1:
        raise RuntimeError(
            "v11 expected exactly one contained episode environment"
        )
    _bind_containment_trace(payload, wrapped_envs[0].observations)
    return payload


def _bind_containment_trace(
    payload: dict[str, Any],
    observations: list[JointLimitObservation],
) -> None:
    policy_rows = [
        row
        for row in payload.get("trace", ())
        if row.get("phase") == "policy"
    ]
    if len(policy_rows) != len(observations):
        raise RuntimeError(
            "v11 containment observations do not cover every policy step"
        )
    triggered = []
    for row, observation in zip(
        policy_rows, observations, strict=True
    ):
        if row.get("step_id") != observation.runner_step_id:
            raise RuntimeError(
                "v11 containment step binding differs from the trace"
            )
        signals = row.get("saber_constraint_signals")
        if (
            not isinstance(signals, Mapping)
            or type(signals.get("joint_limit_violation")) is not bool
            or signals["joint_limit_violation"]
            is not observation.joint_limit_violation
        ):
            raise RuntimeError(
                "v11 model observer disagrees with independent SABER signal"
            )
        row["joint_limit_containment"] = {
            "schema": JOINT_LIMIT_CONTAINMENT_SCHEMA,
            "observer_version": JOINT_LIMIT_CONTAINMENT_VERSION,
            "layer": "L2",
            "post_step_signal": True,
            "joint_limit_violation": (
                observation.joint_limit_violation
            ),
            "halt_before_next_dispatch": (
                observation.joint_limit_violation
            ),
            "environment_done_before_containment": (
                observation.environment_done_before_containment
            ),
            "prevention_claim": False,
        }
        if observation.joint_limit_violation:
            triggered.append(observation)

    if len(triggered) > 1:
        raise RuntimeError(
            "v11 dispatched after the first containment trigger"
        )
    if triggered:
        if not observations[-1].joint_limit_violation:
            raise RuntimeError(
                "v11 trace continued after containment"
            )
        payload["decision"] = "joint_limit_containment"
        payload["success_by_done"] = triggered[
            0
        ].environment_done_before_containment


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Arm the post-step containment observer only for L2-enabled arms."""

    args: argparse.Namespace = kwargs["args"]
    _l1_enabled, l2_enabled = v1._arm_switches(args)
    if l2_enabled:
        payload = _run_with_containment(dict(kwargs))
    else:
        payload = v10.run_episode(**kwargs)

    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "joint_limit_containment_active": bool(l2_enabled),
            "joint_limit_containment_schema": (
                JOINT_LIMIT_CONTAINMENT_SCHEMA
                if l2_enabled
                else None
            ),
            "joint_limit_containment_version": (
                JOINT_LIMIT_CONTAINMENT_VERSION
                if l2_enabled
                else None
            ),
            "joint_limit_containment_layer": (
                "L2" if l2_enabled else None
            ),
            "joint_limit_prevention_claim": False,
            "joint_limit_containment_claim": bool(l2_enabled),
        }
    )
    payload["metadata"] = metadata
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "execution_authorized": False,
            "note": (
                "Import run_episode through a separately frozen v11 "
                "qualification or pilot protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
