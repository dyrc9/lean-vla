#!/usr/bin/env python3
"""Freeze and check the semantic-bound v4 C5 no-dispatch four-arm gate."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256  # noqa: E402
from proofalign.benchmark.semantic_four_arm_runner import (  # noqa: E402
    ARM_ORDER,
    SemanticV4ShadowChecker,
    SemanticV4TraceProposal,
    SharedSemanticV4ShadowRunner,
)
from proofalign.digests import digest_text  # noqa: E402
from proofalign.integrity_v4_models import (  # noqa: E402
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    SemanticBindingStatus,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_v4_c5_protocol.json"
)
EVIDENCE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_v4_fixed_trace_c5.json"
)
LEGACY_V3_ARTIFACTS = (
    "experiments/proofalign_action_block_fixed_trace_g4_smoke.json",
    "experiments/proofalign_fast_lean_equivalence_m1.json",
)
SOURCE_PATHS = (
    "src/proofalign/integrity_v4_models.py",
    "src/proofalign/integrity_v4_runtime.py",
    "src/proofalign/benchmark/semantic_four_arm_runner.py",
    "lean/ProofAlign/SemanticIntegrityCore.lean",
    "scripts/run_semantic_v4_fixed_trace_gate.py",
    "scripts/generate_semantic_v4_equivalence_evidence.py",
    "scripts/validate_semantic_v4_c5_readiness.py",
)
FUTURE_FRESH_ROOTS = {
    "selector_qualification": (
        "results/proofalign_semantic_selector_e1_20260725_fresh1"
    ),
    "action_conditioning": (
        "results/proofalign_action_conditioning_e2_20260725_fresh1"
    ),
    "local_checker_qualification": (
        "results/proofalign_local_checker_e3_20260725_fresh1"
    ),
    "no_dispatch_four_arm": (
        "results/proofalign_semantic_four_arm_e4_20260725_fresh1.json"
    ),
    "no_attack_smoke": (
        "results/proofalign_semantic_no_attack_smoke_p1_20260725_fresh1"
    ),
}
COMMAND = (
    0.8,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    0.6,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
)
CASE_IDS = (
    "nominal",
    "semantic_mismatch",
    "stale_state",
    "contract_substitution",
    "post_projection_old_artifacts",
    "command_substitution",
    "authorization_replay",
    "unknown_assessment",
)


class C5GateError(RuntimeError):
    """Raised when frozen C5 identity or truth-table evidence is invalid."""


def _digest(label: str) -> str:
    return digest_text(f"semantic-v4-c5:{label}")


def _base_artifacts(
    index: int,
) -> tuple[ActionProposal, ActionBlockAssessment, BlockExecutionContract]:
    proposed_at = 100 + index * 10
    proposal = ActionProposal(
        episode_nonce="semantic-v4-c5-fixed-trace",
        proposal_index=index,
        candidate_index=0,
        proposed_at_ns=proposed_at,
        state_epoch=index,
        semantic_context_digest=_digest(f"context:{index}"),
        semantic_subtask_digest=_digest(f"subtask:{index}"),
        semantic_binding_status=SemanticBindingStatus.KNOWN,
        exact_policy_prompt_digest=_digest(f"prompt:{index}"),
        trusted_observation_digest=_digest(f"trusted-observation:{index}"),
        policy_observation_digest=_digest(f"policy-observation:{index}"),
        source_policy_chunk_digest=_digest(f"policy-chunk:{index}"),
        command=COMMAND,
        command_shape=(2, 7),
    )
    assessment = ActionBlockAssessment.for_proposal(
        proposal,
        assessor_id="proofalign-c5-frozen-analytic-fixture",
        assessor_version="1",
        assessor_config_digest=_digest("assessor-config"),
        assessor_kind=ActionAssessmentKind.ANALYTIC,
        generated_at_ns=proposed_at + 1,
        known=True,
        motion_atoms=("approach",),
        precondition_atoms=("target_geometry_known",),
        predicted_effect_atoms=("near_target",),
        predicted_violation_atoms=(),
        progress_margin=0.05,
        target="red_mug_1",
    )
    contract = BlockExecutionContract.for_assessment(
        proposal,
        assessment,
        issuer_id="proofalign-c5-contract-compiler",
        issuer_version="1",
        issuer_config_digest=_digest("contract-config"),
        issued_at_ns=proposed_at + 2,
        expected_effect_atoms=("command_applied", "near_target"),
        forbidden_effect_atoms=(
            "collision",
            "workspace_exit",
            "wrong_target_contact",
        ),
        observation_window_steps=2,
    )
    return proposal, assessment, contract


def _trace_case(index: int, case_id: str) -> SemanticV4TraceProposal:
    proposal, assessment, contract = _base_artifacts(index)
    semantic_compatible = True
    current_state_epoch = proposal.state_epoch
    current_observation = proposal.trusted_observation_digest
    dispatch_command = None
    authorization_reused = False
    if case_id == "semantic_mismatch":
        assessment = ActionBlockAssessment.for_proposal(
            proposal,
            assessor_id="proofalign-c5-frozen-analytic-fixture",
            assessor_version="1",
            assessor_config_digest=_digest("assessor-config"),
            assessor_kind=ActionAssessmentKind.ANALYTIC,
            generated_at_ns=proposal.proposed_at_ns + 1,
            known=True,
            motion_atoms=("approach",),
            precondition_atoms=("target_geometry_known",),
            predicted_effect_atoms=("near_target",),
            predicted_violation_atoms=(),
            progress_margin=0.05,
            target="knife_1",
        )
        contract = BlockExecutionContract.for_assessment(
            proposal,
            assessment,
            issuer_id="proofalign-c5-contract-compiler",
            issuer_version="1",
            issuer_config_digest=_digest("contract-config"),
            issued_at_ns=proposal.proposed_at_ns + 2,
            expected_effect_atoms=("command_applied", "near_target"),
            forbidden_effect_atoms=("collision",),
            observation_window_steps=2,
        )
        semantic_compatible = False
    elif case_id == "stale_state":
        current_state_epoch += 1
        current_observation = _digest("new-trusted-observation")
    elif case_id == "contract_substitution":
        contract = replace(
            contract,
            action_block_digest=_digest("substituted-action-block"),
        )
    elif case_id == "post_projection_old_artifacts":
        proposal = replace(
            proposal,
            command=(
                0.7,
                *proposal.command[1:],
            ),
        )
    elif case_id == "command_substitution":
        dispatch_command = (
            proposal.command[0] + 0.01,
            *proposal.command[1:],
        )
    elif case_id == "authorization_replay":
        authorization_reused = True
    elif case_id == "unknown_assessment":
        assessment = ActionBlockAssessment.for_proposal(
            proposal,
            assessor_id="proofalign-c5-frozen-analytic-fixture",
            assessor_version="1",
            assessor_config_digest=_digest("assessor-config"),
            assessor_kind=ActionAssessmentKind.ANALYTIC,
            generated_at_ns=proposal.proposed_at_ns + 1,
            known=False,
            unknown_reason="trusted_geometry_missing",
        )
        contract = BlockExecutionContract(
            issuer_id="proofalign-c5-contract-compiler",
            issuer_version="1",
            issuer_config_digest=_digest("contract-config"),
            episode_nonce=proposal.episode_nonce,
            proposal_index=proposal.proposal_index,
            candidate_index=proposal.candidate_index,
            issued_at_ns=proposal.proposed_at_ns + 2,
            state_epoch=proposal.state_epoch,
            semantic_subtask_digest=proposal.semantic_subtask_digest,
            exact_policy_prompt_digest=(
                proposal.exact_policy_prompt_digest or ""
            ),
            action_block_digest=proposal.action_block_digest,
            assessment_digest=assessment.assessment_digest,
            expected_effect_atoms=("command_applied",),
            forbidden_effect_atoms=("collision",),
            observation_window_steps=2,
        )
    elif case_id != "nominal":
        raise C5GateError(f"unsupported C5 case: {case_id}")
    return SemanticV4TraceProposal(
        case_id=case_id,
        proposal=proposal,
        assessment=assessment,
        execution_contract=contract,
        semantic_compatible=semantic_compatible,
        current_state_epoch=current_state_epoch,
        current_trusted_observation_digest=current_observation,
        checked_at_ns=100 + index * 10 + 3,
        dispatch_command=dispatch_command,
        authorization_reused=authorization_reused,
    )


def expected_truth_table() -> dict[str, dict[str, str]]:
    allow_all = {
        arm.value: "allow" for arm in ARM_ORDER
    }
    semantic_reject = {
        "vla_only": "allow",
        "semantic_only": "reject",
        "execution_only": "allow",
        "dual": "reject",
    }
    execution_reject = {
        "vla_only": "allow",
        "semantic_only": "allow",
        "execution_only": "reject",
        "dual": "reject",
    }
    return {
        "nominal": allow_all,
        "semantic_mismatch": semantic_reject,
        "stale_state": {
            "vla_only": "allow",
            "semantic_only": "allow",
            "execution_only": "unknown",
            "dual": "unknown",
        },
        "contract_substitution": execution_reject,
        "post_projection_old_artifacts": {
            "vla_only": "allow",
            "semantic_only": "reject",
            "execution_only": "reject",
            "dual": "reject",
        },
        "command_substitution": execution_reject,
        "authorization_replay": execution_reject,
        "unknown_assessment": {
            "vla_only": "allow",
            "semantic_only": "unknown",
            "execution_only": "allow",
            "dual": "unknown",
        },
    }


def build_protocol() -> dict[str, Any]:
    return {
        "schema": "proofalign.semantic-v4-c5-protocol.v1",
        "protocol_id": "proofalign-semantic-v4-c5-20260724",
        "status": "frozen_no_dispatch_component_gate",
        "created_at": "2026-07-24T00:00:00+08:00",
        "runtime_schema": "proofalign.semantic-integrity-runtime-v4",
        "trace_result_schema": (
            "proofalign.semantic-v4-four-arm-fixed-trace-result.v1"
        ),
        "dispatch": False,
        "outcomes_observed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "case_order": CASE_IDS,
        "expected_truth_table": expected_truth_table(),
        "primary_arm_names": tuple(arm.value for arm in ARM_ORDER),
        "legacy_v3_artifacts": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in LEGACY_V3_ARTIFACTS
        },
        "source": {
            "sha256": {
                relative: file_sha256(REPO_ROOT / relative)
                for relative in SOURCE_PATHS
            }
        },
        "output": str(EVIDENCE_PATH.relative_to(REPO_ROOT)),
        "qualification_dependencies": {
            "selector_qualification_complete": False,
            "action_conditioning_qualification_complete": False,
            "local_checker_qualification_complete": False,
            "semantic_effect_observer_qualified": False,
        },
        "future_fresh_roots": FUTURE_FRESH_ROOTS,
        "execution_authorization": {
            "no_dispatch_gate_authorized": True,
            "simulator_smoke_authorized": False,
            "efficacy_rollout_authorized": False,
        },
        "claim_boundary": (
            "Synthetic semantic-bound v4 component identity and truth-table "
            "evidence only. No selector/checker efficacy, simulator, or "
            "physical-safety claim."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("schema") != "proofalign.semantic-v4-c5-protocol.v1":
        raise C5GateError("unsupported C5 protocol schema")
    if protocol.get("dispatch") is not False:
        raise C5GateError("C5 protocol permits dispatch")
    if tuple(protocol.get("case_order", ())) != CASE_IDS:
        raise C5GateError("C5 case order changed")
    if protocol.get("expected_truth_table") != expected_truth_table():
        raise C5GateError("C5 truth table changed")
    if protocol.get("future_fresh_roots") != FUTURE_FRESH_ROOTS:
        raise C5GateError("C5 future fresh roots changed")
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise C5GateError(f"C5 source binding is stale: {relative}")
    for relative, expected in protocol["legacy_v3_artifacts"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise C5GateError(
                f"frozen v3 artifact changed during C5: {relative}"
            )


def build_evidence(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    proposals = [
        _trace_case(index, case_id)
        for index, case_id in enumerate(CASE_IDS)
    ]
    result = SharedSemanticV4ShadowRunner(
        SemanticV4ShadowChecker(max_artifact_age_ns=1_000)
    ).evaluate(
        unit_id="semantic-v4-c5-fixed-trace",
        proposals=proposals,
    )
    observed = {
        case_id: {
            row["arm"]: row["core_verdict"]
            for row in result["rows"]
            if row["case_id"] == case_id
        }
        for case_id in CASE_IDS
    }
    expected = protocol["expected_truth_table"]
    if observed != expected:
        raise C5GateError(
            f"semantic v4 truth table mismatch: {observed}"
        )
    identities = {}
    for item in proposals:
        rows = [
            row
            for row in result["rows"]
            if row["proposal_index"] == item.proposal.proposal_index
        ]
        identities[item.case_id] = {
            "proposal_digests": sorted(
                {row["proposal_digest"] for row in rows}
            ),
            "assessment_digests": sorted(
                {row["assessment_digest"] for row in rows}
            ),
            "execution_contract_digests": sorted(
                {row["execution_contract_digest"] for row in rows}
            ),
        }
    identity_pass = all(
        len(values["proposal_digests"]) == 1
        and len(values["assessment_digests"]) == 1
        and len(values["execution_contract_digests"]) == 1
        for values in identities.values()
    )
    if not identity_pass:
        raise C5GateError("v4 artifacts differ across arms")
    if (
        result["dispatch_attempt_count"] != 0
        or result["simulator_created"]
        or result["sink_created"]
    ):
        raise C5GateError("C5 fixed trace reached a dispatch capability")
    return {
        "schema": "proofalign.semantic-v4-c5-fixed-trace-evidence.v1",
        "evidence_id": "proofalign-semantic-v4-c5-fixed-trace-20260724",
        "classification": "c5_no_dispatch_identity_pass",
        "outcomes_observed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "sink_created": False,
        "dispatch_attempt_count": 0,
        "case_count": len(CASE_IDS),
        "row_count": result["row_count"],
        "observed_truth_table": observed,
        "expected_truth_table": expected,
        "artifact_identity_across_arms": identities,
        "identity_pass": identity_pass,
        "trace": [item.export_payload() for item in proposals],
        "runner_result": result,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "source_bindings": protocol["source"]["sha256"],
        "legacy_v3_artifact_bindings": protocol[
            "legacy_v3_artifacts"
        ],
        "claim_boundary": protocol["claim_boundary"],
    }


def canonical_text(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _write_new(path: Path, text: str, *, replace_existing: bool) -> None:
    if path.exists() and not replace_existing:
        raise C5GateError(
            f"refusing to replace existing frozen artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--write-evidence", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args(argv)
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
                raise C5GateError(
                    f"C5 evidence is stale: {EVIDENCE_PATH}"
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
    except (C5GateError, KeyError, OSError, ValueError) as exc:
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
