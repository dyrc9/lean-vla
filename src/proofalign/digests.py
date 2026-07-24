"""Canonical digest helpers shared by the ProofAlign integrity mainline."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping


def _canonical(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _canonical(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("digest mappings require string keys")
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=_canonical_sort_key)
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("non-finite floats are not valid digest payloads")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported digest payload type: {type(value).__name__}")


def _canonical_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json(value: Any) -> str:
    """Serialize supported values in their deterministic digest representation."""

    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def digest_payload(value: Any) -> str:
    """Return the SHA-256 digest of a canonical JSON payload."""

    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_text(value: str) -> str:
    """Return the SHA-256 digest of an opaque UTF-8 string."""

    return sha256(value.encode("utf-8")).hexdigest()


__all__ = ["canonical_json", "digest_payload", "digest_text"]
