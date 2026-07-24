from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign import MethodArm, ProofAlignPrototype
from proofalign.digests import digest_text
from proofalign.integrity_checker import DeterministicFastChecker, ExactPrefixAuthorizer
from proofalign.integrity_intervention import (
    ProjectCommandIntervention,
    ReplanIntervention,
)
from proofalign.integrity_models import (
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    CoreVerdict,
    ExecutionEvidence,
    LayerVerdict,
    PhaseTemplate,
    StateSnapshot,
    TrustedTaskArtifact,
    command_digest,
)
from proofalign.integrity_runtime import AppliedCommand, InMemoryCommandSink


GOOD_COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
SUBSTITUTED_COMMAND = (-0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
BRAKED_COMMAND = (0.02, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)


def _artifact() -> TrustedTaskArtifact:
    return TrustedTaskArtifact(
        source_id="trusted-fixture-registry",
        source_version="1",
        artifact_digest=digest_text("fixture-task-artifact"),
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
        hard_invariants=("no_collision",),
    )


def _prototype(arm: MethodArm) -> tuple[ProofAlignPrototype, InMemoryCommandSink]:
    sink = InMemoryCommandSink()
    prototype = ProofAlignPrototype.create(
        arm=arm,
        artifact=_artifact(),
        episode_nonce="episode-integrity-v3",
        authorizer=ExactPrefixAuthorizer(
            DeterministicFastChecker(),
            authorization_ttl_ns=50,
        ),
        sink=sink,
    )
    assert prototype.certify_contract(now_ns=10).verdict is CoreVerdict.ALLOW
    return prototype, sink


def _state(*, observed_at_ns: int = 11, max_age_ns: int = 100) -> StateSnapshot:
    return StateSnapshot(
        episode_nonce="episode-integrity-v3",
        state_epoch=0,
        observed_at_ns=observed_at_ns,
        max_age_ns=max_age_ns,
        state_digest=digest_text(f"state:{observed_at_ns}:{max_age_ns}"),
        known=True,
    )


def _proposal(
    *,
    index: int = 0,
    state: StateSnapshot | None = None,
    command: tuple[float, ...] = GOOD_COMMAND,
    proposed_at_ns: int | None = None,
) -> ActionProposal:
    snapshot = state or _state()
    return ActionProposal(
        episode_nonce=snapshot.episode_nonce,
        proposal_index=index,
        proposed_at_ns=12 + index if proposed_at_ns is None else proposed_at_ns,
        observation_digest=snapshot.state_digest or "",
        state_epoch=snapshot.state_epoch,
        command=command,
    )


def _assessment(
    proposal: ActionProposal,
    *,
    target: str = "mug",
    part: str = "handle",
    kind: ActionAssessmentKind = ActionAssessmentKind.FROZEN_MODEL,
    known: bool = True,
    violations: tuple[str, ...] = (),
    generated_at_ns: int | None = None,
) -> ActionBlockAssessment:
    return ActionBlockAssessment(
        assessor_id="frozen-test-action-assessor",
        assessor_version="1",
        assessor_kind=kind,
        episode_nonce=proposal.episode_nonce,
        proposal_index=proposal.proposal_index,
        generated_at_ns=(
            proposal.proposed_at_ns
            if generated_at_ns is None
            else generated_at_ns
        ),
        action_block_digest=proposal.action_block_digest,
        observation_digest=proposal.observation_digest,
        state_epoch=proposal.state_epoch,
        known=known,
        predicted_skill="Pick" if known else None,
        target=target if known else None,
        part=part if known else None,
        precondition_atoms=("visible:mug",) if known else (),
        predicted_effect_atoms=("command_applied",) if known else (),
        predicted_violation_atoms=violations if known else (),
        unknown_reason=None if known else "predictor abstained",
    )


def _execution_contract(
    proposal: ActionProposal,
    assessment: ActionBlockAssessment,
    *,
    expected: tuple[str, ...] = ("command_applied",),
    forbidden: tuple[str, ...] = ("collision",),
    issued_at_ns: int | None = None,
) -> BlockExecutionContract:
    return BlockExecutionContract(
        issuer_id="frozen-test-contract-compiler",
        issuer_version="1",
        episode_nonce=proposal.episode_nonce,
        proposal_index=proposal.proposal_index,
        issued_at_ns=(
            assessment.generated_at_ns
            if issued_at_ns is None
            else issued_at_ns
        ),
        action_block_digest=proposal.action_block_digest,
        assessment_digest=assessment.assessment_digest,
        observation_digest=proposal.observation_digest,
        state_epoch=proposal.state_epoch,
        expected_effect_atoms=expected,
        forbidden_effect_atoms=forbidden,
        observation_window_steps=1,
    )


def _authorize(
    prototype: ProofAlignPrototype,
    *,
    state: StateSnapshot | None = None,
    proposal: ActionProposal | None = None,
    assessment: ActionBlockAssessment | None = None,
    execution_contract: BlockExecutionContract | None = None,
    now_ns: int = 13,
    intervention_policy=None,
):
    snapshot = state or _state()
    block = proposal or _proposal(state=snapshot)
    semantic = assessment or _assessment(block)
    contract = execution_contract or _execution_contract(block, semantic)
    authorization = prototype.authorize_exact_prefix(
        assessment=semantic,
        execution_contract=contract,
        proposal=block,
        state=snapshot,
        now_ns=now_ns,
        intervention_policy=intervention_policy,
    )
    return authorization, block, semantic, contract


def _known_evidence(
    authorization,
    receipt,
    *,
    atoms: tuple[str, ...],
    observed_command_digest: str | None = None,
    authorization_digest: str | None = None,
    receipt_digest: str | None = None,
    violation: bool = False,
    observation_window_complete: bool = True,
) -> ExecutionEvidence:
    return ExecutionEvidence(
        authorization_digest=authorization_digest or authorization.authorization_digest,
        receipt_digest=receipt_digest or receipt.receipt_digest,
        action_block_digest=authorization.action_block_digest,
        execution_contract_digest=authorization.execution_contract_digest,
        episode_nonce=authorization.episode_nonce,
        proposal_index=authorization.proposal_index,
        observed_at_ns=receipt.applied_at_ns + 1,
        observed_command_digest=observed_command_digest or receipt.applied_command_digest,
        observed_atoms=tuple(dict.fromkeys(("command_applied", *atoms))),
        known=True,
        observation_window_complete=observation_window_complete,
        violation=violation,
    )


def test_contract_transaction_is_persistent_and_idempotent() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    first_state = prototype.monitor.state
    again = prototype.certify_contract(now_ns=20)
    assert again.verdict is CoreVerdict.ALLOW
    assert again.after_state == first_state
    assert again.contract == prototype.monitor.active_contract


@pytest.mark.parametrize(
    ("arm", "intent", "execution"),
    [
        (MethodArm.VLA_ONLY, LayerVerdict.DISABLED, LayerVerdict.DISABLED),
        (MethodArm.INTENT_ONLY, LayerVerdict.PROVEN, LayerVerdict.DISABLED),
        (MethodArm.EXECUTION_ONLY, LayerVerdict.DISABLED, LayerVerdict.PROVEN),
        (MethodArm.DUAL, LayerVerdict.PROVEN, LayerVerdict.PROVEN),
    ],
)
def test_four_arms_are_exact_two_switch_factorial(
    arm: MethodArm,
    intent: LayerVerdict,
    execution: LayerVerdict,
) -> None:
    prototype, _ = _prototype(arm)
    authorization, *_ = _authorize(prototype)
    assert authorization.verdict is CoreVerdict.ALLOW
    assert authorization.intent_check.verdict is intent
    assert authorization.execution_check.verdict is execution


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (MethodArm.VLA_ONLY, CoreVerdict.ALLOW),
        (MethodArm.INTENT_ONLY, CoreVerdict.REJECT),
        (MethodArm.EXECUTION_ONLY, CoreVerdict.ALLOW),
        (MethodArm.DUAL, CoreVerdict.REJECT),
    ],
)
def test_intent_action_layer_catches_assessed_wrong_target(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, _ = _prototype(arm)
    block = _proposal()
    wrong = _assessment(block, target="knife", part="blade")
    authorization, *_ = _authorize(
        prototype,
        proposal=block,
        assessment=wrong,
        execution_contract=_execution_contract(block, wrong),
    )
    assert authorization.verdict is expected


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (MethodArm.VLA_ONLY, CoreVerdict.ALLOW),
        (MethodArm.INTENT_ONLY, CoreVerdict.REJECT),
        (MethodArm.EXECUTION_ONLY, CoreVerdict.ALLOW),
        (MethodArm.DUAL, CoreVerdict.REJECT),
    ],
)
def test_intent_action_unknown_and_test_oracle_fail_closed_when_enabled(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, _ = _prototype(arm)
    block = _proposal()
    oracle = _assessment(block, kind=ActionAssessmentKind.ORACLE_TEST)
    authorization, *_ = _authorize(
        prototype,
        proposal=block,
        assessment=oracle,
        execution_contract=_execution_contract(block, oracle),
    )
    assert authorization.verdict is expected


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (MethodArm.VLA_ONLY, CoreVerdict.ALLOW),
        (MethodArm.INTENT_ONLY, CoreVerdict.ALLOW),
        (MethodArm.EXECUTION_ONLY, CoreVerdict.UNKNOWN),
        (MethodArm.DUAL, CoreVerdict.UNKNOWN),
    ],
)
def test_action_execution_layer_catches_stale_state(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, _ = _prototype(arm)
    stale = _state(observed_at_ns=1, max_age_ns=2)
    authorization, *_ = _authorize(prototype, state=stale, now_ns=13)
    assert authorization.verdict is expected


def test_consumer_artifacts_are_bound_to_exact_action_block() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    declared = _proposal(command=GOOD_COMMAND)
    other = _proposal(command=SUBSTITUTED_COMMAND)
    assessment = _assessment(declared)
    contract = _execution_contract(declared, assessment)
    authorization, *_ = _authorize(
        prototype,
        proposal=other,
        assessment=assessment,
        execution_contract=contract,
    )
    assert authorization.verdict is CoreVerdict.REJECT
    assert "another action block" in " ".join(
        authorization.intent_check.issues + authorization.execution_check.issues
    )


def test_assessment_and_contract_must_be_post_block_and_ordered() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    block = _proposal(proposed_at_ns=12)
    early = _assessment(block, generated_at_ns=11)
    contract = _execution_contract(block, early, issued_at_ns=10)
    authorization, *_ = _authorize(
        prototype,
        proposal=block,
        assessment=early,
        execution_contract=contract,
    )
    assert authorization.verdict is CoreVerdict.REJECT


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (MethodArm.VLA_ONLY, CoreVerdict.ALLOW),
        (MethodArm.INTENT_ONLY, CoreVerdict.ALLOW),
        (MethodArm.EXECUTION_ONLY, CoreVerdict.REJECT),
        (MethodArm.DUAL, CoreVerdict.REJECT),
    ],
)
def test_execution_layer_rejects_command_substitution_at_dispatch(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, sink = _prototype(arm)
    authorization, *_ = _authorize(prototype)
    result = prototype.dispatch(authorization, SUBSTITUTED_COMMAND, now_ns=14)
    assert result.verdict is expected
    assert len(sink.applied) == (1 if expected is CoreVerdict.ALLOW else 0)


def test_sink_side_substitution_is_attested_and_rejected() -> None:
    class SubstitutingSink:
        sink_id = "malicious-test-sink"

        def apply(self, command, *, now_ns):
            del command
            return AppliedCommand(SUBSTITUTED_COMMAND, now_ns)

    prototype = ProofAlignPrototype.create(
        arm=MethodArm.DUAL,
        artifact=_artifact(),
        episode_nonce="episode-integrity-v3",
        authorizer=ExactPrefixAuthorizer(DeterministicFastChecker()),
        sink=SubstitutingSink(),
    )
    assert prototype.certify_contract(now_ns=10).verdict is CoreVerdict.ALLOW
    authorization, *_ = _authorize(prototype)
    result = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert result.verdict is CoreVerdict.REJECT
    assert result.receipt is not None
    assert result.receipt.applied_command_digest == command_digest(SUBSTITUTED_COMMAND)


def test_filter_output_is_reauthorized_and_dispatched_exactly_once() -> None:
    prototype, sink = _prototype(MethodArm.DUAL)
    policy = ProjectCommandIntervention(
        adjusted_command=BRAKED_COMMAND,
        witness_digest=digest_text("consumer-checkable-filter-witness"),
    )
    authorization, *_ = _authorize(prototype, intervention_policy=policy)
    assert prototype.dispatch(
        authorization, GOOD_COMMAND, now_ns=14
    ).verdict is CoreVerdict.REJECT
    assert prototype.dispatch(
        authorization, BRAKED_COMMAND, now_ns=15
    ).verdict is CoreVerdict.ALLOW
    assert prototype.dispatch(
        authorization, BRAKED_COMMAND, now_ns=16
    ).verdict is CoreVerdict.REJECT
    assert len(sink.applied) == 1


def test_replan_is_an_intervention_not_a_logic_layer() -> None:
    prototype, sink = _prototype(MethodArm.DUAL)
    authorization, *_ = _authorize(
        prototype, intervention_policy=ReplanIntervention()
    )
    assert authorization.verdict is CoreVerdict.UNKNOWN
    assert prototype.dispatch(
        authorization, GOOD_COMMAND, now_ns=14
    ).verdict is CoreVerdict.REJECT
    assert sink.applied == []


def _dispatch(
    prototype: ProofAlignPrototype,
    *,
    index: int = 0,
    expected: tuple[str, ...] = ("command_applied",),
):
    snapshot = _state()
    block = _proposal(index=index, state=snapshot)
    assessment = _assessment(block)
    contract = _execution_contract(block, assessment, expected=expected)
    authorization, *_ = _authorize(
        prototype,
        state=snapshot,
        proposal=block,
        assessment=assessment,
        execution_contract=contract,
        now_ns=13 + index * 10,
    )
    dispatched = prototype.dispatch(
        authorization, authorization.final_command or (), now_ns=14 + index * 10
    )
    assert dispatched.receipt is not None
    return authorization, contract, dispatched.receipt


def test_phase_advances_only_after_bound_effect_completion() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, contract, receipt = _dispatch(prototype)
    evidence = _known_evidence(
        authorization, receipt, atoms=("holding:mug",)
    )
    result = prototype.check_effect_update(
        execution_contract=contract,
        authorization=authorization,
        receipt=receipt,
        evidence=evidence,
    )
    assert result.verdict is CoreVerdict.COMPLETE
    assert result.after_state.phase == "done"


def test_missing_expected_or_forbidden_effect_prevents_phase_advance() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, contract, receipt = _dispatch(
        prototype, expected=("gripper_moved",)
    )
    evidence = _known_evidence(
        authorization, receipt, atoms=("holding:mug", "collision")
    )
    result = prototype.check_effect_update(
        execution_contract=contract,
        authorization=authorization,
        receipt=receipt,
        evidence=evidence,
    )
    assert result.verdict is CoreVerdict.REJECT
    assert result.after_state.phase == "approach"


def test_open_observation_window_is_pending_without_consuming_proposal() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, contract, receipt = _dispatch(
        prototype, expected=("gripper_moved",)
    )
    partial = _known_evidence(
        authorization,
        receipt,
        atoms=("approaching:mug",),
        observation_window_complete=False,
    )
    before = prototype.monitor.state
    pending = prototype.check_effect_update(
        execution_contract=contract,
        authorization=authorization,
        receipt=receipt,
        evidence=partial,
    )
    assert pending.verdict is CoreVerdict.PENDING
    assert pending.after_state == before


def test_unknown_or_forged_evidence_cannot_advance_phase() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, contract, receipt = _dispatch(prototype)
    unknown = ExecutionEvidence(
        authorization_digest=authorization.authorization_digest,
        receipt_digest=receipt.receipt_digest,
        action_block_digest=authorization.action_block_digest,
        execution_contract_digest=authorization.execution_contract_digest,
        episode_nonce=authorization.episode_nonce,
        proposal_index=authorization.proposal_index,
        observed_at_ns=15,
        observed_command_digest=None,
        observed_atoms=(),
        known=False,
        observation_window_complete=False,
        unknown_reason="observer unavailable",
    )
    before = prototype.monitor.state
    result = prototype.check_effect_update(
        execution_contract=contract,
        authorization=authorization,
        receipt=receipt,
        evidence=unknown,
    )
    assert result.verdict is CoreVerdict.UNKNOWN
    assert result.after_state == before


def test_monitor_identity_tampering_breaks_receipt_chain() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, contract, receipt = _dispatch(prototype)
    evidence = _known_evidence(
        authorization, receipt, atoms=("holding:mug",)
    )
    forged = replace(
        authorization,
        monitor_state_digest=digest_text("another-monitor"),
    )
    before = prototype.monitor.state
    result = prototype.check_effect_update(
        execution_contract=contract,
        authorization=forged,
        receipt=receipt,
        evidence=evidence,
    )
    assert result.verdict is CoreVerdict.REJECT
    assert prototype.monitor.state == before


def test_method_version_isolated_from_prior_lines() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization, *_ = _authorize(prototype)
    assert authorization.method_id == "proofalign-integrity-v3"
    assert authorization.schema_version == "proofalign.integrity-core-v3"
    assert authorization.method_id not in {"ctda-v1", "ctda-v2"}
