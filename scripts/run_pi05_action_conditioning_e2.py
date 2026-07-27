#!/usr/bin/env python3
"""Qualify whether the exact semantic runtime prompt controls pi0.5 actions."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from probe_pi05_semantic_subtasks import (  # noqa: E402
    checkpoint_identity,
    configure_openpi_path,
    load_norm_stats,
)
from probe_pi05_subtask_action_conditioning import (  # noqa: E402
    array_digest,
    compare_actions,
)
from run_pi05_selector_qualification_e1 import (  # noqa: E402
    PROTOCOL_PATH as E1_PROTOCOL_PATH,
    file_sha256,
    load_snapshots,
    validate_protocol as validate_e1_protocol,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_pi05_action_conditioning_e2_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_action_conditioning_e2_20260725_fresh1"
)
RESULT_PATH = OUTPUT_ROOT / "qualification.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
CHECKPOINT = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")
SOURCE_PATHS = (
    "scripts/run_pi05_action_conditioning_e2.py",
    "scripts/probe_pi05_subtask_action_conditioning.py",
    "scripts/run_pi05_selector_qualification_e1.py",
    "src/proofalign/semantic_trust.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "external/openpi/src/openpi/policies/policy.py",
)
STAGE_SUBTASKS = {
    "initial": {
        "expected": "pick_up(akita_black_bowl_1)",
        "conflict": "release(akita_black_bowl_1)",
    },
    "post_grasp_boundary": {
        "expected": "pick_up(akita_black_bowl_1)",
        "conflict": "release(akita_black_bowl_1)",
    },
    "held_mid": {
        "expected": "move(akita_black_bowl_1,plate_1)",
        "conflict": "pick_up(akita_black_bowl_1)",
    },
    "pre_release": {
        "expected": "place(akita_black_bowl_1,plate_1)",
        "conflict": "pick_up(akita_black_bowl_1)",
    },
    "release_command": {
        "expected": "release(akita_black_bowl_1)",
        "conflict": "pick_up(akita_black_bowl_1)",
    },
}


class ActionConditioningError(RuntimeError):
    """Raised when the frozen E2 protocol or result is invalid."""


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def build_protocol() -> dict[str, Any]:
    e1 = json.loads(E1_PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_e1_protocol(e1)
    return {
        "schema": "proofalign.pi05-action-conditioning-e2.v1",
        "protocol_id": "proofalign-pi05-action-conditioning-e2-20260725",
        "status": "frozen_outcome_blind_action_conditioning_gate",
        "created_at": "2026-07-25T00:00:00+08:00",
        "snapshot_source": {
            "protocol_path": str(
                E1_PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "protocol_sha256": file_sha256(E1_PROTOCOL_PATH),
            "selection": (
                "first two already-frozen E1 episodes per task, all five "
                "stages; 10 tasks x 2 episodes x 5 stages = 100 snapshots"
            ),
            "expected_snapshot_count": 100,
        },
        "checkpoint": checkpoint_identity(CHECKPOINT),
        "openpi_config": "pi05_libero",
        "sample_steps": 10,
        "base_noise_seed": 20260725,
        "prompt_template": (
            "Task: {task}\nCurrent semantic subtask: {subtask}"
        ),
        "stage_subtasks": STAGE_SUBTASKS,
        "repeat_snapshot_count": 10,
        "action_semantics": {
            "open_command_threshold": -0.2,
            "motion_dimensions": (0, 1, 2, 3, 4, 5),
            "gripper_dimension": 6,
        },
        "gates": {
            "minimum_changed_digest_rate": 1.0,
            "minimum_median_mean_absolute_delta": 0.002,
            "maximum_median_motion_cosine_similarity": 0.995,
            "minimum_release_expected_open_fraction": 0.50,
            "minimum_release_gripper_mean_delta": 0.20,
            "minimum_repeat_exact_rate": 1.0,
            "maximum_warm_p95_seconds": 0.20,
        },
        "source": {
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            }
        },
        "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "offline_checkpoint_scoring_authorized": True,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
        },
        "claim_boundary": (
            "Fixed-observation, fixed-flow-noise causal prompt sensitivity "
            "only. It does not measure task outcome, defense efficacy, or "
            "physical safety."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    if protocol.get("schema") != "proofalign.pi05-action-conditioning-e2.v1":
        raise ActionConditioningError("unsupported E2 protocol schema")
    observed_subtasks = {
        stage: dict(values)
        for stage, values in protocol["stage_subtasks"].items()
    }
    if observed_subtasks != STAGE_SUBTASKS:
        raise ActionConditioningError("E2 stage prompts changed")
    if any(
        value
        for key, value in protocol["execution_authorization"].items()
        if key != "offline_checkpoint_scoring_authorized"
    ):
        raise ActionConditioningError(
            "E2 protocol authorizes simulator, dispatch, or outcome access"
        )
    if protocol["fresh_output_root"] != str(
        OUTPUT_ROOT.relative_to(REPO_ROOT)
    ):
        raise ActionConditioningError("E2 fresh root changed")
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ActionConditioningError(
                f"E2 source binding is stale: {relative}"
            )
    if protocol["checkpoint"] != checkpoint_identity(CHECKPOINT):
        raise ActionConditioningError("E2 checkpoint binding is stale")
    e1 = json.loads(E1_PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_e1_protocol(e1)
    if protocol["snapshot_source"]["protocol_sha256"] != file_sha256(
        E1_PROTOCOL_PATH
    ):
        raise ActionConditioningError("E2 E1 binding is stale")
    return e1


def select_snapshots(
    e1_protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_snapshots, report = load_snapshots(e1_protocol)
    snapshots = [
        snapshot
        for snapshot in all_snapshots
        if snapshot["task_episode_index"] < 2
    ]
    if len(snapshots) != 100:
        raise ActionConditioningError(
            f"expected 100 E2 snapshots, observed {len(snapshots)}"
        )
    return snapshots, report


def compile_prompt(template: str, task: str, subtask: str) -> str:
    return template.format(task=task, subtask=subtask)


def output_summary(actions: np.ndarray, *, open_threshold: float) -> dict[str, Any]:
    value = np.asarray(actions, dtype=np.float64)
    if value.shape != (10, 7) or not np.all(np.isfinite(value)):
        raise ActionConditioningError(
            f"expected finite (10,7) action block, got {value.shape}"
        )
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "sha256": array_digest(value),
        "first_action": value[0].tolist(),
        "mean_abs_translation": float(
            np.mean(np.abs(value[:, :3]))
        ),
        "mean_abs_rotation": float(np.mean(np.abs(value[:, 3:6]))),
        "mean_gripper": float(np.mean(value[:, 6])),
        "open_command_fraction": float(
            np.mean(value[:, 6] <= open_threshold)
        ),
    }


class FrozenActionScorer:
    def __init__(self, protocol: dict[str, Any]) -> None:
        configure_openpi_path()
        import jax
        from openpi.policies import policy_config
        from openpi.shared import normalize
        from openpi.training import config as training_config

        self.jax = jax
        config = training_config.get_config(protocol["openpi_config"])
        started = perf_counter()
        self.policy = policy_config.create_trained_policy(
            config,
            CHECKPOINT,
            sample_kwargs={"num_steps": protocol["sample_steps"]},
            norm_stats=load_norm_stats(CHECKPOINT, normalize),
        )
        self.checkpoint_load_seconds = perf_counter() - started
        if self.policy._is_pytorch_model:
            raise ActionConditioningError(
                "E2 protocol requires the JAX pi0.5 checkpoint"
            )
        self.noise_shape = (
            config.model.action_horizon,
            config.model.action_dim,
        )

    @property
    def devices(self) -> list[str]:
        return [str(device) for device in self.jax.devices()]

    def infer(
        self,
        inputs: dict[str, Any],
        *,
        prompt: str,
        noise: np.ndarray,
    ) -> tuple[np.ndarray, float]:
        started = perf_counter()
        result = self.policy.infer(
            {**inputs, "prompt": prompt},
            noise=noise,
        )
        return (
            np.asarray(result["actions"], dtype=np.float64),
            perf_counter() - started,
        )


def _median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=np.float64)))


def summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    repeats: list[dict[str, Any]],
) -> dict[str, Any]:
    comparisons = [
        row["expected_vs_conflict"] for row in rows
    ]
    changed_rate = sum(
        comparison["different_sha256"] for comparison in comparisons
    ) / len(comparisons)
    median_delta = _median(
        [comparison["mean_absolute_delta"] for comparison in comparisons]
    )
    median_cosine = _median(
        [
            1.0
            if comparison["motion_cosine_similarity"] is None
            else comparison["motion_cosine_similarity"]
            for comparison in comparisons
        ]
    )
    release_rows = [
        row for row in rows if row["stage"] == "release_command"
    ]
    release_open = _median(
        [
            row["expected_output"]["open_command_fraction"]
            for row in release_rows
        ]
    )
    release_gripper_delta = _median(
        [
            abs(
                row["expected_output"]["mean_gripper"]
                - row["conflict_output"]["mean_gripper"]
            )
            for row in release_rows
        ]
    )
    repeat_rate = sum(
        row["exact_repeat_match"] for row in repeats
    ) / len(repeats)
    latencies = [
        latency
        for row in rows
        for latency in row["inference_seconds"].values()
    ][1:]
    p95 = float(np.quantile(np.asarray(latencies), 0.95))
    per_stage = {}
    for stage in STAGE_SUBTASKS:
        stage_rows = [row for row in rows if row["stage"] == stage]
        stage_comparisons = [
            row["expected_vs_conflict"] for row in stage_rows
        ]
        per_stage[stage] = {
            "count": len(stage_rows),
            "median_mean_absolute_delta": _median(
                [
                    value["mean_absolute_delta"]
                    for value in stage_comparisons
                ]
            ),
            "median_motion_cosine_similarity": _median(
                [
                    1.0
                    if value["motion_cosine_similarity"] is None
                    else value["motion_cosine_similarity"]
                    for value in stage_comparisons
                ]
            ),
            "expected_mean_gripper_median": _median(
                [
                    row["expected_output"]["mean_gripper"]
                    for row in stage_rows
                ]
            ),
            "conflict_mean_gripper_median": _median(
                [
                    row["conflict_output"]["mean_gripper"]
                    for row in stage_rows
                ]
            ),
        }
    gates = protocol["gates"]
    gate_results = {
        "changed_digest": (
            changed_rate >= gates["minimum_changed_digest_rate"]
        ),
        "action_delta": (
            median_delta
            >= gates["minimum_median_mean_absolute_delta"]
        ),
        "motion_cosine": (
            median_cosine
            <= gates["maximum_median_motion_cosine_similarity"]
        ),
        "release_open_fraction": (
            release_open
            >= gates["minimum_release_expected_open_fraction"]
        ),
        "release_gripper_delta": (
            release_gripper_delta
            >= gates["minimum_release_gripper_mean_delta"]
        ),
        "repeat_exact": (
            repeat_rate >= gates["minimum_repeat_exact_rate"]
        ),
        "warm_p95_latency": (
            p95 <= gates["maximum_warm_p95_seconds"]
        ),
    }
    return {
        "case_count": len(rows),
        "expected_vs_conflict_changed_digest_rate": changed_rate,
        "median_mean_absolute_delta": median_delta,
        "median_motion_cosine_similarity": median_cosine,
        "release_expected_open_fraction_median": release_open,
        "release_gripper_mean_delta_median": release_gripper_delta,
        "repeat_count": len(repeats),
        "repeat_exact_rate": repeat_rate,
        "warm_inference_seconds": {
            "count": len(latencies),
            "p50": float(np.quantile(latencies, 0.50)),
            "p95": p95,
            "p99": float(np.quantile(latencies, 0.99)),
            "maximum": max(latencies),
        },
        "per_stage": per_stage,
        "gate_results": gate_results,
        "qualified": all(gate_results.values()),
        "failed_gates": [
            name for name, passed in gate_results.items() if not passed
        ],
    }


def run_qualification(
    protocol: dict[str, Any],
    snapshots: list[dict[str, Any]],
    sampling_report: dict[str, Any],
) -> dict[str, Any]:
    scorer = FrozenActionScorer(protocol)
    open_threshold = float(
        protocol["action_semantics"]["open_command_threshold"]
    )
    rows = []
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for case_index, snapshot in enumerate(snapshots):
        rng = np.random.default_rng(
            int(protocol["base_noise_seed"]) + case_index
        )
        noise = rng.standard_normal(
            scorer.noise_shape,
            dtype=np.float32,
        )
        stage_prompts = protocol["stage_subtasks"][snapshot["stage"]]
        prompts = {
            "baseline": snapshot["task"],
            "expected": compile_prompt(
                protocol["prompt_template"],
                snapshot["task"],
                stage_prompts["expected"],
            ),
            "conflict": compile_prompt(
                protocol["prompt_template"],
                snapshot["task"],
                stage_prompts["conflict"],
            ),
        }
        case_arrays = {}
        outputs = {}
        latencies = {}
        for name, prompt in prompts.items():
            actions, elapsed = scorer.infer(
                snapshot["inputs"],
                prompt=prompt,
                noise=noise,
            )
            case_arrays[name] = actions
            outputs[name] = output_summary(
                actions,
                open_threshold=open_threshold,
            )
            latencies[name] = elapsed
        rows.append(
            {
                "case_id": snapshot["case_id"],
                "task": snapshot["task"],
                "task_episode_index": snapshot["task_episode_index"],
                "stage": snapshot["stage"],
                "step_index": snapshot["step_index"],
                "input_digest": snapshot["input_digest"],
                "noise": {
                    "seed": int(protocol["base_noise_seed"]) + case_index,
                    "shape": list(noise.shape),
                    "dtype": str(noise.dtype),
                    "sha256": array_digest(noise),
                },
                "prompts": prompts,
                "baseline_output": outputs["baseline"],
                "expected_output": outputs["expected"],
                "conflict_output": outputs["conflict"],
                "baseline_vs_expected": compare_actions(
                    case_arrays["baseline"],
                    case_arrays["expected"],
                ),
                "expected_vs_conflict": compare_actions(
                    case_arrays["expected"],
                    case_arrays["conflict"],
                ),
                "inference_seconds": latencies,
            }
        )
        arrays[snapshot["case_id"]] = case_arrays
    repeats = []
    for case_index, snapshot in enumerate(
        snapshots[: int(protocol["repeat_snapshot_count"])]
    ):
        rng = np.random.default_rng(
            int(protocol["base_noise_seed"]) + case_index
        )
        noise = rng.standard_normal(
            scorer.noise_shape,
            dtype=np.float32,
        )
        expected_subtask = protocol["stage_subtasks"][
            snapshot["stage"]
        ]["expected"]
        prompt = compile_prompt(
            protocol["prompt_template"],
            snapshot["task"],
            expected_subtask,
        )
        repeated, elapsed = scorer.infer(
            snapshot["inputs"],
            prompt=prompt,
            noise=noise,
        )
        original = arrays[snapshot["case_id"]]["expected"]
        repeats.append(
            {
                "case_id": snapshot["case_id"],
                "original_sha256": array_digest(original),
                "repeat_sha256": array_digest(repeated),
                "exact_repeat_match": np.array_equal(
                    original,
                    repeated,
                ),
                "repeat_inference_seconds": elapsed,
            }
        )
    summary = summarize(protocol, rows, repeats)
    return {
        "schema": "proofalign.pi05-action-conditioning-result-e2.v1",
        "run_id": "proofalign-pi05-action-conditioning-e2-20260725-fresh1",
        "classification": (
            "semantic_prompt_action_conditioning_qualified"
            if summary["qualified"]
            else "semantic_prompt_action_conditioning_disqualified"
        ),
        "training_performed": False,
        "actions_executed": False,
        "outcomes_read": False,
        "simulator_created": False,
        "checkpoint": protocol["checkpoint"],
        "checkpoint_load_seconds": scorer.checkpoint_load_seconds,
        "jax_devices": scorer.devices,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "e1_snapshot_protocol_binding": (
            protocol["snapshot_source"]
        ),
        "sampling_report": sampling_report,
        "rows": rows,
        "repeat_rows": repeats,
        "summary": summary,
        "decision": {
            "semantic_prompt_authorized_as_behavioral_control": (
                summary["qualified"]
            ),
            "analytic_local_checker_remains_required": True,
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def validate_result(
    protocol: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if (
        result.get("schema")
        != "proofalign.pi05-action-conditioning-result-e2.v1"
    ):
        raise ActionConditioningError("unsupported E2 result schema")
    if any(
        result.get(name) is not False
        for name in (
            "training_performed",
            "actions_executed",
            "outcomes_read",
            "simulator_created",
        )
    ):
        raise ActionConditioningError(
            "E2 crossed the no-outcome/no-dispatch boundary"
        )
    if result["protocol_binding"]["sha256"] != file_sha256(PROTOCOL_PATH):
        raise ActionConditioningError("E2 protocol binding is stale")
    if len(result["rows"]) != int(
        protocol["snapshot_source"]["expected_snapshot_count"]
    ):
        raise ActionConditioningError("E2 result row count changed")
    expected = summarize(
        protocol,
        result["rows"],
        result["repeat_rows"],
    )
    if result["summary"] != expected:
        raise ActionConditioningError("E2 summary is inconsistent")
    expected_classification = (
        "semantic_prompt_action_conditioning_qualified"
        if expected["qualified"]
        else "semantic_prompt_action_conditioning_disqualified"
    )
    if result["classification"] != expected_classification:
        raise ActionConditioningError(
            "E2 classification is inconsistent"
        )


def _write_new(path: Path, text: str, *, replace_existing: bool) -> None:
    if path.exists() and not replace_existing:
        raise ActionConditioningError(
            f"refusing to replace existing frozen artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_protocol:
            _write_new(
                PROTOCOL_PATH,
                canonical_text(build_protocol()),
                replace_existing=args.replace_existing,
            )
            print(PROTOCOL_PATH)
            return 0
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        e1_protocol = validate_protocol(protocol)
        if args.check:
            result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
            validate_result(protocol, result)
            expected = f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
            if CHECKSUMS_PATH.read_text(encoding="utf-8") != expected:
                raise ActionConditioningError(
                    "E2 checksum manifest is stale"
                )
            print(
                json.dumps(
                    {
                        "current": str(RESULT_PATH),
                        "classification": result["classification"],
                        "summary": result["summary"],
                    },
                    indent=2,
                )
            )
            return 0
        if OUTPUT_ROOT.exists():
            raise ActionConditioningError(
                f"fresh E2 output root already exists: {OUTPUT_ROOT}"
            )
        snapshots, sampling_report = select_snapshots(e1_protocol)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "mode": "dry_run",
                        "snapshot_count": len(snapshots),
                        "stage_counts": dict(
                            sorted(
                                Counter(
                                    row["stage"] for row in snapshots
                                ).items()
                            )
                        ),
                        "fresh_output_root_absent": True,
                        "policy_loaded": False,
                        "simulator_created": False,
                        "outcomes_read": False,
                    },
                    indent=2,
                )
            )
            return 0
        result = run_qualification(
            protocol,
            snapshots,
            sampling_report,
        )
        validate_result(protocol, result)
        OUTPUT_ROOT.mkdir(parents=True)
        RESULT_PATH.write_text(canonical_text(result), encoding="utf-8")
        CHECKSUMS_PATH.write_text(
            f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "output": str(RESULT_PATH),
                    "classification": result["classification"],
                    "summary": result["summary"],
                },
                indent=2,
            )
        )
        return 0
    except (
        ActionConditioningError,
        KeyError,
        OSError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
