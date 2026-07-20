from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.ctda import digest_text
from proofalign.evidence_crypto import Ed25519EvidenceIssuer
from proofalign.benchmark.aegis_cbf_filter import (
    AEGIS_FILTER_ID,
    AEGIS_FILTER_VERSION,
    AegisCBFNoActionFilterV2,
    AegisCBFSourceIdentityV2,
)
from proofalign.benchmark.aegis_cbf_geometry import (
    AEGIS_GEOMETRY_PRODUCER_ID,
    AEGIS_GEOMETRY_PRODUCER_VERSION,
    AegisCBFCoefficientProducerV2,
    AegisGeometryObservationV2,
    SignedAegisGeometryObservationV2,
    sign_aegis_geometry_observation,
)
from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import SafeLiberoCommandV2


IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _source() -> AegisCBFSourceIdentityV2:
    return AegisCBFSourceIdentityV2(
        source_commit="57b1aef306f212aea3574b0a3b64aa1a3d8f5e4b",
        source_tree="1b55f9d97f0ae57b97e68fcb1177e524b096d13b",
        file_sha256=(
            ("controller", digest_text("main-aegis")),
            ("geometry", digest_text("utils")),
        ),
    )


def _observation(
    source: AegisCBFSourceIdentityV2,
    *,
    observed_at_ns: int = 100,
) -> AegisGeometryObservationV2:
    return AegisGeometryObservationV2(
        source_identity_digest=source.source_identity_digest,
        state_snapshot_digest=digest_text("geometry-state"),
        safety_bundle_digest=digest_text("geometry-safety"),
        observed_at_ns=observed_at_ns,
        robot_center=(0.0, 0.0, 0.0),
        robot_shape_diagonal=(0.06, 0.12, 0.11),
        robot_rotation=IDENTITY,
        obstacle_center=(0.3, 0.1, 0.05),
        obstacle_shape_diagonal=(0.08, 0.15, 0.2),
        obstacle_rotation=IDENTITY,
        direction_z=(1.0, 0.0, 0.0),
        raw_provenance_digest=digest_text("ellipsoid-fit-output"),
    )


def _signed(source: AegisCBFSourceIdentityV2):
    signer = Ed25519EvidenceIssuer.generate_for_testing(
        AEGIS_GEOMETRY_PRODUCER_ID, AEGIS_GEOMETRY_PRODUCER_VERSION
    )
    observation = _observation(source)
    evidence = sign_aegis_geometry_observation(
        observation,
        signer,
        issued_at_ns=101,
        valid_until_ns=120,
    )
    return evidence, signer


def test_signed_geometry_derives_source_bound_finite_constraint() -> None:
    source = _source()
    evidence, signer = _signed(source)
    producer = AegisCBFCoefficientProducerV2(source, signer.verifier, 10)

    constraint = producer.derive(evidence, now_ns=105)

    assert constraint.source_identity_digest == source.source_identity_digest
    assert constraint.state_snapshot_digest == evidence.observation.state_snapshot_digest
    assert constraint.safety_bundle_digest == evidence.observation.safety_bundle_digest
    assert constraint.provenance_digest == evidence.evidence_digest
    assert constraint.direction_z == pytest.approx((1.0, 0.0, 0.0))
    assert all(abs(value) < float("inf") for value in constraint.a_v + constraint.a_omega + constraint.a_uz)
    assert abs(constraint.h) < float("inf")


def test_geometry_constraint_feeds_signed_no_action_filter() -> None:
    source = _source()
    evidence, signer = _signed(source)
    producer = AegisCBFCoefficientProducerV2(source, signer.verifier, 10)
    constraint = producer.derive(evidence, now_ns=105)
    filter_signer = Ed25519EvidenceIssuer.generate_for_testing(
        AEGIS_FILTER_ID, AEGIS_FILTER_VERSION
    )
    filter_runtime = AegisCBFNoActionFilterV2(source, filter_signer, 10, 20)

    result = filter_runtime.produce(
        SafeLiberoCommandV2((0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)),
        constraint,
        now_ns=105,
    )

    assert result.result.constraint.provenance_digest == evidence.evidence_digest
    assert filter_signer.verifier.verify(result.filter_attestation)
    assert not hasattr(producer, "step")
    assert not hasattr(producer, "dispatch")


@pytest.mark.parametrize(
    "failure", ["payload", "signature", "stale", "source", "causality"]
)
def test_untrusted_geometry_fails_closed_before_coefficient_derivation(failure: str) -> None:
    source = _source()
    evidence, signer = _signed(source)
    now_ns = 105
    if failure == "payload":
        tampered_observation = replace(
            evidence.observation,
            obstacle_center=(0.31, 0.1, 0.05),
        )
        evidence = SignedAegisGeometryObservationV2(tampered_observation, evidence.attestation)
    elif failure == "signature":
        foreign = Ed25519EvidenceIssuer.generate_for_testing(
            AEGIS_GEOMETRY_PRODUCER_ID, AEGIS_GEOMETRY_PRODUCER_VERSION
        )
        evidence = sign_aegis_geometry_observation(
            evidence.observation,
            foreign,
            issued_at_ns=101,
            valid_until_ns=120,
        )
    elif failure == "stale":
        now_ns = 121
    elif failure == "source":
        tampered_observation = replace(
            evidence.observation,
            source_identity_digest=digest_text("foreign-source"),
        )
        evidence = SignedAegisGeometryObservationV2(tampered_observation, evidence.attestation)
    else:
        future_observation = replace(evidence.observation, observed_at_ns=102)
        evidence = sign_aegis_geometry_observation(
            future_observation,
            signer,
            issued_at_ns=101,
            valid_until_ns=120,
        )
    producer = AegisCBFCoefficientProducerV2(source, signer.verifier, 10)

    with pytest.raises(ValueError):
        producer.derive(evidence, now_ns=now_ns)


def test_geometry_rejects_non_rotation_and_nonpositive_shape() -> None:
    source = _source()
    base = _observation(source)

    with pytest.raises(ValueError, match="orthonormal"):
        replace(base, robot_rotation=(1.0,) * 9)
    with pytest.raises(ValueError, match="positive"):
        replace(base, obstacle_shape_diagonal=(0.0, 0.1, 0.1))
