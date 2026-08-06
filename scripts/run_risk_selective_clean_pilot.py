#!/usr/bin/env python3
"""Run or validate a frozen v9 risk-selective clean pilot."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_contact_phase_pick_up_clean_pilot as generic  # noqa: E402
from scripts import run_l2_execution_attack_eval_v9 as online  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402


PROTOCOL_SCHEMA = "proofalign.risk-selective-clean-pilot-protocol.v1"
EVIDENCE_SCHEMA = "proofalign.risk-selective-clean-pilot-evidence.v1"
EXPECTED_RUNNER = online.RUNNER_VARIANT
AUTHORIZED_STATUS = "authorized_v9_risk_selective_clean_pilot"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_risk_selective_fresh15_cotenant_protocol.json"
)


class RiskSelectiveCleanPilotError(RuntimeError):
    """Raised when the v9 clean pilot leaves its frozen scope."""


@contextmanager
def _patched_generic() -> Iterator[None]:
    original_schema = generic.PROTOCOL_SCHEMA
    original_evidence = generic.EVIDENCE_SCHEMA
    original_runner = generic.EXPECTED_RUNNER
    original_online = generic.online
    original_validate = generic.validate_protocol

    def validate_v9(
        protocol: Mapping[str, Any],
        *,
        protocol_path: Path,
    ) -> None:
        if (
            protocol.get("schema") != PROTOCOL_SCHEMA
            or protocol.get("status") != AUTHORIZED_STATUS
        ):
            raise RiskSelectiveCleanPilotError(
                "unsupported or unauthorized v9 clean pilot"
            )
        normalized = dict(protocol)
        normalized["status"] = (
            "authorized_v8_contact_phase_clean_pilot"
        )
        original_validate(
            normalized,
            protocol_path=protocol_path,
        )

    generic.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    generic.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    generic.EXPECTED_RUNNER = EXPECTED_RUNNER
    generic.online = online
    generic.validate_protocol = validate_v9
    try:
        yield
    finally:
        generic.PROTOCOL_SCHEMA = original_schema
        generic.EVIDENCE_SCHEMA = original_evidence
        generic.EXPECTED_RUNNER = original_runner
        generic.online = original_online
        generic.validate_protocol = original_validate


def _risk_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    audits = 0
    unchanged = 0
    physical_rejects = 0
    advisory_atoms = 0
    prompt_digest_mismatches = 0
    metadata_mismatches = 0
    advisory_effect_replans = 0
    first_blocks: dict[str, dict[str, str]] = {}

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
        }
        metadata_mismatches += sum(
            metadata.get(key) != expected
            for key, expected in expected_metadata.items()
        )
        frames = episode["observation_frame_audits"]
        if not frames:
            raise RiskSelectiveCleanPilotError(
                f"episode has no policy frame: {artifact['episode_id']}"
            )
        pair_id = next(
            row["base_pair_id"]
            for row in protocol["schedule"]
            if row["episode_id"] == artifact["episode_id"]
        )
        first_blocks.setdefault(pair_id, {})[arm] = frames[0][
            "policy_action_chunk_sha256"
        ]
        if not l1_enabled:
            continue
        for frame in frames:
            audit = frame.get("online_progress_projection_v3")
            if not isinstance(audit, Mapping):
                raise RiskSelectiveCleanPilotError(
                    "v9 L1 frame lacks risk-selective audit"
                )
            if (
                audit.get("schema")
                != "proofalign.semantic-risk-selective-selection.v9"
            ):
                raise RiskSelectiveCleanPilotError(
                    "v9 L1 frame has a predecessor audit schema"
                )
            audits += 1
            unchanged += int(
                audit.get("returned_source_policy_chunk_sha256")
                == audit.get("returned_action_chunk_sha256")
            )
            risk = audit.get("risk_selective")
            if not isinstance(risk, Mapping):
                raise RiskSelectiveCleanPilotError(
                    "risk-selective audit partition is absent"
                )
            physical = risk.get("physical_risk_atoms", ())
            advisory = risk.get("advisory_semantic_atoms", ())
            if not isinstance(physical, (list, tuple)) or not isinstance(
                advisory, (list, tuple)
            ):
                raise RiskSelectiveCleanPilotError(
                    "risk-selective atom partition is malformed"
                )
            advisory_atoms += len(advisory)
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
                    prompt_digest_mismatches += int(
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

    paired_first_blocks = sum(
        len(values) == 4 and len(set(values.values())) == 1
        for values in first_blocks.values()
    )
    metrics = {
        "risk_selective_audit_count": audits,
        "unchanged_source_action_block_count": unchanged,
        "physical_risk_reject_count": physical_rejects,
        "advisory_semantic_atom_count": advisory_atoms,
        "advisory_effect_replan_count": advisory_effect_replans,
        "prompt_digest_mismatch_count": prompt_digest_mismatches,
        "risk_metadata_mismatch_count": metadata_mismatches,
        "paired_first_action_block_match_count": paired_first_blocks,
        "paired_workload_count": len(first_blocks),
    }
    gates = protocol["v9_gates"]
    gate_results = {
        "all_l1_source_blocks_unchanged": audits == unchanged,
        "prompt_digest_matches": prompt_digest_mismatches == 0,
        "risk_metadata_matches": metadata_mismatches == 0,
        "paired_first_action_blocks_match": (
            paired_first_blocks
            == gates["expected_paired_first_action_block_match_count"]
        ),
        "paired_workload_count": (
            len(first_blocks)
            == gates["expected_paired_workload_count"]
        ),
    }
    return metrics, gate_results


def _enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    metrics, gate_results = _risk_metrics(protocol, evidence)
    combined_gates = {
        **evidence["gate_results"],
        **{
            f"v9_{key}": value
            for key, value in gate_results.items()
        },
    }
    complete = all(combined_gates.values())
    return {
        **evidence,
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["complete_classification"]
            if complete
            else protocol["incomplete_classification"]
        ),
        "pilot_complete": complete,
        "aggregate": {
            **evidence["aggregate"],
            **metrics,
        },
        "gate_results": combined_gates,
        "method_claim": (
            "risk-triggered nominal-policy non-interference"
        ),
    }


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_generic():
        return generic.preflight(
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
    with _patched_generic():
        evidence = generic.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    enriched = _enrich(protocol, evidence)
    output_root = REPO_ROOT / protocol["fresh_output_root"]
    saber_io.atomic_json(output_root / "pilot_evidence.json", enriched)
    manifest_path = output_root / "run_manifest.json"
    manifest = load_json_object(manifest_path)
    manifest["classification"] = enriched["classification"]
    saber_io.atomic_json(manifest_path, manifest)
    p0b.write_checksums(output_root)
    return enriched


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_generic():
        generic.validate_protocol(
            protocol,
            protocol_path=protocol_path,
        )
        output_root = generic._output_root(protocol)
        p0b.read_checksums(output_root)
        retained = load_json_object(
            output_root / "pilot_evidence.json"
        )
        core = generic._build_evidence(
            protocol,
            protocol_path=protocol_path,
            output_root=output_root,
            preflight_report=retained["preflight"],
            device_mapping=retained["device_mapping"],
        )
    rebuilt = _enrich(protocol, core)
    if json.loads(canonical_text(rebuilt)) != retained:
        raise RiskSelectiveCleanPilotError(
            "v9 clean pilot evidence differs from recomputation"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    with _patched_generic():
        expected = [
            spec.episode_id
            for spec in generic.build_specs(protocol)
        ]
    if (
        manifest.get("status") != "complete"
        or manifest.get("completed_episode_ids") != expected
    ):
        raise RiskSelectiveCleanPilotError(
            "v9 clean pilot manifest is not terminal complete"
        )
    return retained


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
