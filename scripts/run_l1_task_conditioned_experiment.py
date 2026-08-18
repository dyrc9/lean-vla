#!/usr/bin/env python3
"""Execute one frozen L1 successor collection without outcome retries."""

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
from scripts.run_l1_task_conditioned_successor import (  # noqa: E402
    annotate_payload,
    patched_task_conditioned_l1_runtime,
)
from scripts.run_llm_template_semantic_v1 import patched_llm_template_runtime  # noqa: E402


class CollectionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_ancestor(commit: str) -> bool:
    return subprocess.run(
        ("git", "merge-base", "--is-ancestor", commit, "HEAD"),
        cwd=REPO_ROOT,
    ).returncode == 0


def validate(protocol_path: Path, protocol: Mapping[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.l1-task-conditioned-collection-protocol.v1"
        or protocol.get("status") != "frozen_no_outcomes_observed"
    ):
        raise CollectionError("protocol is not a frozen L1 successor collection")
    if not _git_ancestor(str(protocol["source"]["repository_commit"])):
        raise CollectionError("source commit is unavailable")
    for relative, expected in protocol["source"]["sha256"].items():
        if file_sha256(REPO_ROOT / relative) != expected:
            raise CollectionError(f"source binding differs: {relative}")
    design = REPO_ROOT / protocol["design_path"]
    catalog = REPO_ROOT / protocol["llm_template_catalog"]["path"]
    if file_sha256(design) != protocol["design_sha256"]:
        raise CollectionError("design checksum differs")
    if file_sha256(catalog) != protocol["llm_template_catalog"]["sha256"]:
        raise CollectionError("LLM template catalog checksum differs")
    schedule = protocol["schedule"]
    import hashlib

    if hashlib.sha256(canonical_text(schedule).encode()).hexdigest() != protocol["schedule_sha256"]:
        raise CollectionError("schedule checksum differs")
    if len(schedule) != int(protocol["expected_episode_count"]):
        raise CollectionError("expected episode count differs")
    specs = base_clean.build_specs(protocol)
    if len({spec.episode_id for spec in specs}) != len(specs):
        raise CollectionError("episode identities are not unique")
    if protocol["condition"] == "attacked" and len(protocol["attack_records"]) != 60:
        raise CollectionError("attacked population lacks 60 exact task records")


def _artifact_path(root: Path, spec: Any) -> Path:
    return (
        root
        / spec.episode_id
        / "episodes"
        / f"{spec.unit.suite}_task{spec.unit.task_id}_init{spec.unit.init_state_id}.json"
    )


def _terminal_payload(
    spec: Any,
    exc: BaseException,
    *,
    condition: str,
    bridge: Any,
) -> dict[str, Any]:
    l1, l2 = ARM_SWITCHES[spec.arm]
    return {
        "schema": "proofalign.l1-task-conditioned-terminal-exception.v1",
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
        "metadata": {
            "benchmark_name": spec.unit.suite,
            "task_id": spec.unit.task_id,
            "init_state_id": spec.unit.init_state_id,
            "seed": spec.unit.env_seed,
            "policy_seed": spec.unit.policy_seed,
            "l1_semantic_alignment": l1,
            "l2_execution_integrity": l2,
            "four_arm_label": spec.arm,
            "terminal_exception_record": True,
            "l1_task_conditioned_successor_active": l1,
            "retry_performed": False,
        },
        "llm_semantic_template_audit": (
            bridge.audit(l1_enabled=l1) if bridge is not None else None
        ),
        "terminal_exception": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "conservative_unsafe": True,
            "identity_and_trace_complete": False,
            "retry_performed": False,
        },
    }


def _collect_one(
    *,
    protocol: Mapping[str, Any],
    spec: Any,
    root: Path,
    args: Any,
    policy: Any,
    jax: Any,
    image_tools: Any,
    extractor: Any,
    bridge: Any,
) -> tuple[Path, dict[str, Any]]:
    episode_dir = root / spec.episode_id
    if episode_dir.exists():
        raise CollectionError(f"refusing to overwrite episode: {spec.episode_id}")
    (episode_dir / "episodes").mkdir(parents=True)
    (episode_dir / "videos").mkdir()
    started = perf_counter()
    try:
        payload = clean_runner._run_episode_adapter(
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
        l1, _l2 = ARM_SWITCHES[spec.arm]
        annotate_payload(payload, l1_enabled=l1)
        clean_runner.disabled_online.v1._persist_annotated_episode(payload)
        artifact = _artifact_path(root, spec)
        if not artifact.is_file():
            raise CollectionError("runner returned without persisted artifact")
        return artifact, {
            "terminal_exception": False,
            "wall_time_seconds": perf_counter() - started,
        }
    except Exception as exc:
        artifact = _artifact_path(root, spec)
        if artifact.exists():
            sidecar = episode_dir / "terminal_exception_sidecar.json"
            sidecar.write_text(
                canonical_text(
                    {
                        "schema": "proofalign.l1-task-conditioned-post-persist-exception.v1",
                        "episode_id": spec.episode_id,
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
            persisted = True
        else:
            payload = _terminal_payload(
                spec, exc, condition=str(protocol["condition"]), bridge=bridge
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(canonical_text(payload), encoding="utf-8")
            sidecar = None
            persisted = False
        return artifact, {
            "terminal_exception": True,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "artifact_persisted_before_exception": persisted,
            "exception_sidecar": (
                sidecar.relative_to(REPO_ROOT).as_posix() if sidecar else None
            ),
            "wall_time_seconds": perf_counter() - started,
        }


def execute(protocol_path: Path, policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    protocol = load_json_object(protocol_path)
    validate(protocol_path, protocol)
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root.exists():
        raise CollectionError(f"fresh output root exists: {root}")
    if shutil.disk_usage(REPO_ROOT).free < 20 * 1024**3:
        raise CollectionError("less than 20 GiB free disk")
    selected = p0b.validate_gpu_selection(
        {"execution_gate": {"selected_gpu_memory_used_mib_max_exclusive": 1000}},
        saber_io.gpu_inventory(),
        policy_gpu,
        egl_gpu,
    )
    root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device = base_clean._configure_environment(policy_gpu, egl_gpu)
    specs = base_clean.build_specs(protocol)
    first_args = base_clean._episode_args(
        protocol,
        spec=specs[0],
        output_dir=root / specs[0].episode_id,
        egl_ordinal=int(device["selected_egl_device_ordinal"]),
    )
    manifest_path = root / "run_manifest.json"
    ledger_path = root / "execution_ledger.jsonl"
    manifest = {
        "schema": "proofalign.l1-task-conditioned-collection-run.v1",
        "status": "loading_policy",
        "protocol_path": protocol_path.relative_to(REPO_ROOT).as_posix(),
        "protocol_sha256": file_sha256(protocol_path),
        "condition": protocol["condition"],
        "population": protocol["population"],
        "selected_gpu": selected,
        "device_mapping": device,
        "runtime": runtime,
        "scheduled_episode_count": len(specs),
        "completed_episode_ids": [],
        "terminal_exception_episode_ids": [],
        "retry_count": 0,
        "started_at": _now(),
    }
    saber_io.atomic_json(manifest_path, manifest)
    policy, jax, image_tools, _ = p0b.load_policy(
        {"victim": protocol["victim"], "episode_config": protocol["episode_constants"]},
        first_args,
    )
    extractor = p0b.make_constraint_extractor()
    manifest["status"] = "running"
    saber_io.atomic_json(manifest_path, manifest)
    legacy_context = (
        attacked_runner._patched_legacy()
        if protocol["condition"] == "attacked"
        else nullcontext()
    )
    with legacy_context:
        attack_context = (
            attacked_runner.legacy._patched_attacked(protocol)
            if protocol["condition"] == "attacked"
            else nullcontext()
        )
        with attack_context:
            catalog = REPO_ROOT / protocol["llm_template_catalog"]["path"]
            with patched_llm_template_runtime(catalog) as bridge:
                with patched_task_conditioned_l1_runtime(bridge):
                    for spec in specs:
                        args = base_clean._episode_args(
                            protocol,
                            spec=spec,
                            output_dir=root / spec.episode_id,
                            egl_ordinal=int(device["selected_egl_device_ordinal"]),
                        )
                        artifact, info = _collect_one(
                            protocol=protocol,
                            spec=spec,
                            root=root,
                            args=args,
                            policy=policy,
                            jax=jax,
                            image_tools=image_tools,
                            extractor=extractor,
                            bridge=bridge,
                        )
                        saber_io.append_ledger(
                            ledger_path,
                            {
                                "schema": "proofalign.l1-task-conditioned-ledger-row.v1",
                                "sequence_index": spec.sequence_index,
                                "episode_id": spec.episode_id,
                                "unit_id": spec.unit.unit_id,
                                "arm": spec.arm,
                                "artifact_path": artifact.relative_to(REPO_ROOT).as_posix(),
                                "artifact_sha256": file_sha256(artifact),
                                **info,
                            },
                        )
                        manifest["completed_episode_ids"].append(spec.episode_id)
                        if info["terminal_exception"]:
                            manifest["terminal_exception_episode_ids"].append(spec.episode_id)
                        saber_io.atomic_json(manifest_path, manifest)
    manifest.update(
        {
            "status": "complete",
            "completed_at": _now(),
            "record_count": len(manifest["completed_episode_ids"]),
        }
    )
    saber_io.atomic_json(manifest_path, manifest)
    p0b.write_checksums(root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--policy-gpu", type=int, required=True)
    parser.add_argument("--egl-gpu", type=int, required=True)
    args = parser.parse_args()
    value = execute(args.protocol.resolve(), args.policy_gpu, args.egl_gpu)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

