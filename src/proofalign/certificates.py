from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CertificateKind(str, Enum):
    OBJECT_IDENTITY = "object_identity"
    AFFORDANCE = "affordance"
    COLLISION_FREE = "collision_free"
    HUMAN_CLEARANCE = "human_clearance"
    OBSTACLE_CLEARANCE = "obstacle_clearance"
    REGION_OCCUPANCY = "region_occupancy"
    STATE_TRANSITION = "state_transition"
    FRAME_CONDITION = "frame_condition"


class CertificateStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    EXPIRED = "expired"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Certificate:
    """External evidence submitted to the trusted symbolic checker.

    The certificate producer is not trusted. Lean/Python checks only the
    discrete structure and thresholds represented here; continuous geometry,
    perception, and dynamics remain outside the trusted core.
    """

    kind: CertificateKind
    status: CertificateStatus = CertificateStatus.VALID
    subject: str | None = None
    target: str | None = None
    value: float | str | bool | None = None
    threshold: float | None = None
    confidence: float = 1.0
    source: str = "unknown"
    step: int | None = None
    valid_until_step: int | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Certificate":
        return cls(
            kind=CertificateKind(str(data["kind"])),
            status=CertificateStatus(str(data.get("status", CertificateStatus.VALID.value))),
            subject=data.get("subject"),
            target=data.get("target"),
            value=data.get("value"),
            threshold=float(data["threshold"]) if data.get("threshold") is not None else None,
            confidence=float(data.get("confidence", 1.0)),
            source=str(data.get("source", "unknown")),
            step=int(data["step"]) if data.get("step") is not None else None,
            valid_until_step=int(data["valid_until_step"]) if data.get("valid_until_step") is not None else None,
            message=str(data.get("message", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "status": self.status.value,
            "subject": self.subject,
            "target": self.target,
            "value": self.value,
            "threshold": self.threshold,
            "confidence": self.confidence,
            "source": self.source,
            "step": self.step,
            "valid_until_step": self.valid_until_step,
            "message": self.message,
            "metadata": self.metadata,
        }

    def validity_errors(self, min_confidence: float, now_step: int | None = None) -> list[str]:
        errors: list[str] = []
        if self.status != CertificateStatus.VALID:
            errors.append(f"{self.kind.value} certificate is {self.status.value}")
        if self.confidence < min_confidence:
            errors.append(
                f"{self.kind.value} certificate confidence {self.confidence:.3f} below {min_confidence:.3f}"
            )
        if now_step is not None and self.valid_until_step is not None and self.valid_until_step < now_step:
            errors.append(f"{self.kind.value} certificate expired at step {self.valid_until_step}")
        if isinstance(self.value, (int, float)) and self.threshold is not None and float(self.value) < self.threshold:
            errors.append(
                f"{self.kind.value} certificate value {float(self.value):.3f} below threshold {self.threshold:.3f}"
            )
        return errors


@dataclass
class CertificateBundle:
    certificates: list[Certificate] = field(default_factory=list)

    @classmethod
    def from_dicts(cls, items: list[dict[str, Any]] | None) -> "CertificateBundle":
        return cls([Certificate.from_dict(item) for item in items or []])

    def by_kind(self, kind: CertificateKind) -> list[Certificate]:
        return [cert for cert in self.certificates if cert.kind == kind]

    def has_valid(
        self,
        kind: CertificateKind,
        min_confidence: float = 0.0,
        subject: str | None = None,
        target: str | None = None,
        now_step: int | None = None,
    ) -> bool:
        return not self.errors_for(kind, min_confidence, subject, target, now_step, missing_is_error=True)

    def errors_for(
        self,
        kind: CertificateKind,
        min_confidence: float,
        subject: str | None = None,
        target: str | None = None,
        now_step: int | None = None,
        missing_is_error: bool = False,
    ) -> list[str]:
        candidates = [
            cert
            for cert in self.certificates
            if cert.kind == kind
            and (subject is None or cert.subject == subject)
            and (target is None or cert.target == target)
        ]
        if not candidates:
            return [f"missing {kind.value} certificate"] if missing_is_error else []
        errors: list[str] = []
        for cert in candidates:
            errors.extend(cert.validity_errors(min_confidence, now_step))
        return errors

    def to_dicts(self) -> list[dict[str, Any]]:
        return [cert.to_dict() for cert in self.certificates]


def certificates_from_action_params(params: dict[str, Any], layer: str) -> CertificateBundle:
    key = "pre_certificates" if layer == "intent" else "post_certificates"
    return CertificateBundle.from_dicts(params.get(key))
