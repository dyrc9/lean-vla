#!/usr/bin/env python3
"""Run the frozen remote full-120 clean or attacked stage fail-closed."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts import run_v15_bounded_state_triggered_task_utility_qualification as clean_runner  # noqa: E402
from scripts import run_v15_14_unified_force_envelope_attacked_task_utility_qualification as attacked_runner  # noqa: E402


CLEAN_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_clean_protocol_20260818.json"
ATTACKED_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_attacked_protocol_20260818.json"
UMBRELLA_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_successor_protocol_20260818.json"
CLEAN_ANALYSIS = REPO_ROOT / "results/proofalign_remote_full120_clean_20260818_fresh1/terminal_analysis.json"


class RemoteFull120Error(RuntimeError):
    pass


def _protocol(stage: str) -> tuple[Path, dict[str, Any], Any]:
    path = CLEAN_PROTOCOL if stage == "clean" else ATTACKED_PROTOCOL
    runner = clean_runner if stage == "clean" else attacked_runner
    return path, load_json_object(path), runner


def _verify_umbrella(stage_protocol: Mapping[str, Any]) -> None:
    umbrella = load_json_object(UMBRELLA_PROTOCOL)
    if umbrella.get("outcomes_observed") is not False:
        raise RemoteFull120Error("successor is not outcome-blind")
    if umbrella["reuse_decision"] != {
        "audit_path": "experiments/proofalign_remote_full120_baseline_reuse_audit_20260818.json",
        "new_episode_count": 960,
        "reused_episode_count": 0,
    }:
        raise RemoteFull120Error("frozen reuse decision differs")
    if len(stage_protocol.get("schedule", [])) != 480:
        raise RemoteFull120Error("stage schedule is not 480 episodes")


def _require_clean_gate() -> None:
    if not CLEAN_ANALYSIS.is_file():
        raise RemoteFull120Error("attacked stage blocked: clean terminal analysis absent")
    payload = load_json_object(CLEAN_ANALYSIS)
    if (
        payload.get("classification") != "remote_full120_clean_gate_pass"
        or payload.get("present_episode_count") != 480
        or payload.get("valid_episode_count") != 480
        or payload.get("episode_artifacts_verified") is not True
        or payload.get("analysis", {}).get("clean_gate_pass") is not True
    ):
        raise RemoteFull120Error("attacked stage blocked: clean terminal gate did not pass")


@contextmanager
def _append_only_execution_ledger(protocol: Mapping[str, Any]) -> Iterator[None]:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    ledger = root / "execution_ledger.jsonl"
    schedule = {str(row["episode_id"]): row for row in protocol["schedule"]}
    original = saber_io.atomic_json
    seen: set[str] = set()

    def wrapped(path: Path, payload: Any) -> None:
        original(path, payload)
        if Path(path) != root / "run_manifest.json" or not isinstance(payload, Mapping):
            return
        for episode_id in payload.get("completed_episode_ids", []):
            episode_id = str(episode_id)
            if episode_id in seen:
                continue
            row = schedule.get(episode_id)
            artifacts = list((root / episode_id / "episodes").glob("*.json"))
            if row is None or len(artifacts) != 1:
                raise RemoteFull120Error(f"cannot ledger completed episode: {episode_id}")
            artifact = artifacts[0]
            entry = {
                "schema": "proofalign.remote-full120-execution-ledger-row.v1",
                "append_index": len(seen),
                "episode_id": episode_id,
                "sequence_index": row["sequence_index"],
                "condition": protocol["design"]["condition"],
                "arm": row["arm"],
                "unit_id": row["unit_id"],
                "base_pair_id": row["base_pair_id"],
                "seed_block_id": row["seed_block_id"],
                "artifact_path": artifact.relative_to(REPO_ROOT).as_posix(),
                "artifact_sha256": file_sha256(artifact),
                "status": "completed",
            }
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
            seen.add(episode_id)

    saber_io.atomic_json = wrapped
    try:
        yield
    finally:
        saber_io.atomic_json = original


@contextmanager
def _patched_default(runner: Any, path: Path) -> Iterator[None]:
    original = runner.DEFAULT_PROTOCOL
    runner.DEFAULT_PROTOCOL = path
    try:
        yield
    finally:
        runner.DEFAULT_PROTOCOL = original


def run(stage: str, mode: str, policy_gpu: int | None, egl_gpu: int | None) -> dict[str, Any]:
    path, protocol, runner = _protocol(stage)
    _verify_umbrella(protocol)
    if stage == "attacked":
        _require_clean_gate()
    with _patched_default(runner, path):
        if mode == "preflight":
            return runner.preflight(protocol, protocol_path=path, policy_gpu=policy_gpu, egl_gpu=egl_gpu)
        if mode == "validate-results":
            return runner.validate_results(protocol, protocol_path=path)
        if policy_gpu is None or egl_gpu is None:
            raise RemoteFull120Error("execute requires policy and EGL GPU indices")
        with _append_only_execution_ledger(protocol):
            return runner.execute(protocol, protocol_path=path, policy_gpu=policy_gpu, egl_gpu=egl_gpu)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("clean", "attacked"), required=True)
    parser.add_argument("--mode", choices=("preflight", "execute", "validate-results"), required=True)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args()
    print(canonical_text(run(args.stage, args.mode, args.policy_gpu, args.egl_gpu)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
