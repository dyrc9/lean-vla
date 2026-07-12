from __future__ import annotations

import argparse
import json
import os
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
    episode_args.max_chunk_steps = args.max_chunk_steps
    episode_args.continue_on_replan = args.continue_on_replan
    episode_args.ctda = args.ctda
    episode_args.ctda_fallback_witness = args.ctda_fallback_witness
    episode_args.ctda_fallback_witness_sha256 = args.ctda_fallback_witness_sha256
    episode_args.ctda_evidence_mode = args.ctda_evidence_mode
    episode_args.ctda_episode_nonce = args.ctda_episode_nonce
    episode_args.ctda_evaluator = args.ctda_evaluator
    episode_args.ctda_artifact_dir = args.ctda_artifact_dir
    episode_args.ctda_lean_timeout_seconds = args.ctda_lean_timeout_seconds
    episode_args.method_name = args.method_name
    episode_args.warmup_steps = args.warmup_steps
    episode_args.warmup_gripper = args.warmup_gripper
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
    episode_args.attack_record = args.attack_record
    episode_args.bddl_file = None
    return episode_args


def load_episode(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"episode result must be a JSON object: {path}")
    return payload | {"_path": str(path)}


def _info_has_cost_or_collision(info: Any) -> bool:
    if not isinstance(info, dict):
        return False
    if info.get("collision") is True:
        return True
    cost = info.get("cost")
    if isinstance(cost, dict):
        if any(bool(value) for value in cost.values()):
            return True
    elif cost not in (None, {}, [], 0, 0.0, False):
        return True
    nested_fallback = info.get("proofalign_fallback_env_info")
    return nested_fallback is not info and _info_has_cost_or_collision(nested_fallback)


def has_cost_or_collision(episode: dict[str, Any]) -> bool:
    for step in episode.get("trace", []):
        if _info_has_cost_or_collision(step.get("env_info")):
            return True
        ctda = step.get("ctda") or {}
        fallback_trace = ctda.get("fallback_trace") or {}
        if _info_has_cost_or_collision(fallback_trace.get("env_info")):
            return True
        receipt = fallback_trace.get("receipt") or ctda.get("fallback_switch") or {}
        postcondition = receipt.get("postcondition") or {}
        if postcondition.get("no_collision") is False or postcondition.get("no_cost") is False:
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
    init_breakdown: dict[str, dict[str, Any]] = defaultdict(
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
    ctda_static_verdicts: Counter[str] = Counter()
    ctda_monitor_verdicts: Counter[str] = Counter()
    ctda_records = 0
    ctda_fallback_attempts = 0
    ctda_fallback_successes = 0
    ctda_fallback_failures = 0
    ctda_fallback_errors = 0

    for episode in episodes:
        metadata = episode.get("metadata", {})
        suite = metadata.get("benchmark_name", "unknown")
        init_state_id = str(metadata.get("init_state_id", "unknown"))
        trace = episode.get("trace", [])
        trace_lengths.append(len(trace))
        for breakdown in (suite_breakdown[suite], init_breakdown[init_state_id]):
            breakdown["total_episodes"] += 1
            breakdown["completed_episodes"] += 1
            breakdown["final_decisions"][episode.get("decision", "unknown")] += 1
            breakdown["trace_lengths"].append(len(trace))
        task_success = episode.get("task_success")
        suite_breakdown[suite]["task_success"][str(task_success)] += 1
        init_breakdown[init_state_id]["task_success"][str(task_success)] += 1
        wall_time = (episode.get("runtime") or {}).get("episode_wall_time_seconds")
        if isinstance(wall_time, (int, float)):
            episode_wall_times.append(float(wall_time))
        for step in trace:
            decision = step.get("decision", "unknown")
            trace_decisions[decision] += 1
            suite_breakdown[suite]["trace_decisions"][decision] += 1
            init_breakdown[init_state_id]["trace_decisions"][decision] += 1
            runtime = step.get("runtime_seconds") or {}
            if isinstance(runtime.get("policy"), (int, float)):
                policy_times.append(float(runtime["policy"]))
            if isinstance(runtime.get("env_step"), (int, float)):
                env_step_times.append(float(runtime["env_step"]))
            proofalign_time = 0.0
            for key in ("intent_check", "ctda_prefix_pre", "ctda_monitor", "effect_check"):
                if isinstance(runtime.get(key), (int, float)):
                    proofalign_time += float(runtime[key])
            proofalign_times.append(proofalign_time)
            ctda = step.get("ctda") or {}
            if ctda.get("static_verdict"):
                ctda_static_verdicts[str(ctda["static_verdict"])] += 1
            if ctda.get("monitor_verdict"):
                ctda_monitor_verdicts[str(ctda["monitor_verdict"])] += 1
            if ctda.get("record_digest"):
                ctda_records += 1
            fallback_switch = ctda.get("fallback_switch") or {}
            fallback_trace = ctda.get("fallback_trace") or {}
            fallback_error = ctda.get("fallback_error")
            if fallback_switch or fallback_trace or fallback_error:
                ctda_fallback_attempts += 1
                receipt = fallback_switch or fallback_trace.get("receipt") or {}
                if receipt.get("succeeded") is True:
                    ctda_fallback_successes += 1
                else:
                    ctda_fallback_failures += 1
                fallback_info = fallback_trace.get("env_info") or {}
                trace_has_error = bool(
                    fallback_trace.get("observation_error")
                    or fallback_info.get("fallback_exception")
                    or fallback_info.get("fallback_observation_exception")
                    or fallback_info.get("fallback_actuator_evidence_error")
                )
                if fallback_error or trace_has_error:
                    ctda_fallback_errors += 1

    for failure in failures:
        suite = failure.get("suite", "unknown")
        init_state_id = str(failure.get("init_state_id", "unknown"))
        suite_breakdown[suite]["total_episodes"] += 1
        suite_breakdown[suite]["failed_episodes"] += 1
        init_breakdown[init_state_id]["total_episodes"] += 1
        init_breakdown[init_state_id]["failed_episodes"] += 1

    def finalize_breakdown(breakdown: dict[str, dict[str, Any]]) -> dict[str, Any]:
        finalized: dict[str, Any] = {}
        for key, data in sorted(breakdown.items()):
            lengths = data["trace_lengths"]
            finalized[key] = {
                "total_episodes": data["total_episodes"],
                "completed_episodes": data["completed_episodes"],
                "failed_episodes": data["failed_episodes"],
                "final_decisions": dict(data["final_decisions"]),
                "trace_decisions": dict(data["trace_decisions"]),
                "average_trace_length": sum(lengths) / len(lengths) if lengths else None,
                "task_success": dict(data["task_success"]),
            }
        return finalized

    suites = finalize_breakdown(suite_breakdown)
    init_states = finalize_breakdown(init_breakdown)

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
        "per_init_state_breakdown": init_states,
        "failure_list": failures,
        "output_files": output_files,
        "task_success_counts": dict(Counter(str(ep.get("task_success")) for ep in episodes)),
        "episodes_with_cost_or_collision": sum(1 for episode in episodes if has_cost_or_collision(episode)),
        "ctda": {
            "static_verdict_counts": dict(ctda_static_verdicts),
            "monitor_verdict_counts": dict(ctda_monitor_verdicts),
            "record_count": ctda_records,
            "fallback_attempt_count": ctda_fallback_attempts,
            "fallback_success_count": ctda_fallback_successes,
            "fallback_failure_count": ctda_fallback_failures,
            "fallback_error_count": ctda_fallback_errors,
        },
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
    parser.add_argument("--init-state-ids", help="Init state ids, e.g. 0-4 or 0,1,2. Overrides --init-state-id.")
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--max-chunk-steps", type=int, default=8)
    parser.add_argument("--continue-on-replan", action="store_true")
    parser.add_argument("--ctda", action="store_true")
    parser.add_argument("--ctda-fallback-witness")
    parser.add_argument("--ctda-fallback-witness-sha256")
    parser.add_argument(
        "--ctda-evidence-mode",
        choices=("local-simulator-exact-allowlist",),
    )
    parser.add_argument("--ctda-episode-nonce")
    parser.add_argument(
        "--ctda-evaluator",
        choices=("ctda-python-reference", "ctda-lean-kernel", "ctda-shadow"),
        default="ctda-python-reference",
    )
    parser.add_argument("--ctda-artifact-dir")
    parser.add_argument("--ctda-lean-timeout-seconds", type=float, default=10.0)
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
    parser.add_argument("--attack-record")
    parser.add_argument("--safety-spec")
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--warmup-gripper", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--camera-height", type=int, default=224)
    parser.add_argument("--camera-width", type=int, default=224)
    parser.add_argument("--camera-names", default="agentview,robot0_eye_in_hand")
    parser.add_argument("--render-gpu-device-id", type=int, default=-1)
    parser.add_argument("--control-freq", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=1000)
    parser.add_argument("--action-dim", type=int, default=7)
    return parser.parse_args(argv)


def validate_batch_args(args: argparse.Namespace) -> None:
    if args.skip_existing and args.ctda:
        raise ValueError(
            "--skip-existing is disabled in CTDA mode because benchmark task roots, "
            "initial state, effective safety spec, environment version, and action "
            "bounds must be revalidated in the live environment"
        )


def write_run_config(
    output_dir: Path,
    args: argparse.Namespace,
    suites: list[str],
    task_ids: list[int],
    init_state_ids: list[int],
) -> None:
    payload = {
        "args": vars(args),
        "tasks": [
            {"suite": suite, "task_id": task_id, "init_state_id": init_state_id}
            for suite in suites
            for task_id in task_ids
            for init_state_id in init_state_ids
        ],
        "environment": {
            "LIBERO_SAFETY_ROOT": os.environ.get("LIBERO_SAFETY_ROOT"),
            "HF_ENDPOINT": os.environ.get("HF_ENDPOINT"),
            "HF_HOME": os.environ.get("HF_HOME"),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "MUJOCO_EGL_DEVICE_ID": os.environ.get("MUJOCO_EGL_DEVICE_ID"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
    }
    (output_dir / "run_config.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_batch_args(args)
    suites = parse_list(args.suites)
    task_ids = parse_task_ids(args.task_ids)
    init_state_ids = parse_task_ids(args.init_state_ids) if args.init_state_ids else [args.init_state_id]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_run_config(output_dir, args, suites, task_ids, init_state_ids)
    failure_path = Path(args.failure_jsonl)
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text("", encoding="utf-8")

    shared_args = build_episode_args(args, suites[0], task_ids[0], output_dir / "unused.json")
    shared_policy = None if args.action_file else build_policy(shared_args)
    shared_abstractor = build_action_abstractor(shared_args)

    episodes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    output_files: list[str] = []
    expected_total = len(suites) * len(task_ids) * len(init_state_ids)

    for suite in suites:
        for task_id in task_ids:
            for init_state_id in init_state_ids:
                args.init_state_id = init_state_id
                output = output_dir / f"{suite}_task{task_id}_init{init_state_id}_{args.method_name}.json"
                output_files.append(str(output))
                episode_args = build_episode_args(args, suite, task_id, output)
                try:
                    if not (args.skip_existing and output.exists()):
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
                        "init_state_id": init_state_id,
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
