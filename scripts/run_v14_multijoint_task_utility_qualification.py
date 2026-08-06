#!/usr/bin/env python3
"""Run or validate held-out v14 task-utility qualification."""

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
from scripts import run_predictive_virtual_brake_v14_multijoint_clean_fresh2 as base  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "task-utility-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "task-utility-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v14_multijoint_task_utility_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "task_utility_qualification_protocol.json"
)
_BASE_ENRICH = base.predecessor._enrich


def _qualification_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ENRICH(protocol, evidence)
    utility_names = (
        "v9_execution_only_task_success_noninferiority",
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_official_unsafe_nonincrease",
        "v9_dual_official_unsafe_nonincrease",
    )
    clean_utility_passed = all(
        enriched["gate_results"].get(name) is True
        for name in utility_names
    )
    qualification_pass = bool(
        enriched["gate_results"]
        and all(
            value is True
            for value in enriched["gate_results"].values()
        )
    )
    return {
        **enriched,
        "classification": (
            protocol["pass_classification"]
            if qualification_pass
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": qualification_pass,
        "clean_utility_gate_passed": clean_utility_passed,
        "task_utility_qualification_claim_authorized": (
            qualification_pass
        ),
        "held_out_population": True,
        "task_outcomes_observed_before_protocol_freeze": False,
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "simulator_safety_claim_authorized": False,
        "method_claim": (
            "held-out clean task-utility qualification for the frozen "
            "fourteen-side predictive simulator virtual brake"
        ),
    }


@contextmanager
def _patched_base() -> Iterator[None]:
    originals = (
        base.PROTOCOL_SCHEMA,
        base.EVIDENCE_SCHEMA,
        base.AUTHORIZED_STATUS,
        base.DEFAULT_PROTOCOL,
        base.predecessor._enrich,
    )
    base.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    base.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    base.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    base.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    base.predecessor._enrich = _qualification_enrich
    try:
        yield
    finally:
        (
            base.PROTOCOL_SCHEMA,
            base.EVIDENCE_SCHEMA,
            base.AUTHORIZED_STATUS,
            base.DEFAULT_PROTOCOL,
            base.predecessor._enrich,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_base():
        report = base.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    report = dict(report)
    for inherited_development_field in (
        "development_role",
        "development1_partial_outcomes_observed",
        "development1_completed_episode_count",
        "scientific_parameters_changed_after_development1",
        "outcomes_observed_before_protocol_freeze",
    ):
        report.pop(inherited_development_field, None)
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "task-utility-qualification-preflight.v1"
        ),
        "qualification_role": True,
        "predecessor_development_outcomes_disclosed": True,
        "selected_pair_task_outcomes_observed_before_freeze": False,
        "stress_proxy_results_observed_before_freeze": True,
        "stress_population_filtered_after_results": False,
        "confirmatory_safety_claim_authorized": False,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_base():
        return base.execute(
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
    with _patched_base():
        return base.validate_results(
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
