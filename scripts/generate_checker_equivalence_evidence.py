#!/usr/bin/env python3
"""Generate the scoped Python/Lean M1 equivalence evidence.

This evidence covers the four treatment switches and the core allow/reject/
unknown truth-table cases anchored by named Lean theorems.  It explicitly does
not claim a machine-checked refinement for Python serialization, simulator
observers, proposal adaptation, floating point, or runtime dispatch.
"""

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
from proofalign.digests import digest_text  # noqa: E402
from proofalign.integrity_checker import (  # noqa: E402
    DeterministicFastChecker,
    ExactPrefixAuthorizer,
)
from proofalign.integrity_models import (  # noqa: E402
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    CoreVerdict,
    MethodArm,
    PhaseTemplate,
    StateSnapshot,
    TrustedTaskArtifact,
)
from proofalign.integrity_runtime import (  # noqa: E402
    InMemoryCommandSink,
    ProofAlignPrototype,
)


DEFAULT_OUTPUT = (
    REPO_ROOT / "experiments" / "proofalign_fast_lean_equivalence_m1.json"
)
LEAN_SOURCE = REPO_ROOT / "lean" / "ProofAlign" / "IntegrityCore.lean"
PYTHON_SOURCES = (
    REPO_ROOT / "src" / "proofalign" / "integrity_models.py",
    REPO_ROOT / "src" / "proofalign" / "integrity_checker.py",
    REPO_ROOT / "src" / "proofalign" / "integrity_runtime.py",
)
COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)


def artifact() -> TrustedTaskArtifact:
    return TrustedTaskArtifact(
        source_id="equivalence-fixture",
        source_version="1",
        artifact_digest=digest_text("equivalence-artifact"),
        instruction_digest=digest_text("pick mug by handle"),
        phases=("act",),
        initial_phase="act",
        templates=(
            PhaseTemplate(
                phase_before="act",
                expected_next_phase="act",
                skill="Pick",
                obligation_id="pick-mug",
                completion_atoms=("terminal",),
                target="mug",
                part="handle",
            ),
        ),
    )


def prototype(arm: MethodArm) -> ProofAlignPrototype:
    value = ProofAlignPrototype.create(
        arm=arm,
        artifact=artifact(),
        episode_nonce="equivalence-episode",
        authorizer=ExactPrefixAuthorizer(
            DeterministicFastChecker(), authorization_ttl_ns=100
        ),
        sink=InMemoryCommandSink(),
    )
    if value.certify_contract(now_ns=0).verdict is not CoreVerdict.ALLOW:
        raise RuntimeError("equivalence fixture contract did not certify")
    return value


def proposal() -> ActionProposal:
    return ActionProposal(
        episode_nonce="equivalence-episode",
        proposal_index=0,
        proposed_at_ns=10,
        observation_digest=digest_text("state:10:1"),
        state_epoch=0,
        command=COMMAND,
    )


def assessment(
    value: ActionProposal,
    *,
    target: str = "mug",
) -> ActionBlockAssessment:
    return ActionBlockAssessment(
        assessor_id="frozen-equivalence-action-assessor",
        assessor_version="1",
        assessor_kind=ActionAssessmentKind.FROZEN_MODEL,
        episode_nonce=value.episode_nonce,
        proposal_index=value.proposal_index,
        generated_at_ns=10,
        action_block_digest=value.action_block_digest,
        observation_digest=value.observation_digest,
        state_epoch=value.state_epoch,
        known=True,
        predicted_skill="Pick",
        target=target,
        part="handle",
        precondition_atoms=("visible:mug",),
        predicted_effect_atoms=("command_applied",),
        predicted_violation_atoms=(),
    )


def execution_contract(
    value: ActionProposal,
    semantic: ActionBlockAssessment,
) -> BlockExecutionContract:
    return BlockExecutionContract(
        issuer_id="equivalence-contract-compiler",
        issuer_version="1",
        episode_nonce=value.episode_nonce,
        proposal_index=value.proposal_index,
        issued_at_ns=10,
        action_block_digest=value.action_block_digest,
        assessment_digest=semantic.assessment_digest,
        observation_digest=value.observation_digest,
        state_epoch=value.state_epoch,
        expected_effect_atoms=("command_applied",),
        forbidden_effect_atoms=("collision",),
        observation_window_steps=1,
    )


def state(*, observed_at_ns: int = 10, max_age_ns: int = 1) -> StateSnapshot:
    return StateSnapshot(
        episode_nonce="equivalence-episode",
        state_epoch=0,
        observed_at_ns=observed_at_ns,
        max_age_ns=max_age_ns,
        state_digest=digest_text(f"state:{observed_at_ns}:{max_age_ns}"),
        known=True,
    )


def authorization_case(
    arm: MethodArm,
    *,
    value: ActionProposal,
    semantic: ActionBlockAssessment,
    contract: BlockExecutionContract,
    snapshot: StateSnapshot,
    now_ns: int,
) -> dict[str, Any]:
    runtime = prototype(arm)
    authorization = runtime.authorize_exact_prefix(
        assessment=semantic,
        execution_contract=contract,
        proposal=value,
        state=snapshot,
        now_ns=now_ns,
    )
    return {
        "arm": arm.value,
        "intent_enabled": arm.intent_enabled,
        "execution_enabled": arm.execution_enabled,
        "core_verdict": authorization.verdict.value,
        "intent_verdict": authorization.intent_check.verdict.value,
        "execution_verdict": authorization.execution_check.verdict.value,
    }


def build_evidence() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for arm in MethodArm:
        block = proposal()
        nominal_assessment = assessment(block)
        nominal_contract = execution_contract(block, nominal_assessment)
        wrong_target_assessment = assessment(block, target="knife")
        wrong_target_contract = execution_contract(block, wrong_target_assessment)
        cases.extend(
            (
                {
                    "case": "nominal",
                    **authorization_case(
                        arm,
                        value=block,
                        semantic=nominal_assessment,
                        contract=nominal_contract,
                        snapshot=state(),
                        now_ns=10,
                    ),
                },
                {
                    "case": "wrong_target",
                    **authorization_case(
                        arm,
                        value=block,
                        semantic=wrong_target_assessment,
                        contract=wrong_target_contract,
                        snapshot=state(),
                        now_ns=10,
                    ),
                },
                {
                    "case": "stale_state",
                    **authorization_case(
                        arm,
                        value=block,
                        semantic=nominal_assessment,
                        contract=nominal_contract,
                        snapshot=state(observed_at_ns=1, max_age_ns=1),
                        now_ns=10,
                    ),
                },
            )
        )
    expected = {
        ("nominal", "vla_only"): ("allow", "disabled", "disabled"),
        ("nominal", "intent_only"): ("allow", "proven", "disabled"),
        ("nominal", "execution_only"): ("allow", "disabled", "proven"),
        ("nominal", "dual"): ("allow", "proven", "proven"),
        ("wrong_target", "vla_only"): ("allow", "disabled", "disabled"),
        ("wrong_target", "intent_only"): ("reject", "refuted", "disabled"),
        ("wrong_target", "execution_only"): ("allow", "disabled", "proven"),
        ("wrong_target", "dual"): ("reject", "refuted", "proven"),
        ("stale_state", "vla_only"): ("allow", "disabled", "disabled"),
        ("stale_state", "intent_only"): ("allow", "proven", "disabled"),
        ("stale_state", "execution_only"): ("unknown", "disabled", "unknown"),
        ("stale_state", "dual"): ("unknown", "proven", "unknown"),
    }
    for row in cases:
        observed = (
            row["core_verdict"],
            row["intent_verdict"],
            row["execution_verdict"],
        )
        if observed != expected[(row["case"], row["arm"])]:
            raise RuntimeError(
                f"unexpected fast-checker truth table at {row['case']}/{row['arm']}"
            )
    lean_text = LEAN_SOURCE.read_text(encoding="utf-8")
    theorem_names = (
        "intent_switch_truth_table",
        "execution_switch_truth_table",
        "dual_dispatch_requires_intent_authorization",
        "dual_dispatch_requires_execution_authorization",
        "execution_arm_dispatches_exact_command",
        "no_phase_advance_without_checked_completion",
        "execution_enabled_phase_advance_requires_alignment",
        "phase_advance_requires_contract_completion",
    )
    missing = [name for name in theorem_names if f"theorem {name}" not in lean_text]
    if missing:
        raise RuntimeError(f"Lean theorem anchors are missing: {missing}")
    return {
        "schema": "proofalign.fast-lean-equivalence-evidence.v1",
        "evidence_id": "proofalign-fast-lean-core-switch-evidence-m1-20260724",
        "outcomes_observed": False,
        "scope": {
            "covered": [
                "four MethodArm treatment switches",
                "disabled/proven/refuted/unknown layer truth-table cases",
                "named Lean invariants for dual authorization, exact execution command, and checked phase advance",
                "typed action-block/receipt/effect predicates and separate execution-alignment/contract-completion theorems",
            ],
            "not_covered": [
                "Python-to-Lean serialization refinement",
                "simulator observer or proposal-adapter correctness",
                "floating-point intervention equivalence",
                "compiled online Lean execution",
                "physical safety",
            ],
            "machine_checked_refinement_complete": False,
        },
        "bindings": {
            "lean_source": {
                "path": str(LEAN_SOURCE.relative_to(REPO_ROOT)),
                "sha256": file_sha256(LEAN_SOURCE),
                "theorems": list(theorem_names),
            },
            "python_sources": {
                str(path.relative_to(REPO_ROOT)): file_sha256(path)
                for path in PYTHON_SOURCES
            },
        },
        "truth_table_case_count": len(cases),
        "truth_table_cases": cases,
        "lean_build_required": True,
        "all_scoped_cases_match": True,
    }


def canonical_text(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected = canonical_text(build_evidence())
    if args.check:
        try:
            observed = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"cannot read equivalence evidence: {exc}", file=sys.stderr)
            return 2
        if observed != expected:
            print(
                f"equivalence evidence is stale: {args.output}",
                file=sys.stderr,
            )
            return 2
        print(f"equivalence evidence is current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
