"""Outcome-informed v11 joint-limit containment observer.

The observer deliberately makes no pre-dispatch prediction claim. It consumes
the independent post-step SABER / robosuite signal and asks an L2-enabled
runner to halt before another action from the active block is dispatched.
Missing or malformed evidence is fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


JOINT_LIMIT_CONTAINMENT_VERSION = "1"
JOINT_LIMIT_CONTAINMENT_SCHEMA = (
    "proofalign.joint-limit-containment.v11"
)
INDEPENDENT_SIGNAL_SCHEMA = (
    "proofalign.saber-independent-constraint-signals.v1"
)
JOINT_LIMIT_VIOLATION_ATOM = "joint_limit_violation"
JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM = "joint_limit_observer_unknown"


def observed_joint_limit_atoms(
    constraint_signals: dict[str, Any] | None,
) -> tuple[str, ...]:
    """Return the physical violation atom that forces L2 containment."""

    if not isinstance(constraint_signals, Mapping):
        return (JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,)
    if (
        constraint_signals.get("schema")
        != INDEPENDENT_SIGNAL_SCHEMA
    ):
        return (JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,)
    value = constraint_signals.get("joint_limit_violation")
    if type(value) is not bool:
        return (JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,)
    source_digest = constraint_signals.get(
        "official_saber_source_sha256"
    )
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in source_digest
        )
    ):
        return (JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM,)
    return (JOINT_LIMIT_VIOLATION_ATOM,) if value else ()


__all__ = [
    "INDEPENDENT_SIGNAL_SCHEMA",
    "JOINT_LIMIT_CONTAINMENT_SCHEMA",
    "JOINT_LIMIT_CONTAINMENT_VERSION",
    "JOINT_LIMIT_OBSERVER_UNKNOWN_ATOM",
    "JOINT_LIMIT_VIOLATION_ATOM",
    "observed_joint_limit_atoms",
]
