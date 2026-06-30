from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from proofalign.baselines import BaselineMode, BaselineRunner
from proofalign.checker import DualAlignmentChecker
from proofalign.models import ExecutionDecision, SafetySpec, WorldState
from proofalign.simulator import DiscreteSimulator


@dataclass
class EpisodeRecord:
    episode_id: str
    category: str
    expected_decision: str
    mode: str
    decision: str
    elapsed_ms: float
    violations: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)


@dataclass
class Metrics:
    mode: str
    episodes: int = 0
    expected_unsafe: int = 0
    rejected_or_stopped: int = 0
    unsafe_rejected: int = 0
    false_rejections: int = 0
    spec_violations: int = 0
    collision_decisions: int = 0
    total_elapsed_ms: float = 0.0

    def update(self, record: EpisodeRecord) -> None:
        self.episodes += 1
        self.total_elapsed_ms += record.elapsed_ms
        expected_unsafe = record.expected_decision != "allow"
        blocked = record.decision in {"reject", "replan", "safe_stop"}
        if expected_unsafe:
            self.expected_unsafe += 1
        if blocked:
            self.rejected_or_stopped += 1
        if expected_unsafe and blocked:
            self.unsafe_rejected += 1
        if not expected_unsafe and blocked:
            self.false_rejections += 1
        if record.violations:
            self.spec_violations += 1
        if record.decision == "safe_stop":
            self.collision_decisions += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "episodes": self.episodes,
            "expected_unsafe": self.expected_unsafe,
            "unsafe_action_rejection_rate": self.unsafe_rejected / self.expected_unsafe if self.expected_unsafe else 0.0,
            "false_rejection_rate": self.false_rejections / max(1, self.episodes - self.expected_unsafe),
            "spec_violation_rate": self.spec_violations / self.episodes if self.episodes else 0.0,
            "rejection_or_stop_rate": self.rejected_or_stopped / self.episodes if self.episodes else 0.0,
            "collision_stop_rate": self.collision_decisions / self.episodes if self.episodes else 0.0,
            "avg_elapsed_ms": self.total_elapsed_ms / self.episodes if self.episodes else 0.0,
        }


def load_json_episode(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("name", path.stem)
    data.setdefault("category", "toy")
    return data


def run_episode(mode: BaselineMode, data: dict[str, Any], runner: BaselineRunner) -> EpisodeRecord:
    started = time.perf_counter()
    decision: ExecutionDecision = runner.run(
        mode,
        data["instruction"],
        WorldState.from_dict(data["initial_state"]),
        SafetySpec.from_dict(data.get("safety_spec")),
        data["candidate_actions"],
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    violations = []
    for step in decision.trace:
        if step.intent_result:
            violations.extend(report.to_dict() for report in step.intent_result.violation_reports)
        if step.effect_result:
            violations.extend(report.to_dict() for report in step.effect_result.violation_reports)
    return EpisodeRecord(
        episode_id=str(data["name"]),
        category=str(data.get("category", "toy")),
        expected_decision=str(data.get("expected_decision", "allow")),
        mode=mode.value,
        decision=decision.decision.value,
        elapsed_ms=elapsed_ms,
        violations=violations,
        explanation=decision.explanation,
    )


def run_directory(
    input_dir: Path,
    output_dir: Path,
    modes: list[BaselineMode],
    warm_lean: bool = True,
) -> dict[str, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    episodes = [load_json_episode(path) for path in sorted(input_dir.glob("*.json"))]
    runner = BaselineRunner(DualAlignmentChecker(), DiscreteSimulator())
    if warm_lean:
        runner.checker.lean.check_project()
    summary: dict[str, dict[str, Any]] = {}
    for mode in modes:
        metrics = Metrics(mode.value)
        records_path = output_dir / f"{mode.value}.jsonl"
        with records_path.open("w", encoding="utf-8") as handle:
            for episode in episodes:
                record = run_episode(mode, episode, runner)
                metrics.update(record)
                handle.write(record.to_json() + "\n")
        summary[mode.value] = metrics.to_dict()
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ProofAlign baseline/ablation experiments.")
    parser.add_argument("--input", default="examples/tasks", help="Directory of JSON episodes.")
    parser.add_argument("--output", default="results/toy", help="Directory for JSONL records and summary metrics.")
    parser.add_argument(
        "--modes",
        default="vla_only,collision_only,intent_only,effect_only,dual",
        help="Comma-separated baseline modes.",
    )
    args = parser.parse_args()
    modes = [BaselineMode(item.strip()) for item in args.modes.split(",") if item.strip()]
    summary = run_directory(Path(args.input), Path(args.output), modes)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
