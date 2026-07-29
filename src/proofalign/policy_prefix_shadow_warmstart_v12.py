"""Warm-start-complete successor for controller-aware policy shadow snapshots.

The v12.4a fixed-prefix qualification restored ``MjSimState``, controller
caches, simulator inputs, and environment clocks. Twenty-nine of thirty
cases replayed within 0.02 rad; the sole divergence was a joint-1 upper-limit
injection with dense contact dynamics. MuJoCo's iterative constraint solver
also consumes ``qacc_warmstart``, which is not part of ``MjSimState``.

This version wraps, rather than mutates, the frozen v12.4a snapshot and binds
that solver warm-start vector explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from proofalign.digests import digest_payload
from proofalign.policy_prefix_shadow_v12 import (
    PolicyShadowRestoreAssessment,
    PolicyShadowRuntimeSnapshot,
    capture_policy_shadow_snapshot,
    restore_policy_shadow_snapshot,
)
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
)


WARMSTART_POLICY_SHADOW_SCHEMA = (
    "proofalign.policy-prefix-shadow-warmstart.v12.4b"
)


@dataclass(frozen=True)
class WarmstartPolicyShadowSnapshot:
    base: PolicyShadowRuntimeSnapshot = field(
        repr=False, compare=False
    )
    qacc_warmstart: tuple[float, ...]
    source_id: str
    schema: str = WARMSTART_POLICY_SHADOW_SCHEMA + ".snapshot"
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.qacc_warmstart)
        if (
            not values
            or not np.isfinite(np.asarray(values)).all()
            or not self.source_id
        ):
            raise RecoverableAlignmentV12Error(
                "warm-start snapshot must be finite and identified"
            )
        object.__setattr__(self, "qacc_warmstart", values)
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "base_snapshot_digest": self.base.snapshot_digest,
                    "qacc_warmstart": values,
                    "source_id": self.source_id,
                }
            ),
        )


@dataclass(frozen=True)
class WarmstartPolicyShadowRestoreAssessment:
    base: PolicyShadowRestoreAssessment = field(
        repr=False, compare=False
    )
    snapshot_digest: str
    qacc_warmstart_identity: bool
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": WARMSTART_POLICY_SHADOW_SCHEMA
                    + ".restore-assessment",
                    "base_assessment_digest": (
                        self.base.assessment_digest
                    ),
                    "snapshot_digest": self.snapshot_digest,
                    "qacc_warmstart_identity": (
                        self.qacc_warmstart_identity
                    ),
                }
            ),
        )

    @property
    def full_simulator_state_bitwise_identity(self) -> bool:
        return self.base.full_simulator_state_bitwise_identity

    @property
    def trusted_arm_bitwise_identity(self) -> bool:
        return self.base.trusted_arm_bitwise_identity

    @property
    def controller_state_identity(self) -> bool:
        return self.base.controller_state_identity

    @property
    def simulator_input_identity(self) -> bool:
        return self.base.simulator_input_identity

    @property
    def environment_clock_identity(self) -> bool:
        return self.base.environment_clock_identity

    @property
    def full_simulator_state_max_abs_error(self) -> float:
        return self.base.full_simulator_state_max_abs_error

    @property
    def full_simulator_state_differing_value_count(self) -> int:
        return self.base.full_simulator_state_differing_value_count


def capture_warmstart_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    *,
    source_id: str,
) -> WarmstartPolicyShadowSnapshot:
    warmstart = np.asarray(
        env.sim.data.qacc_warmstart, dtype=np.float64
    )
    if warmstart.ndim != 1 or not np.isfinite(warmstart).all():
        raise RecoverableAlignmentV12Error(
            "MuJoCo qacc_warmstart is unavailable or malformed"
        )
    return WarmstartPolicyShadowSnapshot(
        base=capture_policy_shadow_snapshot(
            env, robot, source_id=source_id + ":base"
        ),
        qacc_warmstart=tuple(float(value) for value in warmstart),
        source_id=source_id,
    )


def restore_warmstart_policy_shadow_snapshot(
    env: Any,
    robot: Any,
    snapshot: WarmstartPolicyShadowSnapshot,
) -> WarmstartPolicyShadowRestoreAssessment:
    base = restore_policy_shadow_snapshot(env, robot, snapshot.base)
    target = np.asarray(snapshot.qacc_warmstart, dtype=np.float64)
    observed = np.asarray(env.sim.data.qacc_warmstart)
    if observed.shape != target.shape:
        raise RecoverableAlignmentV12Error(
            "MuJoCo qacc_warmstart shape differs on restore"
        )
    env.sim.data.qacc_warmstart[:] = target
    restored = np.asarray(
        env.sim.data.qacc_warmstart, dtype=np.float64
    )
    return WarmstartPolicyShadowRestoreAssessment(
        base=base,
        snapshot_digest=snapshot.snapshot_digest,
        qacc_warmstart_identity=bool(
            np.array_equal(restored, target)
        ),
    )


__all__ = [
    "WARMSTART_POLICY_SHADOW_SCHEMA",
    "WarmstartPolicyShadowRestoreAssessment",
    "WarmstartPolicyShadowSnapshot",
    "capture_warmstart_policy_shadow_snapshot",
    "restore_warmstart_policy_shadow_snapshot",
]
