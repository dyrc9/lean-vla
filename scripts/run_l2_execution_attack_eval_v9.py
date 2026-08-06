#!/usr/bin/env python3
"""Risk-selective nominal-first successor over the frozen v8 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.risk_selective_semantic import (  # noqa: E402
    RISK_SELECTIVE_CHECKER_VERSION,
    RISK_SELECTIVE_EFFECT_POLICY_VERSION,
    RiskSelectiveCandidatePolicy,
    RiskSelectivePrefixDispatchBoundary,
    RiskSelectiveSemanticPolicyWrapper,
    patched_risk_selective_wrapper_bindings,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v6 as v6  # noqa: E402
from scripts import run_l2_execution_attack_eval_v8 as v8  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v9"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v8 with only the risk-selective successor bindings advanced."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original_policy = v8.ContactPhaseReleaseH4CandidatePolicy
    original_bindings = v8.patched_contact_phase_wrapper_bindings
    original_wrapper = v6.H4ReleaseSemanticPolicyWrapper
    original_boundary = v1.SingleUsePrefixDispatchBoundary
    if l1_enabled:
        v8.ContactPhaseReleaseH4CandidatePolicy = (
            RiskSelectiveCandidatePolicy
        )
        v8.patched_contact_phase_wrapper_bindings = (
            patched_risk_selective_wrapper_bindings
        )
        # v6 installs this symbol into v2 immediately before v2 synthesizes
        # its geometry-aware runtime wrapper. Patching the base module here
        # would be overwritten by that successor chain.
        v6.H4ReleaseSemanticPolicyWrapper = (
            RiskSelectiveSemanticPolicyWrapper
        )
        v1.SingleUsePrefixDispatchBoundary = (
            RiskSelectivePrefixDispatchBoundary
        )
    try:
        payload = v8.run_episode(**kwargs)
    finally:
        v8.ContactPhaseReleaseH4CandidatePolicy = original_policy
        v8.patched_contact_phase_wrapper_bindings = original_bindings
        v6.H4ReleaseSemanticPolicyWrapper = original_wrapper
        v1.SingleUsePrefixDispatchBoundary = original_boundary
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "risk_selective_semantic_active": bool(l1_enabled),
            "semantic_local_checker_version": (
                RISK_SELECTIVE_CHECKER_VERSION
                if l1_enabled
                else None
            ),
            "semantic_effect_policy_version": (
                RISK_SELECTIVE_EFFECT_POLICY_VERSION
                if l1_enabled
                else None
            ),
            "full_task_policy_prompt_preserved": bool(l1_enabled),
            "nominal_action_noninterference_active": bool(
                l1_enabled
            ),
            "soft_semantic_constraints_advisory": bool(l1_enabled),
            "soft_effect_miss_replan_active": bool(l1_enabled),
            "observed_violation_fail_closed": bool(l1_enabled),
            "execution_integrity_fail_closed": bool(l1_enabled),
            "post_execution_effect_check_unchanged": False,
            "contact_phase_pick_up_active": False,
            "contact_phase_command_changed": False,
            "horizon_consistent_release_active": False,
            "release_prefix_progress_contract_active": False,
            "release_completion_guard_unchanged": False,
            "online_progress_projection_active": False,
            "progress_projection_command_changed": False,
            "h4_release_chunk_active": False,
            "hard_violation_gates_unchanged": False,
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
                "Import run_episode through a separately frozen v9 "
                "qualification or clean-pilot protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
