#!/usr/bin/env python3
"""Run or validate a frozen v10 physical-sufficiency clean pilot."""

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
from proofalign.physical_sufficiency_semantic import (  # noqa: E402
    PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA,
)
from scripts import run_l2_execution_attack_eval_v10 as online  # noqa: E402
from scripts import run_risk_selective_clean_pilot as inherited  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.physical-sufficiency-clean-pilot-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.physical-sufficiency-clean-pilot-evidence.v1"
)
EXPECTED_RUNNER = online.RUNNER_VARIANT
AUTHORIZED_STATUS = (
    "authorized_v10_physical_sufficiency_clean_pilot"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_physical_sufficiency_fresh15_cotenant_protocol.json"
)


class PhysicalSufficiencyCleanPilotError(RuntimeError):
    """Raised when the v10 clean pilot leaves its frozen scope."""


def _v10_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    audit_count = 0
    unchanged = 0
    physical_rejects = 0
    physical_screened_unknowns = 0
    advisory_atoms = 0
    advisory_effect_replans = 0
    prompt_mismatches = 0
    metadata_mismatches = 0
    first_blocks: dict[str, dict[str, str]] = {}
    schedule_pairs = {
        row["episode_id"]: row["base_pair_id"]
        for row in protocol["schedule"]
    }

    for artifact in evidence["episodes"]:
        episode = load_json_object(REPO_ROOT / artifact["path"])
        metadata = episode["metadata"]
        arm = str(metadata["four_arm_label"])
        l1_enabled = arm in {"semantic_only", "dual"}
        expected_metadata = {
            "risk_selective_semantic_active": l1_enabled,
            "full_task_policy_prompt_preserved": l1_enabled,
            "nominal_action_noninterference_active": l1_enabled,
            "soft_semantic_constraints_advisory": l1_enabled,
            "online_progress_projection_active": False,
            "release_prefix_progress_contract_active": False,
            "horizon_consistent_release_active": False,
            "physical_sufficiency_screen_active": l1_enabled,
            "articulation_state_unknown_advisory": l1_enabled,
            "target_not_held_after_move_advisory": l1_enabled,
        }
        metadata_mismatches += sum(
            metadata.get(key) != expected
            for key, expected in expected_metadata.items()
        )
        frames = episode["observation_frame_audits"]
        if not frames:
            raise PhysicalSufficiencyCleanPilotError(
                f"episode has no policy frame: {artifact['episode_id']}"
            )
        pair = schedule_pairs[artifact["episode_id"]]
        first_blocks.setdefault(pair, {})[arm] = frames[0][
            "policy_action_chunk_sha256"
        ]
        if not l1_enabled:
            continue
        for frame in frames:
            audit = frame.get("online_progress_projection_v3")
            if (
                not isinstance(audit, Mapping)
                or audit.get("schema")
                != PHYSICAL_SUFFICIENCY_AUDIT_SCHEMA
            ):
                raise PhysicalSufficiencyCleanPilotError(
                    "v10 L1 frame lacks a physical-sufficiency audit"
                )
            audit_count += 1
            unchanged += int(
                audit["returned_source_policy_chunk_sha256"]
                == audit["returned_action_chunk_sha256"]
            )
            risk = audit["risk_selective"]
            physical = risk.get("physical_risk_atoms", ())
            advisory = risk.get("advisory_semantic_atoms", ())
            unknowns = risk.get(
                "advisory_semantic_unknown_reasons", ()
            )
            if not all(
                isinstance(values, (list, tuple))
                for values in (physical, advisory, unknowns)
            ):
                raise PhysicalSufficiencyCleanPilotError(
                    "v10 audit partition is malformed"
                )
            advisory_atoms += len(advisory)
            physical_screened_unknowns += len(unknowns)
            physical_rejects += int(
                bool(physical)
                and audit.get(
                    "eligible_selected_source_candidate_index"
                )
                is None
            )
            decision = frame.get("semantic_decision")
            if isinstance(decision, Mapping):
                proposal = decision.get("proposal")
                if isinstance(proposal, Mapping):
                    prompt_mismatches += int(
                        proposal.get("exact_policy_prompt_digest")
                        != frame.get("exact_policy_prompt_digest")
                    )
            transaction = frame.get("semantic_transaction")
            if isinstance(transaction, Mapping):
                issues = transaction.get("effect_issues", ())
                if isinstance(issues, list):
                    advisory_effect_replans += sum(
                        str(issue).startswith("advisory_replan:")
                        for issue in issues
                    )

    paired_first = sum(
        len(values) == 4 and len(set(values.values())) == 1
        for values in first_blocks.values()
    )
    metrics = {
        "physical_sufficiency_audit_count": audit_count,
        "unchanged_source_action_block_count": unchanged,
        "physical_risk_reject_count": physical_rejects,
        "physical_screened_semantic_unknown_count": (
            physical_screened_unknowns
        ),
        "advisory_semantic_atom_count": advisory_atoms,
        "advisory_effect_replan_count": advisory_effect_replans,
        "prompt_digest_mismatch_count": prompt_mismatches,
        "physical_sufficiency_metadata_mismatch_count": (
            metadata_mismatches
        ),
        "paired_first_action_block_match_count": paired_first,
        "paired_workload_count": len(first_blocks),
    }
    gates = protocol["v10_gates"]
    gate_results = {
        "all_l1_source_blocks_unchanged": audit_count == unchanged,
        "prompt_digest_matches": prompt_mismatches == 0,
        "physical_sufficiency_metadata_matches": (
            metadata_mismatches == 0
        ),
        "paired_first_action_blocks_match": (
            paired_first
            == gates["expected_paired_first_action_block_match_count"]
        ),
        "paired_workload_count": (
            len(first_blocks)
            == gates["expected_paired_workload_count"]
        ),
    }
    return metrics, gate_results


@contextmanager
def _patched_inherited() -> Iterator[None]:
    originals = (
        inherited.PROTOCOL_SCHEMA,
        inherited.EVIDENCE_SCHEMA,
        inherited.EXPECTED_RUNNER,
        inherited.AUTHORIZED_STATUS,
        inherited.DEFAULT_PROTOCOL,
        inherited.online,
        inherited._risk_metrics,
    )
    inherited.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    inherited.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    inherited.EXPECTED_RUNNER = EXPECTED_RUNNER
    inherited.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    inherited.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    inherited.online = online
    inherited._risk_metrics = _v10_metrics
    try:
        yield
    finally:
        (
            inherited.PROTOCOL_SCHEMA,
            inherited.EVIDENCE_SCHEMA,
            inherited.EXPECTED_RUNNER,
            inherited.AUTHORIZED_STATUS,
            inherited.DEFAULT_PROTOCOL,
            inherited.online,
            inherited._risk_metrics,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.execute(
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
    with _patched_inherited():
        return inherited.validate_results(
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
