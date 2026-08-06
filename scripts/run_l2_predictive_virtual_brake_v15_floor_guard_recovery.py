#!/usr/bin/env python3
"""Floor-edge fallback for the v14 multi-joint simulator brake.

The frozen v14 brake evaluates guard margins 0.16, 0.18, 0.20, and
0.22 rad.  Outcome-disclosed development and held-out utility traces show a
specific liveness gap: all ten task deadlocks begin with the current minimum
margin in (0.15, 0.16), so none of those guards can be instantiated without
placing the current configuration outside the temporary joint range.

This outcome-informed v15 development successor preserves the v14 candidates
and their order.  It appends one 0.150001-rad floor-edge candidate only as a
fallback.  The source policy action remains exact, the candidate is shadowed
from the same warm-start-complete snapshot, and execution remains authorized
only when the predicted global fourteen-side minimum is at least 0.15 rad.
It is a simulator backup guard, not an actuator or physical recovery claim.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_fresh2 as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_"
    "multijoint_floor_guard_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15."
    "multijoint-floor-guard-recovery.step"
)
JOINT_COUNT = predecessor.JOINT_COUNT
JOINT_SIDES = predecessor.JOINT_SIDES
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
GUARD_SOLREF = predecessor.GUARD_SOLREF
GUARD_SOLIMP = predecessor.GUARD_SOLIMP
RECOVERY_GUARD_MARGIN_RAD = SAFE_MARGIN_FLOOR_RAD + 1e-6
RECOVERY_MARGIN_EPSILON_RAD = 1e-6


class FloorGuardRecoveryError(RuntimeError):
    """Raised when the fallback guard loses its frozen identity."""


@dataclass(frozen=True)
class FloorGuardRecoveryConfig:
    """v14 candidates followed by exactly one floor-edge fallback."""

    joint_indices: tuple[int, ...] = tuple(range(JOINT_COUNT))
    trigger_margin_rad: float = TRIGGER_MARGIN_RAD
    safe_margin_floor_rad: float = SAFE_MARGIN_FLOOR_RAD
    guard_margins_rad: tuple[float, ...] = (
        *BRAKE_MARGINS_RAD,
        RECOVERY_GUARD_MARGIN_RAD,
    )
    guard_solref: tuple[float, float] = GUARD_SOLREF
    guard_solimp: tuple[float, float, float, float, float] = GUARD_SOLIMP

    def __post_init__(self) -> None:
        if (
            self.joint_indices != tuple(range(JOINT_COUNT))
            or self.trigger_margin_rad != TRIGGER_MARGIN_RAD
            or self.safe_margin_floor_rad != SAFE_MARGIN_FLOOR_RAD
            or self.guard_margins_rad
            != (*BRAKE_MARGINS_RAD, RECOVERY_GUARD_MARGIN_RAD)
            or self.guard_solref != GUARD_SOLREF
            or self.guard_solimp != GUARD_SOLIMP
            or not np.isfinite(RECOVERY_GUARD_MARGIN_RAD)
            or RECOVERY_GUARD_MARGIN_RAD
            <= SAFE_MARGIN_FLOOR_RAD
            or RECOVERY_GUARD_MARGIN_RAD
            >= min(BRAKE_MARGINS_RAD)
        ):
            raise ValueError("invalid floor-edge recovery configuration")


def _enrich_recovery_audit(audit: dict[str, Any]) -> None:
    candidates = audit.get("candidates")
    if not isinstance(candidates, list):
        raise FloorGuardRecoveryError("v15 audit lacks candidate rows")
    recovery_rows = [
        row
        for row in candidates
        if isinstance(row, Mapping)
        and float(row["guard_margin_rad"])
        == RECOVERY_GUARD_MARGIN_RAD
    ]
    attempted = bool(recovery_rows)
    if bool(audit.get("triggered")) != attempted:
        raise FloorGuardRecoveryError(
            "each triggered v15 screen must evaluate one recovery fallback"
        )
    if len(recovery_rows) > 1:
        raise FloorGuardRecoveryError(
            "v15 screen contains duplicate recovery candidates"
        )
    baseline_eligible_count = sum(
        int(row.get("eligible") is True)
        for row in candidates
        if isinstance(row, Mapping)
        and float(row["guard_margin_rad"])
        != RECOVERY_GUARD_MARGIN_RAD
    )
    recovery_eligible = bool(
        recovery_rows and recovery_rows[0].get("eligible") is True
    )
    selected_margin = audit.get("selected_guard_margin_rad")
    recovery_selected = bool(
        selected_margin is not None
        and float(selected_margin) == RECOVERY_GUARD_MARGIN_RAD
    )
    baseline_would_deadlock = bool(
        audit.get("triggered") and baseline_eligible_count == 0
    )
    prevented_deadlock = bool(
        baseline_would_deadlock
        and recovery_selected
        and audit.get("deadlock") is False
    )
    audit.update(
        {
            "schema": BRAKE_AUDIT_SCHEMA,
            "floor_guard_recovery_active": True,
            "floor_guard_recovery_margin_rad": (
                RECOVERY_GUARD_MARGIN_RAD
            ),
            "floor_guard_recovery_attempted": attempted,
            "floor_guard_recovery_eligible": recovery_eligible,
            "floor_guard_recovery_selected": recovery_selected,
            "v14_baseline_eligible_candidate_count": (
                baseline_eligible_count
            ),
            "v14_baseline_would_deadlock": baseline_would_deadlock,
            "floor_guard_recovery_prevented_deadlock": (
                prevented_deadlock
            ),
        }
    )


class MultiJointFloorGuardRecoveryEnvironment(
    predecessor.MultiJointPredictiveVirtualBrakeFresh2Environment
):
    """Append one shadow-validated floor-edge fallback candidate."""

    def __init__(
        self,
        env: Any,
        *,
        wait_steps: int,
        enabled: bool,
        config: Any,
    ) -> None:
        super().__init__(
            env,
            wait_steps=wait_steps,
            enabled=enabled,
            config=config,
        )
        self._config = FloorGuardRecoveryConfig()

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        transition = super().step(action)
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise FloorGuardRecoveryError(
                "v15 environment produced a non-object audit"
            )
        if audit.get("enabled") is True:
            _enrich_recovery_audit(audit)
        else:
            audit.update(
                {
                    "schema": BRAKE_AUDIT_SCHEMA,
                    "floor_guard_recovery_active": False,
                    "floor_guard_recovery_margin_rad": None,
                    "floor_guard_recovery_attempted": False,
                    "floor_guard_recovery_eligible": False,
                    "floor_guard_recovery_selected": False,
                    "v14_baseline_eligible_candidate_count": 0,
                    "v14_baseline_would_deadlock": False,
                    "floor_guard_recovery_prevented_deadlock": False,
                }
            )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = (
        predecessor.MultiJointPredictiveVirtualBrakeFresh2Environment
    )
    predecessor.MultiJointPredictiveVirtualBrakeFresh2Environment = (
        MultiJointFloorGuardRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointPredictiveVirtualBrakeFresh2Environment = (
            original
        )


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15 floor-edge fallback episode."""

    with _patched_predecessor_environment():
        payload = predecessor.run_episode(**kwargs)
    metadata = dict(payload["metadata"])
    l2_enabled = bool(metadata["l2_execution_integrity"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_schema": (
                BRAKE_AUDIT_SCHEMA if l2_enabled else None
            ),
            "floor_guard_recovery_active": l2_enabled,
            "floor_guard_recovery_margin_rad": (
                RECOVERY_GUARD_MARGIN_RAD if l2_enabled else None
            ),
            "floor_guard_recovery_margin_epsilon_rad": (
                RECOVERY_MARGIN_EPSILON_RAD if l2_enabled else None
            ),
            "floor_guard_recovery_source_action_substitution": False,
            "floor_guard_recovery_outcome_informed_successor": True,
            "floor_guard_recovery_physical_authority_claim": False,
        }
    )
    payload["metadata"] = metadata
    v1._persist_annotated_episode(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(
        {
            "runner_variant": RUNNER_VARIANT,
            "execution_authorized": False,
            "note": (
                "Import through a separately versioned outcome-informed "
                "v15 development protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
