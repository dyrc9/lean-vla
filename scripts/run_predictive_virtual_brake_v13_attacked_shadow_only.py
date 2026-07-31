#!/usr/bin/env python3
"""Run or validate the v13 attacked shadow-only causal ablation."""

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
from scripts import run_joint_limit_containment_v11_attacked_scale45 as attacker  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v13_shadow_only as online  # noqa: E402
from scripts import run_predictive_virtual_brake_v13_clean as clean  # noqa: E402
from scripts import run_predictive_virtual_brake_v13_shadow_only as shadow  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-attacked-shadow-only-"
    "protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v13-attacked-shadow-only-"
    "evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v13_predictive_virtual_brake_attacked_shadow_only"
)
STAGE = "predictive_virtual_brake_v13_attacked_shadow_only_scale45"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v13_"
    "attacked_shadow_only_protocol.json"
)
_BASE_VALIDATE_PROTOCOL = attacker.validate_protocol
_BASE_ATTACK_ENRICH = attacker.inherited._enrich


def _attacked_shadow_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    metrics, gates = shadow._shadow_metrics(protocol, evidence)
    descriptive = metrics.pop("descriptive_outcome_gate_results")
    return {
        **metrics,
        "descriptive_attacked_shadow_outcome_gate_results": (
            descriptive
        ),
    }, gates


def _attacked_shadow_enrich(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_ATTACK_ENRICH(protocol, evidence)
    return {
        **enriched,
        "method_claim": (
            "outcome-disclosed paired instruction-attack simulator "
            "shadow-and-restore ablation without guard intervention"
        ),
        "shadow_only_ablation": True,
        "guard_candidate_evaluation_enabled": False,
        "guard_intervention_enabled": False,
        "outcome_gates_are_descriptive_only": True,
        "efficacy_pass_declared": False,
        "confirmatory_claim_authorized": False,
        "target_joint_only": True,
    }


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    originals = (
        attacker.PROTOCOL_SCHEMA,
        attacker.AUTHORIZED_STATUS,
        attacker.STAGE,
        attacker.DEFAULT_PROTOCOL,
    )
    attacker.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    attacker.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    attacker.STAGE = STAGE
    attacker.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    try:
        _BASE_VALIDATE_PROTOCOL(
            protocol,
            protocol_path=protocol_path,
        )
    finally:
        (
            attacker.PROTOCOL_SCHEMA,
            attacker.AUTHORIZED_STATUS,
            attacker.STAGE,
            attacker.DEFAULT_PROTOCOL,
        ) = originals


@contextmanager
def _patched_attacker() -> Iterator[None]:
    physical = attacker.inherited
    originals = (
        attacker.PROTOCOL_SCHEMA,
        attacker.EVIDENCE_SCHEMA,
        attacker.AUTHORIZED_STATUS,
        attacker.STAGE,
        attacker.DEFAULT_PROTOCOL,
        attacker.online,
        attacker.validate_protocol,
        attacker.clean._v11_metrics,
        physical._enrich,
        clean.EXPECTED_RUNNER,
        clean.online,
    )
    attacker.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    attacker.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    attacker.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    attacker.STAGE = STAGE
    attacker.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    attacker.online = online
    attacker.validate_protocol = validate_protocol
    # The v11 attacked context assigns base._v10_metrics from this exact
    # symbol after the outer context has entered.  Patch the inner source,
    # not base._v10_metrics, so the v13 hook cannot be overwritten.
    attacker.clean._v11_metrics = _attacked_shadow_metrics
    physical._enrich = _attacked_shadow_enrich
    clean.EXPECTED_RUNNER = online.RUNNER_VARIANT
    clean.online = online
    try:
        yield
    finally:
        (
            attacker.PROTOCOL_SCHEMA,
            attacker.EVIDENCE_SCHEMA,
            attacker.AUTHORIZED_STATUS,
            attacker.STAGE,
            attacker.DEFAULT_PROTOCOL,
            attacker.online,
            attacker.validate_protocol,
            attacker.clean._v11_metrics,
            physical._enrich,
            clean.EXPECTED_RUNNER,
            clean.online,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_attacker():
        report = attacker.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    observed = Path(sys.executable).resolve()
    required = clean.REQUIRED_INTERPRETER.resolve()
    blockers = list(report["blockers"])
    if observed != required:
        blockers.append(
            "v13 attacked shadow-only rollout requires "
            "external/openpi/.venv/bin/python"
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v13-attacked-"
            "shadow-only-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "required_interpreter_resolved": str(required),
        "observed_interpreter_resolved": str(observed),
        "interpreter_ready": observed == required,
        "shadow_only_ablation": True,
        "guard_candidate_evaluation_enabled": False,
        "outcome_gates_are_descriptive_only": True,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    if Path(sys.executable).resolve() != clean.REQUIRED_INTERPRETER.resolve():
        raise RuntimeError(
            "v13 attacked shadow-only rollout requires "
            "external/openpi/.venv/bin/python"
        )
    with _patched_attacker():
        return attacker.execute(
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
    with _patched_attacker():
        return attacker.validate_results(
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
