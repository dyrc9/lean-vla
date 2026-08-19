#!/usr/bin/env python3
"""Run the frozen full-120 LLM-template clean/attacked successor."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_remote_full120_experiment as original  # noqa: E402
from scripts import run_v15_bounded_state_triggered_task_utility_qualification as clean_runner  # noqa: E402
from scripts import run_v15_14_unified_force_envelope_attacked_task_utility_qualification as attacked_runner  # noqa: E402
from scripts.run_llm_template_semantic_v1 import patched_llm_template_runtime  # noqa: E402


CLEAN_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_clean_protocol_20260818.json"
ATTACKED_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json"
UMBRELLA_PROTOCOL = REPO_ROOT / "experiments/proofalign_remote_full120_llm_successor_protocol_20260818.json"
CATALOG = REPO_ROOT / "experiments/proofalign_llm_semantic_template_catalog_20260818.json"
QUALIFICATION = REPO_ROOT / "results/proofalign_llm_semantic_template_qualification_20260818_fresh2/summary.json"
CLEAN_ANALYSIS = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_20260818_fresh1/terminal_analysis.json"


class RemoteFull120LLMError(RuntimeError):
    pass


def _protocol(stage: str) -> tuple[Path, dict[str, Any], Any]:
    path = CLEAN_PROTOCOL if stage == "clean" else ATTACKED_PROTOCOL
    runner = clean_runner if stage == "clean" else attacked_runner
    return path, load_json_object(path), runner


def _verify_successor(protocol: Mapping[str, Any]) -> None:
    umbrella = load_json_object(UMBRELLA_PROTOCOL)
    qualification = load_json_object(QUALIFICATION)
    if umbrella.get("post_failure_exploratory_method_extension") is not True:
        raise RemoteFull120LLMError("LLM successor disclosure is absent")
    if umbrella.get("outcomes_used_for_llm_template_generation") is not False:
        raise RemoteFull120LLMError("LLM template generation is not outcome-blind")
    if qualification.get("classification") != "llm_semantic_template_qualification_pass":
        raise RemoteFull120LLMError("outcome-blind LLM template qualification did not pass")
    if any(
        qualification.get(key) != 0
        for key in (
            "policy_load_count",
            "policy_inference_count",
            "env_step_count",
            "task_outcome_read_count",
            "attacked_prompt_read_count",
        )
    ):
        raise RemoteFull120LLMError("qualification crossed the frozen threat boundary")
    if len(protocol.get("schedule", [])) != 480:
        raise RemoteFull120LLMError("stage schedule is not 480 episodes")


def _require_clean_integrity_complete() -> None:
    if not CLEAN_ANALYSIS.is_file():
        raise RemoteFull120LLMError("attacked stage blocked: clean terminal analysis absent")
    payload = load_json_object(CLEAN_ANALYSIS)
    if (
        payload.get("present_episode_count") != 480
        or payload.get("valid_episode_count") != 480
        or payload.get("episode_artifacts_verified") is not True
    ):
        raise RemoteFull120LLMError(
            "attacked stage blocked: clean data are not integrity-complete"
        )


@contextmanager
def _patched_default(runner: Any, path: Path) -> Iterator[None]:
    original_path = runner.DEFAULT_PROTOCOL
    runner.DEFAULT_PROTOCOL = path
    try:
        yield
    finally:
        runner.DEFAULT_PROTOCOL = original_path


def run(stage: str, mode: str, policy_gpu: int | None, egl_gpu: int | None) -> dict[str, Any]:
    path, protocol, runner = _protocol(stage)
    _verify_successor(protocol)
    if stage == "attacked":
        _require_clean_integrity_complete()
    with _patched_default(runner, path):
        if mode == "preflight":
            return runner.preflight(
                protocol,
                protocol_path=path,
                policy_gpu=policy_gpu,
                egl_gpu=egl_gpu,
            )
        if mode == "validate-results":
            return runner.validate_results(protocol, protocol_path=path)
        if policy_gpu is None or egl_gpu is None:
            raise RemoteFull120LLMError("execute requires policy and EGL GPU indices")
        with patched_llm_template_runtime(CATALOG):
            with original._append_only_execution_ledger(protocol):
                return runner.execute(
                    protocol,
                    protocol_path=path,
                    policy_gpu=policy_gpu,
                    egl_gpu=egl_gpu,
                )


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
