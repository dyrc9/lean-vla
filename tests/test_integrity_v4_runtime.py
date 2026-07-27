from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.digests import digest_text
from proofalign.integrity_v4_models import (
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    IntegrityV4Error,
    PrefixExecutionEvidence,
    SemanticBindingStatus,
)
from proofalign.integrity_v4_runtime import (
    AppliedAction,
    FreshPrefixAuthorizer,
    InMemoryActionSink,
    SingleUsePrefixDispatchBoundary,
    TransactionVerdict,
)


def _digest(label: str) -> str:
    return digest_text(label)


def _artifacts(
    *, command: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4)
) -> tuple[ActionProposal, ActionBlockAssessment, BlockExecutionContract]:
    proposal = ActionProposal(
        episode_nonce="episode-v4-runtime",
        proposal_index=3,
        candidate_index=0,
        proposed_at_ns=50,
        state_epoch=7,
        semantic_context_digest=_digest("context"),
        semantic_subtask_digest=_digest("subtask"),
        semantic_binding_status=SemanticBindingStatus.KNOWN,
        exact_policy_prompt_digest=_digest("prompt"),
        trusted_observation_digest=_digest("trusted-observation"),
        policy_observation_digest=_digest("policy-observation"),
        source_policy_chunk_digest=_digest("chunk"),
        command=command,
        command_shape=(2, 2),
    )
    assessment = ActionBlockAssessment.for_proposal(
        proposal,
        assessor_id="analytic-checker",
        assessor_version="1",
        assessor_config_digest=_digest("checker-config"),
        assessor_kind=ActionAssessmentKind.ANALYTIC,
        generated_at_ns=51,
        known=True,
        motion_atoms=("approach",),
        predicted_effect_atoms=("near_target",),
        progress_margin=0.1,
        target="target",
    )
    contract = BlockExecutionContract.for_assessment(
        proposal,
        assessment,
        issuer_id="contract-compiler",
        issuer_version="1",
        issuer_config_digest=_digest("contract-config"),
        issued_at_ns=52,
        expected_effect_atoms=("command_applied", "near_target"),
        forbidden_effect_atoms=("collision",),
        observation_window_steps=2,
    )
    return proposal, assessment, contract


def _authorization(
    *,
    ttl_ns: int = 100,
):
    proposal, assessment, contract = _artifacts()
    authorization = FreshPrefixAuthorizer(
        authorization_ttl_ns=ttl_ns,
        max_artifact_age_ns=100,
    ).authorize(
        proposal,
        assessment,
        contract,
        current_state_epoch=proposal.state_epoch,
        current_trusted_observation_digest=(
            proposal.trusted_observation_digest
        ),
        now_ns=60,
    )
    return proposal, assessment, contract, authorization


def test_authorizer_rejects_stale_state_and_observation() -> None:
    proposal, assessment, contract = _artifacts()
    authorizer = FreshPrefixAuthorizer()

    with pytest.raises(IntegrityV4Error, match="state epoch"):
        authorizer.authorize(
            proposal,
            assessment,
            contract,
            current_state_epoch=proposal.state_epoch + 1,
            current_trusted_observation_digest=(
                proposal.trusted_observation_digest
            ),
            now_ns=60,
        )
    with pytest.raises(IntegrityV4Error, match="trusted observation"):
        authorizer.authorize(
            proposal,
            assessment,
            contract,
            current_state_epoch=proposal.state_epoch,
            current_trusted_observation_digest=_digest("new-observation"),
            now_ns=60,
        )


def test_projected_block_cannot_reuse_old_assessment_or_contract() -> None:
    nominal, old_assessment, old_contract = _artifacts()
    projected = replace(
        nominal,
        command=(0.1, 0.2, 0.25, 0.4),
    )

    with pytest.raises(IntegrityV4Error, match="not exactly bound"):
        FreshPrefixAuthorizer().authorize(
            projected,
            old_assessment,
            old_contract,
            current_state_epoch=projected.state_epoch,
            current_trusted_observation_digest=(
                projected.trusted_observation_digest
            ),
            now_ns=60,
        )


def test_stale_authorization_is_rejected_before_sink_dispatch() -> None:
    _, _, _, authorization = _authorization(ttl_ns=5)
    sink = InMemoryActionSink()
    boundary = SingleUsePrefixDispatchBoundary(sink)

    opened = boundary.open(authorization, now_ns=66)

    assert opened.verdict is TransactionVerdict.REJECT
    assert opened.session is None
    assert sink.applied == []


def test_command_substitution_consumes_authorization_and_fails_closed() -> None:
    _, _, _, authorization = _authorization()
    sink = InMemoryActionSink()
    boundary = SingleUsePrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=61)
    assert opened.session is not None

    substituted = boundary.dispatch_next(
        opened.session,
        (9.0, 9.0),
        now_ns=62,
    )
    replay = boundary.open(authorization, now_ns=63)

    assert substituted.verdict is TransactionVerdict.REJECT
    assert sink.applied == []
    assert replay.verdict is TransactionVerdict.REJECT
    assert "already been consumed" in replay.issues[0]


def test_prefix_authorization_opens_once_but_dispatches_all_steps() -> None:
    _, _, _, authorization = _authorization()
    sink = InMemoryActionSink()
    boundary = SingleUsePrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=61)
    assert opened.session is not None

    first = boundary.dispatch_next(
        opened.session,
        authorization.action_at(0),
        now_ns=62,
    )
    second = boundary.dispatch_next(
        opened.session,
        authorization.action_at(1),
        now_ns=63,
    )
    replay = boundary.open(authorization, now_ns=64)

    assert first.verdict is TransactionVerdict.ALLOW
    assert second.verdict is TransactionVerdict.ALLOW
    assert opened.session.complete
    assert len(opened.session.receipts) == 2
    assert {
        receipt.authorization_digest
        for receipt in opened.session.receipts
    } == {authorization.authorization_digest}
    assert len(sink.applied) == 2
    assert replay.verdict is TransactionVerdict.REJECT


def test_receipt_and_effect_window_bind_exact_consumed_actions() -> None:
    _, _, contract, authorization = _authorization()
    sink = InMemoryActionSink()
    boundary = SingleUsePrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=61)
    assert opened.session is not None
    for step_index in range(authorization.action_count):
        result = boundary.dispatch_next(
            opened.session,
            authorization.action_at(step_index),
            now_ns=62 + step_index,
        )
        assert result.verdict is TransactionVerdict.ALLOW

    evidence = PrefixExecutionEvidence.for_window(
        authorization,
        contract,
        opened.session.receipts,
        observer_id="test-observer",
        observer_version="1",
        observer_config_digest=_digest("observer-config"),
        window_started_at_ns=61,
        observed_at_ns=64,
        initial_observation_digest=_digest("observation-0"),
        observation_digests=(
            _digest("observation-1"),
            _digest("observation-2"),
        ),
        observed_effect_atoms=("command_applied", "near_target"),
        observed_violation_atoms=(),
        observation_window_complete=True,
        effects_known=True,
    )
    evaluated = boundary.seal(opened.session, contract, evidence)

    assert evaluated.verdict is TransactionVerdict.ALLOW
    assert evidence.prefix_complete
    assert len(evidence.step_receipt_digests) == 2


def test_sink_side_substitution_is_bound_in_rejected_receipt() -> None:
    class SubstitutingSink:
        sink_id = "substituting-test-sink"

        def apply(self, action, *, now_ns):
            return AppliedAction(
                action=(action[0], action[1] + 0.01),
                applied_at_ns=now_ns,
            )

    _, _, _, authorization = _authorization()
    boundary = SingleUsePrefixDispatchBoundary(SubstitutingSink())
    opened = boundary.open(authorization, now_ns=61)
    assert opened.session is not None

    result = boundary.dispatch_next(
        opened.session,
        authorization.action_at(0),
        now_ns=62,
    )

    assert result.verdict is TransactionVerdict.REJECT
    assert result.receipt is not None
    assert (
        result.receipt.applied_action_digest
        != result.receipt.authorized_action_digest
    )
