from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from time import perf_counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from proofalign.benchmark.libero_online_wrapper import (
    LiberoActionAbstractor,
    LiberoOnlineIntegrationError,
    ProofAlignLiberoWrapper,
    action_to_dict,
    make_libero_offscreen_env,
)
from proofalign.benchmark.libero_safety_adapter import LiberoSafetyAdapter, LiberoSafetyUnavailable
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
    if bddl_file:
        bddl_path = Path(bddl_file).expanduser().resolve()
    else:
        bddl_path = _resolve_task_bddl_path(get_libero_path("bddl_files"), task)
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
        leveled = root / problem_folder / f"L{int(level)}" / bddl_file
        if leveled.exists():
            return leveled
    return direct


def create_initialized_env(runtime: LiberoTaskRuntime, args: argparse.Namespace) -> Any:
    env = make_libero_offscreen_env(
        bddl_file_name=str(runtime.bddl_file),
        camera_heights=args.camera_height,
        camera_widths=args.camera_width,
        camera_names=args.camera_names.split(","),
        render_gpu_device_id=args.render_gpu_device_id,
        control_freq=args.control_freq,
        horizon=args.horizon,
    )
    if hasattr(env, "seed"):
        env.seed(args.seed)
    env.reset()
    if runtime.init_state is not None and hasattr(env, "set_init_state"):
        env.set_init_state(runtime.init_state)
    for _ in range(args.warmup_steps):
        env.step([0.0] * args.action_dim)
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
        wrapper = ProofAlignLiberoWrapper(env, runtime.instruction, spec, **wrapper_kwargs)
        try:
            wrapper.current_observation = getattr(env, "_get_observations", lambda: None)()
        except Exception:
            wrapper.current_observation = None
        if wrapper.current_observation is None:
            wrapper.reset()
        else:
            wrapper.current_state = wrapper.state_observer.observe(env, wrapper.current_observation)
        decision = wrapper.run_episode(policy, max_steps=args.max_steps)
        task_success = _check_task_success(env)
        episode_metadata = {
            "task_success": task_success,
            "episode_wall_time_seconds": perf_counter() - episode_start,
        }
        _write_result(args.output, runtime, decision, episode_metadata)
        return decision, episode_metadata
    finally:
        if hasattr(env, "close"):
            env.close()


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
    parser.add_argument("--safety-spec", help="JSON file with ProofAlign SafetySpec overrides.")
    parser.add_argument("--output", default="results/libero_online/episode.json")
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--max-chunk-steps", type=int, default=8)
    parser.add_argument("--warmup-steps", type=int, default=5)
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
