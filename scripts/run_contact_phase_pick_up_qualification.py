#!/usr/bin/env python3
"""Replay-qualify the contact-phase successor on bound v7 evidence."""

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
from proofalign.contact_phase_pick_up import (  # noqa: E402
    CONTACT_PHASE_BYPASS_REASON,
    contact_phase_replay_eligible,
)
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.contact-phase-pick-up-replay-qualification-protocol.v1"
)
RESULT_SCHEMA = (
    "proofalign.contact-phase-pick-up-replay-qualification-result.v1"
)
PROTOCOL_ID = (
    "proofalign-contact-phase-pick-up-replay-qualification-20260728"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_qualification_protocol.json"
)


class ContactPhaseQualificationError(RuntimeError):
    """Raised when replay qualification differs from its frozen scope."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise ContactPhaseQualificationError(
            "qualification output root escapes repository"
        )
    return root


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("protocol_id") != PROTOCOL_ID
        or protocol.get("status")
        != "authorized_read_only_contact_phase_replay"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise ContactPhaseQualificationError(
            "unsupported contact-phase qualification protocol"
        )
    if protocol.get("execution_authorization") != {
        "read_bound_episode_artifacts": True,
        "policy_load": False,
        "simulator_create": False,
        "action_dispatch": False,
        "task_outcome_generation": False,
    }:
        raise ContactPhaseQualificationError(
            "qualification authorization differs"
        )
    source = protocol.get("source")
    if not isinstance(source, Mapping):
        raise ContactPhaseQualificationError(
            "qualification source binding is absent"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ContactPhaseQualificationError(
                f"qualification source differs: {relative}"
            )
    parent = protocol["parent_initial_terminal"]
    parent_path = REPO_ROOT / str(parent["path"])
    parent_payload = load_json_object(parent_path)
    if (
        file_sha256(parent_path) != parent["sha256"]
        or parent_payload.get("classification")
        != "horizon_consistent_v7_four_arm_initial_complete"
        or parent_payload.get("lifecycle", {}).get(
            "semantic_projection_budget_successor_protocol_"
            "freeze_authorized"
        )
        is not True
    ):
        raise ContactPhaseQualificationError(
            "initial terminal parent binding differs"
        )
    evidence = protocol["bound_v7_evidence"]
    evidence_path = REPO_ROOT / str(evidence["path"])
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path) != evidence["sha256"]
    ):
        raise ContactPhaseQualificationError(
            "bound v7 evidence differs"
        )


def build_result(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    evidence_binding = protocol["bound_v7_evidence"]
    evidence = load_json_object(
        REPO_ROOT / str(evidence_binding["path"])
    )
    rows = []
    reason_counts: Counter[str] = Counter()
    recovered_unique = set()
    hard_recovered = 0
    online_audit_count = 0
    for artifact in evidence["episodes"]:
        path = REPO_ROOT / str(artifact["path"])
        if (
            not path.is_file()
            or file_sha256(path) != artifact["sha256"]
        ):
            raise ContactPhaseQualificationError(
                f"episode artifact differs: {path}"
            )
        episode = load_json_object(path)
        for frame in episode["observation_frame_audits"]:
            audit = frame.get("online_progress_projection_v3")
            if not isinstance(audit, Mapping):
                continue
            online_audit_count += 1
            candidates = audit.get("candidates")
            if (
                not isinstance(candidates, list)
                or len(candidates) != 1
                or not isinstance(candidates[0], Mapping)
            ):
                raise ContactPhaseQualificationError(
                    "bound online audit is malformed"
                )
            candidate = candidates[0]
            projection = candidate["progress_projection"]
            nominal = candidate["nominal_checked"]
            reason_counts[str(projection["reason"])] += 1
            if not contact_phase_replay_eligible(candidate):
                continue
            hard = nominal["hard_violation_atoms"]
            hard_recovered += len(hard)
            unique_key = (
                episode["metadata"]["benchmark_name"],
                frame["policy_observation_digest"],
                frame["policy_action_chunk_sha256"],
            )
            recovered_unique.add(unique_key)
            rows.append(
                {
                    "suite": episode["metadata"][
                        "benchmark_name"
                    ],
                    "arm": episode["metadata"]["four_arm_label"],
                    "policy_call_index": frame[
                        "policy_call_index"
                    ],
                    "policy_observation_digest": frame[
                        "policy_observation_digest"
                    ],
                    "policy_action_chunk_sha256": frame[
                        "policy_action_chunk_sha256"
                    ],
                    "predecessor_reason": projection["reason"],
                    "successor_reason": (
                        CONTACT_PHASE_BYPASS_REASON
                    ),
                    "known": nominal["known"],
                    "semantic_compatible": nominal[
                        "semantic_compatible"
                    ],
                    "post_projection_compatible": nominal[
                        "post_projection_compatible"
                    ],
                    "hard_violation_atoms": hard,
                    "nominal_progress_margin": nominal[
                        "progress_margin"
                    ],
                    "command_changed": False,
                }
            )
    aggregate = {
        "online_audit_count": online_audit_count,
        "projection_reason_counts": dict(
            sorted(reason_counts.items())
        ),
        "predecessor_projection_budget_reject_count": (
            reason_counts["semantic_projection_budget_exceeded"]
        ),
        "recovered_arm_instance_count": len(rows),
        "recovered_unique_source_block_count": len(
            recovered_unique
        ),
        "recovered_hard_violation_atom_count": hard_recovered,
        "command_change_count": sum(
            row["command_changed"] for row in rows
        ),
    }
    gates = protocol["gates"]
    gate_results = {
        "online_audit_count": (
            aggregate["online_audit_count"]
            == gates["expected_online_audit_count"]
        ),
        "projection_budget_reject_count": (
            aggregate[
                "predecessor_projection_budget_reject_count"
            ]
            == gates[
                "expected_predecessor_projection_budget_reject_count"
            ]
        ),
        "recovered_arm_instance_count": (
            aggregate["recovered_arm_instance_count"]
            == gates["expected_recovered_arm_instance_count"]
        ),
        "recovered_unique_source_block_count": (
            aggregate["recovered_unique_source_block_count"]
            == gates["expected_recovered_unique_source_block_count"]
        ),
        "recovered_hard_violation_atom_count": (
            aggregate["recovered_hard_violation_atom_count"] == 0
        ),
        "command_change_count": (
            aggregate["command_change_count"] == 0
        ),
    }
    passed = all(gate_results.values())
    return {
        "schema": RESULT_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "contact_phase_pick_up_replay_qualification_pass"
            if passed
            else "contact_phase_pick_up_replay_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "new_task_outcomes_generated": False,
        "protocol": {
            "path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "recovered_instances": rows,
        "aggregate": aggregate,
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
        raise ContactPhaseQualificationError(
            f"qualification root already exists: {output_root}"
        )
    output_root.mkdir(parents=True)
    result = build_result(
        protocol,
        protocol_path=protocol_path,
    )
    saber_io.atomic_json(
        output_root / "qualification.json",
        result,
    )
    p0b.write_checksums(output_root)
    return result


def validate_result(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    output_root = _output_root(protocol)
    p0b.read_checksums(output_root)
    retained = load_json_object(
        output_root / "qualification.json"
    )
    rebuilt = build_result(
        protocol,
        protocol_path=protocol_path,
    )
    if json.loads(canonical_text(rebuilt)) != retained:
        raise ContactPhaseQualificationError(
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
