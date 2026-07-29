#!/usr/bin/env python3
"""Run or validate the frozen v11 paired instruction-attack pilot."""

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

from proofalign.benchmark.confirmatory import (  # noqa: E402
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_joint_limit_containment_v11_clean_pilot as clean  # noqa: E402
from scripts import run_l2_joint_limit_containment_v11 as online  # noqa: E402
from scripts import run_physical_sufficiency_attacked_pilot as inherited  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.joint-limit-containment-v11-attacked-pilot-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.joint-limit-containment-v11-attacked-pilot-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v11_joint_limit_containment_attacked_pilot"
)
STAGE = "joint_limit_containment_v11_attacked_fresh15"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_attacked_"
    "fresh15_protocol.json"
)


@contextmanager
def _patched_inherited() -> Iterator[None]:
    base = inherited.base
    originals = (
        inherited.PROTOCOL_SCHEMA,
        inherited.EVIDENCE_SCHEMA,
        inherited.AUTHORIZED_STATUS,
        inherited.STAGE,
        inherited.DEFAULT_PROTOCOL,
        inherited.online,
        base.PROTOCOL_SCHEMA,
        base.EVIDENCE_SCHEMA,
        base.EXPECTED_RUNNER,
        base.AUTHORIZED_STATUS,
        base.DEFAULT_PROTOCOL,
        base.online,
        base._v10_metrics,
    )
    inherited.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    inherited.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    inherited.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    inherited.STAGE = STAGE
    inherited.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    inherited.online = online
    base.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    base.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    base.EXPECTED_RUNNER = online.RUNNER_VARIANT
    base.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    base.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    base.online = online
    base._v10_metrics = clean._v11_metrics
    try:
        yield
    finally:
        (
            inherited.PROTOCOL_SCHEMA,
            inherited.EVIDENCE_SCHEMA,
            inherited.AUTHORIZED_STATUS,
            inherited.STAGE,
            inherited.DEFAULT_PROTOCOL,
            inherited.online,
            base.PROTOCOL_SCHEMA,
            base.EVIDENCE_SCHEMA,
            base.EXPECTED_RUNNER,
            base.AUTHORIZED_STATUS,
            base.DEFAULT_PROTOCOL,
            base.online,
            base._v10_metrics,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.execute(
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
    with _patched_inherited():
        return inherited.validate_results(
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
