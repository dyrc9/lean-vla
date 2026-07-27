#!/usr/bin/env python3
"""Probe frozen pi0.5/PaliGemma semantic-subtask candidate scores.

This is an outcome-blind feasibility probe. It reads existing policy input records,
loads a frozen checkpoint, and scores a finite candidate set with the checkpoint's
tied language head. It does not train or mutate model weights and does not read
future observations or episode outcomes.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import types
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENPI_ROOT = REPO_ROOT / "external" / "openpi"
DEFAULT_SPEC = REPO_ROOT / "experiments" / "pi05_semantic_subtask_probe_v0.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "pi05_semantic_subtask_probe_v0" / "probe.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score finite semantic-subtask candidates with a frozen pi0.5 checkpoint."
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--case-id",
        action="append",
        help="Run only the selected case id; may be repeated.",
    )
    parser.add_argument(
        "--checkpoint", type=Path, help="Override checkpoint path from the spec."
    )
    parser.add_argument("--openpi-config", help="Override OpenPI config from the spec.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print queries without loading a model.",
    )
    return parser.parse_args()


def configure_openpi_path() -> None:
    paths = (
        OPENPI_ROOT / "src",
        OPENPI_ROOT / "packages" / "openpi-client" / "src",
    )
    for path in paths:
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
    os.environ.setdefault("OPENPI_DATA_HOME", str(Path.home() / ".cache" / "openpi"))
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")


def load_spec(path: Path, selected_case_ids: list[str] | None) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {"checkpoint", "openpi_config", "prompt_template", "candidates", "cases"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Probe spec is missing fields: {sorted(missing)}")
    candidates = spec["candidates"]
    if not candidates or len(candidates) != len(set(candidates)):
        raise ValueError("Probe candidates must be non-empty and unique.")
    cases = spec["cases"]
    if selected_case_ids:
        selected = set(selected_case_ids)
        known = {case["case_id"] for case in cases}
        unknown = selected - known
        if unknown:
            raise ValueError(f"Unknown case ids: {sorted(unknown)}")
        cases = [case for case in cases if case["case_id"] in selected]
    if not cases:
        raise ValueError("No probe cases selected.")
    return {**spec, "cases": cases}


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def load_policy_record(path: Path) -> dict[str, Any]:
    value = np.load(path, allow_pickle=True)
    record = value.item()
    required = {
        "inputs/observation/image",
        "inputs/observation/wrist_image",
        "inputs/observation/state",
        "inputs/prompt",
    }
    missing = required - set(record)
    if missing:
        raise ValueError(f"{path} is missing required input fields: {sorted(missing)}")
    # Intentionally return only policy inputs. Outcome/output fields are never used by the probe.
    return {
        "observation/image": np.asarray(record["inputs/observation/image"]),
        "observation/wrist_image": np.asarray(record["inputs/observation/wrist_image"]),
        "observation/state": np.asarray(record["inputs/observation/state"]),
        "prompt": str(record["inputs/prompt"]),
    }


def build_query(template: str, task: str, candidates: list[str]) -> str:
    choices = " | ".join(candidates)
    return template.format(task=task, choices=choices)


def load_norm_stats(checkpoint: Path, normalize_module: Any) -> Any | None:
    standard = (
        checkpoint / "assets" / "physical-intelligence" / "libero" / "norm_stats.json"
    )
    if standard.exists():
        return None
    released = checkpoint / "assets" / "lerobot"
    if (released / "norm_stats.json").exists():
        return normalize_module.load(released)
    raise FileNotFoundError(f"No norm_stats.json found below {checkpoint / 'assets'}")


def _score_candidates_method(
    self: Any,
    observation: Any,
    candidate_tokens: Any,
    candidate_masks: Any,
) -> tuple[Any, Any, Any]:
    """NNX-bound method used only by the frozen feasibility probe."""
    import einops
    import jax
    import jax.numpy as jnp

    from openpi.models import model as model_lib
    from openpi.models.pi0 import make_attn_mask

    observation = model_lib.preprocess_observation(None, observation, train=False)
    candidate_count = candidate_tokens.shape[0]

    image_embeddings = []
    image_masks = []
    for name in observation.images:
        image_tokens, _ = self.PaliGemma.img(observation.images[name], train=False)
        image_embeddings.append(jnp.repeat(image_tokens, candidate_count, axis=0))
        image_masks.append(
            einops.repeat(
                observation.image_masks[name],
                "b -> (b c) s",
                c=candidate_count,
                s=image_tokens.shape[1],
            )
        )

    prompt_embeddings = self.PaliGemma.llm(observation.tokenized_prompt, method="embed")
    prompt_embeddings = jnp.repeat(prompt_embeddings, candidate_count, axis=0)
    prompt_masks = jnp.repeat(
        observation.tokenized_prompt_mask, candidate_count, axis=0
    )
    candidate_embeddings = self.PaliGemma.llm(candidate_tokens, method="embed")

    embeddings = jnp.concatenate(
        [*image_embeddings, prompt_embeddings, candidate_embeddings], axis=1
    )
    input_mask = jnp.concatenate([*image_masks, prompt_masks, candidate_masks], axis=1)
    image_length = sum(tokens.shape[1] for tokens in image_embeddings)
    prompt_length = observation.tokenized_prompt.shape[1]
    candidate_length = candidate_tokens.shape[1]
    ar_mask = jnp.concatenate(
        [
            jnp.zeros((image_length + prompt_length,), dtype=jnp.bool_),
            jnp.ones((candidate_length,), dtype=jnp.bool_),
        ]
    )
    attention_mask = make_attn_mask(input_mask, ar_mask)
    positions = jnp.cumsum(input_mask, axis=1) - 1
    (hidden, _), _ = self.PaliGemma.llm(
        [embeddings, None],
        mask=attention_mask,
        positions=positions,
    )

    valid_prompt_length = jnp.sum(observation.tokenized_prompt_mask[0]).astype(
        jnp.int32
    )
    first_prediction_index = image_length + valid_prompt_length - 1
    candidate_base = image_length + prompt_length
    prediction_indices = jnp.concatenate(
        [
            first_prediction_index[None],
            candidate_base + jnp.arange(candidate_length - 1, dtype=jnp.int32),
        ]
    )
    prediction_hidden = jnp.take(hidden, prediction_indices, axis=1)
    embedding_table = self.PaliGemma.llm.embedder["input_embedding"].value
    logits = jnp.einsum("cld,vd->clv", prediction_hidden, embedding_table).astype(
        jnp.float32
    )
    target_logits = jnp.take_along_axis(logits, candidate_tokens[..., None], axis=-1)[
        ..., 0
    ]
    token_log_probs = target_logits - jax.nn.logsumexp(logits, axis=-1)
    token_log_probs = jnp.where(candidate_masks, token_log_probs, 0.0)
    lengths = jnp.sum(candidate_masks, axis=-1)
    sum_log_probs = jnp.sum(token_log_probs, axis=-1)
    mean_log_probs = sum_log_probs / jnp.maximum(lengths, 1)
    return mean_log_probs, sum_log_probs, lengths


def tokenize_candidates(
    candidates: list[str], tokenizer: Any
) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    token_lists = [
        list(tokenizer.encode(candidate, add_eos=True)) for candidate in candidates
    ]
    max_length = max(map(len, token_lists))
    tokens = np.zeros((len(candidates), max_length), dtype=np.int32)
    masks = np.zeros((len(candidates), max_length), dtype=bool)
    for index, token_list in enumerate(token_lists):
        tokens[index, : len(token_list)] = token_list
        masks[index, : len(token_list)] = True
    return tokens, masks, token_lists


def digest_file(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def checkpoint_identity(checkpoint: Path) -> dict[str, Any]:
    manifest = checkpoint / "params" / "manifest.ocdbt"
    metadata = checkpoint / "params" / "_METADATA"
    return {
        "path": str(checkpoint.resolve()),
        "manifest_sha256": digest_file(manifest),
        "metadata_sha256": digest_file(metadata),
    }


def make_dry_run(
    spec: dict[str, Any], checkpoint: Path, config_name: str
) -> dict[str, Any]:
    cases = []
    for case in spec["cases"]:
        path = resolve_repo_path(case["record"])
        inputs = load_policy_record(path)
        cases.append(
            {
                "case_id": case["case_id"],
                "record": str(path.resolve()),
                "task": inputs["prompt"],
                "expected": case["expected"],
                "query": build_query(
                    spec["prompt_template"], inputs["prompt"], spec["candidates"]
                ),
                "image_shape": list(inputs["observation/image"].shape),
                "wrist_image_shape": list(inputs["observation/wrist_image"].shape),
                "state_shape": list(inputs["observation/state"].shape),
            }
        )
    return {
        "schema": "proofalign.pi05-semantic-subtask-probe-result.v0",
        "mode": "dry_run",
        "checkpoint": str(checkpoint),
        "openpi_config": config_name,
        "candidates": spec["candidates"],
        "cases": cases,
    }


def run_probe(
    spec: dict[str, Any], checkpoint: Path, config_name: str
) -> dict[str, Any]:
    import jax
    import jax.numpy as jnp

    from openpi.models import model as model_lib
    from openpi.models import tokenizer as tokenizer_lib
    from openpi.policies import policy_config
    from openpi.shared import nnx_utils
    from openpi.shared import normalize
    from openpi.training import config as training_config

    config = training_config.get_config(config_name)
    if config.model.model_type.value != "pi05":
        raise ValueError(f"Expected a pi05 config, got {config.model.model_type.value}")
    norm_stats = load_norm_stats(checkpoint, normalize)
    load_start = perf_counter()
    policy = policy_config.create_trained_policy(
        config,
        checkpoint,
        norm_stats=norm_stats,
    )
    load_seconds = perf_counter() - load_start
    if policy._is_pytorch_model:
        raise NotImplementedError(
            "This probe currently supports the JAX pi0.5 checkpoint only."
        )

    paligemma_tokenizer = tokenizer_lib.PaligemmaTokenizer(
        max_len=config.model.max_token_len
    )
    sentencepiece_tokenizer = paligemma_tokenizer._tokenizer
    candidate_tokens, candidate_masks, candidate_token_lists = tokenize_candidates(
        spec["candidates"], sentencepiece_tokenizer
    )
    bound_method = types.MethodType(_score_candidates_method, policy._model)
    score_candidates = nnx_utils.module_jit(bound_method)

    results = []
    for case in spec["cases"]:
        record_path = resolve_repo_path(case["record"])
        inputs = load_policy_record(record_path)
        task = inputs["prompt"]
        query = build_query(spec["prompt_template"], task, spec["candidates"])
        model_inputs = {**inputs, "prompt": query}
        transformed = policy._input_transform(model_inputs)
        batched = jax.tree.map(lambda value: jnp.asarray(value)[None, ...], transformed)
        observation = model_lib.Observation.from_dict(batched)

        started = perf_counter()
        mean_scores, sum_scores, lengths = score_candidates(
            observation,
            jnp.asarray(candidate_tokens),
            jnp.asarray(candidate_masks),
        )
        jax.block_until_ready(mean_scores)
        elapsed = perf_counter() - started
        mean_values = np.asarray(mean_scores, dtype=np.float64)
        sum_values = np.asarray(sum_scores, dtype=np.float64)
        length_values = np.asarray(lengths, dtype=np.int64)
        order = np.argsort(-mean_values)
        ranked = [
            {
                "rank": rank + 1,
                "candidate": spec["candidates"][index],
                "mean_log_probability": float(mean_values[index]),
                "sum_log_probability": float(sum_values[index]),
                "token_count": int(length_values[index]),
                "token_ids": candidate_token_lists[index],
            }
            for rank, index in enumerate(order)
        ]
        top1 = ranked[0]["candidate"]
        margin = (
            float(mean_values[order[0]] - mean_values[order[1]])
            if len(order) > 1
            else None
        )
        results.append(
            {
                "case_id": case["case_id"],
                "record": str(record_path.resolve()),
                "record_sha256": digest_file(record_path),
                "task": task,
                "expected": case["expected"],
                "query": query,
                "top1": top1,
                "top1_matches_expected": top1 == case["expected"],
                "top1_margin_mean_log_probability": margin,
                "ranked_candidates": ranked,
                "score_seconds_including_first_compile": elapsed,
            }
        )

    matches = sum(case["top1_matches_expected"] for case in results)
    return {
        "schema": "proofalign.pi05-semantic-subtask-probe-result.v0",
        "mode": "frozen_candidate_scoring",
        "training_performed": False,
        "outcomes_read": False,
        "checkpoint": checkpoint_identity(checkpoint),
        "openpi_config": config_name,
        "jax_devices": [str(device) for device in jax.devices()],
        "checkpoint_load_seconds": load_seconds,
        "prompt_template": spec["prompt_template"],
        "candidates": spec["candidates"],
        "summary": {
            "case_count": len(results),
            "top1_expected_count": matches,
            "top1_expected_rate": matches / len(results),
        },
        "cases": results,
        "interpretation": spec.get("interpretation", {}),
    }


def main() -> None:
    args = parse_args()
    configure_openpi_path()
    spec_path = args.spec.resolve()
    spec = load_spec(spec_path, args.case_id)
    checkpoint = (args.checkpoint or Path(spec["checkpoint"])).resolve()
    config_name = args.openpi_config or spec["openpi_config"]
    if not checkpoint.exists():
        raise FileNotFoundError(checkpoint)

    result = (
        make_dry_run(spec, checkpoint, config_name)
        if args.dry_run
        else run_probe(spec, checkpoint, config_name)
    )
    result["spec"] = str(spec_path)
    result["spec_sha256"] = digest_file(spec_path)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
