#!/usr/bin/env python3
"""Freeze and run the outcome-blind full-120 LLM-template qualification."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.semantic_local_checker import TrustedLocalObservation  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_llm_template_semantic_v1 import TemplateGeometryBridge  # noqa: E402


SCHEMA = "proofalign.llm-semantic-template-outcome-blind-qualification-protocol.v1"
ROW_SCHEMA = "proofalign.llm-semantic-template-outcome-blind-qualification-row.v1"
SUMMARY_SCHEMA = "proofalign.llm-semantic-template-outcome-blind-qualification-summary.v1"
PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_llm_semantic_template_qualification_20260818.json"
CATALOG_PATH = REPO_ROOT / "experiments/proofalign_llm_semantic_template_catalog_20260818.json"
POPULATION_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_clean_protocol_20260818.json"
OUTPUT_ROOT = REPO_ROOT / "results/proofalign_llm_semantic_template_qualification_20260818_fresh1"
SOURCE_PATHS = (
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/llm_semantic_templates.py",
    "scripts/run_llm_template_semantic_v1.py",
    "scripts/run_llm_semantic_template_qualification.py",
)


class QualificationError(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise QualificationError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def freeze() -> dict[str, Any]:
    population = load_json_object(POPULATION_PATH)
    catalog = load_json_object(CATALOG_PATH)
    if len(population.get("workloads", [])) != 60 or catalog.get("template_count") != 60:
        raise QualificationError("full-120 workload or catalog population differs")
    commit = _git("rev-parse", "HEAD")
    protocol = {
        "schema": SCHEMA,
        "protocol_id": "proofalign-full120-llm-template-outcome-blind-qualification-20260818",
        "created_at": _now(),
        "fresh_output_root": OUTPUT_ROOT.relative_to(REPO_ROOT).as_posix(),
        "execution_authorization": {
            "environment_initialization": True,
            "policy_load": False,
            "policy_inference": False,
            "env_step": False,
            "task_outcome_read": False,
            "attacked_prompt_read": False,
        },
        "population": {
            "path": POPULATION_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(POPULATION_PATH),
            "workload_count": 60,
            "evaluation_unit_count_after_replication": 120,
            "outcome_based_selection": False,
        },
        "catalog": {
            "path": CATALOG_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(CATALOG_PATH),
            "template_count": 60,
            "runtime_llm_calls": 0,
            "attacked_prompt_visible": False,
        },
        "gates": {
            "valid_row_count": 60,
            "compiled_graph_count": 60,
            "all_goal_geometry_resolved": True,
            "part_resolution_failure_count": 0,
            "policy_load_count": 0,
            "policy_inference_count": 0,
            "env_step_count": 0,
            "task_outcome_read_count": 0,
        },
        "victim": load_json_object(POPULATION_PATH)["victim"],
        "environment_seed": 43,
        "source": {
            "repository_commit": commit,
            "repository_tree": _git("rev-parse", "HEAD^{tree}"),
            "sha256": {
                path: file_sha256(REPO_ROOT / path) for path in SOURCE_PATHS
            },
        },
    }
    PROTOCOL_PATH.write_text(canonical_text(protocol), encoding="utf-8")
    return protocol


def validate_protocol(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema") != SCHEMA:
        raise QualificationError("qualification protocol schema differs")
    expected_auth = {
        "environment_initialization": True,
        "policy_load": False,
        "policy_inference": False,
        "env_step": False,
        "task_outcome_read": False,
        "attacked_prompt_read": False,
    }
    if protocol.get("execution_authorization") != expected_auth:
        raise QualificationError("qualification authorization differs")
    source = protocol["source"]
    if subprocess.run(
        ("git", "merge-base", "--is-ancestor", source["repository_commit"], "HEAD"),
        cwd=REPO_ROOT,
    ).returncode:
        raise QualificationError("bound source commit is not an ancestor")
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise QualificationError(f"source checksum differs: {relative}")
    for section in ("population", "catalog"):
        binding = protocol[section]
        path = REPO_ROOT / binding["path"]
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise QualificationError(f"{section} checksum differs")


def _args(protocol: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        checkpoint_dir=Path(protocol["victim"]["checkpoint"]),
        env_img_res=256,
        camera_names="agentview,robot0_eye_in_hand",
        render_gpu_device_id=0,
        control_freq=20,
        horizon=1000,
        seed=int(protocol["environment_seed"]),
    )


def _qualify_one(
    workload: Mapping[str, Any], bridge: TemplateGeometryBridge, args: SimpleNamespace
) -> dict[str, Any]:
    bddl_path = (REPO_ROOT / str(workload["bddl_path"])).resolve()
    bddl_text = bddl_path.read_text(encoding="utf-8")
    bridge.begin_episode()
    graph = bridge.compile(bddl_text)
    runtime = base.load_libero_task_runtime(
        benchmark_name=str(workload["suite"]),
        task_id=int(workload["task_id"]),
        init_state_id=int(workload["init_state_id"]),
        bddl_file=str(bddl_path),
    )
    if Path(runtime.bddl_file).resolve() != bddl_path:
        raise QualificationError("runtime BDDL path differs from frozen workload")
    env = base.create_env(runtime, args)
    bridge.bind_env(env)
    try:
        observation = env.reset()
        if runtime.init_state is not None:
            observation = env.set_init_state(runtime.init_state)
        if observation is None:
            observation = base.get_observation(env)
        local = TrustedLocalObservation.from_libero_observation(observation, state_epoch=0)
        entities = {item.entity_id: item for item in local.entity_positions}
        part = bridge.resolve_part_target(local.eef_position)
        if part is not None:
            entities[part.entity_id] = part
        local = TrustedLocalObservation(
            state_epoch=0,
            eef_position=local.eef_position,
            gripper_qpos=local.gripper_qpos,
            entity_positions=tuple(entities.values()),
        )
        goal_checks = []
        for goal in graph.goals:
            target_resolved = local.position(goal.target) is not None
            destination_resolved = (
                True if goal.destination is None else local.position(goal.destination) is not None
            )
            goal_checks.append(
                {
                    "predicate": goal.predicate,
                    "target": goal.target,
                    "destination": goal.destination,
                    "part": goal.part,
                    "target_geometry_resolved": target_resolved,
                    "destination_geometry_resolved": destination_resolved,
                    "resolved": target_resolved and destination_resolved,
                }
            )
        audit = bridge.audit(l1_enabled=True)
        return {
            "schema": ROW_SCHEMA,
            "base_pair_id": workload["base_pair_id"],
            "suite": workload["suite"],
            "task_id": workload["task_id"],
            "init_state_id": workload["init_state_id"],
            "bddl_path": workload["bddl_path"],
            "bddl_sha256": file_sha256(bddl_path),
            "runtime_bddl_path_matches": True,
            "graph_digest": graph.graph_digest,
            "goal_checks": goal_checks,
            "all_goal_geometry_resolved": all(row["resolved"] for row in goal_checks),
            "runtime_audit": audit,
            "valid": True,
            "policy_load_count": 0,
            "policy_inference_count": 0,
            "env_step_count": 0,
            "task_outcome_read_count": 0,
            "attacked_prompt_read_count": 0,
        }
    finally:
        env.close()


def _summary(protocol: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(
        check["predicate"] for row in rows for check in row.get("goal_checks", [])
    )
    totals = {
        key: sum(int(row.get(key, 0)) for row in rows)
        for key in (
            "policy_load_count",
            "policy_inference_count",
            "env_step_count",
            "task_outcome_read_count",
            "attacked_prompt_read_count",
        )
    }
    valid = sum(row.get("valid") is True for row in rows)
    compiled = sum(bool(row.get("graph_digest")) for row in rows)
    geometry = all(row.get("all_goal_geometry_resolved") is True for row in rows)
    part_failures = sum(
        int(row["runtime_audit"]["part_resolution_failure_count"]) for row in rows
    )
    conditions = {
        "valid_row_count": valid == 60,
        "compiled_graph_count": compiled == 60,
        "all_goal_geometry_resolved": geometry,
        "part_resolution_failure_count": part_failures == 0,
        "policy_load_count": totals["policy_load_count"] == 0,
        "policy_inference_count": totals["policy_inference_count"] == 0,
        "env_step_count": totals["env_step_count"] == 0,
        "task_outcome_read_count": totals["task_outcome_read_count"] == 0,
        "attacked_prompt_read_count": totals["attacked_prompt_read_count"] == 0,
    }
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "llm_semantic_template_qualification_pass"
            if all(conditions.values())
            else "llm_semantic_template_qualification_nonpass"
        ),
        "pass": all(conditions.values()),
        "row_count": len(rows),
        "valid_row_count": valid,
        "compiled_graph_count": compiled,
        "goal_predicate_counts": dict(sorted(counts.items())),
        "part_resolution_failure_count": part_failures,
        **totals,
        "conditions": conditions,
    }


def execute(protocol: Mapping[str, Any], egl_gpu: int) -> dict[str, Any]:
    validate_protocol(protocol)
    if OUTPUT_ROOT.exists():
        raise QualificationError(f"fresh qualification root exists: {OUTPUT_ROOT}")
    if shutil.disk_usage(REPO_ROOT).free < 1024**3:
        raise QualificationError("less than 1 GiB free disk")
    OUTPUT_ROOT.mkdir(parents=True)
    runtime_config = p0b.ensure_libero_runtime_config(OUTPUT_ROOT)
    os.environ.update(
        {
            "LIBERO_CONFIG_PATH": runtime_config["directory"],
            "LIBERO_SAFETY_ROOT": str(REPO_ROOT / "external/LIBERO-Safety"),
            "CUDA_VISIBLE_DEVICES": str(egl_gpu),
            "MUJOCO_EGL_DEVICE_ID": "0",
            "MUJOCO_GL": "egl",
            "PYOPENGL_PLATFORM": "egl",
        }
    )
    args = _args(protocol)
    base.configure_paths(args)
    population = load_json_object(REPO_ROOT / protocol["population"]["path"])
    bridge = TemplateGeometryBridge(REPO_ROOT / protocol["catalog"]["path"])
    ledger = OUTPUT_ROOT / "qualification_ledger.jsonl"
    manifest = {
        "schema": "proofalign.llm-semantic-template-qualification-run.v1",
        "status": "running",
        "created_at": _now(),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "runtime_config": runtime_config,
        "outcomes_observed": False,
        "policy_loaded": False,
        "env_step_count": 0,
    }
    saber_io.atomic_json(OUTPUT_ROOT / "run_manifest.json", manifest)
    rows = []
    for index, workload in enumerate(population["workloads"]):
        row = {"qualification_index": index, **_qualify_one(workload, bridge, args)}
        saber_io.append_ledger(ledger, row)
        rows.append(row)
    summary = _summary(protocol, rows)
    saber_io.atomic_json(OUTPUT_ROOT / "summary.json", summary)
    manifest.update({"status": "complete", "completed_at": _now(), "summary": summary})
    saber_io.atomic_json(OUTPUT_ROOT / "run_manifest.json", manifest)
    checksum_rows = []
    for path in sorted(OUTPUT_ROOT.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_rows.append(f"{file_sha256(path)}  {path.relative_to(OUTPUT_ROOT).as_posix()}")
    (OUTPUT_ROOT / "checksums.sha256").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    if not summary["pass"]:
        raise QualificationError(f"qualification nonpass: {summary['conditions']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--egl-gpu", type=int, default=0)
    args = parser.parse_args()
    if args.freeze:
        result = freeze()
    else:
        protocol = load_json_object(PROTOCOL_PATH)
        if args.check:
            validate_protocol(protocol)
            result = {"valid": True, "protocol_sha256": file_sha256(PROTOCOL_PATH)}
        else:
            result = execute(protocol, args.egl_gpu)
    print(canonical_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
