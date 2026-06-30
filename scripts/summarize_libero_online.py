from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def main() -> None:
    results_dir = Path("results/libero_online")
    paths = sorted(path for path in results_dir.glob("*.json") if path.name != "summary.json")
    episodes = [json.loads(path.read_text(encoding="utf-8")) | {"_path": str(path)} for path in paths]

    decision_counts = Counter(ep.get("decision", "unknown") for ep in episodes)
    suite_breakdown: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "decisions": Counter(), "steps": 0})
    intent_failures = 0
    effect_failures = 0
    collision_or_cost = 0
    step_counts = []

    for episode in episodes:
        suite = episode.get("metadata", {}).get("benchmark_name", "unknown")
        trace = episode.get("trace", [])
        step_counts.append(len(trace))
        suite_breakdown[suite]["total"] += 1
        suite_breakdown[suite]["decisions"][episode.get("decision", "unknown")] += 1
        suite_breakdown[suite]["steps"] += len(trace)
        for step in trace:
            intent = step.get("intent") or {}
            effect = step.get("effect") or {}
            if intent and not intent.get("passed", False):
                intent_failures += 1
            if effect and not effect.get("passed", False):
                effect_failures += 1
            violations = [*intent.get("violations", []), *effect.get("violations", [])]
            if any("collision" in str(item).lower() or "cost" in str(item).lower() for item in violations):
                collision_or_cost += 1

    suites = {}
    for suite, data in suite_breakdown.items():
        total = data["total"]
        suites[suite] = {
            "total": total,
            "decisions": dict(data["decisions"]),
            "average_steps": data["steps"] / total if total else None,
        }

    summary = {
        "total_episodes": len(episodes),
        "allow": decision_counts.get("allow", 0),
        "reject": decision_counts.get("reject", 0),
        "replan": decision_counts.get("replan", 0),
        "safe_stop": decision_counts.get("safe_stop", 0),
        "intent_failures": intent_failures,
        "effect_failures": effect_failures,
        "collision_or_cost_violations": collision_or_cost,
        "average_steps": sum(step_counts) / len(step_counts) if step_counts else None,
        "average_runtime_seconds": None,
        "suite_breakdown": suites,
        "artifacts": [episode["_path"] for episode in episodes],
        "notes": [
            "Results are real LIBERO-Safety OffScreenRenderEnv online runs.",
            "Replay outputs use experiments/libero_stop_replay.json, not a real VLA policy.",
            "smoke_affordance_task2_init0.json confirms OffScreenRenderEnv.step execution with effect checks.",
        ],
    }
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
