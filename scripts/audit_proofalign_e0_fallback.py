from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from time import monotonic_ns
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e0_v2_fallback_protocol.json"
WORKER_MARKER = "PROOFALIGN_E0_FALLBACK_WORKER="


class E0FallbackError(RuntimeError):
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


def _bound_file(item: dict[str, Any], label: str) -> Path:
    path = REPO_ROOT / str(item.get("path", ""))
    expected = str(item.get("sha256", ""))
    if not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise E0FallbackError(f"{label} is not a readable SHA-bound file")
    if _sha256(path) != expected:
        raise E0FallbackError(f"{label} differs from the fallback protocol")
    return path


def _load_protocol(path: Path) -> dict[str, Any]:
    try:
        protocol = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E0FallbackError(f"cannot read fallback protocol: {exc}") from exc
    if protocol.get("schema") != "proofalign.e0.fallback-protocol.v1":
        raise E0FallbackError("unsupported E0 fallback protocol schema")
    inputs = protocol.get("inputs") or {}
    required = (
        "candidate_protocol",
        "validity_protocol",
        "validity_summary",
        "task_manifest_registry",
        "fallback_registry",
        "audit_script",
    )
    bound = {name: _bound_file(inputs.get(name) or {}, name) for name in required}
    if bound["audit_script"].resolve() != Path(__file__).resolve():
        raise E0FallbackError("fallback protocol audit_script does not identify this auditor")
    benchmark = protocol.get("benchmark") or {}
    benchmark_root = REPO_ROOT / str(benchmark.get("root", ""))
    if _git_commit(benchmark_root) != benchmark.get("commit"):
        raise E0FallbackError("LIBERO-Safety commit differs from fallback protocol")
    if benchmark.get("suite") != "affordance" or benchmark.get("init_state_id") != 0:
        raise E0FallbackError("fallback protocol must retain affordance/init-0")
    execution = protocol.get("execution") or {}
    if execution.get("env_seeds") != [7, 17, 27]:
        raise E0FallbackError("fallback protocol must retain the frozen seed sequence")
    if execution.get("repetitions_per_unit") != 3:
        raise E0FallbackError("fallback protocol must retain three repetitions per unit")
    if execution.get("fallback_action") != [0, 0, 0, 0, 0, 0, 0]:
        raise E0FallbackError("fallback protocol action is not the canonical zero hold")
    if execution.get("max_switch_latency_ns") != 100_000_000:
        raise E0FallbackError("fallback protocol switch bound changed")

    summary = json.loads(bound["validity_summary"].read_text(encoding="utf-8"))
    eligible = [
        int(item["task_id"])
        for item in summary.get("units", [])
        if item.get("status") == "valid"
    ]
    if eligible != list(range(15)) or summary.get("counts", {}).get("fallback_eligible") != 15:
        raise E0FallbackError("validity summary does not freeze exactly task 0..14")
    frozen_units = protocol.get("eligible_units")
    expected_units = [
        {"suite": "affordance", "task_id": task_id, "init_state_id": 0}
        for task_id in range(15)
    ]
    if frozen_units != expected_units:
        raise E0FallbackError("fallback eligible units differ from the validity-pass set")

    registry = json.loads(bound["fallback_registry"].read_text(encoding="utf-8"))
    _validate_fallback_registry(registry, protocol, bound["fallback_registry"])
    protocol["_bound_paths"] = {name: str(item) for name, item in bound.items()}
    protocol["_fallback_registry"] = registry
    protocol["_validity_summary"] = summary
    return protocol


def _validate_fallback_registry(
    registry: dict[str, Any],
    protocol: dict[str, Any],
    registry_path: Path,
) -> None:
    if registry.get("schema") != "proofalign.e0.fallback-registry.v1":
        raise E0FallbackError("unsupported fallback registry schema")
    entries = registry.get("artifacts")
    if not isinstance(entries, list) or len(entries) != 15:
        raise E0FallbackError("fallback registry must bind 15 artifacts")
    expected_ids = list(range(15))
    if [item.get("task_id") for item in entries] != expected_ids:
        raise E0FallbackError("fallback registry task order differs from 0..14")
    for entry in entries:
        if entry.get("suite") != "affordance" or entry.get("init_state_id") != 0:
            raise E0FallbackError("fallback registry unit identity changed")
        artifact = REPO_ROOT / str(entry.get("path", ""))
        expected = str(entry.get("sha256", ""))
        if not artifact.is_file() or _sha256(artifact) != expected:
            raise E0FallbackError(
                f"fallback artifact for task {entry.get('task_id')} differs from registry"
            )
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        if payload.get("spec_id") != f"affordance:{entry['task_id']}:0":
            raise E0FallbackError("fallback artifact spec_id is not task-bound")
        if payload.get("fallback_action") != protocol["execution"]["fallback_action"]:
            raise E0FallbackError("fallback artifact action differs from protocol")
        if payload.get("worst_case_switch_latency_ns") != protocol["execution"][
            "max_switch_latency_ns"
        ]:
            raise E0FallbackError("fallback artifact switch bound differs from protocol")
    declared = Path(str(protocol["inputs"]["fallback_registry"]["path"]))
    if declared.is_absolute() or (REPO_ROOT / declared).resolve() != registry_path.resolve():
        raise E0FallbackError("fallback registry path must be repository-relative and exact")


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


class _CountingEnv:
    def __init__(self, env: Any):
        self.env = env
        self.step_count = 0
        self.applied_actions: list[list[float]] = []

    def step(self, action: Any) -> Any:
        self.step_count += 1
        self.applied_actions.append([float(value) for value in action])
        return self.env.step(action)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.env, name)


def _unknown_observations(state: Any) -> set[str]:
    prefix = "ctda_unknown_observation:"
    return {
        str(note).removeprefix(prefix)
        for note in getattr(state, "notes", ())
        if str(note).startswith(prefix)
    }


def _worker_result(
    protocol: dict[str, Any],
    *,
    task_id: int,
    env_seed: int,
    repetition: int,
) -> dict[str, Any]:
    from proofalign.benchmark.libero_online_runner import (
        _configure_ctda,
        _load_ctda_task_manifest,
        _prepare_ctda_trust_root,
        build_safety_spec,
        create_initialized_env,
        load_libero_task_runtime,
        parse_args as parse_episode_args,
    )
    from proofalign.benchmark.libero_online_wrapper import ProofAlignLiberoWrapper
    from proofalign.ctda import digest_legacy_state

    benchmark = protocol["benchmark"]
    execution = protocol["execution"]
    benchmark_root = REPO_ROOT / str(benchmark["root"])
    manifest_registry = Path(protocol["_bound_paths"]["task_manifest_registry"])
    manifest_registry_sha = protocol["inputs"]["task_manifest_registry"]["sha256"]
    entries = [
        item
        for item in protocol["_fallback_registry"]["artifacts"]
        if item["task_id"] == task_id
    ]
    if len(entries) != 1:
        raise E0FallbackError(f"expected one fallback artifact for task {task_id}")
    fallback_path = REPO_ROOT / entries[0]["path"]

    task_registry = json.loads(manifest_registry.read_text(encoding="utf-8"))
    task_entries = [
        item
        for item in task_registry["manifests"]
        if item["suite"] == "affordance" and item["task_id"] == task_id
    ]
    if len(task_entries) != 1:
        raise E0FallbackError(f"expected one exact task manifest for task {task_id}")
    bddl_path = benchmark_root / task_entries[0]["bddl_file"]
    nonce = f"e0-fallback-affordance-t{task_id}-i0-s{env_seed}-r{repetition}"
    args = parse_episode_args(
        [
            "--benchmark", "affordance",
            "--task-id", str(task_id),
            "--init-state-id", "0",
            "--bddl-file", str(bddl_path),
            "--ctda",
            "--ctda-fallback-witness", str(fallback_path),
            "--ctda-fallback-witness-sha256", entries[0]["sha256"],
            "--ctda-task-manifest-registry", str(manifest_registry),
            "--ctda-task-manifest-registry-sha256", manifest_registry_sha,
            "--ctda-evidence-mode", "local-simulator-exact-allowlist",
            "--ctda-evaluator", "ctda-python-reference",
            "--ctda-episode-nonce", nonce,
            "--ctda-artifact-dir", f"/tmp/proofalign-e0-fallback-wire/t{task_id}-s{env_seed}-r{repetition}",
            "--warmup-steps", "0",
            "--camera-height", "256",
            "--camera-width", "256",
            "--camera-names", "agentview,robot0_eye_in_hand",
            "--render-gpu-device-id", "-1",
            "--control-freq", "20",
            "--horizon", "1000",
            "--seed", str(env_seed),
        ]
    )
    runtime = load_libero_task_runtime(
        benchmark_name="affordance",
        task_id=task_id,
        init_state_id=0,
        bddl_file=str(bddl_path),
    )
    runtime = _prepare_ctda_trust_root(runtime, args)
    task_manifest = _load_ctda_task_manifest(runtime, args)
    if task_manifest is None:
        raise E0FallbackError("exact task manifest unexpectedly unavailable")
    spec = build_safety_spec(args)
    env = create_initialized_env(runtime, args)
    try:
        wrapper = ProofAlignLiberoWrapper(env, runtime.instruction, spec, max_chunk_steps=1)
        wrapper.state_observer.contact_part_queries = (task_manifest.contact_query,)
        wrapper.current_observation = getattr(env, "_proofalign_initialized_observation", None)
        wrapper.current_state = wrapper.state_observer.observe(env, wrapper.current_observation)
        initial_state_digest = digest_legacy_state(wrapper.current_state)
        validity_rows = [
            item
            for item in protocol["_validity_summary"]["units"]
            if item["task_id"] == task_id
        ]
        if len(validity_rows) != 1:
            raise E0FallbackError("validity summary unit is missing or duplicated")
        _configure_ctda(wrapper, runtime, spec, args, task_manifest=task_manifest)

        counting_env = _CountingEnv(env)
        wrapper.env = counting_env
        trigger_ns = monotonic_ns()
        (
            _observation,
            reward,
            done,
            env_info,
            state_after,
            receipt,
            _trace,
            fallback_env_seconds,
        ) = wrapper._execute_ctda_fallback(
            trigger="e0_fallback_validity_gate",
            triggered_at_ns=trigger_ns,
            state_before=wrapper.current_state,
        )
        unknown = _unknown_observations(state_after)
        contact = [
            item
            for item in state_after.gripper_contact_parts
            if item.atom == task_manifest.goal_atom
        ]
        switch_latency_ns = receipt.observed_at_ns - receipt.triggered_at_ns
        expected_action = [float(value) for value in execution["fallback_action"]]
        gates = {
            "selected_init_state_applied": bool(
                getattr(env, "_proofalign_selected_init_state_applied", False)
            ),
            "initialized_observation_source_is_set_init_state": (
                getattr(env, "_proofalign_initialized_observation_source", None)
                == "set_init_state"
            ),
            "initial_state_matches_validity_gate": (
                initial_state_digest == validity_rows[0]["state_digest"]
            ),
            "exactly_one_env_step": counting_env.step_count == 1,
            "exact_zero_action_applied": counting_env.applied_actions == [expected_action],
            "typed_simulator_applied": receipt.command_application == "typed_simulator_applied",
            "receipt_integrity_verified": receipt.verify_integrity(),
            "fallback_postcondition_observation_complete": receipt.postcondition.observation_complete,
            "mission_hard_invariants_hold": receipt.postcondition.mission_invariants_hold,
            "collision_observed": "collision" not in unknown,
            "cost_observed": "cost" not in unknown and receipt.postcondition.no_cost is not None,
            "no_collision": receipt.postcondition.no_collision is True and not state_after.collision,
            "no_nonzero_cost": receipt.postcondition.no_cost is True,
            "contact_part_observation_available": (
                len(contact) == 1 and task_manifest.goal_atom not in unknown
            ),
            "within_switch_latency_bound": switch_latency_ns
            <= int(execution["max_switch_latency_ns"]),
            "strict_fallback_receipt_succeeded": receipt.succeeded,
            "fallback_established_for_timing_policy": (
                wrapper.ctda_session is not None
                and wrapper.ctda_session.fallback_established_for_timing_policy(receipt)
            ),
        }
        return {
            "suite": "affordance",
            "task_id": task_id,
            "init_state_id": 0,
            "env_seed": env_seed,
            "repetition": repetition,
            "episode_nonce": nonce,
            "bddl_sha256": task_manifest.bddl_sha256,
            "task_manifest_digest": task_manifest.manifest_digest,
            "fallback_artifact_path": entries[0]["path"],
            "fallback_artifact_sha256": entries[0]["sha256"],
            "policy_loaded": False,
            "check_success_called": False,
            "env_step_count": counting_env.step_count,
            "applied_actions": counting_env.applied_actions,
            "initial_state_digest": initial_state_digest,
            "post_state_digest": digest_legacy_state(state_after),
            "unknown_observations": sorted(unknown),
            "reward": float(reward),
            "done": bool(done),
            "environment_cost": env_info.get("cost") if isinstance(env_info, dict) else None,
            "switch_latency_ns": switch_latency_ns,
            "switch_latency_bound_ns": receipt.switch_latency_bound_ns,
            "fallback_env_seconds": fallback_env_seconds,
            "receipt_digest": receipt.receipt_digest,
            "receipt": {
                "command_application": receipt.command_application,
                "applied_command_digest": receipt.applied_command_digest,
                "succeeded": receipt.succeeded,
                "integrity_verified": receipt.verify_integrity(),
                "postcondition": asdict(receipt.postcondition),
            },
            "gates": gates,
        }
    finally:
        try:
            if hasattr(env, "close"):
                env.close()
        finally:
            snapshot_dir = getattr(env, "_proofalign_bddl_snapshot_dir", None)
            if snapshot_dir:
                shutil.rmtree(str(snapshot_dir), ignore_errors=True)


def _parse_worker_output(text: str) -> dict[str, Any] | None:
    payloads = [
        line[len(WORKER_MARKER) :]
        for line in text.splitlines()
        if line.startswith(WORKER_MARKER)
    ]
    if len(payloads) != 1:
        return None
    try:
        result = json.loads(payloads[0])
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def _warning_matches(text: str, patterns: list[str]) -> list[str]:
    lines: list[str] = []
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
    availability = {
        "fallback_postcondition_observation_complete",
        "collision_observed",
        "cost_observed",
        "contact_part_observation_available",
    }
    missing = sorted(name for name in availability if gates.get(name) is not True)
    if missing:
        return "unknown", [f"missing required observation: {name}" for name in missing]
    failed = sorted(name for name, passed in gates.items() if passed is not True)
    if failed:
        return "invalid", [f"failed gate: {name}" for name in failed]
    return "valid", []


def audit(protocol_path: Path, *, artifact_dir: Path | None = None) -> dict[str, Any]:
    protocol = _load_protocol(protocol_path)
    benchmark_root = REPO_ROOT / str(protocol["benchmark"]["root"])
    execution = protocol["execution"]
    warning_patterns = [str(item) for item in execution["warning_patterns"]]
    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="proofalign-e0-fallback-config-") as config_dir:
        _write_libero_config(Path(config_dir), benchmark_root)
        worker_env = dict(os.environ)
        worker_env["LIBERO_CONFIG_PATH"] = config_dir
        worker_env["LIBERO_SAFETY_ROOT"] = str(benchmark_root.resolve())
        worker_env.setdefault("MPLCONFIGDIR", "/tmp/proofalign-e0-fallback-mpl")
        for unit in protocol["eligible_units"]:
            task_id = int(unit["task_id"])
            for repetition, env_seed in enumerate(execution["env_seeds"]):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--protocol", str(protocol_path),
                        "--worker-task-id", str(task_id),
                        "--worker-env-seed", str(env_seed),
                        "--worker-repetition", str(repetition),
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
                    "suite": "affordance",
                    "task_id": task_id,
                    "init_state_id": 0,
                    "env_seed": env_seed,
                    "repetition": repetition,
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
                    record["issues"] = list(
                        dict.fromkeys(issues + ["worker exited nonzero"])
                    )
                if artifact_dir is not None:
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    name = f"affordance_task{task_id}_init0_seed{env_seed}_rep{repetition}.log"
                    (artifact_dir / name).write_text(combined, encoding="utf-8")
                records.append(record)

    units: list[dict[str, Any]] = []
    for unit in protocol["eligible_units"]:
        task_id = int(unit["task_id"])
        repetitions = [item for item in records if item["task_id"] == task_id]
        statuses = [item["status"] for item in repetitions]
        if len(repetitions) != 3 or "unknown" in statuses:
            status = "unknown"
        elif all(item == "valid" for item in statuses):
            status = "accepted"
        else:
            status = "rejected"
        units.append(
            {
                **unit,
                "status": status,
                "repetition_statuses": statuses,
                "switch_latency_ns": [item.get("switch_latency_ns") for item in repetitions],
                "receipt_digests": [item.get("receipt_digest") for item in repetitions],
            }
        )
    repetition_counts = Counter(item["status"] for item in records)
    unit_counts = Counter(item["status"] for item in units)
    return {
        "schema": "proofalign.e0.fallback-audit.v1",
        "protocol": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "fallback_registry_sha256": protocol["inputs"]["fallback_registry"]["sha256"],
        "benchmark_commit": _git_commit(benchmark_root),
        "outcome_blind_selection": True,
        "policy_loaded": False,
        "check_success_called": False,
        "task_success_observed": False,
        "replacement_or_rerun": False,
        "counts": {
            "repetitions_total": len(records),
            "repetitions_valid": repetition_counts["valid"],
            "repetitions_invalid": repetition_counts["invalid"],
            "repetitions_unknown": repetition_counts["unknown"],
            "units_total": len(units),
            "units_accepted": unit_counts["accepted"],
            "units_rejected": unit_counts["rejected"],
            "units_unknown": unit_counts["unknown"],
        },
        "units": units,
        "repetitions": records,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit E0 task-bound zero-hold fallback with one env.step per fresh worker."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--worker-task-id", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-env-seed", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-repetition", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.expanduser().resolve()
    worker_values = (
        args.worker_task_id,
        args.worker_env_seed,
        args.worker_repetition,
    )
    if any(value is not None for value in worker_values):
        if any(value is None for value in worker_values):
            print("all worker selectors are required together", file=sys.stderr)
            return 1
        try:
            protocol = _load_protocol(protocol_path)
            result = _worker_result(
                protocol,
                task_id=int(args.worker_task_id),
                env_seed=int(args.worker_env_seed),
                repetition=int(args.worker_repetition),
            )
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
    except (E0FallbackError, OSError, subprocess.SubprocessError) as exc:
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
