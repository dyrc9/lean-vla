from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.ctda import (
    DigestAllowlistEvidenceVerifier,
    EvidenceAttestation,
    StaticVerdict,
    digest_payload,
    digest_text,
)
from proofalign.ctda_v2 import (
    ActiveContractContextV2,
    ContractLeaseClaimV2,
    ContractLeaseV2,
    CTDAV2ReferenceChecker,
    DispatchReceiptV2,
    FilterApplicationV2,
    Intervention,
    PrefixAuthorizationClaimV2,
    PrefixAuthorizationV2,
    PrefixDecisionClaimV2,
    PrefixDecisionV2,
    ProgressBudgetV2,
    ProgressLedgerV2,
    ProgressObservationClaimV2,
    ProgressObservationV2,
    RelevantStateSnapshotV2,
    SafetyChannelEvidenceV2,
    SafetyEvidenceBundleV2,
    SemanticCertificateClaimV2,
    SemanticCertificateV2,
    SnapshotStatus,
)
from proofalign.ctda_v2_wire import (
    V2WireStage,
    V2WireValidationError,
    decode_v2_wire_envelope,
    make_v2_wire_envelope,
)
from proofalign.ctda_v2_golden import state_rebind_payload


CHECKER_ID = "ctda-v2-fast-checker"
CHECKER_VERSION = "2.0.0-test"
CHECKER_DIGEST = digest_text("ctda-v2-fast-checker-fixture")
LEAN_ID = "proofalign-lean-kernel"
LEAN_VERSION = "4.24.0-test"


def _issue(
    verifier: DigestAllowlistEvidenceVerifier,
    evidence_type: str,
    subject_digest: str,
    *,
    issued_at_ns: int,
    valid_until_ns: int = 10_000,
    producer_id: str = CHECKER_ID,
    producer_version: str = CHECKER_VERSION,
) -> EvidenceAttestation:
    attestation = EvidenceAttestation(
        evidence_type=evidence_type,
        subject_digest=subject_digest,
        producer_id=producer_id,
        producer_version=producer_version,
        issued_at_ns=issued_at_ns,
        valid_until_ns=valid_until_ns,
        payload_digest=digest_text(f"payload:{evidence_type}:{subject_digest}"),
        proof_digest=digest_text(f"proof:{evidence_type}:{subject_digest}"),
    )
    verifier.trust(attestation)
    return attestation


def _snapshot(
    *,
    epoch: int,
    observed_at_ns: int,
    state: str,
    episode: str = "episode-v2",
    max_age_ns: int = 1_000,
) -> RelevantStateSnapshotV2:
    return RelevantStateSnapshotV2(
        episode_nonce=episode,
        state_epoch=epoch,
        observed_at_ns=observed_at_ns,
        producer_id="typed-sim-observer",
        producer_version="1",
        provenance_digest=digest_text("typed-sim-observer:fixture"),
        max_sensor_age_ns=max_age_ns,
        status=SnapshotStatus.OBSERVED,
        state_digest=digest_text(state),
    )


def _fixture():
    verifier = DigestAllowlistEvidenceVerifier()
    proof_state = _snapshot(epoch=0, observed_at_ns=10, state="proof-state", max_age_ns=20)
    claim = SemanticCertificateClaimV2(
        mission_root_digest=digest_text("mission-root"),
        episode_nonce="episode-v2",
        phase="approach",
        residual_obligations=("pick-mug",),
        contract_version="pick-contract-v2",
        proof_state=proof_state,
        action_set_digest=digest_text("pick-action-set-v2"),
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_proof_artifact_digest=digest_text("lean-proof-artifact"),
        proof_started_at_ns=20,
    )
    proof = _issue(
        verifier,
        "ctda_v2_semantic_certificate",
        claim.claim_digest,
        issued_at_ns=100,
        producer_id=LEAN_ID,
        producer_version=LEAN_VERSION,
    )
    certificate = SemanticCertificateV2(claim, proof_completed_at_ns=100, proof_attestation=proof)
    current_state = _snapshot(epoch=1, observed_at_ns=101, state="current-state")
    lease_claim = ContractLeaseClaimV2(
        certificate_digest=certificate.certificate_digest,
        activation_state=current_state,
        checker_digest=CHECKER_DIGEST,
        activated_at_ns=102,
        activated_control_epoch=7,
        valid_through_control_epoch=15,
    )
    rebind = _issue(
        verifier,
        "ctda_v2_state_rebind",
        lease_claim.claim_digest,
        issued_at_ns=102,
    )
    lease = ContractLeaseV2(lease_claim, rebind)
    context = ActiveContractContextV2(
        mission_root_digest=claim.mission_root_digest,
        episode_nonce=claim.episode_nonce,
        phase=claim.phase,
        residual_obligations=claim.residual_obligations,
        contract_version=claim.contract_version,
        control_epoch=7,
    )
    checker = CTDAV2ReferenceChecker(
        evidence_verifier=verifier,
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_producer_id=LEAN_ID,
        lean_producer_version=LEAN_VERSION,
    )
    return verifier, checker, certificate, lease, context


def _safety(state: RelevantStateSnapshotV2, *, unknown: bool = False):
    channel = SafetyChannelEvidenceV2(
        channel="collision",
        status=SnapshotStatus.UNKNOWN if unknown else SnapshotStatus.OBSERVED,
        producer_id="official-safelibero-collision",
        producer_version="pinned",
        unit="bool",
        source_ids=() if unknown else ("sim.geom-contact",),
        observed_at_ns=state.observed_at_ns,
        state_epoch=state.state_epoch,
        state_digest=state.state_digest or digest_text("unknown"),
        violation=None if unknown else False,
        value=None if unknown else 0,
        unknown_reason="collision producer unavailable" if unknown else None,
    )
    return SafetyEvidenceBundleV2(
        episode_nonce=state.episode_nonce,
        state_epoch=state.state_epoch,
        state_digest=state.state_digest or digest_text("unknown"),
        required_channels=("collision",),
        observations=(channel,),
    )


def _decision(
    verifier: DigestAllowlistEvidenceVerifier,
    certificate: SemanticCertificateV2,
    lease: ContractLeaseV2,
    safety: SafetyEvidenceBundleV2,
    *,
    intervention: Intervention = Intervention.PASS,
    membership_subject_override: str | None = None,
) -> PrefixDecisionV2:
    nominal = digest_text("nominal-command")
    adjusted = nominal
    filter_application = None
    if intervention is Intervention.PROJECT_OR_BRAKE:
        adjusted = digest_text("braked-command")
        filter_application = FilterApplicationV2(
            filter_id="aegis-adapter",
            filter_version="pinned-test",
            filter_digest=digest_text("aegis-filter"),
            nominal_command_digest=nominal,
            adjusted_command_digest=adjusted,
            reason="obstacle_enclosure",
            modification_norm=0.2,
            constraint_witness_digest=digest_text("constraint-witness"),
        )
    if intervention in (Intervention.REPLAN, Intervention.HARD_BLOCK):
        adjusted = None
    claim = PrefixDecisionClaimV2(
        certificate_digest=certificate.certificate_digest,
        lease_digest=lease.lease_digest,
        episode_nonce=certificate.claim.episode_nonce,
        proposal_index=0,
        control_epoch=7,
        state_snapshot_digest=lease.claim.activation_state.snapshot_digest,
        safety_bundle_digest=safety.bundle_digest,
        nominal_command_digest=nominal,
        intervention=intervention,
        adjusted_command_digest=adjusted,
        filter_application=filter_application,
        reason="nominal_admissible" if intervention is Intervention.PASS else intervention.value,
    )
    membership = None
    if intervention in (Intervention.PASS, Intervention.PROJECT_OR_BRAKE):
        membership = _issue(
            verifier,
            "ctda_v2_command_membership",
            membership_subject_override or claim.claim_digest,
            issued_at_ns=103,
        )
    return PrefixDecisionV2(claim, membership)


def _authorization(
    verifier: DigestAllowlistEvidenceVerifier,
    certificate: SemanticCertificateV2,
    lease: ContractLeaseV2,
    decision: PrefixDecisionV2,
) -> PrefixAuthorizationV2:
    claim = PrefixAuthorizationClaimV2(
        decision_digest=decision.decision_digest,
        certificate_digest=certificate.certificate_digest,
        lease_digest=lease.lease_digest,
        episode_nonce=certificate.claim.episode_nonce,
        proposal_index=decision.claim.proposal_index,
        control_epoch=decision.claim.control_epoch,
        authorized_command_digest=decision.claim.adjusted_command_digest or digest_text("no-command"),
        issued_at_ns=104,
        valid_until_ns=130,
    )
    attestation = _issue(
        verifier,
        "ctda_v2_prefix_authorization",
        claim.claim_digest,
        issued_at_ns=104,
        valid_until_ns=130,
    )
    return PrefixAuthorizationV2(claim, attestation)


def test_proof_latency_does_not_consume_control_epoch_lease() -> None:
    _, checker, certificate, lease, context = _fixture()

    # The proof-state sensor window expired during proof, but the post-proof state
    # was re-observed and authenticated.  Lease life starts at control epoch 7.
    assert certificate.proof_completed_at_ns - certificate.claim.proof_started_at_ns == 80
    assert certificate.claim.proof_state.freshness_issue(103) is not None
    assert checker.check_lease(certificate, lease, context, now_ns=103).proven
    assert checker.check_lease(
        certificate, lease, replace(context, control_epoch=15), now_ns=104
    ).proven


def test_late_proof_cannot_authorize_a_pre_proof_state_snapshot() -> None:
    verifier, checker, certificate, lease, context = _fixture()
    stale_claim = replace(
        lease.claim,
        activation_state=_snapshot(epoch=1, observed_at_ns=99, state="stale-during-proof"),
        activated_at_ns=102,
    )
    stale_lease = ContractLeaseV2(
        stale_claim,
        _issue(verifier, "ctda_v2_state_rebind", stale_claim.claim_digest, issued_at_ns=102),
    )

    result = checker.check_lease(certificate, stale_lease, context, now_ns=103)

    assert result.verdict is StaticVerdict.REFUTED
    assert any("re-observe" in issue for issue in result.issues)


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"phase": "holding"}, "phase"),
        ({"residual_obligations": ("place-mug",)}, "residual obligations"),
        ({"episode_nonce": "replayed-episode"}, "cross-episode"),
        ({"control_epoch": 16}, "control epoch"),
    ],
)
def test_lease_fails_closed_when_contract_epoch_context_changes(change, needle) -> None:
    _, checker, certificate, lease, context = _fixture()

    result = checker.check_lease(certificate, lease, replace(context, **change), now_ns=103)

    assert result.verdict is StaticVerdict.REFUTED
    assert any(needle in issue for issue in result.issues)


def test_pass_preserves_command_digest_and_requires_dual_authorization() -> None:
    verifier, checker, certificate, lease, context = _fixture()
    safety = _safety(lease.claim.activation_state)
    decision = _decision(verifier, certificate, lease, safety)
    authorization = _authorization(verifier, certificate, lease, decision)

    assert decision.claim.intervention is Intervention.PASS
    assert decision.claim.adjusted_command_digest == decision.claim.nominal_command_digest
    assert checker.check_decision(
        certificate, lease, context, safety, decision, now_ns=105
    ).proven
    assert checker.check_authorization(
        certificate, lease, context, safety, decision, authorization, now_ns=105
    ).proven


def test_projected_command_must_receive_a_fresh_post_filter_membership_check() -> None:
    verifier, checker, certificate, lease, context = _fixture()
    safety = _safety(lease.claim.activation_state)
    wrong_subject = digest_text("membership-for-nominal-command")
    decision = _decision(
        verifier,
        certificate,
        lease,
        safety,
        intervention=Intervention.PROJECT_OR_BRAKE,
        membership_subject_override=wrong_subject,
    )

    result = checker.check_decision(
        certificate, lease, context, safety, decision, now_ns=105
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("another subject" in issue for issue in result.issues)


def test_receipt_binds_adjusted_command_and_authorization_is_single_use() -> None:
    verifier, checker, certificate, lease, context = _fixture()
    safety = _safety(lease.claim.activation_state)
    decision = _decision(
        verifier, certificate, lease, safety, intervention=Intervention.PROJECT_OR_BRAKE
    )
    authorization = _authorization(verifier, certificate, lease, decision)
    assert checker.check_authorization(
        certificate, lease, context, safety, decision, authorization, now_ns=105
    ).proven
    actuator_subject = digest_payload(
        {
            "authorization_digest": authorization.authorization_digest,
            "episode_nonce": context.episode_nonce,
            "proposal_index": 0,
            "control_epoch": 7,
            "executed_command_digest": decision.claim.adjusted_command_digest,
            "dispatched_at_ns": 106,
        }
    )
    actuator = _issue(
        verifier,
        "ctda_v2_actuator_receipt",
        actuator_subject,
        issued_at_ns=106,
        producer_id="typed-actuator-adapter",
        producer_version="1",
    )
    receipt = DispatchReceiptV2(
        authorization_digest=authorization.authorization_digest,
        episode_nonce=context.episode_nonce,
        proposal_index=0,
        control_epoch=7,
        nominal_command_digest=decision.claim.nominal_command_digest,
        executed_command_digest=decision.claim.adjusted_command_digest or "",
        dispatched_at_ns=106,
        actuator_attestation=actuator,
    )

    assert checker.check_and_consume_receipt(authorization, decision, receipt).proven
    replay = checker.check_and_consume_receipt(authorization, decision, receipt)
    assert replay.verdict is StaticVerdict.REFUTED
    assert any("replay" in issue for issue in replay.issues)


def test_unknown_safety_provenance_can_replan_but_cannot_dispatch() -> None:
    verifier, checker, certificate, lease, context = _fixture()
    safety = _safety(lease.claim.activation_state, unknown=True)
    dispatch = _decision(verifier, certificate, lease, safety)
    replan = _decision(
        verifier, certificate, lease, safety, intervention=Intervention.REPLAN
    )

    rejected = checker.check_decision(
        certificate, lease, context, safety, dispatch, now_ns=105
    )

    assert rejected.verdict is StaticVerdict.REFUTED
    assert any("unknown safety provenance" in issue for issue in rejected.issues)
    assert checker.check_decision(
        certificate, lease, context, safety, replan, now_ns=105
    ).proven


def _progress_observation(
    verifier: DigestAllowlistEvidenceVerifier,
    ledger: ProgressLedgerV2,
    *,
    after_epoch: int,
    before_m: float | None,
    after_m: float | None,
    translation: float = 0.01,
    motion: float = 0.1,
) -> ProgressObservationV2:
    after = _snapshot(
        epoch=after_epoch,
        observed_at_ns=110 + after_epoch,
        state=f"progress-state-{after_epoch}",
    )
    claim = ProgressObservationClaimV2(
        certificate_digest=ledger.certificate_digest,
        before_snapshot_digest=ledger.last_state.snapshot_digest,
        after_state=after,
        distance_before_m=before_m,
        distance_after_m=after_m,
        minimum_progress_m=0.005,
        elapsed_control_epochs=1,
        translation_consumed_m=translation,
        motion_consumed=motion,
    )
    attestation = _issue(
        verifier,
        "ctda_v2_progress_observation",
        claim.claim_digest,
        issued_at_ns=after.observed_at_ns,
    )
    return ProgressObservationV2(claim, attestation)


def test_progress_ledger_replaces_fixed_three_prefix_limit_without_budget_refund() -> None:
    verifier, checker, certificate, lease, _ = _fixture()
    budget = ProgressBudgetV2(10, 0.2, 2.0)
    ledger = ProgressLedgerV2(
        certificate_digest=certificate.certificate_digest,
        episode_nonce=certificate.claim.episode_nonce,
        last_state=lease.claim.activation_state,
    )

    # Four authenticated non-progress chunks remain live; v1 rejected after three.
    for epoch in range(2, 6):
        update = checker.update_progress(
            ledger,
            _progress_observation(
                verifier, ledger, after_epoch=epoch, before_m=0.2, after_m=0.2
            ),
            budget,
            now_ns=112 + epoch,
        )
        assert update.check.proven
        assert update.required_intervention is Intervention.REPLAN
        ledger = update.ledger
    assert ledger.consecutive_nonprogress_control_epochs == 4
    assert ledger.cumulative_translation_m == pytest.approx(0.04)

    replanned = ledger.record_replan()
    assert replanned.progress_epoch == ledger.progress_epoch
    assert replanned.consecutive_nonprogress_control_epochs == 4
    assert replanned.cumulative_translation_m == ledger.cumulative_translation_m
    assert replanned.cumulative_motion == ledger.cumulative_motion

    progressed = checker.update_progress(
        replanned,
        _progress_observation(
            verifier, replanned, after_epoch=6, before_m=0.2, after_m=0.19
        ),
        budget,
        now_ns=119,
    )
    assert progressed.check.proven
    assert progressed.ledger.progress_epoch == 1
    assert progressed.ledger.consecutive_nonprogress_control_epochs == 0
    # Authenticated progress resets only liveness age, never cumulative motion.
    assert progressed.ledger.cumulative_translation_m == pytest.approx(0.05)
    assert progressed.ledger.cumulative_motion == pytest.approx(0.5)


def test_progress_budget_exhaustion_is_recorded_before_hard_block() -> None:
    verifier, checker, certificate, lease, _ = _fixture()
    budget = ProgressBudgetV2(10, 0.02, 2.0)
    ledger = ProgressLedgerV2(
        certificate_digest=certificate.certificate_digest,
        episode_nonce=certificate.claim.episode_nonce,
        last_state=lease.claim.activation_state,
    )
    update = checker.update_progress(
        ledger,
        _progress_observation(
            verifier,
            ledger,
            after_epoch=2,
            before_m=0.2,
            after_m=0.2,
            translation=0.03,
        ),
        budget,
        now_ns=114,
    )

    assert update.check.verdict is StaticVerdict.REFUTED
    assert update.required_intervention is Intervention.HARD_BLOCK
    assert update.ledger.cumulative_translation_m == pytest.approx(0.03)


def test_v2_wire_rejects_v1_missing_fields_and_digest_tamper() -> None:
    envelope = make_v2_wire_envelope(
        V2WireStage.STATE_REBIND,
        CHECKER_DIGEST,
        state_rebind_payload(),
    )
    decoded = decode_v2_wire_envelope(envelope.canonical_bytes())
    assert decoded.payload_digest == envelope.payload_digest

    v1 = envelope.to_dict()
    v1["schema_version"] = "ctda-wire-v1"
    with pytest.raises(V2WireValidationError, match="unsupported"):
        decode_v2_wire_envelope(v1)

    missing = envelope.to_dict()
    del missing["method_id"]
    with pytest.raises(V2WireValidationError, match="fields mismatch"):
        decode_v2_wire_envelope(missing)

    tampered = envelope.to_dict()
    tampered["payload"] = {**tampered["payload"], "extra": "tamper"}
    with pytest.raises(V2WireValidationError, match="fields mismatch|digest mismatch"):
        decode_v2_wire_envelope(tampered)
