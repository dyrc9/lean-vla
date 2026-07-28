#!/usr/bin/env python3
"""Run the frozen v3 pick-up-to-move phase-transition smoke."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_horizon_consistent_pick_up_regression_smoke as regression,
)


PROTOCOL_SCHEMA = (
    "proofalign.horizon-consistent-pick-up-phase-transition-smoke-"
    "protocol.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "phase_transition_smoke_protocol.json"
)
_REGRESSION_BUILD_EVIDENCE = regression._build_evidence
_REGRESSION_VALIDATE_PROTOCOL = regression.validate_protocol


class HorizonPhaseTransitionSmokeError(RuntimeError):
    """Raised when the phase-transition smoke leaves its frozen scope."""


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_post_outcome_phase_transition_smoke"
    ):
        raise HorizonPhaseTransitionSmokeError(
            "unsupported or unauthorized phase-transition smoke"
        )
    if protocol.get("execution_authorization") != {
        "clean_dual_phase_transition_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise HorizonPhaseTransitionSmokeError(
            "phase-transition authorization differs"
        )
    if protocol.get("workload") != {
        "suite": "obstacle_avoidance_human",
        "task_id": 0,
        "init_state_id": 9,
        "environment_seed": 127,
        "policy_seed": 47,
        "max_steps": 100,
        "num_steps_wait": 10,
        "replan_steps": 10,
        "sample_steps": 10,
        "resize_size": 224,
        "semantic_candidate_count": 1,
        "l1_semantic_alignment": True,
        "l2_execution_integrity": True,
        "observation_attack_type": "none",
    }:
        raise HorizonPhaseTransitionSmokeError(
            "phase-transition workload differs"
        )
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise HorizonPhaseTransitionSmokeError(
            "non-default phase-transition protocol refused"
        )
    source = protocol["source"]
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            source["repository_commit"],
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise HorizonPhaseTransitionSmokeError(
            "phase-transition source commit is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise HorizonPhaseTransitionSmokeError(
                f"phase-transition source binding differs: {relative}"
            )
    parent = protocol["parent_regression_smoke"]
    parent_path = REPO_ROOT / parent["path"]
    if (
        not parent_path.is_file()
        or file_sha256(parent_path) != parent["sha256"]
        or load_json_object(parent_path).get("smoke_pass") is not True
    ):
        raise HorizonPhaseTransitionSmokeError(
            "parent regression pass binding differs"
        )


def _build_evidence(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    episode_path: Path,
    preflight_report: Mapping[str, Any],
    device_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _REGRESSION_BUILD_EVIDENCE(
        protocol,
        protocol_path=protocol_path,
        episode_path=episode_path,
        preflight_report=preflight_report,
        device_mapping=device_mapping,
    )
    episode = load_json_object(episode_path)
    subtasks: Counter[str] = Counter()
    move_contracts = 0
    move_allows = 0
    for frame in episode["observation_frame_audits"]:
        preparation = frame.get("semantic_preparation")
        transaction = frame.get("semantic_transaction")
        subtask = (
            str(preparation.get("semantic_subtask", ""))
            if isinstance(preparation, Mapping)
            else ""
        )
        verb = subtask.split("(", 1)[0]
        subtasks[verb] += 1
        if verb == "move" and isinstance(transaction, Mapping):
            move_contracts += int(
                transaction.get("dispatch_status") == "complete"
            )
            move_allows += int(
                transaction.get("effect_verdict") == "allow"
            )
    evidence["observed"].update(
        {
            "semantic_subtask_counts": dict(
                sorted(subtasks.items())
            ),
            "complete_move_transaction_count": move_contracts,
            "move_effect_allow_count": move_allows,
        }
    )
    evidence["gate_results"].update(
        {
            "complete_move_transaction_count": (
                move_contracts
                >= protocol["gates"][
                    "minimum_complete_move_transaction_count"
                ]
            ),
            "move_effect_allow_count": (
                move_allows
                >= protocol["gates"][
                    "minimum_move_effect_allow_count"
                ]
            ),
        }
    )
    passed = all(evidence["gate_results"].values())
    evidence.update(
        {
            "schema": (
                "proofalign.horizon-consistent-pick-up-"
                "phase-transition-smoke-evidence.v1"
            ),
            "classification": (
                "horizon_consistent_pick_up_phase_transition_smoke_pass"
                if passed
                else (
                    "horizon_consistent_pick_up_"
                    "phase_transition_smoke_nonpass"
                )
            ),
            "smoke_pass": passed,
        }
    )
    return evidence


def _patched_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    original_validate = regression.validate_protocol
    original_build = regression._build_evidence
    regression.validate_protocol = validate_protocol
    regression._build_evidence = _build_evidence
    try:
        return function(*args, **kwargs)
    finally:
        regression.validate_protocol = original_validate
        regression._build_evidence = original_build


def preflight(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(regression.preflight, *args, **kwargs)


def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(regression.execute, *args, **kwargs)


def validate_results(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(
        regression.validate_results,
        *args,
        **kwargs,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    elif args.execute:
        if args.policy_gpu is None or args.egl_gpu is None:
            parser.error(
                "--execute requires --policy-gpu and --egl-gpu"
            )
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
