#!/usr/bin/env python3
"""Generate and freeze the two original-definition EDPA P1 patch assets.

This is deliberately an asset producer, not a simulator runner.  It reads the
published modified-LIBERO RLDS tree, uses the upstream JAX EDPA objective and
update implementation verbatim, and never imports SafeLIBERO or creates an
environment.  A fresh output root is terminal on both success and failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "experiments" / "edpa_safelibero_p1_protocol.json"


class AssetGateError(RuntimeError):
    pass


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_payload(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetGateError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AssetGateError(f"expected JSON object in {path}")
    return value


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def git_head(path: Path) -> str | None:
    result = run(["git", "rev-parse", "HEAD"], cwd=path)
    return result.stdout.strip() if result.returncode == 0 else None


def git_is_clean(path: Path) -> bool:
    result = run(["git", "status", "--porcelain=v1"], cwd=path)
    return result.returncode == 0 and not result.stdout.strip()


def git_source_is_clean(path: Path) -> bool:
    """Ignore only interpreter-created bytecode; never ignore source drift.

    The supplied EDPA checkout tracks a few ``__pycache__`` files.  Importing
    its official JAX module can change those bytes, so treating them as source
    mutation would make an otherwise content-addressed producer impossible to
    rerun.  Every executable source file remains individually hash-pinned.
    """
    result = run(["git", "status", "--porcelain=v1"], cwd=path)
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        text = line[3:]
        if " -> " in text:
            text = text.rsplit(" -> ", 1)[-1]
        candidate = Path(text)
        if candidate.suffix == ".pyc" and "__pycache__" in candidate.parts:
            continue
        return False
    return True


def repo_file(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def dataset_manifest(data_root: Path) -> dict[str, Any]:
    if not data_root.is_dir():
        raise AssetGateError(f"EDPA training-data root is missing: {data_root}")
    files: list[dict[str, Any]] = []
    for path in sorted(data_root.rglob("*")):
        if not path.is_file() or ".cache" in path.relative_to(data_root).parts:
            continue
        files.append(
            {
                "path": str(path.relative_to(data_root)),
                "bytes": path.stat().st_size,
                "sha256": digest_file(path),
            }
        )
    if not files:
        raise AssetGateError("EDPA training-data root has no content-addressed files")
    value = {
        "schema": "proofalign.edpa-p1-training-data-manifest.v1",
        "root": str(data_root),
        "files": files,
    }
    value["tree_sha256"] = digest_payload(files)
    return value


def validate_protocol(protocol: dict[str, Any], protocol_path: Path) -> None:
    if protocol.get("schema") != "proofalign.edpa-safelibero-p1-protocol.v1":
        raise AssetGateError("unexpected EDPA SafeLIBERO P1 protocol schema")
    if protocol.get("protocol_status") not in {
        "asset_generation_authorized",
        "frozen_execution_authorized",
    }:
        raise AssetGateError("protocol does not authorize EDPA asset generation")
    if protocol.get("victim_execution_authorized") is True and protocol.get("protocol_status") != "frozen_execution_authorized":
        raise AssetGateError("only a frozen P1 protocol may authorize the victim")
    generation = protocol.get("asset_generation")
    if not isinstance(generation, dict):
        raise AssetGateError("P1 protocol lacks asset_generation")
    exact = {
        "source_model_config": "pi0_fast_libero",
        "dataset_name": "libero_spatial_no_noops",
        "perturbation_ratio": 0.04,
        "alpha": 0.8,
        "max_steps": 50000,
        "iterations_per_step": 1,
        "step_size": 2 / 255,
        "image_size": 224,
        "batch_size": 2,
        "camera_views": ["primary", "wrist"],
        "downstream_outcomes_visible": False,
        "patch_selection_by_safelibero_outcome": False,
    }
    for key, expected in exact.items():
        if generation.get(key) != expected:
            raise AssetGateError(f"EDPA original-definition setting changed: {key}")
    if not protocol_path.is_file():
        raise AssetGateError("protocol path is missing")


def source_report(protocol: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    report: dict[str, Any] = {}
    blockers: list[str] = []
    source = protocol.get("source") or {}
    roots = {
        "edpa": ROOT / "external" / "EDPA_attack_defense",
        "openpi": ROOT / "external" / "openpi",
    }
    for name, root in roots.items():
        expected = source.get(f"{name}_commit")
        observed = git_head(root) if root.is_dir() else None
        report[f"{name}_commit"] = {"expected": expected, "observed": observed}
        if observed != expected:
            blockers.append(f"{name} commit mismatch")
        clean = git_source_is_clean(root) if name == "edpa" else git_is_clean(root)
        report[f"{name}_source_clean"] = clean
        if root.is_dir() and not clean:
            blockers.append(f"{name} checkout is dirty")
    for record in source.get("required_files", []):
        path = repo_file(str(record.get("path", "")))
        expected = record.get("sha256")
        observed = digest_file(path) if path.is_file() else None
        report[str(record.get("path"))] = {"expected": expected, "observed": observed}
        if not isinstance(expected, str) or observed != expected:
            blockers.append(f"source digest mismatch: {record.get('path')}")
    return report, blockers


def checkpoint_report(protocol: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    generation = protocol["asset_generation"]
    checkpoint = Path(generation["source_checkpoint"])
    expected = generation["source_checkpoint_sha256"]
    result: dict[str, Any] = {"path": str(checkpoint)}
    blockers: list[str] = []
    for relative, digest in expected.items():
        path = checkpoint / relative
        observed = digest_file(path) if path.is_file() else None
        result[relative] = {"expected": digest, "observed": observed}
        if observed != digest:
            blockers.append(f"generator checkpoint digest mismatch: {relative}")
    return result, blockers


def protocol_is_committed(protocol_path: Path) -> bool:
    try:
        relative = protocol_path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    tracked = run(["git", "ls-files", "--error-unmatch", str(relative)], cwd=ROOT)
    clean = run(["git", "diff", "--quiet", "HEAD", "--", str(relative)], cwd=ROOT)
    return tracked.returncode == 0 and clean.returncode == 0


def preflight(protocol: dict[str, Any], protocol_path: Path, output_root: Path) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path)
    source, blockers = source_report(protocol)
    checkpoint, checkpoint_blockers = checkpoint_report(protocol)
    blockers.extend(checkpoint_blockers)
    generation = protocol["asset_generation"]
    data_root = Path(generation["training_data_root"])
    manifest: dict[str, Any] | None = None
    try:
        manifest = dataset_manifest(data_root)
        expected = generation.get("training_data_tree_sha256")
        if expected is not None and manifest["tree_sha256"] != expected:
            blockers.append("training-data tree digest mismatch")
    except AssetGateError as exc:
        blockers.append(str(exc))
    if output_root.exists():
        blockers.append(f"fresh asset output root already exists: {output_root}")
    if not protocol_is_committed(protocol_path):
        blockers.append("asset protocol is not committed byte-identical to HEAD")
    return {
        "schema": "proofalign.edpa-safelibero-p1-asset-preflight.v1",
        "ready": not blockers,
        "protocol_sha256": digest_file(protocol_path),
        "source": source,
        "generator_checkpoint": checkpoint,
        "training_data": manifest,
        "output_root": str(output_root),
        "blockers": blockers,
    }


def _steps_from_dataset(data_root: Path) -> Iterable[dict[str, Any]]:
    import tensorflow_datasets as tfds

    builder = tfds.builder_from_directory(
        str(data_root / "libero_spatial_no_noops" / "1.0.0")
    )
    dataset = builder.as_dataset(split="train", shuffle_files=False)
    while True:
        for episode in tfds.as_numpy(dataset):
            for step in episode["steps"]:
                observation = step["observation"]
                yield {
                    "image": observation["image"],
                    "wrist_image": observation["wrist_image"],
                    "language_instruction": step["language_instruction"].decode("utf-8").lower(),
                }


def _batches(data_root: Path, batch_size: int) -> Iterable[dict[str, Any]]:
    import numpy as np

    iterator = _steps_from_dataset(data_root)
    while True:
        rows = [next(iterator) for _ in range(batch_size)]
        yield {
            "image": np.stack([item["image"] for item in rows]),
            "wrist_image": np.stack([item["wrist_image"] for item in rows]),
            "language_instruction": [item["language_instruction"] for item in rows],
        }


def _gpu_gate(gpu: int) -> dict[str, Any]:
    inventory = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.used",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if inventory.returncode != 0:
        raise AssetGateError(inventory.stderr.strip() or "nvidia-smi inventory failed")
    selected = None
    for line in inventory.stdout.splitlines():
        fields = [part.strip() for part in line.split(",")]
        if len(fields) == 3 and int(fields[0]) == gpu:
            selected = {"index": int(fields[0]), "uuid": fields[1], "memory_used_mib": int(fields[2])}
            break
    if selected is None:
        raise AssetGateError(f"selected GPU {gpu} is absent")
    if selected["memory_used_mib"] >= 4096:
        raise AssetGateError("selected GPU exceeds the 4096 MiB prelaunch asset gate")
    processes = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        check=False,
        capture_output=True,
        text=True,
    )
    if processes.returncode != 0:
        raise AssetGateError(processes.stderr.strip() or "nvidia-smi process query failed")
    if any(line.split(",", 1)[0].strip() == selected["uuid"] for line in processes.stdout.splitlines() if line.strip()):
        raise AssetGateError("selected GPU already has a compute process")
    return selected


def generate(protocol: dict[str, Any], protocol_path: Path, output_root: Path, gpu: int) -> dict[str, Any]:
    report = preflight(protocol, protocol_path, output_root)
    if not report["ready"]:
        raise AssetGateError("asset preflight failed: " + "; ".join(report["blockers"]))
    gpu_before = _gpu_gate(gpu)
    generation = protocol["asset_generation"]
    output_root.mkdir(parents=True, exist_ok=False)
    started = time.time_ns()
    manifest_path = output_root / "asset_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "proofalign.edpa-safelibero-p1-assets.v1",
                "status": "started",
                "started_unix_ns": started,
                "protocol_sha256": report["protocol_sha256"],
                "preflight": report,
                "gpu_physical_index": gpu,
                "gpu_before": gpu_before,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    try:
        # Keep TensorFlow's input pipeline on the host and isolate JAX to the
        # selected physical device before importing either framework.
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
        os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
        edpa_root = ROOT / "external" / "EDPA_attack_defense"
        sys.path.insert(0, str(edpa_root))
        import jax
        import jax.numpy as jnp
        import numpy as np
        from openpi.models import model as model_module
        from openpi.models import tokenizer as tokenizer_module
        from openpi.shared import download
        from openpi.training import config as config_module
        from VLAAttacker.jax.EDPA import EDPA
        from utils.pi0 import get_img_embedding, get_lang_embedding

        devices = jax.devices()
        if len(devices) != 1 or devices[0].platform != "gpu":
            raise AssetGateError(f"expected one selected JAX GPU, observed {devices}")
        cfg = SimpleNamespace(
            max_steps=generation["max_steps"],
            save_steps=generation["max_steps"],
            step_size=generation["step_size"],
            alpha=generation["alpha"],
            iterations=generation["iterations_per_step"],
            image_size=generation["image_size"],
            perturbation_ratio=generation["perturbation_ratio"],
            use_wandb=False,
            vla_path=generation["source_checkpoint"],
        )
        checkpoint = download.maybe_download(generation["source_checkpoint"])
        train_config = config_module.get_config(generation["source_model_config"])
        model = train_config.model.load(
            model_module.restore_params(checkpoint / "params", dtype=jnp.bfloat16)
        )
        tokenizer = tokenizer_module.PaligemmaTokenizer()
        patches: dict[str, dict[str, Any]] = {}
        for camera, batch_key in (("primary", "image"), ("wrist", "wrist_image")):
            # The released CLI creates one EDPA instance per invocation.  The
            # primary and wrist assets therefore need independent EMA state and
            # an independent deterministic traversal of the same source tree.
            attacker = EDPA(cfg)
            batches = _batches(Path(generation["training_data_root"]), generation["batch_size"])
            np.random.seed(int(generation["numpy_seed"]))
            patch_size = int(
                np.sqrt(generation["image_size"] ** 2 * generation["perturbation_ratio"])
            )
            patch = jax.random.uniform(
                jax.random.PRNGKey(int(generation["jax_seed"])),
                (3, patch_size, patch_size),
                minval=0.0,
                maxval=1.0,
            )
            last_cost: float | None = None
            for index in range(int(generation["max_steps"])):
                batch = next(batches)
                instructions, instruction_masks = zip(
                    *(tokenizer.tokenize(text) for text in batch["language_instruction"])
                )
                images = attacker.convert_images_format_and_normalize(batch[batch_key])
                image_embedding = get_img_embedding(model, attacker.preprocess_tensor_images(images))
                language_embedding = get_lang_embedding(model, jnp.array(instructions))
                patch, cost, _, _ = attacker.generate_one_step(
                    model,
                    images,
                    jnp.array(instructions),
                    jnp.array(instruction_masks),
                    patch,
                    images_embed=image_embedding,
                    lang_embed=language_embedding,
                )
                last_cost = float(cost)
            path = output_root / f"{camera}_perturbation.npy"
            np.save(path, np.asarray(patch))
            saved = np.load(path, allow_pickle=False)
            if (
                tuple(saved.shape) != (3, 44, 44)
                or not np.issubdtype(saved.dtype, np.floating)
                or not np.isfinite(saved).all()
                or float(saved.min()) < 0.0
                or float(saved.max()) > 1.0
            ):
                raise AssetGateError(f"generated {camera} patch failed content gate")
            patches[camera] = {
                "path": str(path),
                "sha256": digest_file(path),
                "shape": list(saved.shape),
                "dtype": str(saved.dtype),
                "minimum": float(saved.min()),
                "maximum": float(saved.max()),
                "last_loss": last_cost,
            }
        training = report["training_data"]
        assert isinstance(training, dict)
        training_path = output_root / "training_data_manifest.json"
        training_path.write_text(json.dumps(training, indent=2, sort_keys=True), encoding="utf-8")
        completed = {
            "schema": "proofalign.edpa-safelibero-p1-assets.v1",
            "status": "completed",
            "started_unix_ns": started,
            "completed_unix_ns": time.time_ns(),
            "protocol_sha256": report["protocol_sha256"],
            "preflight": report,
            "training_data_manifest": {
                "path": str(training_path),
                "sha256": digest_file(training_path),
                "tree_sha256": training["tree_sha256"],
            },
            "patches": patches,
            "generator_jax_devices": [str(device) for device in devices],
            "victim_or_simulator_outcomes_observed": False,
        }
        manifest_path.write_text(json.dumps(completed, indent=2, sort_keys=True), encoding="utf-8")
        return completed
    except Exception as exc:
        failure = load_json(manifest_path)
        failure.update(
            {
                "status": "terminal_failed",
                "failed_unix_ns": time.time_ns(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "victim_or_simulator_outcomes_observed": False,
            }
        )
        manifest_path.write_text(json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8")
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--gpu", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.preflight == args.execute:
        raise SystemExit("choose exactly one of --preflight or --execute")
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    output_text = args.output_root or Path(protocol["asset_generation"]["output_root"])
    output_root = Path(output_text).resolve()
    if args.preflight:
        print(json.dumps(preflight(protocol, protocol_path, output_root), indent=2, sort_keys=True))
        return 0
    if args.gpu is None:
        raise SystemExit("--execute requires --gpu PHYSICAL_ID")
    print(json.dumps(generate(protocol, protocol_path, output_root, args.gpu), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
