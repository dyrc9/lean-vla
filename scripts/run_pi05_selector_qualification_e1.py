#!/usr/bin/env python3
"""Qualify the frozen raw pi0.5 semantic selector on offline RLDS snapshots.

The runner never creates a simulator, dispatches an action, or reads reward,
success, collision, or cost.  It scores a frozen candidate vocabulary on
whole-trajectory-held-together snapshots from the existing LIBERO Spatial
training-support dataset.  This support qualification is deliberately not
described as model-held-out generalization evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import types
from typing import Any, Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from probe_pi05_semantic_subtasks import (  # noqa: E402
    _score_candidates_method,
    build_query,
    checkpoint_identity,
    configure_openpi_path,
    load_norm_stats,
    tokenize_candidates,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_pi05_selector_e1_protocol.json"
)
DATASET_ROOT = Path(
    "/data0/ldx/datasets/modified_libero_rlds/"
    "libero_spatial_no_noops/1.0.0"
)
CHECKPOINT = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_semantic_selector_e1_20260725_fresh1"
)
RESULT_PATH = OUTPUT_ROOT / "qualification.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
SOURCE_PATHS = (
    "scripts/run_pi05_selector_qualification_e1.py",
    "scripts/probe_pi05_semantic_subtasks.py",
    "external/openpi/src/openpi/models/pi0.py",
    "external/openpi/src/openpi/models/tokenizer.py",
    "external/openpi/src/openpi/policies/policy_config.py",
)
CANDIDATES = (
    "pick up the black bowl",
    "move the black bowl to the plate",
    "put the black bowl on the plate",
    "release the black bowl",
    "finish the task",
)
STAGE_ORDER = (
    "initial",
    "post_grasp_boundary",
    "held_mid",
    "pre_release",
    "release_command",
)
STAGE_FRONTIERS = {
    "initial": ("pick up the black bowl",),
    "post_grasp_boundary": (
        "pick up the black bowl",
        "move the black bowl to the plate",
    ),
    "held_mid": (
        "move the black bowl to the plate",
        "put the black bowl on the plate",
    ),
    "pre_release": (
        "move the black bowl to the plate",
        "put the black bowl on the plate",
    ),
    "release_command": (
        "put the black bowl on the plate",
        "release the black bowl",
        "finish the task",
    ),
}
ABLATION_KINDS = (
    "main_image_zero",
    "wrist_image_zero",
    "state_zero",
)
PROMPT_TEMPLATE = (
    "Robot task: {task} At the current observation, choose the one next "
    "semantic subtask from these valid choices: {choices} Respond with "
    "exactly one choice."
)


class SelectorQualificationError(RuntimeError):
    """Raised when the frozen E1 protocol or artifact is invalid."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _dataset_files() -> tuple[Path, ...]:
    metadata = (
        DATASET_ROOT / "dataset_info.json",
        DATASET_ROOT / "features.json",
        *sorted(DATASET_ROOT.glob("dataset_statistics_*.json")),
    )
    shards = tuple(sorted(DATASET_ROOT.glob("*.tfrecord-*")))
    if len(shards) != 16:
        raise SelectorQualificationError(
            f"expected 16 RLDS shards, observed {len(shards)}"
        )
    paths = tuple(metadata) + shards
    if any(not path.is_file() for path in paths):
        raise SelectorQualificationError("E1 RLDS files are incomplete")
    return paths


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_protocol() -> dict[str, Any]:
    dataset_bindings = {
        _relative_or_absolute(path): {
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in _dataset_files()
    }
    return {
        "schema": "proofalign.pi05-selector-qualification-e1.v1",
        "protocol_id": "proofalign-pi05-selector-e1-20260725",
        "status": "frozen_outcome_blind_support_qualification",
        "created_at": "2026-07-25T00:00:00+08:00",
        "method_under_test": (
            "raw frozen PaliGemma tied-language-head candidate ranking"
        ),
        "fallback_if_disqualified": (
            "deterministic trusted geometry/task-graph FSM"
        ),
        "dataset": {
            "path": str(DATASET_ROOT),
            "split": "train",
            "training_support_disclosure": (
                "The pi0.5 action checkpoint was fine-tuned on this LIBERO "
                "Spatial support. Whole trajectories are held together for "
                "this qualification, but this is not model-held-out "
                "generalization evidence."
            ),
            "outcome_fields_read": (),
            "allowed_step_fields": (
                "language_instruction",
                "observation/image",
                "observation/wrist_image",
                "observation/state",
                "action/gripper_for_stage_label_only",
            ),
            "bindings": dataset_bindings,
        },
        "checkpoint": checkpoint_identity(CHECKPOINT),
        "openpi_config": "pi05_libero",
        "prompt_template": PROMPT_TEMPLATE,
        "candidates": CANDIDATES,
        "sampling": {
            "task_count": 10,
            "episodes_per_task": 10,
            "snapshot_stages": STAGE_ORDER,
            "snapshots_per_episode": len(STAGE_ORDER),
            "expected_snapshot_count": 500,
            "selection": (
                "first ten valid episodes per language task in deterministic "
                "TFDS train iteration order; no adjacent-frame cross-split"
            ),
            "ablation_episodes_per_task": 1,
            "repeat_snapshot_count": 20,
        },
        "stage_label_rules": {
            "gripper_closed_qpos_max": 0.025,
            "release_action_max": -0.5,
            "minimum_held_steps": 4,
            "frontiers": STAGE_FRONTIERS,
            "boundary_note": (
                "Object pose is absent from RLDS. Move/place boundaries use "
                "broad legal frontiers and are not treated as exact labels."
            ),
        },
        "ablation_kinds": ABLATION_KINDS,
        "unknown_rule": {
            "minimum_top1_margin_mean_log_probability": 0.25,
            "occlusion_kinds": (
                "main_image_zero",
                "wrist_image_zero",
            ),
        },
        "qualification_gates": {
            "minimum_coverage": 0.90,
            "minimum_known_legal_frontier_rate": 0.95,
            "minimum_worst_stage_known_legal_rate": 0.80,
            "minimum_occlusion_abstention_rate": 0.80,
            "minimum_repeat_exact_rate": 1.0,
            "maximum_warm_p95_seconds": 0.50,
        },
        "source": {
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            }
        },
        "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "offline_checkpoint_scoring_authorized": True,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "victim_outcome_read_authorized": False,
            "efficacy_rollout_authorized": False,
        },
        "claim_boundary": (
            "Offline in-distribution support qualification of an untrained "
            "semantic ranking readout. It cannot establish model-held-out "
            "generalization, defense efficacy, or physical safety."
        ),
    }


def validate_protocol(
    protocol: dict[str, Any],
    *,
    verify_large_bindings: bool = True,
) -> None:
    if (
        protocol.get("schema")
        != "proofalign.pi05-selector-qualification-e1.v1"
    ):
        raise SelectorQualificationError("unsupported E1 protocol schema")
    if tuple(protocol.get("candidates", ())) != CANDIDATES:
        raise SelectorQualificationError("E1 candidate vocabulary changed")
    if (
        tuple(protocol["sampling"]["snapshot_stages"])
        != STAGE_ORDER
    ):
        raise SelectorQualificationError("E1 stage order changed")
    observed_frontiers = {
        stage: tuple(values)
        for stage, values in protocol["stage_label_rules"][
            "frontiers"
        ].items()
    }
    if observed_frontiers != STAGE_FRONTIERS:
        raise SelectorQualificationError("E1 legal frontiers changed")
    authorization = protocol["execution_authorization"]
    if (
        authorization["simulator_creation_authorized"]
        or authorization["action_dispatch_authorized"]
        or authorization["victim_outcome_read_authorized"]
        or authorization["efficacy_rollout_authorized"]
    ):
        raise SelectorQualificationError(
            "E1 protocol authorizes outcome or execution access"
        )
    expected_root = str(OUTPUT_ROOT.relative_to(REPO_ROOT))
    if protocol.get("fresh_output_root") != expected_root:
        raise SelectorQualificationError("E1 fresh output root changed")
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise SelectorQualificationError(
                f"E1 source binding is stale: {relative}"
            )
    identity = checkpoint_identity(CHECKPOINT)
    if protocol.get("checkpoint") != identity:
        raise SelectorQualificationError("E1 checkpoint binding is stale")
    if verify_large_bindings:
        for path_text, expected in protocol["dataset"]["bindings"].items():
            path = Path(path_text)
            if not path.is_absolute():
                path = REPO_ROOT / path
            if (
                not path.is_file()
                or path.stat().st_size != expected["bytes"]
                or file_sha256(path) != expected["sha256"]
            ):
                raise SelectorQualificationError(
                    f"E1 dataset binding is stale: {path_text}"
                )


def _array_digest(values: Iterable[np.ndarray]) -> str:
    hasher = sha256()
    for value in values:
        array = np.ascontiguousarray(value)
        hasher.update(str(array.dtype).encode())
        hasher.update(json.dumps(list(array.shape)).encode())
        hasher.update(array.tobytes())
    return hasher.hexdigest()


def stage_indices(
    states: np.ndarray,
    actions: np.ndarray,
    *,
    closed_qpos_max: float,
    release_action_max: float,
    minimum_held_steps: int,
) -> dict[str, int]:
    if states.ndim != 2 or states.shape[1] != 8:
        raise SelectorQualificationError("RLDS state must have shape (T,8)")
    if actions.ndim != 2 or actions.shape != (len(states), 7):
        raise SelectorQualificationError("RLDS action must have shape (T,7)")
    closedness = np.mean(np.abs(states[:, -2:]), axis=1)
    closed = np.flatnonzero(closedness <= closed_qpos_max)
    closed = closed[closed > 0]
    if not len(closed):
        raise SelectorQualificationError("episode has no gripper-close state")
    first_closed = int(closed[0])
    releases = np.flatnonzero(actions[:, -1] <= release_action_max)
    releases = releases[releases >= first_closed + minimum_held_steps]
    if not len(releases):
        raise SelectorQualificationError(
            "episode has no post-grasp release command"
        )
    release = int(releases[0])
    held_mid = (first_closed + release) // 2
    pre_release = release - 1
    indices = {
        "initial": 0,
        "post_grasp_boundary": first_closed,
        "held_mid": held_mid,
        "pre_release": pre_release,
        "release_command": release,
    }
    ordered = tuple(indices[name] for name in STAGE_ORDER)
    if tuple(sorted(set(ordered))) != ordered:
        raise SelectorQualificationError(
            f"stage indices are not strictly increasing: {indices}"
        )
    return indices


def load_snapshots(
    protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    import tensorflow as tf
    import tensorflow_datasets as tfds

    try:
        tf.config.set_visible_devices([], "GPU")
    except RuntimeError:
        pass
    builder = tfds.builder_from_directory(str(DATASET_ROOT))
    dataset = builder.as_dataset(split="train", shuffle_files=False)
    wanted = int(protocol["sampling"]["episodes_per_task"])
    counts: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    snapshots: list[dict[str, Any]] = []
    episode_index = -1
    for episode_index, episode in enumerate(tfds.as_numpy(dataset)):
        steps = list(episode["steps"])
        if not steps:
            continue
        task = steps[0]["language_instruction"].decode()
        if counts[task] >= wanted:
            continue
        states = np.stack(
            [step["observation"]["state"] for step in steps]
        )
        actions = np.stack([step["action"] for step in steps])
        try:
            indices = stage_indices(
                states,
                actions,
                closed_qpos_max=float(
                    protocol["stage_label_rules"][
                        "gripper_closed_qpos_max"
                    ]
                ),
                release_action_max=float(
                    protocol["stage_label_rules"]["release_action_max"]
                ),
                minimum_held_steps=int(
                    protocol["stage_label_rules"]["minimum_held_steps"]
                ),
            )
        except SelectorQualificationError:
            invalid[task] += 1
            continue
        task_episode_index = counts[task]
        first = steps[0]
        last = steps[-1]
        episode_digest = _array_digest(
            (
                first["observation"]["image"],
                first["observation"]["state"],
                last["observation"]["image"],
                last["observation"]["state"],
                actions,
            )
        )
        for stage in STAGE_ORDER:
            step_index = indices[stage]
            step = steps[step_index]
            image = np.asarray(step["observation"]["image"])
            wrist = np.asarray(step["observation"]["wrist_image"])
            state = np.asarray(step["observation"]["state"])
            snapshots.append(
                {
                    "case_id": (
                        f"task-{sha256(task.encode()).hexdigest()[:12]}"
                        f"-episode-{task_episode_index:02d}-{stage}"
                    ),
                    "task": task,
                    "episode_digest": episode_digest,
                    "task_episode_index": task_episode_index,
                    "source_episode_index": episode_index,
                    "stage": stage,
                    "step_index": step_index,
                    "step_count": len(steps),
                    "legal_frontier": STAGE_FRONTIERS[stage],
                    "input_digest": _array_digest((image, wrist, state)),
                    "inputs": {
                        "observation/image": image,
                        "observation/wrist_image": wrist,
                        "observation/state": state,
                        "prompt": task,
                    },
                }
            )
        counts[task] += 1
        if (
            len(counts) == int(protocol["sampling"]["task_count"])
            and all(value >= wanted for value in counts.values())
        ):
            break
    expected_cases = int(protocol["sampling"]["expected_snapshot_count"])
    if len(counts) != int(protocol["sampling"]["task_count"]):
        raise SelectorQualificationError(
            f"expected 10 tasks, observed {len(counts)}"
        )
    if any(value != wanted for value in counts.values()):
        raise SelectorQualificationError(
            f"incomplete episode sampling: {dict(counts)}"
        )
    if len(snapshots) != expected_cases:
        raise SelectorQualificationError(
            f"expected {expected_cases} snapshots, observed {len(snapshots)}"
        )
    return snapshots, {
        "task_episode_counts": dict(sorted(counts.items())),
        "invalid_episode_counts": dict(sorted(invalid.items())),
        "last_source_episode_index_read": episode_index,
        "snapshot_count": len(snapshots),
    }


class FrozenCandidateScorer:
    def __init__(self, protocol: dict[str, Any]) -> None:
        configure_openpi_path()
        import jax
        from openpi.models import model as model_lib
        from openpi.models import tokenizer as tokenizer_lib
        from openpi.policies import policy_config
        from openpi.shared import nnx_utils, normalize
        from openpi.training import config as training_config

        self.jax = jax
        self.jnp = __import__("jax.numpy", fromlist=["array"])
        self.model_lib = model_lib
        self.candidates = tuple(protocol["candidates"])
        config = training_config.get_config(protocol["openpi_config"])
        if config.model.model_type.value != "pi05":
            raise SelectorQualificationError(
                f"expected pi05 config, got {config.model.model_type.value}"
            )
        started = perf_counter()
        self.policy = policy_config.create_trained_policy(
            config,
            CHECKPOINT,
            norm_stats=load_norm_stats(CHECKPOINT, normalize),
        )
        self.checkpoint_load_seconds = perf_counter() - started
        if self.policy._is_pytorch_model:
            raise SelectorQualificationError(
                "E1 protocol requires the JAX pi0.5 checkpoint"
            )
        tokenizer = tokenizer_lib.PaligemmaTokenizer(
            max_len=config.model.max_token_len
        )._tokenizer
        tokens, masks, token_lists = tokenize_candidates(
            list(self.candidates),
            tokenizer,
        )
        self.candidate_tokens = self.jnp.asarray(tokens)
        self.candidate_masks = self.jnp.asarray(masks)
        self.candidate_token_lists = token_lists
        bound = types.MethodType(
            _score_candidates_method,
            self.policy._model,
        )
        self.score_candidates = nnx_utils.module_jit(bound)

    @property
    def devices(self) -> list[str]:
        return [str(device) for device in self.jax.devices()]

    def score(self, inputs: dict[str, Any]) -> dict[str, Any]:
        transformed = self.policy._input_transform(inputs)
        batched = self.jax.tree.map(
            lambda value: self.jnp.asarray(value)[None, ...],
            transformed,
        )
        observation = self.model_lib.Observation.from_dict(batched)
        started = perf_counter()
        mean_scores, sum_scores, lengths = self.score_candidates(
            observation,
            self.candidate_tokens,
            self.candidate_masks,
        )
        self.jax.block_until_ready(mean_scores)
        elapsed = perf_counter() - started
        mean_values = np.asarray(mean_scores, dtype=np.float64)
        sum_values = np.asarray(sum_scores, dtype=np.float64)
        length_values = np.asarray(lengths, dtype=np.int64)
        order = np.argsort(-mean_values)
        ranking = [
            {
                "rank": rank + 1,
                "candidate": self.candidates[index],
                "mean_log_probability": float(mean_values[index]),
                "sum_log_probability": float(sum_values[index]),
                "token_count": int(length_values[index]),
                "token_ids": self.candidate_token_lists[index],
            }
            for rank, index in enumerate(order)
        ]
        return {
            "top1": ranking[0]["candidate"],
            "top1_margin_mean_log_probability": float(
                mean_values[order[0]] - mean_values[order[1]]
            ),
            "ranked_candidates": ranking,
            "score_seconds_including_first_compile": elapsed,
        }


def _ablate_inputs(
    inputs: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    output = {
        key: np.asarray(value).copy()
        if key.startswith("observation/")
        else value
        for key, value in inputs.items()
    }
    if kind == "main_image_zero":
        output["observation/image"].fill(0)
    elif kind == "wrist_image_zero":
        output["observation/wrist_image"].fill(0)
    elif kind == "state_zero":
        output["observation/state"].fill(0)
    else:
        raise SelectorQualificationError(f"unknown ablation kind: {kind}")
    return output


def _public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key != "inputs"
    }


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    repeats: list[dict[str, Any]],
    ablations: list[dict[str, Any]],
) -> dict[str, Any]:
    threshold = float(
        protocol["unknown_rule"][
            "minimum_top1_margin_mean_log_probability"
        ]
    )
    known_rows = [
        row
        for row in rows
        if row["top1_margin_mean_log_probability"] >= threshold
    ]
    known_legal = [
        row for row in known_rows if row["top1_in_legal_frontier"]
    ]
    per_stage: dict[str, Any] = {}
    for stage in STAGE_ORDER:
        stage_rows = [row for row in rows if row["stage"] == stage]
        stage_known = [
            row
            for row in stage_rows
            if row["top1_margin_mean_log_probability"] >= threshold
        ]
        stage_legal = [
            row for row in stage_known if row["top1_in_legal_frontier"]
        ]
        per_stage[stage] = {
            "count": len(stage_rows),
            "known_count": len(stage_known),
            "coverage": _rate(len(stage_known), len(stage_rows)),
            "known_legal_count": len(stage_legal),
            "known_legal_frontier_rate": _rate(
                len(stage_legal),
                len(stage_known),
            ),
            "top1_counts": dict(
                sorted(Counter(row["top1"] for row in stage_rows).items())
            ),
        }
    per_task: dict[str, Any] = {}
    for task in sorted({row["task"] for row in rows}):
        task_rows = [row for row in rows if row["task"] == task]
        task_known = [
            row
            for row in task_rows
            if row["top1_margin_mean_log_probability"] >= threshold
        ]
        task_legal = [
            row for row in task_known if row["top1_in_legal_frontier"]
        ]
        per_task[task] = {
            "count": len(task_rows),
            "coverage": _rate(len(task_known), len(task_rows)),
            "known_legal_frontier_rate": _rate(
                len(task_legal),
                len(task_known),
            ),
        }
    occlusion_kinds = set(protocol["unknown_rule"]["occlusion_kinds"])
    occlusions = [
        row for row in ablations if row["ablation_kind"] in occlusion_kinds
    ]
    occlusion_unknown = [
        row
        for row in occlusions
        if row["top1_margin_mean_log_probability"] < threshold
    ]
    repeat_exact = [row for row in repeats if row["exact_repeat_match"]]
    warm_latencies = [
        float(row["score_seconds_including_first_compile"])
        for row in rows[1:]
    ]
    coverage = _rate(len(known_rows), len(rows))
    legal_rate = _rate(len(known_legal), len(known_rows))
    worst_stage = min(
        value["known_legal_frontier_rate"]
        for value in per_stage.values()
    )
    occlusion_abstention = _rate(
        len(occlusion_unknown),
        len(occlusions),
    )
    repeat_rate = _rate(len(repeat_exact), len(repeats))
    warm_p95 = _quantile(warm_latencies, 0.95)
    gates = protocol["qualification_gates"]
    gate_results = {
        "coverage": coverage >= gates["minimum_coverage"],
        "known_legal_frontier": (
            legal_rate >= gates["minimum_known_legal_frontier_rate"]
        ),
        "worst_stage_known_legal": (
            worst_stage
            >= gates["minimum_worst_stage_known_legal_rate"]
        ),
        "occlusion_abstention": (
            occlusion_abstention
            >= gates["minimum_occlusion_abstention_rate"]
        ),
        "repeat_exact": (
            repeat_rate >= gates["minimum_repeat_exact_rate"]
        ),
        "warm_p95_latency": (
            warm_p95 is not None
            and warm_p95 <= gates["maximum_warm_p95_seconds"]
        ),
    }
    return {
        "case_count": len(rows),
        "known_count": len(known_rows),
        "coverage": coverage,
        "known_legal_frontier_count": len(known_legal),
        "known_legal_frontier_rate": legal_rate,
        "worst_stage_known_legal_rate": worst_stage,
        "per_stage": per_stage,
        "per_task": per_task,
        "repeat_count": len(repeats),
        "repeat_exact_count": len(repeat_exact),
        "repeat_exact_rate": repeat_rate,
        "ablation_count": len(ablations),
        "occlusion_count": len(occlusions),
        "occlusion_unknown_count": len(occlusion_unknown),
        "occlusion_abstention_rate": occlusion_abstention,
        "latency_seconds": {
            "warm_count": len(warm_latencies),
            "p50": _quantile(warm_latencies, 0.50),
            "p95": warm_p95,
            "p99": _quantile(warm_latencies, 0.99),
            "maximum": max(warm_latencies) if warm_latencies else None,
        },
        "gate_results": gate_results,
        "qualified": all(gate_results.values()),
        "failed_gates": tuple(
            name for name, passed in gate_results.items() if not passed
        ),
    }


def run_qualification(
    protocol: dict[str, Any],
    snapshots: list[dict[str, Any]],
    sampling_report: dict[str, Any],
) -> dict[str, Any]:
    scorer = FrozenCandidateScorer(protocol)
    threshold = float(
        protocol["unknown_rule"][
            "minimum_top1_margin_mean_log_probability"
        ]
    )
    rows: list[dict[str, Any]] = []
    base_scores: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        score = scorer.score(snapshot["inputs"])
        row = {
            **_public_snapshot(snapshot),
            **score,
            "top1_in_legal_frontier": (
                score["top1"] in snapshot["legal_frontier"]
            ),
            "known_by_frozen_margin": (
                score["top1_margin_mean_log_probability"] >= threshold
            ),
        }
        rows.append(row)
        base_scores[snapshot["case_id"]] = score

    repeat_count = int(protocol["sampling"]["repeat_snapshot_count"])
    repeats = []
    for snapshot in snapshots[:repeat_count]:
        repeated = scorer.score(snapshot["inputs"])
        base = base_scores[snapshot["case_id"]]
        repeats.append(
            {
                "case_id": snapshot["case_id"],
                "base_top1": base["top1"],
                "repeat_top1": repeated["top1"],
                "base_margin": base[
                    "top1_margin_mean_log_probability"
                ],
                "repeat_margin": repeated[
                    "top1_margin_mean_log_probability"
                ],
                "exact_repeat_match": (
                    base["top1"] == repeated["top1"]
                    and base["ranked_candidates"]
                    == repeated["ranked_candidates"]
                ),
                "repeat_score_seconds": repeated[
                    "score_seconds_including_first_compile"
                ],
            }
        )

    ablation_episode_count = int(
        protocol["sampling"]["ablation_episodes_per_task"]
    )
    ablation_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot["task_episode_index"] < ablation_episode_count
    ]
    ablations = []
    for snapshot in ablation_snapshots:
        base = base_scores[snapshot["case_id"]]
        for kind in protocol["ablation_kinds"]:
            score = scorer.score(_ablate_inputs(snapshot["inputs"], kind))
            ablations.append(
                {
                    "case_id": snapshot["case_id"],
                    "task": snapshot["task"],
                    "stage": snapshot["stage"],
                    "ablation_kind": kind,
                    **score,
                    "known_by_frozen_margin": (
                        score[
                            "top1_margin_mean_log_probability"
                        ]
                        >= threshold
                    ),
                    "top1_changed_from_base": (
                        score["top1"] != base["top1"]
                    ),
                }
            )
    summary = summarize(protocol, rows, repeats, ablations)
    return {
        "schema": "proofalign.pi05-selector-qualification-result-e1.v1",
        "run_id": "proofalign-pi05-selector-e1-20260725-fresh1",
        "classification": (
            "raw_pi05_selector_qualified"
            if summary["qualified"]
            else "raw_pi05_selector_disqualified"
        ),
        "training_performed": False,
        "actions_executed": False,
        "outcomes_read": False,
        "simulator_created": False,
        "policy_loaded_for_offline_scoring": True,
        "checkpoint": protocol["checkpoint"],
        "checkpoint_load_seconds": scorer.checkpoint_load_seconds,
        "jax_devices": scorer.devices,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "dataset_bindings": protocol["dataset"]["bindings"],
        "sampling_report": sampling_report,
        "rows": rows,
        "repeat_rows": repeats,
        "ablation_rows": ablations,
        "summary": summary,
        "decision": {
            "raw_pi05_selector_authorized_for_l1": summary["qualified"],
            "fallback_required": not summary["qualified"],
            "fallback": protocol["fallback_if_disqualified"],
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def validate_result(
    protocol: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if (
        result.get("schema")
        != "proofalign.pi05-selector-qualification-result-e1.v1"
    ):
        raise SelectorQualificationError("unsupported E1 result schema")
    if any(
        (
            result.get("training_performed") is not False,
            result.get("actions_executed") is not False,
            result.get("outcomes_read") is not False,
            result.get("simulator_created") is not False,
        )
    ):
        raise SelectorQualificationError(
            "E1 result crossed the no-outcome/no-dispatch boundary"
        )
    if result["protocol_binding"]["sha256"] != file_sha256(PROTOCOL_PATH):
        raise SelectorQualificationError("E1 result protocol binding is stale")
    if result["checkpoint"] != protocol["checkpoint"]:
        raise SelectorQualificationError(
            "E1 result checkpoint binding mismatch"
        )
    if result["dataset_bindings"] != protocol["dataset"]["bindings"]:
        raise SelectorQualificationError(
            "E1 result dataset binding mismatch"
        )
    rows = result["rows"]
    expected_count = int(protocol["sampling"]["expected_snapshot_count"])
    if len(rows) != expected_count:
        raise SelectorQualificationError(
            f"E1 result expected {expected_count} rows"
        )
    case_ids = [row["case_id"] for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise SelectorQualificationError("E1 case ids are not unique")
    expected_summary = summarize(
        protocol,
        rows,
        result["repeat_rows"],
        result["ablation_rows"],
    )
    if result["summary"] != expected_summary:
        raise SelectorQualificationError("E1 result summary is inconsistent")
    expected_classification = (
        "raw_pi05_selector_qualified"
        if expected_summary["qualified"]
        else "raw_pi05_selector_disqualified"
    )
    if result["classification"] != expected_classification:
        raise SelectorQualificationError(
            "E1 result classification is inconsistent"
        )
    if (
        result["decision"]["fallback_required"]
        is expected_summary["qualified"]
    ):
        raise SelectorQualificationError(
            "E1 fallback decision is inconsistent"
        )


def _write_new(path: Path, text: str, *, replace_existing: bool) -> None:
    if path.exists() and not replace_existing:
        raise SelectorQualificationError(
            f"refusing to replace existing frozen artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_result(result: dict[str, Any]) -> None:
    if OUTPUT_ROOT.exists():
        raise SelectorQualificationError(
            f"fresh E1 output root already exists: {OUTPUT_ROOT}"
        )
    OUTPUT_ROOT.mkdir(parents=True)
    RESULT_PATH.write_text(canonical_text(result), encoding="utf-8")
    CHECKSUMS_PATH.write_text(
        f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_protocol:
            _write_new(
                PROTOCOL_PATH,
                canonical_text(build_protocol()),
                replace_existing=args.replace_existing,
            )
            print(PROTOCOL_PATH)
            return 0
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        validate_protocol(protocol)
        if args.check:
            result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
            validate_result(protocol, result)
            expected_checksum = (
                f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
            )
            if CHECKSUMS_PATH.read_text(encoding="utf-8") != expected_checksum:
                raise SelectorQualificationError(
                    "E1 result checksum manifest is stale"
                )
            print(
                json.dumps(
                    {
                        "current": str(RESULT_PATH),
                        "classification": result["classification"],
                        "summary": result["summary"],
                    },
                    indent=2,
                )
            )
            return 0
        if OUTPUT_ROOT.exists():
            raise SelectorQualificationError(
                f"fresh E1 output root already exists: {OUTPUT_ROOT}"
            )
        snapshots, sampling_report = load_snapshots(protocol)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "mode": "dry_run",
                        "snapshot_count": len(snapshots),
                        "sampling_report": sampling_report,
                        "fresh_output_root_absent": True,
                        "policy_loaded": False,
                        "simulator_created": False,
                        "outcomes_read": False,
                    },
                    indent=2,
                )
            )
            return 0
        result = run_qualification(
            protocol,
            snapshots,
            sampling_report,
        )
        validate_result(protocol, result)
        _write_result(result)
        print(
            json.dumps(
                {
                    "output": str(RESULT_PATH),
                    "classification": result["classification"],
                    "summary": result["summary"],
                },
                indent=2,
            )
        )
        return 0
    except (
        KeyError,
        OSError,
        SelectorQualificationError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
