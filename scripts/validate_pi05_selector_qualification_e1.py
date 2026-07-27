#!/usr/bin/env python3
"""Validate the frozen E1 result without loading TensorFlow, JAX, or a model.

The frozen runner serialized ``failed_gates`` from a tuple to a JSON list, so
its own post-load Python equality check rejects an otherwise identical
summary.  This independent validator preserves the preregistered runner bytes,
normalizes that one JSON container type, and then invokes all frozen checks.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from run_pi05_selector_qualification_e1 import (  # noqa: E402
    CHECKSUMS_PATH,
    PROTOCOL_PATH,
    RESULT_PATH,
    SelectorQualificationError,
    canonical_text,
    file_sha256,
    summarize,
    validate_protocol,
    validate_result,
)


def build_report() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    recomputed = summarize(
        protocol,
        result["rows"],
        result["repeat_rows"],
        result["ablation_rows"],
    )
    if canonical_text(result["summary"]) != canonical_text(recomputed):
        raise SelectorQualificationError(
            "E1 persisted summary differs from JSON-normalized recomputation"
        )
    normalized = copy.deepcopy(result)
    normalized["summary"]["failed_gates"] = tuple(
        normalized["summary"]["failed_gates"]
    )
    validate_result(protocol, normalized)
    expected_checksums = (
        f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
    )
    if CHECKSUMS_PATH.read_text(encoding="utf-8") != expected_checksums:
        raise SelectorQualificationError(
            "E1 result checksum manifest is stale"
        )
    return {
        "schema": "proofalign.pi05-selector-e1-validation.v1",
        "valid": True,
        "result_path": str(RESULT_PATH.relative_to(REPO_ROOT)),
        "result_sha256": file_sha256(RESULT_PATH),
        "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "frozen_runner_sha256": protocol["source"]["sha256"][
            "scripts/run_pi05_selector_qualification_e1.py"
        ],
        "serialization_normalization": {
            "field": "summary.failed_gates",
            "persisted_type": "json_array",
            "frozen_runtime_type": "tuple",
            "values_changed": False,
        },
        "classification": result["classification"],
        "summary": result["summary"],
        "decision": result["decision"],
        "no_outcome_boundary": {
            "training_performed": result["training_performed"],
            "actions_executed": result["actions_executed"],
            "outcomes_read": result["outcomes_read"],
            "simulator_created": result["simulator_created"],
        },
    }


def main() -> int:
    try:
        print(json.dumps(build_report(), indent=2, ensure_ascii=False))
        return 0
    except (
        KeyError,
        OSError,
        SelectorQualificationError,
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
