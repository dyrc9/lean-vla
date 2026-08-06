#!/usr/bin/env python3
"""Run paired SABER-attacked task utility for the frozen v15.14 method."""

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
from scripts import (  # noqa: E402
    run_v15_bounded_state_triggered_task_utility_qualification as clean,
)
from scripts import (  # noqa: E402
    run_v15_force_attributed_recovery_attacked_task_utility_qualification as legacy,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.14-unified-force-envelope-"
    "recovery-attacked-task-utility-qualification-protocol.v1"
)
BASE_EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.14-unified-force-envelope-"
    "recovery-attacked-task-utility-base-evidence.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.14-unified-force-envelope-"
    "recovery-attacked-task-utility-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_14_unified_force_envelope_attacked_task_utility_"
    "qualification"
)
STAGE = (
    "predictive_virtual_brake_v15_14_unified_force_envelope_attacked_"
    "task_utility_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_14_unified_force_envelope_"
    "attacked_task_utility_qualification_fresh2_protocol.json"
)
ATTACKED_EVIDENCE_NAME = legacy.ATTACKED_EVIDENCE_NAME
_CLEAN_QUALIFICATION_ENRICH = clean._qualification_enrich
_LEGACY_BUILD_ATTACKED_EVIDENCE = legacy._build_attacked_evidence
_LEGACY_PATCHED_ATTACKED = legacy._patched_attacked
_WarningAudit = legacy._WarningAudit


class V15UnifiedForceEnvelopeAttackedError(RuntimeError):
    """Raised when frozen v15.14 attacked evidence differs."""


def _attacked_base_enrich(
    protocol: Mapping[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    enriched = _CLEAN_QUALIFICATION_ENRICH(protocol, evidence)
    return {
        **enriched,
        "schema": BASE_EVIDENCE_SCHEMA,
        "condition": "instruction_attacked",
        "held_out_attack_outcomes": True,
        "clean_task_outcomes_observed_before_protocol_freeze": True,
        "task_outcomes_observed_before_protocol_freeze": True,
        "selected_pair_task_outcomes_observed_before_freeze": True,
        "attacked_task_outcomes_observed_before_protocol_freeze": True,
        "fresh1_integrity_nonpass_observed_before_protocol_freeze": True,
        "fresh2_attacked_task_outcomes_observed_before_protocol_freeze": False,
        "method_claim": (
            "paired pre-specified SABER instruction-attack task utility for "
            "the frozen v15.14 unified-force-envelope recovery"
        ),
    }


def _build_attacked_evidence(
    protocol: Mapping[str, Any],
    base: Mapping[str, Any],
    warning_report: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _LEGACY_BUILD_ATTACKED_EVIDENCE(
        protocol, base, warning_report
    )
    return {
        **evidence,
        "schema": EVIDENCE_SCHEMA,
        "method_claim": (
            "paired simulator evidence under the frozen SABER task-prompt "
            "constraint-violation attack for v15.14 unified-force-envelope "
            "recovery"
        ),
    }


@contextmanager
def _patched_all_arm_attack(
    protocol: Mapping[str, Any],
    warnings: _WarningAudit | None = None,
) -> Iterator[None]:
    """Forward the frozen attack to both L2-enabled and disabled runners."""

    original_disabled = clean.disabled_online.run_episode
    records = legacy.attack_base.attack_record_index(protocol)

    def run_attacked_disabled_episode(**kwargs: Any) -> dict[str, Any]:
        forwarded = dict(kwargs)
        forwarded["attack_records"] = records
        if warnings is not None:
            warnings.episode_id = Path(
                str(forwarded["output_dir"])
            ).name
        try:
            return original_disabled(**forwarded)
        finally:
            if warnings is not None:
                warnings.episode_id = None

    clean.disabled_online.run_episode = run_attacked_disabled_episode
    try:
        with _LEGACY_PATCHED_ATTACKED(protocol, warnings):
            yield
    finally:
        clean.disabled_online.run_episode = original_disabled


@contextmanager
def _patched_legacy() -> Iterator[None]:
    originals = (
        legacy.clean,
        legacy.PROTOCOL_SCHEMA,
        legacy.BASE_EVIDENCE_SCHEMA,
        legacy.EVIDENCE_SCHEMA,
        legacy.AUTHORIZED_STATUS,
        legacy.STAGE,
        legacy.DEFAULT_PROTOCOL,
        legacy._BASE_QUALIFICATION_ENRICH,
        legacy._attacked_base_enrich,
        legacy._build_attacked_evidence,
        legacy._patched_attacked,
    )
    legacy.clean = clean
    legacy.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    legacy.BASE_EVIDENCE_SCHEMA = BASE_EVIDENCE_SCHEMA
    legacy.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    legacy.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    legacy.STAGE = STAGE
    legacy.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    legacy._BASE_QUALIFICATION_ENRICH = _CLEAN_QUALIFICATION_ENRICH
    legacy._attacked_base_enrich = _attacked_base_enrich
    legacy._build_attacked_evidence = _build_attacked_evidence
    legacy._patched_attacked = _patched_all_arm_attack
    try:
        yield
    finally:
        (
            legacy.clean,
            legacy.PROTOCOL_SCHEMA,
            legacy.BASE_EVIDENCE_SCHEMA,
            legacy.EVIDENCE_SCHEMA,
            legacy.AUTHORIZED_STATUS,
            legacy.STAGE,
            legacy.DEFAULT_PROTOCOL,
            legacy._BASE_QUALIFICATION_ENRICH,
            legacy._attacked_base_enrich,
            legacy._build_attacked_evidence,
            legacy._patched_attacked,
        ) = originals


def validate_protocol(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> None:
    with _patched_legacy():
        legacy.validate_protocol(protocol, protocol_path=protocol_path)


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_legacy():
        report = legacy.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v15.14-unified-force-"
            "envelope-attacked-task-utility-qualification-preflight.v1"
        ),
        "method_version": "v15.14",
        "selected_pair_task_outcomes_observed_before_freeze": True,
        "attacked_task_outcomes_observed_before_freeze": True,
        "fresh2_attacked_task_outcomes_observed_before_freeze": False,
        "fresh1_integrity_nonpass_observed_before_freeze": True,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_legacy():
        return legacy.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    with _patched_legacy():
        return legacy.validate_results(
            protocol, protocol_path=protocol_path
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
            parser.error("--execute requires --policy-gpu and --egl-gpu")
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol, protocol_path=protocol_path
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
