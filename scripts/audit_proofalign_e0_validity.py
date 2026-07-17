from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e0_v2_validity_protocol.json"
WORKER_MARKER = "PROOFALIGN_E0_VALIDITY_WORKER="


class E0ValidityError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _load_protocol(path: Path) -> dict[str, Any]:
    try:
        protocol = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E0ValidityError(f"cannot read validity protocol: {exc}") from exc
    if protocol.get("schema") != "proofalign.e0.validity-protocol.v1":
        raise E0ValidityError("unsupported E0 validity protocol schema")
    for key in ("parent_protocol", "manifest_registry"):
        item = protocol.get(key) or {}
        target = REPO_ROOT / str(item.get("path", ""))
        if not target.is_file() or _sha256(target) != item.get("sha256"):
            raise E0ValidityError(f"{key} path or digest differs from preregistration")
    benchmark = protocol.get("benchmark") or {}
    benchmark_root = REPO_ROOT / str(benchmark.get("root", ""))
    if _git_commit(benchmark_root) != benchmark.get("commit"):
        raise E0ValidityError("LIBERO-Safety commit differs from validity protocol")
    task_ids = tuple(int(item) for item in benchmark.get("task_ids", ()))
    if task_ids != tuple(range(15)):
        raise E0ValidityError("validity protocol must retain the frozen 15-task candidate set")
    return protocol


def _write_libero_config(config_dir: Path, benchmark_root: Path) -> None:
    source_root = (benchmark_root / "libero" / "libero").resolve()
    payload = {
        "benchmark_root": str(source_root),
        "bddl_files": str(source_root / "bddl_files"),
        "init_states": str(source_root / "init_files"),
        "datasets": str((benchmark_root / "libero" / "datasets").resolve()),
        "assets": str(source_root / "assets"),
    }
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _worker_result(protocol: dict[str, Any], task_id: int) -> dict[str, Any]:
    from proofalign.benchmark.libero_online_runner import (
        _environment_action_bounds,
        build_safety_spec,
        create_initialized_env,
        load_libero_task_runtime,
        parse_args as parse_episode_args,
    )
    from proofalign.benchmark.libero_online_wrapper import (
        LiberoStateObserver,
        unwrap_libero_env,
    )
    from proofalign.benchmark.libero_task_manifest import load_libero_task_manifest

    benchmark = protocol["benchmark"]
    benchmark_root = REPO_ROOT / str(benchmark["root"])
    registry_path = REPO_ROOT / str(protocol["manifest_registry"]["path"])
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = [
        item
        for item in registry["manifests"]
        if item["suite"] == benchmark["suite"] and item["task_id"] == task_id
    ]
    if len(entries) != 1:
        raise E0ValidityError(f"expected one frozen manifest entry for task {task_id}")
    bddl_path = benchmark_root / entries[0]["bddl_file"]
    manifest = load_libero_task_manifest(
        registry_path,
        suite=str(benchmark["suite"]),
        task_id=task_id,
        bddl_path=bddl_path,
    )
    args = parse_episode_args(
        [
            "--benchmark",
            str(benchmark["suite"]),
            "--task-id",
            str(task_id),
            "--init-state-id",
            str(benchmark["init_state_id"]),
            "--bddl-file",
            str(bddl_path),
            "--warmup-steps",
            "0",
            "--camera-height",
            "256",
            "--camera-width",
            "256",
            "--camera-names",
            "agentview,robot0_eye_in_hand",
            "--render-gpu-device-id",
            "-1",
            "--control-freq",
            "20",
            "--horizon",
            "1000",
            "--seed",
            str(benchmark["env_seed"]),
        ]
    )
    runtime = load_libero_task_runtime(
        benchmark_name=str(benchmark["suite"]),
        task_id=task_id,
        init_state_id=int(benchmark["init_state_id"]),
        bddl_file=str(bddl_path),
    )
    spec = build_safety_spec(args)
    env = create_initialized_env(runtime, args)
    try:
        observation = getattr(env, "_proofalign_initialized_observation", None)
        observer = LiberoStateObserver(contact_part_queries=(manifest.contact_query,))
        state = observer.observe(env, observation)
        raw_env = unwrap_libero_env(env)
        cost = _initial_cost(raw_env)
        unknown = {
            note.removeprefix("ctda_unknown_observation:")
            for note in state.notes
            if note.startswith("ctda_unknown_observation:")
        }
        contact_witnesses = [
            item for item in state.gripper_contact_parts if item.atom == manifest.goal_atom
        ]
        try:
            action_low, action_high = _environment_action_bounds(env)
        except Exception as exc:
            action_low = action_high = ()
            action_bounds_error = f"{type(exc).__name__}: {exc}"
        else:
            action_bounds_error = None
        poses = [state.robot_pose] + [item.pose for item in state.objects.values()]
        finite_poses = all(
            isfinite(value)
            for pose in poses
            for value in (pose.x, pose.y, pose.z)
        )
        sim = getattr(raw_env, "sim", getattr(env, "sim", None))
        sim_model = getattr(sim, "model", None)
        sim_data = getattr(sim, "data", None)
        current_ncon = _optional_int(getattr(sim_data, "ncon", None))
        nconmax = _optional_int(getattr(sim_model, "nconmax", None))
        gates = {
            "registered_init_present": runtime.init_state is not None,
            "selected_init_state_applied": bool(
                getattr(env, "_proofalign_selected_init_state_applied", False)
            ),
            "initialized_observation_source_is_set_init_state": (
                getattr(env, "_proofalign_initialized_observation_source", None)
                == "set_init_state"
            ),
            "manifest_target_observed": manifest.target_object in state.objects,
            "contact_query_observed": len(contact_witnesses) == 1
            and manifest.goal_atom not in unknown,
            "initial_goal_false": len(contact_witnesses) == 1
            and not contact_witnesses[0].satisfied,
            "finite_pose_observations": finite_poses,
            "collision_observed": "collision" not in unknown,
            "initial_no_collision": "collision" not in unknown and not state.collision,
            "cost_observed": "cost" not in unknown and cost is not None,
            "initial_no_cost": cost is not None and not any(bool(value) for value in cost.values()),
            "seven_dimensional_action_bounds": len(action_low) == len(action_high) == 7,
            "zero_action_inside_bounds": len(action_low) == len(action_high) == 7
            and all(low <= 0.0 <= high for low, high in zip(action_low, action_high)),
        }
        return {
            "suite": manifest.suite,
            "task_id": task_id,
            "task_name": manifest.task_name,
            "init_state_id": runtime.init_state_id,
            "env_seed": benchmark["env_seed"],
            "bddl_sha256": manifest.bddl_sha256,
            "manifest_digest": manifest.manifest_digest,
            "goal_atom": manifest.goal_atom,
            "policy_loaded": False,
            "env_step_called": False,
            "check_success_called": False,
            "gates": gates,
            "unknown_observations": sorted(unknown),
            "initial_cost": cost,
            "action_bounds": {
                "low": list(action_low),
                "high": list(action_high),
                "error": action_bounds_error,
            },
            "contact_capacity": {
                "snapshot_ncon": current_ncon,
                "model_nconmax": nconmax,
            },
            "state_digest": _state_digest(state),
        }
    finally:
        if hasattr(env, "close"):
            env.close()


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _initial_cost(raw_env: Any) -> dict[str, Any] | None:
    raw_cost = getattr(raw_env, "cost", None)
    if isinstance(raw_cost, dict):
        return dict(raw_cost)
    if raw_cost is not None:
        return {"cost": raw_cost}
    checker = getattr(raw_env, "_check_constraint", None)
    if not callable(checker):
        return None
    try:
        value = checker(False)
    except Exception:
        return None
    return dict(value) if isinstance(value, dict) else None


def _state_digest(state: Any) -> str:
    from proofalign.ctda import digest_legacy_state

    return digest_legacy_state(state)


def _parse_worker_output(text: str) -> dict[str, Any] | None:
    payloads = [line[len(WORKER_MARKER) :] for line in text.splitlines() if line.startswith(WORKER_MARKER)]
    if len(payloads) != 1:
        return None
    try:
        result = json.loads(payloads[0])
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def _warning_matches(text: str, patterns: list[str]) -> list[str]:
    lines = []
    for line in text.splitlines():
        if any(pattern.lower() in line.lower() for pattern in patterns):
            cleaned = " ".join(line.split())
            if cleaned and cleaned not in lines:
                lines.append(cleaned)
    return lines


def _classify(result: dict[str, Any] | None) -> tuple[str, list[str]]:
    if result is None:
        return "unknown", ["worker did not produce one valid result"]
    gates = result.get("gates") or {}
    availability = {"contact_query_observed", "collision_observed", "cost_observed"}
    missing = sorted(name for name in availability if gates.get(name) is not True)
    if missing:
        return "unknown", [f"missing required observation: {name}" for name in missing]
    failed = sorted(name for name, passed in gates.items() if passed is not True)
    if failed:
        return "invalid", [f"failed gate: {name}" for name in failed]
    return "valid", []


def audit(protocol_path: Path, *, artifact_dir: Path | None = None) -> dict[str, Any]:
    protocol = _load_protocol(protocol_path)
    benchmark = protocol["benchmark"]
    benchmark_root = REPO_ROOT / str(benchmark["root"])
    warning_patterns = [str(item) for item in protocol["init_gate"]["warning_patterns"]]
    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="proofalign-e0-validity-config-") as config_dir:
        _write_libero_config(Path(config_dir), benchmark_root)
        worker_env = dict(os.environ)
        worker_env["LIBERO_CONFIG_PATH"] = config_dir
        worker_env["LIBERO_SAFETY_ROOT"] = str(benchmark_root.resolve())
        worker_env.setdefault("MPLCONFIGDIR", "/tmp/proofalign-e0-validity-mpl")
        for task_id in benchmark["task_ids"]:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--protocol",
                    str(protocol_path),
                    "--worker-task-id",
                    str(task_id),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
                env=worker_env,
                cwd=REPO_ROOT,
            )
            combined = completed.stdout + "\n" + completed.stderr
            result = _parse_worker_output(completed.stdout)
            warnings = _warning_matches(combined, warning_patterns)
            if result is not None:
                result["gates"]["no_contact_capacity_warning"] = not warnings
            status, issues = _classify(result)
            record = result or {
                "suite": benchmark["suite"],
                "task_id": task_id,
                "init_state_id": benchmark["init_state_id"],
                "env_seed": benchmark["env_seed"],
                "gates": {},
            }
            record.update(
                {
                    "status": status,
                    "issues": issues,
                    "worker_returncode": completed.returncode,
                    "worker_output_sha256": sha256(combined.encode("utf-8")).hexdigest(),
                    "contact_capacity_warnings": warnings,
                }
            )
            if completed.returncode != 0:
                record["status"] = "unknown"
                record["issues"] = list(dict.fromkeys(issues + ["worker exited nonzero"]))
            if artifact_dir is not None:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / f"affordance_task{task_id}_init0.log").write_text(
                    combined,
                    encoding="utf-8",
                )
            records.append(record)
    counts = Counter(item["status"] for item in records)
    return {
        "schema": "proofalign.e0.validity-audit.v1",
        "protocol": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "benchmark_commit": _git_commit(benchmark_root),
        "outcome_blind_selection": True,
        "policy_loaded": False,
        "env_step_called": False,
        "check_success_called": False,
        "counts": {
            "total": len(records),
            "valid": counts["valid"],
            "invalid": counts["invalid"],
            "unknown": counts["unknown"],
            "fallback_eligible": counts["valid"],
        },
        "fallback_eligible_units": [
            {"suite": item["suite"], "task_id": item["task_id"], "init_state_id": item["init_state_id"]}
            for item in records
            if item["status"] == "valid"
        ],
        "tasks": records,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit E0 v2 candidate init validity without env.step.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--worker-task-id", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.expanduser().resolve()
    if args.worker_task_id is not None:
        try:
            protocol = _load_protocol(protocol_path)
            result = _worker_result(protocol, args.worker_task_id)
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(WORKER_MARKER + json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    try:
        report = audit(
            protocol_path,
            artifact_dir=(args.artifact_dir.expanduser().resolve() if args.artifact_dir else None),
        )
    except (E0ValidityError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, indent=2))
        return 1
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
