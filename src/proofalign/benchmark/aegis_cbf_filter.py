"""Source-bound AEGIS single-constraint CBF/QP producer without dispatch.

The pinned AEGIS controller minimizes a diagonal weighted quadratic objective
under one linear CBF half-space constraint.  This module evaluates the exact
closed-form weighted projection for that QP, records the latent nine-variable
solution and direction-state update, and signs the resulting filter witness.

No perception model, simulator, policy, socket, environment step, or actuator
is imported or invoked here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
from math import isfinite, sqrt
from pathlib import Path
import re
from typing import Any

from proofalign.ctda import EvidenceAttestation, EvidenceVerifier, StaticCheckResult, digest_payload
from proofalign.ctda_runtime import CTDAEvidenceIssuer
from proofalign.ctda_v2 import (
    ActiveContractContextV2,
    ContractLeaseV2,
    PrefixAuthorizationV2,
    PrefixDecisionV2,
    SafetyEvidenceBundleV2,
    SemanticCertificateV2,
    SnapshotStatus,
)
from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import (
    FILTER_WITNESS_SCHEMA,
    SafeLiberoCommandV2,
    SafeLiberoNoDispatchTransactionV2,
    SafeLiberoPostFilterNoDispatchAdapterV2,
    SafeLiberoPostFilterWitnessV2,
)


AEGIS_CBF_SCHEMA = "proofalign.aegis-cbf-filter-v1"
AEGIS_FILTER_ID = "aegis-cbf-qp-source-bound"
AEGIS_FILTER_VERSION = "57b1aef-single-halfspace-v1"
AEGIS_FILTER_EVIDENCE_TYPE = "ctda_v2_post_filter_witness"
AEGIS_ALPHA = 10.0
AEGIS_ACTION_SCALE = 0.2
AEGIS_REFERENCE_SCALE = 5.0
AEGIS_DIRECTION_SCALE = 10.0
AEGIS_DIRECTION_DT = 0.05
AEGIS_WEIGHT_DIAGONAL = (
    1.0 / 25.0,
    1.0 / 25.0,
    1.0 / 25.0,
    1.0 / 25.0,
    1.0 / 25.0,
    1.0 / 25.0,
    1.0,
    1.0,
    1.0,
)
AEGIS_PROJECTION_EPSILON = 1e-12
AEGIS_RESIDUAL_TOLERANCE = 1e-9

_SOURCE_PATHS = {
    "controller": "main/main_aegis.py",
    "geometry": "main/utils.py",
}


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _finite_tuple(name: str, values: tuple[float, ...], size: int) -> tuple[float, ...]:
    if len(values) != size:
        raise ValueError(f"{name} must contain {size} scalars")
    if any(type(value) not in (int, float) or not isfinite(float(value)) for value in values):
        raise ValueError(f"{name} contains a non-finite or non-numeric scalar")
    return tuple(float(value) for value in values)


def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _matvec(matrix: tuple[float, ...], vector: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        sum(matrix[row * 3 + column] * vector[column] for column in range(3))
        for row in range(3)
    )


def _transpose_matvec(
    matrix: tuple[float, ...], vector: tuple[float, ...]
) -> tuple[float, ...]:
    return tuple(
        sum(matrix[row * 3 + column] * vector[row] for row in range(3))
        for column in range(3)
    )


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    norm = sqrt(_dot(vector, vector))
    if norm <= AEGIS_PROJECTION_EPSILON:
        raise ValueError("AEGIS direction update produced a zero vector")
    return tuple(value / norm for value in vector)  # type: ignore[return-value]


def _rotation_issue(rotation: tuple[float, ...]) -> str | None:
    rows = tuple(tuple(rotation[row * 3 + column] for column in range(3)) for row in range(3))
    for row in range(3):
        for column in range(3):
            expected = 1.0 if row == column else 0.0
            if abs(_dot(rows[row], rows[column]) - expected) > 1e-6:
                return "AEGIS end-effector rotation is not orthonormal"
    determinant = (
        rotation[0] * (rotation[4] * rotation[8] - rotation[5] * rotation[7])
        - rotation[1] * (rotation[3] * rotation[8] - rotation[5] * rotation[6])
        + rotation[2] * (rotation[3] * rotation[7] - rotation[4] * rotation[6])
    )
    if abs(determinant - 1.0) > 1e-6:
        return "AEGIS end-effector rotation determinant is not +1"
    return None


@dataclass(frozen=True)
class AegisCBFSourceIdentityV2:
    source_commit: str
    source_tree: str
    file_sha256: tuple[tuple[str, str], ...]
    source_identity_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}", self.source_commit) is None:
            raise ValueError("AEGIS source commit is invalid")
        if re.fullmatch(r"[0-9a-f]{40}", self.source_tree) is None:
            raise ValueError("AEGIS source tree is invalid")
        files = tuple(sorted(self.file_sha256))
        if set(dict(files)) != set(_SOURCE_PATHS):
            raise ValueError("AEGIS CBF source identity does not cover the frozen files")
        if any(re.fullmatch(r"[0-9a-f]{64}", digest) is None for _, digest in files):
            raise ValueError("AEGIS CBF source identity contains an invalid file digest")
        object.__setattr__(self, "file_sha256", files)
        object.__setattr__(
            self,
            "source_identity_digest",
            digest_payload(
                {
                    "schema": AEGIS_CBF_SCHEMA,
                    "source_commit": self.source_commit,
                    "source_tree": self.source_tree,
                    "file_sha256": files,
                    "alpha": AEGIS_ALPHA,
                    "action_scale": AEGIS_ACTION_SCALE,
                    "reference_scale": AEGIS_REFERENCE_SCALE,
                    "direction_scale": AEGIS_DIRECTION_SCALE,
                    "direction_dt": AEGIS_DIRECTION_DT,
                    "weight_diagonal": AEGIS_WEIGHT_DIAGONAL,
                    "solver": "closed_form_weighted_single_halfspace_projection",
                }
            ),
        )


def audit_aegis_cbf_source(
    source_root: Path,
    *,
    source_commit: str,
    source_tree: str,
) -> AegisCBFSourceIdentityV2:
    """Pin the exact source statements mirrored by the no-action producer."""

    paths = {name: source_root / relative for name, relative in _SOURCE_PATHS.items()}
    if any(not path.is_file() for path in paths.values()):
        missing = sorted(name for name, path in paths.items() if not path.is_file())
        raise ValueError(f"AEGIS CBF source files are missing: {missing}")
    controller = paths["controller"].read_text(encoding="utf-8")
    geometry = paths["geometry"].read_text(encoding="utf-8")
    required_controller = (
        "a_u_v = 0.2 * a_v",
        "a_u_omega = 0.2 * a_omega",
        "u_z_nom = 10 * mu_row",
        "W = np.diag([1.0/25, 1.0/25, 1.0/25, 1.0/25, 1.0/25, 1.0/25, 1.0, 1.0, 1.0])",
        "a_u_v @ u[:3] + a_u_omega @ u[3:6] + a_uz @ u[6:] + 10 * h >= 0",
        "prob.solve(solver=cp.OSQP)",
        "action_input[:3] = 0.2 * R1 @ u_v",
        "action_input[3:6] = 0.2 * u_omega",
        "dz = (Id - np.outer(z_fixed, z_fixed)) @ u_z",
        "z_fixed = z_fixed + dz * dt",
        "z_fixed = z_fixed / np.linalg.norm(z_fixed)",
    )
    if any(statement not in controller for statement in required_controller):
        raise ValueError("pinned AEGIS controller statements changed")
    required_geometry = (
        "a_v = (eta_row @ R_i).ravel()",
        "a_omega = zeta_tilde @ R_i",
        "a_uz = (mu_row @ project_matrix(z)).ravel()",
        "return a_v, a_omega, a_uz, h, mu_row",
    )
    if any(statement not in geometry for statement in required_geometry):
        raise ValueError("pinned AEGIS geometry coefficient statements changed")
    return AegisCBFSourceIdentityV2(
        source_commit=source_commit,
        source_tree=source_tree,
        file_sha256=tuple(
            (name, _sha256_file(path)) for name, path in sorted(paths.items())
        ),
    )


@dataclass(frozen=True)
class AegisCBFConstraintV2:
    source_identity_digest: str
    state_snapshot_digest: str
    safety_bundle_digest: str
    observed_at_ns: int
    rotation_world_from_eef: tuple[float, ...]
    direction_z: tuple[float, float, float]
    a_v: tuple[float, float, float]
    a_omega: tuple[float, float, float]
    a_uz: tuple[float, float, float]
    h: float
    mu_row: tuple[float, float, float]
    provenance_digest: str
    constraint_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "source_identity_digest",
            "state_snapshot_digest",
            "safety_bundle_digest",
            "provenance_digest",
        ):
            _require_digest(name, getattr(self, name))
        if self.observed_at_ns < 0:
            raise ValueError("AEGIS CBF observation time must be non-negative")
        rotation = _finite_tuple("rotation_world_from_eef", self.rotation_world_from_eef, 9)
        direction = _finite_tuple("direction_z", self.direction_z, 3)
        a_v = _finite_tuple("a_v", self.a_v, 3)
        a_omega = _finite_tuple("a_omega", self.a_omega, 3)
        a_uz = _finite_tuple("a_uz", self.a_uz, 3)
        mu_row = _finite_tuple("mu_row", self.mu_row, 3)
        if type(self.h) not in (int, float) or not isfinite(float(self.h)):
            raise ValueError("AEGIS CBF h must be finite")
        rotation_issue = _rotation_issue(rotation)
        if rotation_issue is not None:
            raise ValueError(rotation_issue)
        if abs(_dot(direction, direction) - 1.0) > 1e-6:
            raise ValueError("AEGIS direction_z must be unit length")
        object.__setattr__(self, "rotation_world_from_eef", rotation)
        object.__setattr__(self, "direction_z", direction)
        object.__setattr__(self, "a_v", a_v)
        object.__setattr__(self, "a_omega", a_omega)
        object.__setattr__(self, "a_uz", a_uz)
        object.__setattr__(self, "mu_row", mu_row)
        object.__setattr__(self, "h", float(self.h))
        object.__setattr__(self, "constraint_digest", digest_payload(self.payload()))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": AEGIS_CBF_SCHEMA,
            "source_identity_digest": self.source_identity_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "safety_bundle_digest": self.safety_bundle_digest,
            "observed_at_ns": self.observed_at_ns,
            "rotation_world_from_eef": self.rotation_world_from_eef,
            "direction_z": self.direction_z,
            "a_v": self.a_v,
            "a_omega": self.a_omega,
            "a_uz": self.a_uz,
            "h": self.h,
            "mu_row": self.mu_row,
            "provenance_digest": self.provenance_digest,
        }


@dataclass(frozen=True)
class AegisCBFFilterResultV2:
    filter_digest: str
    constraint: AegisCBFConstraintV2
    nominal_command: SafeLiberoCommandV2
    adjusted_command: SafeLiberoCommandV2
    latent_nominal: tuple[float, ...]
    latent_solution: tuple[float, ...]
    next_direction_z: tuple[float, float, float]
    nominal_constraint_residual: float
    adjusted_constraint_residual: float
    projection_active: bool
    solver_status: str
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest("filter_digest", self.filter_digest)
        latent_nominal = _finite_tuple("latent_nominal", self.latent_nominal, 9)
        latent_solution = _finite_tuple("latent_solution", self.latent_solution, 9)
        next_direction = _finite_tuple("next_direction_z", self.next_direction_z, 3)
        if any(
            type(value) not in (int, float) or not isfinite(float(value))
            for value in (self.nominal_constraint_residual, self.adjusted_constraint_residual)
        ):
            raise ValueError("AEGIS CBF residual is non-finite")
        if self.solver_status not in {"optimal", "infeasible_degenerate"}:
            raise ValueError("unsupported AEGIS analytical solver status")
        object.__setattr__(self, "latent_nominal", latent_nominal)
        object.__setattr__(self, "latent_solution", latent_solution)
        object.__setattr__(self, "next_direction_z", next_direction)
        object.__setattr__(self, "result_digest", digest_payload(self.payload()))

    @property
    def adjusted_admissible(self) -> bool:
        return bool(
            self.solver_status == "optimal"
            and self.adjusted_constraint_residual >= -AEGIS_RESIDUAL_TOLERANCE
        )

    def payload(self) -> dict[str, Any]:
        return {
            "schema": AEGIS_CBF_SCHEMA,
            "filter_digest": self.filter_digest,
            "constraint_digest": self.constraint.constraint_digest,
            "nominal_command_digest": self.nominal_command.command_digest,
            "adjusted_command_digest": self.adjusted_command.command_digest,
            "latent_nominal": self.latent_nominal,
            "latent_solution": self.latent_solution,
            "next_direction_z": self.next_direction_z,
            "nominal_constraint_residual": self.nominal_constraint_residual,
            "adjusted_constraint_residual": self.adjusted_constraint_residual,
            "projection_active": self.projection_active,
            "solver_status": self.solver_status,
        }


@dataclass(frozen=True)
class SignedAegisCBFFilterEvidenceV2:
    result: AegisCBFFilterResultV2
    witness: SafeLiberoPostFilterWitnessV2
    filter_attestation: EvidenceAttestation
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.witness.schema != FILTER_WITNESS_SCHEMA:
            raise ValueError("signed AEGIS evidence contains an unsupported witness")
        object.__setattr__(
            self,
            "evidence_digest",
            digest_payload(
                {
                    "schema": AEGIS_CBF_SCHEMA,
                    "result_digest": self.result.result_digest,
                    "witness_digest": self.witness.witness_digest,
                    "attestation_digest": self.filter_attestation.attestation_digest,
                }
            ),
        )

    def attestation_payload(self) -> dict[str, Any]:
        return {
            "schema": AEGIS_CBF_SCHEMA,
            "result": self.result.payload(),
            "witness": self.witness.payload(),
        }


@dataclass(frozen=True)
class AegisCBFNoActionFilterV2:
    source_identity: AegisCBFSourceIdentityV2
    issuer: CTDAEvidenceIssuer
    max_constraint_age_ns: int
    attestation_valid_for_ns: int
    filter_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            self.issuer.producer_id != AEGIS_FILTER_ID
            or self.issuer.producer_version != AEGIS_FILTER_VERSION
        ):
            raise ValueError("AEGIS filter signer identity does not match the frozen producer")
        if self.max_constraint_age_ns <= 0 or self.attestation_valid_for_ns <= 0:
            raise ValueError("AEGIS filter evidence lifetimes must be positive")
        object.__setattr__(
            self,
            "filter_digest",
            digest_payload(
                {
                    "schema": AEGIS_CBF_SCHEMA,
                    "source_identity_digest": self.source_identity.source_identity_digest,
                    "filter_id": AEGIS_FILTER_ID,
                    "filter_version": AEGIS_FILTER_VERSION,
                    "alpha": AEGIS_ALPHA,
                    "action_scale": AEGIS_ACTION_SCALE,
                    "reference_scale": AEGIS_REFERENCE_SCALE,
                    "direction_scale": AEGIS_DIRECTION_SCALE,
                    "direction_dt": AEGIS_DIRECTION_DT,
                    "weight_diagonal": AEGIS_WEIGHT_DIAGONAL,
                    "max_constraint_age_ns": self.max_constraint_age_ns,
                    "solver": "closed_form_weighted_single_halfspace_projection",
                }
            ),
        )

    def produce(
        self,
        nominal_command: SafeLiberoCommandV2,
        constraint: AegisCBFConstraintV2,
        *,
        now_ns: int,
    ) -> SignedAegisCBFFilterEvidenceV2:
        issue = None
        if constraint.source_identity_digest != self.source_identity.source_identity_digest:
            issue = "AEGIS constraint source identity mismatch"
        elif not (0 <= now_ns - constraint.observed_at_ns <= self.max_constraint_age_ns):
            issue = "AEGIS constraint is stale or not yet valid"

        rotation = constraint.rotation_world_from_eef
        translation = tuple(nominal_command.values[:3])
        rotation_command = tuple(nominal_command.values[3:6])
        velocity_ref = _transpose_matvec(rotation, translation)
        latent_nominal = tuple(
            AEGIS_REFERENCE_SCALE * value for value in velocity_ref + rotation_command
        ) + tuple(AEGIS_DIRECTION_SCALE * value for value in constraint.mu_row)
        coefficients = (
            tuple(AEGIS_ACTION_SCALE * value for value in constraint.a_v)
            + tuple(AEGIS_ACTION_SCALE * value for value in constraint.a_omega)
            + constraint.a_uz
        )
        boundary_offset = AEGIS_ALPHA * constraint.h
        nominal_residual = _dot(coefficients, latent_nominal) + boundary_offset
        latent_solution = latent_nominal
        projection_active = False
        solver_status = "optimal"
        if issue is None and nominal_residual < 0.0:
            inverse_weighted = tuple(
                coefficient / weight
                for coefficient, weight in zip(coefficients, AEGIS_WEIGHT_DIAGONAL)
            )
            denominator = _dot(coefficients, inverse_weighted)
            if denominator <= AEGIS_PROJECTION_EPSILON:
                issue = "AEGIS CBF constraint is infeasible because its normal is degenerate"
                solver_status = "infeasible_degenerate"
            else:
                multiplier = -nominal_residual / denominator
                latent_solution = tuple(
                    nominal + multiplier * direction
                    for nominal, direction in zip(latent_nominal, inverse_weighted)
                )
                projection_active = True
        adjusted_residual = _dot(coefficients, latent_solution) + boundary_offset
        world_velocity = _matvec(rotation, tuple(latent_solution[:3]))
        adjusted_values = (
            tuple(AEGIS_ACTION_SCALE * value for value in world_velocity)
            + tuple(AEGIS_ACTION_SCALE * value for value in latent_solution[3:6])
            + (nominal_command.values[6],)
        )
        adjusted_command = SafeLiberoCommandV2(adjusted_values)
        z = constraint.direction_z
        u_z = tuple(latent_solution[6:9])
        projected_u_z = tuple(u_z[index] - z[index] * _dot(z, u_z) for index in range(3))
        try:
            next_direction = _normalize(
                tuple(
                    z[index] + AEGIS_DIRECTION_DT * projected_u_z[index]
                    for index in range(3)
                )  # type: ignore[arg-type]
            )
        except ValueError as exc:
            issue = issue or str(exc)
            next_direction = z
            solver_status = "infeasible_degenerate"
        result = AegisCBFFilterResultV2(
            filter_digest=self.filter_digest,
            constraint=constraint,
            nominal_command=nominal_command,
            adjusted_command=adjusted_command,
            latent_nominal=latent_nominal,
            latent_solution=latent_solution,
            next_direction_z=next_direction,
            nominal_constraint_residual=nominal_residual,
            adjusted_constraint_residual=adjusted_residual,
            projection_active=projection_active,
            solver_status=solver_status,
        )
        admissible = issue is None and result.adjusted_admissible
        witness = SafeLiberoPostFilterWitnessV2(
            filter_id=AEGIS_FILTER_ID,
            filter_version=AEGIS_FILTER_VERSION,
            filter_digest=self.filter_digest,
            state_snapshot_digest=constraint.state_snapshot_digest,
            safety_bundle_digest=constraint.safety_bundle_digest,
            nominal_command_digest=nominal_command.command_digest,
            adjusted_command_digest=adjusted_command.command_digest,
            constraint_ids=(
                "aegis-single-linear-cbf-halfspace",
                f"aegis-source:{self.source_identity.source_identity_digest}",
                f"aegis-result:{result.result_digest}",
            ),
            status=SnapshotStatus.OBSERVED if admissible else SnapshotStatus.UNKNOWN,
            adjusted_admissible=True if admissible else None,
            reason=(
                "aegis_cbf_projection" if projection_active else "aegis_cbf_nominal_admissible"
            ),
            observed_at_ns=constraint.observed_at_ns,
            unknown_reason=None if admissible else (issue or "AEGIS adjusted constraint is not admissible"),
        )
        payload = {
            "schema": AEGIS_CBF_SCHEMA,
            "result": result.payload(),
            "witness": witness.payload(),
        }
        attestation = self.issuer.issue(
            AEGIS_FILTER_EVIDENCE_TYPE,
            witness.witness_digest,
            payload=payload,
            issued_at_ns=now_ns,
            valid_until_ns=now_ns + self.attestation_valid_for_ns,
            assumptions=(
                "pinned-aegis-source-derived",
                "coefficient-provenance-external",
                "no-action-no-dispatch",
            ),
            producer_id=AEGIS_FILTER_ID,
            producer_version=AEGIS_FILTER_VERSION,
        )
        return SignedAegisCBFFilterEvidenceV2(result, witness, attestation)


@dataclass(frozen=True)
class SignedAegisFilterTransactionV2:
    filter_evidence: SignedAegisCBFFilterEvidenceV2
    filter_evidence_check: StaticCheckResult
    transaction: SafeLiberoNoDispatchTransactionV2
    dispatch_count: int = 0
    formal_rollout_authorized: bool = False
    transaction_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.dispatch_count != 0 or self.formal_rollout_authorized:
            raise ValueError("signed AEGIS transaction cannot dispatch or authorize rollout")
        object.__setattr__(
            self,
            "transaction_digest",
            digest_payload(
                {
                    "schema": AEGIS_CBF_SCHEMA,
                    "filter_evidence_digest": self.filter_evidence.evidence_digest,
                    "filter_evidence_verdict": self.filter_evidence_check.verdict.value,
                    "ctda_transaction_digest": self.transaction.transaction_digest,
                    "dispatch_count": self.dispatch_count,
                    "formal_rollout_authorized": self.formal_rollout_authorized,
                }
            ),
        )


@dataclass(frozen=True)
class SignedAegisPostFilterNoDispatchAdapterV2:
    adapter: SafeLiberoPostFilterNoDispatchAdapterV2
    filter_evidence_verifier: EvidenceVerifier

    def evaluate(
        self,
        *,
        certificate: SemanticCertificateV2,
        lease: ContractLeaseV2,
        context: ActiveContractContextV2,
        safety: SafetyEvidenceBundleV2,
        filter_evidence: SignedAegisCBFFilterEvidenceV2,
        proposal_index: int,
        now_ns: int,
    ) -> SignedAegisFilterTransactionV2:
        attestation = filter_evidence.filter_attestation
        expected_payload_digest = digest_payload(filter_evidence.attestation_payload())
        issues: list[str] = []
        if attestation.evidence_type != AEGIS_FILTER_EVIDENCE_TYPE:
            issues.append("AEGIS filter attestation type mismatch")
        if attestation.subject_digest != filter_evidence.witness.witness_digest:
            issues.append("AEGIS filter attestation is bound to another witness")
        if attestation.payload_digest != expected_payload_digest:
            issues.append("AEGIS filter attestation payload does not bind the full QP result")
        if (
            attestation.producer_id != AEGIS_FILTER_ID
            or attestation.producer_version != AEGIS_FILTER_VERSION
        ):
            issues.append("AEGIS filter attestation producer identity mismatch")
        if not attestation.is_fresh(now_ns):
            issues.append("AEGIS filter attestation is stale or not yet valid")
        if not self.filter_evidence_verifier.verify(attestation):
            issues.append("AEGIS filter attestation signature is not authenticated")
        if filter_evidence.result.constraint.state_snapshot_digest != lease.claim.activation_state.snapshot_digest:
            issues.append("AEGIS QP result is bound to another relevant state")
        if filter_evidence.result.constraint.safety_bundle_digest != safety.bundle_digest:
            issues.append("AEGIS QP result is bound to another safety bundle")
        if filter_evidence.result.nominal_command.command_digest != filter_evidence.witness.nominal_command_digest:
            issues.append("AEGIS QP nominal command binding mismatch")
        if filter_evidence.result.adjusted_command.command_digest != filter_evidence.witness.adjusted_command_digest:
            issues.append("AEGIS QP adjusted command binding mismatch")
        check = (
            StaticCheckResult.success(AEGIS_CBF_SCHEMA)
            if not issues
            else StaticCheckResult.refuted(*issues)
        )
        witness = filter_evidence.witness
        if not check.proven:
            witness = replace(
                witness,
                status=SnapshotStatus.UNKNOWN,
                adjusted_admissible=None,
                unknown_reason="; ".join(check.issues),
            )
        transaction = self.adapter.evaluate(
            certificate=certificate,
            lease=lease,
            context=context,
            safety=safety,
            nominal_command=filter_evidence.result.nominal_command,
            adjusted_command=filter_evidence.result.adjusted_command,
            filter_witness=witness,
            proposal_index=proposal_index,
            now_ns=now_ns,
        )
        return SignedAegisFilterTransactionV2(filter_evidence, check, transaction)
