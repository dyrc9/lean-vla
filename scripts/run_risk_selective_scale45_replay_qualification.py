#!/usr/bin/env python3
"""Read-only mechanism replay for the v9 risk-selective successor.

This qualification deliberately does not replay the simulator or infer task
outcomes.  It partitions every retained v8 nominal assessment into physical
risk versus advisory task semantics, and checks which predecessor terminal
decisions the frozen v9 rule would keep or make available for replanning.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.risk_selective_semantic import (  # noqa: E402
    is_physical_risk_atom,
)
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.risk-selective-scale45-replay-qualification-protocol.v1"
)
RESULT_SCHEMA = (
    "proofalign.risk-selective-scale45-replay-qualification-result.v1"
)
PROTOCOL_ID = (
    "proofalign-risk-selective-scale45-replay-qualification-20260729"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_risk_selective_scale45_replay_qualification_protocol.json"
)


class RiskSelectiveReplayError(RuntimeError):
    """Raised when the retained replay differs from its frozen scope."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise RiskSelectiveReplayError(
            "qualification output root escapes repository"
        )
    return root


def _validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("protocol_id") != PROTOCOL_ID
        or protocol.get("status")
        != "authorized_read_only_risk_partition_replay"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise RiskSelectiveReplayError(
            "unsupported risk-selective replay protocol"
        )
    if protocol.get("execution_authorization") != {
        "read_bound_episode_artifacts": True,
        "policy_load": False,
        "simulator_create": False,
        "action_dispatch": False,
        "task_outcome_generation": False,
    }:
        raise RiskSelectiveReplayError(
            "qualification authorization differs"
        )
    source = protocol.get("source")
    if not isinstance(source, Mapping):
        raise RiskSelectiveReplayError("source binding is absent")
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise RiskSelectiveReplayError(
                f"qualification source differs: {relative}"
            )
    parent = protocol["parent_scale45_terminal"]
    parent_path = REPO_ROOT / str(parent["path"])
    parent_payload = load_json_object(parent_path)
    if (
        not parent_path.is_file()
        or file_sha256(parent_path) != parent["sha256"]
        or parent_payload.get("classification")
        != "contact_phase_pick_up_scale45_data_complete"
        or parent_payload.get("data_complete") is not True
    ):
        raise RiskSelectiveReplayError(
            "scale45 terminal parent binding differs"
        )
    evidence = protocol["bound_scale45_evidence"]
    evidence_path = REPO_ROOT / str(evidence["path"])
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path) != evidence["sha256"]
    ):
        raise RiskSelectiveReplayError(
            "bound scale45 evidence differs"
        )


def _partition_atoms(
    atoms: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(atoms, list) or not all(
        isinstance(atom, str) for atom in atoms
    ):
        raise RiskSelectiveReplayError(
            "nominal hard-violation atoms are malformed"
        )
    physical = tuple(
        atom for atom in atoms if is_physical_risk_atom(atom)
    )
    advisory = tuple(atom for atom in atoms if atom not in physical)
    return physical, advisory


def _candidate_from_frame(
    frame: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    audit = frame.get("online_progress_projection_v3")
    if not isinstance(audit, Mapping):
        raise RiskSelectiveReplayError(
            "expected predecessor projection audit is absent"
        )
    candidates = audit.get("candidates")
    if (
        not isinstance(candidates, list)
        or len(candidates) != 1
        or not isinstance(candidates[0], Mapping)
    ):
        raise RiskSelectiveReplayError(
            "predecessor candidate audit is malformed"
        )
    return audit, candidates[0]


def build_result(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    """Recompute the complete retained mechanism partition."""

    _validate_protocol(protocol, protocol_path=protocol_path)
    evidence_binding = protocol["bound_scale45_evidence"]
    evidence = load_json_object(
        REPO_ROOT / str(evidence_binding["path"])
    )
    if (
        evidence.get("aggregate", {}).get("episode_count") != 180
        or len(evidence.get("episodes", ())) != 180
    ):
        raise RiskSelectiveReplayError(
            "bound evidence is not the complete scale45 table"
        )

    counts: Counter[str] = Counter()
    physical_atoms: Counter[str] = Counter()
    advisory_atoms: Counter[str] = Counter()
    effect_issues: Counter[str] = Counter()
    by_arm: dict[str, Counter[str]] = {}
    terminal_rows: list[dict[str, Any]] = []

    for artifact in evidence["episodes"]:
        path = REPO_ROOT / str(artifact["path"])
        if (
            not path.is_file()
            or file_sha256(path) != artifact["sha256"]
        ):
            raise RiskSelectiveReplayError(
                f"episode artifact differs: {path}"
            )
        episode = load_json_object(path)
        arm = str(episode["metadata"]["four_arm_label"])
        if arm not in {"semantic_only", "dual"}:
            continue
        arm_counts = by_arm.setdefault(arm, Counter())
        counts["semantic_episode_count"] += 1
        arm_counts["episode_count"] += 1

        for event in episode["semantic_events"]:
            if (
                event.get("known") is False
                or event.get("finished") is True
            ):
                counts["selector_fallback_endpoint_count"] += 1
                arm_counts["selector_fallback_endpoint_count"] += 1

        for frame in episode["observation_frame_audits"]:
            if "online_progress_projection_v3" not in frame:
                continue
            audit, candidate = _candidate_from_frame(frame)
            nominal = candidate.get("nominal_checked")
            if not isinstance(nominal, Mapping):
                raise RiskSelectiveReplayError(
                    "nominal predecessor assessment is malformed"
                )
            source_digest = audit.get(
                "returned_source_policy_chunk_sha256"
            )
            returned_digest = audit.get(
                "returned_action_chunk_sha256"
            )
            if (
                not isinstance(source_digest, str)
                or len(source_digest) != 64
                or frame.get("policy_action_chunk_sha256")
                != returned_digest
            ):
                raise RiskSelectiveReplayError(
                    "source/returned action provenance differs"
                )
            counts["nominal_audit_count"] += 1
            arm_counts["nominal_audit_count"] += 1
            if source_digest == returned_digest:
                counts["predecessor_unchanged_block_count"] += 1
            else:
                counts["predecessor_changed_block_count"] += 1

            physical, advisory = _partition_atoms(
                nominal.get("hard_violation_atoms")
            )
            physical_atoms.update(physical)
            advisory_atoms.update(advisory)
            counts["physical_risk_atom_count"] += len(physical)
            counts["advisory_semantic_atom_count"] += len(advisory)
            known = nominal.get("known") is True
            successor_eligible = known and not physical
            if successor_eligible:
                counts["successor_nominal_eligible_count"] += 1
                arm_counts["successor_nominal_eligible_count"] += 1
            else:
                counts["successor_physical_reject_count"] += 1
                arm_counts["successor_physical_reject_count"] += 1

            decision = frame.get("semantic_decision")
            if not isinstance(decision, Mapping):
                raise RiskSelectiveReplayError(
                    "semantic decision is absent"
                )
            if decision.get("accepted") is False:
                counts["predecessor_terminal_action_reject_count"] += 1
                arm_counts[
                    "predecessor_terminal_action_reject_count"
                ] += 1
                classification = (
                    "available_for_replan"
                    if successor_eligible
                    else "physical_risk_reject_retained"
                )
                counts[
                    "successor_recovered_action_reject_count"
                    if successor_eligible
                    else "successor_retained_physical_reject_count"
                ] += 1
                arm_counts[
                    "successor_recovered_action_reject_count"
                    if successor_eligible
                    else "successor_retained_physical_reject_count"
                ] += 1
                terminal_rows.append(
                    {
                        "episode_id": artifact["episode_id"],
                        "suite": episode["metadata"][
                            "benchmark_name"
                        ],
                        "arm": arm,
                        "policy_call_index": frame[
                            "policy_call_index"
                        ],
                        "source_policy_chunk_sha256": source_digest,
                        "predecessor_returned_action_chunk_sha256": (
                            returned_digest
                        ),
                        "physical_risk_atoms": physical,
                        "advisory_semantic_atoms": advisory,
                        "successor_classification": classification,
                        "counterfactual_task_outcome_claimed": False,
                    }
                )

            transaction = frame.get("semantic_transaction")
            if (
                isinstance(transaction, Mapping)
                and transaction.get("effect_verdict") == "reject"
            ):
                issues = transaction.get("effect_issues")
                if not isinstance(issues, list) or not issues:
                    raise RiskSelectiveReplayError(
                        "effect rejection issues are malformed"
                    )
                if not all(isinstance(issue, str) for issue in issues):
                    raise RiskSelectiveReplayError(
                        "effect rejection issue is not text"
                    )
                effect_issues.update(issues)
                counts["predecessor_effect_reject_count"] += 1
                missing_only = all(
                    issue.startswith("expected effects missing:")
                    for issue in issues
                )
                counts[
                    "successor_effect_replan_count"
                    if missing_only
                    else "successor_retained_effect_reject_count"
                ] += 1

    aggregate = {
        **dict(sorted(counts.items())),
        "physical_risk_atom_counts": dict(
            sorted(physical_atoms.items())
        ),
        "advisory_semantic_atom_counts": dict(
            sorted(advisory_atoms.items())
        ),
        "effect_issue_counts": dict(sorted(effect_issues.items())),
    }
    gate_results = {
        name: aggregate.get(name) == expected
        for name, expected in protocol["gates"].items()
    }
    gate_results["terminal_partition_complete"] = (
        aggregate["predecessor_terminal_action_reject_count"]
        == (
            aggregate["successor_recovered_action_reject_count"]
            + aggregate[
                "successor_retained_physical_reject_count"
            ]
        )
    )
    gate_results["nominal_partition_complete"] = (
        aggregate["nominal_audit_count"]
        == (
            aggregate["successor_nominal_eligible_count"]
            + aggregate["successor_physical_reject_count"]
        )
    )
    passed = all(gate_results.values())
    return {
        "schema": RESULT_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "risk_selective_scale45_replay_qualification_pass"
            if passed
            else "risk_selective_scale45_replay_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "new_task_outcomes_generated": False,
        "counterfactual_success_rate_computed": False,
        "protocol": {
            "path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "aggregate": aggregate,
        "by_arm": {
            arm: dict(sorted(values.items()))
            for arm, values in sorted(by_arm.items())
        },
        "terminal_action_decisions": terminal_rows,
        "gate_results": gate_results,
        "claim_boundary": protocol["claim_boundary"],
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    output_root = _output_root(protocol)
    if output_root.exists():
        raise RiskSelectiveReplayError(
            f"qualification root already exists: {output_root}"
        )
    output_root.mkdir(parents=True)
    result = build_result(protocol, protocol_path=protocol_path)
    saber_io.atomic_json(output_root / "qualification.json", result)
    p0b.write_checksums(output_root)
    return result


def validate_result(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    output_root = _output_root(protocol)
    p0b.read_checksums(output_root)
    retained = load_json_object(output_root / "qualification.json")
    rebuilt = build_result(protocol, protocol_path=protocol_path)
    if json.loads(canonical_text(rebuilt)) != retained:
        raise RiskSelectiveReplayError(
            "qualification result differs from recomputation"
        )
    return retained


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-result", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    payload = (
        execute(protocol, protocol_path=protocol_path)
        if args.execute
        else validate_result(
            protocol,
            protocol_path=protocol_path,
        )
    )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
