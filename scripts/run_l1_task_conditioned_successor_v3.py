#!/usr/bin/env python3
"""Install the bounded-retreat v3 L1 into the frozen v15 L2 stack."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.task_conditioned_l1 import AdvisoryAfterExactShadowChecker  # noqa: E402
from proofalign.task_conditioned_l1_v3 import (  # noqa: E402
    BoundedRetreatRecoveryCandidatePolicy,
    TASK_CONDITIONED_L1_V3_SCHEMA,
    TASK_CONDITIONED_L1_V3_VERSION,
    recovery_library_digest,
)
from scripts import run_l2_execution_attack_eval_v10 as v10  # noqa: E402


RUNNER_VARIANT = "proofalign_l1_task_conditioned_bounded_retreat_v3"


@contextmanager
def _patched_exact_checker_bindings() -> Iterator[None]:
    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = AdvisoryAfterExactShadowChecker
    wrapper.LOCAL_CHECKER_VERSION = "task-conditioned-bounded-retreat-3"
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


@contextmanager
def patched_task_conditioned_l1_v3_runtime(bridge: Any) -> Iterator[None]:
    original_policy = v10.PhysicalSufficiencyCandidatePolicy
    original_bindings = v10.patched_physical_sufficiency_wrapper_bindings

    class BoundBoundedRetreatRecoveryCandidatePolicy(
        BoundedRetreatRecoveryCandidatePolicy
    ):
        pass

    BoundBoundedRetreatRecoveryCandidatePolicy.bridge = bridge
    v10.PhysicalSufficiencyCandidatePolicy = BoundBoundedRetreatRecoveryCandidatePolicy
    v10.patched_physical_sufficiency_wrapper_bindings = _patched_exact_checker_bindings
    try:
        yield
    finally:
        v10.PhysicalSufficiencyCandidatePolicy = original_policy
        v10.patched_physical_sufficiency_wrapper_bindings = original_bindings


def annotate_payload(payload: dict[str, Any], *, l1_enabled: bool) -> dict[str, Any]:
    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "l1_task_conditioned_successor_active": bool(l1_enabled),
            "l1_task_conditioned_successor_schema": TASK_CONDITIONED_L1_V3_SCHEMA if l1_enabled else None,
            "l1_task_conditioned_successor_version": TASK_CONDITIONED_L1_V3_VERSION if l1_enabled else None,
            "l1_decision_domain": "allow_reject_abstain" if l1_enabled else None,
            "l1_nominal_full_link_shadow_active": bool(l1_enabled),
            "l1_held_object_contact_shadow_active": bool(l1_enabled),
            "l1_fresh_recovery_transaction_active": bool(l1_enabled),
            "l1_registered_transition_channels_only": bool(l1_enabled),
            "l1_unqualified_fallback_dispatch_allowed": False,
            "l1_bounded_retreat_library_digest": recovery_library_digest() if l1_enabled else None,
            "l1_policy_prompt_or_task_outcome_read_by_checker": False,
            "l1_llm_template_authoritative": False,
            "l1_legacy_point_distance_proxy_authoritative": False,
            "l1_successor_runner_variant": RUNNER_VARIANT if l1_enabled else None,
        }
    )
    payload["metadata"] = metadata
    return payload


__all__ = ["RUNNER_VARIANT", "annotate_payload", "patched_task_conditioned_l1_v3_runtime"]
