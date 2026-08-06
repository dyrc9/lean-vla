#!/usr/bin/env python3
"""v15.7 incremental adaptive recovery with short-circuit search."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_adaptive_force_recovery as predecessor,
)


force_attribution = predecessor.predecessor.predecessor.predecessor
_BASE_CANDIDATE_GROUPS = predecessor._candidate_groups
RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v15_7_"
    "incremental_adaptive_force_recovery"
)
BRAKE_AUDIT_SCHEMA = (
    "proofalign.predictive-hard-virtual-brake.v15.7."
    "incremental-adaptive-force-recovery.step"
)


class IncrementalAdaptiveForceRecoveryError(RuntimeError):
    """Raised when v15.7 cannot bind incremental recovery search."""


def _incremental_candidate_groups(
    config: predecessor.AdaptiveForceRecoveryConfig,
) -> tuple[tuple[dict[str, Any], ...], ...]:
    groups = _BASE_CANDIDATE_GROUPS(config)
    primary = groups[0]
    extended_group = groups[1]
    incremental = tuple((row,) for row in extended_group)
    return (primary, *incremental, *groups[2:])


def _selected_candidate(audit: dict[str, Any]) -> dict[str, Any] | None:
    selected_margin = audit.get("selected_guard_margin_rad")
    selected_profile = audit.get("selected_candidate_profile_id")
    rows = [
        row
        for row in audit.get("candidates", ())
        if selected_margin is not None
        and float(row["guard_margin_rad"]) == float(selected_margin)
        and row.get("candidate_profile_id") == selected_profile
    ]
    if len(rows) > 1:
        raise IncrementalAdaptiveForceRecoveryError(
            "v15.7 selected candidate identity is ambiguous"
        )
    return rows[0] if rows else None


def _adaptive_force_attribution(
    original: Any,
    audit: dict[str, Any],
    **kwargs: Any,
) -> None:
    selected = _selected_candidate(audit)
    extended_selected = bool(
        selected is not None
        and selected.get("candidate_profile_id")
        == "soft_extended_recovery"
    )
    if extended_selected:
        audit["floor_or_current_edge_recovery_selected"] = True
        audit["floor_or_current_edge_recovery_prevented_deadlock"] = bool(
            audit.get("v14_baseline_would_deadlock") is True
            and audit.get("deadlock") is False
        )
    original(audit, **kwargs)
    audit["incremental_extended_recovery_force_attribution_bound"] = bool(
        not extended_selected
        or audit.get("force_attribution_active") is True
        and audit.get("floor_or_current_edge_recovery_selected") is True
    )


class MultiJointIncrementalAdaptiveForceRecoveryEnvironment(
    predecessor.MultiJointAdaptiveForceRecoveryEnvironment
):
    """Evaluate intermediate recovery margins one at a time."""

    def step(self, action: Any) -> Any:
        original_groups = predecessor._candidate_groups
        original_enrich = force_attribution._enrich_force_attribution

        def enrich(audit: dict[str, Any], **kwargs: Any) -> None:
            _adaptive_force_attribution(
                original_enrich, audit, **kwargs
            )

        predecessor._candidate_groups = _incremental_candidate_groups
        force_attribution._enrich_force_attribution = enrich
        try:
            transition = super().step(action)
        finally:
            force_attribution._enrich_force_attribution = original_enrich
            predecessor._candidate_groups = original_groups
        audit = self.observations[-1]
        if not isinstance(audit, dict):
            raise IncrementalAdaptiveForceRecoveryError(
                "v15.7 environment produced a non-object audit"
            )
        candidates = audit.get("candidates", [])
        if not isinstance(candidates, list):
            raise IncrementalAdaptiveForceRecoveryError(
                "v15.7 environment lacks candidates"
            )
        extended_rows = [
            row
            for row in candidates
            if row.get("candidate_profile_id")
            == "soft_extended_recovery"
        ]
        extended_selected = bool(
            audit.get("selected_candidate_profile_id")
            == "soft_extended_recovery"
        )
        attribution_identity = bool(
            audit.get(
                "incremental_extended_recovery_force_attribution_bound"
            )
            is True
        )
        if not attribution_identity:
            raise IncrementalAdaptiveForceRecoveryError(
                "v15.7 extended recovery force attribution differs"
            )
        audit.update(
            {
                "schema": BRAKE_AUDIT_SCHEMA,
                "incremental_adaptive_force_recovery_active": bool(
                    audit.get("enabled") is True
                ),
                "incremental_extended_search_active": True,
                "incremental_extended_candidate_evaluated_count": len(
                    extended_rows
                ),
                "incremental_extended_search_short_circuit_identity": bool(
                    not extended_selected or len(extended_rows) >= 1
                ),
                "incremental_extended_recovery_force_attribution_identity": (
                    attribution_identity
                ),
                "incremental_search_change_source_action": False,
                "incremental_search_task_outcome_informed": False,
            }
        )
        return transition


@contextmanager
def _patched_predecessor_environment() -> Iterator[None]:
    original = predecessor.MultiJointAdaptiveForceRecoveryEnvironment
    predecessor.MultiJointAdaptiveForceRecoveryEnvironment = (
        MultiJointIncrementalAdaptiveForceRecoveryEnvironment
    )
    try:
        yield
    finally:
        predecessor.MultiJointAdaptiveForceRecoveryEnvironment = original


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one v15.7 episode without changing the source policy action."""

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
            "incremental_adaptive_force_recovery_active": l2_enabled,
            "incremental_extended_search_active": l2_enabled,
            "incremental_search_change_source_action": False,
            "incremental_search_outcome_informed_successor": True,
            "incremental_search_physical_authority_claim": False,
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
            "note": "Import through a separately frozen v15.7 protocol.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
