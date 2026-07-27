#!/usr/bin/env python3
"""Generate the dispatch-free ActionBlock v3 four-arm smoke evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256  # noqa: E402
from proofalign.benchmark.four_arm_runner import (  # noqa: E402
    SharedFourArmShadowRunner,
    TypedTraceProposal,
)
from proofalign.digests import digest_text  # noqa: E402
from proofalign.integrity_models import (  # noqa: E402
    ActionAssessmentKind,
    PhaseTemplate,
    TrustedTaskArtifact,
)


DEFAULT_OUTPUT = (
    REPO_ROOT / "experiments" / "proofalign_action_block_fixed_trace_g4_smoke.json"
)
COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)


def artifact() -> TrustedTaskArtifact:
    return TrustedTaskArtifact(
        source_id="proofalign-g4-smoke-authority",
        source_version="1",
        artifact_digest=digest_text("g4-smoke-artifact"),
        instruction_digest=digest_text("pick the mug by the handle"),
        phases=("approach", "done"),
        initial_phase="approach",
        templates=(
            PhaseTemplate(
                phase_before="approach",
                expected_next_phase="done",
                skill="Pick",
                obligation_id="pick-mug",
                completion_atoms=("holding:mug",),
                target="mug",
                part="handle",
            ),
        ),
    )


def trace_step(
    index: int,
    *,
    target: str = "mug",
    part: str = "handle",
    assessor_kind: ActionAssessmentKind = ActionAssessmentKind.FROZEN_MODEL,
    stale: bool = False,
) -> TypedTraceProposal:
    proposed_at = 10 + index * 10
    state_digest = digest_text(f"g4-state:{index}")
    return TypedTraceProposal(
        episode_nonce="g4-smoke-unit",
        proposal_index=index,
        proposed_at_ns=proposed_at,
        assessed_at_ns=proposed_at,
        execution_contract_issued_at_ns=proposed_at,
        assessor_id="g4-frozen-action-assessor-fixture",
        assessor_version="1",
        assessor_kind=assessor_kind,
        predicted_skill="Pick",
        target=target,
        part=part,
        command=COMMAND,
        state_epoch=index,
        state_observed_at_ns=1 if stale else proposed_at,
        state_max_age_ns=2 if stale else 5,
        state_digest=state_digest,
        precondition_atoms=("visible:mug",),
        predicted_effect_atoms=("command_applied",),
        predicted_violation_atoms=(),
        expected_effect_atoms=("command_applied",),
        forbidden_effect_atoms=("collision",),
        observation_window_steps=1,
    )


def build_evidence() -> dict[str, Any]:
    proposals = [
        trace_step(0),
        trace_step(1, target="knife", part="blade"),
        trace_step(2, stale=True),
        trace_step(3, assessor_kind=ActionAssessmentKind.ORACLE_TEST),
    ]
    runner = SharedFourArmShadowRunner(
        artifact=artifact(),
        episode_nonce="g4-smoke-unit",
    )
    result = runner.evaluate(unit_id="g4-smoke-unit", proposals=proposals)
    by_case = {
        case: {
            row["arm"]: row["authorization_verdict"]
            for row in result["rows"]
            if row["proposal_index"] == index
        }
        for index, case in enumerate(
            ("nominal", "wrong_target", "stale_state", "oracle_provenance")
        )
    }
    expected = {
        "nominal": {
            "vla_only": "allow",
            "intent_only": "allow",
            "execution_only": "allow",
            "dual": "allow",
        },
        "wrong_target": {
            "vla_only": "allow",
            "intent_only": "reject",
            "execution_only": "allow",
            "dual": "reject",
        },
        "stale_state": {
            "vla_only": "allow",
            "intent_only": "allow",
            "execution_only": "unknown",
            "dual": "unknown",
        },
        "oracle_provenance": {
            "vla_only": "allow",
            "intent_only": "reject",
            "execution_only": "allow",
            "dual": "reject",
        },
    }
    if by_case != expected:
        raise RuntimeError(f"unexpected G4 truth table: {by_case}")
    assessment_identity = {
        index: {
            row["assessment_digest"]
            for row in result["rows"]
            if row["proposal_index"] == index
        }
        for index in range(len(proposals))
    }
    proposal_identity = {
        index: {
            row["proposal_digest"]
            for row in result["rows"]
            if row["proposal_index"] == index
        }
        for index in range(len(proposals))
    }
    identity_pass = all(
        len(assessment_identity[index]) == 1
        and len(proposal_identity[index]) == 1
        for index in range(len(proposals))
    )
    stable_result = {
        **result,
        "rows": [
            {key: value for key, value in row.items() if key != "checker_latency_ns"}
            for row in result["rows"]
        ],
    }
    return {
        "schema": "proofalign.action-block-fixed-trace-smoke.v1",
        "evidence_id": "proofalign-action-block-g4-smoke-20260724",
        "classification": (
            "g4_component_smoke_pass" if identity_pass else "g4_component_smoke_nonpass"
        ),
        "outcomes_observed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "simulator_step_count": 0,
        "dispatch_count": result["dispatch_attempt_count"],
        "claim_boundary": (
            "Synthetic ActionBlocks and frozen-assessor fixtures only; this "
            "does not qualify a real action-semantics assessor."
        ),
        "cases": by_case,
        "expected_cases": expected,
        "assessment_identity_across_arms": {
            str(index): sorted(values)
            for index, values in assessment_identity.items()
        },
        "proposal_identity_across_arms": {
            str(index): sorted(values)
            for index, values in proposal_identity.items()
        },
        "identity_pass": identity_pass,
        "trace": [proposal.export_payload() for proposal in proposals],
        "runner_result": stable_result,
        "source_bindings": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in (
                "src/proofalign/integrity_models.py",
                "src/proofalign/integrity_checker.py",
                "src/proofalign/integrity_runtime.py",
                "src/proofalign/benchmark/four_arm_runner.py",
                "lean/ProofAlign/IntegrityCore.lean",
                "scripts/run_action_block_fixed_trace_gate.py",
            )
        },
    }


def canonical_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical_text(build_evidence())
    if args.check:
        if not args.output.is_file():
            raise SystemExit(f"G4 evidence is missing: {args.output}")
        if args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"G4 evidence is stale: {args.output}")
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
