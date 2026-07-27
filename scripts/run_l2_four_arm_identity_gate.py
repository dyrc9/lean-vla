#!/usr/bin/env python3
"""Generate the no-dispatch shared-source-chunk L1/L2 four-arm gate."""

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

from proofalign.benchmark.confirmatory import file_sha256  # noqa: E402
from proofalign.benchmark.execution_attack_relay import (  # noqa: E402
    AttackPlacement,
    PublishedAffineFamily,
)
from proofalign.benchmark.l2_four_arm_identity import (  # noqa: E402
    IdentityLayerVerdict,
    L2FourArmIdentityCase,
    action_chunk_digest,
    evaluate_l2_four_arm_identity,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_l2_four_arm_identity_gate_v1.json"
)
SOURCE_CHUNK = (
    (0.1, -0.2, 0.3, -0.4, 0.5, -0.6, -1.0),
    (-0.2, 0.1, -0.4, 0.3, -0.6, 0.5, 1.0),
)
SOURCE_PATHS = (
    "src/proofalign/benchmark/execution_attack_relay.py",
    "src/proofalign/benchmark/l2_four_arm_identity.py",
    "src/proofalign/benchmark/semantic_four_arm_runner.py",
)


class L2FourArmGateError(RuntimeError):
    """Raised when committed four-arm component evidence is stale."""


def _cases() -> list[L2FourArmIdentityCase]:
    cases = [
        L2FourArmIdentityCase(
            unit_id="nominal",
            source_action_chunk=SOURCE_CHUNK,
        ),
        L2FourArmIdentityCase(
            unit_id="semantic_reject",
            source_action_chunk=SOURCE_CHUNK,
            semantic_verdict=IdentityLayerVerdict.REJECT,
        ),
        L2FourArmIdentityCase(
            unit_id="semantic_unknown",
            source_action_chunk=SOURCE_CHUNK,
            semantic_verdict=IdentityLayerVerdict.UNKNOWN,
        ),
    ]
    for family in (
        PublishedAffineFamily.SCALING,
        PublishedAffineFamily.REFLECTION,
        PublishedAffineFamily.SHEAR,
    ):
        for placement in AttackPlacement:
            cases.append(
                L2FourArmIdentityCase(
                    unit_id=f"{family.value}__{placement.value}",
                    source_action_chunk=SOURCE_CHUNK,
                    attack_family=family,
                    attack_placement=placement,
                )
            )
    return cases


def build_evidence() -> dict[str, Any]:
    results = [
        evaluate_l2_four_arm_identity(case) for case in _cases()
    ]
    source_digest = action_chunk_digest(SOURCE_CHUNK)
    source_identity_pass = all(
        result["source_chunk_identity_pass"]
        and result["source_action_chunk_digest"] == source_digest
        for result in results
    )
    treatment_identity_pass = all(
        result["treatment_switch_identity_pass"]
        for result in results
    )
    no_dispatch = all(
        result["dispatch_attempt_count"] == 0
        and result["policy_loaded"] is False
        and result["simulator_created"] is False
        and result["sink_created"] is False
        and result["outcomes_observed"] is False
        for result in results
    )
    complete = (
        source_identity_pass
        and treatment_identity_pass
        and no_dispatch
        and len(results) == 12
        and sum(result["arm_count"] for result in results) == 48
    )
    return {
        "schema": "proofalign.l2-four-arm-identity-gate.v1",
        "gate_id": "proofalign-l2-four-arm-identity-20260727-v1",
        "classification": (
            "l2_four_arm_component_identity_pass"
            if complete
            else "l2_four_arm_component_identity_failed"
        ),
        "complete": complete,
        "source_action_chunk_shape": (2, 7),
        "source_action_chunk_digest": source_digest,
        "case_count": len(results),
        "row_count": sum(
            result["arm_count"] for result in results
        ),
        "source_chunk_identity_pass": source_identity_pass,
        "treatment_switch_identity_pass": treatment_identity_pass,
        "dispatch_attempt_count": 0,
        "policy_loaded": False,
        "simulator_created": False,
        "sink_created": False,
        "outcomes_observed": False,
        "live_online_arm_switches_evidenced_by_this_gate": False,
        "four_arm_confirmatory_ready": False,
        "source_bindings": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in SOURCE_PATHS
        },
        "case_results": results,
        "claim_boundary": (
            "This outcome-free component gate proves that four treatment "
            "routes consume one byte-identical source action chunk and obey "
            "the expected L1/P1/P2/P3 routing truth table. It creates no "
            "policy, simulator, sink, dispatch, reward, success, or safety "
            "outcome. It does not by itself prove the separate live-runner "
            "wiring or authorize four-arm rollout."
        ),
    }


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        text = canonical_text(build_evidence())
        if args.check:
            if not args.output.is_file():
                raise L2FourArmGateError(
                    f"four-arm identity artifact is absent: {args.output}"
                )
            if args.output.read_text(encoding="utf-8") != text:
                raise L2FourArmGateError(
                    f"four-arm identity artifact is stale: {args.output}"
                )
            print(f"current: {args.output}")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(args.output)
        return 0
    except (
        KeyError,
        L2FourArmGateError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
