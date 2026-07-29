#!/usr/bin/env python3
"""Run the v12.4b warm-start-complete policy-prefix shadow successor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from proofalign.policy_prefix_shadow_warmstart_v12 import (  # noqa: E402
    capture_warmstart_policy_shadow_snapshot,
    restore_warmstart_policy_shadow_snapshot,
)
from scripts import run_fixed_policy_prefix_shadow_v12_qualification as base  # noqa: E402
from scripts.freeze_warmstart_policy_prefix_shadow_v12_qualification import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)
from scripts.generate_fixed_policy_prefix_v12_corpus import (  # noqa: E402
    CORPUS_PATH,
)


PILOT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_warmstart_policy_prefix_shadow_v12_"
    "engineering_pilot_20260729"
)
SUMMARY_SCHEMA = (
    "proofalign.warmstart-policy-prefix-shadow-v12-"
    "qualification-summary.v1"
)
_BASE_BUILD_SUMMARY = base.build_summary
_BASE_SNAPSHOT_PAYLOAD = base._snapshot_payload


def _snapshot_payload(assessment: Any) -> dict[str, Any]:
    return {
        **_BASE_SNAPSHOT_PAYLOAD(assessment),
        "qacc_warmstart_identity": (
            assessment.qacc_warmstart_identity
        ),
    }


def _warmstart_rate(rows: list[dict[str, Any]]) -> float:
    restores = [
        assessment
        for row in rows
        if row.get("valid") is True
        for assessment in row["restore_assessments"]
    ]
    return (
        sum(
            assessment["qacc_warmstart_identity"]
            for assessment in restores
        )
        / len(restores)
    )


def build_summary(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    pilot: bool,
) -> dict[str, Any]:
    predecessor = _BASE_BUILD_SUMMARY(
        config, rows, pilot=pilot
    )
    metrics = {
        **predecessor["metrics"],
        "qacc_warmstart_restore_identity_rate": (
            _warmstart_rate(rows)
        ),
    }
    if pilot:
        return {
            **predecessor,
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "warmstart_policy_prefix_shadow_v12_"
                "engineering_pilot_complete"
            ),
            "metrics": metrics,
        }
    conditions = {
        **predecessor["gate_conditions"],
        "qacc_warmstart_restore_identity_rate": (
            metrics["qacc_warmstart_restore_identity_rate"]
            >= config["gates"][
                "qacc_warmstart_restore_identity_rate_min"
            ]
        ),
    }
    passed = all(conditions.values())
    return {
        **predecessor,
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "warmstart_policy_prefix_shadow_v12_qualification_pass"
            if passed
            else "warmstart_policy_prefix_shadow_v12_qualification_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "failed_gates": [
            name for name, value in conditions.items() if not value
        ],
    }


def _install_successor() -> None:
    base.capture_policy_shadow_snapshot = (
        capture_warmstart_policy_shadow_snapshot
    )
    base.restore_policy_shadow_snapshot = (
        restore_warmstart_policy_shadow_snapshot
    )
    base._snapshot_payload = _snapshot_payload
    base.build_summary = build_summary


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _pilot_config() -> dict[str, Any]:
    corpus = _load(CORPUS_PATH)
    entry = next(
        row
        for row in corpus["formal_prefixes"]
        if row["base_pair_id"]
        == "obstacle_avoidance_human_task4_init17"
    )
    return {
        "schema": "proofalign.warmstart-policy-shadow-v12-pilot.v1",
        "protocol_id": "warmstart-engineering-pilot",
        "population": {
            "prefixes": [
                {
                    **entry,
                    "synthetic_joint_index": 1,
                    "synthetic_joint_side": "upper",
                }
            ]
        },
        "episode": {
            "control_frequency_hz": 20,
            "environment_horizon": 100000,
            "stabilization_steps": 10,
            "trigger_margin_rad": 0.1,
            "synthetic_injected_margin_rad": 0.05,
            "trajectory_tolerance_rad": 0.02,
        },
        "resource_gate": {
            "simulator_gpu_memory_used_mib_max_exclusive": 30000,
            "minimum_free_disk_gib": 10,
        },
        "claim_boundary": (
            "This two-case result-informed engineering pilot replays the "
            "sole v12.4a outlier with qacc_warmstart bound. It reads no "
            "outcome and is not qualification or fresh-policy evidence."
        ),
    }


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise RuntimeError(f"missing formal protocol: {PROTOCOL_PATH}")
    observed = _load(PROTOCOL_PATH)
    expected = build_protocol()
    if observed != expected or observed["schema"] != PROTOCOL_SCHEMA:
        raise RuntimeError("warm-start formal protocol is stale")
    return observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args(argv)
    _install_successor()
    if args.pilot:
        if args.gpu is None:
            parser.error("--pilot requires --gpu")
        if args.preflight or args.execute or args.validate_results:
            parser.error("--pilot cannot be combined with formal modes")
        payload = base._run(
            _pilot_config(),
            output_root=PILOT_ROOT,
            gpu=args.gpu,
            formal=False,
            protocol_path=None,
        )
    else:
        if sum(
            (args.preflight, args.execute, args.validate_results)
        ) != 1:
            parser.error(
                "choose one formal mode: --preflight, --execute, "
                "or --validate-results"
            )
        config = _verify_protocol()
        if args.preflight:
            payload = base._preflight(
                config,
                output_root=OUTPUT_ROOT,
                gpu=args.gpu,
                formal=True,
            )
        elif args.execute:
            if args.gpu is None:
                parser.error("--execute requires --gpu")
            payload = base._run(
                config,
                output_root=OUTPUT_ROOT,
                gpu=args.gpu,
                formal=True,
                protocol_path=PROTOCOL_PATH,
            )
        else:
            payload = base._validate(
                config, output_root=OUTPUT_ROOT, pilot=False
            )
    print(base._canonical(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
