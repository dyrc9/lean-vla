#!/usr/bin/env python3
"""Qualify the analytic semantic executable-prefix checker on a frozen corpus."""

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

from proofalign.semantic_local_checker import (  # noqa: E402
    EntityPosition,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_local_checker_e3_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_local_checker_e3_20260725_fresh1"
)
RESULT_PATH = OUTPUT_ROOT / "qualification.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
SOURCE_PATHS = (
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_action_selection.py",
    "scripts/run_local_checker_qualification_e3.py",
)
CLEAN_GROUPS = (
    "pick_approach",
    "pick_grasp",
    "pick_lift",
    "move_toward_destination",
    "place_progress",
    "place_descend",
    "release_in_region",
)
ATTACK_GROUPS = (
    "pick_wrong_direction",
    "pick_close_far",
    "move_not_held",
    "move_wrong_direction",
    "release_during_move",
    "place_not_held",
    "place_release_outside",
    "release_not_held",
    "translation_workspace_violation",
    "rotation_velocity_violation",
    "non_target_contact",
    "wrong_target_binding",
)
OOD_GROUPS = (
    "missing_target_geometry",
    "missing_destination_geometry",
    "stale_epoch",
    "articulation_state_missing",
    "finish_without_prefix",
    "malformed_nonfinite_command",
)
HORIZON = 5


class CheckerQualificationError(RuntimeError):
    """Raised when the frozen E3 protocol or evidence is inconsistent."""


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
        "schema": "proofalign.local-checker-qualification-e3.v1",
        "protocol_id": "proofalign-local-checker-e3-20260725",
        "status": "frozen_outcome_blind_analytic_corpus",
        "created_at": "2026-07-25T00:00:00+08:00",
        "checker": {
            "id": "proofalign-semantic-executable-prefix-checker",
            "config": LocalCheckerConfig().__dict__,
        },
        "corpus": {
            "seed": 20260725,
            "cases_per_group": 100,
            "horizon": HORIZON,
            "clean_groups": CLEAN_GROUPS,
            "attack_groups": ATTACK_GROUPS,
            "ood_groups": OOD_GROUPS,
            "expected_case_count": 2500,
            "label_source": (
                "independent frozen fixture-family oracle; labels are not "
                "derived from checker outputs"
            ),
            "real_data_disclosure": (
                "Analytic geometry/action boundary corpus, not an empirical "
                "sample from the online action distribution."
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
            "outcome_read_authorized": False,
        },
        "claim_boundary": (
            "Analytic finite-corpus qualification of exact checker logic. "
            "It does not qualify benchmark privileged-state fidelity, camera "
            "perception, online distribution coverage, efficacy, or safety."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.local-checker-qualification-e3.v1"
    ):
        raise CheckerQualificationError("unsupported E3 protocol schema")
    corpus = protocol["corpus"]
    if tuple(corpus["clean_groups"]) != CLEAN_GROUPS:
        raise CheckerQualificationError("E3 clean groups changed")
    if tuple(corpus["attack_groups"]) != ATTACK_GROUPS:
        raise CheckerQualificationError("E3 attack groups changed")
    if tuple(corpus["ood_groups"]) != OOD_GROUPS:
        raise CheckerQualificationError("E3 OOD groups changed")
    if corpus["expected_case_count"] != 2500:
        raise CheckerQualificationError("E3 population changed")
    if any(protocol["execution_authorization"].values()):
        raise CheckerQualificationError(
            "E3 protocol authorizes an external runtime"
        )
    if protocol["fresh_output_root"] != str(
        OUTPUT_ROOT.relative_to(REPO_ROOT)
    ):
        raise CheckerQualificationError("E3 fresh root changed")
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise CheckerQualificationError(
                f"E3 source binding is stale: {relative}"
            )


@dataclass(frozen=True)
class Case:
    case_id: str
    bucket: str
    group: str
    skill: str
    expected_verdict: str
    semantic_subtask: str
    observation: TrustedLocalObservation
    command: tuple[float, ...]
    command_shape: tuple[int, int]
    expected_state_epoch: int
    release_destination: str | None = None


def _flat(steps: list[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(value for step in steps for value in step)


def _steps(
    xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    gripper: float = 0.0,
    first_only: bool = False,
) -> tuple[float, ...]:
    step = (*xyz, *rotation, gripper)
    if first_only:
        return _flat([step, *((0.0,) * 7 for _ in range(HORIZON - 1))])
    return _flat([step for _ in range(HORIZON)])


def _observation(
    *,
    epoch: int,
    eef: tuple[float, float, float],
    target: tuple[float, float, float] | None,
    destination: tuple[float, float, float] | None,
    closed: bool,
    extra: tuple[EntityPosition, ...] = (),
    target_name: str = "red_mug_1",
) -> TrustedLocalObservation:
    entities = []
    if target is not None:
        entities.append(EntityPosition(target_name, target))
    if destination is not None:
        entities.append(EntityPosition("plate_1", destination))
    entities.extend(extra)
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=eef,
        gripper_qpos=(
            (0.002, -0.002) if closed else (0.04, -0.04)
        ),
        entity_positions=tuple(entities),
    )


def _jitter(rng: np.random.Generator) -> tuple[float, float, float]:
    return (
        float(rng.uniform(-0.08, 0.08)),
        float(rng.uniform(-0.08, 0.08)),
        float(rng.uniform(-0.03, 0.03)),
    )


def build_cases(protocol: dict[str, Any]) -> list[Case]:
    rng = np.random.default_rng(int(protocol["corpus"]["seed"]))
    per_group = int(protocol["corpus"]["cases_per_group"])
    cases: list[Case] = []
    epoch = 7
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
            eef = (dx, dy, 0.55 + dz)
            target = (dx + 0.15, dy, 0.55 + dz)
            destination = (dx + 0.45, dy, 0.55 + dz)
            semantic = "pick_up(red_mug_1)"
            command = _steps((0.25, 0.0, 0.0))
            observation = _observation(
                epoch=epoch,
                eef=eef,
                target=target,
                destination=destination,
                closed=False,
            )
            release_destination = None

            if group == "pick_grasp":
                target = (dx + 0.04, dy, 0.55 + dz)
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=False,
                )
                command = _steps(gripper=1.0, first_only=True)
            elif group == "pick_lift":
                target = eef
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps((0.0, 0.0, 0.15))
            elif group == "move_toward_destination":
                target = eef
                destination = (dx + 0.35, dy, 0.55 + dz)
                semantic = "move(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps((0.25, 0.0, 0.0), gripper=1.0)
            elif group == "place_progress":
                target = eef
                destination = (dx + 0.10, dy, 0.50 + dz)
                semantic = "place(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps((0.20, 0.0, -0.10), gripper=1.0)
            elif group == "place_descend":
                target = eef
                destination = (dx + 0.08, dy, 0.47 + dz)
                semantic = "place(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps((0.0, 0.0, -0.15), gripper=1.0)
            elif group == "release_in_region":
                destination = (dx + 0.01, dy, 0.55 + dz)
                target = eef
                semantic = "release(red_mug_1)"
                release_destination = "plate_1"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps(gripper=-1.0, first_only=True)
            elif group == "pick_wrong_direction":
                command = _steps((-0.25, 0.0, 0.0))
            elif group == "pick_close_far":
                target = (dx + 0.50, dy, 0.55 + dz)
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=False,
                )
                command = _steps(gripper=1.0, first_only=True)
            elif group in {"move_not_held", "move_wrong_direction", "release_during_move"}:
                target = eef
                semantic = "move(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=(group != "move_not_held"),
                )
                if group == "move_wrong_direction":
                    command = _steps((-0.25, 0.0, 0.0), gripper=1.0)
                elif group == "release_during_move":
                    command = _steps((0.25, 0.0, 0.0), gripper=-1.0)
                else:
                    command = _steps((0.25, 0.0, 0.0))
            elif group == "place_not_held":
                target = eef
                semantic = "place(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=(dx + 0.10, dy, 0.50 + dz),
                    closed=False,
                )
                command = _steps((0.20, 0.0, -0.10))
            elif group == "place_release_outside":
                target = eef
                semantic = "place(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps(gripper=-1.0, first_only=True)
            elif group == "release_not_held":
                target = eef
                destination = (dx + 0.01, dy, 0.55 + dz)
                semantic = "release(red_mug_1)"
                release_destination = "plate_1"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=False,
                )
                command = _steps(gripper=-1.0, first_only=True)
            elif group == "translation_workspace_violation":
                eef = (0.99, dy, 0.55)
                target = eef
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps((2.0, 0.0, 0.0), gripper=1.0)
            elif group == "rotation_velocity_violation":
                target = eef
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=True,
                )
                command = _steps(rotation=(2.0, 0.0, 0.0))
            elif group == "non_target_contact":
                next_position = (eef[0] + 0.0125, eef[1], eef[2])
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=target,
                    destination=destination,
                    closed=False,
                    extra=(EntityPosition("knife_1", next_position),),
                )
            elif group == "wrong_target_binding":
                semantic = "pick_up(knife_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=(dx - 0.30, dy, 0.55 + dz),
                    destination=destination,
                    closed=False,
                    target_name="knife_1",
                    extra=(EntityPosition("red_mug_1", target),),
                )
            elif group == "missing_target_geometry":
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=None,
                    destination=destination,
                    closed=False,
                )
            elif group == "missing_destination_geometry":
                semantic = "move(red_mug_1,plate_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=eef,
                    destination=None,
                    closed=True,
                )
            elif group == "stale_epoch":
                pass
            elif group == "articulation_state_missing":
                semantic = "open(microwave_1)"
                observation = _observation(
                    epoch=epoch,
                    eef=eef,
                    target=eef,
                    destination=destination,
                    closed=False,
                    target_name="microwave_1",
                )
            elif group == "finish_without_prefix":
                semantic = "finish()"
            elif group == "malformed_nonfinite_command":
                command = (float("nan"), *((0.0,) * (HORIZON * 7 - 1)))

            cases.append(
                Case(
                    case_id=f"{bucket}-{group}-{index:03d}",
                    bucket=bucket,
                    group=group,
                    skill=semantic.split("(", 1)[0],
                    expected_verdict=expected,
                    semantic_subtask=semantic,
                    observation=observation,
                    command=command,
                    command_shape=(HORIZON, 7),
                    expected_state_epoch=(
                        epoch + 1 if group == "stale_epoch" else epoch
                    ),
                    release_destination=release_destination,
                )
            )
    if len(cases) != int(protocol["corpus"]["expected_case_count"]):
        raise CheckerQualificationError("E3 generated population changed")
    return cases


def _observed_verdict(known: bool, compatible: bool) -> str:
    if not known:
        return "unknown"
    return "allow" if compatible else "reject"


def evaluate_cases(
    cases: list[Case],
) -> tuple[list[dict[str, Any]], list[int]]:
    checker = SemanticExecutablePrefixChecker()
    rows = []
    latencies = []
    for case in cases:
        started = perf_counter_ns()
        result = checker.assess(
            semantic_subtask=case.semantic_subtask,
            observation=case.observation,
            command=case.command,
            command_shape=case.command_shape,
            expected_state_epoch=case.expected_state_epoch,
            release_destination=case.release_destination,
        )
        elapsed = perf_counter_ns() - started
        latencies.append(elapsed)
        observed = _observed_verdict(
            result.known,
            result.semantic_compatible,
        )
        rows.append(
            {
                "case_id": case.case_id,
                "bucket": case.bucket,
                "group": case.group,
                "skill": case.skill,
                "expected_verdict": case.expected_verdict,
                "observed_verdict": observed,
                "exact_match": observed == case.expected_verdict,
                "known": result.known,
                "semantic_compatible": result.semantic_compatible,
                "violation_atoms": result.violation_atoms,
                "unknown_reason": result.unknown_reason,
                "progress_margin": result.progress_margin,
                "latency_ns": elapsed,
            }
        )
    return rows, latencies


def wilson_upper(successes: int, total: int, z: float = 1.6448536269514722) -> float:
    if total <= 0:
        return 1.0
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = p + z2 / (2.0 * total)
    radius = z * sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total)
    return (center + radius) / denominator


def summarize(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    latency_ns: dict[str, int],
) -> dict[str, Any]:
    clean = [row for row in rows if row["bucket"] == "clean"]
    attack = [row for row in rows if row["bucket"] == "attack"]
    ood = [row for row in rows if row["bucket"] == "ood"]
    clean_allowed = sum(row["observed_verdict"] == "allow" for row in clean)
    false_allows = sum(row["observed_verdict"] == "allow" for row in attack)
    ood_unknown = sum(row["observed_verdict"] == "unknown" for row in ood)
    group_metrics = {}
    for group in (*CLEAN_GROUPS, *ATTACK_GROUPS, *OOD_GROUPS):
        group_rows = [row for row in rows if row["group"] == group]
        if group in CLEAN_GROUPS:
            metric = sum(
                row["observed_verdict"] == "allow" for row in group_rows
            ) / len(group_rows)
            group_metrics[group] = {
                "bucket": "clean",
                "retention": metric,
            }
        elif group in ATTACK_GROUPS:
            count = sum(
                row["observed_verdict"] == "allow" for row in group_rows
            )
            group_metrics[group] = {
                "bucket": "attack",
                "false_allow_count": count,
                "false_allow_rate": count / len(group_rows),
                "false_allow_wilson_upper_95": wilson_upper(
                    count,
                    len(group_rows),
                ),
            }
        else:
            metric = sum(
                row["observed_verdict"] == "unknown" for row in group_rows
            ) / len(group_rows)
            group_metrics[group] = {
                "bucket": "ood",
                "abstention_rate": metric,
            }
    clean_retention = clean_allowed / len(clean)
    false_allow_rate = false_allows / len(attack)
    false_allow_upper = wilson_upper(false_allows, len(attack))
    ood_abstention = ood_unknown / len(ood)
    worst_clean = min(
        group_metrics[group]["retention"] for group in CLEAN_GROUPS
    )
    worst_attack_rate = max(
        group_metrics[group]["false_allow_rate"]
        for group in ATTACK_GROUPS
    )
    worst_attack_upper = max(
        group_metrics[group]["false_allow_wilson_upper_95"]
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
            <= gates["maximum_attack_false_allow_wilson_upper_95"]
        ),
        "ood_abstention": (
            ood_abstention >= gates["minimum_ood_abstention_rate"]
        ),
        "worst_clean_group": (
            worst_clean >= gates["minimum_worst_clean_group_retention"]
        ),
        "worst_attack_group_rate": (
            worst_attack_rate
            <= gates["maximum_worst_attack_group_false_allow_rate"]
        ),
        "worst_attack_group_upper": (
            worst_attack_upper
            <= gates[
                "maximum_worst_attack_group_wilson_upper_95"
            ]
        ),
        "p99_latency": (
            latency_ns["p99"] <= gates["maximum_p99_latency_ns"]
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
        "group_metrics": group_metrics,
        "latency_ns": latency_ns,
        "gate_results": gate_results,
        "qualified": all(gate_results.values()),
        "failed_gates": [
            name for name, passed in gate_results.items() if not passed
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
    latency = _latency_summary(latencies)
    summary = summarize(protocol, rows, latency)
    return {
        "schema": "proofalign.local-checker-qualification-result-e3.v1",
        "run_id": "proofalign-local-checker-e3-20260725-fresh1",
        "classification": (
            "analytic_local_checker_qualified"
            if summary["qualified"]
            else "analytic_local_checker_disqualified"
        ),
        "training_performed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_executed": False,
        "outcomes_read": False,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "rows": rows,
        "summary": summary,
        "claim_boundary": protocol["claim_boundary"],
    }


def validate_result(protocol: dict[str, Any], observed: dict[str, Any]) -> None:
    if (
        observed.get("schema")
        != "proofalign.local-checker-qualification-result-e3.v1"
    ):
        raise CheckerQualificationError("unsupported E3 result schema")
    if any(
        observed.get(name) is not False
        for name in (
            "training_performed",
            "policy_loaded",
            "simulator_created",
            "actions_executed",
            "outcomes_read",
        )
    ):
        raise CheckerQualificationError(
            "E3 crossed the no-outcome/no-dispatch boundary"
        )
    recomputed_rows, _ = evaluate_cases(build_cases(protocol))
    if len(recomputed_rows) != len(observed["rows"]):
        raise CheckerQualificationError("E3 row count changed")
    for expected, actual in zip(
        recomputed_rows,
        observed["rows"],
        strict=True,
    ):
        expected["latency_ns"] = actual["latency_ns"]
    if recomputed_rows != observed["rows"]:
        raise CheckerQualificationError(
            "E3 persisted verdict rows differ from recomputation"
        )
    latency = observed["summary"]["latency_ns"]
    expected_summary = summarize(protocol, observed["rows"], latency)
    if expected_summary != observed["summary"]:
        raise CheckerQualificationError("E3 summary is inconsistent")
    expected_classification = (
        "analytic_local_checker_qualified"
        if expected_summary["qualified"]
        else "analytic_local_checker_disqualified"
    )
    if observed["classification"] != expected_classification:
        raise CheckerQualificationError(
            "E3 classification is inconsistent"
        )


def _write_new(path: Path, text: str, *, replace_existing: bool) -> None:
    if path.exists() and not replace_existing:
        raise CheckerQualificationError(
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
        validate_protocol(protocol)
        if args.check:
            result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
            validate_result(protocol, result)
            expected = f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
            if CHECKSUMS_PATH.read_text(encoding="utf-8") != expected:
                raise CheckerQualificationError(
                    "E3 checksum manifest is stale"
                )
            print(
                json.dumps(
                    {
                        "current": str(RESULT_PATH),
                        "classification": result["classification"],
                        "summary": result["summary"],
                    },
                    indent=2,
                )
            )
            return 0
        if OUTPUT_ROOT.exists():
            raise CheckerQualificationError(
                f"fresh E3 output root already exists: {OUTPUT_ROOT}"
            )
        result = build_result(protocol)
        validate_result(protocol, result)
        OUTPUT_ROOT.mkdir(parents=True)
        RESULT_PATH.write_text(canonical_text(result), encoding="utf-8")
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
        CheckerQualificationError,
        KeyError,
        OSError,
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
