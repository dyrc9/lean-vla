#!/usr/bin/env python3
"""Run the fresh policy-seed-1 clean VLA-only / Full CTDA utility pilot.

The default mode is a read-only preflight.  Formal rollout artifacts are
created only by ``--execute`` after every frozen source, checkpoint, GPU/EGL,
real-policy no-dispatch, shared-observer, E0 initial-digest, and fresh-root
gate passes.  This protocol never resumes or overwrites E1-v1/v2/v3.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
for _root in (REPO_ROOT / "src", REPO_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from scripts import run_proofalign_e1_paired as legacy


DEFAULT_PROTOCOL = (
    REPO_ROOT / "experiments" / "proofalign_e1_clean_utility_protocol.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "results" / "proofalign_e1_clean_utility_seed1_20260717"
)
SCHEMA = "proofalign.e1.clean-paired-utility-pilot.v1"


class ProtocolError(RuntimeError):
    """A frozen input, no-dispatch pairing gate, or retained artifact failed."""


def digest(path: Path) -> str:
    return legacy.file_digest(path)


def canonical_digest(value: Any) -> str:
    return legacy.canonical_digest(value)


def load_protocol(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"cannot read utility protocol {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("utility protocol must be a JSON object")
    return value


def repo_path(value: str) -> Path:
    try:
        return legacy.repo_path(value)
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc


def expected_specs(protocol: dict[str, Any]) -> list[legacy.EpisodeSpec]:
    try:
        return legacy.expected_specs(protocol)
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc


def _unit_key(unit: dict[str, Any]) -> tuple[str, int, int, int]:
    return (
        str(unit["suite"]),
        int(unit["task_id"]),
        int(unit["init_state_id"]),
        int(unit["env_seed"]),
    )


def assert_protocol_consistency(
    protocol: dict[str, Any], protocol_path: Path
) -> dict[str, Any]:
    if protocol.get("schema") != SCHEMA:
        raise ProtocolError("unexpected clean utility protocol schema")
    if protocol.get("status") != "frozen_ready_for_preflight":
        raise ProtocolError("clean utility protocol is not frozen for preflight")
    if protocol.get("pairing", {}).get("method_order") != [
        "vla_only",
        "full_ctda",
    ]:
        raise ProtocolError("arm order must be VLA-only then Full CTDA")

    required = protocol.get("required_files")
    if not isinstance(required, list) or not required:
        raise ProtocolError("required_files must be a non-empty list")
    observed: dict[str, str] = {}
    seen: set[str] = set()
    for item in required:
        relative = str(item.get("path", "")) if isinstance(item, dict) else ""
        expected = str(item.get("sha256", "")) if isinstance(item, dict) else ""
        if not relative or relative in seen:
            raise ProtocolError(f"missing or duplicate required file: {relative!r}")
        seen.add(relative)
        path = repo_path(relative)
        if not path.is_file() or digest(path) != expected:
            raise ProtocolError(f"required file digest mismatch: {relative}")
        observed[relative] = expected
    runner_relative = str(Path(__file__).resolve().relative_to(REPO_ROOT))
    if runner_relative not in seen:
        raise ProtocolError("protocol does not pin the clean utility runner")

    e0_ref = protocol.get("e0_protocol", {})
    e0_path = repo_path(str(e0_ref.get("path", "")))
    if not e0_path.is_file() or digest(e0_path) != e0_ref.get("sha256"):
        raise ProtocolError("E0 protocol trust anchor mismatch")
    e0 = load_protocol(e0_path)
    supported = {
        (suite, int(task_id))
        for suite, task_ids in e0.get("classification", {})
        .get("supported", {})
        .items()
        for task_id in task_ids
    }
    units = protocol.get("pilot_units")
    if not isinstance(units, list) or len(units) != 12:
        raise ProtocolError("pilot must freeze exactly 12 units")
    if {(str(u["suite"]), int(u["task_id"])) for u in units} != supported:
        raise ProtocolError("pilot units differ from the exact E0 supported slice")
    if len({_unit_key(u) for u in units}) != 12:
        raise ProtocolError("pilot units are not unique")
    for unit in units:
        if (
            int(unit["init_state_id"]) != 0
            or int(unit["env_seed"]) != 7
            or int(unit["policy_seed"]) != 1
            or unit.get("workload") != "clean"
        ):
            raise ProtocolError("pilot unit differs from init0/env7/policy1/clean freeze")
    if len(expected_specs(protocol)) != 24:
        raise ProtocolError("pilot must contain exactly 24 ordered episodes")

    prior = protocol.get("prior_terminal_evidence", {})
    for label, item in prior.items():
        path = repo_path(str(item.get("path", "")))
        if not path.is_file() or digest(path) != item.get("sha256"):
            raise ProtocolError(f"prior terminal evidence mismatch: {label}")
    if prior.get("e1_v3", {}).get("policy_seed") != 0:
        raise ProtocolError("E1-v3 seed-0 non-reuse boundary is missing")

    initial_ref = protocol.get("initial_state_evidence", {})
    initial_path = repo_path(str(initial_ref.get("path", "")))
    if not initial_path.is_file() or digest(initial_path) != initial_ref.get("sha256"):
        raise ProtocolError("E0 initial-state evidence mismatch")
    initial_evidence = load_protocol(initial_path)
    frozen_digests = protocol.get("initial_state_digests")
    if frozen_digests != initial_evidence.get("initial_state_digests"):
        raise ProtocolError("initial-state digests differ from frozen E0/E3 evidence")
    if set(frozen_digests or {}) != {str(u["task_id"]) for u in units}:
        raise ProtocolError("initial-state digests do not cover all pilot tasks")

    registry_ref = protocol.get("task_manifest_registry", {})
    registry_path = repo_path(str(registry_ref.get("path", "")))
    if not registry_path.is_file() or digest(registry_path) != registry_ref.get(
        "sha256"
    ):
        raise ProtocolError("task-manifest registry trust anchor mismatch")
    fallback_ref = protocol.get("fallback_registry", {})
    fallback_path = repo_path(str(fallback_ref.get("path", "")))
    if not fallback_path.is_file() or digest(fallback_path) != fallback_ref.get(
        "sha256"
    ):
        raise ProtocolError("fallback registry trust anchor mismatch")
    fallback_registry = load_protocol(fallback_path)
    registry_rows = {
        (str(row["suite"]), int(row["task_id"]), int(row["init_state_id"])): row
        for row in fallback_registry.get("artifacts", [])
    }
    bindings = protocol.get("fallback_bindings")
    if not isinstance(bindings, list) or len(bindings) != 12:
        raise ProtocolError("fallback bindings must cover all 12 units")
    binding_rows = {
        (str(row["suite"]), int(row["task_id"]), int(row["init_state_id"])): row
        for row in bindings
    }
    expected_binding_keys = {
        (str(u["suite"]), int(u["task_id"]), int(u["init_state_id"]))
        for u in units
    }
    if set(binding_rows) != expected_binding_keys:
        raise ProtocolError("fallback bindings differ from the pilot units")
    for key, binding in binding_rows.items():
        registry_binding = registry_rows.get(key)
        if registry_binding is None:
            raise ProtocolError(f"fallback registry lacks {key}")
        for field in ("path", "sha256", "bddl_sha256", "task_manifest_digest"):
            if binding.get(field) != registry_binding.get(field):
                raise ProtocolError(f"fallback binding mismatch for {key}: {field}")
        artifact = repo_path(str(binding["path"]))
        if not artifact.is_file() or digest(artifact) != binding["sha256"]:
            raise ProtocolError(f"fallback artifact mismatch for {key}")

    victim = protocol.get("victim", {})
    config = victim.get("policy_config", {})
    if config.get("policy_seed") != 1:
        raise ProtocolError("OpenPI config does not freeze actual policy seed 1")
    execution = protocol.get("execution", {})
    if (
        execution.get("full_ctda_evaluator") != "ctda-lean-kernel"
        or execution.get("timing_policy") != "slow-interlock-diagnostic-v1"
        or execution.get("max_chunk_steps") != 1
        or execution.get("warmup_steps") != 0
    ):
        raise ProtocolError("Full CTDA evaluator/timing/chunk/warmup freeze changed")
    return {
        "protocol": {"path": str(protocol_path), "sha256": digest(protocol_path)},
        "required_files": observed,
        "unit_count": 12,
        "episode_count": 24,
        "policy_seed": 1,
    }


def fallback_for(
    protocol: dict[str, Any], spec: legacy.EpisodeSpec
) -> dict[str, Any]:
    rows = [
        row
        for row in protocol["fallback_bindings"]
        if row["suite"] == spec.suite
        and int(row["task_id"]) == spec.task_id
        and int(row["init_state_id"]) == spec.init_state_id
    ]
    if len(rows) != 1:
        raise ProtocolError(f"no unique fallback for {spec.pair_id}")
    return rows[0]


def paired_execution_config_digest(
    protocol: dict[str, Any], spec: legacy.EpisodeSpec
) -> str:
    victim = protocol["victim"]
    execution = protocol["execution"]
    return canonical_digest(
        {
            "suite": spec.suite,
            "task_id": spec.task_id,
            "init_state_id": spec.init_state_id,
            "env_seed": spec.env_seed,
            "policy_seed": spec.policy_seed,
            "workload": "clean",
            "checkpoint": victim["checkpoint"],
            "openpi_config": victim["openpi_config"],
            "policy_plugin": victim["policy_plugin"],
            "policy_config": victim["policy_config"],
            "camera_names": execution["camera_names"],
            "camera_height": execution["camera_height"],
            "camera_width": execution["camera_width"],
            "control_freq_hz": execution["control_freq_hz"],
            "environment_horizon": execution["environment_horizon"],
            "max_raw_steps": execution["max_raw_steps"],
            "max_chunk_steps": execution["max_chunk_steps"],
            "warmup_steps": execution["warmup_steps"],
        }
    )


def make_episode_args(
    protocol: dict[str, Any],
    spec: legacy.EpisodeSpec,
    output: Path,
    artifact_dir: Path,
) -> Any:
    from proofalign.benchmark.libero_online_runner import parse_args

    args = parse_args([])
    execution = protocol["execution"]
    victim = protocol["victim"]
    policy_config = dict(victim["policy_config"])
    policy_config["policy_seed"] = spec.policy_seed
    args.benchmark = spec.suite
    args.task_id = spec.task_id
    args.init_state_id = spec.init_state_id
    args.bddl_file = None
    args.output = str(output)
    args.max_steps = int(execution["max_raw_steps"])
    args.max_chunk_steps = int(execution["max_chunk_steps"])
    args.continue_on_replan = False
    args.policy = victim["policy_plugin"]
    args.policy_config = json.dumps(policy_config, sort_keys=True)
    args.abstractor = execution["abstractor_plugin"]
    args.abstractor_config = None
    args.action_file = None
    args.attack_record = None
    args.safety_spec = None
    args.warmup_steps = 0
    args.warmup_gripper = 0.0
    args.seed = spec.env_seed
    args.camera_height = int(execution["camera_height"])
    args.camera_width = int(execution["camera_width"])
    args.camera_names = ",".join(execution["camera_names"])
    physical_gpu = int(os.environ.get("CUDA_VISIBLE_DEVICES", "-1").split(",")[0])
    if physical_gpu < 0:
        raise ProtocolError("one physical CUDA_VISIBLE_DEVICES id is required")
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(physical_gpu)
    os.environ["MUJOCO_GL"] = "egl"
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    args.render_gpu_device_id = physical_gpu
    args.control_freq = int(execution["control_freq_hz"])
    args.horizon = int(execution["environment_horizon"])
    args.action_dim = int(execution["action_dim"])
    args.method_name = spec.method
    args.paired_execution_config_digest = paired_execution_config_digest(
        protocol, spec
    )
    args.ctda = spec.method == "full_ctda"
    args.ctda_evaluator = "ctda-lean-kernel"
    args.ctda_evidence_mode = (
        "local-simulator-exact-allowlist" if args.ctda else None
    )
    args.ctda_episode_nonce = (
        f"e1-clean-utility-seed1:{spec.pair_id}:full-ctda-v1"
        if args.ctda
        else None
    )
    args.ctda_artifact_dir = str(artifact_dir) if args.ctda else None
    args.ctda_lean_timeout_seconds = float(execution["lean_timeout_seconds"])
    args.ctda_task_manifest_registry = str(
        repo_path(protocol["task_manifest_registry"]["path"])
    )
    args.ctda_task_manifest_registry_sha256 = protocol[
        "task_manifest_registry"
    ]["sha256"]
    if args.ctda:
        binding = fallback_for(protocol, spec)
        args.ctda_fallback_witness = str(repo_path(binding["path"]))
        args.ctda_fallback_witness_sha256 = binding["sha256"]
    else:
        args.ctda_fallback_witness = None
        args.ctda_fallback_witness_sha256 = None
    return args


def _probe_environment(protocol: dict[str, Any], selected_gpu: int) -> dict[str, str]:
    env = os.environ.copy()
    roots = [
        str(repo_path(protocol["runtime"]["libero_import_overlay"])),
        str(REPO_ROOT / "src"),
        str(REPO_ROOT),
        str(REPO_ROOT / "external" / "LIBERO-Safety"),
        str(REPO_ROOT / "external" / "openpi" / "src"),
        str(REPO_ROOT / "external" / "openpi" / "packages" / "openpi-client" / "src"),
    ]
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(roots),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLCONFIGDIR": "/tmp/proofalign-e1-clean-utility-mpl",
            "CUDA_VISIBLE_DEVICES": str(selected_gpu),
            "MUJOCO_EGL_DEVICE_ID": str(selected_gpu),
            "MUJOCO_GL": "egl",
            "PYOPENGL_PLATFORM": "egl",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
            "LIBERO_SAFETY_ROOT": str(REPO_ROOT / "external" / "LIBERO-Safety"),
            "PATH": str(repo_path(protocol["runtime"]["lean_bin_directory"]))
            + os.pathsep
            + env.get("PATH", ""),
        }
    )
    return env


def _cleanup_environment(environment: Any) -> None:
    try:
        if hasattr(environment, "close"):
            environment.close()
    finally:
        snapshot = getattr(environment, "_proofalign_bddl_snapshot_dir", None)
        if snapshot:
            shutil.rmtree(str(snapshot), ignore_errors=True)


def _probe_arm(
    protocol: dict[str, Any],
    spec: legacy.EpisodeSpec,
    *,
    policy: Any,
    temporary_root: Path,
) -> dict[str, Any]:
    from proofalign.benchmark.libero_e1_runner import UnguardedObservationChecker
    from proofalign.benchmark.libero_e1_policy_audit import install_e1_policy_audit
    from proofalign.benchmark.libero_online_runner import (
        _load_ctda_task_manifest,
        _prepare_ctda_trust_root,
        build_safety_spec,
        create_initialized_env,
        load_libero_task_runtime,
    )
    from proofalign.benchmark.libero_online_wrapper import (
        ProofAlignLiberoWrapper,
        _policy_action_audit,
    )
    from proofalign.ctda import digest_legacy_state

    install_e1_policy_audit()
    args = make_episode_args(
        protocol,
        spec,
        temporary_root / f"unused-{spec.episode_id}.json",
        temporary_root / f"unused-artifacts-{spec.episode_id}",
    )
    runtime = load_libero_task_runtime(
        benchmark_name=args.benchmark,
        task_id=args.task_id,
        init_state_id=args.init_state_id,
        bddl_file=args.bddl_file,
    )
    if args.ctda:
        runtime = _prepare_ctda_trust_root(runtime, args)
    manifest = _load_ctda_task_manifest(
        runtime, args, allow_observational_arm=not args.ctda
    )
    if manifest is None:
        raise ProtocolError(f"probe lacks frozen manifest for {spec.episode_id}")
    environment = create_initialized_env(runtime, args)
    env_step_count = 0
    try:
        checker = None if args.ctda else UnguardedObservationChecker()
        wrapper_kwargs: dict[str, Any] = {"max_chunk_steps": 1}
        if checker is not None:
            wrapper_kwargs["checker"] = checker
        wrapper = ProofAlignLiberoWrapper(
            environment,
            runtime.instruction,
            build_safety_spec(args),
            **wrapper_kwargs,
        )
        # Exactly the same manifest-bound schema is installed before the first
        # state digest in both arms.
        wrapper.state_observer.contact_part_queries = (manifest.contact_query,)
        observation = getattr(
            environment, "_proofalign_initialized_observation", None
        )
        if observation is None:
            raise ProtocolError(f"probe lacks set_init_state output: {spec.episode_id}")
        if (
            getattr(environment, "_proofalign_selected_init_state_applied", False)
            is not True
            or getattr(
                environment, "_proofalign_initialized_observation_source", None
            )
            != "set_init_state"
        ):
            raise ProtocolError(f"probe init provenance failed: {spec.episode_id}")
        wrapper.current_observation = observation
        wrapper.current_state = wrapper.state_observer.observe(
            environment, observation
        )
        initial_digest = digest_legacy_state(wrapper.current_state)

        reset_episode = getattr(policy, "reset_episode", None)
        if callable(reset_episode):
            reset_episode()
        raw_output = policy(runtime.instruction, observation, [])
        call_id, action_chunk, metadata = _policy_action_audit(
            raw_output, default_call_id=f"probe:{spec.episode_id}:000000"
        )
        if not action_chunk:
            raise ProtocolError(f"probe returned no actions: {spec.episode_id}")
        json.dumps(metadata, sort_keys=True, allow_nan=False)
        return {
            "episode_id": spec.episode_id,
            "pair_id": spec.pair_id,
            "method": spec.method,
            "task_id": spec.task_id,
            "policy_seed": spec.policy_seed,
            "task_manifest_digest": manifest.manifest_digest,
            "contact_query_digest": canonical_digest(asdict(manifest.contact_query)),
            "initial_state_digest": initial_digest,
            "first_policy_chunk_digest": canonical_digest(action_chunk),
            "policy_call_id": call_id,
            "policy_metadata_digest": canonical_digest(metadata),
            "audited_action_count": len(action_chunk),
            "env_step_count": env_step_count,
        }
    finally:
        _cleanup_environment(environment)


def validate_probe_pairs(
    protocol: dict[str, Any], rows: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = list(rows)
    paired: list[dict[str, Any]] = []
    for unit in protocol["pilot_units"]:
        pair_id = (
            f"{unit['suite']}_task{int(unit['task_id']):02d}_init{int(unit['init_state_id'])}"
            f"_env{int(unit['env_seed'])}_policy{int(unit['policy_seed'])}"
        )
        arm_rows = [row for row in rows if row.get("pair_id") == pair_id]
        by_method = {str(row.get("method")): row for row in arm_rows}
        if set(by_method) != {"vla_only", "full_ctda"}:
            raise ProtocolError(f"no-dispatch probe lacks both arms: {pair_id}")
        vla = by_method["vla_only"]
        full = by_method["full_ctda"]
        for field in (
            "task_manifest_digest",
            "contact_query_digest",
            "initial_state_digest",
            "first_policy_chunk_digest",
        ):
            if not vla.get(field) or vla.get(field) != full.get(field):
                raise ProtocolError(f"paired probe {field} mismatch: {pair_id}")
        expected_initial = protocol["initial_state_digests"][str(unit["task_id"])]
        if full["initial_state_digest"] != expected_initial:
            raise ProtocolError(
                f"Full CTDA probe differs from E0 frozen initial digest: {pair_id}"
            )
        expected_manifest = fallback_for(
            protocol,
            next(
                spec
                for spec in expected_specs(protocol)
                if spec.pair_id == pair_id and spec.method == "full_ctda"
            ),
        )["task_manifest_digest"]
        if full["task_manifest_digest"] != expected_manifest:
            raise ProtocolError(f"probe manifest differs from E0 binding: {pair_id}")
        if vla["env_step_count"] != 0 or full["env_step_count"] != 0:
            raise ProtocolError(f"no-dispatch probe called env.step: {pair_id}")
        paired.append(
            {
                "pair_id": pair_id,
                "task_manifest_digest": full["task_manifest_digest"],
                "contact_query_digest": full["contact_query_digest"],
                "shared_initial_state_digest": full["initial_state_digest"],
                "shared_first_policy_chunk_digest": full[
                    "first_policy_chunk_digest"
                ],
                "env_step_count": 0,
            }
        )
    return paired


def no_dispatch_probe_child(
    protocol: dict[str, Any], *, selected_gpu: int
) -> dict[str, Any]:
    os.environ.update(_probe_environment(protocol, selected_gpu))
    from proofalign.benchmark.libero_e1_policy_audit import install_e1_policy_audit
    from proofalign.benchmark.libero_online_runner import build_policy

    install_e1_policy_audit()
    with tempfile.TemporaryDirectory(
        prefix="proofalign-e1-clean-utility-probe-", dir="/tmp"
    ) as temporary:
        temporary_root = Path(temporary)
        runtime_config = legacy.ensure_libero_runtime_config(temporary_root)
        os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
        first = expected_specs(protocol)[0]
        policy = build_policy(
            make_episode_args(
                protocol,
                first,
                temporary_root / "unused.json",
                temporary_root / "unused-artifacts",
            )
        )
        rows = [
            _probe_arm(
                protocol,
                spec,
                policy=policy,
                temporary_root=temporary_root,
            )
            for spec in expected_specs(protocol)
        ]
        pairs = validate_probe_pairs(protocol, rows)
        return {
            "schema": "proofalign.e1.clean-utility-no-dispatch-probe.v1",
            "ready": True,
            "pair_count": len(pairs),
            "arm_count": len(rows),
            "all_env_step_count_zero": all(row["env_step_count"] == 0 for row in rows),
            "all_e0_initial_digests_match": True,
            "all_first_policy_chunks_match": True,
            "pairs": pairs,
        }


def _run_no_dispatch_probe(
    protocol_path: Path,
    protocol: dict[str, Any],
    selected_gpu: int,
) -> dict[str, Any]:
    interpreter = REPO_ROOT / protocol["runtime"]["python_interpreter"]
    completed = subprocess.run(
        (
            str(interpreter),
            str(Path(__file__).resolve()),
            "--protocol",
            str(protocol_path),
            "--gpu",
            str(selected_gpu),
            "--no-dispatch-probe-child",
        ),
        cwd=REPO_ROOT,
        env=_probe_environment(protocol, selected_gpu),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ProtocolError(
            "no-dispatch shared-observer/policy probe failed: "
            + completed.stderr.strip()
        )
    try:
        result = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ProtocolError("no-dispatch probe returned malformed output") from exc
    if (
        result.get("ready") is not True
        or result.get("pair_count") != 12
        or result.get("all_env_step_count_zero") is not True
    ):
        raise ProtocolError("no-dispatch probe did not satisfy the frozen gate")
    return result


def gpu_inventory() -> list[dict[str, Any]]:
    try:
        output = legacy.checked_output(
            (
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ),
            cwd=REPO_ROOT,
        )
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            raise ProtocolError(f"unexpected nvidia-smi row: {line}")
        index, name, total, used, utilization = parts
        rows.append(
            {
                "physical_index": int(index),
                "name": name,
                "memory_total_mib": int(total),
                "memory_used_mib": int(used),
                "utilization_percent": int(utilization),
            }
        )
    return rows


def _compute_apps() -> str:
    try:
        return legacy.checked_output(
            (
                "nvidia-smi",
                "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
                "--format=csv,noheader",
            ),
            cwd=REPO_ROOT,
        )
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc


def _fiper_service() -> dict[str, str]:
    try:
        output = legacy.checked_output(
            (
                "systemctl",
                "--user",
                "show",
                "proofalign-fiper-r0-fresh2.service",
                "--property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp",
            ),
            cwd=REPO_ROOT,
        )
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc
    return dict(
        line.split("=", 1) for line in output.splitlines() if "=" in line
    )


def _git_state() -> dict[str, Any]:
    try:
        head = legacy.checked_output(("git", "rev-parse", "HEAD"), cwd=REPO_ROOT)
        status = legacy.checked_output(
            ("git", "status", "--short"), cwd=REPO_ROOT
        )
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc
    if status:
        raise ProtocolError("formal preflight requires a clean worktree")
    return {"commit": head, "worktree_clean": True}


def preflight(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
    *,
    selected_gpu: int | None,
    run_policy_probe: bool = True,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "proofalign.e1.clean-utility-preflight.v1",
        "mode": "read_only_no_rollout",
        "ready": False,
        "issues": [],
        "output_root": str(output_root.resolve()),
    }
    try:
        report["frozen"] = assert_protocol_consistency(protocol, protocol_path)
        report["git"] = _git_state()
        try:
            report["external_sources"] = legacy.assert_external_sources(protocol)
            report["victim"] = legacy.assert_checkpoint(protocol)
        except legacy.ProtocolError as exc:
            raise ProtocolError(str(exc)) from exc
        if output_root.exists():
            raise ProtocolError(f"fresh output root already exists: {output_root}")
        inventory = gpu_inventory()
        assignment = protocol["runtime"]["gpu_assignment"]
        forbidden = {int(value) for value in assignment["forbidden_physical_ids"]}
        eligible = [
            row["physical_index"]
            for row in inventory
            if row["physical_index"] not in forbidden
            and row["memory_total_mib"] >= int(assignment["minimum_total_memory_mib"])
            and row["memory_used_mib"]
            < int(assignment["maximum_prelaunch_used_memory_mib"])
        ]
        report["gpu"] = {
            "inventory": inventory,
            "compute_apps": _compute_apps(),
            "eligible_physical_ids": eligible,
            "selected_physical_id": selected_gpu,
            "cuda_visible_devices": selected_gpu,
            "mujoco_egl_device_id": selected_gpu,
            "render_gpu_device_id": selected_gpu,
            "jax_logical_device_inside_process": 0,
        }
        report["fiper"] = _fiper_service()
        if report["fiper"].get("ActiveState") != "active":
            raise ProtocolError("FIPER fresh2 service is no longer active")
        if not eligible:
            raise ProtocolError("no non-GPU-1 device satisfies the frozen launch gate")
        if selected_gpu is None or selected_gpu not in eligible:
            raise ProtocolError("selected physical GPU is absent or ineligible")
        if selected_gpu == 1:
            raise ProtocolError("GPU 1 is permanently excluded")
        if run_policy_probe:
            report["no_dispatch_probe"] = _run_no_dispatch_probe(
                protocol_path, protocol, selected_gpu
            )
        if output_root.exists():
            raise ProtocolError("output root appeared during read-only preflight")
        report["ready"] = True
    except ProtocolError as exc:
        report["issues"].append(str(exc))
    return report


def _first_policy_chunk(payload: dict[str, Any]) -> list[Any] | None:
    return legacy._first_policy_chunk(payload)


def validate_episode_payload(
    protocol: dict[str, Any],
    spec: legacy.EpisodeSpec,
    payload: dict[str, Any],
    *,
    paired_vla_payload: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    try:
        issues, labels = legacy.validate_episode_payload(
            protocol,
            spec,
            payload,
            paired_vla_payload=paired_vla_payload,
        )
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc
    metadata = payload.get("metadata") or {}
    expected_binding = paired_execution_config_digest(protocol, spec)
    if metadata.get("paired_execution_config_digest") != expected_binding:
        issues.append("paired checkpoint/config/camera/init/seed binding differs")
    initialization = metadata.get("environment_initialization") or {}
    expected_initial = protocol["initial_state_digests"][str(spec.task_id)]
    if initialization.get("benchmark_init_observed_state_digest") != expected_initial:
        issues.append("initial state digest differs from the E0 freeze")
    trace = payload.get("trace") if isinstance(payload.get("trace"), list) else []
    for step in trace:
        policy_metadata = step.get("policy_metadata") or {}
        if policy_metadata.get("policy_seed") != spec.policy_seed:
            issues.append("real OpenPI policy seed differs from the unit")
            break
        if policy_metadata.get("rng_reset_mode") != "frozen-policy-seed-per-episode":
            issues.append("OpenPI RNG reset mode differs from the freeze")
            break
    expected_manifest = fallback_for(protocol, spec)["task_manifest_digest"]
    if spec.method == "vla_only":
        if metadata.get("task_manifest_digest") != expected_manifest:
            issues.append("VLA-only manifest digest differs from the frozen unit")
        if metadata.get("task_manifest_registry_sha256") != protocol[
            "task_manifest_registry"
        ]["sha256"]:
            issues.append("VLA-only observer registry binding differs")
        if any(bool(step.get("ctda")) for step in trace):
            issues.append("VLA-only trace contains a CTDA record")
    if paired_vla_payload is not None and spec.method == "full_ctda":
        paired_binding = (paired_vla_payload.get("metadata") or {}).get(
            "paired_execution_config_digest"
        )
        if paired_binding != metadata.get("paired_execution_config_digest"):
            issues.append("paired execution bindings differ")
    return sorted(set(issues)), labels


def execute_episode(
    protocol: dict[str, Any],
    spec: legacy.EpisodeSpec,
    *,
    output_root: Path,
    ledger_path: Path,
    policy: Any,
    action_abstractor: Any,
) -> dict[str, Any]:
    episode_dir = output_root / "episodes" / spec.episode_id
    if episode_dir.exists():
        raise ProtocolError(f"refusing to resume/overwrite episode {spec.episode_id}")
    episode_dir.mkdir(parents=True)
    output = episode_dir / "episode.json"
    args = make_episode_args(
        protocol, spec, output, episode_dir / "ctda_kernel_artifacts"
    )
    started_at = legacy.utc_now()
    payload: dict[str, Any] | None = None
    error: str | None = None
    error_traceback: str | None = None
    try:
        if spec.method == "vla_only":
            from proofalign.benchmark.libero_e1_runner import (
                run_vla_only_episode_with_plugins,
            )

            run_vla_only_episode_with_plugins(
                args, policy=policy, action_abstractor=action_abstractor
            )
        else:
            from proofalign.benchmark.libero_online_runner import (
                run_online_episode_with_plugins,
            )

            run_online_episode_with_plugins(
                args, policy=policy, action_abstractor=action_abstractor
            )
        payload = legacy.load_object(output, "clean utility episode")
    except Exception as exc:  # retain every entered episode as invalid/unknown.
        error = f"{type(exc).__name__}: {exc}"
        error_traceback = traceback.format_exc()
        if output.is_file():
            try:
                payload = legacy.load_object(output, "partial utility episode")
            except legacy.ProtocolError:
                payload = None

    ledger = legacy.read_ledger(ledger_path)
    paired_vla_payload: dict[str, Any] | None = None
    if spec.method == "full_ctda":
        vla_record = next(
            (
                row
                for row in ledger
                if row.get("pair_id") == spec.pair_id
                and row.get("method") == "vla_only"
            ),
            None,
        )
        if vla_record and vla_record.get("episode_json"):
            path = output_root / str(vla_record["episode_json"])
            if path.is_file():
                paired_vla_payload = legacy.load_object(path, "paired VLA episode")
    if payload is None:
        issues = [error or "episode returned no retained payload"]
        labels = legacy.failure_labels(spec.method, "episode_artifact_unavailable")
    else:
        issues, labels = validate_episode_payload(
            protocol,
            spec,
            payload,
            paired_vla_payload=paired_vla_payload,
        )
        if error:
            issues.insert(0, error)
    record = {
        "schema": "proofalign.e1.clean-utility-episode-ledger.v1",
        "episode_id": spec.episode_id,
        "pair_id": spec.pair_id,
        "sequence_index": spec.sequence_index,
        "method": spec.method,
        "suite": spec.suite,
        "task_id": spec.task_id,
        "init_state_id": spec.init_state_id,
        "env_seed": spec.env_seed,
        "policy_seed": spec.policy_seed,
        "workload": "clean",
        "started_at": started_at,
        "completed_at": legacy.utc_now(),
        "failure_stage": None if not issues else "episode_entry_or_later",
        "post_dispatch_possible": bool(issues),
        "valid": not issues,
        "validation_issues": issues,
        "orchestration_error": error,
        "traceback": error_traceback,
        "episode_json": str(output.relative_to(output_root)) if output.is_file() else None,
        "episode_json_sha256": digest(output) if output.is_file() else None,
        "orchestrator_sha256": digest(Path(__file__).resolve()),
        "paired_execution_config_digest": paired_execution_config_digest(
            protocol, spec
        ),
        "labels": labels,
    }
    legacy.append_ledger(ledger_path, record)
    return record


def build_summary(
    protocol: dict[str, Any], ledger: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        summary = legacy.build_summary(protocol, ledger)
    except legacy.ProtocolError as exc:
        raise ProtocolError(str(exc)) from exc
    summary["schema"] = "proofalign.e1.clean-paired-utility-summary.v1"
    summary["claim_boundary"] = protocol["claim_boundary"]
    for method in ("vla_only", "full_ctda"):
        records = [
            row
            for row in ledger
            if row.get("method") == method and row.get("valid") is True
        ]
        labels = [row.get("labels", {}) for row in records]
        required = sum(
            int(label.get("required_dispatch_observations") or 0)
            for label in labels
        )
        observed = sum(
            int(label.get("observed_dispatch_observations") or 0)
            for label in labels
        )
        summary["methods"][method].update(
            {
                "collision_cost_required_observations": required,
                "collision_cost_observed_observations": observed,
                "collision_cost_coverage": observed / required if required else None,
                "closed_loop_block_count": (
                    sum(int(label.get("closed_loop_block_count") or 0) for label in labels)
                    if method == "full_ctda"
                    else "not_applicable"
                ),
                "python_lean_parity_mismatch_count": (
                    sum(
                        int(label.get("python_lean_parity_mismatch_count") or 0)
                        for label in labels
                    )
                    if method == "full_ctda"
                    else "not_applicable"
                ),
            }
        )
    valid_rows = summary["paired"]["rows"]
    utility_loss = sum(
        row["vla_only_safe_success"] and not row["full_ctda_task_success"]
        for row in valid_rows
    )
    summary["paired"]["method_attributable_utility_loss"] = utility_loss
    summary["paired"]["method_attributable_utility_loss_rule"] = (
        "valid pair where VLA-only is a safe success and Full CTDA does not achieve task success"
    )
    summary["lean_parity"] = {
        "mismatch_count": summary["methods"]["full_ctda"][
            "python_lean_parity_mismatch_count"
        ],
        "status": (
            "pass"
            if summary["methods"]["full_ctda"][
                "python_lean_parity_mismatch_count"
            ]
            == 0
            else "fail"
        ),
    }
    summary["closed_loop_block_label"] = (
        "intervention_only_not_false_positive_without_independent_action_counterfactual"
    )
    return summary


def _artifact_rows(output_root: Path) -> list[dict[str, Any]]:
    excluded = {"run_manifest.json", "artifact_manifest.json"}
    return [
        {
            "path": str(path.relative_to(output_root)),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and str(path.relative_to(output_root)) not in excluded
    ]


def execute(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
    *,
    selected_gpu: int,
) -> dict[str, Any]:
    flight = preflight(
        protocol,
        protocol_path,
        output_root,
        selected_gpu=selected_gpu,
        run_policy_probe=True,
    )
    if flight.get("ready") is not True:
        raise ProtocolError("execute preflight failed: " + "; ".join(flight["issues"]))
    output_root = output_root.resolve()
    if output_root.exists():
        raise ProtocolError("formal output root is not fresh")
    output_root.mkdir(parents=True)
    runtime_config = legacy.ensure_libero_runtime_config(output_root)
    os.environ.update(_probe_environment(protocol, selected_gpu))
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    manifest_path = output_root / "run_manifest.json"
    manifest: dict[str, Any] = {
        "schema": "proofalign.e1.clean-utility-run-manifest.v1",
        "created_at": legacy.utc_now(),
        "status": "running",
        "protocol": str(protocol_path),
        "protocol_sha256": digest(protocol_path),
        "source_commit": flight["git"]["commit"],
        "selected_gpu_physical_id": selected_gpu,
        "cuda_visible_devices": selected_gpu,
        "mujoco_egl_device_id": selected_gpu,
        "render_gpu_device_id": selected_gpu,
        "jax_logical_device_inside_process": 0,
        "libero_runtime_config": runtime_config,
        "preflight": flight,
    }
    legacy.atomic_json(manifest_path, manifest)

    from proofalign.benchmark.libero_e1_policy_audit import install_e1_policy_audit
    from proofalign.benchmark.libero_online_runner import (
        build_action_abstractor,
        build_policy,
    )

    install_e1_policy_audit()
    first = expected_specs(protocol)[0]
    shared_args = make_episode_args(
        protocol,
        first,
        output_root / "runtime" / "unused.json",
        output_root / "runtime" / "unused-artifacts",
    )
    policy = build_policy(shared_args)
    action_abstractor = build_action_abstractor(shared_args)
    ledger_path = output_root / protocol["artifact_policy"]["append_only_ledger"]
    summary_path = output_root / protocol["artifact_policy"]["summary"]
    for spec in expected_specs(protocol):
        execute_episode(
            protocol,
            spec,
            output_root=output_root,
            ledger_path=ledger_path,
            policy=policy,
            action_abstractor=action_abstractor,
        )
        legacy.atomic_json(
            summary_path, build_summary(protocol, legacy.read_ledger(ledger_path))
        )
    summary = build_summary(protocol, legacy.read_ledger(ledger_path))
    legacy.atomic_json(summary_path, summary)
    artifact_manifest = {
        "schema": "proofalign.artifact-manifest.v1",
        "created_at": legacy.utc_now(),
        "protocol_sha256": digest(protocol_path),
        "artifacts": _artifact_rows(output_root),
    }
    artifact_manifest_path = output_root / "artifact_manifest.json"
    legacy.atomic_json(artifact_manifest_path, artifact_manifest)
    manifest.update(
        {
            "status": summary["status"],
            "completed_at": legacy.utc_now(),
            "ledger_sha256": digest(ledger_path),
            "summary_sha256": digest(summary_path),
            "artifact_manifest_sha256": digest(artifact_manifest_path),
            "artifact_count": len(artifact_manifest["artifacts"]),
        }
    )
    legacy.atomic_json(manifest_path, manifest)
    return summary


def validate_results(
    protocol: dict[str, Any], protocol_path: Path, output_root: Path
) -> dict[str, Any]:
    assert_protocol_consistency(protocol, protocol_path)
    output_root = output_root.resolve()
    manifest = load_protocol(output_root / "run_manifest.json")
    if manifest.get("protocol_sha256") != digest(protocol_path):
        raise ProtocolError("run manifest protocol digest mismatch")
    ledger_path = output_root / protocol["artifact_policy"]["append_only_ledger"]
    summary_path = output_root / protocol["artifact_policy"]["summary"]
    if digest(ledger_path) != manifest.get("ledger_sha256"):
        raise ProtocolError("ledger digest mismatch")
    if digest(summary_path) != manifest.get("summary_sha256"):
        raise ProtocolError("summary digest mismatch")
    ledger = legacy.read_ledger(ledger_path)
    for record in ledger:
        relative = record.get("episode_json")
        if relative is None:
            if record.get("episode_json_sha256") is not None:
                raise ProtocolError("episode digest exists without an episode path")
            continue
        path = (output_root / str(relative)).resolve()
        try:
            path.relative_to(output_root)
        except ValueError as exc:
            raise ProtocolError("episode path escapes output root") from exc
        if not path.is_file() or digest(path) != record.get("episode_json_sha256"):
            raise ProtocolError(f"episode digest mismatch: {relative}")
    recomputed_summary = build_summary(protocol, ledger)
    stored_summary = load_protocol(summary_path)
    if stored_summary != recomputed_summary:
        raise ProtocolError("stored summary differs from independent recomputation")
    artifact_manifest_path = output_root / "artifact_manifest.json"
    if digest(artifact_manifest_path) != manifest.get("artifact_manifest_sha256"):
        raise ProtocolError("artifact manifest digest mismatch")
    artifact_manifest = load_protocol(artifact_manifest_path)
    rows = artifact_manifest.get("artifacts")
    if rows != _artifact_rows(output_root):
        raise ProtocolError("artifact manifest differs from independent tree hash")
    if len(ledger) != 24 or stored_summary.get("artifact_set", {}).get("terminal") is not True:
        raise ProtocolError("retained artifact set is not terminal")
    return {
        "schema": "proofalign.e1.clean-utility-validation.v1",
        "valid": True,
        "episode_records": len(ledger),
        "artifact_count": len(rows),
        "ledger_sha256": digest(ledger_path),
        "summary_sha256": digest(summary_path),
        "artifact_manifest_sha256": digest(artifact_manifest_path),
        "summary": stored_summary,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gpu", type=int)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--validate-results", action="store_true")
    modes.add_argument(
        "--no-dispatch-probe-child", action="store_true", help=argparse.SUPPRESS
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_protocol(protocol_path)
    if args.no_dispatch_probe_child:
        if args.gpu is None:
            raise ProtocolError("probe child requires --gpu")
        print(
            json.dumps(
                no_dispatch_probe_child(protocol, selected_gpu=args.gpu),
                sort_keys=True,
            )
        )
        return 0
    if args.execute:
        if args.gpu is None:
            raise ProtocolError("--execute requires a selected physical GPU")
        result = execute(
            protocol,
            protocol_path,
            args.output_root,
            selected_gpu=args.gpu,
        )
    elif args.validate_results:
        result = validate_results(protocol, protocol_path, args.output_root)
    else:
        result = preflight(
            protocol,
            protocol_path,
            args.output_root,
            selected_gpu=args.gpu,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ready", result.get("valid", True)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
