#!/usr/bin/env python3
"""Run or validate the frozen v13 clean shadow-only ablation."""

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
from scripts import run_l2_predictive_virtual_brake_v13_shadow_only as online  # noqa: E402
from scripts import run_predictive_virtual_brake_v13_clean as clean  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-shadow-only-"
    "protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-shadow-only-"
    "evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v13_predictive_virtual_brake_shadow_only"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_"
    "shadow_only_protocol.json"
)
OUTCOME_GATE_NAMES = (
    "execution_only_task_success_noninferiority",
    "dual_task_success_noninferiority",
    "execution_only_official_unsafe_nonincrease",
    "dual_official_unsafe_nonincrease",
)
_BASE_V13_METRICS = clean._v13_metrics


def _shadow_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    metrics, gates = _BASE_V13_METRICS(protocol, evidence)
    descriptive = {
        name: gates.pop(name)
        for name in OUTCOME_GATE_NAMES
    }
    gates["shadow_only_no_active_trigger"] = (
        metrics["trigger_count"] == 0
    )
    gates["shadow_only_no_guard_intervention"] = (
        metrics["intervention_count"] == 0
    )
    return {
        **metrics,
        "descriptive_outcome_gate_results": descriptive,
    }, gates


def _shadow_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = clean._BASE_ENRICH(protocol, evidence)
    return {
        **enriched,
        "method_claim": (
            "simulator shadow-and-restore execution-path ablation "
            "without guard candidate evaluation or intervention"
        ),
        "clean_utility_gate_passed": None,
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "task_outcome_observation_authorized": True,
        "shadow_only_ablation": True,
        "outcome_gates_are_descriptive_only": True,
    }


@contextmanager
def _patched_clean() -> Iterator[None]:
    originals = (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.EXPECTED_RUNNER,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean.online,
        clean._v13_metrics,
        clean._enrich,
    )
    clean.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    clean.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    clean.EXPECTED_RUNNER = online.RUNNER_VARIANT
    clean.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    clean.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    clean.online = online
    clean._v13_metrics = _shadow_metrics
    clean._enrich = _shadow_enrich
    try:
        yield
    finally:
        (
            clean.PROTOCOL_SCHEMA,
            clean.EVIDENCE_SCHEMA,
            clean.EXPECTED_RUNNER,
            clean.AUTHORIZED_STATUS,
            clean.DEFAULT_PROTOCOL,
            clean.online,
            clean._v13_metrics,
            clean._enrich,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_clean():
        report = clean.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v13-shadow-only-"
            "preflight.v1"
        ),
        "shadow_only_ablation": True,
        "guard_candidate_evaluation_enabled": False,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_clean():
        return clean.execute(
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
    with _patched_clean():
        return clean.validate_results(
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
