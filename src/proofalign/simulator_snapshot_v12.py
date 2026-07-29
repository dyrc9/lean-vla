"""Typed simulator snapshot diagnostics for v12.3.

MuJoCo ``MjSimState`` contains time plus every model qpos/qvel.  Restoring it
and calling ``forward`` may canonically renormalize non-arm object
quaternions, so full-array bitwise equality is not the same estimand as exact
restoration of the trusted arm execution state.  This module reports both:

* full simulator bitwise identity and maximum absolute numerical error;
* exact trusted arm qpos/qvel identity, which is the recovery precondition.

The distinction is versioned and explicit; it does not rewrite the frozen
v12.2 nonpass that conflated shadow restoration with harness cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from proofalign.digests import digest_payload
from proofalign.recoverable_alignment_v12 import (
    RecoverableAlignmentV12Error,
)


SIMULATOR_SNAPSHOT_SCHEMA = "proofalign.simulator-snapshot.v12.3"


def _indexes(
    values: Sequence[int],
    *,
    name: str,
) -> tuple[int, ...]:
    frozen = tuple(int(value) for value in values)
    if not frozen or any(value < 0 for value in frozen):
        raise RecoverableAlignmentV12Error(
            f"{name} must contain non-negative indexes"
        )
    return frozen


@dataclass(frozen=True)
class SimulatorSnapshot:
    state: Any = field(repr=False, compare=False)
    flat_state: tuple[float, ...]
    arm_qpos_indexes: tuple[int, ...]
    arm_qvel_indexes: tuple[int, ...]
    arm_qpos: tuple[float, ...]
    arm_qvel: tuple[float, ...]
    source_id: str
    schema: str = SIMULATOR_SNAPSHOT_SCHEMA
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        flat = tuple(float(value) for value in self.flat_state)
        qpos_indexes = _indexes(
            self.arm_qpos_indexes,
            name="arm_qpos_indexes",
        )
        qvel_indexes = _indexes(
            self.arm_qvel_indexes,
            name="arm_qvel_indexes",
        )
        qpos = tuple(float(value) for value in self.arm_qpos)
        qvel = tuple(float(value) for value in self.arm_qvel)
        if (
            not flat
            or len(qpos_indexes) != len(qpos)
            or len(qvel_indexes) != len(qvel)
            or len(qpos) != len(qvel)
        ):
            raise RecoverableAlignmentV12Error(
                "simulator snapshot arm shape is inconsistent"
            )
        if not isinstance(self.source_id, str) or not self.source_id:
            raise RecoverableAlignmentV12Error(
                "simulator snapshot source id must be non-empty"
            )
        object.__setattr__(self, "flat_state", flat)
        object.__setattr__(self, "arm_qpos_indexes", qpos_indexes)
        object.__setattr__(self, "arm_qvel_indexes", qvel_indexes)
        object.__setattr__(self, "arm_qpos", qpos)
        object.__setattr__(self, "arm_qvel", qvel)
        object.__setattr__(
            self,
            "snapshot_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "flat_state": flat,
                    "arm_qpos_indexes": qpos_indexes,
                    "arm_qvel_indexes": qvel_indexes,
                    "arm_qpos": qpos,
                    "arm_qvel": qvel,
                    "source_id": self.source_id,
                }
            ),
        )


@dataclass(frozen=True)
class SnapshotRestoreAssessment:
    snapshot_digest: str
    full_state_bitwise_identity: bool
    trusted_arm_bitwise_identity: bool
    full_state_max_abs_error: float
    full_state_differing_value_count: int
    observed_arm_qpos: tuple[float, ...]
    observed_arm_qvel: tuple[float, ...]
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_digest",
            digest_payload(
                {
                    "schema": SIMULATOR_SNAPSHOT_SCHEMA + ".assessment",
                    "snapshot_digest": self.snapshot_digest,
                    "full_state_bitwise_identity": (
                        self.full_state_bitwise_identity
                    ),
                    "trusted_arm_bitwise_identity": (
                        self.trusted_arm_bitwise_identity
                    ),
                    "full_state_max_abs_error": (
                        self.full_state_max_abs_error
                    ),
                    "full_state_differing_value_count": (
                        self.full_state_differing_value_count
                    ),
                    "observed_arm_qpos": self.observed_arm_qpos,
                    "observed_arm_qvel": self.observed_arm_qvel,
                }
            ),
        )


def capture_simulator_snapshot(
    env: Any,
    *,
    arm_qpos_indexes: Sequence[int],
    arm_qvel_indexes: Sequence[int],
    source_id: str,
) -> SimulatorSnapshot:
    qpos_indexes = _indexes(
        arm_qpos_indexes, name="arm_qpos_indexes"
    )
    qvel_indexes = _indexes(
        arm_qvel_indexes, name="arm_qvel_indexes"
    )
    state = env.sim.get_state()
    return SimulatorSnapshot(
        state=state,
        flat_state=tuple(float(value) for value in state.flatten()),
        arm_qpos_indexes=qpos_indexes,
        arm_qvel_indexes=qvel_indexes,
        arm_qpos=tuple(
            float(value)
            for value in env.sim.data.qpos[list(qpos_indexes)]
        ),
        arm_qvel=tuple(
            float(value)
            for value in env.sim.data.qvel[list(qvel_indexes)]
        ),
        source_id=source_id,
    )


def restore_simulator_snapshot(
    env: Any,
    robot: Any,
    snapshot: SimulatorSnapshot,
) -> SnapshotRestoreAssessment:
    env.sim.set_state(snapshot.state)
    env.sim.forward()
    robot.controller.update(force=True)
    robot.controller.reset_goal()
    observed_state = np.asarray(
        env.sim.get_state().flatten(), dtype=np.float64
    )
    expected_state = np.asarray(
        snapshot.flat_state, dtype=np.float64
    )
    if observed_state.shape != expected_state.shape:
        raise RecoverableAlignmentV12Error(
            "restored simulator state shape differs"
        )
    qpos = tuple(
        float(value)
        for value in env.sim.data.qpos[
            list(snapshot.arm_qpos_indexes)
        ]
    )
    qvel = tuple(
        float(value)
        for value in env.sim.data.qvel[
            list(snapshot.arm_qvel_indexes)
        ]
    )
    differences = np.abs(observed_state - expected_state)
    return SnapshotRestoreAssessment(
        snapshot_digest=snapshot.snapshot_digest,
        full_state_bitwise_identity=bool(
            np.array_equal(observed_state, expected_state)
        ),
        trusted_arm_bitwise_identity=(
            qpos == snapshot.arm_qpos and qvel == snapshot.arm_qvel
        ),
        full_state_max_abs_error=float(np.max(differences)),
        full_state_differing_value_count=int(
            np.count_nonzero(observed_state != expected_state)
        ),
        observed_arm_qpos=qpos,
        observed_arm_qvel=qvel,
    )


__all__ = [
    "SIMULATOR_SNAPSHOT_SCHEMA",
    "SimulatorSnapshot",
    "SnapshotRestoreAssessment",
    "capture_simulator_snapshot",
    "restore_simulator_snapshot",
]
