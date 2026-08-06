#!/usr/bin/env python3
"""Prioritize current-edge before floor-edge recovery candidates."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v15_current_edge_recovery as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_2_"
    "multijoint_current_edge_priority_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.2."
    "multijoint-current-edge-priority-recovery.step"
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
CURRENT_EDGE_EPSILON_RAD = predecessor.CURRENT_EDGE_EPSILON_RAD


@dataclass(frozen=True)
class CurrentEdgePriorityRecoveryConfig(
    predecessor.CurrentEdgeRecoveryConfig
):
    """v14 candidates, current edge, then numerical-floor fallback."""

    @property
    def guard_margins_rad(self) -> tuple[float, ...]:
        middle = (
            ()
            if self.current_edge_margin_rad is None
            else (self.current_edge_margin_rad,)
        )
        return (*BRAKE_MARGINS_RAD, *middle, RECOVERY_GUARD_MARGIN_RAD)


class MultiJointCurrentEdgePriorityRecoveryEnvironment(
    predecessor.MultiJointCurrentEdgeRecoveryEnvironment
):
    """Use the current buffer before allowing floor-edge continuation."""

    def step(self, action: Any) -> Any:
        before = len(self.observations)
        original_config = predecessor.CurrentEdgeRecoveryConfig
        predecessor.CurrentEdgeRecoveryConfig = (
            CurrentEdgePriorityRecoveryConfig
        )
        try:
            transition = super().step(action)
        finally:
            predecessor.CurrentEdgeRecoveryConfig = original_config
        if len(self.observations) > before:
            audit = self.observations[-1]
            if isinstance(audit, dict):
                audit.update(
                    {
                        "schema": BRAKE_AUDIT_SCHEMA,
                        "current_edge_priority_recovery_active": bool(
                            audit.get("enabled") is True
                        ),
                        "recovery_candidate_priority": (
                            [
                                "v14_frozen_guard_margins",
                                "current_edge",
                                "floor_edge",
                            ]
                            if audit.get("enabled") is True
                            else None
                        ),
                    }
                )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointCurrentEdgeRecoveryEnvironment
    predecessor.MultiJointCurrentEdgeRecoveryEnvironment = (
        MultiJointCurrentEdgePriorityRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointCurrentEdgeRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.2 priority-recovery development episode."""

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
            "current_edge_priority_recovery_active": l2_enabled,
            "recovery_candidate_priority": (
                [
                    "v14_frozen_guard_margins",
                    "current_edge",
                    "floor_edge",
                ]
                if l2_enabled
                else None
            ),
            "current_edge_priority_source_action_substitution": False,
            "current_edge_priority_outcome_informed_successor": True,
            "current_edge_priority_physical_authority_claim": False,
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
            "note": "Import through the frozen v15.2 development protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
