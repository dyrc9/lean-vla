#!/usr/bin/env python3
"""Read-only v10 mechanism replay on the completed v9 fresh15 traces."""

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
from proofalign.physical_sufficiency_semantic import (  # noqa: E402
    ADVISORY_OBSERVED_VIOLATION_ATOMS,
    ADVISORY_SEMANTIC_UNKNOWN_REASONS,
)
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.physical-sufficiency-replay-qualification-protocol.v1"
)
RESULT_SCHEMA = (
    "proofalign.physical-sufficiency-replay-qualification-result.v1"
)
PROTOCOL_ID = (
    "proofalign-physical-sufficiency-replay-qualification-20260729"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_replay_qualification_protocol.json"
)


class PhysicalSufficiencyReplayError(RuntimeError):
    """Raised when the retained v9 mechanism replay differs."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise PhysicalSufficiencyReplayError(
            "qualification output root escapes repository"
        )
    return root


def _validate(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("protocol_id") != PROTOCOL_ID
        or protocol.get("status")
        != "authorized_read_only_physical_sufficiency_replay"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise PhysicalSufficiencyReplayError(
            "unsupported physical-sufficiency protocol"
        )
    if protocol.get("execution_authorization") != {
        "read_bound_episode_artifacts": True,
        "policy_load": False,
        "simulator_create": False,
        "action_dispatch": False,
        "task_outcome_generation": False,
    }:
        raise PhysicalSufficiencyReplayError(
            "qualification authorization differs"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise PhysicalSufficiencyReplayError(
                f"qualification source differs: {relative}"
            )
    evidence_binding = protocol["bound_v9_evidence"]
    evidence_path = REPO_ROOT / evidence_binding["path"]
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path) != evidence_binding["sha256"]
    ):
        raise PhysicalSufficiencyReplayError(
            "bound v9 evidence differs"
        )


def build_result(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    _validate(protocol, protocol_path=protocol_path)
    binding = protocol["bound_v9_evidence"]
    evidence = load_json_object(REPO_ROOT / binding["path"])
    if (
        evidence.get("classification")
        != "risk_selective_fresh15_clean_data_complete"
        or evidence.get("pilot_complete") is not True
    ):
        raise PhysicalSufficiencyReplayError(
            "bound v9 clean evidence is not complete"
        )

    counts: Counter[str] = Counter()
    unknowns: Counter[str] = Counter()
    effects: Counter[str] = Counter()
    terminal_rows = []
    for artifact in evidence["episodes"]:
        path = REPO_ROOT / artifact["path"]
        if (
            not path.is_file()
            or file_sha256(path) != artifact["sha256"]
        ):
            raise PhysicalSufficiencyReplayError(
                f"episode artifact differs: {path}"
            )
        episode = load_json_object(path)
        arm = episode["metadata"]["four_arm_label"]
        if arm not in {"semantic_only", "dual"}:
            continue
        counts["semantic_episode_count"] += 1
        for frame in episode["observation_frame_audits"]:
            audit = frame.get("online_progress_projection_v3")
            if not isinstance(audit, Mapping):
                continue
            candidates = audit.get("candidates")
            if (
                not isinstance(candidates, list)
                or len(candidates) != 1
                or not isinstance(candidates[0], Mapping)
            ):
                raise PhysicalSufficiencyReplayError(
                    "v9 candidate audit is malformed"
                )
            nominal = candidates[0]["nominal_checked"]
            risk = audit["risk_selective"]
            physical = tuple(risk["physical_risk_atoms"])
            unknown = nominal.get("unknown_reason")
            advisory_unknown = (
                unknown in ADVISORY_SEMANTIC_UNKNOWN_REASONS
            )
            counts["nominal_audit_count"] += 1
            counts["unchanged_source_action_block_count"] += int(
                audit["returned_source_policy_chunk_sha256"]
                == audit["returned_action_chunk_sha256"]
            )
            if advisory_unknown:
                unknowns[str(unknown)] += 1
                counts[
                    "physical_screened_semantic_unknown_count"
                ] += 1
            eligible = (
                not physical
                and (
                    nominal.get("known") is True
                    or advisory_unknown
                )
            )
            counts[
                "successor_nominal_eligible_count"
                if eligible
                else "successor_physical_or_unknown_reject_count"
            ] += 1
            decision = frame["semantic_decision"]
            if decision.get("accepted") is False:
                counts[
                    "predecessor_terminal_action_reject_count"
                ] += 1
                classification = (
                    "physical_screened_semantic_unknown_replan"
                    if advisory_unknown and not physical
                    else "physical_risk_reject_retained"
                    if physical
                    else "unrecognized_unknown_reject_retained"
                )
                counts[
                    "successor_recovered_semantic_unknown_count"
                    if classification.startswith("physical_screened")
                    else "successor_retained_physical_reject_count"
                    if physical
                    else "successor_retained_unknown_reject_count"
                ] += 1
                terminal_rows.append(
                    {
                        "episode_id": artifact["episode_id"],
                        "arm": arm,
                        "policy_call_index": frame[
                            "policy_call_index"
                        ],
                        "unknown_reason": unknown,
                        "physical_risk_atoms": physical,
                        "successor_classification": classification,
                        "counterfactual_task_outcome_claimed": False,
                    }
                )
            transaction = frame.get("semantic_transaction")
            if (
                isinstance(transaction, Mapping)
                and transaction.get("effect_verdict") == "reject"
            ):
                issues = transaction.get("effect_issues", ())
                if not isinstance(issues, list) or not issues:
                    raise PhysicalSufficiencyReplayError(
                        "v9 effect rejection is malformed"
                    )
                effects.update(str(issue) for issue in issues)
                counts["predecessor_effect_reject_count"] += 1
                atoms = []
                soft = True
                for issue in issues:
                    prefix = "observer violations: "
                    if not str(issue).startswith(prefix):
                        soft = False
                        break
                    atoms.extend(
                        atom
                        for atom in str(issue)
                        .removeprefix(prefix)
                        .split(",")
                        if atom
                    )
                soft = (
                    soft
                    and bool(atoms)
                    and all(
                        atom in ADVISORY_OBSERVED_VIOLATION_ATOMS
                        for atom in atoms
                    )
                )
                counts[
                    "successor_effect_replan_count"
                    if soft
                    else "successor_retained_effect_reject_count"
                ] += 1

    aggregate = {
        **dict(sorted(counts.items())),
        "semantic_unknown_reason_counts": dict(
            sorted(unknowns.items())
        ),
        "effect_issue_counts": dict(sorted(effects.items())),
    }
    gate_results = {
        name: aggregate.get(name) == expected
        for name, expected in protocol["gates"].items()
    }
    gate_results["action_terminal_partition_complete"] = (
        aggregate["predecessor_terminal_action_reject_count"]
        == aggregate["successor_recovered_semantic_unknown_count"]
        + aggregate["successor_retained_physical_reject_count"]
        + aggregate.get("successor_retained_unknown_reject_count", 0)
    )
    gate_results["effect_terminal_partition_complete"] = (
        aggregate["predecessor_effect_reject_count"]
        == aggregate["successor_effect_replan_count"]
        + aggregate["successor_retained_effect_reject_count"]
    )
    passed = all(gate_results.values())
    return {
        "schema": RESULT_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "physical_sufficiency_replay_qualification_pass"
            if passed
            else "physical_sufficiency_replay_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "new_task_outcomes_generated": False,
        "counterfactual_success_rate_computed": False,
        "protocol": {
            "path": protocol_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "aggregate": aggregate,
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
        raise PhysicalSufficiencyReplayError(
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
        raise PhysicalSufficiencyReplayError(
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
            protocol, protocol_path=protocol_path
        )
    )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
