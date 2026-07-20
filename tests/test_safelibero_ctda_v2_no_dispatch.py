from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.ctda import EvidenceAttestation, StaticVerdict, digest_payload, digest_text
from proofalign.ctda_runtime import ExactAllowlistEvidenceIssuer
from proofalign.ctda_v2 import (
    ActiveContractContextV2,
    ContractLeaseClaimV2,
    ContractLeaseV2,
    CTDAV2ReferenceChecker,
    Intervention,
    ProgressBudgetV2,
    ProgressLedgerV2,
    RelevantStateSnapshotV2,
    SafetyChannelEvidenceV2,
    SafetyEvidenceBundleV2,
    SemanticCertificateClaimV2,
    SemanticCertificateV2,
    SnapshotStatus,
)
from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import (
    SafeLiberoCommandV2,
    SafeLiberoOpenRegionProgressProducerV2,
    SafeLiberoPostFilterNoDispatchAdapterV2,
    SafeLiberoPostFilterWitnessV2,
    SafeLiberoRecoveryNoDispatchAdapterV2,
)
from proofalign.benchmark.safelibero_open_region import (
    OFFICIAL_JOINT_SOURCE_ID,
    SafeLiberoOpenRegionBindingV2,
    SafeLiberoOpenRegionRuntimeV2,
)


CHECKER_ID = "ctda-v2-fast-checker"
CHECKER_VERSION = "2.0.0-no-dispatch-test"
CHECKER_DIGEST = digest_text("ctda-v2-no-dispatch-checker")
LEAN_ID = "proofalign-lean-kernel"
LEAN_VERSION = "4.24.0-test"


def _snapshot(
    epoch: int,
    observed_at_ns: int,
    state: str,
    *,
    episode_nonce: str = "drawer-online-episode",
) -> RelevantStateSnapshotV2:
    return RelevantStateSnapshotV2(
        episode_nonce=episode_nonce,
        state_epoch=epoch,
        observed_at_ns=observed_at_ns,
        producer_id="typed-safelibero-state",
        producer_version="fixture",
        provenance_digest=digest_text("typed-safelibero-state:fixture"),
        max_sensor_age_ns=1_000,
        status=SnapshotStatus.OBSERVED,
        state_digest=digest_text(state),
    )


def _runtime(issuer: ExactAllowlistEvidenceIssuer) -> SafeLiberoOpenRegionProgressProducerV2:
    binding = SafeLiberoOpenRegionBindingV2(
        goal_manifest_digest=digest_text("drawer-goal"),
        mission_step_digest=digest_text("drawer-open-step"),
        source_identity_digest=digest_text("official-source-identity"),
    )
    runtime = SafeLiberoOpenRegionRuntimeV2(
        binding=binding,
        producer_id="official-safelibero-joint-observer",
        producer_version="source-bound-test",
        max_sensor_age_ns=100,
    )
    return SafeLiberoOpenRegionProgressProducerV2(
        runtime=runtime,
        issuer=issuer,
        attestation_valid_for_ns=100,
    )


def _ctda_fixture():
    issuer = ExactAllowlistEvidenceIssuer()
    proof_state = _snapshot(0, 10, "proof-state")
    certificate_claim = SemanticCertificateClaimV2(
        mission_root_digest=digest_text("drawer-mission-root"),
        episode_nonce=proof_state.episode_nonce,
        phase="open-drawer",
        residual_obligations=("put-bowl-inside",),
        contract_version="drawer-contract-v2",
        proof_state=proof_state,
        action_set_digest=digest_text("drawer-action-set"),
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_proof_artifact_digest=digest_text("drawer-lean-proof"),
        proof_started_at_ns=20,
    )
    proof = issuer.issue(
        "ctda_v2_semantic_certificate",
        certificate_claim.claim_digest,
        payload=certificate_claim.payload(),
        issued_at_ns=100,
        valid_until_ns=1_000,
        producer_id=LEAN_ID,
        producer_version=LEAN_VERSION,
    )
    certificate = SemanticCertificateV2(
        certificate_claim, proof_completed_at_ns=100, proof_attestation=proof
    )
    activation = _snapshot(1, 101, "activation-state")
    lease_claim = ContractLeaseClaimV2(
        certificate_digest=certificate.certificate_digest,
        activation_state=activation,
        checker_digest=CHECKER_DIGEST,
        activated_at_ns=102,
        activated_control_epoch=7,
        valid_through_control_epoch=15,
    )
    rebind = issuer.issue(
        "ctda_v2_state_rebind",
        lease_claim.claim_digest,
        payload=lease_claim.payload(),
        issued_at_ns=102,
        valid_until_ns=1_000,
        producer_id=CHECKER_ID,
        producer_version=CHECKER_VERSION,
    )
    lease = ContractLeaseV2(lease_claim, rebind)
    context = ActiveContractContextV2(
        mission_root_digest=certificate_claim.mission_root_digest,
        episode_nonce=certificate_claim.episode_nonce,
        phase=certificate_claim.phase,
        residual_obligations=certificate_claim.residual_obligations,
        contract_version=certificate_claim.contract_version,
        control_epoch=7,
    )
    checker = CTDAV2ReferenceChecker(
        evidence_verifier=issuer.verifier,
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_producer_id=LEAN_ID,
        lean_producer_version=LEAN_VERSION,
    )
    collision = SafetyChannelEvidenceV2(
        channel="collision",
        status=SnapshotStatus.OBSERVED,
        producer_id="official-safelibero-collision",
        producer_version="pinned",
        unit="bool",
        source_ids=("sim.geom-contact",),
        observed_at_ns=activation.observed_at_ns,
        state_epoch=activation.state_epoch,
        state_digest=activation.state_digest or "",
        violation=False,
        value=0,
    )
    safety = SafetyEvidenceBundleV2(
        episode_nonce=activation.episode_nonce,
        state_epoch=activation.state_epoch,
        state_digest=activation.state_digest or "",
        required_channels=("collision",),
        observations=(collision,),
    )
    return issuer, checker, certificate, lease, context, safety


def _commands() -> tuple[SafeLiberoCommandV2, SafeLiberoCommandV2]:
    return (
        SafeLiberoCommandV2((0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
        SafeLiberoCommandV2((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
    )


def _filter_witness(
    lease: ContractLeaseV2,
    safety: SafetyEvidenceBundleV2,
    nominal: SafeLiberoCommandV2,
    adjusted: SafeLiberoCommandV2,
    *,
    state_snapshot_digest: str | None = None,
    status: SnapshotStatus = SnapshotStatus.OBSERVED,
    adjusted_admissible: bool | None = True,
) -> SafeLiberoPostFilterWitnessV2:
    return SafeLiberoPostFilterWitnessV2(
        filter_id="aegis-post-filter",
        filter_version="pinned-test",
        filter_digest=digest_text("aegis-post-filter-artifact"),
        state_snapshot_digest=(
            state_snapshot_digest or lease.claim.activation_state.snapshot_digest
        ),
        safety_bundle_digest=safety.bundle_digest,
        nominal_command_digest=nominal.command_digest,
        adjusted_command_digest=adjusted.command_digest,
        constraint_ids=("collision-envelope", "mission-membership"),
        status=status,
        adjusted_admissible=adjusted_admissible,
        reason="collision_envelope_projection",
        observed_at_ns=104,
        unknown_reason="filter evidence unavailable" if status is SnapshotStatus.UNKNOWN else None,
    )


def test_command_digest_is_consumer_derived_and_nonfinite_rejected() -> None:
    command = SafeLiberoCommandV2((0, 0, 0, 0, 0, 0, -1))

    assert command.command_digest == digest_payload(command.payload())
    assert command.values == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
    with pytest.raises(ValueError, match="seven"):
        SafeLiberoCommandV2((0.0,) * 6)
    with pytest.raises(ValueError, match="non-finite"):
        SafeLiberoCommandV2((0.0, 0.0, 0.0, 0.0, 0.0, float("nan"), -1.0))


def test_open_region_progress_packet_binds_exact_source_states_and_attestation() -> None:
    issuer = ExactAllowlistEvidenceIssuer()
    producer = _runtime(issuer)
    certificate_digest = digest_text("drawer-progress-certificate")
    packet = producer.produce(
        certificate_digest=certificate_digest,
        before_base_state=_snapshot(1, 10, "before-base"),
        after_base_state=_snapshot(2, 20, "after-base"),
        before_joint_position_m=0.0,
        after_joint_position_m=-0.145,
        before_joint_source_id=OFFICIAL_JOINT_SOURCE_ID,
        after_joint_source_id=OFFICIAL_JOINT_SOURCE_ID,
        minimum_progress_m=0.005,
        elapsed_control_epochs=1,
        translation_consumed_m=0.01,
        motion_consumed=0.1,
    )
    checker = CTDAV2ReferenceChecker(
        evidence_verifier=issuer.verifier,
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_producer_id=LEAN_ID,
        lean_producer_version=LEAN_VERSION,
    )
    ledger = ProgressLedgerV2(
        certificate_digest=certificate_digest,
        episode_nonce=packet.before_state.episode_nonce,
        last_state=packet.before_state,
    )
    update = checker.update_progress(
        ledger,
        packet.progress,
        ProgressBudgetV2(4, 0.1, 1.0),
        now_ns=20,
    )

    assert packet.progress.claim.made_progress is True
    assert packet.after_observation.is_open is True
    assert issuer.verifier.verify(packet.progress.progress_attestation)
    assert update.check.proven
    assert update.required_intervention is Intervention.PASS
    assert not hasattr(producer, "action")
    assert not hasattr(producer, "dispatch")


def test_open_region_progress_unknown_source_never_receives_attestation() -> None:
    producer = _runtime(ExactAllowlistEvidenceIssuer())

    with pytest.raises(ValueError, match="source is unknown"):
        producer.produce(
            certificate_digest=digest_text("drawer-progress-certificate"),
            before_base_state=_snapshot(1, 10, "before-base"),
            after_base_state=_snapshot(2, 20, "after-base"),
            before_joint_position_m=0.0,
            after_joint_position_m=-0.15,
            before_joint_source_id=OFFICIAL_JOINT_SOURCE_ID,
            after_joint_source_id="wooden_cabinet_1_middle_level",
            minimum_progress_m=0.005,
            elapsed_control_epochs=1,
            translation_consumed_m=0.01,
            motion_consumed=0.1,
        )


def test_post_filter_transaction_binds_adjusted_command_but_never_dispatches() -> None:
    issuer, checker, certificate, lease, context, safety = _ctda_fixture()
    nominal, adjusted = _commands()
    witness = _filter_witness(lease, safety, nominal, adjusted)
    adapter = SafeLiberoPostFilterNoDispatchAdapterV2(
        checker=checker,
        issuer=issuer,
        filter_id=witness.filter_id,
        filter_version=witness.filter_version,
        filter_digest=witness.filter_digest,
        max_filter_witness_age_ns=10,
        membership_valid_for_ns=20,
        authorization_valid_for_ns=10,
    )

    transaction = adapter.evaluate(
        certificate=certificate,
        lease=lease,
        context=context,
        safety=safety,
        nominal_command=nominal,
        adjusted_command=adjusted,
        filter_witness=witness,
        proposal_index=0,
        now_ns=105,
    )

    assert transaction.decision.claim.intervention is Intervention.PROJECT_OR_BRAKE
    assert transaction.decision.claim.adjusted_command_digest == adjusted.command_digest
    assert transaction.authorization is not None
    assert transaction.authorization.claim.authorized_command_digest == adjusted.command_digest
    assert transaction.authorization_ready is True
    assert transaction.dispatch_count == 0
    assert transaction.formal_rollout_authorized is False
    assert not hasattr(adapter, "dispatch")
    assert not hasattr(adapter, "action")


def test_post_filter_cross_state_or_unknown_witness_hard_blocks_before_authorization() -> None:
    issuer, checker, certificate, lease, context, safety = _ctda_fixture()
    nominal, adjusted = _commands()
    adapter = SafeLiberoPostFilterNoDispatchAdapterV2(
        checker=checker,
        issuer=issuer,
        filter_id="aegis-post-filter",
        filter_version="pinned-test",
        filter_digest=digest_text("aegis-post-filter-artifact"),
        max_filter_witness_age_ns=10,
        membership_valid_for_ns=20,
        authorization_valid_for_ns=10,
    )
    witnesses = (
        _filter_witness(
            lease,
            safety,
            nominal,
            adjusted,
            state_snapshot_digest=digest_text("foreign-state"),
        ),
        _filter_witness(
            lease,
            safety,
            nominal,
            adjusted,
            status=SnapshotStatus.UNKNOWN,
            adjusted_admissible=None,
        ),
        replace(_filter_witness(lease, safety, nominal, adjusted), observed_at_ns=80),
    )

    for witness in witnesses:
        transaction = adapter.evaluate(
            certificate=certificate,
            lease=lease,
            context=context,
            safety=safety,
            nominal_command=nominal,
            adjusted_command=adjusted,
            filter_witness=witness,
            proposal_index=0,
            now_ns=105,
        )
        assert transaction.decision.claim.intervention is Intervention.HARD_BLOCK
        assert transaction.decision_check.proven
        assert transaction.authorization is None
        assert transaction.authorization_ready is False
        assert transaction.dispatch_count == 0


def test_recovery_record_replans_without_refund_and_untrusted_progress_hard_blocks() -> None:
    issuer = ExactAllowlistEvidenceIssuer()
    producer = _runtime(issuer)
    certificate_digest = digest_text("drawer-progress-certificate")
    packet = producer.produce(
        certificate_digest=certificate_digest,
        before_base_state=_snapshot(1, 10, "before-base"),
        after_base_state=_snapshot(2, 20, "after-base"),
        before_joint_position_m=0.0,
        after_joint_position_m=-0.001,
        before_joint_source_id=OFFICIAL_JOINT_SOURCE_ID,
        after_joint_source_id=OFFICIAL_JOINT_SOURCE_ID,
        minimum_progress_m=0.005,
        elapsed_control_epochs=1,
        translation_consumed_m=0.01,
        motion_consumed=0.1,
    )
    checker = CTDAV2ReferenceChecker(
        evidence_verifier=issuer.verifier,
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_producer_id=LEAN_ID,
        lean_producer_version=LEAN_VERSION,
    )
    ledger = ProgressLedgerV2(
        certificate_digest=certificate_digest,
        episode_nonce=packet.before_state.episode_nonce,
        last_state=packet.before_state,
    )
    recovery = SafeLiberoRecoveryNoDispatchAdapterV2(checker)
    record = recovery.record(
        ledger,
        packet.progress,
        ProgressBudgetV2(4, 0.1, 1.0),
        now_ns=20,
    )

    assert record.update.required_intervention is Intervention.REPLAN
    assert record.resulting_ledger.replan_count == 1
    assert record.resulting_ledger.cumulative_translation_m == pytest.approx(0.01)
    assert record.resulting_ledger.cumulative_motion == pytest.approx(0.1)
    assert record.dispatch_count == 0
    assert record.command_digest is None

    untrusted = EvidenceAttestation(
        evidence_type="ctda_v2_progress_observation",
        subject_digest=packet.progress.claim.claim_digest,
        producer_id="forged-producer",
        producer_version="1",
        issued_at_ns=20,
        valid_until_ns=120,
        payload_digest=digest_text("forged-payload"),
        proof_digest=digest_text("forged-proof"),
    )
    rejected = recovery.record(
        ledger,
        replace(packet.progress, progress_attestation=untrusted),
        ProgressBudgetV2(4, 0.1, 1.0),
        now_ns=20,
    )
    assert rejected.update.check.verdict is StaticVerdict.REFUTED
    assert rejected.update.required_intervention is Intervention.HARD_BLOCK
    assert rejected.resulting_ledger.ledger_digest == ledger.ledger_digest
    assert rejected.terminal is True
