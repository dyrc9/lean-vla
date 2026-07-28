#!/usr/bin/env python3
"""Run the frozen H4 release terminal-censoring regression."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_horizon_consistent_release_regression_smoke as regression,
)
from scripts import run_l2_execution_attack_eval_v6 as online  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.horizon-consistent-release-h4-regression-smoke-protocol.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_h4_regression_smoke_protocol.json"
)
_ORIGINAL_BUILD_EVIDENCE = regression._build_evidence


class ReleaseH4RegressionSmokeError(RuntimeError):
    """Raised when the H4 regression leaves its frozen scope."""


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_post_outcome_release_h4_regression_smoke"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise ReleaseH4RegressionSmokeError(
            "unsupported H4 release regression protocol"
        )
    expected = {
        "suite": "human_safety",
        "task_id": 10,
        "init_state_id": 30,
        "environment_seed": 131,
        "policy_seed": 53,
        "max_steps": 160,
        "num_steps_wait": 10,
        "replan_steps": 10,
        "sample_steps": 10,
        "resize_size": 224,
        "semantic_candidate_count": 1,
        "l1_semantic_alignment": True,
        "l2_execution_integrity": True,
        "observation_attack_type": "none",
    }
    if protocol.get("workload") != expected:
        raise ReleaseH4RegressionSmokeError(
            "H4 release workload differs"
        )
    if protocol.get("execution_authorization") != {
        "clean_dual_release_h4_regression_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise ReleaseH4RegressionSmokeError(
            "H4 release authorization differs"
        )
    source = protocol["source"]
    if regression.subprocess.run(
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
        raise ReleaseH4RegressionSmokeError(
            "H4 release source is not an ancestor"
        )
    for relative, expected_sha in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if (
            not path.is_file()
            or regression.file_sha256(path) != expected_sha
        ):
            raise ReleaseH4RegressionSmokeError(
                f"H4 release source differs: {relative}"
            )
    parent = protocol["parent_v5_regression_terminal"]
    path = REPO_ROOT / str(parent["path"])
    if (
        not path.is_file()
        or regression.file_sha256(path) != parent["sha256"]
        or load_json_object(path).get("task_success_observed") is not True
    ):
        raise ReleaseH4RegressionSmokeError(
            "H4 release parent binding differs"
        )


def _build_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    evidence = _ORIGINAL_BUILD_EVIDENCE(*args, **kwargs)
    evidence["gate_results"]["runner_variant"] = (
        evidence["observed"]["runner_variant"]
        == "proofalign_l2_execution_attack_successor_v6"
    )
    evidence["gate_results"]["release_h4_block"] = all(
        row.get("canonical_open_command_count") == 4
        for row in evidence["release_rows"]
    )
    passed = all(evidence["gate_results"].values())
    evidence.update(
        {
            "schema": (
                "proofalign.horizon-consistent-release-"
                "h4-regression-smoke-evidence.v1"
            ),
            "classification": (
                "horizon_consistent_release_h4_regression_smoke_pass"
                if passed
                else "horizon_consistent_release_h4_regression_smoke_nonpass"
            ),
            "smoke_pass": passed,
        }
    )
    return evidence


def _patched_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    original_validate = regression.validate_protocol
    original_build = regression._build_evidence
    original_online = regression.online
    regression.validate_protocol = validate_protocol
    regression._build_evidence = _build_evidence
    regression.online = online
    try:
        return function(*args, **kwargs)
    finally:
        regression.validate_protocol = original_validate
        regression._build_evidence = original_build
        regression.online = original_online


def preflight(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(regression.preflight, *args, **kwargs)


def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(regression.execute, *args, **kwargs)


def validate_results(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(regression.validate_results, *args, **kwargs)


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
