#!/usr/bin/env python3
"""Release-prefix effect contracts over the H4 v6 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.horizon_consistent_release_prefix import (  # noqa: E402
    RELEASE_PREFIX_CHECKER_VERSION,
    RELEASE_PREFIX_OBSERVER_VERSION,
    ReleasePrefixSemanticEffectObserver,
    patched_release_prefix_wrapper_bindings,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v4 as v4  # noqa: E402
from scripts import run_l2_execution_attack_eval_v6 as v6  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v7"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v6 while replacing only v4's checker/observer injection."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original_observer = (
        v4.HorizonConsistentSemanticPrefixEffectObserver
    )
    original_bindings = v4.patched_semantic_wrapper_bindings
    if l1_enabled:
        v4.HorizonConsistentSemanticPrefixEffectObserver = (
            ReleasePrefixSemanticEffectObserver
        )
        v4.patched_semantic_wrapper_bindings = (
            patched_release_prefix_wrapper_bindings
        )
    try:
        payload = v6.run_episode(**kwargs)
    finally:
        v4.HorizonConsistentSemanticPrefixEffectObserver = (
            original_observer
        )
        v4.patched_semantic_wrapper_bindings = original_bindings
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "release_prefix_progress_contract_active": bool(
                l1_enabled
            ),
            "semantic_local_checker_version": (
                RELEASE_PREFIX_CHECKER_VERSION
                if l1_enabled
                else None
            ),
            "semantic_effect_observer_version": (
                RELEASE_PREFIX_OBSERVER_VERSION
                if l1_enabled
                else None
            ),
            "release_completion_guard_unchanged": bool(l1_enabled),
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
