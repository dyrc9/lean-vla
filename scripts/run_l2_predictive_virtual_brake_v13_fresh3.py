#!/usr/bin/env python3
"""Observation-plumbing-only successor for the v13 fresh3 repeat."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l2_execution_attack_eval as v1  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v13 as predecessor  # noqa: E402


RUNNER_VARIANT = (
    "proofalign_l2_predictive_hard_virtual_brake_v13_fresh3"
)
BRAKE_AUDIT_SCHEMA = predecessor.BRAKE_AUDIT_SCHEMA
BRAKE_MARGINS_RAD = predecessor.BRAKE_MARGINS_RAD
TRIGGER_MARGIN_RAD = predecessor.TRIGGER_MARGIN_RAD
SAFE_MARGIN_FLOOR_RAD = predecessor.SAFE_MARGIN_FLOOR_RAD
TARGET_JOINT_INDEX = predecessor.TARGET_JOINT_INDEX
TARGET_JOINT_SIDE = predecessor.TARGET_JOINT_SIDE
DEADLOCK_INFO_KEY = predecessor.DEADLOCK_INFO_KEY
GUARD_SOLREF = predecessor.GUARD_SOLREF
GUARD_SOLIMP = predecessor.GUARD_SOLIMP
PredictiveVirtualBrakeConfig = (
    predecessor.PredictiveVirtualBrakeConfig
)
PredictiveVirtualBrakeEnvironment = (
    predecessor.PredictiveVirtualBrakeEnvironment
)


class PredictiveVirtualBrakeFresh3Error(RuntimeError):
    """Raised when the observation-only successor leaves its scope."""


def _terminal_shadow_observation_deadlock_transition(
    _env: Any,
    template: Any,
    *,
    reason: str,
) -> Any:
    """Return a terminal-only shadow observation without another dispatch.

    The predecessor already restored the simulator/controller snapshot before
    entering this branch.  LIBERO's wrapper does not expose a callable
    observation getter there.  The discarded shadow transition nevertheless
    contains a correctly shaped observation.  It is safe to return that value
    only because ``done=True`` and the base runner immediately terminates:
    no policy consumes it and no additional ``env.step`` occurs.
    """

    if not isinstance(template, tuple) or len(template) not in {4, 5}:
        raise PredictiveVirtualBrakeFresh3Error(
            "cannot synthesize a fail-closed terminal transition"
        )
    info = dict(template[-1] or {})
    info[DEADLOCK_INFO_KEY] = reason
    info["proofalign_deadlock_observation_source"] = (
        "discarded_shadow_transition_terminal_only"
    )
    if len(template) == 4:
        return template[0], 0.0, True, info
    return template[0], 0.0, True, False, info


@contextmanager
def _patched_deadlock_transition() -> Iterator[None]:
    original = predecessor._deadlock_transition
    predecessor._deadlock_transition = (
        _terminal_shadow_observation_deadlock_transition
    )
    try:
        yield
    finally:
        predecessor._deadlock_transition = original


def _annotate_deadlock_observation_source(
    payload: Mapping[str, Any],
) -> None:
    for row in payload.get("trace", ()):
        audit = row.get("predictive_virtual_brake")
        if (
            isinstance(audit, dict)
            and audit.get("deadlock") is True
        ):
            audit["deadlock_observation_source"] = (
                "discarded_shadow_transition_terminal_only"
            )
            audit["deadlock_observation_policy_consumed"] = False


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run the predecessor with only its terminal observation path fixed."""

    with _patched_deadlock_transition():
        payload = predecessor.run_episode(**kwargs)
    _annotate_deadlock_observation_source(payload)
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": RUNNER_VARIANT,
            "predictive_virtual_brake_fresh3_successor": True,
            "fresh3_scientific_parameters_changed": False,
            "deadlock_observation_source": (
                "discarded_shadow_transition_terminal_only"
            ),
            "deadlock_observation_policy_consumed": False,
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
                "Import run_episode through the separately frozen fresh3 "
                "full-repeat protocol."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
