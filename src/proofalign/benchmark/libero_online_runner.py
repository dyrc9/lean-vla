from __future__ import annotations

import argparse
from hashlib import sha256
import importlib
import json
from math import isfinite
import os
import secrets
import shutil
import sys
import tempfile
from time import monotonic_ns, perf_counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from proofalign.benchmark.attack_records import apply_attack_record, get_attack_record, load_attack_record_index
from proofalign.benchmark.libero_online_wrapper import (
    LiberoActionAbstractor,
    LiberoOnlineIntegrationError,
    ProofAlignLiberoWrapper,
    action_to_dict,
    make_libero_offscreen_env,
)
from proofalign.benchmark.libero_safety_adapter import LiberoSafetyAdapter, LiberoSafetyUnavailable
from proofalign.ctda import AuthorityEnvelope, TimeBase, digest_legacy_state, digest_payload
from proofalign.ctda_runtime import (
    ConditionalKinematicConfig,
    CTDARuntimeSession,
    ExactAllowlistEvidenceIssuer,
)
from proofalign.intent_parser import parse_intent
from proofalign.models import Decision, ExecutionDecision, ExecutionStep, SafetySpec


PolicyFactory = Callable[..., Callable[[str, Any, list[ExecutionStep]], Any]]


@dataclass(frozen=True)
class LiberoTaskRuntime:
    benchmark: Any
    task: Any
    task_id: int
    task_name: str
    instruction: str
    bddl_file: Path
    init_state: Any | None
    init_state_id: int
    frozen_bddl_bytes: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ZeroActionPolicy:
    """Small smoke-test policy that only proves the real env loop is wired."""

    def __init__(self, action_dim: int = 7, symbolic_action: dict[str, Any] | None = None) -> None:
        self.action_dim = action_dim
        self.symbolic_action = symbolic_action or {"type": "Stop"}

    def __call__(self, instruction: str, observation: Any, history: list[ExecutionStep]) -> dict[str, Any]:
        del instruction, observation, history
        return {
            "raw_action": [0.0] * self.action_dim,
            "proofalign_action": dict(self.symbolic_action),
        }


class ActionFilePolicy:
    """Replay raw VLA actions captured from another process."""

    def __init__(self, path: Path) -> None:
        self.actions = _load_action_file(path)
        if not self.actions:
            raise LiberoOnlineIntegrationError(f"Action file has no actions: {path}")
        self.index = 0

    def __call__(self, instruction: str, observation: Any, history: list[ExecutionStep]) -> Any:
        del instruction, observation, history
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action


def load_plugin(spec: str) -> Any:
    if ":" not in spec:
        raise LiberoOnlineIntegrationError(f"Plugin spec must be module:attribute, got {spec!r}")
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    module_name, attr_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    value: Any = module
    for part in attr_name.split("."):
        value = getattr(value, part)
    return value


def build_policy(args: argparse.Namespace) -> Callable[[str, Any, list[ExecutionStep]], Any]:
    if args.action_file:
        return ActionFilePolicy(Path(args.action_file))
    if args.policy:
        factory = load_plugin(args.policy)
        if args.policy_config:
            config = json.loads(Path(args.policy_config).read_text(encoding="utf-8"))
            return factory(**config)
        return factory()
    return ZeroActionPolicy(action_dim=args.action_dim, symbolic_action=json.loads(args.zero_symbolic_action))


def build_action_abstractor(args: argparse.Namespace) -> LiberoActionAbstractor | None:
    if not args.abstractor:
        return None
    factory = load_plugin(args.abstractor)
    if args.abstractor_config:
        config = json.loads(Path(args.abstractor_config).read_text(encoding="utf-8"))
        return factory(**config)
    return factory()


def load_libero_task_runtime(
    *,
    benchmark_name: str,
    task_id: int,
    init_state_id: int,
    bddl_file: str | None = None,
) -> LiberoTaskRuntime:
    try:
        from libero.libero import get_libero_path
        from libero.libero.benchmark import get_benchmark
    except Exception as exc:  # pragma: no cover - depends on external benchmark install.
        raise LiberoOnlineIntegrationError(
            "Could not import LIBERO/LIBERO-Safety. Install the benchmark package in editable mode first."
        ) from exc

    benchmark = get_benchmark(benchmark_name)()
    task = benchmark.get_task(task_id)
    task_name = str(getattr(task, "name", f"{benchmark_name}_{task_id}"))
    instruction = str(getattr(task, "language", "") or task_name.replace("_", " "))
    canonical_bddl_path = _resolve_task_bddl_path(get_libero_path("bddl_files"), task).resolve()
    if bddl_file:
        bddl_path = Path(bddl_file).expanduser().resolve()
    else:
        bddl_path = canonical_bddl_path
    init_state = _load_init_state(benchmark, task, task_id, init_state_id)
    return LiberoTaskRuntime(
        benchmark=benchmark,
        task=task,
        task_id=task_id,
        task_name=task_name,
        instruction=instruction,
        bddl_file=bddl_path,
        init_state=init_state,
        init_state_id=init_state_id,
        metadata={
            "benchmark_name": benchmark_name,
            "task_id": task_id,
            "task_name": task_name,
            "init_state_id": init_state_id,
            "bddl_file": str(bddl_path),
            "canonical_bddl_file": str(canonical_bddl_path),
        },
    )


def _resolve_task_bddl_path(bddl_root: str, task: Any) -> Path:
    root = Path(bddl_root)
    problem_folder = str(getattr(task, "problem_folder", ""))
    bddl_file = str(getattr(task, "bddl_file"))
    direct = root / problem_folder / bddl_file
    if direct.exists():
        return direct
    level = getattr(task, "level", None)
    if level is not None:
        level_dir = root / problem_folder / f"L{int(level)}"
        leveled = level_dir / bddl_file
        if leveled.exists():
            return leveled
        matched = _match_bddl_stem(level_dir, bddl_file)
        if matched is not None:
            return matched
    matched = _match_bddl_stem(root / problem_folder, bddl_file)
    if matched is not None:
        return matched
    return direct


def _match_bddl_stem(directory: Path, bddl_file: str) -> Path | None:
    """Handle LIBERO-Safety metadata/file-name drift within one task folder."""

    if not directory.exists():
        return None
    requested = Path(bddl_file).stem
    matches = [
        candidate
        for candidate in sorted(directory.glob("*.bddl"))
        if requested.startswith(candidate.stem) or candidate.stem.startswith(requested)
    ]
    return matches[0] if len(matches) == 1 else None


def create_initialized_env(runtime: LiberoTaskRuntime, args: argparse.Namespace) -> Any:
    snapshot_dir: Path | None = None
    bddl_path = runtime.bddl_file
    if getattr(args, "ctda", False):
        if runtime.frozen_bddl_bytes is None:
            raise LiberoOnlineIntegrationError("CTDA task root has no frozen BDDL bytes")
        snapshot_dir = Path(tempfile.mkdtemp(prefix="proofalign-ctda-bddl-"))
        bddl_path = snapshot_dir / runtime.bddl_file.name
        bddl_path.write_bytes(runtime.frozen_bddl_bytes)
        bddl_path.chmod(0o400)
    try:
        env = make_libero_offscreen_env(
            bddl_file_name=str(bddl_path),
            camera_heights=args.camera_height,
            camera_widths=args.camera_width,
            camera_names=args.camera_names.split(","),
            render_gpu_device_id=args.render_gpu_device_id,
            control_freq=args.control_freq,
            horizon=args.horizon,
        )
    except Exception:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise
    if snapshot_dir is not None:
        setattr(env, "_proofalign_bddl_snapshot_path", str(bddl_path))
        setattr(env, "_proofalign_bddl_snapshot_dir", str(snapshot_dir))
    try:
        if hasattr(env, "seed"):
            env.seed(args.seed)
        env.reset()
        if runtime.init_state is not None and hasattr(env, "set_init_state"):
            env.set_init_state(runtime.init_state)
        warmup_action = [0.0] * args.action_dim
        if args.action_dim:
            warmup_action[-1] = args.warmup_gripper
        for _ in range(args.warmup_steps):
            env.step(warmup_action)
    except Exception:
        try:
            if hasattr(env, "close"):
                env.close()
        finally:
            if snapshot_dir is not None:
                shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise
    return env


def run_online_episode(args: argparse.Namespace) -> ExecutionDecision:
    return run_online_episode_with_plugins(args)[0]


def run_online_episode_with_plugins(
    args: argparse.Namespace,
    *,
    policy: Callable[[str, Any, list[ExecutionStep]], Any] | None = None,
    action_abstractor: LiberoActionAbstractor | None = None,
) -> tuple[ExecutionDecision, dict[str, Any]]:
    episode_start = perf_counter()
    runtime = load_libero_task_runtime(
        benchmark_name=args.benchmark,
        task_id=args.task_id,
        init_state_id=args.init_state_id,
        bddl_file=args.bddl_file,
    )
    runtime = _prepare_ctda_trust_root(runtime, args)
    attack_records = load_attack_record_index(getattr(args, "attack_record", None))
    attack_record = get_attack_record(
        attack_records,
        suite=args.benchmark,
        task_id=args.task_id,
        init_state_id=args.init_state_id,
    )
    if getattr(args, "ctda", False) and attack_record is not None:
        claimed_original = attack_record.get("original_instruction")
        if claimed_original != runtime.instruction:
            raise LiberoOnlineIntegrationError(
                "CTDA attack record original_instruction must exactly match the benchmark task"
            )
    runtime = apply_attack_record(runtime, attack_record)
    runtime = replace(
        runtime,
        metadata={
            **runtime.metadata,
            "method_name": getattr(args, "method_name", None),
            "execution_config_digest": _execution_config_digest(args),
        },
    )
    env = create_initialized_env(runtime, args)
    task_success: bool | None = None
    try:
        if policy is None:
            policy = build_policy(args)
        else:
            reset_episode = getattr(policy, "reset_episode", None)
            if callable(reset_episode):
                reset_episode()
        if action_abstractor is None:
            action_abstractor = build_action_abstractor(args)
        spec = build_safety_spec(args)
        wrapper_kwargs: dict[str, Any] = {}
        if action_abstractor is not None:
            wrapper_kwargs["action_abstractor"] = action_abstractor
        wrapper_kwargs["max_chunk_steps"] = getattr(args, "max_chunk_steps", 8)
        wrapper_kwargs["stop_on_replan"] = not getattr(args, "continue_on_replan", False)
        wrapper = ProofAlignLiberoWrapper(env, runtime.instruction, spec, **wrapper_kwargs)
        try:
            wrapper.current_observation = getattr(env, "_get_observations", lambda: None)()
        except Exception:
            wrapper.current_observation = None
        if wrapper.current_observation is None:
            wrapper.reset()
        else:
            wrapper.current_state = wrapper.state_observer.observe(env, wrapper.current_observation)
        if getattr(args, "ctda", False):
            _configure_ctda(wrapper, runtime, spec, args)
        decision = wrapper.run_episode(policy, max_steps=args.max_steps)
        task_success = _check_task_success(env)
        episode_metadata = {
            "task_success": task_success,
            "episode_wall_time_seconds": perf_counter() - episode_start,
        }
        _write_result(args.output, runtime, decision, episode_metadata)
        return decision, episode_metadata
    finally:
        try:
            if hasattr(env, "close"):
                env.close()
        finally:
            snapshot_dir = getattr(env, "_proofalign_bddl_snapshot_dir", None)
            if snapshot_dir:
                shutil.rmtree(str(snapshot_dir), ignore_errors=True)


def build_safety_spec(args: argparse.Namespace) -> SafetySpec:
    if args.safety_spec:
        return SafetySpec.from_dict(json.loads(Path(args.safety_spec).read_text(encoding="utf-8")))
    root = os.environ.get("LIBERO_SAFETY_ROOT")
    if root:
        try:
            return SafetySpec.from_dict(LiberoSafetyAdapter(Path(root)).map_safety_spec(suite=args.benchmark))
        except LiberoSafetyUnavailable:
            pass
    return SafetySpec.from_dict({})


def _prepare_ctda_trust_root(
    runtime: LiberoTaskRuntime,
    args: argparse.Namespace,
) -> LiberoTaskRuntime:
    """Freeze benchmark-owned task inputs before any attack or environment action."""

    if not getattr(args, "ctda", False):
        return runtime
    if int(getattr(args, "warmup_steps", 0)) != 0:
        raise LiberoOnlineIntegrationError(
            "--ctda requires --warmup-steps 0; unmonitored warmup actions are outside CTDA"
        )
    selected = runtime.bddl_file.expanduser().resolve()
    if not selected.is_file():
        raise LiberoOnlineIntegrationError(f"CTDA requires a readable BDDL task root: {selected}")
    selected_bytes = selected.read_bytes()
    selected_digest = sha256(selected_bytes).hexdigest()
    canonical_value = runtime.metadata.get("canonical_bddl_file")
    if canonical_value:
        canonical = Path(str(canonical_value)).expanduser().resolve()
        if not canonical.is_file():
            raise LiberoOnlineIntegrationError(
                f"CTDA benchmark-owned canonical BDDL file is unreadable: {canonical}"
            )
        canonical_digest = sha256(canonical.read_bytes()).hexdigest()
        if not secrets.compare_digest(selected_digest, canonical_digest):
            raise LiberoOnlineIntegrationError(
                "--bddl-file content does not match the selected benchmark task"
            )
    metadata = dict(runtime.metadata)
    metadata.update(
        {
            "benchmark_instruction": runtime.instruction,
            "bddl_digest": selected_digest,
            "ctda_task_root_frozen_before_env": True,
        }
    )
    return replace(
        runtime,
        bddl_file=selected,
        frozen_bddl_bytes=selected_bytes,
        metadata=metadata,
    )


def _execution_config_digest(args: argparse.Namespace) -> str:
    """Bind result reuse to behavior-affecting CLI inputs and artifact contents."""

    artifact_args = (
        "bddl_file",
        "policy_config",
        "abstractor_config",
        "action_file",
        "attack_record",
        "safety_spec",
        "ctda_fallback_witness",
    )
    artifacts: dict[str, str | None] = {}
    for name in artifact_args:
        value = getattr(args, name, None)
        if not value:
            artifacts[name] = None
            continue
        path = Path(str(value)).expanduser()
        artifacts[name] = (
            sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        )
    return digest_payload(
        {
            "benchmark": getattr(args, "benchmark", None),
            "task_id": getattr(args, "task_id", None),
            "init_state_id": getattr(args, "init_state_id", None),
            "method_name": getattr(args, "method_name", None),
            "max_steps": getattr(args, "max_steps", None),
            "max_chunk_steps": getattr(args, "max_chunk_steps", None),
            "continue_on_replan": getattr(args, "continue_on_replan", False),
            "policy": getattr(args, "policy", None),
            "abstractor": getattr(args, "abstractor", None),
            "seed": getattr(args, "seed", None),
            "warmup_steps": getattr(args, "warmup_steps", None),
            "warmup_gripper": getattr(args, "warmup_gripper", None),
            "camera_height": getattr(args, "camera_height", None),
            "camera_width": getattr(args, "camera_width", None),
            "camera_names": getattr(args, "camera_names", None),
            "control_freq": getattr(args, "control_freq", None),
            "horizon": getattr(args, "horizon", None),
            "action_dim": getattr(args, "action_dim", None),
            "render_gpu_device_id": getattr(args, "render_gpu_device_id", None),
            "ctda": getattr(args, "ctda", False),
            "ctda_evidence_mode": getattr(args, "ctda_evidence_mode", None),
            "ctda_episode_nonce": getattr(args, "ctda_episode_nonce", None),
            "ctda_fallback_witness_sha256": getattr(
                args, "ctda_fallback_witness_sha256", None
            ),
            "artifacts": artifacts,
            "implementation": _implementation_digests(),
            "policy_source": _plugin_source_digest(getattr(args, "policy", None)),
            "abstractor_source": _plugin_source_digest(
                getattr(args, "abstractor", None)
            ),
        }
    )


def _implementation_digests() -> dict[str, str]:
    package_root = Path(__file__).resolve().parents[1]
    paths = (
        Path(__file__).resolve(),
        package_root / "ctda.py",
        package_root / "ctda_runtime.py",
        package_root / "checker.py",
        package_root / "lean_bridge.py",
        Path(__file__).with_name("libero_online_wrapper.py").resolve(),
    )
    return {
        str(path): sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }


def _plugin_source_digest(spec: Any) -> str | None:
    if not isinstance(spec, str) or not spec:
        return None
    module_name = spec.split(":", 1)[0]
    try:
        module_spec = importlib.util.find_spec(module_name)
        origin = Path(str(module_spec.origin)).resolve() if module_spec and module_spec.origin else None
    except (ImportError, AttributeError, ValueError):
        origin = None
    if origin is None or not origin.is_file():
        return "unresolved"
    return sha256(origin.read_bytes()).hexdigest()


def _configure_ctda(
    wrapper: ProofAlignLiberoWrapper,
    runtime: LiberoTaskRuntime,
    spec: SafetySpec,
    args: argparse.Namespace,
) -> None:
    if wrapper.current_state is None:
        raise LiberoOnlineIntegrationError("CTDA requires an observed initial state")
    fallback_path_value = getattr(args, "ctda_fallback_witness", None)
    if not fallback_path_value:
        raise LiberoOnlineIntegrationError(
            "--ctda requires --ctda-fallback-witness; fallback safety is never assumed"
        )
    fallback_path = Path(fallback_path_value).expanduser().resolve()
    if not fallback_path.is_file():
        raise LiberoOnlineIntegrationError(f"CTDA fallback witness does not exist: {fallback_path}")
    if not runtime.bddl_file.is_file():
        raise LiberoOnlineIntegrationError(
            f"CTDA authenticated task root requires a readable BDDL file: {runtime.bddl_file}"
        )
    bddl_digest = sha256(runtime.bddl_file.read_bytes()).hexdigest()
    frozen_bddl_digest = runtime.metadata.get("bddl_digest")
    if not isinstance(frozen_bddl_digest, str) or not secrets.compare_digest(
        bddl_digest, frozen_bddl_digest
    ):
        raise LiberoOnlineIntegrationError(
            "CTDA BDDL task root changed after environment creation"
        )
    snapshot_value = getattr(wrapper.env, "_proofalign_bddl_snapshot_path", None)
    if not snapshot_value:
        raise LiberoOnlineIntegrationError(
            "CTDA environment did not expose its immutable BDDL snapshot"
        )
    snapshot_path = Path(str(snapshot_value))
    if not snapshot_path.is_file() or not secrets.compare_digest(
        sha256(snapshot_path.read_bytes()).hexdigest(), frozen_bddl_digest
    ):
        raise LiberoOnlineIntegrationError(
            "CTDA environment BDDL snapshot differs from the frozen task root"
        )
    fallback_bytes = fallback_path.read_bytes()
    fallback_digest = sha256(fallback_bytes).hexdigest()
    expected_fallback_digest = str(
        getattr(args, "ctda_fallback_witness_sha256", "") or ""
    ).lower()
    if not expected_fallback_digest:
        raise LiberoOnlineIntegrationError(
            "--ctda requires --ctda-fallback-witness-sha256 as an explicit artifact trust anchor"
        )
    if not secrets.compare_digest(fallback_digest, expected_fallback_digest):
        raise LiberoOnlineIntegrationError(
            "CTDA fallback witness digest does not match --ctda-fallback-witness-sha256"
        )
    evidence_mode = getattr(args, "ctda_evidence_mode", None)
    if evidence_mode != "local-simulator-exact-allowlist":
        raise LiberoOnlineIntegrationError(
            "--ctda currently requires --ctda-evidence-mode local-simulator-exact-allowlist; "
            "this explicitly places the deterministic simulator adapter in the TCB"
        )
    control_period_ns = max(1, round(1_000_000_000 / max(1, int(args.control_freq))))
    spec_id = f"{args.benchmark}:{runtime.task_id}:{runtime.init_state_id}"
    action_low, action_high = _environment_action_bounds(wrapper.env)
    safety_spec_digest = digest_payload(asdict(spec))
    fallback_manifest = _validate_ctda_fallback_manifest(
        fallback_bytes,
        spec_id=spec_id,
        bddl_digest=bddl_digest,
        safety_spec_digest=safety_spec_digest,
        action_low=action_low,
        action_high=action_high,
        max_switch_latency_ns=control_period_ns * 2,
    )
    trusted_instruction = str(
        runtime.metadata.get("benchmark_instruction", runtime.instruction)
    )
    authority = AuthorityEnvelope(
        authority_id=f"libero:{args.benchmark}",
        source=f"{runtime.bddl_file}#sha256={bddl_digest}",
        version=f"task-{runtime.task_id}",
        attestation_digest=sha256(
            json.dumps(
                {
                    "bddl_digest": bddl_digest,
                    "instruction": trusted_instruction,
                    "task_id": runtime.task_id,
                    "init_state_id": runtime.init_state_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        authenticated=False,
    )
    time_base = TimeBase(
        clock_id="python-monotonic-ns",
        control_period_ns=control_period_ns,
        max_jitter_ns=control_period_ns // 10,
        monitor_latency_ns=control_period_ns,
        switch_latency_ns=int(fallback_manifest["worst_case_switch_latency_ns"]),
    )
    evidence = ("legacy_certificate",) if spec.require_certificates else ()
    issuer = ExactAllowlistEvidenceIssuer(
        producer_id=f"proofalign-libero-simulator:{args.benchmark}",
        producer_version="1",
    )
    created_at = monotonic_ns()
    wrapper.ctda_session = CTDARuntimeSession.from_legacy(
        parse_intent(trusted_instruction),
        wrapper.current_state,
        spec,
        authority,
        time_base,
        spec_id=spec_id,
        episode_nonce=(getattr(args, "ctda_episode_nonce", None) or secrets.token_hex(16)),
        evidence_issuer=issuer,
        now_ns=created_at,
        config=ConditionalKinematicConfig(
            control_period_ns=control_period_ns,
            fallback_id="hold",
            fallback_witness_digest=fallback_digest,
            fallback_verified=True,
            fallback_action=tuple(float(value) for value in fallback_manifest["fallback_action"]),
            semantic_evidence=evidence,
        ),
    )
    # Keep the validated artifact fields available for audit output without
    # treating the JSON declaration itself as a proof.
    setattr(wrapper.ctda_session, "fallback_manifest", fallback_manifest)
    setattr(
        wrapper.ctda_session,
        "assurance_scope",
        fallback_manifest["assurance_scope"],
    )
    runtime.metadata["ctda"] = {
        "enabled": True,
        "assurance_scope": fallback_manifest["assurance_scope"],
        "evidence_mode": evidence_mode,
        "bddl_digest": bddl_digest,
        "fallback_manifest_digest": fallback_digest,
        "safe_set_digest": fallback_manifest["safe_set_digest"],
        "assurance_artifact_digest": fallback_manifest["assurance_artifact_digest"],
        "safety_spec_digest": safety_spec_digest,
        "spec_digest": wrapper.ctda_session.supervisor.mission.spec_digest,
        "mission_claim_digest": wrapper.ctda_session.supervisor.mission.mission_claim_digest,
        "episode_nonce": wrapper.ctda_session.supervisor.mission.episode_nonce,
        "switch_latency_bound_ns": int(fallback_manifest["worst_case_switch_latency_ns"]),
        "environment_action_bounds": {
            "lower": list(action_low),
            "upper": list(action_high),
        },
        "fallback_action_digest": digest_payload(
            tuple(float(value) for value in fallback_manifest["fallback_action"])
        ),
        "initial_state_digest": digest_legacy_state(wrapper.current_state),
        "proof_verified": False,
    }


def _validate_ctda_fallback_manifest(
    raw: bytes,
    *,
    spec_id: str,
    bddl_digest: str,
    safety_spec_digest: str,
    action_low: tuple[float, ...],
    action_high: tuple[float, ...],
    max_switch_latency_ns: int,
) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiberoOnlineIntegrationError("CTDA fallback witness must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise LiberoOnlineIntegrationError("CTDA fallback witness must be a JSON object")
    expected = {
        "schema": "proofalign.ctda.fallback.v2",
        "spec_id": spec_id,
        "bddl_digest": bddl_digest,
        "safety_spec_digest": safety_spec_digest,
        "controller_id": "hold",
        "model_id": "libero-delta-kinematic-v1",
        "assurance_scope": "operator-pinned-simulator-test-only",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise LiberoOnlineIntegrationError(
                f"CTDA fallback witness {key!r} is not bound to the active runtime"
            )
    if "verified" in payload:
        raise LiberoOnlineIntegrationError(
            "CTDA fallback manifest must not self-assert proof verification"
        )
    if payload.get("operator_trusted") is not True:
        raise LiberoOnlineIntegrationError(
            "CTDA simulator fallback manifest requires explicit operator_trusted=true"
        )
    for key in ("safe_set_digest", "assurance_artifact_digest"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise LiberoOnlineIntegrationError(f"CTDA fallback witness is missing {key}")
    latency = payload.get("worst_case_switch_latency_ns")
    if type(latency) is not int or latency <= 0 or latency > max_switch_latency_ns:
        raise LiberoOnlineIntegrationError(
            "CTDA fallback witness exceeds the configured switch-latency bound"
        )
    action = payload.get("fallback_action")
    if not isinstance(action, list) or len(action) != len(action_low):
        raise LiberoOnlineIntegrationError("CTDA fallback action has the wrong dimension")
    if any(type(value) not in (int, float) or not isfinite(float(value)) for value in action):
        raise LiberoOnlineIntegrationError("CTDA fallback action contains a non-finite value")
    if any(
        float(value) < lower or float(value) > upper
        for value, lower, upper in zip(action, action_low, action_high)
    ):
        raise LiberoOnlineIntegrationError(
            "CTDA fallback action is outside the environment action bounds"
        )
    if any(abs(float(value)) > 1e-12 for value in action):
        raise LiberoOnlineIntegrationError(
            "the built-in hold controller requires the canonical all-zero action"
        )
    return dict(payload)


def _environment_action_bounds(env: Any) -> tuple[tuple[float, ...], tuple[float, ...]]:
    spec = getattr(env, "action_spec", None)
    if callable(spec):
        spec = spec()
    if not isinstance(spec, (tuple, list)) or len(spec) != 2:
        raise LiberoOnlineIntegrationError(
            "CTDA requires environment-provided action_spec bounds"
        )
    low = _finite_numeric_tuple(spec[0], "lower")
    high = _finite_numeric_tuple(spec[1], "upper")
    if not low or len(low) != len(high) or any(a > b for a, b in zip(low, high)):
        raise LiberoOnlineIntegrationError("environment action_spec bounds are malformed")
    return low, high


def _finite_numeric_tuple(value: Any, label: str) -> tuple[float, ...]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (tuple, list)):
        raise LiberoOnlineIntegrationError(f"environment action_spec {label} bound is not a vector")
    result: list[float] = []
    for item in value:
        if type(item) not in (int, float) or not isfinite(float(item)):
            raise LiberoOnlineIntegrationError(
                f"environment action_spec {label} bound contains a non-finite value"
            )
        result.append(float(item))
    return tuple(result)


def _load_init_state(benchmark: Any, task: Any, task_id: int, init_state_id: int) -> Any | None:
    for method_name, call_args in (
        ("get_task_init_states", (task_id,)),
        ("get_task_init_states_by_level_id", (getattr(task, "level", 0), getattr(task, "level_id", task_id))),
    ):
        method = getattr(benchmark, method_name, None)
        if not callable(method):
            continue
        try:
            init_states = method(*call_args)
            return _select_init_state(init_states, init_state_id)
        except Exception:
            continue
    init_file = getattr(task, "init_states_file", None)
    problem_folder = getattr(task, "problem_folder", None)
    if init_file and problem_folder:
        try:
            from libero.libero import get_libero_path
            import torch

            path = Path(get_libero_path("init_states")) / str(problem_folder) / str(init_file)
            return _select_init_state(torch.load(path), init_state_id)
        except Exception:
            return None
    return None


def _select_init_state(init_states: Any, init_state_id: int) -> Any:
    if init_states is None:
        return None
    try:
        return init_states[init_state_id]
    except Exception:
        return init_states


def _load_action_file(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "actions" in data:
        return list(data["actions"])
    if isinstance(data, dict) and "candidate_actions" in data:
        return [{"proofalign_action": action, "raw_action": action.get("raw_action", [0.0] * 7)} for action in data["candidate_actions"]]
    raise LiberoOnlineIntegrationError(f"Unsupported action file shape: {path}")


def _check_task_success(env: Any) -> bool | None:
    check = getattr(env, "check_success", None)
    if not callable(check):
        return None
    try:
        return bool(check())
    except Exception:
        return None


def _write_result(
    path: str | None,
    runtime: LiberoTaskRuntime,
    decision: ExecutionDecision,
    episode_metadata: dict[str, Any] | None = None,
) -> None:
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": runtime.metadata,
        "task_success": (episode_metadata or {}).get("task_success"),
        "runtime": {
            "episode_wall_time_seconds": (episode_metadata or {}).get("episode_wall_time_seconds"),
        },
        "decision": decision.decision.value,
        "explanation": decision.explanation,
        "final_state": decision.final_state.to_dict(),
        "trace": [
            {
                "action": step.action.kind.value,
                "object": step.action.object_id,
                "part": step.action.part,
                "region": step.action.region,
                "raw_action": step.raw_action,
                "raw_actions": step.raw_actions,
                "proofalign_action": step.proofalign_action or action_to_dict(step.action),
                "chunk_id": step.chunk_id,
                "contract": step.contract,
                "ctda": step.ctda,
                "summary": step.trace_summary.to_dict() if step.trace_summary else None,
                "decision": step.decision.value,
                "intent": step.intent_result.__dict__,
                "effect": step.effect_result.__dict__ if step.effect_result else None,
                "reward": step.reward,
                "done": step.done,
                "env_info": step.env_info,
                "runtime_seconds": step.runtime_seconds,
            }
            for step in decision.trace
        ],
    }
    output.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, Decision):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
    except Exception:
        pass
    return str(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ProofAlign online around a real LIBERO-Safety env.")
    parser.add_argument("--benchmark", default="affordance", help="LIBERO/LIBERO-Safety benchmark name.")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--bddl-file", help="Optional explicit BDDL file path.")
    parser.add_argument("--policy", help="Policy factory plugin as module:callable. Must return a callable policy.")
    parser.add_argument("--policy-config", help="JSON config passed to the policy factory.")
    parser.add_argument("--abstractor", help="Action abstractor factory plugin as module:callable.")
    parser.add_argument("--abstractor-config", help="JSON config passed to the abstractor factory.")
    parser.add_argument("--action-file", help="Replay a JSON/JSONL action file instead of loading a policy plugin.")
    parser.add_argument("--attack-record", help="JSON/JSONL file with SABER-style instruction overrides.")
    parser.add_argument("--safety-spec", help="JSON file with ProofAlign SafetySpec overrides.")
    parser.add_argument("--output", default="results/libero_online/episode.json")
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--max-chunk-steps", type=int, default=8)
    parser.add_argument("--continue-on-replan", action="store_true")
    parser.add_argument(
        "--ctda",
        action="store_true",
        help="Enable fail-closed CTDA prefix authorization and persistent trace monitoring.",
    )
    parser.add_argument(
        "--ctda-fallback-witness",
        help="Required with --ctda: structured, runtime-bound fallback witness JSON.",
    )
    parser.add_argument(
        "--ctda-fallback-witness-sha256",
        help="Required with --ctda: pinned SHA-256 trust anchor for the fallback witness.",
    )
    parser.add_argument(
        "--ctda-evidence-mode",
        choices=("local-simulator-exact-allowlist",),
        help="Explicit CTDA evidence TCB. The built-in mode is simulator/test only.",
    )
    parser.add_argument("--ctda-episode-nonce", help="Optional fixed nonce for reproducible audit replay.")
    parser.add_argument("--warmup-steps", type=int, default=5)
    parser.add_argument("--warmup-gripper", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--camera-height", type=int, default=128)
    parser.add_argument("--camera-width", type=int, default=128)
    parser.add_argument("--camera-names", default="agentview,robot0_eye_in_hand")
    parser.add_argument("--render-gpu-device-id", type=int, default=int(os.environ.get("MUJOCO_EGL_DEVICE_ID", -1)))
    parser.add_argument("--control-freq", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=1000)
    parser.add_argument("--action-dim", type=int, default=7)
    parser.add_argument("--zero-symbolic-action", default='{"type":"Stop"}')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    decision = run_online_episode(args)
    print(json.dumps({"decision": decision.decision.value, "explanation": decision.explanation}, indent=2))


if __name__ == "__main__":
    main()
