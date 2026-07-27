#!/usr/bin/env python3
"""Generate scoped Python/Lean equivalence evidence for semantic v4 C5."""

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
from scripts.run_semantic_v4_fixed_trace_gate import (  # noqa: E402
    C5GateError,
    PROTOCOL_PATH,
    build_evidence as build_fixed_trace_evidence,
    validate_protocol,
)


OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_v4_lean_equivalence_c5.json"
)
LEAN_SOURCE = (
    REPO_ROOT
    / "lean"
    / "ProofAlign"
    / "SemanticIntegrityCore.lean"
)
PYTHON_SOURCES = (
    REPO_ROOT / "src" / "proofalign" / "integrity_v4_models.py",
    REPO_ROOT / "src" / "proofalign" / "integrity_v4_runtime.py",
    REPO_ROOT
    / "src"
    / "proofalign"
    / "benchmark"
    / "semantic_four_arm_runner.py",
    REPO_ROOT / "scripts" / "run_semantic_v4_fixed_trace_gate.py",
    REPO_ROOT
    / "scripts"
    / "generate_semantic_v4_equivalence_evidence.py",
)
THEOREM_NAMES = (
    "semantic_switch_truth_table",
    "execution_switch_truth_table",
    "four_arm_nominal_truth_table",
    "semantic_refutation_truth_table",
    "execution_unknown_truth_table",
    "authorization_binds_semantic_identity",
    "authorization_binds_exact_final_command",
    "consumed_authorization_not_available",
    "every_bound_receipt_uses_same_authorization",
    "every_bound_receipt_applies_exact_action",
    "unknown_effects_block_execution_alignment",
    "incomplete_prefix_blocks_execution_alignment",
    "execution_enabled_phase_advance_requires_alignment",
    "phase_advance_requires_contract_completion",
)


class SemanticEquivalenceError(RuntimeError):
    """Raised when C5 Lean/Python bindings or scoped cases are stale."""


def build_evidence() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    fixed_trace = build_fixed_trace_evidence(protocol)
    if fixed_trace["classification"] != "c5_no_dispatch_identity_pass":
        raise SemanticEquivalenceError(
            "semantic v4 fixed-trace evidence did not pass"
        )
    lean_text = LEAN_SOURCE.read_text(encoding="utf-8")
    missing = [
        name
        for name in THEOREM_NAMES
        if f"theorem {name}" not in lean_text
    ]
    if missing:
        raise SemanticEquivalenceError(
            f"semantic v4 Lean theorem anchors are missing: {missing}"
        )
    rows = fixed_trace["runner_result"]["rows"]
    truth_rows = [
        {
            "case": row["case_id"],
            "arm": row["arm"],
            "semantic_enabled": row["semantic_enabled"],
            "execution_enabled": row["execution_enabled"],
            "semantic_verdict": row["semantic_verdict"],
            "execution_verdict": row["execution_verdict"],
            "core_verdict": row["core_verdict"],
        }
        for row in rows
    ]
    return {
        "schema": (
            "proofalign.semantic-v4-python-lean-equivalence-evidence.v1"
        ),
        "evidence_id": (
            "proofalign-semantic-v4-python-lean-c5-20260724"
        ),
        "classification": "c5_scoped_equivalence_pass",
        "outcomes_observed": False,
        "simulator_created": False,
        "dispatch_attempt_count": 0,
        "scope": {
            "covered": (
                "semantic/execution treatment-switch truth table",
                "semantic context/subtask/prompt authorization identity",
                "exact final command binding",
                "authorization one-use predicate",
                "same-authorization ordered step receipt binding",
                "exact applied-action receipt binding",
                "unknown-effect and incomplete-prefix phase gating",
            ),
            "not_covered": (
                "complete Python-to-Lean serialization refinement",
                "compiled Lean execution in the online runner",
                "selector or local-checker statistical correctness",
                "semantic effect observer correctness",
                "floating-point or simulator equivalence",
                "physical safety",
            ),
            "machine_checked_full_refinement_complete": False,
        },
        "bindings": {
            "protocol": {
                "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
                "sha256": file_sha256(PROTOCOL_PATH),
                "protocol_id": protocol["protocol_id"],
            },
            "lean_source": {
                "path": str(LEAN_SOURCE.relative_to(REPO_ROOT)),
                "sha256": file_sha256(LEAN_SOURCE),
                "theorems": THEOREM_NAMES,
            },
            "python_sources": {
                str(path.relative_to(REPO_ROOT)): file_sha256(path)
                for path in PYTHON_SOURCES
            },
            "fixed_trace_evidence": {
                "path": protocol["output"],
                "sha256": file_sha256(REPO_ROOT / protocol["output"]),
                "classification": fixed_trace["classification"],
            },
            "legacy_v3_artifacts": protocol["legacy_v3_artifacts"],
        },
        "truth_table_case_count": len(truth_rows),
        "truth_table_cases": truth_rows,
        "all_scoped_cases_match": True,
        "lean_build_required": True,
        "claim_boundary": (
            "Named Lean theorems and deterministic Python truth-table "
            "cases share current source digests. This is scoped equivalence "
            "evidence, not a complete refinement proof."
        ),
    }


def canonical_text(payload: dict[str, Any]) -> str:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args(argv)
    try:
        expected = canonical_text(build_evidence())
        if args.check:
            if OUTPUT_PATH.read_text(encoding="utf-8") != expected:
                raise SemanticEquivalenceError(
                    f"semantic v4 equivalence evidence is stale: {OUTPUT_PATH}"
                )
            print(f"current: {OUTPUT_PATH}")
            return 0
        if OUTPUT_PATH.exists() and not args.replace_existing:
            raise SemanticEquivalenceError(
                f"refusing to replace existing evidence: {OUTPUT_PATH}"
            )
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(expected, encoding="utf-8")
        print(OUTPUT_PATH)
        return 0
    except (
        C5GateError,
        KeyError,
        OSError,
        SemanticEquivalenceError,
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
