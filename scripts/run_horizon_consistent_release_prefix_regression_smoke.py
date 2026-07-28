#!/usr/bin/env python3
"""Run the frozen H4 release-prefix regression with the v7 runner."""

from __future__ import annotations

import argparse
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
from proofalign.horizon_consistent_release_prefix import (  # noqa: E402
    RELEASE_PREFIX_PROGRESS_EFFECT,
)
from scripts import (  # noqa: E402
    run_horizon_consistent_release_h4_regression_smoke as h4,
)
from scripts import run_l2_execution_attack_eval_v7 as online  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.horizon-consistent-release-prefix-regression-smoke-"
    "protocol.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_prefix_"
    "regression_smoke_protocol.json"
)
_ORIGINAL_H4_BUILD_EVIDENCE = h4._build_evidence


class ReleasePrefixRegressionError(RuntimeError):
    """Raised when the release-prefix regression leaves frozen scope."""


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_release_prefix_progress_regression_smoke"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise ReleasePrefixRegressionError(
            "unsupported release-prefix protocol"
        )
    if protocol.get("execution_authorization") != {
        "clean_dual_release_prefix_regression_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise ReleasePrefixRegressionError(
            "release-prefix authorization differs"
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
        raise ReleasePrefixRegressionError(
            "release-prefix source is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ReleasePrefixRegressionError(
                f"release-prefix source differs: {relative}"
            )
    parent = protocol["parent_h4_terminal"]
    path = REPO_ROOT / str(parent["path"])
    if (
        not path.is_file()
        or file_sha256(path) != parent["sha256"]
        or load_json_object(path).get("smoke_pass") is not False
    ):
        raise ReleasePrefixRegressionError(
            "release-prefix parent binding differs"
        )


def _build_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    evidence = _ORIGINAL_H4_BUILD_EVIDENCE(*args, **kwargs)
    protocol = args[0] if args else kwargs["protocol"]
    release_rows = evidence["release_rows"]
    evidence["observed"].update(
        {
            "release_canonicalization_count": sum(
                row.get("projection_reason")
                == "release_h4_open_gripper_canonicalization"
                for row in release_rows
            ),
            "release_effect_observed_count": sum(
                RELEASE_PREFIX_PROGRESS_EFFECT
                in (row.get("observed_effect_atoms") or ())
                for row in release_rows
            ),
            "release_prefix_progress_observed_count": sum(
                RELEASE_PREFIX_PROGRESS_EFFECT
                in (row.get("observed_effect_atoms") or ())
                for row in release_rows
            ),
        }
    )
    gates = protocol["gates"]
    evidence["gate_results"].update(
        {
            "release_canonicalization_count": (
                evidence["observed"][
                    "release_canonicalization_count"
                ]
                >= gates["minimum_release_canonicalization_count"]
            ),
            "release_effect_observed_count": (
                evidence["observed"][
                    "release_effect_observed_count"
                ]
                >= gates["minimum_release_effect_observed_count"]
            ),
            "runner_variant": (
                evidence["observed"]["runner_variant"]
                == "proofalign_l2_execution_attack_successor_v7"
            ),
            "release_prefix_progress_observed": (
                evidence["observed"][
                    "release_prefix_progress_observed_count"
                ]
                >= 1
            ),
        }
    )
    passed = all(evidence["gate_results"].values())
    evidence.update(
        {
            "schema": (
                "proofalign.horizon-consistent-release-prefix-"
                "regression-smoke-evidence.v1"
            ),
            "classification": (
                "horizon_consistent_release_prefix_regression_smoke_pass"
                if passed
                else (
                    "horizon_consistent_release_prefix_"
                    "regression_smoke_nonpass"
                )
            ),
            "smoke_pass": passed,
        }
    )
    return evidence


def _patched_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    original_validate = h4.validate_protocol
    original_build = h4._build_evidence
    original_online = h4.online
    h4.validate_protocol = validate_protocol
    h4._build_evidence = _build_evidence
    h4.online = online
    try:
        return function(*args, **kwargs)
    finally:
        h4.validate_protocol = original_validate
        h4._build_evidence = original_build
        h4.online = original_online


def preflight(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(h4.preflight, *args, **kwargs)


def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(h4.execute, *args, **kwargs)


def validate_results(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _patched_call(h4.validate_results, *args, **kwargs)


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
