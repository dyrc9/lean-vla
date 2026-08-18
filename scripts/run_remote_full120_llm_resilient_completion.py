#!/usr/bin/env python3
"""Collect every frozen full-120 episode, recording fail-closed exceptions."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
import traceback
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import ARM_SWITCHES, canonical_text  # noqa: E402
from scripts import run_contact_phase_pick_up_clean_pilot as base_clean  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts import run_v15_bounded_state_triggered_task_utility_qualification as clean_runner  # noqa: E402
from scripts import run_v15_14_unified_force_envelope_attacked_task_utility_qualification as attacked_runner  # noqa: E402
from scripts.run_llm_template_semantic_v1 import patched_llm_template_runtime  # noqa: E402


PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_resilient_completion_v2_protocol_20260818.json"
CLEAN_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_clean_protocol_20260818.json"
ATTACKED_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json"
CATALOG = REPO_ROOT / "experiments/proofalign_llm_semantic_template_catalog_20260818.json"
PARENT_CLEAN_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_20260818_fresh1"
CLEAN_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_completion_20260818_fresh2"
PARENT_COMPLETION_ROOT = CLEAN_ROOT
CLEAN_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_completion_20260818_fresh3"
PARENT_COMPLETION_LOG = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_completion_execute_20260818.log"
ATTACKED_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_attacked_20260818_fresh1"
SOURCE_PATHS = (
    "scripts/run_remote_full120_llm_resilient_completion.py",
    "scripts/run_llm_template_semantic_v1.py",
    "src/proofalign/llm_semantic_templates.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/semantic_local_checker.py",
    "scripts/run_v15_bounded_state_triggered_task_utility_qualification.py",
    "scripts/run_v15_14_unified_force_envelope_attacked_task_utility_qualification.py",
)


class CompletionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise CompletionError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def freeze() -> dict[str, Any]:
    parent_manifest = PARENT_CLEAN_ROOT / "run_manifest.json"
    parent_sums = PARENT_CLEAN_ROOT / "SHA256SUMS"
    parent = load_json_object(parent_manifest)
    if (
        parent.get("status") != "terminal_failed_closed"
        or len(parent.get("completed_episode_ids", [])) != 426
        or "deadlock lacks a bounded shadow transition" not in str(parent.get("error"))
    ):
        raise CompletionError("bound parent stop state differs")
    clean = load_json_object(CLEAN_PROTOCOL)
    attacked = load_json_object(ATTACKED_PROTOCOL)
    partial_manifest = load_json_object(PARENT_COMPLETION_ROOT / "run_manifest.json")
    if (
        partial_manifest.get("status") != "running"
        or len(partial_manifest.get("completed_episode_ids", [])) != 47
        or len(partial_manifest.get("terminal_exception_episode_ids", [])) != 1
    ):
        raise CompletionError("bound clean completion partial state differs")
    orphan_spec = base_clean.build_specs(clean)[473]
    orphan_artifact = _artifact_path(PARENT_COMPLETION_ROOT, orphan_spec)
    if not orphan_artifact.is_file():
        raise CompletionError("persisted postcheck-exception artifact is absent")
    commit = _git("rev-parse", "HEAD")
    payload = {
        "schema": "proofalign.remote-full120-llm-resilient-completion-protocol.v2",
        "protocol_id": "proofalign-remote-full120-llm-resilient-completion-v2-20260818",
        "created_at": _now(),
        "source": {
            "repository_commit": commit,
            "repository_tree": _git("rev-parse", "HEAD^{tree}"),
            "sha256": {path: file_sha256(REPO_ROOT / path) for path in SOURCE_PATHS},
        },
        "catalog": {"path": CATALOG.relative_to(REPO_ROOT).as_posix(), "sha256": file_sha256(CATALOG)},
        "parent_clean": {
            "root": PARENT_CLEAN_ROOT.relative_to(REPO_ROOT).as_posix(),
            "manifest_sha256": file_sha256(parent_manifest),
            "checksums_sha256": file_sha256(parent_sums),
            "verified_completed_episode_count": 426,
            "terminal_error": parent["error"],
            "terminal_error_sequence_index": 426,
            "terminal_error_episode_id": clean["schedule"][426]["episode_id"],
            "retry_authorized": False,
        },
        "parent_clean_completion": {
            "root": PARENT_COMPLETION_ROOT.relative_to(REPO_ROOT).as_posix(),
            "manifest_sha256": file_sha256(PARENT_COMPLETION_ROOT / "run_manifest.json"),
            "ledger_sha256": file_sha256(PARENT_COMPLETION_ROOT / "execution_ledger.jsonl"),
            "checksums_sha256": file_sha256(PARENT_COMPLETION_ROOT / "SHA256SUMS"),
            "verified_record_count": 47,
            "covered_indices": list(range(426, 473)),
            "persisted_postcheck_exception_index": 473,
            "persisted_postcheck_exception_episode_id": orphan_spec.episode_id,
            "persisted_artifact_path": orphan_artifact.relative_to(REPO_ROOT).as_posix(),
            "persisted_artifact_sha256": file_sha256(orphan_artifact),
            "execution_log_path": PARENT_COMPLETION_LOG.relative_to(REPO_ROOT).as_posix(),
            "execution_log_sha256": file_sha256(PARENT_COMPLETION_LOG),
            "postcheck_exception": "V15BoundedStateTriggeredTaskUtilityError: task-runtime bounded-core coverage differs",
            "retry_authorized": False,
        },
        "clean_completion": {
            "source_protocol": CLEAN_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
            "source_protocol_sha256": file_sha256(CLEAN_PROTOCOL),
            "fresh_output_root": CLEAN_ROOT.relative_to(REPO_ROOT).as_posix(),
            "terminal_error_record_only_indices": [],
            "execute_indices": list(range(474, 480)),
            "expected_record_count": 6,
        },
        "attacked_collection": {
            "source_protocol": ATTACKED_PROTOCOL.relative_to(REPO_ROOT).as_posix(),
            "source_protocol_sha256": file_sha256(ATTACKED_PROTOCOL),
            "fresh_output_root": ATTACKED_ROOT.relative_to(REPO_ROOT).as_posix(),
            "execute_indices": list(range(480)),
            "expected_record_count": 480,
            "per_episode_exception_behavior": "record conservative invalid unsafe terminal artifact and continue; never retry",
        },
        "frozen_semantics": {
            "system_arm_actions_or_thresholds_changed": False,
            "attack_records_changed": False,
            "sample_or_schedule_changed": False,
            "outcome_conditioned_retry": False,
            "terminal_exception_counts_as_one_episode_attempt": True,
            "terminal_exception_task_success": False,
            "terminal_exception_unsafe": True,
            "missing_identity_or_raw_trace": "explicit invalid classification",
        },
    }
    PROTOCOL.write_text(canonical_text(payload), encoding="utf-8")
    return payload


def validate(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema") != "proofalign.remote-full120-llm-resilient-completion-protocol.v2":
        raise CompletionError("completion protocol schema differs")
    source = protocol["source"]
    if subprocess.run(
        ("git", "merge-base", "--is-ancestor", source["repository_commit"], "HEAD"),
        cwd=REPO_ROOT,
    ).returncode:
        raise CompletionError("completion source commit is unavailable")
    for relative, expected in source["sha256"].items():
        if file_sha256(REPO_ROOT / relative) != expected:
            raise CompletionError(f"completion source differs: {relative}")
    for section in ("clean_completion", "attacked_collection"):
        row = protocol[section]
        path = REPO_ROOT / row["source_protocol"]
        if file_sha256(path) != row["source_protocol_sha256"]:
            raise CompletionError(f"{section} source protocol differs")
    parent = protocol["parent_clean"]
    root = REPO_ROOT / parent["root"]
    if (
        file_sha256(root / "run_manifest.json") != parent["manifest_sha256"]
        or file_sha256(root / "SHA256SUMS") != parent["checksums_sha256"]
    ):
        raise CompletionError("parent clean stop artifacts differ")
    p0b.read_checksums(root)
    partial = protocol["parent_clean_completion"]
    partial_root = REPO_ROOT / partial["root"]
    if (
        file_sha256(partial_root / "run_manifest.json") != partial["manifest_sha256"]
        or file_sha256(partial_root / "execution_ledger.jsonl") != partial["ledger_sha256"]
        or file_sha256(partial_root / "SHA256SUMS") != partial["checksums_sha256"]
        or file_sha256(REPO_ROOT / partial["persisted_artifact_path"])
        != partial["persisted_artifact_sha256"]
        or file_sha256(REPO_ROOT / partial["execution_log_path"])
        != partial["execution_log_sha256"]
    ):
        raise CompletionError("parent clean completion artifacts differ")
    p0b.read_checksums(partial_root)


def _terminal_artifact(spec: Any, error: BaseException | str, *, condition: str, bridge: Any | None) -> dict[str, Any]:
    l1, l2 = ARM_SWITCHES[spec.arm]
    message = str(error)
    error_type = type(error).__name__ if isinstance(error, BaseException) else "BoundParentTerminalError"
    metadata = {
        "benchmark_name": spec.unit.suite,
        "task_id": spec.unit.task_id,
        "init_state_id": spec.unit.init_state_id,
        "seed": spec.unit.env_seed,
        "policy_seed": spec.unit.policy_seed,
        "l1_semantic_alignment": l1,
        "l2_execution_integrity": l2,
        "four_arm_label": spec.arm,
        "runner_variant": clean_runner.online.RUNNER_VARIANT,
        "initial_state_sha256": None,
        "initial_execution_observation_digest": None,
        "terminal_exception_record": True,
        "terminal_exception_type": error_type,
        "terminal_exception_message": message,
        "llm_semantic_template_active": l1,
        "llm_semantic_template_runtime_llm_calls": 0,
        "llm_semantic_template_attacked_prompt_visible": False,
        "post_failure_exploratory_method_extension": True,
        "bounded_state_triggered_recovery_active": l2,
        "task_runtime_method_version": "v15.14",
        "task_runtime_task_outcome_read": False,
    }
    audit = bridge.audit(l1_enabled=l1) if bridge is not None else None
    return {
        "schema": "proofalign.libero-terminal-exception-episode.v1",
        "suite": spec.unit.suite,
        "task_id": spec.unit.task_id,
        "init_state_id": spec.unit.init_state_id,
        "policy_seed": spec.unit.policy_seed,
        "condition": condition,
        "task_success": False,
        "strict_success_no_cost": False,
        "unsafe_cost_or_collision": True,
        "decision": "terminal_runner_exception",
        "trace": [],
        "observation_frame_audits": [],
        "semantic_events": [],
        "runtime": {"episode_wall_time_seconds": 0.0},
        "metadata": metadata,
        "llm_semantic_template_audit": audit,
        "terminal_exception": {
            "type": error_type,
            "message": message,
            "traceback": (
                traceback.format_exc()
                if isinstance(error, BaseException)
                else None
            ),
            "conservative_unsafe": True,
            "retry_performed": False,
            "identity_and_trace_complete": False,
        },
    }


def _artifact_path(root: Path, spec: Any) -> Path:
    return root / spec.episode_id / "episodes" / f"{spec.unit.suite}_task{spec.unit.task_id}_init{spec.unit.init_state_id}.json"


def _write_terminal(root: Path, spec: Any, payload: Mapping[str, Any]) -> Path:
    path = _artifact_path(root, spec)
    if path.exists():
        raise CompletionError(f"refusing to replace terminal artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent.parent / "videos").mkdir(exist_ok=True)
    path.write_text(canonical_text(payload), encoding="utf-8")
    return path


def _collect_one(
    *, spec: Any, source_protocol: Mapping[str, Any], root: Path, args: Any,
    policy: Any, jax: Any, image_tools: Any, extractor: Any, bridge: Any,
    condition: str,
) -> tuple[Path, dict[str, Any]]:
    episode_dir = root / spec.episode_id
    if episode_dir.exists():
        raise CompletionError(f"refusing to replace episode directory: {episode_dir}")
    (episode_dir / "episodes").mkdir(parents=True)
    (episode_dir / "videos").mkdir()
    started = perf_counter()
    try:
        clean_runner._run_episode_adapter(
            args=args,
            policy=policy,
            jax=jax,
            policy_seed=spec.unit.policy_seed,
            image_tools=image_tools,
            suite=spec.unit.suite,
            task_id=spec.unit.task_id,
            init_state_id=spec.unit.init_state_id,
            attack_records={},
            output_dir=episode_dir,
            observation_transform=None,
            wrist_observation_transform=None,
            constraint_signal_extractor=extractor,
        )
        artifact = _artifact_path(root, spec)
        if not artifact.is_file():
            raise CompletionError("runner returned without an episode artifact")
        return artifact, {"terminal_exception": False, "wall_time_seconds": perf_counter() - started}
    except Exception as exc:
        artifact = _artifact_path(root, spec)
        persisted_before_exception = artifact.is_file()
        sidecar = None
        if persisted_before_exception:
            sidecar = artifact.parent.parent / "terminal_exception_sidecar.json"
            sidecar.write_text(
                canonical_text(
                    {
                        "schema": "proofalign.persisted-episode-postcheck-exception.v1",
                        "episode_id": spec.episode_id,
                        "artifact_path": artifact.relative_to(REPO_ROOT).as_posix(),
                        "artifact_sha256": file_sha256(artifact),
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "traceback": traceback.format_exc(),
                        "conservative_invalid": True,
                        "retry_performed": False,
                    }
                ),
                encoding="utf-8",
            )
        else:
            payload = _terminal_artifact(spec, exc, condition=condition, bridge=bridge)
            artifact = _write_terminal(root, spec, payload)
        return artifact, {
            "terminal_exception": True,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "artifact_persisted_before_exception": persisted_before_exception,
            "exception_sidecar_path": (
                sidecar.relative_to(REPO_ROOT).as_posix() if sidecar else None
            ),
            "exception_sidecar_sha256": file_sha256(sidecar) if sidecar else None,
            "wall_time_seconds": perf_counter() - started,
        }


def execute(condition: str, policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    protocol = load_json_object(PROTOCOL)
    validate(protocol)
    section = protocol["clean_completion" if condition == "clean" else "attacked_collection"]
    source_path = REPO_ROOT / section["source_protocol"]
    source = load_json_object(source_path)
    root = REPO_ROOT / section["fresh_output_root"]
    if root.exists():
        raise CompletionError(f"fresh resilient root exists: {root}")
    if shutil.disk_usage(REPO_ROOT).free < 20 * 1024**3:
        raise CompletionError("less than 20 GiB free disk")
    selected = p0b.validate_gpu_selection(
        {"execution_gate": {"selected_gpu_memory_used_mib_max_exclusive": source["resource_gate"]["selected_gpu_memory_used_mib_max_exclusive"]}},
        saber_io.gpu_inventory(), policy_gpu, egl_gpu,
    )
    root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device = base_clean._configure_environment(policy_gpu, egl_gpu)
    specs = base_clean.build_specs(source)
    indices = list(section.get("execute_indices", []))
    all_indices = [*section.get("terminal_error_record_only_indices", []), *indices]
    first_spec = specs[indices[0]]
    first_args = base_clean._episode_args(
        source, spec=first_spec, output_dir=root,
        egl_ordinal=int(device["selected_egl_device_ordinal"]),
    )
    manifest_path = root / "run_manifest.json"
    ledger_path = root / "execution_ledger.jsonl"
    manifest = {
        "schema": "proofalign.remote-full120-resilient-collection-run.v1",
        "status": "loading_policy",
        "condition": condition,
        "protocol_sha256": file_sha256(PROTOCOL),
        "source_protocol_sha256": file_sha256(source_path),
        "selected_gpu": selected,
        "device_mapping": device,
        "runtime": runtime,
        "scheduled_indices": all_indices,
        "completed_episode_ids": [],
        "terminal_exception_episode_ids": [],
        "retry_count": 0,
    }
    saber_io.atomic_json(manifest_path, manifest)
    policy, jax, image_tools, _ = p0b.load_policy(
        {"victim": source["victim"], "episode_config": source["episode_constants"]},
        first_args,
    )
    extractor = p0b.make_constraint_extractor()
    manifest["status"] = "running"
    saber_io.atomic_json(manifest_path, manifest)
    attack_context = nullcontext()
    legacy_context = nullcontext()
    if condition == "attacked":
        legacy_context = attacked_runner._patched_legacy()
    with legacy_context:
        if condition == "attacked":
            attack_context = attacked_runner.legacy._patched_attacked(source)
        with attack_context:
            with patched_llm_template_runtime(CATALOG) as bridge:
                for index in section.get("terminal_error_record_only_indices", []):
                    spec = specs[index]
                    payload = _terminal_artifact(
                        spec, protocol["parent_clean"]["terminal_error"],
                        condition=condition, bridge=None,
                    )
                    artifact = _write_terminal(root, spec, payload)
                    info = {"terminal_exception": True, "bound_parent_record": True}
                    saber_io.append_ledger(ledger_path, {
                        "schema": "proofalign.remote-full120-resilient-execution-ledger-row.v1",
                        "sequence_index": index,
                        "episode_id": spec.episode_id,
                        "unit_id": spec.unit.unit_id,
                        "arm": spec.arm,
                        "artifact_path": artifact.relative_to(REPO_ROOT).as_posix(),
                        "artifact_sha256": file_sha256(artifact),
                        **info,
                    })
                    manifest["completed_episode_ids"].append(spec.episode_id)
                    manifest["terminal_exception_episode_ids"].append(spec.episode_id)
                    saber_io.atomic_json(manifest_path, manifest)
                for index in indices:
                    spec = specs[index]
                    args = base_clean._episode_args(
                        source, spec=spec, output_dir=root / spec.episode_id,
                        egl_ordinal=int(device["selected_egl_device_ordinal"]),
                    )
                    artifact, info = _collect_one(
                        spec=spec, source_protocol=source, root=root, args=args,
                        policy=policy, jax=jax, image_tools=image_tools,
                        extractor=extractor, bridge=bridge, condition=condition,
                    )
                    saber_io.append_ledger(ledger_path, {
                        "schema": "proofalign.remote-full120-resilient-execution-ledger-row.v1",
                        "sequence_index": index,
                        "episode_id": spec.episode_id,
                        "unit_id": spec.unit.unit_id,
                        "arm": spec.arm,
                        "artifact_path": artifact.relative_to(REPO_ROOT).as_posix(),
                        "artifact_sha256": file_sha256(artifact),
                        **info,
                    })
                    manifest["completed_episode_ids"].append(spec.episode_id)
                    if info["terminal_exception"]:
                        manifest["terminal_exception_episode_ids"].append(spec.episode_id)
                    saber_io.atomic_json(manifest_path, manifest)
    manifest["status"] = "complete"
    manifest["completed_at"] = _now()
    manifest["record_count"] = len(manifest["completed_episode_ids"])
    saber_io.atomic_json(manifest_path, manifest)
    p0b.write_checksums(root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--condition", choices=("clean", "attacked"), default="clean")
    parser.add_argument("--policy-gpu", type=int, default=0)
    parser.add_argument("--egl-gpu", type=int, default=1)
    args = parser.parse_args()
    if args.freeze:
        result = freeze()
    elif args.check:
        payload = load_json_object(PROTOCOL)
        validate(payload)
        result = {"valid": True, "protocol_sha256": file_sha256(PROTOCOL)}
    else:
        result = execute(args.condition, args.policy_gpu, args.egl_gpu)
    print(canonical_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
