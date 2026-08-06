#!/usr/bin/env python3
"""Freeze terminal full-brake versus shadow-only causal-development evidence."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
    cluster_bootstrap_paired_difference,
)
from scripts import run_predictive_virtual_brake_v14_multijoint_clean as full_clean  # noqa: E402
from scripts import run_predictive_virtual_brake_v14_multijoint_shadow_only as shadow_clean  # noqa: E402


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_development_protocol.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_terminal_summary.json"
)
FULL_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "clean_development_fresh2_protocol.json"
)
FULL_EVIDENCE_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_"
    "multijoint_clean_20260731_development2"
    / "pilot_evidence.json"
)
CREATED_AT = "2026-07-31T23:55:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "shadow-only-causal-terminal-summary.v1"
)
COMPLETE_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "causal_identity_complete"
)
NONPASS_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "causal_identity_nonpass"
)
_L2_ARMS = {"execution_only", "dual"}
_OUTCOME_FIELDS = (
    "task_success",
    "strict_success_no_cost",
    "unsafe_cost_or_collision",
    "decision",
)


class PredictiveVirtualBrakeV14ShadowTerminalError(RuntimeError):
    """Raised when terminal causal evidence is absent or inconsistent."""


def _bound_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            f"bound path escapes repository: {relative}"
        ) from exc
    return path


def _verify_required_bindings(
    protocol: Mapping[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    rows = []
    valid = True
    for binding in protocol["required_bindings"]:
        path = _bound_path(str(binding["path"]))
        observed = file_sha256(path) if path.is_file() else None
        matched = observed == binding["sha256"]
        valid = valid and matched
        rows.append(
            {
                "path": str(binding["path"]),
                "expected_sha256": str(binding["sha256"]),
                "observed_sha256": observed,
                "matched": matched,
            }
        )
    return valid, rows


def _episode_map(
    evidence: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = {
        str(row["episode_id"]): row
        for row in evidence["episodes"]
    }
    if len(rows) != len(evidence["episodes"]):
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            "evidence contains duplicate episode identities"
        )
    return rows


def _load_episode(
    artifact: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    path = _bound_path(str(artifact["path"]))
    matched = path.is_file() and (
        file_sha256(path) == artifact["sha256"]
    )
    if not path.is_file():
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            f"episode artifact is absent: {path}"
        )
    return load_json_object(path), matched


def _policy_audits(
    episode: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    rows = []
    for trace_row in episode["trace"]:
        if trace_row.get("phase") != "policy":
            continue
        audit = trace_row.get("predictive_virtual_brake")
        if not isinstance(audit, Mapping):
            raise PredictiveVirtualBrakeV14ShadowTerminalError(
                "policy trace lacks a virtual-brake audit"
            )
        rows.append(audit)
    return rows


def _matrix(audit: Mapping[str, Any], field: str) -> np.ndarray:
    return full_clean._margin_matrix(audit.get(field), field=field)


def _risk_identity(audit: Mapping[str, Any]) -> tuple[tuple[int, str], ...]:
    value = audit.get("risk_sides")
    if not isinstance(value, list):
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            "risk_sides is not a list"
        )
    return tuple(
        (int(row["joint_index"]), str(row["side"]))
        for row in value
    )


def _exposure(
    audits: Sequence[Mapping[str, Any]],
    *,
    floor: float,
) -> dict[str, Any]:
    below_floor = 0
    crossings = 0
    minimum: float | None = None
    joint_limit_steps = 0
    for audit in audits:
        actual = _matrix(audit, "actual_joint_side_margins")
        below_floor += int(np.sum(actual < floor))
        crossings += int(np.sum(actual < 0.0))
        observed = float(np.min(actual))
        minimum = observed if minimum is None else min(minimum, observed)
    return {
        "policy_step_count": len(audits),
        "actual_below_floor_count": below_floor,
        "actual_crossing_count": crossings,
        "minimum_actual_margin_rad": minimum,
        "joint_limit_violation_step_count": joint_limit_steps,
    }


def _paired_bootstrap_mean(
    values: Sequence[float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            "paired bootstrap requires at least one finite value"
        )
    rng = np.random.default_rng(seed)
    estimates = np.empty(resamples, dtype=np.float64)
    chunk_size = 10_000
    for start in range(0, resamples, chunk_size):
        stop = min(start + chunk_size, resamples)
        indices = rng.integers(
            0,
            array.size,
            size=(stop - start, array.size),
        )
        estimates[start:stop] = np.mean(array[indices], axis=1)
    return {
        "estimate": float(np.mean(array)),
        "lower": float(np.percentile(estimates, 2.5)),
        "upper": float(np.percentile(estimates, 97.5)),
        "unit_count": int(array.size),
        "resamples": resamples,
        "seed": seed,
        "method": "paired_episode_percentile_bootstrap",
    }


def _unknown_or_deadlock(episode: Mapping[str, Any]) -> bool:
    decision = str(episode["decision"])
    return bool(
        "unknown" in decision
        or "deadlock" in decision
    )


def build_summary(
    *,
    protocol_path: Path = PROTOCOL_PATH,
    created_at: str = CREATED_AT,
) -> dict[str, Any]:
    protocol = load_json_object(protocol_path)
    if (
        protocol.get("schema") != shadow_clean.PROTOCOL_SCHEMA
        or protocol.get("status") != shadow_clean.AUTHORIZED_STATUS
    ):
        raise PredictiveVirtualBrakeV14ShadowTerminalError(
            "shadow-only protocol is not the authorized frozen design"
        )
    bindings_valid, binding_rows = _verify_required_bindings(protocol)
    full_protocol = load_json_object(FULL_PROTOCOL_PATH)
    full_evidence = load_json_object(FULL_EVIDENCE_PATH)
    shadow_root = _bound_path(str(protocol["fresh_output_root"]))
    shadow_evidence_path = shadow_root / "pilot_evidence.json"
    shadow_manifest_path = shadow_root / "run_manifest.json"
    shadow_checksums_path = shadow_root / "SHA256SUMS"
    for required in (
        shadow_evidence_path,
        shadow_manifest_path,
        shadow_checksums_path,
    ):
        if not required.is_file():
            raise PredictiveVirtualBrakeV14ShadowTerminalError(
                f"shadow-only terminal artifact is absent: {required}"
            )
    shadow_evidence = load_json_object(shadow_evidence_path)
    shadow_manifest = load_json_object(shadow_manifest_path)

    schedule_identity = all(
        protocol.get(key) == full_protocol.get(key)
        for key in (
            "schedule",
            "schedule_sha256",
            "workloads",
            "episode_constants",
            "victim",
        )
    )
    schedule = {
        str(row["episode_id"]): row
        for row in protocol["schedule"]
    }
    full_artifacts = _episode_map(full_evidence)
    shadow_artifacts = _episode_map(shadow_evidence)
    episode_identity = (
        set(schedule)
        == set(full_artifacts)
        == set(shadow_artifacts)
    )

    aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    per_episode = []
    full_hash_matches = 0
    shadow_hash_matches = 0
    identity = Counter()
    maximum_pre_divergence_margin_error = 0.0
    maximum_disabled_margin_error = 0.0
    binary_units: dict[str, dict[str, list[dict[str, Any]]]] = {
        arm: {
            "task_success": [],
            "unknown_or_deadlock": [],
        }
        for arm in sorted(_L2_ARMS)
    }
    exposure_differences: dict[str, dict[str, list[float]]] = {
        arm: {
            "actual_below_floor_count": [],
            "actual_crossing_count": [],
        }
        for arm in sorted(_L2_ARMS)
    }

    if episode_identity:
        for episode_id, spec in schedule.items():
            arm = str(spec["arm"])
            l2_enabled = arm in _L2_ARMS
            full_episode, full_hash_match = _load_episode(
                full_artifacts[episode_id]
            )
            shadow_episode, shadow_hash_match = _load_episode(
                shadow_artifacts[episode_id]
            )
            full_hash_matches += int(full_hash_match)
            shadow_hash_matches += int(shadow_hash_match)
            full_audits = _policy_audits(full_episode)
            shadow_audits = _policy_audits(shadow_episode)
            full_exposure = _exposure(
                full_audits,
                floor=float(
                    protocol["episode_constants"][
                        "predictive_virtual_brake_safe_margin_floor_rad"
                    ]
                )
                if "predictive_virtual_brake_safe_margin_floor_rad"
                in protocol["episode_constants"]
                else 0.15,
            )
            shadow_exposure = _exposure(
                shadow_audits,
                floor=float(
                    protocol["episode_constants"].get(
                        "predictive_virtual_brake_safe_margin_floor_rad",
                        0.15,
                    )
                ),
            )
            for prefix, episode, exposure in (
                ("full", full_episode, full_exposure),
                ("shadow", shadow_episode, shadow_exposure),
            ):
                aggregate[arm][f"{prefix}_episode_count"] += 1
                aggregate[arm][f"{prefix}_task_success_count"] += int(
                    episode["task_success"]
                )
                aggregate[arm][
                    f"{prefix}_strict_success_no_cost_count"
                ] += int(episode["strict_success_no_cost"])
                aggregate[arm][
                    f"{prefix}_unsafe_cost_or_collision_count"
                ] += int(episode["unsafe_cost_or_collision"])
                aggregate[arm][
                    f"{prefix}_unknown_or_deadlock_count"
                ] += int(_unknown_or_deadlock(episode))
                for field in (
                    "policy_step_count",
                    "actual_below_floor_count",
                    "actual_crossing_count",
                ):
                    aggregate[arm][f"{prefix}_{field}"] += int(
                        exposure[field]
                    )

            first_trigger = next(
                (
                    index
                    for index, audit in enumerate(full_audits)
                    if audit.get("triggered") is True
                ),
                None,
            )
            if l2_enabled:
                identity["l2_episode_count"] += 1
                identity["full_trigger_episode_count"] += int(
                    first_trigger is not None
                )
                identity["full_trigger_count"] += sum(
                    audit.get("triggered") is True
                    for audit in full_audits
                )
                identity["full_intervention_count"] += sum(
                    audit.get("intervened") is True
                    for audit in full_audits
                )
                identity["full_deadlock_count"] += sum(
                    audit.get("deadlock") is True
                    for audit in full_audits
                )
                compare_count = (
                    len(full_audits)
                    if first_trigger is None
                    else first_trigger + 1
                )
                if len(shadow_audits) < compare_count:
                    identity[
                        "pre_divergence_trace_length_mismatch_count"
                    ] += 1
                    compare_count = len(shadow_audits)
                identity[
                    "pre_divergence_compared_policy_step_count"
                ] += compare_count
                for index in range(compare_count):
                    full_audit = full_audits[index]
                    shadow_audit = shadow_audits[index]
                    identity[
                        "pre_divergence_action_digest_mismatch_count"
                    ] += int(
                        full_audit.get("source_action_digest")
                        != shadow_audit.get("source_action_digest")
                    )
                    for field in (
                        "current_joint_side_margins",
                        "unguarded_predicted_joint_side_margins",
                    ):
                        errors = np.abs(
                            _matrix(full_audit, field)
                            - _matrix(shadow_audit, field)
                        )
                        maximum_pre_divergence_margin_error = max(
                            maximum_pre_divergence_margin_error,
                            float(np.max(errors)),
                        )
                    identity[
                        "pre_divergence_risk_identity_mismatch_count"
                    ] += int(
                        _risk_identity(full_audit)
                        != _risk_identity(shadow_audit)
                    )
                    if (
                        first_trigger is None
                        or index < first_trigger
                    ):
                        errors = np.abs(
                            _matrix(
                                full_audit,
                                "actual_joint_side_margins",
                            )
                            - _matrix(
                                shadow_audit,
                                "actual_joint_side_margins",
                            )
                        )
                        maximum_pre_divergence_margin_error = max(
                            maximum_pre_divergence_margin_error,
                            float(np.max(errors)),
                        )
                if first_trigger is None:
                    identity["no_trigger_l2_episode_count"] += 1
                    identity[
                        "no_trigger_l2_trace_length_mismatch_count"
                    ] += int(
                        len(full_audits) != len(shadow_audits)
                    )
                    identity[
                        "no_trigger_l2_outcome_mismatch_count"
                    ] += sum(
                        full_episode[field] != shadow_episode[field]
                        for field in _OUTCOME_FIELDS
                    )
                for outcome_name, accessor in (
                    (
                        "task_success",
                        lambda value: bool(value["task_success"]),
                    ),
                    (
                        "unknown_or_deadlock",
                        _unknown_or_deadlock,
                    ),
                ):
                    binary_units[arm][outcome_name].append(
                        {
                            "base_pair_id": episode_id,
                            "outcomes": {
                                "full": accessor(full_episode),
                                "shadow": accessor(shadow_episode),
                            },
                        }
                    )
                for field in (
                    "actual_below_floor_count",
                    "actual_crossing_count",
                ):
                    exposure_differences[arm][field].append(
                        float(full_exposure[field])
                        - float(shadow_exposure[field])
                    )
            else:
                identity["disabled_episode_count"] += 1
                identity[
                    "disabled_trace_length_mismatch_count"
                ] += int(
                    len(full_audits) != len(shadow_audits)
                )
                identity["disabled_outcome_mismatch_count"] += sum(
                    full_episode[field] != shadow_episode[field]
                    for field in _OUTCOME_FIELDS
                )
                for full_audit, shadow_audit in zip(
                    full_audits,
                    shadow_audits,
                ):
                    identity[
                        "disabled_action_digest_mismatch_count"
                    ] += int(
                        full_audit.get("source_action_digest")
                        != shadow_audit.get("source_action_digest")
                    )
                    errors = np.abs(
                        _matrix(
                            full_audit,
                            "actual_joint_side_margins",
                        )
                        - _matrix(
                            shadow_audit,
                            "actual_joint_side_margins",
                        )
                    )
                    maximum_disabled_margin_error = max(
                        maximum_disabled_margin_error,
                        float(np.max(errors)),
                    )

            per_episode.append(
                {
                    "episode_id": episode_id,
                    "base_pair_id": str(spec["base_pair_id"]),
                    "arm": arm,
                    "full": {
                        **full_exposure,
                        **{
                            field: full_episode[field]
                            for field in _OUTCOME_FIELDS
                        },
                    },
                    "shadow": {
                        **shadow_exposure,
                        **{
                            field: shadow_episode[field]
                            for field in _OUTCOME_FIELDS
                        },
                    },
                    "first_full_trigger_policy_index": first_trigger,
                }
            )

    analysis = protocol["analysis"]
    resamples = int(analysis["bootstrap_resamples"])
    seed_base = int(analysis["bootstrap_seed_base"]) + 500
    causal_estimates: dict[str, Any] = {}
    for arm_index, arm in enumerate(sorted(_L2_ARMS)):
        causal_estimates[arm] = {
            "full_minus_shadow_task_success": (
                cluster_bootstrap_paired_difference(
                    binary_units[arm]["task_success"],
                    treatment="full",
                    control="shadow",
                    resamples=resamples,
                    seed=seed_base + arm_index * 10,
                )
            ),
            "full_minus_shadow_unknown_or_deadlock": (
                cluster_bootstrap_paired_difference(
                    binary_units[arm]["unknown_or_deadlock"],
                    treatment="full",
                    control="shadow",
                    resamples=resamples,
                    seed=seed_base + arm_index * 10 + 1,
                )
            ),
            "full_minus_shadow_actual_below_floor_count": (
                _paired_bootstrap_mean(
                    exposure_differences[arm][
                        "actual_below_floor_count"
                    ],
                    resamples=resamples,
                    seed=seed_base + arm_index * 10 + 2,
                )
            ),
            "full_minus_shadow_actual_crossing_count": (
                _paired_bootstrap_mean(
                    exposure_differences[arm][
                        "actual_crossing_count"
                    ],
                    resamples=resamples,
                    seed=seed_base + arm_index * 10 + 3,
                )
            ),
        }

    expected_episode_count = int(
        protocol["shadow_only_gates"]["expected_episode_count"]
    )
    pre_tolerance = float(
        protocol["shadow_only_gates"][
            "pre_divergence_margin_tolerance_rad"
        ]
    )
    disabled_tolerance = float(
        protocol["shadow_only_gates"][
            "disabled_arm_margin_tolerance_rad"
        ]
    )
    required_shadow_gates = (
        "shadow_only_metadata_matches",
        "shadow_only_all_policy_steps_audited",
        "shadow_only_l2_contract",
        "shadow_only_disabled_arm_contract",
        "shadow_only_zero_intervention_and_deadlock",
        "shadow_restore_identity",
        "exact_action_identity",
    )
    gate_results = {
        "required_bindings_match": bindings_valid,
        "full_and_shadow_schedule_identity": schedule_identity,
        "episode_identity_and_count": (
            episode_identity
            and len(schedule) == expected_episode_count
        ),
        "full_episode_artifact_checksums": (
            full_hash_matches == expected_episode_count
        ),
        "shadow_episode_artifact_checksums": (
            shadow_hash_matches == expected_episode_count
        ),
        "shadow_manifest_complete": (
            shadow_manifest.get("status") == "complete"
            and shadow_manifest.get("classification")
            == protocol["complete_classification"]
        ),
        "shadow_evidence_contract": all(
            shadow_evidence.get("gate_results", {}).get(name) is True
            for name in required_shadow_gates
        ),
        "full_trigger_support_present": (
            identity["full_trigger_count"]
            >= int(
                protocol["shadow_only_gates"][
                    "full_brake_trigger_count_minimum"
                ]
            )
        ),
        "pre_divergence_trace_coverage": (
            identity[
                "pre_divergence_trace_length_mismatch_count"
            ]
            == 0
        ),
        "pre_divergence_action_identity": (
            identity[
                "pre_divergence_action_digest_mismatch_count"
            ]
            == 0
        ),
        "pre_divergence_risk_identity": (
            identity[
                "pre_divergence_risk_identity_mismatch_count"
            ]
            == 0
        ),
        "pre_divergence_margin_identity": (
            maximum_pre_divergence_margin_error <= pre_tolerance
        ),
        "no_trigger_l2_deterministic_identity": (
            identity[
                "no_trigger_l2_trace_length_mismatch_count"
            ]
            == 0
            and identity[
                "no_trigger_l2_outcome_mismatch_count"
            ]
            == 0
        ),
        "disabled_arm_deterministic_identity": (
            identity["disabled_trace_length_mismatch_count"] == 0
            and identity["disabled_outcome_mismatch_count"] == 0
            and identity[
                "disabled_action_digest_mismatch_count"
            ]
            == 0
            and maximum_disabled_margin_error <= disabled_tolerance
        ),
    }
    identity_complete = all(gate_results.values())
    l2_full_crossings = sum(
        aggregate[arm]["full_actual_crossing_count"]
        for arm in _L2_ARMS
    )
    l2_shadow_crossings = sum(
        aggregate[arm]["shadow_actual_crossing_count"]
        for arm in _L2_ARMS
    )
    l2_full_below_floor = sum(
        aggregate[arm]["full_actual_below_floor_count"]
        for arm in _L2_ARMS
    )
    l2_shadow_below_floor = sum(
        aggregate[arm]["shadow_actual_below_floor_count"]
        for arm in _L2_ARMS
    )
    causal_safety_signal = bool(
        identity_complete
        and (
            l2_shadow_crossings > l2_full_crossings
            or l2_shadow_below_floor > l2_full_below_floor
        )
    )
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "classification": (
            COMPLETE_CLASSIFICATION
            if identity_complete
            else NONPASS_CLASSIFICATION
        ),
        "causal_identity_complete": identity_complete,
        "causal_safety_signal_observed": causal_safety_signal,
        "confirmatory_claim_authorized": False,
        "attacked_stage_authorized": False,
        "episode_count": len(schedule),
        "paired_workload_count": len(
            {str(row["base_pair_id"]) for row in protocol["schedule"]}
        ),
        "gate_results": gate_results,
        "failed_gates": sorted(
            name
            for name, passed in gate_results.items()
            if passed is not True
        ),
        "identity": {
            **dict(sorted(identity.items())),
            "maximum_pre_divergence_margin_error_rad": (
                maximum_pre_divergence_margin_error
            ),
            "maximum_disabled_margin_error_rad": (
                maximum_disabled_margin_error
            ),
        },
        "by_arm": {
            arm: dict(sorted(values.items()))
            for arm, values in sorted(aggregate.items())
        },
        "causal_estimates": causal_estimates,
        "l2_safety_exposure": {
            "full_actual_below_floor_count": l2_full_below_floor,
            "shadow_actual_below_floor_count": (
                l2_shadow_below_floor
            ),
            "full_actual_crossing_count": l2_full_crossings,
            "shadow_actual_crossing_count": l2_shadow_crossings,
            "full_minus_shadow_actual_below_floor_count": (
                l2_full_below_floor - l2_shadow_below_floor
            ),
            "full_minus_shadow_actual_crossing_count": (
                l2_full_crossings - l2_shadow_crossings
            ),
        },
        "per_episode": per_episode,
        "bindings": binding_rows,
        "terminal": {
            "protocol_path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "protocol_sha256": file_sha256(protocol_path),
            "full_protocol_path": FULL_PROTOCOL_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "full_protocol_sha256": file_sha256(FULL_PROTOCOL_PATH),
            "full_evidence_path": FULL_EVIDENCE_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "full_evidence_sha256": file_sha256(FULL_EVIDENCE_PATH),
            "shadow_evidence_path": shadow_evidence_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "shadow_evidence_sha256": file_sha256(
                shadow_evidence_path
            ),
            "shadow_manifest_path": shadow_manifest_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "shadow_manifest_sha256": file_sha256(
                shadow_manifest_path
            ),
            "shadow_checksums_path": shadow_checksums_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "shadow_checksums_sha256": file_sha256(
                shadow_checksums_path
            ),
        },
        "interpretation": (
            "This outcome-disclosed development comparison supports a "
            "causal brake-authority interpretation only when the frozen "
            "identity gates pass. Safety exposure and task/availability "
            "differences remain descriptive and require a new outcome-blind "
            "population for confirmation."
        ),
        "claim_boundary": str(protocol["claim_boundary"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    summary = build_summary(
        protocol_path=args.protocol.resolve(),
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        ),
    )
    text = canonical_text(summary)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PredictiveVirtualBrakeV14ShadowTerminalError(
                f"shadow-only terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
