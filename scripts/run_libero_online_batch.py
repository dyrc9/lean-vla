from __future__ import annotations

import argparse
import json
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from proofalign.benchmark.libero_online_runner import (
    build_action_abstractor,
    build_policy,
    parse_args as parse_episode_args,
    run_online_episode_with_plugins,
)


DECISIONS = ("allow", "reject", "replan", "safe_stop")


def parse_list(values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(",") if part.strip())
    return items


def parse_task_ids(value: str) -> list[int]:
    task_ids: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            task_ids.extend(range(int(start), int(end) + 1))
        else:
            task_ids.append(int(part))
    return list(dict.fromkeys(task_ids))


def build_episode_args(args: argparse.Namespace, suite: str, task_id: int, output: Path) -> argparse.Namespace:
    episode_args = parse_episode_args([])
    episode_args.benchmark = suite
    episode_args.task_id = task_id
    episode_args.init_state_id = args.init_state_id
    episode_args.output = str(output)
    episode_args.max_steps = args.max_steps
    episode_args.warmup_steps = args.warmup_steps
    episode_args.seed = args.seed
    episode_args.camera_height = args.camera_height
    episode_args.camera_width = args.camera_width
    episode_args.camera_names = args.camera_names
    episode_args.render_gpu_device_id = args.render_gpu_device_id
    episode_args.control_freq = args.control_freq
    episode_args.horizon = args.horizon
    episode_args.action_dim = args.action_dim
    episode_args.policy = args.policy
    episode_args.policy_config = args.policy_config
    episode_args.abstractor = args.abstractor
    episode_args.abstractor_config = args.abstractor_config
    episode_args.safety_spec = args.safety_spec
    episode_args.action_file = args.action_file
    episode_args.bddl_file = None
    return episode_args


def load_episode(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) | {"_path": str(path)}


def has_cost_or_collision(episode: dict[str, Any]) -> bool:
    for step in episode.get("trace", []):
        info = step.get("env_info") or {}
        if info.get("collision"):
            return True
        cost = info.get("cost")
        if isinstance(cost, dict) and any(bool(value) for value in cost.values()):
            return True
        if cost not in (None, {}, [], 0, 0.0, False):
            return True
    return False


def summarize(
    *,
    expected_total: int,
    episodes: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    output_files: list[str],
) -> dict[str, Any]:
    final_decisions = Counter(ep.get("decision", "unknown") for ep in episodes)
    trace_decisions: Counter[str] = Counter()
    suite_breakdown: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total_episodes": 0,
            "completed_episodes": 0,
            "failed_episodes": 0,
            "final_decisions": Counter(),
            "trace_decisions": Counter(),
            "trace_lengths": [],
            "task_success": Counter(),
        }
    )
    trace_lengths: list[int] = []
    policy_times: list[float] = []
    env_step_times: list[float] = []
    proofalign_times: list[float] = []
    episode_wall_times: list[float] = []

    for episode in episodes:
        suite = episode.get("metadata", {}).get("benchmark_name", "unknown")
        trace = episode.get("trace", [])
        trace_lengths.append(len(trace))
        suite_breakdown[suite]["total_episodes"] += 1
        suite_breakdown[suite]["completed_episodes"] += 1
        suite_breakdown[suite]["final_decisions"][episode.get("decision", "unknown")] += 1
        suite_breakdown[suite]["trace_lengths"].append(len(trace))
        task_success = episode.get("task_success")
        suite_breakdown[suite]["task_success"][str(task_success)] += 1
        wall_time = (episode.get("runtime") or {}).get("episode_wall_time_seconds")
        if isinstance(wall_time, (int, float)):
            episode_wall_times.append(float(wall_time))
        for step in trace:
            decision = step.get("decision", "unknown")
            trace_decisions[decision] += 1
            suite_breakdown[suite]["trace_decisions"][decision] += 1
            runtime = step.get("runtime_seconds") or {}
            if isinstance(runtime.get("policy"), (int, float)):
                policy_times.append(float(runtime["policy"]))
            if isinstance(runtime.get("env_step"), (int, float)):
                env_step_times.append(float(runtime["env_step"]))
            proofalign_time = 0.0
            for key in ("intent_check", "effect_check"):
                if isinstance(runtime.get(key), (int, float)):
                    proofalign_time += float(runtime[key])
            proofalign_times.append(proofalign_time)

    for failure in failures:
        suite = failure.get("suite", "unknown")
        suite_breakdown[suite]["total_episodes"] += 1
        suite_breakdown[suite]["failed_episodes"] += 1

    suites: dict[str, Any] = {}
    for suite, data in sorted(suite_breakdown.items()):
        lengths = data["trace_lengths"]
        suites[suite] = {
            "total_episodes": data["total_episodes"],
            "completed_episodes": data["completed_episodes"],
            "failed_episodes": data["failed_episodes"],
            "final_decisions": dict(data["final_decisions"]),
            "trace_decisions": dict(data["trace_decisions"]),
            "average_trace_length": sum(lengths) / len(lengths) if lengths else None,
            "task_success": dict(data["task_success"]),
        }

    def average(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    summary = {
        "total_episodes": expected_total,
        "completed_episodes": len(episodes),
        "failed_episodes": len(failures),
        "allow": final_decisions.get("allow", 0),
        "reject": final_decisions.get("reject", 0),
        "replan": final_decisions.get("replan", 0),
        "safe_stop": final_decisions.get("safe_stop", 0),
        "final_decision_counts": {decision: final_decisions.get(decision, 0) for decision in DECISIONS},
        "trace_decision_counts": {decision: trace_decisions.get(decision, 0) for decision in DECISIONS},
        "average_trace_length": average([float(length) for length in trace_lengths]),
        "per_suite_breakdown": suites,
        "failure_list": failures,
        "output_files": output_files,
        "task_success_counts": dict(Counter(str(ep.get("task_success")) for ep in episodes)),
        "episodes_with_cost_or_collision": sum(1 for episode in episodes if has_cost_or_collision(episode)),
        "runtime_seconds": {
            "average_episode_wall": average(episode_wall_times),
            "average_policy_step": average(policy_times),
            "average_env_step": average(env_step_times),
            "average_proofalign_step": average(proofalign_times),
        },
    }
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a LIBERO-Safety online VLA batch with ProofAlign.")
    parser.add_argument("--suites", nargs="+", default=["affordance"], help="Suite names, comma or space separated.")
    parser.add_argument("--task-ids", default="0-4", help="Task ids, e.g. 0-4 or 0,1,2.")
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--output-dir", default="results/libero_online")
    parser.add_argument("--method-name", default="openvla_oft_dual")
    parser.add_argument("--summary", default="results/libero_online/summary_openvla_oft.json")
    parser.add_argument("--failure-jsonl", default="results/libero_online/failures_openvla_oft.jsonl")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--policy", default="experiments.libero_vla_plugin:create_policy")
    parser.add_argument("--policy-config")
    parser.add_argument("--abstractor", default="experiments.libero_vla_plugin:create_abstractor")
    parser.add_argument("--abstractor-config")
    parser.add_argument("--action-file")
    parser.add_argument("--safety-spec")
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--camera-height", type=int, default=224)
    parser.add_argument("--camera-width", type=int, default=224)
    parser.add_argument("--camera-names", default="agentview,robot0_eye_in_hand")
    parser.add_argument("--render-gpu-device-id", type=int, default=-1)
    parser.add_argument("--control-freq", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=1000)
    parser.add_argument("--action-dim", type=int, default=7)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    suites = parse_list(args.suites)
    task_ids = parse_task_ids(args.task_ids)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    failure_path = Path(args.failure_jsonl)
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text("", encoding="utf-8")

    shared_args = build_episode_args(args, suites[0], task_ids[0], output_dir / "unused.json")
    shared_policy = None if args.action_file else build_policy(shared_args)
    shared_abstractor = build_action_abstractor(shared_args)

    episodes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    output_files: list[str] = []
    expected_total = len(suites) * len(task_ids)

    for suite in suites:
        for task_id in task_ids:
            output = output_dir / f"{suite}_task{task_id}_init{args.init_state_id}_{args.method_name}.json"
            output_files.append(str(output))
            if args.skip_existing and output.exists():
                episodes.append(load_episode(output))
                continue
            episode_args = build_episode_args(args, suite, task_id, output)
            try:
                run_online_episode_with_plugins(
                    episode_args,
                    policy=shared_policy,
                    action_abstractor=shared_abstractor,
                )
                episodes.append(load_episode(output))
            except Exception as exc:
                failure = {
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": args.init_state_id,
                    "output": str(output),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
                failures.append(failure)
                with failure_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(failure) + "\n")

            summary = summarize(
                expected_total=expected_total,
                episodes=episodes,
                failures=failures,
                output_files=output_files,
            )
            Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
