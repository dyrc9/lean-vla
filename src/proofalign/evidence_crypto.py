"""Versioned Ed25519 authentication for CTDA evidence attestations.

The existing ``EvidenceAttestation.proof_digest`` field is an opaque proof
carrier despite its historical name.  This module stores a domain-separated,
URL-safe Ed25519 signature in that field and verifies it against an exact
``(producer_id, producer_version)`` public-key binding.

This establishes cryptographic message authenticity.  It does not establish
secure key storage, process isolation, trusted sensing, revocation transport,
or hardware attestation.
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from proofalign.ctda import (
    EvidenceAttestation,
    EvidenceVerifier,
    canonical_json,
    digest_payload,
)


ED25519_PROOF_VERSION = "proofalign-ed25519-v1"
ED25519_PROOF_PREFIX = f"{ED25519_PROOF_VERSION}:"
ED25519_PUBLIC_KEY_BYTES = 32
ED25519_PRIVATE_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _public_bytes(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _proof_encode(signature: bytes) -> str:
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise ValueError("Ed25519 signature has an unexpected length")
    return ED25519_PROOF_PREFIX + urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def _proof_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value.startswith(ED25519_PROOF_PREFIX):
        raise ValueError("evidence proof is not proofalign-ed25519-v1")
    encoded = value[len(ED25519_PROOF_PREFIX) :]
    if re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None:
        raise ValueError("evidence Ed25519 signature encoding is invalid")
    padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
    signature = urlsafe_b64decode(padded.encode("ascii"))
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise ValueError("evidence Ed25519 signature length is invalid")
    if urlsafe_b64encode(signature).decode("ascii").rstrip("=") != encoded:
        raise ValueError("evidence Ed25519 signature encoding is not canonical")
    return signature


def attestation_signing_payload(
    *,
    evidence_type: str,
    subject_digest: str,
    producer_id: str,
    producer_version: str,
    issued_at_ns: int,
    valid_until_ns: int,
    payload_digest: str,
    assumptions: Sequence[str],
) -> dict[str, Any]:
    """Return the exact domain-separated payload signed by an evidence producer."""

    return {
        "domain": ED25519_PROOF_VERSION,
        "evidence_type": evidence_type,
        "subject_digest": subject_digest,
        "producer_id": producer_id,
        "producer_version": producer_version,
        "issued_at_ns": issued_at_ns,
        "valid_until_ns": valid_until_ns,
        "payload_digest": payload_digest,
        "assumptions": tuple(sorted(set(assumptions))),
    }


def attestation_signing_bytes(attestation: EvidenceAttestation) -> bytes:
    return canonical_json(
        attestation_signing_payload(
            evidence_type=attestation.evidence_type,
            subject_digest=attestation.subject_digest,
            producer_id=attestation.producer_id,
            producer_version=attestation.producer_version,
            issued_at_ns=attestation.issued_at_ns,
            valid_until_ns=attestation.valid_until_ns,
            payload_digest=attestation.payload_digest,
            assumptions=attestation.assumptions,
        )
    ).encode("utf-8")


@dataclass(frozen=True)
class Ed25519PublicKeyBinding:
    producer_id: str
    producer_version: str
    public_key_bytes: bytes
    key_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text("producer_id", self.producer_id)
        _require_text("producer_version", self.producer_version)
        raw = bytes(self.public_key_bytes)
        if len(raw) != ED25519_PUBLIC_KEY_BYTES:
            raise ValueError("Ed25519 public key must contain exactly 32 bytes")
        Ed25519PublicKey.from_public_bytes(raw)
        object.__setattr__(self, "public_key_bytes", raw)
        object.__setattr__(self, "key_fingerprint", sha256(raw).hexdigest())

    @property
    def identity(self) -> tuple[str, str]:
        return (self.producer_id, self.producer_version)


class Ed25519EvidenceVerifier(EvidenceVerifier):
    """Verify exact producer/version bindings with optional local revocation."""

    def __init__(
        self,
        bindings: Iterable[Ed25519PublicKeyBinding],
        *,
        revoked_key_fingerprints: Iterable[str] = (),
    ) -> None:
        self._bindings: dict[tuple[str, str], Ed25519PublicKeyBinding] = {}
        for binding in bindings:
            if binding.identity in self._bindings:
                raise ValueError(f"duplicate Ed25519 producer binding: {binding.identity!r}")
            self._bindings[binding.identity] = binding
        if not self._bindings:
            raise ValueError("Ed25519 verifier requires at least one public-key binding")
        self._revoked = frozenset(revoked_key_fingerprints)

    @classmethod
    def from_mapping(
        cls,
        bindings: Mapping[tuple[str, str], bytes],
        *,
        revoked_key_fingerprints: Iterable[str] = (),
    ) -> "Ed25519EvidenceVerifier":
        return cls(
            (
                Ed25519PublicKeyBinding(identity[0], identity[1], public_key)
                for identity, public_key in bindings.items()
            ),
            revoked_key_fingerprints=revoked_key_fingerprints,
        )

    @property
    def key_fingerprints(self) -> tuple[str, ...]:
        return tuple(sorted(binding.key_fingerprint for binding in self._bindings.values()))

    def verify(self, attestation: EvidenceAttestation) -> bool:
        if not isinstance(attestation, EvidenceAttestation) or not attestation.verify_integrity():
            return False
        binding = self._bindings.get((attestation.producer_id, attestation.producer_version))
        if binding is None or binding.key_fingerprint in self._revoked:
            return False
        try:
            signature = _proof_decode(attestation.proof_digest)
            public_key = Ed25519PublicKey.from_public_bytes(binding.public_key_bytes)
            public_key.verify(signature, attestation_signing_bytes(attestation))
        except (InvalidSignature, TypeError, ValueError):
            return False
        return True


@dataclass(frozen=True)
class Ed25519EvidenceIssuer:
    """In-process signer for a single exact producer/version identity.

    Passing this object conveys signing authority.  Applications are expected
    to construct it from a protected key provider; this class intentionally
    does not write, discover, or generate key files.
    """

    producer_id: str
    producer_version: str
    _private_key: Ed25519PrivateKey = field(repr=False)
    public_key_binding: Ed25519PublicKeyBinding = field(init=False)
    _verifier: Ed25519EvidenceVerifier = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _require_text("producer_id", self.producer_id)
        _require_text("producer_version", self.producer_version)
        if not isinstance(self._private_key, Ed25519PrivateKey):
            raise TypeError("Ed25519 issuer requires an Ed25519 private key")
        binding = Ed25519PublicKeyBinding(
            self.producer_id,
            self.producer_version,
            _public_bytes(self._private_key.public_key()),
        )
        object.__setattr__(self, "public_key_binding", binding)
        object.__setattr__(self, "_verifier", Ed25519EvidenceVerifier((binding,)))

    @classmethod
    def generate_for_testing(
        cls, producer_id: str, producer_version: str
    ) -> "Ed25519EvidenceIssuer":
        """Generate an ephemeral key; never use this helper for persisted authority."""

        return cls(producer_id, producer_version, Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(
        cls,
        producer_id: str,
        producer_version: str,
        private_key_bytes: bytes,
    ) -> "Ed25519EvidenceIssuer":
        raw = bytes(private_key_bytes)
        if len(raw) != ED25519_PRIVATE_KEY_BYTES:
            raise ValueError("Ed25519 private key must contain exactly 32 bytes")
        return cls(
            producer_id,
            producer_version,
            Ed25519PrivateKey.from_private_bytes(raw),
        )

    @property
    def verifier(self) -> Ed25519EvidenceVerifier:
        return self._verifier

    @property
    def key_fingerprint(self) -> str:
        return self.public_key_binding.key_fingerprint

    def issue(
        self,
        evidence_type: str,
        subject_digest: str,
        *,
        payload: Any,
        issued_at_ns: int,
        valid_until_ns: int,
        assumptions: Sequence[str] = (),
        producer_id: str | None = None,
        producer_version: str | None = None,
    ) -> EvidenceAttestation:
        actual_producer = producer_id or self.producer_id
        actual_version = producer_version or self.producer_version
        if actual_producer != self.producer_id or actual_version != self.producer_version:
            raise ValueError("Ed25519 issuer cannot impersonate another producer identity")
        normalized_assumptions = tuple(sorted(set(assumptions)))
        payload_digest = digest_payload(payload)
        signing_payload = attestation_signing_payload(
            evidence_type=evidence_type,
            subject_digest=subject_digest,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            payload_digest=payload_digest,
            assumptions=normalized_assumptions,
        )
        signature = self._private_key.sign(canonical_json(signing_payload).encode("utf-8"))
        return EvidenceAttestation(
            evidence_type=evidence_type,
            subject_digest=subject_digest,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            payload_digest=payload_digest,
            proof_digest=_proof_encode(signature),
            assumptions=normalized_assumptions,
        )
