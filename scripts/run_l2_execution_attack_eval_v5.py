#!/usr/bin/env python3
"""Horizon-consistent release actuator layer over the versioned v4 runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.horizon_consistent_release import (  # noqa: E402
    HorizonConsistentReleaseCandidatePolicy,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v3 as v3  # noqa: E402
from scripts import run_l2_execution_attack_eval_v4 as v4  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v5"


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v4 with a temporary release candidate-policy successor."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original = v3.OnlineProgressProjectionCandidatePolicy
    if l1_enabled:
        v3.OnlineProgressProjectionCandidatePolicy = (
            HorizonConsistentReleaseCandidatePolicy
        )
    try:
        payload = v4.run_episode(**kwargs)
    finally:
        v3.OnlineProgressProjectionCandidatePolicy = original
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "horizon_consistent_release_active": bool(l1_enabled),
            "release_actuator_canonicalization": (
                "H10_gripper_open" if l1_enabled else None
            ),
            "release_cartesian_rotation_source": (
                "pi0.5_enveloped" if l1_enabled else None
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
