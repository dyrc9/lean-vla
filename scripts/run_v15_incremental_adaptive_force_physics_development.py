#!/usr/bin/env python3
"""Develop v15.7 incremental adaptive recovery on disclosed physics lanes."""

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
    run_l2_predictive_virtual_brake_v15_incremental_adaptive_force_recovery as recovery,
)
from scripts import run_v15_adaptive_force_physics_development as v156  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "physics-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "physics-development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_7_incremental_adaptive_force_physics_development"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "physics_development_protocol.json"
)
V14_BASELINE = v156.V14_BASELINE
V15_BASELINE = "v15_7_incremental_adaptive_force_recovery"
BASELINES = ("no_guard", "reactive_stop", V14_BASELINE, V15_BASELINE)
PHYSICS_CONDITIONS = v156.PHYSICS_CONDITIONS
_BASE_VERIFY_PROTOCOL = v156._verify_protocol
_BASE_ANALYZE = v156._analyze
_BASE_REPLACE_NAMES = v156._replace_names
_BASE_RUN_SCREENED = v156._run_screened


class V15IncrementalAdaptiveForcePhysicsDevelopmentError(RuntimeError):
    """Raised when the v15.7 development contract differs."""


def _replace_names(value: Any, *, reverse: bool = False) -> Any:
    old, new = (
        (V15_BASELINE, v156.v155.V15_BASELINE)
        if reverse
        else (v156.v155.V15_BASELINE, V15_BASELINE)
    )

    def replace(text: str) -> str:
        result = text.replace(old, new)
        return result.replace("v15_7", "v15_6") if reverse else result.replace(
            "v15_6", "v15_7"
        )

    if isinstance(value, dict):
        return {
            replace(str(key)): _replace_names(item, reverse=reverse)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_names(item, reverse=reverse) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_names(item, reverse=reverse) for item in value)
    if isinstance(value, str):
        return replace(value)
    return value


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    _BASE_VERIFY_PROTOCOL(protocol)
    design = protocol.get("design", {})
    if (
        design.get("incremental_extended_search") is not True
        or design.get("maximum_extended_candidates_per_increment") != 1
        or design.get("extended_recovery_force_attribution_bound") is not True
    ):
        raise V15IncrementalAdaptiveForcePhysicsDevelopmentError(
            "unsupported v15.7 incremental search contract"
        )


def _run_screened(env: Any) -> dict[str, Any]:
    created: list[Any] = []
    v154 = v156.v155.v154
    original_class = v154.recovery.MultiJointDynamicStateRecoveryEnvironment
    original_schema = v154.recovery.BRAKE_AUDIT_SCHEMA

    class RecordingIncrementalEnvironment(
        recovery.MultiJointIncrementalAdaptiveForceRecoveryEnvironment
    ):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    v154.recovery.MultiJointDynamicStateRecoveryEnvironment = (
        RecordingIncrementalEnvironment
    )
    v154.recovery.BRAKE_AUDIT_SCHEMA = recovery.BRAKE_AUDIT_SCHEMA
    try:
        result = v154._run_screened(env)
    finally:
        v154.recovery.BRAKE_AUDIT_SCHEMA = original_schema
        v154.recovery.MultiJointDynamicStateRecoveryEnvironment = original_class
    if len(created) != 1:
        raise V15IncrementalAdaptiveForcePhysicsDevelopmentError(
            "v15.7 screened wrapper creation count differs"
        )
    observations = created[0].observations
    result.update(
        {
            "force_constrained_audit_count": len(observations),
            "force_constrained_inactive_count": sum(
                row.get("force_constrained_recovery_active") is not True
                for row in observations
            ),
            "selected_post_force_prediction_identity_failure_count": sum(
                row.get("selected_post_force_prediction_execution_identity")
                is not True
                for row in observations
            ),
            "selected_force_infeasible_count": sum(
                row.get("selected_force_feasible") is not True
                for row in observations
            ),
            "force_rejected_base_eligible_candidate_count": sum(
                int(row["force_rejected_base_eligible_candidate_count"])
                for row in observations
            ),
            "force_constrained_soft_profile_mismatch_count": sum(
                row.get("adaptive_force_recovery_active") is not True
                for row in observations
            ),
            "adaptive_force_audit_count": len(observations),
            "adaptive_force_inactive_count": sum(
                row.get("adaptive_force_recovery_active") is not True
                for row in observations
            ),
            "proactive_trigger_margin_mismatch_count": sum(
                row.get("adaptive_proactive_trigger_margin_rad")
                != recovery.predecessor.PROACTIVE_TRIGGER_MARGIN_RAD
                for row in observations
            ),
            "extended_recovery_evaluated_count": sum(
                row.get("adaptive_extended_recovery_evaluated") is True
                for row in observations
            ),
            "extended_recovery_selected_count": sum(
                row.get("adaptive_extended_recovery_selected") is True
                for row in observations
            ),
            "fallback_profile_evaluated_count": sum(
                row.get("adaptive_fallback_profile_evaluated") is True
                for row in observations
            ),
            "fallback_profile_selected_count": sum(
                row.get("adaptive_fallback_profile_selected") is True
                for row in observations
            ),
            "incremental_adaptive_force_audit_count": len(observations),
            "incremental_adaptive_force_inactive_count": sum(
                row.get("incremental_adaptive_force_recovery_active")
                is not True
                for row in observations
            ),
            "incremental_short_circuit_identity_failure_count": sum(
                row.get("incremental_extended_search_short_circuit_identity")
                is not True
                for row in observations
            ),
            "incremental_force_attribution_identity_failure_count": sum(
                row.get(
                    "incremental_extended_recovery_force_attribution_identity"
                )
                is not True
                for row in observations
            ),
            "maximum_incremental_extended_candidate_evaluated_count": max(
                (
                    int(
                        row[
                            "incremental_extended_candidate_evaluated_count"
                        ]
                    )
                    for row in observations
                ),
                default=0,
            ),
        }
    )
    return result


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failures: Mapping[str, int],
    contact_reports: list[Mapping[str, Any]],
    physics_audits: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    analysis, gates = _BASE_ANALYZE(
        protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    reports = [row["baselines"][v156.OLD_V15_BASELINE] for row in rows]
    metrics = {
        "v15_7_incremental_adaptive_force_audit_count": sum(
            int(report["incremental_adaptive_force_audit_count"])
            for report in reports
        ),
        "v15_7_incremental_adaptive_force_inactive_count": sum(
            int(report["incremental_adaptive_force_inactive_count"])
            for report in reports
        ),
        "v15_7_incremental_short_circuit_identity_failure_count": sum(
            int(report["incremental_short_circuit_identity_failure_count"])
            for report in reports
        ),
        "v15_7_incremental_force_attribution_identity_failure_count": sum(
            int(report["incremental_force_attribution_identity_failure_count"])
            for report in reports
        ),
        "v15_7_maximum_incremental_extended_candidate_evaluated_count": max(
            (
                int(
                    report[
                        "maximum_incremental_extended_candidate_evaluated_count"
                    ]
                )
                for report in reports
            ),
            default=0,
        ),
    }
    gates = {
        **gates,
        "v15_7_incremental_adaptive_force_audit_coverage": (
            metrics["v15_7_incremental_adaptive_force_audit_count"]
            == protocol["gates"]["expected_v15_7_policy_step_count"]
        ),
        "v15_7_incremental_adaptive_force_active": (
            metrics["v15_7_incremental_adaptive_force_inactive_count"] == 0
        ),
        "v15_7_incremental_short_circuit_identity": (
            metrics["v15_7_incremental_short_circuit_identity_failure_count"]
            == 0
        ),
        "v15_7_incremental_force_attribution_identity": (
            metrics[
                "v15_7_incremental_force_attribution_identity_failure_count"
            ]
            == 0
        ),
        "v15_7_incremental_extended_candidate_bound": (
            metrics[
                "v15_7_maximum_incremental_extended_candidate_evaluated_count"
            ]
            <= protocol["gates"][
                "maximum_incremental_extended_candidate_evaluated_per_step"
            ]
        ),
    }
    return (
        {
            **analysis,
            "incremental_adaptive_force_metrics": metrics,
            "predecessor_incremental_nonpass_reinterpreted": False,
        },
        gates,
    )


@contextmanager
def _patched_runner_contract() -> Iterator[None]:
    replacements = {
        "PROTOCOL_SCHEMA": PROTOCOL_SCHEMA,
        "EVIDENCE_SCHEMA": EVIDENCE_SCHEMA,
        "AUTHORIZED_STATUS": AUTHORIZED_STATUS,
        "DEFAULT_PROTOCOL": DEFAULT_PROTOCOL,
        "V15_BASELINE": V15_BASELINE,
        "BASELINES": BASELINES,
        "_replace_names": _replace_names,
        "_verify_protocol": _verify_protocol,
        "_run_screened": _run_screened,
        "_analyze": _analyze,
    }
    originals = {name: getattr(v156, name) for name in replacements}
    for name, value in replacements.items():
        setattr(v156, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            setattr(v156, name, value)


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    with _patched_runner_contract():
        report = v156.preflight(protocol, gpu=gpu)
    report["schema"] = EVIDENCE_SCHEMA.replace("evidence.v1", "preflight.v1")
    return report


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    with _patched_runner_contract():
        return v156.execute(protocol, protocol_path=protocol_path, gpu=gpu)


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    with _patched_runner_contract():
        return v156.validate_results(protocol, protocol_path=protocol_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        print(canonical_text(preflight(protocol, gpu=args.gpu)), end="")
        return 0
    if args.validate_results:
        evidence = validate_results(protocol, protocol_path=protocol_path)
        print(
            canonical_text(
                {
                    "schema": EVIDENCE_SCHEMA + ".validation",
                    "valid": True,
                    "development_pass": evidence["development_pass"],
                    "classification": evidence["classification"],
                }
            ),
            end="",
        )
        return 0
    evidence = execute(protocol, protocol_path=protocol_path, gpu=args.gpu)
    print(
        canonical_text(
            {
                "schema": EVIDENCE_SCHEMA + ".completion",
                "development_pass": evidence["development_pass"],
                "classification": evidence["classification"],
                "output_root": v156._output_root(protocol)
                .relative_to(REPO_ROOT)
                .as_posix(),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
