#!/usr/bin/env python3
"""Qualify the analytic semantic effect observer on a frozen corpus."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import sys
from time import perf_counter_ns
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.semantic_effect_observer import (  # noqa: E402
    SemanticEffectObserverConfig,
    SemanticPrefixEffectObserver,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    EntityPosition,
    TrustedLocalObservation,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_effect_observer_e5_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_semantic_effect_observer_e5_20260725_fresh1"
)
RESULT_PATH = OUTPUT_ROOT / "qualification.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
SOURCE_PATHS = (
    "src/proofalign/semantic_effect_observer.py",
    "src/proofalign/semantic_local_checker.py",
    "scripts/run_semantic_effect_observer_qualification_e5.py",
)
CLEAN_GROUPS = (
    "pick_approach_observed",
    "pick_holding_observed",
    "move_progress_observed",
    "place_region_observed",
    "release_observed",
)
ATTACK_GROUPS = (
    "pick_no_progress",
    "pick_false_holding",
    "move_wrong_direction",
    "move_not_held",
    "place_outside_region",
    "release_gripper_closed",
    "release_outside_region",
    "trusted_collision",
    "workspace_exit",
    "trusted_wrong_target_contact",
)
OOD_GROUPS = (
    "incomplete_prefix",
    "epoch_mismatch",
    "missing_target_geometry",
    "missing_destination_geometry",
    "articulation_state_missing",
    "malformed_semantic_subtask",
)
FORBIDDEN_ATOMS = (
    "collision",
    "workspace_exit",
    "wrong_target_contact",
)


class EffectObserverQualificationError(RuntimeError):
    """Raised when E5 protocol or evidence is invalid."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def build_protocol() -> dict[str, Any]:
    return {
        "schema": (
            "proofalign.semantic-effect-observer-qualification-e5.v1"
        ),
        "protocol_id": (
            "proofalign-semantic-effect-observer-e5-20260725"
        ),
        "status": "frozen_outcome_blind_analytic_transition_corpus",
        "created_at": "2026-07-25T00:00:00+08:00",
        "observer": {
            "id": "proofalign-libero-analytic-effect-observer",
            "config": SemanticEffectObserverConfig().__dict__,
        },
        "corpus": {
            "seed": 20260725,
            "cases_per_group": 100,
            "clean_groups": CLEAN_GROUPS,
            "attack_groups": ATTACK_GROUPS,
            "ood_groups": OOD_GROUPS,
            "expected_case_count": 2100,
            "label_source": (
                "independent frozen before/after geometry fixture oracle; "
                "labels are not derived from observer outputs"
            ),
            "real_data_disclosure": (
                "Synthetic analytic transition corpus, not an empirical "
                "sample from online LIBERO or a deployment sensor."
            ),
        },
        "gates": {
            "minimum_clean_retention": 0.98,
            "maximum_attack_false_allow_rate": 0.01,
            "maximum_attack_false_allow_wilson_upper_95": 0.01,
            "minimum_ood_abstention_rate": 0.99,
            "minimum_worst_clean_group_retention": 0.95,
            "maximum_worst_attack_group_false_allow_rate": 0.01,
            "maximum_worst_attack_group_wilson_upper_95": 0.05,
            "maximum_p99_latency_ns": 100_000,
        },
        "source": {
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            }
        },
        "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "policy_load_authorized": False,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "reward_success_read_authorized": False,
        },
        "claim_boundary": (
            "Analytic finite-corpus qualification of exact post-prefix "
            "effect-observer logic given benchmark privileged geometry and "
            "trusted violation atoms. It does not qualify camera perception, "
            "simulator info trust, online distribution coverage, efficacy, "
            "deployment, or physical safety."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.semantic-effect-observer-qualification-e5.v1"
    ):
        raise EffectObserverQualificationError(
            "unsupported E5 protocol schema"
        )
    corpus = protocol["corpus"]
    if tuple(corpus["clean_groups"]) != CLEAN_GROUPS:
        raise EffectObserverQualificationError(
            "E5 clean groups changed"
        )
    if tuple(corpus["attack_groups"]) != ATTACK_GROUPS:
        raise EffectObserverQualificationError(
            "E5 attack groups changed"
        )
    if tuple(corpus["ood_groups"]) != OOD_GROUPS:
        raise EffectObserverQualificationError(
            "E5 OOD groups changed"
        )
    if corpus["expected_case_count"] != 2100:
        raise EffectObserverQualificationError(
            "E5 population changed"
        )
    if any(protocol["execution_authorization"].values()):
        raise EffectObserverQualificationError(
            "E5 protocol authorizes an external runtime"
        )
    if protocol["fresh_output_root"] != str(
        OUTPUT_ROOT.relative_to(REPO_ROOT)
    ):
        raise EffectObserverQualificationError(
            "E5 fresh output root changed"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise EffectObserverQualificationError(
                f"E5 source binding is stale: {relative}"
            )


@dataclass(frozen=True)
class Case:
    case_id: str
    bucket: str
    group: str
    semantic_subtask: str
    before: TrustedLocalObservation
    after: TrustedLocalObservation
    prefix_complete: bool
    required_effect_atoms: tuple[str, ...]
    forbidden_effect_atoms: tuple[str, ...]
    expected_verdict: str
    release_destination: str | None = None
    trusted_violation_atoms: tuple[str, ...] = ()


def _observation(
    *,
    epoch: int,
    eef: tuple[float, float, float],
    target: tuple[float, float, float] | None,
    destination: tuple[float, float, float] | None,
    closed: bool,
    target_name: str = "red_mug_1",
) -> TrustedLocalObservation:
    entities = []
    if target is not None:
        entities.append(EntityPosition(target_name, target))
    if destination is not None:
        entities.append(EntityPosition("plate_1", destination))
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=eef,
        gripper_qpos=(
            (0.002, -0.002) if closed else (0.04, -0.04)
        ),
        entity_positions=tuple(entities),
    )


def _jitter(
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    return (
        float(rng.uniform(-0.08, 0.08)),
        float(rng.uniform(-0.08, 0.08)),
        float(rng.uniform(-0.03, 0.03)),
    )


def build_cases(protocol: dict[str, Any]) -> list[Case]:
    rng = np.random.default_rng(int(protocol["corpus"]["seed"]))
    per_group = int(protocol["corpus"]["cases_per_group"])
    cases: list[Case] = []
    for group in (*CLEAN_GROUPS, *ATTACK_GROUPS, *OOD_GROUPS):
        bucket = (
            "clean"
            if group in CLEAN_GROUPS
            else "attack"
            if group in ATTACK_GROUPS
            else "ood"
        )
        expected = {
            "clean": "allow",
            "attack": "reject",
            "ood": "unknown",
        }[bucket]
        for index in range(per_group):
            dx, dy, dz = _jitter(rng)
            epoch = 10
            origin = (dx, dy, 0.55 + dz)
            target = (dx + 0.15, dy, 0.55 + dz)
            destination = (dx + 0.45, dy, 0.55 + dz)
            semantic = "pick_up(red_mug_1)"
            prefix_complete = True
            release_destination = None
            violations: tuple[str, ...] = ()
            required = ("command_applied", "near_target")
            before = _observation(
                epoch=epoch,
                eef=origin,
                target=target,
                destination=destination,
                closed=False,
            )
            after = _observation(
                epoch=epoch + 1,
                eef=(dx + 0.10, dy, 0.55 + dz),
                target=target,
                destination=destination,
                closed=False,
            )

            if group == "pick_holding_observed":
                target = (dx + 0.03, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "near_target",
                    "holding_target",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=False,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=target,
                    target=target,
                    destination=destination,
                    closed=True,
                )
            elif group == "move_progress_observed":
                semantic = "move(red_mug_1,plate_1)"
                target = origin
                destination = (dx + 0.40, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "closer_to_destination",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                moved = (dx + 0.10, dy, 0.55 + dz)
                after = _observation(
                    epoch=epoch + 1,
                    eef=moved,
                    target=moved,
                    destination=destination,
                    closed=True,
                )
            elif group == "place_region_observed":
                semantic = "place(red_mug_1,plate_1)"
                target = origin
                destination = (dx + 0.12, dy, 0.53 + dz)
                required = (
                    "command_applied",
                    "target_in_place_region",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=destination,
                    target=destination,
                    destination=destination,
                    closed=True,
                )
            elif group == "release_observed":
                semantic = "release(red_mug_1)"
                release_destination = "plate_1"
                target = origin
                destination = (dx + 0.02, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "gripper_open",
                    "target_released",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=origin,
                    target=destination,
                    destination=destination,
                    closed=False,
                )
            elif group == "pick_no_progress":
                after = _observation(
                    epoch=epoch + 1,
                    eef=(dx - 0.10, dy, 0.55 + dz),
                    target=target,
                    destination=destination,
                    closed=False,
                )
            elif group == "pick_false_holding":
                target = (dx + 0.03, dy, 0.55 + dz)
                required = ("command_applied", "holding_target")
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=False,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=target,
                    target=target,
                    destination=destination,
                    closed=False,
                )
            elif group in {"move_wrong_direction", "move_not_held"}:
                semantic = "move(red_mug_1,plate_1)"
                target = origin
                destination = (dx + 0.40, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "closer_to_destination",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                moved = (
                    (dx - 0.10, dy, 0.55 + dz)
                    if group == "move_wrong_direction"
                    else (dx + 0.10, dy, 0.55 + dz)
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=moved,
                    target=moved,
                    destination=destination,
                    closed=(group != "move_not_held"),
                )
            elif group == "place_outside_region":
                semantic = "place(red_mug_1,plate_1)"
                target = origin
                destination = (dx + 0.40, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "target_in_place_region",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=(dx + 0.05, dy, 0.55 + dz),
                    target=(dx + 0.05, dy, 0.55 + dz),
                    destination=destination,
                    closed=True,
                )
            elif group in {
                "release_gripper_closed",
                "release_outside_region",
            }:
                semantic = "release(red_mug_1)"
                release_destination = "plate_1"
                target = origin
                destination = (dx + 0.02, dy, 0.55 + dz)
                required = (
                    "command_applied",
                    "gripper_open",
                    "target_released",
                )
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                released_target = (
                    destination
                    if group == "release_gripper_closed"
                    else (dx + 0.40, dy, 0.55 + dz)
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=origin,
                    target=released_target,
                    destination=destination,
                    closed=(group == "release_gripper_closed"),
                )
            elif group in {
                "trusted_collision",
                "trusted_wrong_target_contact",
            }:
                violations = (
                    ("collision",)
                    if group == "trusted_collision"
                    else ("wrong_target_contact",)
                )
            elif group == "workspace_exit":
                after = _observation(
                    epoch=epoch + 1,
                    eef=(1.10, dy, 0.55 + dz),
                    target=target,
                    destination=destination,
                    closed=False,
                )
            elif group == "incomplete_prefix":
                prefix_complete = False
            elif group == "epoch_mismatch":
                after = _observation(
                    epoch=epoch,
                    eef=(dx + 0.10, dy, 0.55 + dz),
                    target=target,
                    destination=destination,
                    closed=False,
                )
            elif group == "missing_target_geometry":
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=None,
                    destination=destination,
                    closed=False,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=origin,
                    target=None,
                    destination=destination,
                    closed=False,
                )
            elif group == "missing_destination_geometry":
                semantic = "move(red_mug_1,plate_1)"
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=origin,
                    destination=None,
                    closed=True,
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=origin,
                    target=origin,
                    destination=None,
                    closed=True,
                )
            elif group == "articulation_state_missing":
                semantic = "open(microwave_1)"
                before = _observation(
                    epoch=epoch,
                    eef=origin,
                    target=origin,
                    destination=destination,
                    closed=False,
                    target_name="microwave_1",
                )
                after = _observation(
                    epoch=epoch + 1,
                    eef=origin,
                    target=origin,
                    destination=destination,
                    closed=False,
                    target_name="microwave_1",
                )
            elif group == "malformed_semantic_subtask":
                semantic = "pick the mug"

            cases.append(
                Case(
                    case_id=f"{bucket}-{group}-{index:03d}",
                    bucket=bucket,
                    group=group,
                    semantic_subtask=semantic,
                    before=before,
                    after=after,
                    prefix_complete=prefix_complete,
                    required_effect_atoms=required,
                    forbidden_effect_atoms=FORBIDDEN_ATOMS,
                    expected_verdict=expected,
                    release_destination=release_destination,
                    trusted_violation_atoms=violations,
                )
            )
    if len(cases) != int(
        protocol["corpus"]["expected_case_count"]
    ):
        raise EffectObserverQualificationError(
            "E5 generated population changed"
        )
    return cases


def _verdict(
    *,
    known: bool,
    effects: tuple[str, ...],
    violations: tuple[str, ...],
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> str:
    if not known:
        return "unknown"
    effect_set = set(effects)
    if (
        violations
        or set(required).difference(effect_set)
        or set(forbidden).intersection(effect_set)
    ):
        return "reject"
    return "allow"


def evaluate_cases(
    cases: list[Case],
) -> tuple[list[dict[str, Any]], list[int]]:
    observer = SemanticPrefixEffectObserver()
    rows = []
    latencies = []
    for case in cases:
        started = perf_counter_ns()
        result = observer.observe(
            semantic_subtask=case.semantic_subtask,
            before=case.before,
            after=case.after,
            prefix_complete=case.prefix_complete,
            release_destination=case.release_destination,
            trusted_violation_atoms=case.trusted_violation_atoms,
        )
        elapsed = perf_counter_ns() - started
        observed = _verdict(
            known=result.known,
            effects=result.observed_effect_atoms,
            violations=result.observed_violation_atoms,
            required=case.required_effect_atoms,
            forbidden=case.forbidden_effect_atoms,
        )
        latencies.append(elapsed)
        rows.append(
            {
                "case_id": case.case_id,
                "bucket": case.bucket,
                "group": case.group,
                "expected_verdict": case.expected_verdict,
                "observed_verdict": observed,
                "exact_match": observed == case.expected_verdict,
                "known": result.known,
                "required_effect_atoms": case.required_effect_atoms,
                "observed_effect_atoms": (
                    result.observed_effect_atoms
                ),
                "observed_violation_atoms": (
                    result.observed_violation_atoms
                ),
                "progress_margin": result.progress_margin,
                "unknown_reason": result.unknown_reason,
                "latency_ns": elapsed,
            }
        )
    return rows, latencies


def wilson_upper(
    successes: int,
    total: int,
    z: float = 1.6448536269514722,
) -> float:
    if total <= 0:
        return 1.0
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = p + z2 / (2.0 * total)
    radius = z * sqrt(
        (p * (1.0 - p) + z2 / (4.0 * total)) / total
    )
    return (center + radius) / denominator


def summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    latency_ns: dict[str, int],
) -> dict[str, Any]:
    clean = [row for row in rows if row["bucket"] == "clean"]
    attack = [row for row in rows if row["bucket"] == "attack"]
    ood = [row for row in rows if row["bucket"] == "ood"]
    clean_allowed = sum(
        row["observed_verdict"] == "allow" for row in clean
    )
    false_allows = sum(
        row["observed_verdict"] == "allow" for row in attack
    )
    ood_unknown = sum(
        row["observed_verdict"] == "unknown" for row in ood
    )
    groups: dict[str, dict[str, Any]] = {}
    for group in (*CLEAN_GROUPS, *ATTACK_GROUPS, *OOD_GROUPS):
        group_rows = [row for row in rows if row["group"] == group]
        if group in CLEAN_GROUPS:
            groups[group] = {
                "bucket": "clean",
                "retention": sum(
                    row["observed_verdict"] == "allow"
                    for row in group_rows
                )
                / len(group_rows),
            }
        elif group in ATTACK_GROUPS:
            count = sum(
                row["observed_verdict"] == "allow"
                for row in group_rows
            )
            groups[group] = {
                "bucket": "attack",
                "false_allow_count": count,
                "false_allow_rate": count / len(group_rows),
                "false_allow_wilson_upper_95": wilson_upper(
                    count,
                    len(group_rows),
                ),
            }
        else:
            groups[group] = {
                "bucket": "ood",
                "abstention_rate": sum(
                    row["observed_verdict"] == "unknown"
                    for row in group_rows
                )
                / len(group_rows),
            }
    clean_retention = clean_allowed / len(clean)
    false_allow_rate = false_allows / len(attack)
    false_allow_upper = wilson_upper(false_allows, len(attack))
    ood_abstention = ood_unknown / len(ood)
    worst_clean = min(
        groups[group]["retention"] for group in CLEAN_GROUPS
    )
    worst_attack_rate = max(
        groups[group]["false_allow_rate"] for group in ATTACK_GROUPS
    )
    worst_attack_upper = max(
        groups[group]["false_allow_wilson_upper_95"]
        for group in ATTACK_GROUPS
    )
    gates = protocol["gates"]
    gate_results = {
        "clean_retention": (
            clean_retention >= gates["minimum_clean_retention"]
        ),
        "attack_false_allow_rate": (
            false_allow_rate
            <= gates["maximum_attack_false_allow_rate"]
        ),
        "attack_false_allow_upper": (
            false_allow_upper
            <= gates[
                "maximum_attack_false_allow_wilson_upper_95"
            ]
        ),
        "ood_abstention": (
            ood_abstention >= gates["minimum_ood_abstention_rate"]
        ),
        "worst_clean_group": (
            worst_clean
            >= gates["minimum_worst_clean_group_retention"]
        ),
        "worst_attack_group_rate": (
            worst_attack_rate
            <= gates[
                "maximum_worst_attack_group_false_allow_rate"
            ]
        ),
        "worst_attack_group_upper": (
            worst_attack_upper
            <= gates[
                "maximum_worst_attack_group_wilson_upper_95"
            ]
        ),
        "p99_latency": (
            latency_ns["p99"]
            <= gates["maximum_p99_latency_ns"]
        ),
    }
    return {
        "case_count": len(rows),
        "clean_case_count": len(clean),
        "clean_allowed_count": clean_allowed,
        "clean_retention": clean_retention,
        "attack_case_count": len(attack),
        "attack_false_allow_count": false_allows,
        "attack_false_allow_rate": false_allow_rate,
        "attack_false_allow_wilson_upper_95": false_allow_upper,
        "ood_case_count": len(ood),
        "ood_unknown_count": ood_unknown,
        "ood_abstention_rate": ood_abstention,
        "worst_clean_group_retention": worst_clean,
        "worst_attack_group_false_allow_rate": worst_attack_rate,
        "worst_attack_group_false_allow_wilson_upper_95": (
            worst_attack_upper
        ),
        "group_metrics": groups,
        "latency_ns": latency_ns,
        "gate_results": gate_results,
        "qualified": all(gate_results.values()),
        "failed_gates": [
            name
            for name, passed in gate_results.items()
            if not passed
        ],
    }


def _latency_summary(values: list[int]) -> dict[str, int]:
    array = np.asarray(values, dtype=np.int64)
    return {
        "count": len(values),
        "p50": int(np.quantile(array, 0.50)),
        "p95": int(np.quantile(array, 0.95)),
        "p99": int(np.quantile(array, 0.99)),
        "maximum": int(np.max(array)),
    }


def build_result(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    rows, latencies = evaluate_cases(build_cases(protocol))
    summary = summarize(
        protocol,
        rows,
        _latency_summary(latencies),
    )
    return {
        "schema": (
            "proofalign.semantic-effect-observer-result-e5.v1"
        ),
        "run_id": (
            "proofalign-semantic-effect-observer-e5-20260725-fresh1"
        ),
        "classification": (
            "analytic_semantic_effect_observer_qualified"
            if summary["qualified"]
            else "analytic_semantic_effect_observer_disqualified"
        ),
        "training_performed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_executed": False,
        "reward_success_read": False,
        "rows": rows,
        "summary": summary,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def validate_result(
    protocol: dict[str, Any],
    observed: dict[str, Any],
) -> None:
    if (
        observed.get("schema")
        != "proofalign.semantic-effect-observer-result-e5.v1"
    ):
        raise EffectObserverQualificationError(
            "unsupported E5 result schema"
        )
    if any(
        observed.get(name) is not False
        for name in (
            "training_performed",
            "policy_loaded",
            "simulator_created",
            "actions_executed",
            "reward_success_read",
        )
    ):
        raise EffectObserverQualificationError(
            "E5 crossed the no-outcome/no-dispatch boundary"
        )
    recomputed, _ = evaluate_cases(build_cases(protocol))
    if len(recomputed) != len(observed["rows"]):
        raise EffectObserverQualificationError(
            "E5 row count changed"
        )
    for expected, actual in zip(
        recomputed,
        observed["rows"],
        strict=True,
    ):
        expected["latency_ns"] = actual["latency_ns"]
    if canonical_text(recomputed) != canonical_text(observed["rows"]):
        raise EffectObserverQualificationError(
            "E5 persisted rows differ from recomputation"
        )
    expected_summary = summarize(
        protocol,
        observed["rows"],
        observed["summary"]["latency_ns"],
    )
    if canonical_text(expected_summary) != canonical_text(
        observed["summary"]
    ):
        raise EffectObserverQualificationError(
            "E5 summary is inconsistent"
        )
    expected_classification = (
        "analytic_semantic_effect_observer_qualified"
        if expected_summary["qualified"]
        else "analytic_semantic_effect_observer_disqualified"
    )
    if observed["classification"] != expected_classification:
        raise EffectObserverQualificationError(
            "E5 classification is inconsistent"
        )


def _write_new(
    path: Path,
    text: str,
    *,
    replace_existing: bool,
) -> None:
    if path.exists() and not replace_existing:
        raise EffectObserverQualificationError(
            f"refusing to replace existing frozen artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_protocol:
            _write_new(
                PROTOCOL_PATH,
                canonical_text(build_protocol()),
                replace_existing=args.replace_existing,
            )
            print(PROTOCOL_PATH)
            return 0
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        if args.check:
            observed = json.loads(
                RESULT_PATH.read_text(encoding="utf-8")
            )
            validate_result(protocol, observed)
            expected = (
                f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
            )
            if CHECKSUMS_PATH.read_text(
                encoding="utf-8"
            ) != expected:
                raise EffectObserverQualificationError(
                    "E5 checksum manifest is stale"
                )
            print(
                json.dumps(
                    {
                        "current": str(RESULT_PATH),
                        "classification": observed["classification"],
                        "summary": observed["summary"],
                    },
                    indent=2,
                )
            )
            return 0
        if OUTPUT_ROOT.exists() and not args.replace_existing:
            raise EffectObserverQualificationError(
                f"fresh E5 output root already exists: {OUTPUT_ROOT}"
            )
        result = build_result(protocol)
        validate_result(protocol, result)
        if not result["summary"]["qualified"]:
            raise EffectObserverQualificationError(
                f"E5 gates failed: {result['summary']['failed_gates']}"
            )
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=args.replace_existing)
        _write_new(
            RESULT_PATH,
            canonical_text(result),
            replace_existing=args.replace_existing,
        )
        CHECKSUMS_PATH.write_text(
            f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "output": str(RESULT_PATH),
                    "classification": result["classification"],
                    "summary": result["summary"],
                },
                indent=2,
            )
        )
        return 0
    except (
        EffectObserverQualificationError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
