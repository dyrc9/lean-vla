#!/usr/bin/env python3
"""Run or validate the v14 all-joint clean development Fresh2 repeat."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_fresh2 as online  # noqa: E402
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-clean-"
    "development-fresh2-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-clean-"
    "development-fresh2-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v14_multijoint_clean_development_fresh2_outcome"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)


@contextmanager
def _patched_predecessor() -> Iterator[None]:
    originals = (
        predecessor.PROTOCOL_SCHEMA,
        predecessor.EVIDENCE_SCHEMA,
        predecessor.AUTHORIZED_STATUS,
        predecessor.DEFAULT_PROTOCOL,
        predecessor.EXPECTED_RUNNER,
        predecessor.online,
    )
    predecessor.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    predecessor.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    predecessor.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    predecessor.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    predecessor.EXPECTED_RUNNER = online.RUNNER_VARIANT
    predecessor.online = online
    try:
        yield
    finally:
        (
            predecessor.PROTOCOL_SCHEMA,
            predecessor.EVIDENCE_SCHEMA,
            predecessor.AUTHORIZED_STATUS,
            predecessor.DEFAULT_PROTOCOL,
            predecessor.EXPECTED_RUNNER,
            predecessor.online,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_predecessor():
        report = predecessor.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "clean-development-fresh2-preflight.v1"
        ),
        "development1_partial_outcomes_observed": True,
        "development1_completed_episode_count": 2,
        "scientific_parameters_changed_after_development1": False,
        "confirmatory_claim_authorized": False,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_predecessor():
        return predecessor.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_predecessor():
        return predecessor.validate_results(
            protocol,
            protocol_path=protocol_path,
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
