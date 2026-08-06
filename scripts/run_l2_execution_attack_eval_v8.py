#!/usr/bin/env python3
"""Contact-phase pick-up availability over the frozen v7 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.contact_phase_pick_up import (  # noqa: E402
    CONTACT_PHASE_CHECKER_VERSION,
    ContactPhaseReleaseH4CandidatePolicy,
    patched_contact_phase_wrapper_bindings,
)
from proofalign.horizon_consistent_release_prefix import (  # noqa: E402
    RELEASE_PREFIX_OBSERVER_VERSION,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v6 as v6  # noqa: E402
from scripts import run_l2_execution_attack_eval_v7 as v7  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v8"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v7 with only its checker and candidate policy advanced."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original_policy = v6.HorizonConsistentReleaseH4CandidatePolicy
    original_bindings = v7.patched_release_prefix_wrapper_bindings
    if l1_enabled:
        v6.HorizonConsistentReleaseH4CandidatePolicy = (
            ContactPhaseReleaseH4CandidatePolicy
        )
        v7.patched_release_prefix_wrapper_bindings = (
            patched_contact_phase_wrapper_bindings
        )
    try:
        payload = v7.run_episode(**kwargs)
    finally:
        v6.HorizonConsistentReleaseH4CandidatePolicy = original_policy
        v7.patched_release_prefix_wrapper_bindings = original_bindings
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "contact_phase_pick_up_active": bool(l1_enabled),
            "contact_phase_command_changed": False,
            "semantic_local_checker_version": (
                CONTACT_PHASE_CHECKER_VERSION
                if l1_enabled
                else None
            ),
            "semantic_effect_observer_version": (
                RELEASE_PREFIX_OBSERVER_VERSION
                if l1_enabled
                else None
            ),
            "hard_violation_gates_unchanged": bool(l1_enabled),
            "post_execution_effect_check_unchanged": bool(
                l1_enabled
            ),
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
                "Import run_episode through a separately frozen successor "
                "protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
