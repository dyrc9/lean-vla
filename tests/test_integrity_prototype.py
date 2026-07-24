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
    ActionProposal,
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
        episode_nonce="episode-integrity-v1",
        authorizer=ExactPrefixAuthorizer(
            DeterministicFastChecker(),
            authorization_ttl_ns=50,
        ),
        sink=sink,
    )
    transaction = prototype.certify_contract(now_ns=10)
    assert transaction.verdict is CoreVerdict.ALLOW
    return prototype, sink


def _state(*, observed_at_ns: int = 11, max_age_ns: int = 100) -> StateSnapshot:
    return StateSnapshot(
        episode_nonce="episode-integrity-v1",
        state_epoch=0,
        observed_at_ns=observed_at_ns,
        max_age_ns=max_age_ns,
        state_digest=digest_text(f"state:{observed_at_ns}:{max_age_ns}"),
        known=True,
    )


def _proposal(
    *,
    index: int = 0,
    target: str = "mug",
    part: str = "handle",
    command: tuple[float, ...] = GOOD_COMMAND,
) -> ActionProposal:
    return ActionProposal(
        episode_nonce="episode-integrity-v1",
        proposal_index=index,
        proposed_at_ns=12 + index,
        skill="Pick",
        target=target,
        part=part,
        command=command,
    )


def _authorize(
    prototype: ProofAlignPrototype,
    *,
    proposal: ActionProposal | None = None,
    state: StateSnapshot | None = None,
    now_ns: int = 13,
    intervention_policy=None,
):
    return prototype.authorize_exact_prefix(
        proposal=proposal or _proposal(),
        state=state or _state(),
        now_ns=now_ns,
        intervention_policy=intervention_policy,
    )


def _known_evidence(
    authorization,
    receipt,
    *,
    atoms: tuple[str, ...],
    observed_command_digest: str | None = None,
    authorization_digest: str | None = None,
    receipt_digest: str | None = None,
    violation: bool = False,
) -> ExecutionEvidence:
    return ExecutionEvidence(
        authorization_digest=authorization_digest or authorization.authorization_digest,
        receipt_digest=receipt_digest or receipt.receipt_digest,
        episode_nonce=authorization.episode_nonce,
        proposal_index=authorization.proposal_index,
        observed_at_ns=receipt.applied_at_ns + 1,
        observed_command_digest=observed_command_digest or receipt.applied_command_digest,
        observed_atoms=atoms,
        known=True,
        violation=violation,
    )


def test_contract_transaction_is_persistent_and_idempotent() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    first_state = prototype.monitor.state

    again = prototype.certify_contract(now_ns=20)

    assert again.verdict is CoreVerdict.ALLOW
    assert again.after_state == first_state
    assert again.contract == prototype.monitor.active_contract
    assert again.contract is not None
    assert again.contract.mission_root_digest == prototype.mission.root_digest


@pytest.mark.parametrize(
    ("arm", "intent", "execution"),
    [
        (MethodArm.VLA_ONLY, LayerVerdict.DISABLED, LayerVerdict.DISABLED),
        (MethodArm.INTENT_ONLY, LayerVerdict.PROVEN, LayerVerdict.DISABLED),
        (MethodArm.EXECUTION_ONLY, LayerVerdict.DISABLED, LayerVerdict.PROVEN),
        (MethodArm.DUAL, LayerVerdict.PROVEN, LayerVerdict.PROVEN),
    ],
)
def test_four_arms_share_one_authorizer_with_explicit_layer_switches(
    arm: MethodArm,
    intent: LayerVerdict,
    execution: LayerVerdict,
) -> None:
    prototype, _ = _prototype(arm)

    authorization = _authorize(prototype)

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
def test_intent_layer_has_an_independent_wrong_target_catch(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, _ = _prototype(arm)

    authorization = _authorize(prototype, proposal=_proposal(target="knife", part="blade"))

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
def test_execution_layer_has_an_independent_stale_state_catch(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, _ = _prototype(arm)
    stale = _state(observed_at_ns=1, max_age_ns=2)

    authorization = _authorize(prototype, state=stale, now_ns=13)

    assert authorization.verdict is expected


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (MethodArm.VLA_ONLY, CoreVerdict.ALLOW),
        (MethodArm.INTENT_ONLY, CoreVerdict.ALLOW),
        (MethodArm.EXECUTION_ONLY, CoreVerdict.REJECT),
        (MethodArm.DUAL, CoreVerdict.REJECT),
    ],
)
def test_execution_layer_uniquely_rejects_command_substitution_at_dispatch(
    arm: MethodArm,
    expected: CoreVerdict,
) -> None:
    prototype, sink = _prototype(arm)
    authorization = _authorize(prototype)

    result = prototype.dispatch(authorization, SUBSTITUTED_COMMAND, now_ns=14)

    assert result.verdict is expected
    assert len(sink.applied) == (1 if expected is CoreVerdict.ALLOW else 0)


def test_dual_dispatch_requires_both_layer_authorizations() -> None:
    prototype, sink = _prototype(MethodArm.DUAL)
    rejected = _authorize(prototype, proposal=_proposal(target="knife", part="blade"))

    result = prototype.dispatch(rejected, GOOD_COMMAND, now_ns=14)

    assert result.verdict is CoreVerdict.REJECT
    assert sink.applied == []


def test_boundary_reports_a_sink_side_command_substitution() -> None:
    class SubstitutingSink:
        sink_id = "malicious-test-sink"

        def apply(self, command, *, now_ns):
            del command
            return AppliedCommand(SUBSTITUTED_COMMAND, now_ns)

    prototype = ProofAlignPrototype.create(
        arm=MethodArm.DUAL,
        artifact=_artifact(),
        episode_nonce="episode-integrity-v1",
        authorizer=ExactPrefixAuthorizer(DeterministicFastChecker()),
        sink=SubstitutingSink(),
    )
    assert prototype.certify_contract(now_ns=10).verdict is CoreVerdict.ALLOW
    authorization = _authorize(prototype)

    result = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)

    assert result.verdict is CoreVerdict.REJECT
    assert result.receipt is not None
    assert result.receipt.applied_command_digest == command_digest(SUBSTITUTED_COMMAND)
    assert any("sink applied" in issue for issue in result.issues)


def test_filter_output_is_the_command_reauthorized_and_dispatched() -> None:
    prototype, sink = _prototype(MethodArm.DUAL)
    policy = ProjectCommandIntervention(
        adjusted_command=BRAKED_COMMAND,
        witness_digest=digest_text("consumer-checkable-filter-witness"),
    )

    authorization = _authorize(prototype, intervention_policy=policy)
    nominal_attempt = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)

    assert authorization.verdict is CoreVerdict.ALLOW
    assert authorization.final_command_digest == command_digest(BRAKED_COMMAND)
    assert authorization.execution_check.verdict is LayerVerdict.PROVEN
    assert nominal_attempt.verdict is CoreVerdict.REJECT
    assert sink.applied == []

    # A rejected attempt does not consume the authorization because the sink was
    # never called; the exact adjusted command can still use it once.
    adjusted_attempt = prototype.dispatch(authorization, BRAKED_COMMAND, now_ns=15)
    replay = prototype.dispatch(authorization, BRAKED_COMMAND, now_ns=16)
    assert adjusted_attempt.verdict is CoreVerdict.ALLOW
    assert replay.verdict is CoreVerdict.REJECT
    assert len(sink.applied) == 1


def test_replan_is_an_intervention_not_a_logic_layer() -> None:
    prototype, sink = _prototype(MethodArm.DUAL)

    authorization = _authorize(prototype, intervention_policy=ReplanIntervention())
    result = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)

    assert authorization.verdict is CoreVerdict.UNKNOWN
    assert authorization.final_command is None
    assert result.verdict is CoreVerdict.REJECT
    assert sink.applied == []


def test_pending_effect_does_not_advance_phase_and_completion_does() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    first = _authorize(prototype, proposal=_proposal(index=0))
    first_dispatch = prototype.dispatch(first, GOOD_COMMAND, now_ns=14)
    assert first_dispatch.receipt is not None
    pending_evidence = _known_evidence(
        first,
        first_dispatch.receipt,
        atoms=("approaching:mug",),
    )

    pending = prototype.check_effect_update(
        authorization=first,
        receipt=first_dispatch.receipt,
        evidence=pending_evidence,
    )

    assert pending.verdict is CoreVerdict.PENDING
    assert pending.after_state.phase == "approach"
    assert pending.after_state.active_contract_digest is not None

    second = _authorize(prototype, proposal=_proposal(index=1), now_ns=20)
    second_dispatch = prototype.dispatch(second, GOOD_COMMAND, now_ns=21)
    assert second_dispatch.receipt is not None
    completion_evidence = _known_evidence(
        second,
        second_dispatch.receipt,
        atoms=("holding:mug",),
    )
    complete = prototype.check_effect_update(
        authorization=second,
        receipt=second_dispatch.receipt,
        evidence=completion_evidence,
    )

    assert complete.verdict is CoreVerdict.COMPLETE
    assert complete.after_state.phase == "done"
    assert complete.after_state.active_contract_digest is None
    assert "pick-mug" not in complete.after_state.residual_obligations


def test_execution_binding_rejects_false_completion_without_state_mutation() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)
    dispatch = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert dispatch.receipt is not None
    before = prototype.monitor.state
    forged = _known_evidence(
        authorization,
        dispatch.receipt,
        atoms=("holding:mug",),
        receipt_digest=digest_text("stale-or-forged-receipt"),
    )

    result = prototype.check_effect_update(
        authorization=authorization,
        receipt=dispatch.receipt,
        evidence=forged,
    )

    assert result.verdict is CoreVerdict.REJECT
    assert result.after_state == before
    assert prototype.monitor.state == before


def test_unknown_completion_evidence_cannot_advance_phase() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)
    dispatch = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert dispatch.receipt is not None
    before = prototype.monitor.state
    unknown = ExecutionEvidence(
        authorization_digest=authorization.authorization_digest,
        receipt_digest=dispatch.receipt.receipt_digest,
        episode_nonce=authorization.episode_nonce,
        proposal_index=authorization.proposal_index,
        observed_at_ns=15,
        observed_command_digest=None,
        observed_atoms=(),
        known=False,
        unknown_reason="observer unavailable",
    )

    result = prototype.check_effect_update(
        authorization=authorization,
        receipt=dispatch.receipt,
        evidence=unknown,
    )

    assert result.verdict is CoreVerdict.UNKNOWN
    assert result.after_state == before
    assert prototype.monitor.state.phase == "approach"


def test_violation_cannot_advance_phase_even_with_completion_atom() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)
    dispatch = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert dispatch.receipt is not None
    evidence = _known_evidence(
        authorization,
        dispatch.receipt,
        atoms=("holding:mug",),
        violation=True,
    )

    result = prototype.check_effect_update(
        authorization=authorization,
        receipt=dispatch.receipt,
        evidence=evidence,
    )

    assert result.verdict is CoreVerdict.REJECT
    assert result.after_state.phase == "approach"
    assert result.after_state.active_contract_digest is not None
    assert "pick-mug" in result.after_state.residual_obligations


def test_monitor_rejects_stale_proposal_after_pending_commit() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)
    dispatch = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert dispatch.receipt is not None
    pending = _known_evidence(
        authorization,
        dispatch.receipt,
        atoms=("approaching:mug",),
    )
    result = prototype.check_effect_update(
        authorization=authorization,
        receipt=dispatch.receipt,
        evidence=pending,
    )
    assert result.verdict is CoreVerdict.PENDING

    replay = _authorize(prototype, proposal=_proposal(index=0), now_ns=20)

    assert replay.verdict is CoreVerdict.REJECT
    assert replay.execution_check.verdict is LayerVerdict.REFUTED


def test_method_version_isolated_from_ctda_v1_and_v2() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)

    assert authorization.method_id == "proofalign-integrity-v1"
    assert authorization.schema_version == "proofalign.integrity-core-v1"
    assert authorization.method_id not in {"ctda-v1", "ctda-v2"}


def test_monitor_identity_cannot_be_replaced_by_dataclass_tampering() -> None:
    prototype, _ = _prototype(MethodArm.DUAL)
    authorization = _authorize(prototype)
    dispatch = prototype.dispatch(authorization, GOOD_COMMAND, now_ns=14)
    assert dispatch.receipt is not None
    evidence = _known_evidence(
        authorization,
        dispatch.receipt,
        atoms=("holding:mug",),
    )
    before = prototype.monitor.state
    forged_authorization = replace(
        authorization,
        monitor_state_digest=digest_text("another-monitor"),
    )

    # Reconstructing a frozen dataclass recomputes the authorization digest, so
    # it no longer matches the receipt/evidence transaction.
    result = prototype.check_effect_update(
        authorization=forged_authorization,
        receipt=dispatch.receipt,
        evidence=evidence,
    )

    assert result.verdict is CoreVerdict.REJECT
    assert prototype.monitor.state == before
