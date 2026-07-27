#!/usr/bin/env python3
"""Run the preregistered deterministic geometry-FSM fallback gate.

This is an exhaustive finite boundary gate over the exact predicates consumed
by ``DeterministicTaskGraphSelector``.  It loads trusted BDDL files but no
policy, dataset, simulator, or outcome.  The gate qualifies transaction-level
selector logic for benchmark privileged geometry; it does not qualify a
deployment perception system.
"""

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
    TrustedLocalObservation,
)
from proofalign.semantic_policy_wrapper import (  # noqa: E402
    DeterministicTaskGraphSelector,
    SemanticGoal,
    compile_libero_task_graph,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deterministic_selector_e1f_protocol.json"
)
EVIDENCE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deterministic_selector_e1f.json"
)
BDDL_ROOT = (
    REPO_ROOT
    / "external"
    / "LIBERO-phantom-r0"
    / "libero"
    / "libero"
    / "bddl_files"
    / "libero_spatial"
)
SOURCE_PATHS = (
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/semantic_local_checker.py",
    "scripts/run_deterministic_selector_qualification_e1f.py",
)
CASE_FAMILIES = (
    "missing_target_geometry",
    "missing_destination_geometry",
    "open_far_target_pick",
    "open_goal_satisfied_finish",
    "closed_unbound_target_unknown",
    "closed_held_far_move",
    "closed_held_place_region",
    "closed_held_release_region",
    "held_boundary_inside",
    "held_boundary_outside",
    "gripper_boundary_closed",
    "gripper_boundary_open",
    "destination_xy_boundary_inside",
    "destination_xy_boundary_outside",
    "release_radius_inside",
    "release_radius_outside",
)


class FallbackQualificationError(RuntimeError):
    """Raised when deterministic selector evidence is stale or inconsistent."""


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


def _bddl_paths() -> tuple[Path, ...]:
    paths = tuple(sorted(BDDL_ROOT.glob("*.bddl")))
    if len(paths) != 10:
        raise FallbackQualificationError(
            f"expected 10 LIBERO Spatial BDDL files, observed {len(paths)}"
        )
    return paths


def build_protocol() -> dict[str, Any]:
    config = LocalCheckerConfig()
    return {
        "schema": "proofalign.deterministic-selector-e1f-protocol.v1",
        "protocol_id": "proofalign-deterministic-selector-e1f-20260725",
        "status": "frozen_no_outcome_fallback_boundary_gate",
        "created_at": "2026-07-25T00:00:00+08:00",
        "trigger": {
            "e1_result": (
                "results/proofalign_semantic_selector_e1_20260725_fresh1/"
                "qualification.json"
            ),
            "required_classification": "raw_pi05_selector_disqualified",
        },
        "selector": (
            "proofalign.semantic_policy_wrapper."
            "DeterministicTaskGraphSelector"
        ),
        "geometry_mode": "benchmark_privileged_state",
        "bddl_bindings": {
            str(path.relative_to(REPO_ROOT)): file_sha256(path)
            for path in _bddl_paths()
        },
        "config": {
            "gripper_closed_qpos_max": config.gripper_closed_qpos_max,
            "held_neighborhood_m": config.held_neighborhood_m,
            "destination_neighborhood_m": (
                config.destination_neighborhood_m
            ),
            "release_neighborhood_m": config.release_neighborhood_m,
        },
        "case_families": CASE_FAMILIES,
        "expected_task_count": 10,
        "expected_case_count": 10 * len(CASE_FAMILIES),
        "boundary_epsilon": 1e-6,
        "latency_repetitions_per_case": 100,
        "gates": {
            "minimum_exact_case_rate": 1.0,
            "minimum_unknown_fail_closed_rate": 1.0,
            "maximum_p99_latency_ns": 100_000,
        },
        "source": {
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            }
        },
        "output": str(EVIDENCE_PATH.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "policy_load_authorized": False,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
        },
        "claim_boundary": (
            "Exhaustive finite boundary evidence for deterministic task-graph "
            "selection given exact benchmark privileged geometry. It does not "
            "qualify camera perception, hardware attestation, learned "
            "semantics, deployment generalization, efficacy, or safety."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.deterministic-selector-e1f-protocol.v1"
    ):
        raise FallbackQualificationError("unsupported E1F protocol schema")
    if tuple(protocol.get("case_families", ())) != CASE_FAMILIES:
        raise FallbackQualificationError("E1F case families changed")
    if protocol.get("expected_case_count") != 160:
        raise FallbackQualificationError("E1F case count changed")
    if any(protocol["execution_authorization"].values()):
        raise FallbackQualificationError(
            "E1F protocol authorizes an external runtime"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise FallbackQualificationError(
                f"E1F source binding is stale: {relative}"
            )
    for relative, expected in protocol["bddl_bindings"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise FallbackQualificationError(
                f"E1F BDDL binding is stale: {relative}"
            )
    trigger_path = REPO_ROOT / protocol["trigger"]["e1_result"]
    trigger = json.loads(trigger_path.read_text(encoding="utf-8"))
    if (
        trigger.get("classification")
        != protocol["trigger"]["required_classification"]
    ):
        raise FallbackQualificationError(
            "E1F fallback trigger classification is not satisfied"
        )


@dataclass(frozen=True)
class Fixture:
    case_family: str
    expected_known: bool
    expected_finished: bool
    expected_verb: str
    expected_reason: str
    eef: tuple[float, float, float]
    gripper: tuple[float, float]
    target: tuple[float, float, float] | None
    destination: tuple[float, float, float] | None


def fixture_matrix(config: LocalCheckerConfig, epsilon: float) -> tuple[Fixture, ...]:
    destination = (0.0, 0.0, 0.8)
    far_target = (0.4, 0.0, 0.8)
    held_eef = far_target
    open_gripper = (0.04, -0.04)
    closed_gripper = (0.002, -0.002)
    gripper_boundary = (
        config.gripper_closed_qpos_max,
        -config.gripper_closed_qpos_max,
    )
    gripper_outside = (
        config.gripper_closed_qpos_max + epsilon,
        -(config.gripper_closed_qpos_max + epsilon),
    )
    held_inside_eef = (
        far_target[0] + config.held_neighborhood_m - epsilon,
        far_target[1],
        far_target[2],
    )
    held_outside_eef = (
        far_target[0] + config.held_neighborhood_m + epsilon,
        far_target[1],
        far_target[2],
    )
    place_inside_xy = (
        config.destination_neighborhood_m - epsilon,
        0.0,
        destination[2] + 0.08,
    )
    move_outside_xy = (
        config.destination_neighborhood_m + epsilon,
        0.0,
        destination[2] + 0.08,
    )
    release_xy = 0.14
    release_inside_radius = config.release_neighborhood_m - epsilon
    release_outside_radius = config.release_neighborhood_m + epsilon
    release_inside = (
        release_xy,
        0.0,
        destination[2]
        + sqrt(release_inside_radius**2 - release_xy**2),
    )
    release_outside = (
        release_xy,
        0.0,
        destination[2]
        + sqrt(release_outside_radius**2 - release_xy**2),
    )
    release_target = (0.14, 0.0, 0.8)
    goal_target = (0.10, 0.0, 0.8)
    return (
        Fixture(
            "missing_target_geometry",
            False,
            False,
            "unknown",
            "missing_target_geometry",
            (0.0, 0.0, 1.0),
            open_gripper,
            None,
            destination,
        ),
        Fixture(
            "missing_destination_geometry",
            False,
            False,
            "unknown",
            "missing_destination_geometry",
            (0.0, 0.0, 1.0),
            open_gripper,
            far_target,
            None,
        ),
        Fixture(
            "open_far_target_pick",
            True,
            False,
            "pick_up",
            "target_not_held",
            (0.0, 0.0, 1.0),
            open_gripper,
            far_target,
            destination,
        ),
        Fixture(
            "open_goal_satisfied_finish",
            True,
            True,
            "finish",
            "all_supported_goals_satisfied",
            (0.0, 0.0, 1.0),
            open_gripper,
            goal_target,
            destination,
        ),
        Fixture(
            "closed_unbound_target_unknown",
            False,
            False,
            "unknown",
            "closed_without_bound_target",
            (0.0, 0.0, 1.2),
            closed_gripper,
            far_target,
            destination,
        ),
        Fixture(
            "closed_held_far_move",
            True,
            False,
            "move",
            "held_target_outside_destination_xy",
            held_eef,
            closed_gripper,
            far_target,
            destination,
        ),
        Fixture(
            "closed_held_place_region",
            True,
            False,
            "place",
            "held_target_requires_placement",
            place_inside_xy,
            closed_gripper,
            place_inside_xy,
            destination,
        ),
        Fixture(
            "closed_held_release_region",
            True,
            False,
            "release",
            "held_target_inside_release_region",
            release_target,
            closed_gripper,
            release_target,
            destination,
        ),
        Fixture(
            "held_boundary_inside",
            True,
            False,
            "move",
            "held_target_outside_destination_xy",
            held_inside_eef,
            closed_gripper,
            far_target,
            destination,
        ),
        Fixture(
            "held_boundary_outside",
            False,
            False,
            "unknown",
            "closed_without_bound_target",
            held_outside_eef,
            closed_gripper,
            far_target,
            destination,
        ),
        Fixture(
            "gripper_boundary_closed",
            True,
            False,
            "move",
            "held_target_outside_destination_xy",
            held_eef,
            gripper_boundary,
            far_target,
            destination,
        ),
        Fixture(
            "gripper_boundary_open",
            True,
            False,
            "pick_up",
            "target_not_held",
            held_eef,
            gripper_outside,
            far_target,
            destination,
        ),
        Fixture(
            "destination_xy_boundary_inside",
            True,
            False,
            "place",
            "held_target_requires_placement",
            place_inside_xy,
            closed_gripper,
            place_inside_xy,
            destination,
        ),
        Fixture(
            "destination_xy_boundary_outside",
            True,
            False,
            "move",
            "held_target_outside_destination_xy",
            move_outside_xy,
            closed_gripper,
            move_outside_xy,
            destination,
        ),
        Fixture(
            "release_radius_inside",
            True,
            False,
            "release",
            "held_target_inside_release_region",
            release_inside,
            closed_gripper,
            release_inside,
            destination,
        ),
        Fixture(
            "release_radius_outside",
            True,
            False,
            "place",
            "held_target_requires_placement",
            release_outside,
            closed_gripper,
            release_outside,
            destination,
        ),
    )


def _verb(selection: str) -> str:
    return selection.split("(", 1)[0]


def _observation(
    fixture: Fixture,
    goal: SemanticGoal,
    *,
    state_epoch: int,
) -> TrustedLocalObservation:
    entities = []
    if fixture.target is not None:
        entities.append(EntityPosition(goal.target, fixture.target))
    if fixture.destination is not None:
        assert goal.destination is not None
        entities.append(
            EntityPosition(goal.destination, fixture.destination)
        )
    return TrustedLocalObservation(
        state_epoch=state_epoch,
        eef_position=fixture.eef,
        gripper_qpos=fixture.gripper,
        entity_positions=tuple(entities),
    )


def build_evidence(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    config = LocalCheckerConfig()
    fixtures = fixture_matrix(
        config,
        float(protocol["boundary_epsilon"]),
    )
    if tuple(item.case_family for item in fixtures) != CASE_FAMILIES:
        raise FallbackQualificationError(
            "E1F fixture implementation differs from frozen case order"
        )
    rows = []
    latencies = []
    repetitions = int(protocol["latency_repetitions_per_case"])
    for task_index, path in enumerate(_bddl_paths()):
        graph = compile_libero_task_graph(
            path.read_text(encoding="utf-8")
        )
        if len(graph.goals) != 1:
            raise FallbackQualificationError(
                f"E1F expects one goal per BDDL: {path}"
            )
        goal = graph.goals[0]
        selector = DeterministicTaskGraphSelector(graph, config)
        for fixture_index, fixture in enumerate(fixtures):
            observation = _observation(
                fixture,
                goal,
                state_epoch=fixture_index,
            )
            started = perf_counter_ns()
            selection = selector.select(observation)
            elapsed = perf_counter_ns() - started
            latencies.append(elapsed)
            for _ in range(repetitions - 1):
                started = perf_counter_ns()
                repeated = selector.select(observation)
                latencies.append(perf_counter_ns() - started)
                if repeated != selection:
                    raise FallbackQualificationError(
                        "deterministic selector returned inconsistent results"
                    )
            exact = (
                selection.known == fixture.expected_known
                and selection.finished == fixture.expected_finished
                and _verb(selection.selected_subtask)
                == fixture.expected_verb
                and selection.reason == fixture.expected_reason
            )
            rows.append(
                {
                    "task_index": task_index,
                    "task_bddl": str(path.relative_to(REPO_ROOT)),
                    "task_graph_digest": graph.graph_digest,
                    "target": goal.target,
                    "destination": goal.destination,
                    "case_index": fixture_index,
                    "case_family": fixture.case_family,
                    "observation_digest": observation.observation_digest,
                    "expected": {
                        "known": fixture.expected_known,
                        "finished": fixture.expected_finished,
                        "verb": fixture.expected_verb,
                        "reason": fixture.expected_reason,
                    },
                    "observed": {
                        "known": selection.known,
                        "finished": selection.finished,
                        "selected_subtask": selection.selected_subtask,
                        "verb": _verb(selection.selected_subtask),
                        "reason": selection.reason,
                    },
                    "exact_match": exact,
                    "first_latency_ns": elapsed,
                }
            )
    exact_count = sum(row["exact_match"] for row in rows)
    unknown_rows = [
        row for row in rows if not row["expected"]["known"]
    ]
    unknown_closed = [
        row
        for row in unknown_rows
        if not row["observed"]["known"]
        and row["observed"]["verb"] == "unknown"
    ]
    latency_array = np.asarray(latencies, dtype=np.int64)
    exact_rate = exact_count / len(rows)
    fail_closed_rate = len(unknown_closed) / len(unknown_rows)
    p99 = int(np.quantile(latency_array, 0.99))
    gates = protocol["gates"]
    gate_results = {
        "exact_case_rate": (
            exact_rate >= gates["minimum_exact_case_rate"]
        ),
        "unknown_fail_closed_rate": (
            fail_closed_rate
            >= gates["minimum_unknown_fail_closed_rate"]
        ),
        "p99_latency": p99 <= gates["maximum_p99_latency_ns"],
    }
    passed = all(gate_results.values())
    return {
        "schema": "proofalign.deterministic-selector-e1f-evidence.v1",
        "evidence_id": "proofalign-deterministic-selector-e1f-20260725",
        "classification": (
            "deterministic_fsm_fallback_gate_pass"
            if passed
            else "deterministic_fsm_fallback_gate_fail"
        ),
        "training_performed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_executed": False,
        "outcomes_read": False,
        "geometry_mode": protocol["geometry_mode"],
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "source_bindings": protocol["source"]["sha256"],
        "bddl_bindings": protocol["bddl_bindings"],
        "case_count": len(rows),
        "exact_match_count": exact_count,
        "exact_match_rate": exact_rate,
        "unknown_case_count": len(unknown_rows),
        "unknown_fail_closed_count": len(unknown_closed),
        "unknown_fail_closed_rate": fail_closed_rate,
        "latency_ns": {
            "measurement_count": len(latencies),
            "p50": int(np.quantile(latency_array, 0.50)),
            "p95": int(np.quantile(latency_array, 0.95)),
            "p99": p99,
            "maximum": int(np.max(latency_array)),
        },
        "gate_results": gate_results,
        "qualified": passed,
        "rows": rows,
        "claim_boundary": protocol["claim_boundary"],
    }


def _write_new(path: Path, text: str, *, replace_existing: bool) -> None:
    if path.exists() and not replace_existing:
        raise FallbackQualificationError(
            f"refusing to replace existing frozen artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--write-evidence", action="store_true")
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
        expected = canonical_text(build_evidence(protocol))
        if args.check:
            if EVIDENCE_PATH.read_text(encoding="utf-8") != expected:
                raise FallbackQualificationError(
                    f"E1F evidence is stale: {EVIDENCE_PATH}"
                )
            print(f"current: {EVIDENCE_PATH}")
            return 0
        _write_new(
            EVIDENCE_PATH,
            expected,
            replace_existing=args.replace_existing,
        )
        print(EVIDENCE_PATH)
        return 0
    except (
        FallbackQualificationError,
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
