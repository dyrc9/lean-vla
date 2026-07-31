#!/usr/bin/env python3
"""Run or validate the v14 same-schedule shadow-only causal control."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_shadow_only as online  # noqa: E402
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "shadow-only-causal-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "shadow-only-causal-development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v14_multijoint_shadow_only_causal_development"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_development_protocol.json"
)
_BASE_V14_METRICS = predecessor._v14_metrics
_BASE_V14_ENRICH = predecessor._enrich
_L2_ARMS = {"execution_only", "dual"}


class PredictiveVirtualBrakeV14ShadowOnlyError(RuntimeError):
    """Raised when shadow-only evidence differs from its frozen design."""


def _shadow_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    metrics, gates = _BASE_V14_METRICS(protocol, evidence)
    schedule = {
        str(row["episode_id"]): row
        for row in protocol["schedule"]
    }
    counters: Counter[str] = Counter()
    metadata_mismatches = 0

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        arm = str(schedule[episode_id]["arm"])
        l2_enabled = arm in _L2_ARMS
        episode = load_json_object(REPO_ROOT / artifact["path"])
        metadata = episode["metadata"]
        expected_metadata = {
            "runner_variant": online.RUNNER_VARIANT,
            "predictive_virtual_brake_active": l2_enabled,
            "predictive_virtual_brake_simultaneous_guarding": False,
            "predictive_virtual_brake_shadow_monitor_active": l2_enabled,
            "predictive_virtual_brake_shadow_only": l2_enabled,
            "predictive_virtual_brake_intervention_authority": False,
            "predictive_virtual_brake_guard_candidate_evaluation": False,
            "shadow_only_same_schedule_causal_control": True,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value
            for key, value in expected_metadata.items()
        )

        for trace_row in episode["trace"]:
            if trace_row.get("phase") != "policy":
                continue
            audit = trace_row.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
            ):
                raise PredictiveVirtualBrakeV14ShadowOnlyError(
                    "policy row lacks the typed shadow-only audit"
                )
            counters["shadow_only_policy_audit_count"] += 1
            actual = predecessor._margin_matrix(
                audit.get("actual_joint_side_margins"),
                field="actual_joint_side_margins",
            )
            below_floor = int(
                np.sum(actual < online.SAFE_MARGIN_FLOOR_RAD)
            )
            crossings = int(np.sum(actual < 0.0))
            if l2_enabled:
                counters["shadow_only_l2_policy_audit_count"] += 1
                counters["shadow_only_l2_trigger_count"] += int(
                    audit.get("triggered") is True
                )
                counters[
                    "shadow_only_l2_actual_below_floor_count"
                ] += below_floor
                counters[
                    "shadow_only_l2_actual_crossing_count"
                ] += crossings
                contract = (
                    audit.get("enabled") is True
                    and audit.get("screen_performed") is True
                    and audit.get("shadow_only") is True
                    and audit.get(
                        "intervention_authority_enabled"
                    )
                    is False
                    and audit.get(
                        "guard_candidate_evaluation_performed"
                    )
                    is False
                    and audit.get("intervened") is False
                    and audit.get("deadlock") is False
                    and audit.get("exact_action_identity") is True
                    and audit.get("shadow_restore_identity") is True
                    and audit.get("candidate_count") == 0
                    and audit.get("eligible_candidate_count") == 0
                    and audit.get("shadow_env_step_count") == 1
                    and audit.get(
                        "selected_predicted_joint_side_margins"
                    )
                    is None
                    and float(
                        audit[
                            "maximum_abs_guarded_constraint_force"
                        ]
                    )
                    == 0.0
                    and int(
                        audit["torque_bound_violation_count"]
                    )
                    == 0
                )
                counters[
                    "shadow_only_l2_contract_mismatch_count"
                ] += int(not contract)
            else:
                counters[
                    "shadow_only_disabled_policy_audit_count"
                ] += 1
                contract = (
                    audit.get("enabled") is False
                    and audit.get("screen_performed") is False
                    and audit.get("shadow_only") is False
                    and audit.get("intervened") is False
                    and audit.get("deadlock") is False
                    and audit.get("exact_action_identity") is True
                    and audit.get("shadow_env_step_count") == 0
                )
                counters[
                    "shadow_only_disabled_contract_mismatch_count"
                ] += int(not contract)

    expected_l2_episodes = sum(
        str(row["arm"]) in _L2_ARMS
        for row in protocol["schedule"]
    )
    inherited_expected_guarding_mismatches = int(
        metrics["v14_metadata_mismatch_count"]
    )
    expected_policy_steps = int(metrics["policy_step_count"])
    expected_l2_steps = int(metrics["l2_policy_step_count"])
    expected_disabled_steps = (
        expected_policy_steps - expected_l2_steps
    )
    shadow_gates = {
        "shadow_only_metadata_matches": (
            metadata_mismatches == 0
            and inherited_expected_guarding_mismatches
            == expected_l2_episodes
        ),
        "shadow_only_all_policy_steps_audited": (
            counters["shadow_only_policy_audit_count"]
            == expected_policy_steps
        ),
        "shadow_only_l2_contract": (
            counters["shadow_only_l2_policy_audit_count"]
            == expected_l2_steps
            and counters[
                "shadow_only_l2_contract_mismatch_count"
            ]
            == 0
        ),
        "shadow_only_disabled_arm_contract": (
            counters[
                "shadow_only_disabled_policy_audit_count"
            ]
            == expected_disabled_steps
            and counters[
                "shadow_only_disabled_contract_mismatch_count"
            ]
            == 0
        ),
        "shadow_only_zero_intervention_and_deadlock": (
            int(metrics["intervention_count"]) == 0
            and int(metrics["deadlock_count"]) == 0
        ),
    }
    adjusted_gates = {
        **gates,
        "v14_metadata_matches": shadow_gates[
            "shadow_only_metadata_matches"
        ],
        **shadow_gates,
    }
    adjusted_metrics = {
        **metrics,
        **dict(sorted(counters.items())),
        "v14_metadata_mismatch_count": metadata_mismatches,
        "shadow_only_inherited_expected_guarding_mismatch_count": (
            inherited_expected_guarding_mismatches
        ),
        "shadow_only_metadata_mismatch_count": metadata_mismatches,
    }
    return adjusted_metrics, adjusted_gates


def _shadow_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_V14_ENRICH(protocol, evidence)
    return {
        **enriched,
        "method_claim": (
            "outcome-disclosed same-schedule fourteen-side shadow-only "
            "causal control with exact source-action dispatch and no "
            "intervention authority"
        ),
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "causal_development_control": True,
        "full_brake_comparison_requires_terminal_analysis": True,
    }


@contextmanager
def _patched_predecessor() -> Iterator[None]:
    originals = (
        predecessor.PROTOCOL_SCHEMA,
        predecessor.EVIDENCE_SCHEMA,
        predecessor.AUTHORIZED_STATUS,
        predecessor.DEFAULT_PROTOCOL,
        predecessor.EXPECTED_RUNNER,
        predecessor.online,
        predecessor._v14_metrics,
        predecessor._enrich,
    )
    predecessor.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    predecessor.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    predecessor.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    predecessor.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    predecessor.EXPECTED_RUNNER = online.RUNNER_VARIANT
    predecessor.online = online
    predecessor._v14_metrics = _shadow_metrics
    predecessor._enrich = _shadow_enrich
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
            predecessor._v14_metrics,
            predecessor._enrich,
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
            "shadow-only-causal-development-preflight.v1"
        ),
        "causal_development_control": True,
        "same_schedule_as_full_brake": True,
        "intervention_authority_enabled": False,
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
