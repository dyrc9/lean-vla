"""Typed, authenticated AEGIS geometry-to-CBF coefficient producer.

This module mirrors the pure geometry portion of the pinned AEGIS
``compute_h_coeffs_3d`` implementation using fixed-size scalar operations.  It
accepts only a fresh, signed geometry observation and returns a source-bound
``AegisCBFConstraintV2``.  It does not acquire images, build point clouds, fit
ellipsoids, construct a simulator, query a policy, or dispatch an action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
import re
from typing import Any

from proofalign.ctda import EvidenceAttestation, EvidenceVerifier, digest_payload
from proofalign.ctda_runtime import CTDAEvidenceIssuer
from proofalign.benchmark.aegis_cbf_filter import (
    AegisCBFConstraintV2,
    AegisCBFSourceIdentityV2,
)


AEGIS_GEOMETRY_SCHEMA = "proofalign.aegis-cbf-geometry-v1"
AEGIS_GEOMETRY_EVIDENCE_TYPE = "aegis_cbf_geometry_observation"
AEGIS_GEOMETRY_PRODUCER_ID = "aegis-typed-geometry-observation"
AEGIS_GEOMETRY_PRODUCER_VERSION = "57b1aef-geometry-input-v1"
AEGIS_GEOMETRY_EPSILON = 1e-10
AEGIS_PROJECT_EPSILON = 1e-12


def _finite_tuple(name: str, values: tuple[float, ...], size: int) -> tuple[float, ...]:
    if len(values) != size:
        raise ValueError(f"{name} must contain {size} scalars")
    if any(type(value) not in (int, float) or not isfinite(float(value)) for value in values):
        raise ValueError(f"{name} contains a non-finite or non-numeric scalar")
    return tuple(float(value) for value in values)


def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _norm(vector: tuple[float, ...]) -> float:
    return sqrt(_dot(vector, vector))


def _matvec(matrix: tuple[float, ...], vector: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        sum(matrix[row * 3 + column] * vector[column] for column in range(3))
        for row in range(3)
    )


def _row_mat(vector: tuple[float, ...], matrix: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        sum(vector[row] * matrix[row * 3 + column] for row in range(3))
        for column in range(3)
    )


def _matmul(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        sum(left[row * 3 + inner] * right[inner * 3 + column] for inner in range(3))
        for row in range(3)
        for column in range(3)
    )


def _transpose(matrix: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(matrix[row * 3 + column] for column in range(3) for row in range(3))


def _scale(vector: tuple[float, ...], scalar: float) -> tuple[float, ...]:
    return tuple(scalar * value for value in vector)


def _add(*vectors: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(sum(values) for values in zip(*vectors))


def _sub(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(a - b for a, b in zip(left, right))


def _inverse(matrix: tuple[float, ...]) -> tuple[float, ...]:
    a, b, c, d, e, f, g, h, i = matrix
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(determinant) <= 1e-15:
        raise ValueError("AEGIS geometry shape matrix is singular")
    inverse_det = 1.0 / determinant
    return (
        (e * i - f * h) * inverse_det,
        (c * h - b * i) * inverse_det,
        (b * f - c * e) * inverse_det,
        (f * g - d * i) * inverse_det,
        (a * i - c * g) * inverse_det,
        (c * d - a * f) * inverse_det,
        (d * h - e * g) * inverse_det,
        (b * g - a * h) * inverse_det,
        (a * e - b * d) * inverse_det,
    )


def _hat(vector: tuple[float, ...]) -> tuple[float, ...]:
    x, y, z = vector
    return (0.0, -z, y, z, 0.0, -x, -y, x, 0.0)


def _diagonal(values: tuple[float, ...]) -> tuple[float, ...]:
    return (values[0], 0.0, 0.0, 0.0, values[1], 0.0, 0.0, 0.0, values[2])


def _rotation_issue(rotation: tuple[float, ...]) -> str | None:
    product = _matmul(rotation, _transpose(rotation))
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    if max(abs(actual - expected) for actual, expected in zip(product, identity)) > 1e-6:
        return "AEGIS geometry rotation is not orthonormal"
    determinant = (
        rotation[0] * (rotation[4] * rotation[8] - rotation[5] * rotation[7])
        - rotation[1] * (rotation[3] * rotation[8] - rotation[5] * rotation[6])
        + rotation[2] * (rotation[3] * rotation[7] - rotation[4] * rotation[6])
    )
    return None if abs(determinant - 1.0) <= 1e-6 else "AEGIS geometry rotation determinant is not +1"


@dataclass(frozen=True)
class AegisGeometryObservationV2:
    source_identity_digest: str
    state_snapshot_digest: str
    safety_bundle_digest: str
    observed_at_ns: int
    robot_center: tuple[float, float, float]
    robot_shape_diagonal: tuple[float, float, float]
    robot_rotation: tuple[float, ...]
    obstacle_center: tuple[float, float, float]
    obstacle_shape_diagonal: tuple[float, float, float]
    obstacle_rotation: tuple[float, ...]
    direction_z: tuple[float, float, float]
    raw_provenance_digest: str
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "source_identity_digest",
            "state_snapshot_digest",
            "safety_bundle_digest",
            "raw_provenance_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a SHA-256 digest")
        if self.observed_at_ns < 0:
            raise ValueError("AEGIS geometry observation time must be non-negative")
        robot_center = _finite_tuple("robot_center", self.robot_center, 3)
        robot_shape = _finite_tuple("robot_shape_diagonal", self.robot_shape_diagonal, 3)
        robot_rotation = _finite_tuple("robot_rotation", self.robot_rotation, 9)
        obstacle_center = _finite_tuple("obstacle_center", self.obstacle_center, 3)
        obstacle_shape = _finite_tuple("obstacle_shape_diagonal", self.obstacle_shape_diagonal, 3)
        obstacle_rotation = _finite_tuple("obstacle_rotation", self.obstacle_rotation, 9)
        direction = _finite_tuple("direction_z", self.direction_z, 3)
        if any(value <= 0.0 for value in robot_shape + obstacle_shape):
            raise ValueError("AEGIS geometry shape diagonals must be positive")
        for rotation in (robot_rotation, obstacle_rotation):
            issue = _rotation_issue(rotation)
            if issue is not None:
                raise ValueError(issue)
        if _norm(direction) <= AEGIS_GEOMETRY_EPSILON:
            raise ValueError("AEGIS geometry direction must be nonzero")
        object.__setattr__(self, "robot_center", robot_center)
        object.__setattr__(self, "robot_shape_diagonal", robot_shape)
        object.__setattr__(self, "robot_rotation", robot_rotation)
        object.__setattr__(self, "obstacle_center", obstacle_center)
        object.__setattr__(self, "obstacle_shape_diagonal", obstacle_shape)
        object.__setattr__(self, "obstacle_rotation", obstacle_rotation)
        object.__setattr__(self, "direction_z", direction)
        object.__setattr__(self, "observation_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": AEGIS_GEOMETRY_SCHEMA,
            "source_identity_digest": self.source_identity_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "safety_bundle_digest": self.safety_bundle_digest,
            "observed_at_ns": self.observed_at_ns,
            "robot_center": self.robot_center,
            "robot_shape_diagonal": self.robot_shape_diagonal,
            "robot_rotation": self.robot_rotation,
            "obstacle_center": self.obstacle_center,
            "obstacle_shape_diagonal": self.obstacle_shape_diagonal,
            "obstacle_rotation": self.obstacle_rotation,
            "direction_z": self.direction_z,
            "raw_provenance_digest": self.raw_provenance_digest,
        }


@dataclass(frozen=True)
class SignedAegisGeometryObservationV2:
    observation: AegisGeometryObservationV2
    attestation: EvidenceAttestation
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_digest",
            digest_payload(
                {
                    "schema": AEGIS_GEOMETRY_SCHEMA,
                    "observation_digest": self.observation.observation_digest,
                    "attestation_digest": self.attestation.attestation_digest,
                }
            ),
        )

    def attestation_payload(self) -> dict[str, Any]:
        return {"schema": AEGIS_GEOMETRY_SCHEMA, "observation": self.observation.payload()}


def sign_aegis_geometry_observation(
    observation: AegisGeometryObservationV2,
    issuer: CTDAEvidenceIssuer,
    *,
    issued_at_ns: int,
    valid_until_ns: int,
) -> SignedAegisGeometryObservationV2:
    if (
        issuer.producer_id != AEGIS_GEOMETRY_PRODUCER_ID
        or issuer.producer_version != AEGIS_GEOMETRY_PRODUCER_VERSION
    ):
        raise ValueError("AEGIS geometry signer identity does not match the frozen producer")
    payload = {"schema": AEGIS_GEOMETRY_SCHEMA, "observation": observation.payload()}
    attestation = issuer.issue(
        AEGIS_GEOMETRY_EVIDENCE_TYPE,
        observation.observation_digest,
        payload=payload,
        issued_at_ns=issued_at_ns,
        valid_until_ns=valid_until_ns,
        assumptions=(
            "raw-perception-and-ellipsoid-fit-external",
            "pinned-aegis-geometry-schema",
            "no-action-no-dispatch",
        ),
        producer_id=AEGIS_GEOMETRY_PRODUCER_ID,
        producer_version=AEGIS_GEOMETRY_PRODUCER_VERSION,
    )
    return SignedAegisGeometryObservationV2(observation, attestation)


def _compute_coefficients(
    observation: AegisGeometryObservationV2,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    float,
    tuple[float, float, float],
]:
    p_i = observation.robot_center
    p_j = observation.obstacle_center
    delta = _sub(p_j, p_i)
    r_i = observation.robot_rotation
    r_j = observation.obstacle_rotation
    q_i = _diagonal(observation.robot_shape_diagonal)
    q_j = _diagonal(observation.obstacle_shape_diagonal)
    qbar_i = _matmul(_matmul(r_i, q_i), _transpose(r_i))
    qbar_j = _matmul(_matmul(r_j, q_j), _transpose(r_j))
    qbar_i_inverse = _inverse(qbar_i)
    qbar_i_inverse2 = _matmul(qbar_i_inverse, qbar_i_inverse)
    qbar_j2 = _matmul(qbar_j, qbar_j)

    z_raw = observation.direction_z
    z = _scale(z_raw, 1.0 / (_norm(z_raw) + AEGIS_GEOMETRY_EPSILON))
    a_vec = _matvec(qbar_i_inverse, z)
    denominator = _norm(a_vec) + AEGIS_GEOMETRY_EPSILON
    b_vec = _matvec(qbar_j, a_vec)
    term1 = _norm(b_vec) + AEGIS_GEOMETRY_EPSILON
    sigma = term1 * denominator + AEGIS_GEOMETRY_EPSILON
    rho = 1.0 - _dot(delta, a_vec) + term1

    eta_row = _scale(_row_mat(z, qbar_i_inverse), -1.0 / denominator)
    mu_1 = _scale(
        _row_mat(z, qbar_i_inverse2),
        rho / (denominator**3 + AEGIS_GEOMETRY_EPSILON),
    )
    mu_2 = _scale(_row_mat(delta, qbar_i_inverse), 1.0 / denominator)
    mu_3_matrix = _matmul(_matmul(qbar_i_inverse, qbar_j2), qbar_i_inverse)
    mu_3 = _scale(_row_mat(z, mu_3_matrix), 1.0 / sigma)
    mu_row = _sub(_add(mu_1, mu_2), mu_3)

    tmp1 = _row_mat(_row_mat(z, qbar_i_inverse2), _hat(z))
    left = _row_mat(_row_mat(z, qbar_i_inverse), qbar_j2)
    tmp2_matrix = tuple(
        a - b
        for a, b in zip(_hat(a_vec), _matmul(qbar_i_inverse, _hat(z)))
    )
    tmp2 = _row_mat(left, tmp2_matrix)
    tmp3 = _add(
        _row_mat(_row_mat(delta, qbar_i_inverse), _hat(z)),
        _row_mat(_row_mat(z, qbar_i_inverse), _hat(delta)),
    )
    zeta = _add(
        _scale(tmp1, rho / (denominator**3 + AEGIS_GEOMETRY_EPSILON)),
        _scale(tmp2, 1.0 / sigma),
        _scale(tmp3, 1.0 / denominator),
    )
    a_v = _row_mat(eta_row, r_i)
    a_omega = _row_mat(zeta, r_i)

    project_z = _scale(z, 1.0 / (_norm(z) + AEGIS_PROJECT_EPSILON))
    projection = tuple(
        (1.0 if row == column else 0.0) - project_z[row] * project_z[column]
        for row in range(3)
        for column in range(3)
    )
    a_uz = _row_mat(mu_row, projection)

    h_z = _scale(z, 1.0 / _norm(z))
    h_inverse_z = _matvec(qbar_i_inverse, h_z)
    h_term1 = _norm(_matvec(qbar_j, h_inverse_z))
    h_term2 = _dot(delta, h_inverse_z)
    h_value = (-h_term1 + h_term2 - 1.0) / _norm(h_inverse_z)
    return (
        tuple(a_v),  # type: ignore[return-value]
        tuple(a_omega),  # type: ignore[return-value]
        tuple(a_uz),  # type: ignore[return-value]
        h_value,
        tuple(mu_row),  # type: ignore[return-value]
    )


@dataclass(frozen=True)
class AegisCBFCoefficientProducerV2:
    source_identity: AegisCBFSourceIdentityV2
    geometry_verifier: EvidenceVerifier
    max_observation_age_ns: int

    def __post_init__(self) -> None:
        if self.max_observation_age_ns <= 0:
            raise ValueError("AEGIS geometry observation lifetime must be positive")

    def derive(
        self,
        evidence: SignedAegisGeometryObservationV2,
        *,
        now_ns: int,
    ) -> AegisCBFConstraintV2:
        observation = evidence.observation
        attestation = evidence.attestation
        issues: list[str] = []
        if observation.source_identity_digest != self.source_identity.source_identity_digest:
            issues.append("AEGIS geometry source identity mismatch")
        if attestation.evidence_type != AEGIS_GEOMETRY_EVIDENCE_TYPE:
            issues.append("AEGIS geometry evidence type mismatch")
        if attestation.subject_digest != observation.observation_digest:
            issues.append("AEGIS geometry attestation subject mismatch")
        if attestation.payload_digest != digest_payload(evidence.attestation_payload()):
            issues.append("AEGIS geometry attestation payload mismatch")
        if (
            attestation.producer_id != AEGIS_GEOMETRY_PRODUCER_ID
            or attestation.producer_version != AEGIS_GEOMETRY_PRODUCER_VERSION
        ):
            issues.append("AEGIS geometry producer identity mismatch")
        if not attestation.is_fresh(now_ns):
            issues.append("AEGIS geometry attestation is stale or not yet valid")
        if not (0 <= now_ns - observation.observed_at_ns <= self.max_observation_age_ns):
            issues.append("AEGIS geometry observation is stale or not yet valid")
        if observation.observed_at_ns > attestation.issued_at_ns:
            issues.append("AEGIS geometry attestation predates its observation")
        if not self.geometry_verifier.verify(attestation):
            issues.append("AEGIS geometry signature is not authenticated")
        if issues:
            raise ValueError("; ".join(issues))
        a_v, a_omega, a_uz, h_value, mu_row = _compute_coefficients(observation)
        return AegisCBFConstraintV2(
            source_identity_digest=self.source_identity.source_identity_digest,
            state_snapshot_digest=observation.state_snapshot_digest,
            safety_bundle_digest=observation.safety_bundle_digest,
            observed_at_ns=observation.observed_at_ns,
            rotation_world_from_eef=observation.robot_rotation,
            direction_z=tuple(
                value / _norm(observation.direction_z) for value in observation.direction_z
            ),  # type: ignore[arg-type]
            a_v=a_v,
            a_omega=a_omega,
            a_uz=a_uz,
            h=h_value,
            mu_row=mu_row,
            provenance_digest=evidence.evidence_digest,
        )


__all__ = [
    "AEGIS_GEOMETRY_EVIDENCE_TYPE",
    "AEGIS_GEOMETRY_PRODUCER_ID",
    "AEGIS_GEOMETRY_PRODUCER_VERSION",
    "AEGIS_GEOMETRY_SCHEMA",
    "AegisCBFCoefficientProducerV2",
    "AegisGeometryObservationV2",
    "SignedAegisGeometryObservationV2",
    "sign_aegis_geometry_observation",
]
