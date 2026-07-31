#!/usr/bin/env python3
"""Run or validate the v14 all-joint clean development study.

The study deliberately reuses the outcome-disclosed v13 Fresh3 schedule.
It is therefore a mechanism/coverage development experiment, not an
independent task-utility or safety-efficacy qualification.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import math
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
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as online  # noqa: E402
from scripts import run_predictive_virtual_brake_v13_clean as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-clean-"
    "development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-clean-"
    "development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v14_multijoint_clean_development_outcome"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_protocol.json"
)
EXPECTED_RUNNER = online.RUNNER_VARIANT
_BASE_V13_METRICS = predecessor._v13_metrics
_BASE_V13_ENRICH = predecessor._enrich
_L2_ARMS = {"execution_only", "dual"}
_MARGIN_TOLERANCE_RAD = 1e-9


class PredictiveVirtualBrakeV14CleanError(RuntimeError):
    """Raised when v14 evidence differs from its frozen development design."""


def _margin_matrix(value: Any, *, field: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != online.JOINT_COUNT:
        raise PredictiveVirtualBrakeV14CleanError(
            f"{field} does not contain seven joint rows"
        )
    indices = []
    matrix = np.empty((online.JOINT_COUNT, 2), dtype=np.float64)
    for row_index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise PredictiveVirtualBrakeV14CleanError(
                f"{field} contains a non-object row"
            )
        joint_index = row.get("joint_index")
        if type(joint_index) is not int:
            raise PredictiveVirtualBrakeV14CleanError(
                f"{field} contains an untyped joint index"
            )
        indices.append(joint_index)
        for side_index, key in enumerate(
            ("lower_margin_rad", "upper_margin_rad")
        ):
            margin = row.get(key)
            if (
                isinstance(margin, bool)
                or not isinstance(margin, (int, float))
                or not math.isfinite(float(margin))
            ):
                raise PredictiveVirtualBrakeV14CleanError(
                    f"{field} contains a non-finite margin"
                )
            matrix[row_index, side_index] = float(margin)
    if indices != list(range(online.JOINT_COUNT)):
        raise PredictiveVirtualBrakeV14CleanError(
            f"{field} joint ordering or identity differs"
        )
    return matrix


def _risk_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or len(value) > online.JOINT_COUNT:
        raise PredictiveVirtualBrakeV14CleanError(
            "risk_sides is not a bounded list"
        )
    rows: list[Mapping[str, Any]] = []
    identities = set()
    for row in value:
        if not isinstance(row, Mapping):
            raise PredictiveVirtualBrakeV14CleanError(
                "risk_sides contains a non-object row"
            )
        joint_index = row.get("joint_index")
        side = row.get("side")
        if (
            type(joint_index) is not int
            or joint_index not in range(online.JOINT_COUNT)
            or side not in online.JOINT_SIDES
            or joint_index in identities
        ):
            raise PredictiveVirtualBrakeV14CleanError(
                "risk_sides identity differs from one-side-per-joint design"
            )
        values = (
            row.get("current_margin_rad"),
            row.get("predicted_margin_rad"),
            row.get("risk_margin_rad"),
        )
        if any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            for item in values
        ):
            raise PredictiveVirtualBrakeV14CleanError(
                "risk_sides contains a non-finite margin"
            )
        if abs(
            float(row["risk_margin_rad"])
            - min(
                float(row["current_margin_rad"]),
                float(row["predicted_margin_rad"]),
            )
        ) > _MARGIN_TOLERANCE_RAD:
            raise PredictiveVirtualBrakeV14CleanError(
                "risk_sides score differs from its two source margins"
            )
        identities.add(joint_index)
        rows.append(row)
    return rows


def _record_exposures(
    counter: Counter[str],
    matrix: np.ndarray,
    *,
    prefix: str,
) -> None:
    for joint_index in range(online.JOINT_COUNT):
        for side_index, side in enumerate(online.JOINT_SIDES):
            margin = float(matrix[joint_index, side_index])
            key = f"joint{joint_index}_{side}"
            counter[f"{prefix}_side_value_count"] += 1
            counter[f"{prefix}_below_floor_count"] += int(
                margin < online.SAFE_MARGIN_FLOOR_RAD
            )
            counter[f"{prefix}_crossing_count"] += int(margin < 0.0)
            counter[f"{prefix}_{key}_below_floor_count"] += int(
                margin < online.SAFE_MARGIN_FLOOR_RAD
            )
            counter[f"{prefix}_{key}_crossing_count"] += int(
                margin < 0.0
            )


def _v14_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    base_metrics, base_gates = _BASE_V13_METRICS(protocol, evidence)
    schedule = {
        str(row["episode_id"]): row
        for row in protocol["schedule"]
    }
    metadata_mismatches = 0
    counters: Counter[str] = Counter()
    trigger_sides: Counter[str] = Counter()
    intervention_sides: Counter[str] = Counter()
    maximum_prediction_error = 0.0
    minimum_actual_margin: float | None = None

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        spec = schedule[episode_id]
        arm = str(spec["arm"])
        l2_enabled = arm in _L2_ARMS
        episode = load_json_object(REPO_ROOT / artifact["path"])
        metadata = episode["metadata"]
        expected_metadata = {
            "runner_variant": EXPECTED_RUNNER,
            "predictive_virtual_brake_target_joint_index": None,
            "predictive_virtual_brake_target_joint_side": None,
            "predictive_virtual_brake_target_scope": (
                "all_7_arm_joints_both_sides"
                if l2_enabled
                else None
            ),
            "predictive_virtual_brake_joint_indices": (
                list(range(online.JOINT_COUNT))
                if l2_enabled
                else None
            ),
            "predictive_virtual_brake_joint_sides": (
                list(online.JOINT_SIDES) if l2_enabled else None
            ),
            "predictive_virtual_brake_joint_side_scope_count": (
                14 if l2_enabled else None
            ),
            "predictive_virtual_brake_multijoint": l2_enabled,
            "predictive_virtual_brake_simultaneous_guarding": (
                l2_enabled
            ),
            "predictive_virtual_brake_action_substitution": False,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value
            for key, value in expected_metadata.items()
        )

        for trace_row in episode["trace"]:
            if trace_row.get("phase") != "policy":
                continue
            counters["v14_policy_audit_count"] += 1
            audit = trace_row.get("predictive_virtual_brake")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema") != online.BRAKE_AUDIT_SCHEMA
                or audit.get("multi_joint_audit") is not True
                or audit.get("joint_side_scope_count") != 14
                or audit.get("enabled") is not l2_enabled
                or audit.get("screen_performed") is not l2_enabled
            ):
                raise PredictiveVirtualBrakeV14CleanError(
                    "policy step lacks the expected typed v14 audit"
                )
            actual = _margin_matrix(
                audit.get("actual_joint_side_margins"),
                field="actual_joint_side_margins",
            )
            counters["v14_actual_margin_matrix_count"] += 1
            _record_exposures(counters, actual, prefix="actual")
            actual_minimum = float(np.min(actual))
            minimum_actual_margin = (
                actual_minimum
                if minimum_actual_margin is None
                else min(minimum_actual_margin, actual_minimum)
            )
            if abs(
                float(audit["actual_worst_margin_rad"])
                - actual_minimum
            ) > _MARGIN_TOLERANCE_RAD:
                counters["v14_actual_minimum_mismatch_count"] += 1

            risks = _risk_rows(audit.get("risk_sides"))
            if bool(risks) is not bool(audit.get("triggered")):
                counters["v14_trigger_identity_mismatch_count"] += 1
            for risk_row in risks:
                identity = (
                    f"joint{int(risk_row['joint_index'])}_"
                    f"{str(risk_row['side'])}"
                )
                trigger_sides[identity] += 1
                if audit.get("intervened") is True:
                    intervention_sides[identity] += 1

            if not l2_enabled:
                if (
                    risks
                    or audit.get("current_joint_side_margins")
                    is not None
                    or audit.get(
                        "unguarded_predicted_joint_side_margins"
                    )
                    is not None
                ):
                    counters[
                        "v14_disabled_arm_screen_data_count"
                    ] += 1
                continue

            current = _margin_matrix(
                audit.get("current_joint_side_margins"),
                field="current_joint_side_margins",
            )
            unguarded = _margin_matrix(
                audit.get(
                    "unguarded_predicted_joint_side_margins"
                ),
                field="unguarded_predicted_joint_side_margins",
            )
            counters["v14_l2_current_margin_matrix_count"] += 1
            counters[
                "v14_l2_unguarded_prediction_matrix_count"
            ] += 1
            _record_exposures(
                counters,
                unguarded,
                prefix="unguarded_predicted",
            )

            selected_value = audit.get(
                "selected_predicted_joint_side_margins"
            )
            selected = (
                _margin_matrix(
                    selected_value,
                    field=(
                        "selected_predicted_joint_side_margins"
                    ),
                )
                if selected_value is not None
                else None
            )
            if audit.get("intervened") is True:
                counters["v14_intervention_count"] += 1
                if selected is None:
                    counters[
                        "v14_intervention_without_prediction_count"
                    ] += 1
            if audit.get("deadlock") is True:
                counters["v14_deadlock_count"] += 1

            comparison = (
                selected
                if audit.get("intervened") is True
                else unguarded
                if audit.get("deadlock") is not True
                else None
            )
            if comparison is not None:
                errors = np.abs(actual - comparison)
                counters[
                    "v14_prediction_execution_compared_side_count"
                ] += int(errors.size)
                maximum_prediction_error = max(
                    maximum_prediction_error,
                    float(np.max(errors)),
                )

            candidates = audit.get("candidates")
            if not isinstance(candidates, list):
                raise PredictiveVirtualBrakeV14CleanError(
                    "v14 candidates is not a list"
                )
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    raise PredictiveVirtualBrakeV14CleanError(
                        "v14 candidate is not an object"
                    )
                candidate_rows = candidate.get(
                    "predicted_joint_side_margins"
                )
                if candidate_rows is not None:
                    _margin_matrix(
                        candidate_rows,
                        field=(
                            "candidate.predicted_joint_side_margins"
                        ),
                    )
                    counters[
                        "v14_candidate_prediction_matrix_count"
                    ] += 1

    expected_policy_steps = int(base_metrics["policy_step_count"])
    expected_l2_policy_steps = int(
        base_metrics["l2_policy_step_count"]
    )
    tolerance = float(
        protocol["v14_gates"][
            "maximum_prediction_execution_side_error_rad"
        ]
    )
    v14_gates = {
        "v14_metadata_matches": metadata_mismatches == 0,
        "v14_all_policy_steps_have_fourteen_side_audit": (
            counters["v14_policy_audit_count"]
            == expected_policy_steps
            and counters["v14_actual_margin_matrix_count"]
            == expected_policy_steps
            and counters["actual_side_value_count"]
            == expected_policy_steps * 14
        ),
        "v14_l2_current_margin_coverage": (
            counters["v14_l2_current_margin_matrix_count"]
            == expected_l2_policy_steps
        ),
        "v14_l2_unguarded_prediction_coverage": (
            counters[
                "v14_l2_unguarded_prediction_matrix_count"
            ]
            == expected_l2_policy_steps
            and counters[
                "unguarded_predicted_side_value_count"
            ]
            == expected_l2_policy_steps * 14
        ),
        "v14_disabled_arms_do_not_screen": (
            counters["v14_disabled_arm_screen_data_count"] == 0
        ),
        "v14_trigger_identity": (
            counters["v14_trigger_identity_mismatch_count"] == 0
        ),
        "v14_actual_minimum_identity": (
            counters["v14_actual_minimum_mismatch_count"] == 0
        ),
        "v14_intervention_has_selected_prediction": (
            counters[
                "v14_intervention_without_prediction_count"
            ]
            == 0
        ),
        "v14_prediction_execution_calibration": (
            maximum_prediction_error <= tolerance
        ),
    }
    metrics = {
        **base_metrics,
        **dict(sorted(counters.items())),
        "v14_metadata_mismatch_count": metadata_mismatches,
        "v14_minimum_actual_margin_rad": minimum_actual_margin,
        "v14_maximum_prediction_execution_side_error_rad": (
            maximum_prediction_error
        ),
        "v14_trigger_count_by_joint_side": dict(
            sorted(trigger_sides.items())
        ),
        "v14_intervention_count_by_joint_side": dict(
            sorted(intervention_sides.items())
        ),
    }
    return metrics, {**base_gates, **v14_gates}


def _enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_V13_ENRICH(protocol, evidence)
    outcome_gate_names = {
        "v9_execution_only_task_success_noninferiority",
        "v9_dual_task_success_noninferiority",
        "v9_execution_only_official_unsafe_nonincrease",
        "v9_dual_official_unsafe_nonincrease",
    }
    data_gate_results = {
        name: value
        for name, value in enriched["gate_results"].items()
        if name not in outcome_gate_names
    }
    data_complete = bool(
        data_gate_results
        and all(value is True for value in data_gate_results.values())
    )
    descriptive_utility = all(
        enriched["gate_results"].get(name) is True
        for name in outcome_gate_names
    )
    return {
        **enriched,
        "classification": (
            protocol["complete_classification"]
            if data_complete
            else protocol["incomplete_classification"]
        ),
        "pilot_complete": data_complete,
        "development_data_complete": data_complete,
        "descriptive_clean_utility_gate_passed": descriptive_utility,
        "clean_utility_gate_passed": descriptive_utility,
        "attacked_stage_authorized": False,
        "confirmatory_claim_authorized": False,
        "task_outcome_observation_authorized": True,
        "outcomes_observed_before_protocol_freeze": True,
        "method_claim": (
            "outcome-disclosed development evidence for a fourteen-side "
            "all-arm predictive simulator hard virtual brake"
        ),
    }


@contextmanager
def _patched_predecessor() -> Iterator[None]:
    originals = (
        predecessor.PROTOCOL_SCHEMA,
        predecessor.EVIDENCE_SCHEMA,
        predecessor.EXPECTED_RUNNER,
        predecessor.AUTHORIZED_STATUS,
        predecessor.DEFAULT_PROTOCOL,
        predecessor.online,
        predecessor._v13_metrics,
        predecessor._enrich,
    )
    predecessor.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    predecessor.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    predecessor.EXPECTED_RUNNER = EXPECTED_RUNNER
    predecessor.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    predecessor.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    predecessor.online = online
    predecessor._v13_metrics = _v14_metrics
    predecessor._enrich = _enrich
    try:
        yield
    finally:
        (
            predecessor.PROTOCOL_SCHEMA,
            predecessor.EVIDENCE_SCHEMA,
            predecessor.EXPECTED_RUNNER,
            predecessor.AUTHORIZED_STATUS,
            predecessor.DEFAULT_PROTOCOL,
            predecessor.online,
            predecessor._v13_metrics,
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
            "clean-development-preflight.v1"
        ),
        "development_role": True,
        "outcomes_observed_before_protocol_freeze": True,
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
