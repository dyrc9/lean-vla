#!/usr/bin/env python3
"""H4 release micro-block over the versioned v5 semantic runner."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.horizon_consistent_release_h4 import (  # noqa: E402
    HorizonConsistentReleaseH4CandidatePolicy,
    RELEASE_MICRO_BLOCK_STEPS,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    parse_semantic_subtask,
)
from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_execution_attack_eval_v2 as v2  # noqa: E402
from scripts import run_l2_execution_attack_eval_v3 as v3  # noqa: E402
from scripts import run_l2_execution_attack_eval_v4 as v4  # noqa: E402


RUNNER_VARIANT = "proofalign_l2_execution_attack_successor_v6"


class H4ReleaseSemanticPolicyWrapper(
    v2.TrustedSemanticPolicyWrapper
):
    """Compile only a release proposal into an exact four-action block."""

    def complete_policy_call(
        self,
        request: Any,
        *,
        nominal_command: Any,
        command_shape: Any,
        **kwargs: Any,
    ) -> Any:
        command = tuple(float(value) for value in nominal_command)
        shape = tuple(int(value) for value in command_shape)
        if (
            parse_semantic_subtask(
                request.artifact.selected_subtask
            ).verb
            == "release"
        ):
            if (
                len(shape) != 2
                or shape[1] != 7
                or shape[0] < RELEASE_MICRO_BLOCK_STEPS
            ):
                raise RuntimeError(
                    "release H4 wrapper requires an Hx7 source block"
                )
            command = command[
                : RELEASE_MICRO_BLOCK_STEPS * shape[1]
            ]
            shape = (RELEASE_MICRO_BLOCK_STEPS, shape[1])
        return super().complete_policy_call(
            request,
            nominal_command=command,
            command_shape=shape,
            **kwargs,
        )


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run v4 checker/observer bindings with the H4 release policy."""

    args: argparse.Namespace = kwargs["args"]
    l1_enabled, _l2_enabled = v1._arm_switches(args)
    original_policy = v3.OnlineProgressProjectionCandidatePolicy
    original_wrapper = v2.TrustedSemanticPolicyWrapper
    if l1_enabled:
        v3.OnlineProgressProjectionCandidatePolicy = (
            HorizonConsistentReleaseH4CandidatePolicy
        )
        v2.TrustedSemanticPolicyWrapper = (
            H4ReleaseSemanticPolicyWrapper
        )
    try:
        payload = v4.run_episode(**kwargs)
    finally:
        v3.OnlineProgressProjectionCandidatePolicy = original_policy
        v2.TrustedSemanticPolicyWrapper = original_wrapper
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "horizon_consistent_release_active": bool(l1_enabled),
            "release_authorized_action_block_steps": (
                RELEASE_MICRO_BLOCK_STEPS if l1_enabled else None
            ),
            "spatial_authorized_action_block_steps": (
                10 if l1_enabled else None
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
