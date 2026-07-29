#!/usr/bin/env python3
"""Physical-sufficiency successor over the frozen v9 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.physical_sufficiency_semantic import (  # noqa: E402
    PHYSICAL_SUFFICIENCY_CHECKER_VERSION,
    PHYSICAL_SUFFICIENCY_EFFECT_POLICY_VERSION,
    PhysicalSufficiencyCandidatePolicy,
    PhysicalSufficiencyPrefixDispatchBoundary,
    patched_physical_sufficiency_wrapper_bindings,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v9 as v9  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v10"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Advance only v9's checker, effect partition, and audit identity."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original_policy = v9.RiskSelectiveCandidatePolicy
    original_bindings = v9.patched_risk_selective_wrapper_bindings
    original_boundary = v9.RiskSelectivePrefixDispatchBoundary
    if l1_enabled:
        v9.RiskSelectiveCandidatePolicy = (
            PhysicalSufficiencyCandidatePolicy
        )
        v9.patched_risk_selective_wrapper_bindings = (
            patched_physical_sufficiency_wrapper_bindings
        )
        v9.RiskSelectivePrefixDispatchBoundary = (
            PhysicalSufficiencyPrefixDispatchBoundary
        )
    try:
        payload = v9.run_episode(**kwargs)
    finally:
        v9.RiskSelectiveCandidatePolicy = original_policy
        v9.patched_risk_selective_wrapper_bindings = (
            original_bindings
        )
        v9.RiskSelectivePrefixDispatchBoundary = original_boundary
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "semantic_local_checker_version": (
                PHYSICAL_SUFFICIENCY_CHECKER_VERSION
                if l1_enabled
                else None
            ),
            "semantic_effect_policy_version": (
                PHYSICAL_SUFFICIENCY_EFFECT_POLICY_VERSION
                if l1_enabled
                else None
            ),
            "physical_sufficiency_screen_active": bool(l1_enabled),
            "articulation_state_unknown_advisory": bool(l1_enabled),
            "target_not_held_after_move_advisory": bool(l1_enabled),
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
                "Import run_episode through a separately frozen v10 "
                "qualification or clean-pilot protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
