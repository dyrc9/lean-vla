#!/usr/bin/env python3
"""Check whether a frozen semantic subtask causally changes pi0.5 actions.

The probe holds the observation and flow-matching noise fixed, varies only the
prompt's semantic-subtask clause, and compares the returned ActionBlocks. It
does not execute actions, read outcomes, train, or mutate checkpoint weights.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from probe_pi05_semantic_subtasks import (
    REPO_ROOT,
    checkpoint_identity,
    configure_openpi_path,
    load_norm_stats,
    load_policy_record,
    resolve_repo_path,
)


DEFAULT_RECORD = (
    REPO_ROOT
    / "results"
    / "phantom_menace_r0b_20260715"
    / "clean_task7_init0"
    / "server"
    / "policy_records"
    / "step_0.npy"
)
DEFAULT_CHECKPOINT = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")
DEFAULT_OUTPUT = (
    REPO_ROOT / "results" / "pi05_subtask_action_conditioning_v0" / "probe.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe frozen z_t prompt conditioning with fixed flow noise."
    )
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--openpi-config", default="pi05_libero")
    parser.add_argument("--expected-subtask", default="pick up the black bowl")
    parser.add_argument(
        "--alternative-subtask", default="put the black bowl on the plate"
    )
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--sample-steps", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def array_digest(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    hasher = sha256()
    hasher.update(str(value.dtype).encode())
    hasher.update(json.dumps(list(value.shape)).encode())
    hasher.update(value.tobytes())
    return hasher.hexdigest()


def action_summary(actions: np.ndarray) -> dict[str, Any]:
    return {
        "shape": list(actions.shape),
        "dtype": str(actions.dtype),
        "sha256": array_digest(actions),
        "first_action": actions[0].tolist(),
        "mean_abs_translation": float(np.mean(np.abs(actions[:, :3]))),
        "mean_abs_rotation": float(np.mean(np.abs(actions[:, 3:6]))),
        "mean_gripper": float(np.mean(actions[:, 6])),
        "action_chunk": actions.tolist(),
    }


def compare_actions(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    delta = right - left
    left_flat = left[:, :6].reshape(-1)
    right_flat = right[:, :6].reshape(-1)
    denominator = np.linalg.norm(left_flat) * np.linalg.norm(right_flat)
    cosine = float(np.dot(left_flat, right_flat) / denominator) if denominator else None
    return {
        "mean_absolute_delta": float(np.mean(np.abs(delta))),
        "max_absolute_delta": float(np.max(np.abs(delta))),
        "translation_mean_absolute_delta": float(np.mean(np.abs(delta[:, :3]))),
        "rotation_mean_absolute_delta": float(np.mean(np.abs(delta[:, 3:6]))),
        "gripper_mean_absolute_delta": float(np.mean(np.abs(delta[:, 6]))),
        "motion_cosine_similarity": cosine,
        "different_sha256": array_digest(left) != array_digest(right),
    }


def main() -> None:
    args = parse_args()
    configure_openpi_path()

    import jax

    from openpi.policies import policy_config
    from openpi.shared import normalize
    from openpi.training import config as training_config

    checkpoint = args.checkpoint.resolve()
    record_path = resolve_repo_path(str(args.record)).resolve()
    inputs = load_policy_record(record_path)
    task = inputs["prompt"]
    prompts = {
        "baseline": task,
        "expected_subtask_appended": f"{task}. Current semantic subtask: {args.expected_subtask}.",
        "alternative_subtask_appended": f"{task}. Current semantic subtask: {args.alternative_subtask}.",
        "expected_subtask_only": args.expected_subtask,
        "alternative_subtask_only": args.alternative_subtask,
    }

    config = training_config.get_config(args.openpi_config)
    norm_stats = load_norm_stats(checkpoint, normalize)
    loaded_at = perf_counter()
    policy = policy_config.create_trained_policy(
        config,
        checkpoint,
        sample_kwargs={"num_steps": args.sample_steps},
        norm_stats=norm_stats,
    )
    checkpoint_load_seconds = perf_counter() - loaded_at
    if policy._is_pytorch_model:
        raise NotImplementedError(
            "This probe currently supports the JAX checkpoint only."
        )

    rng = np.random.default_rng(args.seed)
    noise = rng.standard_normal(
        (config.model.action_horizon, config.model.action_dim),
        dtype=np.float32,
    )
    outputs = {}
    for label, prompt in prompts.items():
        started = perf_counter()
        result = policy.infer({**inputs, "prompt": prompt}, noise=noise)
        actions = np.asarray(result["actions"])
        outputs[label] = {
            "prompt": prompt,
            "elapsed_seconds_including_first_compile": perf_counter() - started,
            **action_summary(actions),
        }

    arrays = {
        label: np.asarray(value["action_chunk"]) for label, value in outputs.items()
    }
    result = {
        "schema": "proofalign.pi05-subtask-action-conditioning-result.v0",
        "training_performed": False,
        "actions_executed": False,
        "outcomes_read": False,
        "checkpoint": checkpoint_identity(checkpoint),
        "checkpoint_load_seconds": checkpoint_load_seconds,
        "openpi_config": args.openpi_config,
        "jax_devices": [str(device) for device in jax.devices()],
        "record": str(record_path),
        "task": task,
        "fixed_noise": {
            "seed": args.seed,
            "shape": list(noise.shape),
            "dtype": str(noise.dtype),
            "sha256": array_digest(noise),
        },
        "outputs": outputs,
        "comparisons": {
            "baseline_vs_expected_appended": compare_actions(
                arrays["baseline"], arrays["expected_subtask_appended"]
            ),
            "baseline_vs_alternative_appended": compare_actions(
                arrays["baseline"], arrays["alternative_subtask_appended"]
            ),
            "expected_vs_alternative_appended": compare_actions(
                arrays["expected_subtask_appended"],
                arrays["alternative_subtask_appended"],
            ),
            "baseline_vs_expected_only": compare_actions(
                arrays["baseline"], arrays["expected_subtask_only"]
            ),
            "baseline_vs_alternative_only": compare_actions(
                arrays["baseline"], arrays["alternative_subtask_only"]
            ),
            "expected_vs_alternative_only": compare_actions(
                arrays["expected_subtask_only"], arrays["alternative_subtask_only"]
            ),
        },
        "interpretation": (
            "A non-zero difference establishes prompt-path causal sensitivity only. "
            "It does not establish that the conditioned action is better or safer."
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
