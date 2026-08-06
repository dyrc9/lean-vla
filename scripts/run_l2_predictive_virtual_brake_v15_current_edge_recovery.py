#!/usr/bin/env python3
"""Current-edge successor for residual v15 floor-guard deadlocks."""

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
from scripts import run_l2_predictive_virtual_brake_v15_floor_guard_recovery as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_1_"
    "multijoint_current_edge_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.1."
    "multijoint-current-edge-recovery.step"
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
RECOVERY_GUARD_MARGIN_RAD = predecessor.RECOVERY_GUARD_MARGIN_RAD
RECOVERY_MARGIN_EPSILON_RAD = predecessor.RECOVERY_MARGIN_EPSILON_RAD
CURRENT_EDGE_EPSILON_RAD = 1e-9


class CurrentEdgeRecoveryError(RuntimeError):
    """Raised when the current-edge candidate loses audit identity."""


@dataclass(frozen=True)
class CurrentEdgeRecoveryConfig:
    """Preserve v14/floor order and append a dynamic final candidate."""

    current_edge_margin_rad: float | None
    joint_indices: tuple[int, ...] = tuple(range(JOINT_COUNT))
    trigger_margin_rad: float = TRIGGER_MARGIN_RAD
    safe_margin_floor_rad: float = SAFE_MARGIN_FLOOR_RAD
    guard_solref: tuple[float, float] = GUARD_SOLREF
    guard_solimp: tuple[float, float, float, float, float] = GUARD_SOLIMP

    def __post_init__(self) -> None:
        edge = self.current_edge_margin_rad
        if (
            self.joint_indices != tuple(range(JOINT_COUNT))
            or self.trigger_margin_rad != TRIGGER_MARGIN_RAD
            or self.safe_margin_floor_rad != SAFE_MARGIN_FLOOR_RAD
            or self.guard_solref != GUARD_SOLREF
            or self.guard_solimp != GUARD_SOLIMP
            or (
                edge is not None
                and (
                    not np.isfinite(edge)
                    or edge <= SAFE_MARGIN_FLOOR_RAD
                    or edge >= min(BRAKE_MARGINS_RAD)
                    or edge == RECOVERY_GUARD_MARGIN_RAD
                )
            )
        ):
            raise ValueError("invalid current-edge recovery configuration")

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        suffix = (
            ()
            if self.current_edge_margin_rad is None
            else (self.current_edge_margin_rad,)
        )
        return (*BRAKE_MARGINS_RAD, RECOVERY_GUARD_MARGIN_RAD, *suffix)


def _candidate_for_margin(
    candidates: list[Any],
    margin: float,
) -> Mapping[str, Any] | None:
    matches = [
        row
        for row in candidates
        if isinstance(row, Mapping)
        and float(row["guard_margin_rad"]) == margin
    ]
    if len(matches) > 1:
        raise CurrentEdgeRecoveryError(
            "duplicate current-edge recovery candidate"
        )
    return matches[0] if matches else None


def _enrich_current_edge_audit(
    audit: dict[str, Any],
    *,
    configured_current_edge_margin_rad: float | None,
) -> None:
    candidates = audit.get("candidates")
    if not isinstance(candidates, list):
        raise CurrentEdgeRecoveryError("v15.1 audit lacks candidates")
    triggered = audit.get("triggered") is True
    baseline_eligible = sum(
        int(row.get("eligible") is True)
        for row in candidates
        if isinstance(row, Mapping)
        and float(row["guard_margin_rad"]) in BRAKE_MARGINS_RAD
    )
    floor = _candidate_for_margin(
        candidates, RECOVERY_GUARD_MARGIN_RAD
    )
    edge = (
        None
        if configured_current_edge_margin_rad is None
        else _candidate_for_margin(
            candidates, configured_current_edge_margin_rad
        )
    )
    if triggered and floor is None:
        raise CurrentEdgeRecoveryError(
            "triggered v15.1 screen lacks floor candidate"
        )
    if triggered and configured_current_edge_margin_rad is not None and edge is None:
        raise CurrentEdgeRecoveryError(
            "triggered v15.1 screen lacks configured current-edge candidate"
        )
    selected_margin = audit.get("selected_guard_margin_rad")
    floor_selected = bool(
        selected_margin is not None
        and float(selected_margin) == RECOVERY_GUARD_MARGIN_RAD
    )
    current_selected = bool(
        selected_margin is not None
        and configured_current_edge_margin_rad is not None
        and float(selected_margin)
        == configured_current_edge_margin_rad
    )
    recovery_selected = bool(floor_selected or current_selected)
    baseline_would_deadlock = bool(triggered and baseline_eligible == 0)
    prevented = bool(
        baseline_would_deadlock
        and recovery_selected
        and audit.get("deadlock") is False
    )
    audit.update(
        {
            "schema": BRAKE_AUDIT_SCHEMA,
            "v14_baseline_eligible_candidate_count": baseline_eligible,
            "v14_baseline_would_deadlock": baseline_would_deadlock,
            "current_edge_recovery_active": True,
            "current_edge_recovery_epsilon_rad": (
                CURRENT_EDGE_EPSILON_RAD
            ),
            "current_edge_recovery_configured_margin_rad": (
                configured_current_edge_margin_rad
            ),
            "current_edge_recovery_attempted": edge is not None,
            "current_edge_recovery_eligible": bool(
                edge is not None and edge.get("eligible") is True
            ),
            "current_edge_recovery_selected": current_selected,
            "floor_or_current_edge_recovery_selected": (
                recovery_selected
            ),
            "floor_or_current_edge_recovery_prevented_deadlock": (
                prevented
            ),
        }
    )


class MultiJointCurrentEdgeRecoveryEnvironment(
    predecessor.MultiJointFloorGuardRecoveryEnvironment
):
    """Append the strongest feasible guard inside the current gap state."""

    def _current_edge_margin(self) -> float | None:
        if not self._enabled or self._call_index < self._wait_steps:
            return None
        _robot, qidx, _vidx, limits = self._arrays()
        current = self._margin_matrix(qidx, limits)
        current_minimum = float(np.min(current))
        if not (
            SAFE_MARGIN_FLOOR_RAD + CURRENT_EDGE_EPSILON_RAD
            < current_minimum
            < min(BRAKE_MARGINS_RAD)
        ):
            return None
        candidate = current_minimum - CURRENT_EDGE_EPSILON_RAD
        if candidate == RECOVERY_GUARD_MARGIN_RAD:
            candidate -= CURRENT_EDGE_EPSILON_RAD
        return candidate

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        edge_margin = self._current_edge_margin()
        self._config = CurrentEdgeRecoveryConfig(edge_margin)
        transition = super().step(action)
        if len(self.observations) == before:
            return transition
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise CurrentEdgeRecoveryError(
                "v15.1 environment produced a non-object audit"
            )
        if audit.get("enabled") is True:
            _enrich_current_edge_audit(
                audit,
                configured_current_edge_margin_rad=edge_margin,
            )
        else:
            audit.update(
                {
                    "schema": BRAKE_AUDIT_SCHEMA,
                    "current_edge_recovery_active": False,
                    "current_edge_recovery_epsilon_rad": None,
                    "current_edge_recovery_configured_margin_rad": None,
                    "current_edge_recovery_attempted": False,
                    "current_edge_recovery_eligible": False,
                    "current_edge_recovery_selected": False,
                    "floor_or_current_edge_recovery_selected": False,
                    "floor_or_current_edge_recovery_prevented_deadlock": (
                        False
                    ),
                }
            )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointFloorGuardRecoveryEnvironment
    predecessor.MultiJointFloorGuardRecoveryEnvironment = (
        MultiJointCurrentEdgeRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointFloorGuardRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one current-edge recovery development episode."""

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
            "current_edge_recovery_active": l2_enabled,
            "current_edge_recovery_epsilon_rad": (
                CURRENT_EDGE_EPSILON_RAD if l2_enabled else None
            ),
            "current_edge_recovery_source_action_substitution": False,
            "current_edge_recovery_outcome_informed_successor": True,
            "current_edge_recovery_physical_authority_claim": False,
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
            "note": "Import through the frozen v15.1 development protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
