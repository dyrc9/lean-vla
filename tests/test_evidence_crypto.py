from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.ctda import digest_text
from proofalign.ctda_v2 import (
    CTDAV2ReferenceChecker,
    Intervention,
    ProgressBudgetV2,
    ProgressLedgerV2,
    RelevantStateSnapshotV2,
    SnapshotStatus,
)
from proofalign.evidence_crypto import (
    ED25519_PROOF_PREFIX,
    Ed25519EvidenceIssuer,
    Ed25519EvidenceVerifier,
    Ed25519PublicKeyBinding,
)
from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import (
    SafeLiberoOpenRegionProgressProducerV2,
)
from proofalign.benchmark.safelibero_open_region import (
    OFFICIAL_JOINT_SOURCE_ID,
    SafeLiberoOpenRegionBindingV2,
    SafeLiberoOpenRegionRuntimeV2,
)


def _issuer(
    producer_id: str = "source-bound-observer",
    producer_version: str = "1",
) -> Ed25519EvidenceIssuer:
    return Ed25519EvidenceIssuer.generate_for_testing(producer_id, producer_version)


def _attestation(issuer: Ed25519EvidenceIssuer):
    return issuer.issue(
        "ctda_v2_progress_observation",
        digest_text("progress-claim"),
        payload={"state_epoch": 2, "distance_after_m": 0.1},
        issued_at_ns=100,
        valid_until_ns=120,
        assumptions=("simulator", "source-bound"),
    )


def test_ed25519_attestation_round_trip_and_exact_identity_binding() -> None:
    issuer = _issuer()
    attestation = _attestation(issuer)

    assert attestation.proof_digest.startswith(ED25519_PROOF_PREFIX)
    assert issuer.verifier.verify(attestation)
    assert issuer.key_fingerprint == issuer.public_key_binding.key_fingerprint
    assert len(issuer.public_key_binding.public_key_bytes) == 32
    assert not Ed25519EvidenceVerifier(
        (
            Ed25519PublicKeyBinding(
                "source-bound-observer",
                "2",
                issuer.public_key_binding.public_key_bytes,
            ),
        )
    ).verify(attestation)


@pytest.mark.parametrize(
    "change",
    [
        {"subject_digest": digest_text("other-claim")},
        {"payload_digest": digest_text("other-payload")},
        {"issued_at_ns": 99},
        {"valid_until_ns": 121},
        {"assumptions": ("source-bound",)},
        {"producer_version": "2"},
    ],
)
def test_ed25519_signature_rejects_bound_field_tamper(change) -> None:
    issuer = _issuer()
    attestation = _attestation(issuer)

    tampered = replace(attestation, **change)

    assert tampered.verify_integrity()
    assert not issuer.verifier.verify(tampered)


def test_ed25519_signature_rejects_malformed_proof_wrong_key_and_revocation() -> None:
    issuer = _issuer()
    other = _issuer("other-observer", "1")
    attestation = _attestation(issuer)
    malformed = replace(attestation, proof_digest=ED25519_PROOF_PREFIX + "AA")
    wrong_key = Ed25519EvidenceVerifier(
        (
            Ed25519PublicKeyBinding(
                issuer.producer_id,
                issuer.producer_version,
                other.public_key_binding.public_key_bytes,
            ),
        )
    )
    revoked = Ed25519EvidenceVerifier(
        (issuer.public_key_binding,),
        revoked_key_fingerprints=(issuer.key_fingerprint,),
    )

    assert not issuer.verifier.verify(malformed)
    assert not wrong_key.verify(attestation)
    assert not revoked.verify(attestation)


def test_ed25519_keyring_supports_multiple_non_impersonating_producers() -> None:
    source = _issuer("source-observer", "1")
    checker = _issuer("ctda-fast-checker", "2")
    verifier = Ed25519EvidenceVerifier(
        (source.public_key_binding, checker.public_key_binding)
    )
    source_evidence = _attestation(source)
    checker_evidence = checker.issue(
        "ctda_v2_command_membership",
        digest_text("decision-claim"),
        payload={"adjusted_command": digest_text("adjusted")},
        issued_at_ns=100,
        valid_until_ns=110,
    )

    assert verifier.verify(source_evidence)
    assert verifier.verify(checker_evidence)
    with pytest.raises(ValueError, match="impersonate"):
        source.issue(
            "ctda_v2_state_rebind",
            digest_text("lease"),
            payload={},
            issued_at_ns=100,
            valid_until_ns=110,
            producer_id=checker.producer_id,
            producer_version=checker.producer_version,
        )


def test_ed25519_private_key_import_is_deterministic_and_length_checked() -> None:
    private_key = bytes(range(32))
    first = Ed25519EvidenceIssuer.from_private_bytes("producer", "1", private_key)
    second = Ed25519EvidenceIssuer.from_private_bytes("producer", "1", private_key)

    assert first.key_fingerprint == second.key_fingerprint
    assert first.verifier.verify(_attestation(first))
    with pytest.raises(ValueError, match="32 bytes"):
        Ed25519EvidenceIssuer.from_private_bytes("producer", "1", b"short")


def test_ed25519_source_evidence_drives_open_region_progress_checker() -> None:
    issuer = _issuer("official-safelibero-joint-observer", "signed-v1")
    runtime = SafeLiberoOpenRegionRuntimeV2(
        binding=SafeLiberoOpenRegionBindingV2(
            goal_manifest_digest=digest_text("drawer-goal"),
            mission_step_digest=digest_text("drawer-open-step"),
            source_identity_digest=digest_text("official-source"),
        ),
        producer_id=issuer.producer_id,
        producer_version=issuer.producer_version,
        max_sensor_age_ns=100,
    )
    producer = SafeLiberoOpenRegionProgressProducerV2(runtime, issuer, 100)

    def snapshot(epoch: int, observed_at_ns: int) -> RelevantStateSnapshotV2:
        return RelevantStateSnapshotV2(
            episode_nonce="signed-drawer-episode",
            state_epoch=epoch,
            observed_at_ns=observed_at_ns,
            producer_id="signed-state-observer",
            producer_version="1",
            provenance_digest=digest_text("signed-state-observer"),
            max_sensor_age_ns=100,
            status=SnapshotStatus.OBSERVED,
            state_digest=digest_text(f"state-{epoch}"),
        )

    certificate_digest = digest_text("signed-progress-certificate")
    packet = producer.produce(
        certificate_digest=certificate_digest,
        before_base_state=snapshot(1, 10),
        after_base_state=snapshot(2, 20),
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
        checker_id="ctda-v2-fast-checker",
        checker_version="signed-v1",
        checker_digest=digest_text("signed-checker"),
        lean_producer_id="proofalign-lean-kernel",
        lean_producer_version="4.24.0",
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

    assert issuer.verifier.verify(packet.progress.progress_attestation)
    assert update.check.proven
    assert update.required_intervention is Intervention.PASS
