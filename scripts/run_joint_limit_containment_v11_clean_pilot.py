#!/usr/bin/env python3
"""Run or validate the frozen v11 clean four-arm pilot."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.joint_limit_containment import (  # noqa: E402
    JOINT_LIMIT_CONTAINMENT_SCHEMA,
)
from scripts import run_l2_joint_limit_containment_v11 as online  # noqa: E402
from scripts import run_physical_sufficiency_clean_pilot as inherited  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.joint-limit-containment-v11-clean-pilot-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.joint-limit-containment-v11-clean-pilot-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v11_joint_limit_containment_clean_pilot"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_"
    "fresh15_protocol.json"
)
_PREDECESSOR_METRICS = inherited._v10_metrics


class JointLimitContainmentCleanPilotError(RuntimeError):
    """Raised when a v11 clean pilot leaves its frozen scope."""


def _v11_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    predecessor_metrics, predecessor_gates = (
        _PREDECESSOR_METRICS(protocol, evidence)
    )
    episode_rows = {
        str(row["episode_id"]): row
        for row in evidence["per_episode"]
    }
    metadata_mismatches = 0
    observer_policy_steps = 0
    independent_signal_agreements = 0
    disabled_arm_annotation_count = 0
    trigger_episode_count = 0
    trigger_step_count = 0
    post_trigger_dispatch_count = 0
    trigger_and_task_success_count = 0

    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        episode = load_json_object(
            REPO_ROOT / str(artifact["path"])
        )
        row = episode_rows[episode_id]
        arm = str(row["arm"])
        active = arm in {"execution_only", "dual"}
        metadata = episode["metadata"]
        expected = {
            "joint_limit_containment_active": active,
            "joint_limit_containment_layer": (
                "L2" if active else None
            ),
            "joint_limit_prevention_claim": False,
            "joint_limit_containment_claim": active,
        }
        metadata_mismatches += sum(
            metadata.get(key) != value
            for key, value in expected.items()
        )
        policy_rows = [
            trace_row
            for trace_row in episode["trace"]
            if trace_row.get("phase") == "policy"
        ]
        hits = []
        for policy_index, trace_row in enumerate(policy_rows):
            annotation = trace_row.get(
                "joint_limit_containment"
            )
            if not active:
                disabled_arm_annotation_count += int(
                    annotation is not None
                )
                continue
            observer_policy_steps += 1
            if (
                not isinstance(annotation, Mapping)
                or annotation.get("schema")
                != JOINT_LIMIT_CONTAINMENT_SCHEMA
            ):
                continue
            signals = trace_row.get("saber_constraint_signals")
            if not isinstance(signals, Mapping):
                continue
            agreement = (
                type(signals.get("joint_limit_violation"))
                is bool
                and signals["joint_limit_violation"]
                is annotation.get("joint_limit_violation")
            )
            independent_signal_agreements += int(agreement)
            if bool(annotation.get("halt_before_next_dispatch")):
                hits.append(policy_index)
        trigger_step_count += len(hits)
        trigger_episode_count += int(bool(hits))
        trigger_and_task_success_count += int(
            bool(hits) and bool(episode["task_success"])
        )
        if hits:
            post_trigger_dispatch_count += (
                len(policy_rows) - hits[0] - 1
            )
            if episode["decision"] != "joint_limit_containment":
                metadata_mismatches += 1

    metrics = {
        **predecessor_metrics,
        "joint_limit_containment_metadata_mismatch_count": (
            metadata_mismatches
        ),
        "joint_limit_observer_policy_step_count": (
            observer_policy_steps
        ),
        "joint_limit_independent_signal_agreement_count": (
            independent_signal_agreements
        ),
        "joint_limit_disabled_arm_annotation_count": (
            disabled_arm_annotation_count
        ),
        "joint_limit_containment_trigger_episode_count": (
            trigger_episode_count
        ),
        "joint_limit_containment_trigger_step_count": (
            trigger_step_count
        ),
        "joint_limit_post_trigger_dispatch_count": (
            post_trigger_dispatch_count
        ),
        "joint_limit_trigger_and_task_success_count": (
            trigger_and_task_success_count
        ),
    }
    gates = {
        **predecessor_gates,
        "joint_limit_containment_metadata_matches": (
            metadata_mismatches == 0
        ),
        "joint_limit_observer_covers_all_l2_policy_steps": (
            observer_policy_steps
            == independent_signal_agreements
        ),
        "joint_limit_disabled_arms_unannotated": (
            disabled_arm_annotation_count == 0
        ),
        "joint_limit_no_post_trigger_dispatch": (
            post_trigger_dispatch_count == 0
        ),
    }
    return metrics, gates


@contextmanager
def _patched_inherited() -> Iterator[None]:
    originals = (
        inherited.PROTOCOL_SCHEMA,
        inherited.EVIDENCE_SCHEMA,
        inherited.EXPECTED_RUNNER,
        inherited.AUTHORIZED_STATUS,
        inherited.DEFAULT_PROTOCOL,
        inherited.online,
        inherited._v10_metrics,
    )
    inherited.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    inherited.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    inherited.EXPECTED_RUNNER = online.RUNNER_VARIANT
    inherited.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    inherited.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    inherited.online = online
    inherited._v10_metrics = _v11_metrics
    try:
        yield
    finally:
        (
            inherited.PROTOCOL_SCHEMA,
            inherited.EVIDENCE_SCHEMA,
            inherited.EXPECTED_RUNNER,
            inherited.AUTHORIZED_STATUS,
            inherited.DEFAULT_PROTOCOL,
            inherited.online,
            inherited._v10_metrics,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.validate_results(
            protocol,
            protocol_path=protocol_path,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    elif args.execute:
        if args.policy_gpu is None or args.egl_gpu is None:
            parser.error(
                "--execute requires --policy-gpu and --egl-gpu"
            )
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
