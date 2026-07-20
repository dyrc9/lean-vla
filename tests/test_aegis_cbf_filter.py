from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from proofalign.ctda import StaticVerdict, digest_payload, digest_text
from proofalign.ctda_v2 import (
    ActiveContractContextV2,
    ContractLeaseClaimV2,
    ContractLeaseV2,
    CTDAV2ReferenceChecker,
    Intervention,
    RelevantStateSnapshotV2,
    SafetyChannelEvidenceV2,
    SafetyEvidenceBundleV2,
    SemanticCertificateClaimV2,
    SemanticCertificateV2,
    SnapshotStatus,
)
from proofalign.evidence_crypto import (
    Ed25519EvidenceIssuer,
    Ed25519EvidenceVerifier,
)
from proofalign.benchmark.aegis_cbf_filter import (
    AEGIS_FILTER_ID,
    AEGIS_FILTER_VERSION,
    AegisCBFConstraintV2,
    AegisCBFNoActionFilterV2,
    AegisCBFSourceIdentityV2,
    SignedAegisCBFFilterEvidenceV2,
    SignedAegisPostFilterNoDispatchAdapterV2,
    audit_aegis_cbf_source,
)
from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import (
    SafeLiberoCommandV2,
    SafeLiberoPostFilterNoDispatchAdapterV2,
)


ROOT = Path(__file__).resolve().parents[1]
AEGIS = ROOT / "external" / "vlsa-aegis"
SOURCE_COMMIT = "57b1aef306f212aea3574b0a3b64aa1a3d8f5e4b"
SOURCE_TREE = "1b55f9d97f0ae57b97e68fcb1177e524b096d13b"
CHECKER_ID = "ctda-v2-fast-checker"
CHECKER_VERSION = "aegis-signed-v1"
CHECKER_DIGEST = digest_text("aegis-signed-checker")
LEAN_ID = "proofalign-lean-kernel"
LEAN_VERSION = "4.24.0-test"


def _source_identity() -> AegisCBFSourceIdentityV2:
    return AegisCBFSourceIdentityV2(
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
        file_sha256=(
            ("controller", digest_text("pinned-main-aegis")),
            ("geometry", digest_text("pinned-aegis-utils")),
        ),
    )


def _constraint(
    source: AegisCBFSourceIdentityV2,
    *,
    state_snapshot_digest: str = digest_text("state-snapshot"),
    safety_bundle_digest: str = digest_text("safety-bundle"),
    observed_at_ns: int = 104,
    a_v: tuple[float, float, float] = (1.0, 0.0, 0.0),
    a_uz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    h: float = 0.0,
) -> AegisCBFConstraintV2:
    return AegisCBFConstraintV2(
        source_identity_digest=source.source_identity_digest,
        state_snapshot_digest=state_snapshot_digest,
        safety_bundle_digest=safety_bundle_digest,
        observed_at_ns=observed_at_ns,
        rotation_world_from_eef=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        direction_z=(0.0, 0.0, 1.0),
        a_v=a_v,
        a_omega=(0.0, 0.0, 0.0),
        a_uz=a_uz,
        h=h,
        mu_row=(0.0, 0.0, 0.0),
        provenance_digest=digest_text("aegis-coefficient-provenance"),
    )


def _filter(source: AegisCBFSourceIdentityV2):
    signer = Ed25519EvidenceIssuer.generate_for_testing(
        AEGIS_FILTER_ID, AEGIS_FILTER_VERSION
    )
    return AegisCBFNoActionFilterV2(source, signer, 10, 20), signer


@pytest.mark.skipif(not AEGIS.is_dir(), reason="official AEGIS checkout is absent")
def test_aegis_cbf_source_identity_pins_controller_and_geometry() -> None:
    identity = audit_aegis_cbf_source(
        AEGIS,
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
    )

    assert identity.source_commit == SOURCE_COMMIT
    assert identity.source_tree == SOURCE_TREE
    assert set(dict(identity.file_sha256)) == {"controller", "geometry"}


def test_aegis_nominal_admissible_command_is_preserved_and_signed() -> None:
    source = _source_identity()
    filter_runtime, signer = _filter(source)
    nominal = SafeLiberoCommandV2((0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))

    evidence = filter_runtime.produce(nominal, _constraint(source), now_ns=105)

    assert evidence.result.projection_active is False
    assert evidence.result.adjusted_command.command_digest == nominal.command_digest
    assert evidence.result.nominal_constraint_residual == pytest.approx(0.1)
    assert evidence.result.adjusted_admissible is True
    assert evidence.witness.status is SnapshotStatus.OBSERVED
    assert signer.verifier.verify(evidence.filter_attestation)


def test_aegis_unsafe_nominal_is_weighted_projected_to_cbf_boundary() -> None:
    source = _source_identity()
    filter_runtime, signer = _filter(source)
    nominal = SafeLiberoCommandV2((-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))

    evidence = filter_runtime.produce(nominal, _constraint(source), now_ns=105)

    assert evidence.result.projection_active is True
    assert evidence.result.nominal_constraint_residual == pytest.approx(-0.1)
    assert evidence.result.adjusted_constraint_residual == pytest.approx(0.0, abs=1e-12)
    assert evidence.result.adjusted_command.values[0] == pytest.approx(0.0, abs=1e-12)
    assert evidence.result.adjusted_command.values[6] == nominal.values[6]
    assert evidence.witness.adjusted_admissible is True
    assert signer.verifier.verify(evidence.filter_attestation)
    assert not hasattr(filter_runtime, "step")
    assert not hasattr(filter_runtime, "dispatch")


def test_aegis_direction_update_matches_normalized_source_euler_step() -> None:
    source = _source_identity()
    filter_runtime, _ = _filter(source)
    nominal = SafeLiberoCommandV2((0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    constraint = replace(
        _constraint(source),
        mu_row=(1.0, 0.0, 0.0),
    )

    evidence = filter_runtime.produce(nominal, constraint, now_ns=105)

    # u_z = 10 * mu_row and dt = 0.05, so the source update is
    # normalize((0, 0, 1) + 0.05 * (10, 0, 0)).
    assert evidence.result.next_direction_z == pytest.approx(
        (1.0 / 5.0 ** 0.5, 0.0, 2.0 / 5.0 ** 0.5)
    )
    assert sum(value * value for value in evidence.result.next_direction_z) == pytest.approx(1.0)


@pytest.mark.parametrize("failure", ["stale", "source", "degenerate"])
def test_aegis_untrusted_or_infeasible_constraint_produces_unknown_witness(failure) -> None:
    source = _source_identity()
    filter_runtime, signer = _filter(source)
    nominal = SafeLiberoCommandV2((-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    constraint = _constraint(source)
    now_ns = 105
    if failure == "stale":
        constraint = replace(constraint, observed_at_ns=80)
    elif failure == "source":
        constraint = replace(
            constraint, source_identity_digest=digest_text("foreign-aegis-source")
        )
    else:
        constraint = _constraint(
            source,
            a_v=(0.0, 0.0, 0.0),
            a_uz=(0.0, 0.0, 0.0),
            h=-0.1,
        )

    evidence = filter_runtime.produce(nominal, constraint, now_ns=now_ns)

    assert evidence.witness.status is SnapshotStatus.UNKNOWN
    assert evidence.witness.adjusted_admissible is None
    assert evidence.witness.unknown_reason
    assert signer.verifier.verify(evidence.filter_attestation)


def _ctda_fixture(source: AegisCBFSourceIdentityV2):
    filter_signer = Ed25519EvidenceIssuer.generate_for_testing(
        AEGIS_FILTER_ID, AEGIS_FILTER_VERSION
    )
    checker_signer = Ed25519EvidenceIssuer.generate_for_testing(
        CHECKER_ID, CHECKER_VERSION
    )
    lean_signer = Ed25519EvidenceIssuer.generate_for_testing(LEAN_ID, LEAN_VERSION)
    verifier = Ed25519EvidenceVerifier(
        (
            filter_signer.public_key_binding,
            checker_signer.public_key_binding,
            lean_signer.public_key_binding,
        )
    )

    def snapshot(epoch: int, observed_at_ns: int, state: str) -> RelevantStateSnapshotV2:
        return RelevantStateSnapshotV2(
            episode_nonce="aegis-filter-episode",
            state_epoch=epoch,
            observed_at_ns=observed_at_ns,
            producer_id="typed-safelibero-state",
            producer_version="1",
            provenance_digest=digest_text("typed-safelibero-state"),
            max_sensor_age_ns=1_000,
            status=SnapshotStatus.OBSERVED,
            state_digest=digest_text(state),
        )

    proof_state = snapshot(0, 10, "proof")
    certificate_claim = SemanticCertificateClaimV2(
        mission_root_digest=digest_text("mission-root"),
        episode_nonce=proof_state.episode_nonce,
        phase="approach",
        residual_obligations=("open-drawer",),
        contract_version="aegis-filter-v2",
        proof_state=proof_state,
        action_set_digest=digest_text("action-set"),
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_proof_artifact_digest=digest_text("lean-proof"),
        proof_started_at_ns=20,
    )
    proof = lean_signer.issue(
        "ctda_v2_semantic_certificate",
        certificate_claim.claim_digest,
        payload=certificate_claim.payload(),
        issued_at_ns=100,
        valid_until_ns=1_000,
    )
    certificate = SemanticCertificateV2(
        certificate_claim, proof_completed_at_ns=100, proof_attestation=proof
    )
    activation = snapshot(1, 101, "activation")
    lease_claim = ContractLeaseClaimV2(
        certificate_digest=certificate.certificate_digest,
        activation_state=activation,
        checker_digest=CHECKER_DIGEST,
        activated_at_ns=102,
        activated_control_epoch=7,
        valid_through_control_epoch=15,
    )
    rebind = checker_signer.issue(
        "ctda_v2_state_rebind",
        lease_claim.claim_digest,
        payload=lease_claim.payload(),
        issued_at_ns=102,
        valid_until_ns=1_000,
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
    checker = CTDAV2ReferenceChecker(
        evidence_verifier=verifier,
        checker_id=CHECKER_ID,
        checker_version=CHECKER_VERSION,
        checker_digest=CHECKER_DIGEST,
        lean_producer_id=LEAN_ID,
        lean_producer_version=LEAN_VERSION,
    )
    filter_runtime = AegisCBFNoActionFilterV2(source, filter_signer, 10, 20)
    adapter = SafeLiberoPostFilterNoDispatchAdapterV2(
        checker=checker,
        issuer=checker_signer,
        filter_id=AEGIS_FILTER_ID,
        filter_version=AEGIS_FILTER_VERSION,
        filter_digest=filter_runtime.filter_digest,
        max_filter_witness_age_ns=10,
        membership_valid_for_ns=20,
        authorization_valid_for_ns=10,
    )
    signed_adapter = SignedAegisPostFilterNoDispatchAdapterV2(adapter, verifier)
    return filter_runtime, signed_adapter, certificate, lease, context, safety


def test_signed_aegis_projection_reaches_ctda_authorization_without_dispatch() -> None:
    source = _source_identity()
    filter_runtime, adapter, certificate, lease, context, safety = _ctda_fixture(source)
    nominal = SafeLiberoCommandV2((-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    constraint = _constraint(
        source,
        state_snapshot_digest=lease.claim.activation_state.snapshot_digest,
        safety_bundle_digest=safety.bundle_digest,
    )
    evidence = filter_runtime.produce(nominal, constraint, now_ns=105)

    transaction = adapter.evaluate(
        certificate=certificate,
        lease=lease,
        context=context,
        safety=safety,
        filter_evidence=evidence,
        proposal_index=0,
        now_ns=105,
    )

    assert transaction.filter_evidence_check.proven
    assert transaction.transaction.decision.claim.intervention is Intervention.PROJECT_OR_BRAKE
    assert transaction.transaction.authorization_ready is True
    assert transaction.transaction.dispatch_count == 0
    assert transaction.formal_rollout_authorized is False


def test_signed_aegis_full_result_tamper_hard_blocks_before_authorization() -> None:
    source = _source_identity()
    filter_runtime, adapter, certificate, lease, context, safety = _ctda_fixture(source)
    nominal = SafeLiberoCommandV2((-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0))
    constraint = _constraint(
        source,
        state_snapshot_digest=lease.claim.activation_state.snapshot_digest,
        safety_bundle_digest=safety.bundle_digest,
    )
    evidence = filter_runtime.produce(nominal, constraint, now_ns=105)
    tampered_result = replace(
        evidence.result,
        next_direction_z=(0.0, 1.0, 0.0),
    )
    tampered = SignedAegisCBFFilterEvidenceV2(
        tampered_result,
        evidence.witness,
        evidence.filter_attestation,
    )

    transaction = adapter.evaluate(
        certificate=certificate,
        lease=lease,
        context=context,
        safety=safety,
        filter_evidence=tampered,
        proposal_index=0,
        now_ns=105,
    )

    assert transaction.filter_evidence_check.verdict is StaticVerdict.REFUTED
    assert transaction.transaction.decision.claim.intervention is Intervention.HARD_BLOCK
    assert transaction.transaction.authorization is None
    assert transaction.transaction.dispatch_count == 0
