#!/usr/bin/env python3
"""Validate the frozen smoke while normalizing JSON container types.

The frozen v1 runner wrote tuples as JSON arrays, then compared the retained
JSON object against an in-memory recomputation that still contained tuples in
the deterministic release-branch audit.  This validator leaves the frozen
runner, protocol, episode, evidence, and checksums unchanged; it normalizes the
recomputation through JSON before performing the exact comparison.
"""

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

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    run_four_arm_v4_l1_progress_projection_smoke as frozen,
)
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402


class ProgressProjectionSmokeV2ValidationError(RuntimeError):
    """Raised when frozen smoke evidence fails exact normalized validation."""


def normalize_json_types(value: Any) -> Any:
    """Return the exact value representable by canonical JSON."""

    return json.loads(json.dumps(value, sort_keys=True))


def validate(
    *,
    protocol_path: Path = frozen.DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    resolved = protocol_path.resolve()
    protocol = load_json_object(resolved)
    frozen.validate_protocol(protocol, protocol_path=resolved)
    output_root = frozen._output_root(protocol)
    p0b.read_checksums(output_root)
    retained = load_json_object(output_root / "smoke_evidence.json")
    episode_path = REPO_ROOT / retained["episode"]["path"]
    recomputed = frozen._build_evidence(
        protocol,
        protocol_path=resolved,
        output_root=output_root,
        episode_path=episode_path,
        preflight_report=retained["preflight"],
        device_mapping=retained["device_mapping"],
        release_gate=frozen._release_branch_gate(),
    )
    normalized = normalize_json_types(recomputed)
    if normalized != retained:
        raise ProgressProjectionSmokeV2ValidationError(
            "retained smoke evidence differs after JSON normalization"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    if (
        manifest.get("status") != "complete"
        or manifest.get("classification")
        != retained.get("classification")
        or retained.get("classification")
        != "l1_progress_projection_closed_loop_smoke_pass"
        or retained.get("smoke_pass") is not True
    ):
        raise ProgressProjectionSmokeV2ValidationError(
            "smoke terminal state is not the frozen pass"
        )
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-progress-projection-"
            "smoke-validation.v2"
        ),
        "classification": retained["classification"],
        "smoke_pass": True,
        "normalized_recomputation_matches": True,
        "checksums_valid": True,
        "observed": retained["observed"],
        "gate_results": retained["gate_results"],
        "claim_boundary": retained["claim_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=frozen.DEFAULT_PROTOCOL,
    )
    args = parser.parse_args(argv)
    print(
        canonical_text(validate(protocol_path=args.protocol)),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
