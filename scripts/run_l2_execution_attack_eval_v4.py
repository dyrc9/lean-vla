#!/usr/bin/env python3
"""Horizon-consistent pick-up contracts over the frozen v3 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.horizon_consistent_pick_up import (  # noqa: E402
    HORIZON_CHECKER_VERSION,
    HORIZON_EFFECT_OBSERVER_VERSION,
    HorizonConsistentSemanticPrefixEffectObserver,
    patched_semantic_wrapper_bindings,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v3 as v3  # noqa: E402
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v4"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v3 with temporary v3 checker/observer bindings for L1 arms."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    if not l1_enabled:
        payload = v3.run_episode(**kwargs)
    else:
        original_observer = base.SemanticPrefixEffectObserver
        base.SemanticPrefixEffectObserver = (
            HorizonConsistentSemanticPrefixEffectObserver
        )
        try:
            with patched_semantic_wrapper_bindings():
                payload = v3.run_episode(**kwargs)
        finally:
            base.SemanticPrefixEffectObserver = original_observer
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "horizon_consistent_pick_up_contract_active": bool(
                l1_enabled
            ),
            "semantic_local_checker_version": (
                HORIZON_CHECKER_VERSION if l1_enabled else None
            ),
            "semantic_effect_observer_version": (
                HORIZON_EFFECT_OBSERVER_VERSION
                if l1_enabled
                else None
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
                "Import run_episode through a separately frozen clean or "
                "attacked successor protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
